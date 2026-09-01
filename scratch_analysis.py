import os
import sys
from dotenv import load_dotenv

# Load env before importing project modules
load_dotenv()

from google_scraper import (
    build_query_variations,
    get_smart_page_limit,
    _run_google_search_actor,
    _clean_and_filter_candidates,
    _cross_check_candidate_leads,
    is_instagram_url,
    is_valid_profile_url,
    normalize_url,
    _APIFY_IG_URL_PATTERN,
)
from gender_filter import filter_candidate_profiles
import config
from apify_client import ApifyClient
from run_agent import get_gspread_client

def analyze_search(niche, state, pages):
    print(f"=== ANALYZING: {niche} in {state} ({pages} pages) ===")
    
    token = config.APIFY_API_TOKEN
    client = ApifyClient(token.strip())
    
    # 1. Queries
    state_name = state
    city_name = ""
    if " - " in state:
        state_name, city_name = state.split(" - ", 1)
        
    effective_pages = get_smart_page_limit(state_name, pages)
    all_queries = build_query_variations(niche, state_name, city_name)
    num_queries = min(len(all_queries), effective_pages)
    queries = all_queries[:num_queries]
    
    pages_per_query = effective_pages // num_queries
    extra_pages = effective_pages % num_queries
    
    print("Exact queries used:")
    for i, q in enumerate(queries, 1):
        q_pages = pages_per_query + (extra_pages if i == 1 else 0)
        print(f"  {i}. {q} ({q_pages} pages)")
        
    # 2. Raw results
    all_raw_items = []
    for i, query in enumerate(queries, 1):
        q_pages = pages_per_query + (extra_pages if i == 1 else 0)
        res = _run_google_search_actor(client, query, q_pages)
        all_raw_items.extend(res.get("items", []))
        
    print(f"\nRaw Google results: {len(all_raw_items)}")
    
    # 3. Filtering pipeline breakdown
    # Step 1: keep only instagram.com
    instagram_items = [it for it in all_raw_items if is_instagram_url(it.get("url", ""))]
    print(f"Removed non-IG URLs: {len(all_raw_items) - len(instagram_items)}")
    
    # Step 2: remove junk
    profile_items = [it for it in instagram_items if is_valid_profile_url(it.get("url", ""))]
    print(f"Removed junk/post URLs: {len(instagram_items) - len(profile_items)}")
    
    # Step 3 & 4: Deduplicate
    normalized_items = []
    for it in profile_items:
        normalized_items.append({
            "url": normalize_url(it.get("url", "")),
            "title": it.get("title", ""),
            "description": it.get("description", "")
        })
    seen = set()
    unique_items = []
    for it in normalized_items:
        if it["url"] not in seen:
            seen.add(it["url"])
            unique_items.append(it)
            
    print(f"Removed duplicates within batch: {len(normalized_items) - len(unique_items)}")
    
    # Step 5: Apify validate
    validated_items = []
    for it in unique_items:
        if _APIFY_IG_URL_PATTERN.match(it["url"]):
            validated_items.append(it)
    print(f"Removed by Apify IG regex validate: {len(unique_items) - len(validated_items)}")
    
    url_validation_removed = (len(all_raw_items) - len(validated_items))
    print(f"TOTAL removed by URL Validation & dedup: {url_validation_removed}")
    
    # 4. Gender Filter
    surviving_candidates = validated_items
    filter_metrics = {"tier1_removed": 0, "tier2_removed": 0}
    if validated_items:
        surviving_candidates, filter_metrics = filter_candidate_profiles(
            candidates=validated_items,
            groq_api_key=config.GROQ_API_KEY,
            gemini_api_key=config.GEMINI_API_KEY
        )
    print(f"\nRemoved by Tier 1 Gender Filter (Heuristic): {filter_metrics['tier1_removed']}")
    print(f"Removed by Tier 2 Gender Filter (AI): {filter_metrics['tier2_removed']}")
    
    # 5. Duplicates in Leads Tab
    leads_skipped = 0
    try:
        gc = get_gspread_client()
        sh = gc.open_by_key(config.GOOGLE_SHEET_ID)
        from google_scraper import get_existing_leads_urls
        existing = get_existing_leads_urls(sh)
        
        new_items = []
        for it in surviving_candidates:
            if it["url"] in existing:
                leads_skipped += 1
            else:
                new_items.append(it)
        surviving_candidates = new_items
    except Exception as e:
        print(f"Error checking duplicates: {e}")
        
    print(f"\nRemoved as duplicates already in Leads tab: {leads_skipped}")
    
    print(f"\nFinal saved as new leads: {len(surviving_candidates)}")
    print("="*50)

if __name__ == '__main__':
    analyze_search("Career Coach", "New York City", 10)
    analyze_search("Executive Coach", "New York City", 10)
