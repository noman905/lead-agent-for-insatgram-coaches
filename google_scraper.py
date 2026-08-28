import os
import re
import sys
import math
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
# Multi-query, smart pages, and city-level search helpers
# ---------------------------------------------------------------------------

# Apify's Instagram URL validation regex (must match before sending to actor)
_APIFY_IG_URL_PATTERN = re.compile(
    r"^(https:\/\/)?(www\.)?instagram\.com\/[A-Za-z0-9._-]+(\/.*)?$",
    re.IGNORECASE
)

# State size classifications for smart page scaling
SMALL_STATES = {
    "wyoming", "vermont", "alaska", "north dakota", "south dakota",
    "delaware", "montana", "maine", "new hampshire", "west virginia",
    "rhode island", "hawaii"
}

MEDIUM_STATES = {
    "nebraska", "idaho", "new mexico", "mississippi", "arkansas",
    "kansas", "louisiana", "utah", "oklahoma", "connecticut",
    "oregon", "iowa", "nevada", "south carolina", "kentucky"
}

SMALL_STATE_MAX_PAGES = 3
MEDIUM_STATE_MAX_PAGES = 7


def parse_state_city(state_input: str) -> tuple[str, str]:
    """
    Parses 'State - City' format from the Control tab.
    Returns (state, city). If no city specified, city is empty string.
    Examples:
      'Texas' -> ('Texas', '')
      'Texas - Houston' -> ('Texas', 'Houston')
    """
    if " - " in state_input:
        parts = state_input.split(" - ", 1)
        return parts[0].strip(), parts[1].strip()
    return state_input.strip(), ""


def get_smart_page_limit(state: str, requested_pages: int) -> int:
    """
    Auto-caps maxPagesPerQuery based on state population size
    to avoid wasting Apify credits on empty Google result pages.
    """
    state_lower = state.lower().strip()
    if state_lower in SMALL_STATES:
        capped = min(requested_pages, SMALL_STATE_MAX_PAGES)
        if capped < requested_pages:
            print(f"    - [SMART PAGES] Capped pages from {requested_pages} -> {capped} (small state: {state})")
        return capped
    elif state_lower in MEDIUM_STATES:
        capped = min(requested_pages, MEDIUM_STATE_MAX_PAGES)
        if capped < requested_pages:
            print(f"    - [SMART PAGES] Capped pages from {requested_pages} -> {capped} (medium state: {state})")
        return capped
    return requested_pages


def build_query_variations(niche: str, state: str, city: str = "") -> list[str]:
    """
    Generates multiple Google Search query variations to maximize
    unique Instagram profile discovery. Different query patterns
    trigger different Google ranking algorithms, surfacing profiles
    that a single query would miss.
    """
    location = city if city else state
    niche_clean = niche.strip()
    location_clean = location.strip()

    # Build coaching variant (e.g., "Executive Coach" -> "Executive Coaching")
    coaching_variant = niche_clean.replace("Coach", "Coaching").replace("coach", "coaching")

    queries = [
        # Q1: Original exact match (current approach)
        f'"{niche_clean}" "{location_clean}" instagram.com',
        # Q2: site: operator forces only instagram.com domain, different ranking
        f'"{niche_clean}" "{location_clean}" site:instagram.com',
        # Q3: Unquoted broad match finds partial/related keyword matches
        f'{niche_clean} {location_clean} instagram',
    ]

    # Q4: Coaching variant (only if meaningfully different from original)
    if coaching_variant.lower() != niche_clean.lower():
        queries.append(f'"{coaching_variant}" "{location_clean}" instagram.com')

    # Q5: If city was provided, also include a state-level query for broader coverage
    if city:
        queries.append(f'"{niche_clean}" "{state.strip()}" site:instagram.com')

    return queries


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

