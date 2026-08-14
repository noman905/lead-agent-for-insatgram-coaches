import os
import sys
import gspread

# Import settings from config module (.env & config.py)
import config

SERVICE_ACCOUNT_FILE = config.GOOGLE_SERVICE_ACCOUNT_FILE
if not os.path.exists(SERVICE_ACCOUNT_FILE) and os.path.exists("credentials.json.json"):
    SERVICE_ACCOUNT_FILE = "credentials.json.json"

# CLI argument overrides config setting if provided
SHEET_ID_OR_NAME = sys.argv[1] if len(sys.argv) > 1 else config.GOOGLE_SHEET_ID



import datetime

def ensure_sheet_structure(sh):
    existing_worksheets = {ws.title: ws for ws in sh.worksheets()}
    
    # 1. Ensure 'Control' tab exists and has columnar header: Niche | State | Pages | Status
    if "Control" not in existing_worksheets:
        print("[+] Creating 'Control' tab...")
        control_sheet = sh.add_worksheet(title="Control", rows=50, cols=10)
        control_sheet.update(range_name='A1:D1', values=[['Niche', 'State', 'Pages', 'Status']])
        print("[SUCCESS] Created 'Control' tab with header: Niche | State | Pages | Status")
    else:
        control_sheet = existing_worksheets["Control"]
        records = control_sheet.get_all_values()
        # Check if header needs to be updated from old vertical format to new column queue format
        if not records or (len(records[0]) < 4 or records[0][0].strip().lower() != 'niche' or (len(records) >= 2 and records[1][0].strip().lower() == 'state')):
            print("[+] Updating 'Control' tab header to column queue layout (Niche | State | Pages | Status)...")
            control_sheet.clear()
            control_sheet.update(range_name='A1:D1', values=[['Niche', 'State', 'Pages', 'Status']])
            print("[SUCCESS] 'Control' tab header updated.")
        else:
            print("[+] 'Control' tab queue structure verified.")

    # 2. Ensure 'Leads' tab exists and has full 9-column header
    leads_header = [
        'Profile URL', 'Username', 'Full Name', 'Biography',
        'Followers Count', 'Recent Posts Activity', 'Date Added', 'Niche', 'State'
    ]

    if "Leads" not in existing_worksheets:
        print("[+] Creating 'Leads' tab...")
        leads_sheet = sh.add_worksheet(title="Leads", rows=100, cols=15)
        leads_sheet.update(range_name='A1:I1', values=[leads_header])
        print("[SUCCESS] Created 'Leads' tab with 9-column header.")
    else:
        leads_sheet = existing_worksheets["Leads"]
        records = leads_sheet.get_all_values()
        if not records or len(records[0]) < 9 or records[0][:9] != leads_header:
            print("[+] Updating 'Leads' tab header to exact 9-column layout...")
            leads_sheet.update(range_name='A1:I1', values=[leads_header])
            print("[SUCCESS] 'Leads' tab header updated.")
        else:
            print("[+] 'Leads' tab structure verified.")


    # 3. Ensure 'Run Log' tab exists
    if "Run Log" not in existing_worksheets:
        print("[+] Creating 'Run Log' tab...")
        run_log_sheet = sh.add_worksheet(title="Run Log", rows=100, cols=15)
        run_log_header = [['Timestamp', 'Niche', 'State', 'Pages Searched', 'Total Profiles Found', 'Leads Added (New)', 'Duplicates Skipped', 'Garbage/Invalid Skipped', 'Status', 'Notes']]
        run_log_sheet.update(range_name='A1:J1', values=run_log_header)
        print("[SUCCESS] Created 'Run Log' tab with audit headers.")
    else:
        print("[+] 'Run Log' tab already exists.")

    # 4. Ensure 'Error Log' tab exists
    if "Error Log" not in existing_worksheets:
        print("[+] Creating 'Error Log' tab...")
        error_log_sheet = sh.add_worksheet(title="Error Log", rows=100, cols=10)
        error_log_header = [['Timestamp', 'Niche', 'State', 'Invalid URL', 'Error Reason', 'Stage']]
        error_log_sheet.update(range_name='A1:F1', values=error_log_header)
        print("[SUCCESS] Created 'Error Log' tab with audit headers.")
    else:
        print("[+] 'Error Log' tab already exists.")

    print("-" * 60)


