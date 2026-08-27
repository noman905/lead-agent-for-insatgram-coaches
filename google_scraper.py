import os
import sys
from apify_client import ApifyClient
import config


# ---------------------------------------------------------------------------
# Query builders
# ---------------------------------------------------------------------------

def build_search_query(niche: str, state: str) -> str:
    """
    Constructs the primary Google Search query for Instagram profile discovery.
    Format: "{niche}" "{state}" instagram.com
    """
    return f'"{niche.strip()}" "{state.strip()}" instagram.com'


def build_retry_query(niche: str, state: str) -> str:
    """
    Constructs an alternative retry query when the primary query returns 0 results.
    Format: "{niche}" coach "{state}" instagram
    """
    return f'"{niche.strip()}" coach "{state.strip()}" instagram'


# ---------------------------------------------------------------------------
# URL filtering, cleaning & normalization helpers
# ---------------------------------------------------------------------------

def is_instagram_url(url: str) -> bool:
    """Returns True only if the URL contains 'instagram.com/'."""
    if not url:
        return False
    if "instagram.com/" not in url:
        return False
    return True


# Patterns that indicate junk / non-profile Instagram pages
_JUNK_PATTERNS = [
    "/explore/", "/p/", "/reel/", "/tv/",
    "/stories/", "/direct/", "/accounts/",
    "/hashtag/", "?"
]


def is_valid_profile_url(url: str) -> bool:
    """
    Returns True only for real Instagram profile URLs.
    Rejects posts, reels, explore, stories, accounts, hashtags,
    and any URL with query parameters.
    """
    for pattern in _JUNK_PATTERNS:
        if pattern in url:
            return False
    return True


def normalize_url(url: str) -> str:
    """
    Normalises an Instagram URL:
      - lowercase
      - strip whitespace
      - remove www. prefix
      - remove trailing slash
    """
    url = url.lower().strip()
    url = url.replace("www.", "")
    url = url.rstrip("/")
    return url


# ---------------------------------------------------------------------------
# Existing Leads tab URL reader (for cross-check / credit saving)
# ---------------------------------------------------------------------------

def get_existing_leads_urls(sh) -> set[str]:
    """
    Reads the 'Leads' worksheet and returns a set of normalised profile URLs
    already present (column A — 'Profile URL').
    Falls back to username-based URLs when Profile URL column is missing.
    """
    leads_sheet = sh.worksheet("Leads")
    all_rows = leads_sheet.get_all_values()

    existing = set()
    if not all_rows or len(all_rows) <= 1:
        return existing

    header = [h.strip().lower() for h in all_rows[0]]

    # Try to find Profile URL column first
    url_col_idx = -1
    for idx, col_name in enumerate(header):
        if "profile" in col_name and "url" in col_name:
            url_col_idx = idx
            break

    # Fall back to username column if Profile URL column is missing
    username_col_idx = -1
    for idx, col_name in enumerate(header):
        if "user" in col_name or "handle" in col_name:
            username_col_idx = idx
            break

    for row in all_rows[1:]:
        # First priority: use Profile URL column
        if url_col_idx >= 0 and len(row) > url_col_idx and row[url_col_idx].strip():
            existing.add(normalize_url(row[url_col_idx].strip()))
        # Second priority: construct from username
        elif username_col_idx >= 0 and len(row) > username_col_idx and row[username_col_idx].strip():
            username = row[username_col_idx].strip().lower()
            existing.add(f"https://instagram.com/{username}")

    return existing


# ---------------------------------------------------------------------------
# Core: run Apify Google Search actor for a single query string
# ---------------------------------------------------------------------------

def _run_google_search_actor(client: ApifyClient, query: str, pages: int) -> list[str]:
    """
    Executes the Apify Google Search Scraper actor for the given *query* and
    returns ALL raw URLs from the result dataset (no filtering applied here).
    Raises RuntimeError on actor failure.
    """
    run_input = {
        "queries": query,
        "maxPagesPerQuery": int(pages),
        "resultsPerPage": 100,
        "mobileResults": False
    }

    print(f"[+] Initializing Apify Google Search Scraper...")
    print(f"    - Query string: {query}")
    print(f"    - Requested pages: {pages}")
    print(f"    - Triggering actor 'apify/google-search-scraper' on Apify Cloud...")

    run = client.actor("apify/google-search-scraper").call(run_input=run_input)

    if isinstance(run, dict):
        status = run.get("status")
        status_msg = run.get("statusMessage") or ""
        run_id = run.get("id")
        dataset_id = run.get("defaultDatasetId") or run.get("default_dataset_id")
    else:
        status = getattr(run, "status", None)
        status_msg = getattr(run, "status_message", getattr(run, "statusMessage", ""))
        run_id = getattr(run, "id", None)
        dataset_id = getattr(run, "default_dataset_id", getattr(run, "defaultDatasetId", None))
        if not dataset_id and hasattr(run, "__getitem__"):
            try:
                dataset_id = run["defaultDatasetId"]
            except (KeyError, TypeError):
                dataset_id = run.get("default_dataset_id") if hasattr(run, "get") else None

    print(f"[+] Actor run finished. Status: {status} | Run ID: {run_id}")

    if status and status in ("FAILED", "ABORTED", "TIMED-OUT"):
        raise RuntimeError(
            f"Apify Google Search actor run failed with status '{status}': "
            f"{status_msg or 'Execution incomplete'}"
        )

    if not dataset_id:
        print("[WARNING] No dataset ID returned from actor execution.")
        return []

    all_urls = []
    print(f"[+] Reading dataset items (Dataset ID: {dataset_id})...")
    for item in client.dataset(dataset_id).iterate_items():
        # Case 1: item contains an organicResults array
        if "organicResults" in item and isinstance(item["organicResults"], list):
            for result in item["organicResults"]:
                u = result.get("url") or result.get("link")
                if u:
                    all_urls.append(u)
        # Case 2: item is a flattened result row containing url directly
        elif "url" in item and item["url"]:
            all_urls.append(item["url"])
        elif "link" in item and item["link"]:
            all_urls.append(item["link"])

    print(f"[+] Raw URLs extracted from dataset: {len(all_urls)}")
    return all_urls


