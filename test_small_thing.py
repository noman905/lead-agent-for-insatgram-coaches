import sys
import config
from google_scraper import fetch_instagram_profiles_from_google

def run_small_test():
    niche = "career coach"
    state = "New York"
    pages = 3
    
    print(f"Testing Google Scraper for '{niche}' in '{state}' for {pages} page(s)...")
    try:
        query_summary, status_msg, clean_urls = fetch_instagram_profiles_from_google(
            niche=niche,
            state=state,
            pages=pages,
            api_token=config.APIFY_API_TOKEN,
            sh=None
        )
        print("\n--- RESULTS ---")
        print(f"Status Message: {status_msg}")
        print(f"Found {len(clean_urls)} clean profile URLs:")
        for url in clean_urls:
            print(f"  {url}")
            
    except Exception as e:
        print(f"Error during test: {e}")

if __name__ == "__main__":
    run_small_test()
