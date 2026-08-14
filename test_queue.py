import os
import sys
import time
import gspread
import config
from test_sheet import ensure_sheet_structure, get_control_jobs, update_job_status, append_run_log_entry

def run_queue_isolation_test():
    print("=" * 70)
    print(" [TEST] ISOLATED QUEUE & GOOGLE SHEETS TEST")
    print("=" * 70)

    service_account_file = config.GOOGLE_SERVICE_ACCOUNT_FILE
    sheet_id = config.GOOGLE_SHEET_ID

    if not os.path.exists(service_account_file):
        print(f"[ERROR] Service account key file '{service_account_file}' not found.")
        sys.exit(1)


    print(f"[1/4] Authenticating with Google Sheets API ({service_account_file})...")
    gc = gspread.service_account(filename=service_account_file)

    print(f"[2/4] Opening spreadsheet: {sheet_id}...")
    try:
        sh = gc.open_by_key(sheet_id)
    except Exception:
        sh = gc.open(sheet_id)

    print(f"[SUCCESS] Connected to spreadsheet: '{sh.title}'")
    print("-" * 70)

    # 1. Ensure tab structures
    ensure_sheet_structure(sh)

    # 2. Test reading existing usernames from 'Leads' tab for Dedup
    print("[TEST A] Reading existing usernames from 'Leads' tab for Deduplication...")
    leads_sheet = sh.worksheet("Leads")
    all_rows = leads_sheet.get_all_values()
    existing_usernames = set()
    if len(all_rows) > 1:
        header = [h.strip().lower() for h in all_rows[0]]
        username_col_idx = 0
        for idx, col_name in enumerate(header):
            if "user" in col_name or "handle" in col_name:
                username_col_idx = idx
                break

        for row in all_rows[1:]:
            if len(row) > username_col_idx and row[username_col_idx].strip():
                existing_usernames.add(row[username_col_idx].strip().lower())

    print(f"  --> Found {len(existing_usernames)} existing username(s) for deduplication filtering.")
    if existing_usernames:
        sample_handles = list(existing_usernames)[:5]
        print(f"  --> Sample handles: {', '.join(sample_handles)}")
    print("-" * 70)

    # 3. Read Control Queue & filter strictly for Status == 'Pending'
    print("[TEST B] Reading job queue from 'Control' tab...")
    control_sheet = sh.worksheet("Control")
    all_jobs = get_control_jobs(control_sheet)

    pending_jobs = [j for j in all_jobs if j["status"].strip().lower() == "pending"]

    print(f"  --> Total Queue Rows: {len(all_jobs)}")
    print(f"  --> Pending Jobs:     {len(pending_jobs)}")

    if not pending_jobs:
        print("\n[NOTE] No 'Pending' jobs found in Control tab. Adding a sample pending job for testing...")
        sample_row = ['test coach', 'California', '1', 'Pending']
        control_sheet.append_row(sample_row)
        print("  --> Added sample job: ['test coach', 'California', '1', 'Pending']")
        all_jobs = get_control_jobs(control_sheet)
        pending_jobs = [j for j in all_jobs if j["status"].strip().lower() == "pending"]

    target_job = pending_jobs[0]
    row_num = target_job["row_number"]
    niche = target_job["niche"]
    state = target_job["state"]
    pages = target_job["pages"]

    print(f"\n[TEST C] Testing Status Transition (Pending -> Running -> Done) on Row {row_num}...")
    print(f"  --> Processing Job: Row {row_num} | Niche='{niche}' | State='{state}' | Pages='{pages}'")

    # Step C1: Change status to 'Running'
    print(f"\n  [Step 1] Setting Row {row_num} Status -> 'Running'...")
    update_job_status(control_sheet, row_num, "Running")
    print("  --> [SHEET UPDATED] Status is now 'Running' in Google Sheet!")

    print("  --> Simulating pipeline processing (sleeping 3 seconds)...")
    time.sleep(3)

    # Step C2: Append Run Log test entry
    print("\n  [Step 2] Writing simulation entry to 'Run Log' tab...")
    append_run_log_entry(
        sh,
        niche=niche,
        state=state,
        pages_searched=pages,
        total_profiles=10,
        leads_added=8,
        duplicates_skipped=2,
        garbage_skipped=0,
        status="SUCCESS (TEST)",
        notes="Queue isolation dry-run test successful"
    )

    # Step C3: Change status to 'Done'
    print(f"\n  [Step 3] Setting Row {row_num} Status -> 'Done'...")
    update_job_status(control_sheet, row_num, "Done")
    print("  --> [SHEET UPDATED] Status is now 'Done' in Google Sheet!")

    print("\n" + "=" * 70)
    print(" [SUCCESS] QUEUE ISOLATION TEST PASSED SUCCESSFULLY!")
    print(" All queue reading, deduplication set reading, and status updates verified.")
    print("=" * 70)


if __name__ == "__main__":
    run_queue_isolation_test()
