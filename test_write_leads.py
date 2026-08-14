import os
import sys
import datetime
import gspread
import config
from test_sheet import ensure_sheet_structure
from leads_writer import get_existing_usernames, write_new_leads

def run_isolated_leads_writer_test():
    print("=" * 70)
    print(" [TEST] STEP 4: DEDUPLICATION & LEADS SHEET WRITER (ISOLATION TEST)")
    print("=" * 70)

    service_account_file = config.GOOGLE_SERVICE_ACCOUNT_FILE
    sheet_id = config.GOOGLE_SHEET_ID

    if not os.path.exists(service_account_file):
        print(f"[ERROR] Service account file '{service_account_file}' not found.")
        sys.exit(1)

    print(f"[1/3] Connecting to Google Sheets API ({service_account_file})...")
    gc = gspread.service_account(filename=service_account_file)
    try:
        sh = gc.open_by_key(sheet_id)
    except Exception:
        sh = gc.open(sheet_id)

    print(f"[SUCCESS] Connected to spreadsheet: '{sh.title}'")
    ensure_sheet_structure(sh)
    print("-" * 70)

    # Read existing usernames
    existing_handles = get_existing_usernames(sh)
    print(f"[+] Loaded {len(existing_handles)} existing username(s) from 'Leads' tab.")
    print("-" * 70)

    # Test sample profile batch containing 1 new profile and 1 duplicate profile
    timestamp_tag = datetime.datetime.now().strftime("%M%S")
    sample_profiles = [
        {
            "username": f"test_lead_{timestamp_tag}",
            "name": f"Test Lead {timestamp_tag}",
            "bio": "Certified Career & Life Coach in CT",
            "profile_url": f"https://www.instagram.com/test_lead_{timestamp_tag}/"
        },
        {
            "username": "the.rd.coach",  # Known handle for duplicate testing
            "name": "Kelan Sarnoff",
            "bio": "Career Coach for Dietitians",
            "profile_url": "https://www.instagram.com/the.rd.coach/"
        }
    ]

    print(f"[+] Input profiles to write ({len(sample_profiles)} profiles):")
    for p in sample_profiles:
        print(f"    - @{p['username']} ({p['name']})")
    print("-" * 70)

    print("[+] Executing deduplication and writing to 'Leads' tab...")
    added_count, dup_count, written_items = write_new_leads(
        sh=sh,
        profiles=sample_profiles,
        niche="career coach",
        state="Connecticut"
    )

    print("\n" + "=" * 70)
    print(f" [RESULTS] LEADS WRITING SUMMARY")
    print("=" * 70)
    print(f"  * Leads Added (New):    {added_count}")
    print(f"  * Duplicates Skipped:   {dup_count}")
    print("=" * 70)
    print(" [SUCCESS] Step 4 test completed. Check your 'Leads' tab in Google Sheets!")
    print("=" * 70)

if __name__ == "__main__":
    run_isolated_leads_writer_test()
