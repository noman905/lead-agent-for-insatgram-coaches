import os
import sys
import datetime
import traceback
import gspread
import config

from test_sheet import ensure_sheet_structure, get_control_jobs, update_job_status, append_run_log_entry, append_error_log_entry
from google_scraper import fetch_instagram_profiles_from_google, build_search_query
from instagram_scraper import fetch_instagram_profile_details, filter_and_clean_profile_urls, extract_username_from_url, clean_and_validate_instagram_url
from leads_writer import get_existing_usernames, write_new_leads
from email_notifier import send_completion_notification, send_failure_notification



def process_single_job(sh, control_sheet, job: dict) -> bool:
    row_num = job["row_number"]
    niche = job["niche"]
    state = job["state"]
    pages_str = job["pages"]

    try:
        pages = int(pages_str) if pages_str and pages_str.isdigit() else 1
    except ValueError:
        pages = 1

    print("\n" + "=" * 70)
    print(f" [RUN] PROCESSING JOB: Row {row_num} | Niche='{niche}' | State='{state}' | Pages={pages}")
    print("=" * 70)

    # 1. Update status to 'Running' in Google Sheet Control tab
    update_job_status(control_sheet, row_num, "Running")

    try:
        # 2. Step 2: Google Search Scraper
        query_string, raw_urls = fetch_instagram_profiles_from_google(
            niche=niche,
            state=state,
            pages=pages,
            api_token=config.APIFY_API_TOKEN
        )
        total_raw_found = len(raw_urls)

        # Check for zero results
        if total_raw_found == 0:
            err_msg = "Google Search actor returned 0 results for this query."
            print(f"[WARNING] {err_msg}")
            update_job_status(control_sheet, row_num, "Failed")
            append_run_log_entry(
                sh=sh,
                niche=niche,
                state=state,
                pages_searched=pages,
                total_profiles=0,
                leads_added=0,
                duplicates_skipped=0,
                garbage_skipped=0,
                status="Failed",
                notes=err_msg
            )
            # Send failure email for zero results
            send_failure_notification(niche, state, err_msg)
            return False

        # 3. Filter URLs for direct profiles and deduplicate against existing sheet handles BEFORE scraping
        clean_profile_urls = []
        invalid_extraction_urls = []

        for url in raw_urls:
            is_valid, clean_u, reason = clean_and_validate_instagram_url(url)
            if is_valid:
                clean_profile_urls.append(clean_u)
            else:
                invalid_extraction_urls.append((url, reason))
                append_error_log_entry(
                    sh=sh,
                    niche=niche,
                    state=state,
                    invalid_url=url,
                    error_reason=f"invalid URL format, skipped enrichment ({reason})",
                    stage="Extraction"
                )

        garbage_skipped = total_raw_found - len(clean_profile_urls)

        existing_handles = get_existing_usernames(sh)
        urls_to_scrape = []
        pre_duplicates_count = 0

        for url in clean_profile_urls:
            handle = extract_username_from_url(url).lower()
            if handle in existing_handles:
                pre_duplicates_count += 1
                print(f"    - [CREDIT SAVED] Skipping handle @{handle} before scraping (already in Leads tab).")
            else:
                # Pre-enrichment regex check
                is_valid, clean_u, reason = clean_and_validate_instagram_url(url)
                if is_valid:
                    urls_to_scrape.append(clean_u)
                else:
                    print(f"    - [SKIPPED ENRICHMENT] Invalid URL format for '{url}': {reason}")
                    append_error_log_entry(
                        sh=sh,
                        niche=niche,
                        state=state,
                        invalid_url=url,
                        error_reason=f"invalid URL format, skipped enrichment ({reason})",
                        stage="Pre-Enrichment"
                    )

        print(f"[+] Total raw Google URLs:        {total_raw_found}")
        print(f"[+] Valid profile URLs:          {len(clean_profile_urls)}")
        print(f"[+] Non-profile/garbage links:   {garbage_skipped}")
        print(f"[+] Pre-known duplicate handles: {pre_duplicates_count}")
        print(f"[+] Profiles to scrape via Apify: {len(urls_to_scrape)}")
        print("-" * 70)

        # 4. Step 3: Instagram Profile Scraper
        scraped_profiles = []
        if urls_to_scrape:
            scraped_profiles = fetch_instagram_profile_details(
                profile_urls=urls_to_scrape,
                api_token=config.APIFY_API_TOKEN
            )

        # 5. Step 4: Write New Leads to Google Sheet Leads tab
        leads_added, write_duplicates, written_leads = write_new_leads(
            sh=sh,
            profiles=scraped_profiles,
            niche=niche,
            state=state
        )


        total_duplicates_skipped = pre_duplicates_count + write_duplicates

        # 6. Update Status to 'Done' in Control tab
        update_job_status(control_sheet, row_num, "Done")

        # 7. Append Audit Log entry in 'Run Log' tab
        issues = [
            f"@{p['username']} ({p.get('scrape_status', 'Issue')})"
            for p in scraped_profiles
            if p.get('scrape_status') and p.get('scrape_status') != 'Success'
        ]
        notes_summary = f"Successfully processed {leads_added} new lead(s)."
        if issues:
            notes_summary += f" Profile notes: {', '.join(issues[:5])}"

        append_run_log_entry(
            sh=sh,
            niche=niche,
            state=state,
            pages_searched=pages,
            total_profiles=total_raw_found,
            leads_added=leads_added,
            duplicates_skipped=total_duplicates_skipped,
            garbage_skipped=garbage_skipped,
            status="Done",
            notes=notes_summary
        )

        # 8. Step 5: Send Completion Email Notification
        print(f"[+] Sending completion email notification for [{niche} / {state}]...")
        send_completion_notification(
            niche=niche,
            state=state,
            leads_added=leads_added,
            duplicates_skipped=total_duplicates_skipped,
            total_found=total_raw_found,
            notes=notes_summary
        )

        print("\n" + "=" * 70)
        print(f" [SUCCESS] JOB COMPLETED (Row {row_num})")
        print(f"  * Niche / State:       {niche} / {state}")
        print(f"  * Total URLs Found:   {total_raw_found}")
        print(f"  * New Leads Wrote:    {leads_added}")
        print(f"  * Duplicates Skipped: {total_duplicates_skipped}")
        print(f"  * Status:             Done")
        print("=" * 70)
        return True

    except Exception as err:
        err_msg = str(err)
        print(f"\n[ERROR] Job execution failed for Row {row_num} [{niche} / {state}]: {err_msg}")
        traceback.print_exc()

        # Mark Status as 'Failed' in Control tab
        update_job_status(control_sheet, row_num, "Failed")

        # Record failure in 'Run Log' tab
        append_run_log_entry(
            sh=sh,
            niche=niche,
            state=state,
            pages_searched=pages,
            total_profiles=0,
            leads_added=0,
            duplicates_skipped=0,
            garbage_skipped=0,
            status="Failed",
            notes=f"Error: {err_msg[:200]}"
        )

        # Send failure alert email
        send_failure_notification(niche, state, err_msg)
        return False


