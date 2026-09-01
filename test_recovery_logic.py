from google_scraper import _clean_and_filter_candidates

# Mock raw items typical of a Google search
mock_raw_items = [
    {
        "url": "https://www.instagram.com/trainerterryjones/",
        "title": "Trainer Terry Jones (@trainerterryjones) • Instagram photos and videos",
        "description": "I'm a career coach. I teach people how to win in rooms we weren't always invited into.",
        "websiteTitle": ""
    },
    {
        "url": "https://www.instagram.com/p/C_abc123/",
        "title": "Trainer Terry Jones (@trainerterryjones)",
        "description": "You have the right to become someone new in your career.",
        "websiteTitle": "Instagram · trainerterryjones"
    },
    {
        "url": "https://www.instagram.com/reel/D_xyz789/",
        "title": "Road to Hire | \"My career coach was not just ...",
        "description": "My career coach was not just ... :) Hunter The City University of New York Career Center",
        "websiteTitle": "Instagram · roadtohire"
    },
    {
        "url": "https://www.instagram.com/explore/tags/careercoachnyc/",
        "title": "#careercoachnyc hashtag on Instagram",
        "description": "See all photos and videos from hashtag careercoachnyc",
        "websiteTitle": "Instagram"
    }
]

print(f"Total input URLs: {len(mock_raw_items)}")
for it in mock_raw_items:
    print(f"  {it['url']}")

print("\nRunning _clean_and_filter_candidates...\n")
results = _clean_and_filter_candidates(mock_raw_items)

print(f"\nTotal output URLs: {len(results)}")
for res in results:
    print(f"  {res['url']}")
