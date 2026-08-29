import os
import sys
import datetime
import traceback
import gspread
import config

from test_sheet import ensure_sheet_structure, get_control_jobs, update_job_status, append_run_log_entry
from google_scraper import fetch_instagram_profiles_from_google
from instagram_scraper import fetch_instagram_profile_details
from leads_writer import write_new_leads
from email_notifier import send_summary_notification, send_apify_credits_alert


class ApifyCreditsExhaustedError(Exception):
    """Raised when Apify credits or usage limits are exhausted."""
    pass


def is_apify_credit_exhausted(err: Exception | str) -> bool:
    """
    Checks if an exception or error message indicates that Apify credits
    or compute unit usage limits are exhausted.
    """
    if isinstance(err, ApifyCreditsExhaustedError):
        return True

    # 1. Check HTTP status code on ApifyApiError / ApifyClientError
    status_code = getattr(err, "status_code", None)
    if status_code == 402:  # 402 Payment Required
        return True

    # 2. Check error type attribute from Apify response payload
    err_type = str(getattr(err, "type", "")).lower()
    if any(k in err_type for k in ["usage-limit", "monthly-usage", "credit", "payment-required", "quota", "limit-exceeded"]):
        return True

    # 3. Check text string representations
    msg = str(err).lower()
    credit_indicators = [
        "monthly usage limit exceeded",
        "usage limit exceeded",
        "usage limit",
        "credits exhausted",
        "out of credit",
        "out of credits",
        "insufficient credit",
        "not enough credit",
        "credit limit",
        "monthly-usage-limit-exceeded",
        "usage-limit-exceeded",
        "payment required",
        "compute units limit",
        "exceeded your usage limit",
        "exceeded its free usage limit",
        "reached its monthly usage limit",
        "reached your monthly usage limit",
        "account has run out of credit",
        "plan limit exceeded",
        "quota exceeded",
        "credits are out",
        "exceeded remaining usage"
    ]
    return any(indicator in msg for indicator in credit_indicators)