def append_run_log_entry(sh, niche, state, pages_searched, total_profiles, leads_added, duplicates_skipped, garbage_skipped, status, notes=""):
    """
    Appends an audit entry row to the 'Run Log' tab.
    """
    run_log_sheet = sh.worksheet("Run Log")
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row_values = [
        timestamp,
        niche,
        state,
        str(pages_searched),
        str(total_profiles),
        str(leads_added),
        str(duplicates_skipped),
        str(garbage_skipped),
        status,
        notes
    ]
    run_log_sheet.append_row(row_values)
    print(f"[+] Appended entry to 'Run Log' tab for [{niche} / {state}] -> Status: {status}")


def append_error_log_entry(sh, niche, state, invalid_url, error_reason="invalid URL format, skipped enrichment", stage="Enrichment"):
    """
    Appends an error entry row to the 'Error Log' tab.
    """
    try:
        error_log_sheet = sh.worksheet("Error Log")
    except Exception:
        error_log_sheet = sh.add_worksheet(title="Error Log", rows=100, cols=10)
        error_log_header = [['Timestamp', 'Niche', 'State', 'Invalid URL', 'Error Reason', 'Stage']]
        error_log_sheet.update(range_name='A1:F1', values=error_log_header)

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row_values = [
        timestamp,
        niche,
        state,
        invalid_url,
        error_reason,
        stage
    ]
    error_log_sheet.append_row(row_values)
    print(f"    - [ERROR LOGGED] '{invalid_url}' -> {error_reason} (Stage: {stage})")



def update_job_status(control_sheet, row_number, status_str):
    """
    Updates the Status cell (Column D / 4) for the given 1-indexed row number.
    """
    control_sheet.update_cell(row_number, 4, status_str)
    print(f"[+] Updated Row {row_number} Status -> '{status_str}'")


def add_sample_jobs_if_empty(control_sheet):
    """
    Adds sample Pending jobs to Control tab if queue is empty.
    """
    rows = control_sheet.get_all_values()
    if len(rows) <= 1:
        sample_data = [
            ['career coach', 'Connecticut', '3', 'Pending'],
            ['business coach', 'Texas', '5', 'Pending'],
            ['life coach', 'Florida', '2', 'Pending']
        ]
        control_sheet.update(range_name=f'A2:D{1+len(sample_data)}', values=sample_data)
        print("[+] Added sample Pending jobs to Control tab for testing.")


def get_control_jobs(control_sheet):
    """
    Reads all job rows from Control tab (starting row 2).
    Returns list of dicts with row_number, niche, state, pages, status.
    """
    rows = control_sheet.get_all_values()
    if not rows:
        return []

    header = [h.strip().lower() for h in rows[0]]
    niche_idx = header.index("niche") if "niche" in header else 0
    state_idx = header.index("state") if "state" in header else 1
    pages_idx = header.index("pages") if "pages" in header else 2
    status_idx = header.index("status") if "status" in header else 3

    jobs = []
    for row_num, row in enumerate(rows[1:], start=2): # 1-indexed row in sheet
        # Pad row to at least 4 items
        row_padded = row + [""] * (4 - len(row))
        niche = row_padded[niche_idx].strip()
        state = row_padded[state_idx].strip()
        pages = row_padded[pages_idx].strip()
        status = row_padded[status_idx].strip()

        # Skip completely empty rows
        if not niche and not state and not pages and not status:
            continue

        jobs.append({
            "row_number": row_num,
            "niche": niche,
            "state": state,
            "pages": pages,
            "status": status if status else "Pending"
        })

    return jobs


