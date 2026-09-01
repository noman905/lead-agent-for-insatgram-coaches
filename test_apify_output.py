import sys
import config
from apify_client import ApifyClient
import json

client = ApifyClient(config.APIFY_API_TOKEN)
run_input = {
    "queries": '"career coach" "New York" instagram.com',
    "maxPagesPerQuery": 1,
    "resultsPerPage": 20
}
run = client.actor('apify/google-search-scraper').call(run_input=run_input)
dataset_id = run.get('defaultDatasetId')
items = list(client.dataset(dataset_id).iterate_items())

results = []
for item in items:
    for r in item.get('organicResults', []):
        url = r.get('url', '')
        if 'instagram.com' in url and ('/p/' in url or '/reel/' in url):
            results.append(r)

print(json.dumps(results[:3], indent=2))