def run_agent():
    print("=" * 70)
    print(" INSTAGRAM LEAD GENERATION AGENT - MAIN RUNNER")
    print("=" * 70)

    service_account_file = config.GOOGLE_SERVICE_ACCOUNT_FILE
    sheet_id = config.GOOGLE_SHEET_ID
    apify_token = config.APIFY_API_TOKEN

    if not os.path.exists(service_account_file):
        print(f"[ERROR] Service account file '{service_account_file}' not found.")
        sys.exit(1)

    if not apify_token or apify_token.strip() in ("", "your_apify_api_token_here"):
        print("[ERROR] APIFY_API_TOKEN is missing or not configured in .env file.")
        sys.exit(1)

    # 1. Connect to Google Sheets
    print(f"[+] Connecting to Google Sheets API ({service_account_file})...")
    gc = gspread.service_account(filename=service_account_file)
    try:
        sh = gc.open_by_key(sheet_id)
    except Exception:
        sh = gc.open(sheet_id)

    print(f"[SUCCESS] Connected to spreadsheet: '{sh.title}'")
    ensure_sheet_structure(sh)
    print("-" * 70)

    # 2. Read Queue Jobs from Control tab
    control_sheet = sh.worksheet("Control")
    all_jobs = get_control_jobs(control_sheet)

    pending_jobs = [j for j in all_jobs if j["status"].strip().lower() == "pending"]

    print(f"[+] Total Jobs in Control Queue: {len(all_jobs)}")
    print(f"[+] Pending Jobs to Process:     {len(pending_jobs)}")

    if not pending_jobs:
        print("\n[NOTE] No 'Pending' jobs found in the Control queue tab.")
        print("       Add rows with Status = 'Pending' in your Google Sheet to run search jobs.")
        print("=" * 70)
        return

    # 3. Process Pending Jobs sequentially
    success_count = 0
    failed_count = 0

    for idx, job in enumerate(pending_jobs, start=1):
        print(f"\n>>> Processing Queue Item {idx} of {len(pending_jobs)} <<<")
        success = process_single_job(sh, control_sheet, job)
        if success:
            success_count += 1
        else:
            failed_count += 1

    print("\n" + "=" * 70)
    print(" [FINISHED] ALL QUEUE JOBS PROCESSED")
    print(f"  * Total Pending Processed: {len(pending_jobs)}")
    print(f"  * Successful Runs:        {success_count}")
    print(f"  * Failed Runs:            {failed_count}")
    print("=" * 70)


if __name__ == "__main__":
    run_agent()