def connect_and_read_sheet():
    print("=" * 60)
    print("Step 1: Google Sheet Queue & Connection Test")
    print("=" * 60)

    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        print(f"[ERROR] Service account file '{SERVICE_ACCOUNT_FILE}' not found.")
        print("Please place your service account JSON file in this directory or update GOOGLE_SERVICE_ACCOUNT_FILE in .env.")
        sys.exit(1)

    if not SHEET_ID_OR_NAME:
        print("[ERROR] No Google Sheet ID provided.")
        print("Usage option 1: py test_sheet.py YOUR_GOOGLE_SHEET_ID")
        print("Usage option 2: Set GOOGLE_SHEET_ID in your .env file")
        sys.exit(1)

    try:
        print(f"[+] Authenticating using service account key: {SERVICE_ACCOUNT_FILE}")
        gc = gspread.service_account(filename=SERVICE_ACCOUNT_FILE)

        print(f"[+] Opening Google Sheet: {SHEET_ID_OR_NAME}")
        try:
            sh = gc.open_by_key(SHEET_ID_OR_NAME)
        except Exception:
            sh = gc.open(SHEET_ID_OR_NAME)

        print(f"[SUCCESS] Connected to spreadsheet: '{sh.title}'")
        print("-" * 60)

        # Ensure Control & Leads tabs exist & have correct headers
        ensure_sheet_structure(sh)

        # 1. Read Control Queue
        print("[+] Reading job queue from 'Control' tab...")
        control_sheet = sh.worksheet("Control")
        
        # Populate sample pending jobs if queue is empty for instant verification
        add_sample_jobs_if_empty(control_sheet)

        all_jobs = get_control_jobs(control_sheet)

        pending_jobs = [j for j in all_jobs if j["status"].lower() == "pending"]
        running_jobs = [j for j in all_jobs if j["status"].lower() == "running"]
        done_jobs = [j for j in all_jobs if j["status"].lower() == "done"]
        failed_jobs = [j for j in all_jobs if j["status"].lower() == "failed"]

        print(f"    - Total queue rows found: {len(all_jobs)}")
        print(f"    - Pending jobs:  {len(pending_jobs)}")
        print(f"    - Running jobs:  {len(running_jobs)}")
        print(f"    - Done jobs:     {len(done_jobs)}")
        print(f"    - Failed jobs:   {len(failed_jobs)}")
        print("-" * 60)

        if pending_jobs:
            print("[+] Next Pending Job(s) to process:")
            for j in pending_jobs:
                print(f"    * Row {j['row_number']}: Niche='{j['niche']}', State='{j['state']}', Pages='{j['pages']}', Status='{j['status']}'")
        else:
            print("[NOTE] No 'Pending' jobs found in the Control queue.")
            print("       Add rows with Status = 'Pending' in your sheet to run search jobs.")

        print("-" * 60)

        # 2. Read Leads Tab
        print("[+] Reading 'Leads' tab for existing usernames...")
        leads_sheet = sh.worksheet("Leads")
        all_rows = leads_sheet.get_all_values()
        
        existing_usernames = []
        if all_rows:
            header = [h.strip().lower() for h in all_rows[0]]
            username_col_idx = -1
            for idx, col_name in enumerate(header):
                if "username" in col_name or "user" in col_name or "handle" in col_name:
                    username_col_idx = idx
                    break
            
            if username_col_idx == -1:
                username_col_idx = 0

            for row in all_rows[1:]:
                if len(row) > username_col_idx and row[username_col_idx].strip():
                    existing_usernames.append(row[username_col_idx].strip())

        print(f"    - Found {len(existing_usernames)} existing username(s) in 'Leads' tab:")
        for u in existing_usernames[:10]:
            print(f"      * {u}")
        if len(existing_usernames) > 10:
            print(f"      ... and {len(existing_usernames) - 10} more.")

        print("-" * 60)

        # 3. Read Run Log Tab
        print("[+] Reading 'Run Log' tab for historical run logs...")
        run_log_sheet = sh.worksheet("Run Log")
        log_rows = run_log_sheet.get_all_values()
        log_entries_count = max(0, len(log_rows) - 1)
        print(f"    - Found {log_entries_count} historical audit log entry(ies) in 'Run Log' tab.")

        print("=" * 60)
        print("[STEP 1 SUCCESSFUL] Control queue, Leads, and Run Log tabs read & verified cleanly.")
        print("=" * 60)

    except Exception as e:
        print(f"[ERROR] Failed to connect or read Google Sheet queue: {e}")
        sys.exit(1)

if __name__ == "__main__":
    connect_and_read_sheet()


