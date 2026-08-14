import os
import re
import sys
import datetime
from urllib.parse import urlparse
from apify_client import ApifyClient
import config

RESERVED_IG_PATHS = {
    "p", "reel", "reels", "stories", "explore", "accounts", 
    "direct", "tv", "developer", "about", "legal", "privacy", "help",
    "locations", "places", "tags", "directory", "login", "create", "api", "shop"
}

SYSTEM_NON_PROFILE_PATHS = {
    "explore", "accounts", "direct", "tv", "developer", "about", 
    "legal", "privacy", "help", "locations", "places", "tags", 
    "directory", "login", "create", "api", "shop"
}

IG_URL_PATTERN = re.compile(r"^(https:\/\/)?(www\.)?instagram\.com\/[A-Za-z0-9._-]+(\/.*)?$", re.IGNORECASE)


def clean_and_validate_instagram_url(url: str) -> tuple[bool, str, str]:
    """
    Validates and cleans an Instagram URL.
    Returns tuple: (is_valid: bool, clean_url: str, error_reason: str)
    """
    if not url or not isinstance(url, str):
        return False, str(url or ""), "empty or non-string URL"

    url_str = url.strip()
    if "instagram.com" not in url_str.lower():
        return False, url_str, "not an instagram.com domain"

    try:
        parsed = urlparse(url_str)
        netloc = parsed.netloc.lower()
        if netloc not in ("instagram.com", "www.instagram.com"):
            return False, url_str, f"invalid domain '{netloc}'"

        path_parts = [p for p in parsed.path.strip("/").split("/") if p]
        
        if not path_parts:
            return False, url_str, "root domain URL (no profile handle)"

        first_segment = path_parts[0].lower()

        # Skip non-profile system paths (/explore/, /locations/, /accounts/, /direct/, /tags/, etc.)
        if first_segment in SYSTEM_NON_PROFILE_PATHS:
            return False, url_str, f"non-profile system path '/{first_segment}/'"

        if first_segment in {"p", "reel", "reels", "stories"}:
            if len(path_parts) > 1:
                clean_url = f"https://www.instagram.com/{first_segment}/{path_parts[1]}/"
            else:
                clean_url = f"https://www.instagram.com/{first_segment}/"
        else:
            username = path_parts[0]
            if username.startswith("@"):
                username = username[1:]
            clean_url = f"https://www.instagram.com/{username}/"

        if not IG_URL_PATTERN.match(clean_url):
            return False, url_str, f"does not match required Instagram pattern ^(https://)?(www.)?instagram.com/[A-Za-z0-9._-]+(/.*)?$"

        return True, clean_url, ""
    except Exception as err:
        return False, url_str, f"URL parsing exception: {err}"


def filter_and_clean_profile_urls(urls: list[str]) -> list[str]:
    """
    Filters a list of Instagram URLs to isolate valid target URLs (profiles, posts, reels)
    skipping non-profile system pages (/explore, /locations, /accounts, /direct, /tags, etc.).
    """
    valid_urls = []
    seen = set()

    for url in urls:
        is_valid, clean_url, _ = clean_and_validate_instagram_url(url)
        if is_valid and clean_url not in seen:
            seen.add(clean_url)
            valid_urls.append(clean_url)

    return valid_urls



def extract_username_from_url(url: str) -> str:
    """
    Helper to parse handle from Instagram profile URL.
    """
    try:
        parsed = urlparse(url)
        path_parts = [p for p in parsed.path.strip("/").split("/") if p]
        if path_parts and path_parts[0].lower() not in RESERVED_IG_PATHS:
            return path_parts[0]
    except Exception:
        pass
    return ""