# ---------------------------------------------------------------------------
# Full pipeline: clean / filter / normalize / deduplicate / cross-check
# ---------------------------------------------------------------------------

def _clean_and_filter_urls(raw_urls: list[str]) -> list[str]:
    """
    Applies the full 4-step URL cleaning pipeline:
      1. Keep only URLs containing instagram.com/
      2. Remove junk Instagram URLs (reels, posts, explore, stories, etc.)
      3. Normalise (lowercase, remove www., remove trailing slash)
      4. Deduplicate within batch (preserve order)
    Returns a list of unique, normalised Instagram profile URLs.
    """
    # Step 1 — keep only instagram.com URLs
    instagram_urls = [url for url in raw_urls if is_instagram_url(url)]
    non_ig_count = len(raw_urls) - len(instagram_urls)
    if non_ig_count:
        print(f"    - [FILTER] Removed {non_ig_count} non-Instagram URL(s)")

    # Step 2 — remove junk Instagram URLs
    profile_urls = [url for url in instagram_urls if is_valid_profile_url(url)]
    junk_count = len(instagram_urls) - len(profile_urls)
    if junk_count:
        print(f"    - [FILTER] Removed {junk_count} junk Instagram URL(s) (posts/reels/explore/stories/params)")

    # Step 3 — normalise
    normalized = [normalize_url(url) for url in profile_urls]

    # Step 4 — deduplicate (preserve order)
    seen = set()
    unique_urls = []
    for url in normalized:
        if url not in seen:
            seen.add(url)
            unique_urls.append(url)

    dup_count = len(normalized) - len(unique_urls)
    if dup_count:
        print(f"    - [DEDUP]  Removed {dup_count} duplicate URL(s) within batch")

    return unique_urls


def _cross_check_leads(unique_urls: list[str], existing_leads_urls: set[str]) -> tuple[list[str], int]:
    """
    Removes URLs that already exist in the Leads tab.
    Returns (new_urls, skipped_count).
    """
    new_urls = []
    skipped = 0
    for url in unique_urls:
        if url in existing_leads_urls:
            skipped += 1
            print(f"    - [CREDIT SAVED] Skipping '{url}' (already in Leads tab)")
        else:
            new_urls.append(url)
    return new_urls, skipped


# ---------------------------------------------------------------------------
# Public API — called by run_agent.py
# ---------------------------------------------------------------------------

def fetch_instagram_profiles_from_google(
    niche: str,
    state: str,
    pages: int = 1,
    api_token: str = None,
    sh=None,
) -> tuple[str, list[str]]:
    """
    Runs the full Google-search → filter → normalise → dedup → cross-check
    pipeline and returns (query_used, final_clean_urls).

    If the primary query returns 0 Instagram profile URLs it automatically
    retries with an alternative query once.

    When *sh* (spreadsheet handle) is provided the results are cross-checked
    against existing Leads tab URLs to save Apify credits.
    """
    token = api_token or config.APIFY_API_TOKEN
    if not token or token.strip() in ("", "your_apify_api_token_here"):
        raise ValueError(
            "[ERROR] APIFY_API_TOKEN is missing or set to placeholder in .env file. "
            "Please update APIFY_API_TOKEN in your .env file."
        )

    client = ApifyClient(token.strip())

    # --- Attempt 1: primary query ---
    query = build_search_query(niche, state)
    raw_urls = _run_google_search_actor(client, query, pages)
    unique_urls = _clean_and_filter_urls(raw_urls)

    # --- Attempt 2: retry with alternative query if 0 profile URLs ---
    if not unique_urls:
        retry_query = build_retry_query(niche, state)
        print(f"[RETRY] Primary query returned 0 profile URLs. Retrying with: {retry_query}")
        raw_urls = _run_google_search_actor(client, retry_query, pages)
        unique_urls = _clean_and_filter_urls(raw_urls)
        query = retry_query  # report the query that was actually used

    # --- Cross-check against existing Leads tab ---
    leads_skipped = 0
    if sh is not None and unique_urls:
        existing = get_existing_leads_urls(sh)
        unique_urls, leads_skipped = _cross_check_leads(unique_urls, existing)

    # --- Summary ---
    print(f"[+] Total raw Google URLs:             {len(raw_urls)}")
    print(f"[+] Clean unique Instagram profiles:   {len(unique_urls) + leads_skipped}")
    if leads_skipped:
        print(f"[+] Already in Leads tab (skipped):    {leads_skipped}")
    print(f"[+] Final new URLs to scrape:          {len(unique_urls)}")

    print(f"[SUCCESS] Extracted {len(unique_urls)} new unique Instagram profile URL(s) from Google Search.")
    return query, unique_urls
