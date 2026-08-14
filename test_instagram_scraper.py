import os
import sys
import config
from google_scraper import fetch_instagram_profiles_from_google
from instagram_scraper import fetch_instagram_profile_details, filter_and_clean_profile_urls, clean_and_validate_instagram_url

def test_url_validation_logic():
    print("[+] Testing clean_and_validate_instagram_url logic...")
    
    # 1. Invalid URLs that MUST be filtered out
    invalid_cases = [
        "https://www.instagram.com/explore/locations/108342410884687/des-moines-iowa/",
        "https://www.instagram.com/explore/locations/213009033/wichita-kansas/",
        "https://www.instagram.com/explore/tags/businesscoach/",
        "https://www.instagram.com/accounts/login/",
        "https://www.instagram.com/direct/inbox/",
        "https://www.instagram.com/",
        "https://www-fallback.instagram.com/vanessajoybusiness/",
        "https://www.instagram.com/locations/213009034/columbia-south-carolina/"
    ]
    for url in invalid_cases:
        is_valid, clean_u, reason = clean_and_validate_instagram_url(url)
        assert not is_valid, f"Expected invalid for '{url}' but got valid ({clean_u})"
        print(f"    - [PASS] Filtered invalid URL: '{url}' -> {reason}")

    # 2. Valid URLs that MUST pass regex
    valid_cases = [
        ("https://www.instagram.com/jennifer_sharon_growthcoach/", "https://www.instagram.com/jennifer_sharon_growthcoach/"),
        ("https://www.instagram.com/@jennifer_sharon_growthcoach/", "https://www.instagram.com/jennifer_sharon_growthcoach/"),
        ("https://www.instagram.com/p/C-12345/", "https://www.instagram.com/p/C-12345/"),
        ("https://www.instagram.com/reel/C-12345/", "https://www.instagram.com/reel/C-12345/"),
        ("https://instagram.com/iowabusinessgrowth", "https://www.instagram.com/iowabusinessgrowth/")
    ]
    for raw_url, expected_clean in valid_cases:
        is_valid, clean_u, reason = clean_and_validate_instagram_url(raw_url)
        assert is_valid, f"Expected valid for '{raw_url}' but failed: {reason}"
        assert clean_u == expected_clean, f"Expected '{expected_clean}' but got '{clean_u}'"
        print(f"    - [PASS] Validated clean URL: '{raw_url}' -> '{clean_u}'")

    print("[SUCCESS] All URL validation unit tests passed cleanly.\n")

def run_isolated_instagram_scraper_test():
    print("=" * 70)
    print(" [TEST] APIFY INSTAGRAM PROFILE SCRAPER (ISOLATION TEST)")
    print("=" * 70)

    test_url_validation_logic()

    token = config.APIFY_API_TOKEN
    if not token or token.strip() in ("", "your_apify_api_token_here"):
        print("[ERROR] APIFY_API_TOKEN is not set in your .env file.")
        sys.exit(1)

    # Sample testing URLs or fetch live results from Step 2
    sample_urls = [
        "https://www.instagram.com/the.rd.coach/",
        "https://www.instagram.com/tonyrobbins/"
    ]

    print("[+] Step 3 Test Mode Options:")
    print("    1. Perform Google Search live to get fresh profile URLs (Step 2 + 3 flow)")
    print("    2. Use sample verified Instagram profile URLs")
    
    # We will run Google Search first to get live real URLs from Step 2
    print("\n[+] Executing Google Search Scraper to fetch target URLs...")
    try:
        query, google_urls = fetch_instagram_profiles_from_google(
            niche="career coach",
            state="Connecticut",
            pages=1,
            api_token=token
        )
        print(f"[+] Total URLs returned from Google Search: {len(google_urls)}")
        
        # Filter for profile URLs
        profile_urls = filter_and_clean_profile_urls(google_urls)
        print(f"[+] Direct Instagram profile URLs after filtering post/reel links: {len(profile_urls)}")
        
        if not profile_urls:
            print("[NOTE] No direct profile URLs found in search result page 1. Using sample fallback URLs.")
            profile_urls = sample_urls
    except Exception as e:
        print(f"[NOTE] Google Search fetch skipped/failed ({e}). Using sample profile URLs.")
        profile_urls = sample_urls

    # Limit to top 3 profiles for fast isolation test
    test_urls = profile_urls[:3]

    print("-" * 70)
    print(f"[+] Target URLs to scrape ({len(test_urls)} profile(s)):")
    for u in test_urls:
        print(f"    - {u}")
    print("-" * 70)

    # Execute Instagram Scraper
    try:
        profiles = fetch_instagram_profile_details(test_urls, api_token=token)

        print("\n" + "=" * 70)
        print(f" [RESULTS] SCRAPED INSTAGRAM PROFILES ({len(profiles)} items)")
        print("=" * 70)

        for idx, item in enumerate(profiles, start=1):
            clean_bio = item['bio'].encode('ascii', errors='ignore').decode('ascii') if item['bio'] else '[No Bio]'
            clean_name = item['name'].encode('ascii', errors='ignore').decode('ascii') if item['name'] else '[No Name]'
            print(f"\n --- Profile #{idx} ---")
            print(f"  1. Profile URL:             {item['profile_url']}")
            print(f"  2. Username:                @{item['username']}")
            print(f"  3. Full Name:               {clean_name}")
            print(f"  4. Biography:               {clean_bio}")
            print(f"  5. Followers Count:         {item['followers_count']}")
            print(f"  6. Recent Posts Activity:   {item['recent_posts_activity'] or '[No Dates]'}")

        print("\n" + "=" * 70)
        print(" [SUCCESS] Step 3 Apify Instagram Profile Scraper test completed.")
        print("=" * 70)

    except Exception as err:
        print(f"\n[ERROR] Instagram Scraper test execution failed: {err}")
        sys.exit(1)

if __name__ == "__main__":
    run_isolated_instagram_scraper_test()