def parse_post_timestamp_and_date(post_item: dict) -> tuple[float, str]:
    """
    Extracts epoch float timestamp and YYYY-MM-DD date string from a post object.
    Returns (epoch_seconds, date_str). Returns (0.0, "") if invalid.
    """
    if not isinstance(post_item, dict):
        return 0.0, ""

    raw_ts = post_item.get("timestamp") or post_item.get("takenAt") or post_item.get("pubDate") or post_item.get("taken_at_timestamp")
    if not raw_ts:
        return 0.0, ""

    epoch_val = 0.0
    date_str = ""

    if isinstance(raw_ts, (int, float)):
        epoch_val = float(raw_ts)
        try:
            date_str = datetime.datetime.fromtimestamp(epoch_val, tz=datetime.timezone.utc).strftime("%Y-%m-%d")
        except Exception:
            date_str = ""
    else:
        raw_str = str(raw_ts).strip()
        if raw_str.isdigit():
            epoch_val = float(raw_str)
            try:
                date_str = datetime.datetime.fromtimestamp(int(raw_str), tz=datetime.timezone.utc).strftime("%Y-%m-%d")
            except Exception:
                date_str = ""
        else:
            try:
                dt = datetime.datetime.fromisoformat(raw_str.replace("Z", "+00:00"))
                epoch_val = dt.timestamp()
                date_str = dt.strftime("%Y-%m-%d")
            except Exception:
                match = re.search(r"(\d{4}-\d{2}-\d{2})", raw_str)
                if match:
                    date_str = match.group(1)
                    try:
                        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc)
                        epoch_val = dt.timestamp()
                    except Exception:
                        epoch_val = 0.0

    return epoch_val, date_str


def sort_recent_posts_activity(raw_posts) -> str:
    """
    Takes raw posts (list of dicts, list of strings, or pipe-separated string of dates)
    and formats them as a clean, pipe-separated string of unique YYYY-MM-DD dates,
    strictly sorted by timestamp/date in descending order (newest -> oldest).
    Limits output to top 5 unique dates.
    """
    if not raw_posts:
        return ""

    items_to_process = []
    if isinstance(raw_posts, str):
        parts = [p.strip() for p in raw_posts.split("|") if p.strip()]
        for p in parts:
            items_to_process.append({"timestamp": p})
    elif isinstance(raw_posts, list):
        items_to_process = raw_posts
    else:
        return ""

    parsed_entries = []
    for item in items_to_process:
        if isinstance(item, dict):
            epoch_ts, d_str = parse_post_timestamp_and_date(item)
        elif isinstance(item, str):
            epoch_ts, d_str = parse_post_timestamp_and_date({"timestamp": item})
        else:
            continue

        if d_str:
            parsed_entries.append({"epoch": epoch_ts, "date_str": d_str})

    if not parsed_entries:
        return ""

    # Sort strictly descending (newest to oldest) by timestamp epoch, ignoring isPinned
    parsed_entries.sort(key=lambda x: x["epoch"], reverse=True)

    unique_dates = []
    for entry in parsed_entries:
        d = entry["date_str"]
        if d and d not in unique_dates:
            unique_dates.append(d)
        if len(unique_dates) >= 10:
            break

    return " | ".join(unique_dates)



def format_recent_posts_activity(item: dict) -> str:
    """
    Extracts 6-7 most recent posts, sorts them strictly by timestamp (newest to oldest),
    and formats as clean pipe-separated YYYY-MM-DD dates (up to 5 unique dates).
    Example: 2026-07-30 | 2026-07-27 | 2026-07-22 | 2025-01-29 | 2023-06-07
    """
    posts_list = item.get("latestPosts") or item.get("posts") or item.get("timelinePosts") or []
    return sort_recent_posts_activity(posts_list)




def parse_profile_item(item: dict) -> dict:
    """
    Parses a dataset item returned by Apify Instagram Scraper.
    Returns a standardized profile dictionary including scrape_status.
    """
    username = item.get("username") or item.get("ownerUsername")
    if not username and isinstance(item.get("owner"), dict):
        username = item["owner"].get("username")
    if not username:
        username = extract_username_from_url(item.get("url", "")) or extract_username_from_url(item.get("inputUrl", ""))

    if not username:
        return None

    username = username.strip()
    name = item.get("fullName") or item.get("name") or item.get("ownerFullName") or (item.get("owner") if isinstance(item.get("owner"), dict) else {}).get("fullName", "")
    bio = item.get("biography") or item.get("bio") or (item.get("owner") if isinstance(item.get("owner"), dict) else {}).get("biography", "")
    
    followers_count = item.get("followersCount")
    if followers_count is None:
        followers_count = 0

    recent_posts_dates = format_recent_posts_activity(item)

    is_private = item.get("isPrivate", False)
    error = item.get("error") or item.get("errorMessage") or item.get("errorType")

    if error:
        scrape_status = f"Actor error: {error}"
    elif is_private:
        scrape_status = "Private account"
    elif not bio and followers_count == 0:
        scrape_status = "Partial profile / Post URL"
    else:
        scrape_status = "Success"

    return {
        "profile_url": f"https://www.instagram.com/{username}/",
        "username": username,
        "name": str(name).strip(),
        "bio": str(bio).replace("\n", " ").strip(),
        "followers_count": followers_count,
        "recent_posts_activity": recent_posts_dates,
        "is_private": bool(is_private),
        "scrape_status": scrape_status
    }