def process_single_job(sh, control_sheet, job: dict) -> dict:
    """
    Executes a single search & scrape job.
    Returns a dict with:
      - 'status': 'Done' or 'Failed'
      - 'row_number': int
      - 'niche': str
      - 'state': str
      - 'leads_added': int (if Done)
      - 'duplicates_skipped': int (if Done)
      - 'total_found': int (if Done)
      - 'error': str (if Failed)
    Raises ApifyCreditsExhaustedError if Apify credits are out.
    """
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
        # 2. Step 2: Google Search Scraper (includes retry, filtering, normalization, dedup, cross-check)
        query_string, status_msg, clean_urls = fetch_instagram_profiles_from_google(
            niche=niche,
            state=state,
            pages=pages,
            api_token=config.APIFY_API_TOKEN,
            sh=sh
        )
        total_raw_found = len(clean_urls)

        # Check if zero new URLs to scrape
        if total_raw_found == 0:
            if "Done" in status_msg:
                note_msg = "0 new unique profiles (all existing in Leads tab or filtered)"
                print(f"[+] {note_msg}")
                update_job_status(control_sheet, row_num, status_msg)
                append_run_log_entry(
                    sh=sh,
                    niche=niche,
                    state=state,
                    pages_searched=pages,
                    total_profiles=0,
                    leads_added=0,
                    duplicates_skipped=0,
                    garbage_skipped=0,
                    status="Done",
                    notes=note_msg
                )
                return {
                    "status": "Done",
                    "row_number": row_num,
                    "niche": niche,
                    "state": state,
                    "leads_added": 0,
                    "duplicates_skipped": 0,
                    "total_found": 0
                }
            else:
                err_msg = "Google Search actor returned 0 results after retry"
                print(f"[WARNING] {err_msg}")
                update_job_status(control_sheet, row_num, f"Failed: {err_msg}")
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
                return {
                    "status": "Failed",
                    "row_number": row_num,
                    "niche": niche,
                    "state": state,
                    "error": err_msg
                }


        print(f"[+] Clean new URLs to scrape via Apify: {total_raw_found}")
        print("-" * 70)

        # 3. Step 3: Instagram Profile Scraper
        scraped_profiles = []
        if clean_urls:
            scraped_profiles = fetch_instagram_profile_details(
                profile_urls=clean_urls,
                api_token=config.APIFY_API_TOKEN
            )

        # 4. Step 4: Write New Leads to Google Sheet Leads tab
        leads_added, write_duplicates, written_leads = write_new_leads(
            sh=sh,
            profiles=scraped_profiles,
            niche=niche,
            state=state
        )

        total_duplicates_skipped = write_duplicates

        # 5. Update Status in Control tab
        update_job_status(control_sheet, row_num, status_msg)

        # 6. Append Audit Log entry in 'Run Log' tab
        issues = [
            f"@{p['username']} ({p.get('scrape_status', 'Issue')})"
            for p in scraped_profiles
            if p.get('scrape_status') and p.get('scrape_status') != 'Success'
        ]
        notes_summary = f"[{status_msg}] Successfully processed {leads_added} new lead(s)."
        if issues:
            notes_summary += f" Profile notes: {', '.join(issues[:5])}"

        append_run_log_entry(
            sh=sh,
            niche=niche,
            state=state,
            pages_searched=pages,
            total_profiles=len(scraped_profiles),
            leads_added=leads_added,
            duplicates_skipped=total_duplicates_skipped,
            garbage_skipped=len(clean_urls) - len(scraped_profiles),
            status=status_msg.split(' (')[0],  # "Done" or "Incomplete"
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

        return {
            "status": "Done",
            "row_number": row_num,
            "niche": niche,
            "state": state,
            "leads_added": leads_added,
            "duplicates_skipped": total_duplicates_skipped,
            "total_found": total_raw_found
        }

    except Exception as err:
        err_msg = str(err)
        # Check if error is due to Apify credits exhaustion
        if is_apify_credit_exhausted(err):
            print(f"\n[CRITICAL] Apify credits exhausted on Row {row_num} [{niche} / {state}]: {err_msg}")
            # Mark the current row as Failed (Credit limit exceeded) instead of Pending
            update_job_status(control_sheet, row_num, "Failed (Credit limit exceeded)")
            append_run_log_entry(
                sh=sh,
                niche=niche,
                state=state,
                pages_searched=pages,
                total_profiles=0,
                leads_added=0,
                duplicates_skipped=0,
                garbage_skipped=0,
                status="Failed (Credits Out)",
                notes=f"Halted: Apify credits exhausted ({err_msg[:150]})"
            )
            raise ApifyCreditsExhaustedError(err_msg)

        print(f"\n[ERROR] Job execution failed for Row {row_num} [{niche} / {state}]: {err_msg}")
        traceback.print_exc()

        # Mark Status as 'Failed: <reason>' in Control tab
        update_job_status(control_sheet, row_num, f"Failed: {err_msg}")

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

        return {
            "status": "Failed",
            "row_number": row_num,
            "niche": niche,
            "state": state,
            "error": err_msg
        }


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
    done_jobs = []
    failed_jobs = []
    credits_exhausted = False
    credit_exhaustion_job = None
    credit_exhaustion_reason = ""

    for idx, job in enumerate(pending_jobs, start=1):
        print(f"\n>>> Processing Queue Item {idx} of {len(pending_jobs)} <<<")
        try:
            result = process_single_job(sh, control_sheet, job)
            if result.get("status") == "Done":
                done_jobs.append(result)
            else:
                failed_jobs.append(result)
                print(f"[-] Row {job['row_number']} failed ({result.get('error')}). Continuing to next pending job...")
        except ApifyCreditsExhaustedError as ce:
            credits_exhausted = True
            credit_exhaustion_job = job
            credit_exhaustion_reason = str(ce)
            print("\n" + "!" * 70)
            print(" [CRITICAL] APIFY CREDITS EXHAUSTED — STOPPING PIPELINE IMMEDIATELY")
            print(" Remaining jobs in queue left as 'Pending'.")
            print("!" * 70)
            break
        except Exception as unexpected_err:
            if is_apify_credit_exhausted(unexpected_err):
                credits_exhausted = True
                credit_exhaustion_job = job
                credit_exhaustion_reason = str(unexpected_err)
                try:
                    update_job_status(control_sheet, job["row_number"], "Failed (Credit limit exceeded)")
                except Exception:
                    pass
                print("\n" + "!" * 70)
                print(" [CRITICAL] APIFY CREDITS EXHAUSTED — STOPPING PIPELINE IMMEDIATELY")
                print("!" * 70)
                break
            else:
                err_str = str(unexpected_err)
                try:
                    update_job_status(control_sheet, job["row_number"], f"Failed: {err_str}")
                except Exception:
                    pass
                failed_jobs.append({
                    "status": "Failed",
                    "row_number": job["row_number"],
                    "niche": job["niche"],
                    "state": job["state"],
                    "error": err_str
                })
                print(f"[-] Row {job['row_number']} failed ({err_str}). Continuing to next pending job...")

    # 4. Handle Pipeline Exit & Email Notifications
    if credits_exhausted:
        niche = credit_exhaustion_job.get("niche", "") if credit_exhaustion_job else ""
        state = credit_exhaustion_job.get("state", "") if credit_exhaustion_job else ""
        print("\n[+] Sending urgent alert email: 'Apify credits are out — pipeline stopped.'...")
        send_apify_credits_alert(niche=niche, state=state, reason=credit_exhaustion_reason)

        print("\n" + "=" * 70)
        print(" [STOPPED] PIPELINE HALTED (APIFY CREDITS EXHAUSTED)")
        print(f"  * Jobs Completed (Done): {len(done_jobs)}")
        print(f"  * Jobs Failed:           {len(failed_jobs)}")
        print(f"  * Remaining Jobs:        Preserved as 'Pending'")
        print("=" * 70)
        return

    total_leads_added = sum(j.get("leads_added", 0) for j in done_jobs)

    print("\n" + "=" * 70)
    print(" [FINISHED] ALL QUEUE JOBS PROCESSED")
    print(f"  * Total Pending Processed: {len(pending_jobs)}")
    print(f"  * Successful Runs (Done): {len(done_jobs)}")
    print(f"  * Failed Runs:            {len(failed_jobs)}")
    print(f"  * Total New Leads Added:  {total_leads_added}")
    print("=" * 70)

    # 5. Send one consolidated summary email at the end of all jobs
    if done_jobs or failed_jobs:
        print("[+] Sending end-of-run consolidated summary email...")
        send_summary_notification(
            done_jobs=done_jobs,
            failed_jobs=failed_jobs,
            total_leads_added=total_leads_added
        )


if __name__ == "__main__":
    run_agent()
