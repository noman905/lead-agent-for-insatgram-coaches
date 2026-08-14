import os
import sys
import config
from google_scraper import fetch_instagram_profiles_from_google, build_search_query

def run_isolated_google_search_test():
    print("=" * 70)
    print(" [TEST] APIFY GOOGLE SEARCH SCRAPER (ISOLATION TEST)")
    print("=" * 70)

    # 1. Verify Apify API token
    token = config.APIFY_API_TOKEN
    if not token or token.strip() in ("", "your_apify_api_token_here"):
        print("[ERROR] APIFY_API_TOKEN is not configured in your .env file.")
        print("Please edit .env and set APIFY_API_TOKEN=your_real_apify_token")
        sys.exit(1)

    print(f"[+] Found APIFY_API_TOKEN (Length: {len(token.strip())} chars)")

    # 2. Check if a Pending job can be read from Google Sheet, or fallback to sample inputs
    niche = "career coach"
    state = "Connecticut"
    pages = 1

    # Try reading from Google Sheet if credentials are present
    if os.path.exists(config.GOOGLE_SERVICE_ACCOUNT_FILE):
        try:
            import gspread
            from test_sheet import get_control_jobs
            
            gc = gspread.service_account(filename=config.GOOGLE_SERVICE_ACCOUNT_FILE)
            sh = gc.open_by_key(config.GOOGLE_SHEET_ID) if config.GOOGLE_SHEET_ID else None
            if sh:
                control_sheet = sh.worksheet("Control")
                jobs = get_control_jobs(control_sheet)
                pending = [j for j in jobs if j["status"].strip().lower() == "pending"]
                if pending:
                    job = pending[0]
                    niche = job["niche"] or niche
                    state = job["state"] or state
                    pages = int(job["pages"]) if job["pages"].isdigit() else pages
                    print(f"[+] Loaded Pending job from Google Sheet Control queue (Row {job['row_number']}):")
                    print(f"    - Niche: {niche}")
                    print(f"    - State: {state}")
                    print(f"    - Pages: {pages}")
                else:
                    print(f"[NOTE] No Pending jobs in Google Sheet Control tab. Using test defaults:")
                    print(f"    - Niche: {niche} | State: {state} | Pages: {pages}")
        except Exception as e:
            print(f"[NOTE] Could not read Google Sheet queue ({e}). Using test defaults:")
            print(f"    - Niche: {niche} | State: {state} | Pages: {pages}")
    else:
        print(f"[NOTE] Using test defaults: Niche='{niche}', State='{state}', Pages={pages}")

    print("-" * 70)

    # 3. Construct Query
    query = build_search_query(niche, state)
    print(f"[+] Constructed Google Query: {query}")
    print("-" * 70)

    # 4. Execute Apify Google Search Scraper
    try:
        query_used, profile_urls = fetch_instagram_profiles_from_google(
            niche=niche,
            state=state,
            pages=pages,
            api_token=token
        )

        print("\n" + "=" * 70)
        print(f" [RESULTS] SUMMARY ({len(profile_urls)} Profile URLs Returned)")
        print("=" * 70)

        
        if profile_urls:
            print(f"[+] List of Instagram Profile URLs returned by Apify:")
            for idx, url in enumerate(profile_urls, start=1):
                print(f"    {idx:2d}. {url}")
        else:
            print("[WARNING] Zero URLs were returned. Check query or page count.")

        print("=" * 70)
        print(" [SUCCESS] Step 2 Apify Google Search Scraper test completed.")
        print("=" * 70)

    except Exception as err:
        print(f"\n[ERROR] Apify Google Search Scraper execution failed: {err}")
        sys.exit(1)

if __name__ == "__main__":
    run_isolated_google_search_test()