def fetch_instagram_profile_details(profile_urls: list[str], api_token: str = None) -> list[dict]:
    """
    Feeds a list of Instagram profile URLs to the Apify Instagram Scraper actor ('apify/instagram-scraper').
    Uses 2-pass auto-resolution to convert post/reel links into fully populated profile objects.
    Captures private, deleted, or error accounts with explicit warnings.
    """
    token = api_token or config.APIFY_API_TOKEN
    if not token or token.strip() in ("", "your_apify_api_token_here"):
        raise ValueError(
            "[ERROR] APIFY_API_TOKEN is missing or not set in .env file."
        )

    if not profile_urls:
        print("[WARNING] No profile URLs provided for Instagram scraping.")
        return []

    clean_urls = filter_and_clean_profile_urls(profile_urls)
    if not clean_urls:
        clean_urls = profile_urls

    client = ApifyClient(token.strip())

    # --- PASS 1: Scrape initial URLs ---
    run_input_1 = {
        "directUrls": clean_urls,
        "resultsType": "details",
        "searchType": "user",
        "searchLimit": 1
    }

    print(f"[+] Initializing Apify Instagram Scraper ('apify/instagram-scraper')...")
    print(f"    - Pass 1: Scraping {len(clean_urls)} URL(s)...")

    run_1 = client.actor("apify/instagram-scraper").call(run_input=run_input_1)
    dataset_id_1 = run_1.get("defaultDatasetId") if isinstance(run_1, dict) else getattr(run_1, "default_dataset_id", getattr(run_1, "defaultDatasetId", None))

    profiles_dict = {}
    unresolved_usernames = set()

    if dataset_id_1:
        print(f"[+] Reading Pass 1 dataset items (Dataset ID: {dataset_id_1})...")
        for item in client.dataset(dataset_id_1).iterate_items():
            parsed = parse_profile_item(item)
            if not parsed:
                continue

            u = parsed["username"].lower()
            if parsed["scrape_status"] == "Success" or parsed["followers_count"] > 0 or parsed["bio"]:
                profiles_dict[u] = parsed
            else:
                # Store partial profile, but flag handle for Pass 2 auto-resolution
                if u not in profiles_dict:
                    profiles_dict[u] = parsed
                unresolved_usernames.add(parsed["username"])

    # --- PASS 2: Auto-resolve handles that came from post/reel links or returned partial data ---
    pass2_urls = [f"https://www.instagram.com/{u}/" for u in unresolved_usernames]

    if pass2_urls:
        print(f"[+] Pass 2: Auto-resolving {len(pass2_urls)} post/partial handle(s) via direct profile scrape...")
        try:
            run_2 = client.actor("apify/instagram-scraper").call(run_input={
                "directUrls": pass2_urls,
                "resultsType": "details",
                "searchType": "user",
                "searchLimit": 1
            })
            dataset_id_2 = run_2.get("defaultDatasetId") if isinstance(run_2, dict) else getattr(run_2, "default_dataset_id", getattr(run_2, "defaultDatasetId", None))

            if dataset_id_2:
                for item in client.dataset(dataset_id_2).iterate_items():
                    parsed = parse_profile_item(item)
                    if not parsed:
                        continue

                    u = parsed["username"].lower()
                    # If Pass 2 retrieved full data or a concrete reason, update profile
                    if parsed["scrape_status"] == "Success" or parsed["followers_count"] > 0 or parsed["bio"]:
                        profiles_dict[u] = parsed
                    elif parsed["scrape_status"] != "Partial profile / Post URL":
                        profiles_dict[u] = parsed

        except Exception as err:
            print(f"[WARNING] Pass 2 profile auto-resolution encountered an error: {err}")

    # --- Final Audit & Error Logging ---
    final_profiles = list(profiles_dict.values())
    success_count = 0
    issue_count = 0

    for p in final_profiles:
        status = p.get("scrape_status", "Success")
        if status == "Success" or p.get("followers_count", 0) > 0 or p.get("bio"):
            p["scrape_status"] = "Success"
            success_count += 1
        else:
            issue_count += 1
            print(f"    - [WARNING] Scrape issue for @{p['username']}: {status}")

    print(f"[SUCCESS] Scraped details for {len(final_profiles)} profile(s) ({success_count} complete, {issue_count} with issues/notes).")
    return final_profiles
