import sys
import config
from google_scraper import fetch_instagram_profiles_from_google

def run_niche_overlap_test():
    niches = [
        "Executive Coach",
        "CEO Coach",
        "C-Suite Coach",
        "Executive Mentor"
    ]
    state = "New York"
    pages = 1 # 1 page per variation to keep it fast but representative
    
    results_by_niche = {}
    all_unique_profiles = set()
    
    print(f"--- STARTING NICHE VARIATION TEST FOR {state} ---")
    
    for niche in niches:
        print(f"\n[+] Fetching for: '{niche}'")
        try:
            # We pass sh=None to skip the Google Sheet dedup for this isolated test
            _, status_msg, clean_urls = fetch_instagram_profiles_from_google(
                niche=niche,
                state=state,
                pages=pages,
                api_token=config.APIFY_API_TOKEN,
                sh=None
            )
            # clean_urls is already deduplicated within its own run
            urls_set = set(clean_urls)
            results_by_niche[niche] = urls_set
            
            print(f"    -> Found {len(urls_set)} clean profile URLs for '{niche}'")
            
        except Exception as e:
            print(f"    -> Error fetching '{niche}': {e}")
            results_by_niche[niche] = set()

    # Analysis
    print("\n\n=== OVERLAP ANALYSIS ===")
    base_niche = "Executive Coach"
    base_results = results_by_niche.get(base_niche, set())
    
    print(f"Base Search '{base_niche}': {len(base_results)} leads")
    
    total_net_new = 0
    for niche in niches:
        if niche == base_niche:
            continue
            
        niche_results = results_by_niche.get(niche, set())
        
        # Calculate how many in this niche were NOT in the base search
        net_new = niche_results - base_results
        overlap = niche_results.intersection(base_results)
        
        print(f"\nVariant Search '{niche}':")
        print(f"  - Total Found: {len(niche_results)}")
        print(f"  - Overlap with '{base_niche}': {len(overlap)} (These would be duplicates)")
        print(f"  - NET NEW LEADS: {len(net_new)} (These are totally fresh leads!)")
        
        total_net_new += len(net_new)
        # Add to base results so we calculate true unique addition across all variations
        base_results.update(niche_results)
        
    print(f"\n======================================")
    print(f"Summary:")
    print(f"If you ONLY searched 'Executive Coach': {len(results_by_niche.get(base_niche, set()))} leads")
    print(f"If you searched ALL 4 variations: {len(base_results)} total unique leads")
    print(f"Increase in leads by using variations: +{total_net_new} net new leads!")
    print(f"======================================")


if __name__ == "__main__":
    run_niche_overlap_test()