def _run_google_search_actor(client: ApifyClient, query: str, pages: int) -> dict:
    """
    Executes the Apify Google Search Scraper actor for the given *query* and
    returns a dictionary containing:
      - 'urls': ALL raw URLs from the result dataset (no filtering applied here)
      - 'actual_pages': The number of distinct pages returned by Google
      - 'has_next_page': True if Google indicated there are more results
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
        return {"urls": [], "actual_pages": 0, "has_next_page": False}

    all_urls = []
    pages_observed = set()
    has_next_page = False
    
    print(f"[+] Reading dataset items (Dataset ID: {dataset_id})...")
    for item in client.dataset(dataset_id).iterate_items():
        # Track page numbers
        page_num = item.get("searchQuery", {}).get("page") or item.get("searchQuery", {}).get("pageNumber") or item.get("pageNumber")
        if page_num:
            pages_observed.add(int(page_num))
            
        if item.get("hasNextPage") is not None:
            has_next_page = item.get("hasNextPage")
            
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
    
    actual_pages_count = len(pages_observed) if pages_observed else (1 if all_urls else 0)
    
    return {
        "urls": all_urls,
        "actual_pages": actual_pages_count,
        "has_next_page": has_next_page
    }


# ---------------------------------------------------------------------------
# Full pipeline: clean / filter / normalize / deduplicate / cross-check
# ---------------------------------------------------------------------------

def _clean_and_filter_urls(raw_urls: list[str]) -> list[str]:
    """
    Applies the full 5-step URL cleaning pipeline:
      1. Keep only URLs containing instagram.com/
      2. Remove junk Instagram URLs (reels, posts, explore, stories, etc.)
      3. Normalise (lowercase, remove www., remove trailing slash)
      4. Deduplicate within batch (preserve order)
      5. Validate against Apify's Instagram URL regex (prevents actor crashes)
    Returns a list of unique, normalised, validated Instagram profile URLs.
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

    # Step 5 — validate against Apify's Instagram URL regex pattern
    # This prevents the "Field input.directUrls.X must match pattern" crash
    validated = []
    invalid_count = 0
    for url in unique_urls:
        if _APIFY_IG_URL_PATTERN.match(url):
            validated.append(url)
        else:
            invalid_count += 1
            print(f"    - [INVALID] Rejected URL (bad pattern): {url}")
    if invalid_count:
        print(f"    - [VALIDATE] Removed {invalid_count} URL(s) that don't match Apify's required Instagram pattern")

    return validated


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
) -> tuple[str, str, list[str]]:
    """
    Runs the full multi-query Google-search → filter → normalise → dedup → cross-check
    pipeline and returns (queries_summary, status_msg, final_clean_urls).

    Uses multiple query variations to maximize unique profile discovery.
    Applies smart page scaling for small/medium states to save credits.
    Supports 'State - City' format for city-level searches.

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

    # --- Parse state/city (supports "Texas - Houston" format) ---
    state_name, city_name = parse_state_city(state)

    # --- Smart page scaling based on state population ---
    effective_pages = get_smart_page_limit(state_name, pages)

    # --- Generate multiple query variations ---
    all_queries = build_query_variations(niche, state_name, city_name)

    # Cap queries based on available pages (each query needs at least 1 page)
    num_queries = min(len(all_queries), effective_pages)
    queries = all_queries[:num_queries]

    pages_per_query = effective_pages // num_queries
    extra_pages = effective_pages % num_queries

    total_pages_planned = pages_per_query * num_queries + extra_pages
    pages_msg = f"{pages_per_query} per query"
    if extra_pages > 0:
        pages_msg += f", +{extra_pages} extra for primary query"
    print(f"[+] Multi-Query Strategy: {num_queries} query variation(s), {total_pages_planned} pages total ({pages_msg})")
    if city_name:
        print(f"    - City-level search: {city_name}, {state_name}")

    all_raw_urls = []
    queries_used = []
    total_actual_pages = 0
    any_has_next = False
    supplemented_queries = []

    for i, query in enumerate(queries, 1):
        q_pages = pages_per_query + (extra_pages if i == 1 else 0)
        print(f"\n--- Query {i}/{num_queries} ({q_pages} page(s)): {query} ---")
        try:
            result = _run_google_search_actor(client, query, q_pages)
            urls = result["urls"]
            actual_pages = result["actual_pages"]
            has_next = result["has_next_page"]
            
            # Detect incomplete run and retry once with modified query
            if actual_pages < q_pages and has_next:
                print(f"[!] Incomplete run detected: Got {actual_pages}/{q_pages} pages. Retrying with alternate query...")
                retry_query = query.replace('instagram.com', 'site:instagram.com') if 'site:' not in query else query.replace('site:instagram.com', 'instagram.com')
                retry_result = _run_google_search_actor(client, retry_query, q_pages - actual_pages)
                urls.extend(retry_result["urls"])
                actual_pages += retry_result["actual_pages"]
                has_next = retry_result["has_next_page"]
                supplemented_queries.append(retry_query)
                queries_used.append(retry_query)
            
            all_raw_urls.extend(urls)
            queries_used.append(query)
            total_actual_pages += actual_pages
            if has_next:
                any_has_next = True
                
        except Exception as e:
            error_msg = str(e).lower()
            # Credit exhaustion — must stop immediately, let caller handle it
            if any(k in error_msg for k in ["exceed", "usage limit", "credit", "billing", "payment"]):
                raise
            print(f"[WARNING] Query {i} failed: {e}. Continuing with remaining queries...")

    # --- Clean, filter, validate, and deduplicate merged results ---
    unique_urls = _clean_and_filter_urls(all_raw_urls)

    # --- If all queries returned 0 profiles, try the legacy retry query ---
    if not unique_urls:
        retry_query = build_retry_query(niche, state_name)
        print(f"\n[RETRY] All {num_queries} queries returned 0 profile URLs. Final retry with: {retry_query}")
        try:
            result = _run_google_search_actor(client, retry_query, effective_pages)
            unique_urls = _clean_and_filter_urls(result["urls"])
            all_raw_urls.extend(result["urls"])
            total_actual_pages += result["actual_pages"]
            if result["has_next_page"]:
                any_has_next = True
            if unique_urls:
                queries_used.append(retry_query)
        except Exception as e:
            error_msg = str(e).lower()
            if any(k in error_msg for k in ["exceed", "usage limit", "credit", "billing", "payment"]):
                raise
            print(f"[WARNING] Retry query also failed: {e}")

    # --- Cross-check against existing Leads tab ---
    leads_skipped = 0
    if sh is not None and unique_urls:
        existing = get_existing_leads_urls(sh)
        unique_urls, leads_skipped = _cross_check_leads(unique_urls, existing)

    # --- Summary and Status Logic ---
    queries_summary = queries_used[0] if queries_used else build_search_query(niche, state_name)
    
    # Build honest status message
    if total_actual_pages >= total_pages_planned:
        status_msg = f"Done ({total_actual_pages}/{total_pages_planned} pages scraped)"
    elif not any_has_next:
        status_msg = f"Done (Natural end at {total_actual_pages} pages, no more results)"
    else:
        status_msg = f"Incomplete ({total_actual_pages}/{total_pages_planned} pages)"
        if supplemented_queries:
            status_msg += f", supplemented with alternate query"

    print(f"\n[+] Total raw Google URLs (all queries):   {len(all_raw_urls)}")
    print(f"[+] Clean unique Instagram profiles:       {len(unique_urls) + leads_skipped}")
    if leads_skipped:
        print(f"[+] Already in Leads tab (skipped):        {leads_skipped}")
    print(f"[+] Final new URLs to scrape:              {len(unique_urls)}")

    print(f"[SUCCESS] {status_msg}")
    print(f"Extracted {len(unique_urls)} new unique Instagram profile URL(s) from {len(queries_used)} Google Search query(ies).")
    
    return queries_summary, status_msg, unique_urls
