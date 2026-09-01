import sys
import config
from apify_client import ApifyClient
from google_scraper import _clean_and_filter_candidates

def run_live_recovery_test():
    print("Initializing Apify to search specifically for Instagram Reels...")
    client = ApifyClient(config.APIFY_API_TOKEN)
    
    # We intentionally search for reels to force the scraper to find "junk" URLs
    query = 'site:instagram.com/reel/ "career coach"'
    print(f"Query: {query}")
    
    run_input = {
        "queries": query,
        "maxPagesPerQuery": 1,
        "resultsPerPage": 20,
        "mobileResults": False
    }
    
    run = client.actor("apify/google-search-scraper").call(run_input=run_input)
    dataset_id = getattr(run, "default_dataset_id", getattr(run, "defaultDatasetId", None))
    if not dataset_id and hasattr(run, "__getitem__"):
        try:
            dataset_id = run["defaultDatasetId"]
        except (KeyError, TypeError):
            pass
    
    all_raw_items = []
    print("\n[+] Raw results extracted from Google:")
    for item in client.dataset(dataset_id).iterate_items():
        if "organicResults" in item and isinstance(item["organicResults"], list):
            for result in item["organicResults"]:
                u = result.get("url") or result.get("link")
                if u:
                    raw_item = {
                        "url": u,
                        "title": result.get("title") or "",
                        "description": result.get("description") or "",
                        "websiteTitle": result.get("websiteTitle") or result.get("siteName") or ""
                    }
                    all_raw_items.append(raw_item)
                    try:
                        print(f"  - Found: {u}")
                        title_str = raw_item['websiteTitle'] or raw_item['title']
                        clean_title = title_str.encode('ascii', 'ignore').decode('ascii')
                        print(f"    (title: {clean_title})")
                    except Exception:
                        pass

    print(f"\n[+] Total raw items found: {len(all_raw_items)}")
    
    print("\n[+] Running our new recovery and filtering logic...")
    recovered_items = _clean_and_filter_candidates(all_raw_items)
    
    print(f"\n[SUCCESS] Final Clean Profile URLs after recovery ({len(recovered_items)}):")
    for res in recovered_items:
        print(f"  -> {res['url']}")

if __name__ == "__main__":
    run_live_recovery_test()
