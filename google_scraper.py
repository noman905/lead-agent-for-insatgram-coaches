import os
import sys
from apify_client import ApifyClient
import config

from instagram_scraper import clean_and_validate_instagram_url

def build_search_query(niche: str, state: str) -> str:
    """
    Constructs the exact Google Search query for Instagram profile discovery.
    Format: site:instagram.com "{niche}" "{state}"
    """
    return f'site:instagram.com "{niche.strip()}" "{state.strip()}"'

def fetch_instagram_profiles_from_google(niche: str, state: str, pages: int = 1, api_token: str = None) -> tuple[str, list[str]]:
    """
    Calls the Apify Google Search Scraper actor ('apify/google-search-scraper')
    and returns (constructed_query, list_of_instagram_urls).
    Filters out non-profile system paths (/explore/, /locations/, /accounts/, /direct/, etc.) at extraction stage.
    """
    token = api_token or config.APIFY_API_TOKEN
    if not token or token.strip() in ("", "your_apify_api_token_here"):
        raise ValueError(
            "[ERROR] APIFY_API_TOKEN is missing or set to placeholder in .env file. "
            "Please update APIFY_API_TOKEN in your .env file."
        )

    client = ApifyClient(token.strip())
    query = build_search_query(niche, state)

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

    # Run the actor synchronously and fetch dataset results
    run = client.actor("apify/google-search-scraper").call(run_input=run_input)
    
    # Safely handle both dict and object return types from apify-client SDK
    if isinstance(run, dict):
        status = run.get("status")
        run_id = run.get("id")
        dataset_id = run.get("defaultDatasetId") or run.get("default_dataset_id")
    else:
        status = getattr(run, "status", None)
        run_id = getattr(run, "id", None)
        dataset_id = getattr(run, "default_dataset_id", getattr(run, "defaultDatasetId", None))
        if not dataset_id and hasattr(run, "__getitem__"):
            try:
                dataset_id = run["defaultDatasetId"]
            except (KeyError, TypeError):
                dataset_id = run.get("default_dataset_id") if hasattr(run, "get") else None

    print(f"[+] Actor run finished. Status: {status} | Run ID: {run_id}")

    if not dataset_id:
        print("[WARNING] No dataset ID returned from actor execution.")
        return query, []

    extracted_urls = []
    print(f"[+] Reading dataset items (Dataset ID: {dataset_id})...")
    for item in client.dataset(dataset_id).iterate_items():
        candidates = []
        # Case 1: item contains an organicResults array
        if "organicResults" in item and isinstance(item["organicResults"], list):
            for result in item["organicResults"]:
                u = result.get("url") or result.get("link")
                if u:
                    candidates.append(u)
        # Case 2: item is a flattened result row containing url directly
        elif "url" in item and item["url"]:
            candidates.append(item["url"])
        elif "link" in item and item["link"]:
            candidates.append(item["link"])

        for candidate in candidates:
            if "instagram.com" in candidate.lower():
                is_valid, clean_u, reason = clean_and_validate_instagram_url(candidate)
                if is_valid:
                    extracted_urls.append(clean_u)
                else:
                    print(f"    - [EXTRACTION SKIPPED] Skipped non-profile URL: '{candidate}' ({reason})")

    # Deduplicate list preserving original order
    seen = set()
    unique_urls = []
    for u in extracted_urls:
        if u not in seen:
            seen.add(u)
            unique_urls.append(u)

    print(f"[SUCCESS] Extracted {len(unique_urls)} unique Instagram URL(s) from Google Search.")
    return query, unique_urls
