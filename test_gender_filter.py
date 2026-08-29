import os
import sys
from gender_filter import (
    parse_google_title,
    clean_google_bio,
    extract_gender_signals,
    evaluate_tier1,
    filter_candidate_profiles,
    UNISEX_NAMES,
    FEMALE_FIRST_NAMES
)

def run_tier1_tests():
    print("=" * 70)
    print(" [TEST SUITE] TIER 1 SMART GENDER PRE-FILTER ISOLATION TEST")
    print("=" * 70)

    test_cases = [
        {
            "id": 1,
            "description": "Obvious female: Female name + Female pronouns in bio",
            "title": "Sarah Jenkins (@sarahjenkins_coaching) • Instagram photos and videos",
            "url": "https://www.instagram.com/sarahjenkins_coaching/",
            "bio_raw": "3,420 Followers, 810 Following, 342 Posts - Executive Coach in Dallas, TX. (she/her). Helping leaders scale.",
            "expected_t1": "REMOVE",
        },
        {
            "id": 2,
            "description": "Obvious female: Female name + Targets women",
            "title": "Jessica Alba (@jessica_coach) • Instagram",
            "url": "https://www.instagram.com/jessica_coach/",
            "bio_raw": "1,200 Followers - Leadership Coach. I help women entrepreneurs build 7-figure businesses.",
            "expected_t1": "REMOVE",
        },
        {
            "id": 3,
            "description": "Obvious female: Female name + Female self-description (mama / wife)",
            "title": "Emily Watson (@emilywatson) • Instagram",
            "url": "https://www.instagram.com/emilywatson/",
            "bio_raw": "5,000 Followers - Boy mom of 2 | Wife | Business Coach for executives in Austin.",
            "expected_t1": "REMOVE",
        },
        {
            "id": 4,
            "description": "Pronouns alone (unisex/unclear name + she/they pronouns)",
            "title": "Riley Smith (@rileysmith) • Instagram photos",
            "url": "https://www.instagram.com/rileysmith/",
            "bio_raw": "800 Followers - Career strategist (she/they).",
            "expected_t1": "REMOVE",
        },
        {
            "id": 5,
            "description": "Female targeting alone (Unisex/business title)",
            "title": "Apex Coaching (@apexcoaching) • Instagram",
            "url": "https://www.instagram.com/apexcoaching/",
            "bio_raw": "10k Followers - Dedicated to empowering women in business and female founders.",
            "expected_t1": "REMOVE",
        },
        {
            "id": 6,
            "description": "Obvious Male Coach: Male name + Male/neutral bio",
            "title": "John Miller (@johnmiller_executive) • Instagram photos and videos",
            "url": "https://www.instagram.com/johnmiller_executive/",
            "bio_raw": "2,100 Followers, 450 Following, 210 Posts - Executive Leadership Coach in Houston, Texas. Scaling tech founders.",
            "expected_t1": "KEEP",
        },
        {
            "id": 7,
            "description": "Unisex name alone: Taylor (No female signals -> MUST KEEP)",
            "title": "Taylor Brooks (@taylorbrooks_coach) • Instagram",
            "url": "https://www.instagram.com/taylorbrooks_coach/",
            "bio_raw": "1,500 Followers - Leadership & Performance Strategist in Dallas, TX.",
            "expected_t1": "KEEP",
        },
        {
            "id": 8,
            "description": "Unisex name alone: Jordan (No female signals -> MUST KEEP)",
            "title": "Jordan Reed (@jordanreed_leads) • Instagram",
            "url": "https://www.instagram.com/jordanreed_leads/",
            "bio_raw": "3,000 Followers - Executive advisor for C-suite leaders.",
            "expected_t1": "KEEP",
        },
        {
            "id": 9,
            "description": "Unisex name alone: Alex / Sam / Chris (MUST KEEP)",
            "title": "Alex Vance (@alexvance) • Instagram",
            "url": "https://www.instagram.com/alexvance/",
            "bio_raw": "900 Followers - Business consulting & executive coaching.",
            "expected_t1": "KEEP",
        },
        {
            "id": 10,
            "description": "Business / Agency profile (Summit Leadership Group -> MUST KEEP)",
            "title": "Summit Leadership Group (@summitleadership) • Instagram",
            "url": "https://www.instagram.com/summitleadership/",
            "bio_raw": "1,150 Followers, 340 Following - Executive coaching firm based in Dallas, TX. We develop executive teams.",
            "expected_t1": "KEEP",
        },
        {
            "id": 11,
            "description": "Female name alone without supporting bio -> AMBIGUOUS (Needs Tier 2 AI check)",
            "title": "Amanda Collins (@amandacollins) • Instagram",
            "url": "https://www.instagram.com/amandacollins/",
            "bio_raw": "300 Followers - Executive Coach in Texas.",
            "expected_t1": "AMBIGUOUS",
        },
        {
            "id": 12,
            "description": "Cultural / Non-English male name (e.g. Andrea Pirlo / Andrea Bocelli in Italian -> Andrea is unisex/ambiguous)",
            "title": "Andrea Rossi (@andrearossi_coach) • Instagram",
            "url": "https://www.instagram.com/andrearossi_coach/",
            "bio_raw": "500 Followers - International executive coach based in Dallas.",
            "expected_t1": "KEEP",
        },
        {
            "id": 13,
            "description": "Female First Name + Female Username Token -> REMOVE",
            "title": "Rachel Green (@rachel_queen_coach) • Instagram",
            "url": "https://www.instagram.com/rachel_queen_coach/",
            "bio_raw": "800 Followers - Executive coaching.",
            "expected_t1": "REMOVE",
        }
    ]

    passed_count = 0
    failed_count = 0

    for case in test_cases:
        cid = case["id"]
        desc = case["description"]
        title = case["title"]
        url = case["url"]
        bio_raw = case["bio_raw"]
        expected = case["expected_t1"]

        full_name, user_from_title = parse_google_title(title)
        username = user_from_title or case["url"].strip("/").split("/")[-1]
        bio_clean = clean_google_bio(bio_raw)

        signals = extract_gender_signals(full_name, username, bio_clean)
        action, reason = evaluate_tier1(signals, full_name, username, bio_clean)

        passed = (action == expected)
        if passed:
            passed_count += 1
            print(f"[PASS] Case {cid:2d}: {desc}")
            print(f"       Action: {action} (Expected: {expected}) | Reason: {reason}")
        else:
            failed_count += 1
            print(f"[FAIL] Case {cid:2d}: {desc}")
            print(f"       Action: {action} != Expected: {expected} | Reason: {reason}")
            print(f"       Signals: {signals}")

    print("\n" + "=" * 70)
    print(f" [TEST RESULTS] Total: {len(test_cases)} | Passed: {passed_count} | Failed: {failed_count}")
    print("=" * 70)

    if failed_count > 0:
        print("[ERROR] Some test cases failed.")
        sys.exit(1)
    else:
        print("[SUCCESS] All Tier 1 test cases passed perfectly!")

    # Test Full Batch Filter with Tier 2 Fallback (No API Keys provided)
    print("\n" + "=" * 70)
    print(" [TEST SUITE] FULL BATCH FILTER & TIER 2 SAFE FALLBACK TEST")
    print("=" * 70)
    
    candidates = [
        {"title": c["title"], "url": c["url"], "description": c["bio_raw"]}
        for c in test_cases
    ]
    
    # Run with empty API keys to test safe fallback behavior
    surviving, metrics = filter_candidate_profiles(
        candidates=candidates,
        groq_api_key="",
        gemini_api_key=""
    )

    print(f"\n[+] Batch Test Metrics: {metrics}")
    # Cases 1, 2, 3, 4, 5, 13 must be removed by Tier 1 (6 profiles)
    # Case 11 is ambiguous -> sent to Tier 2 -> with no keys, kept safely (1 profile)
    # Cases 6, 7, 8, 9, 10, 12 kept by Tier 1 (6 profiles)
    # Total kept = 7 profiles, Total removed = 6 profiles
    assert metrics["tier1_removed"] == 6, f"Expected 6 Tier 1 removals, got {metrics['tier1_removed']}"
    assert metrics["tier2_sent"] == 1, f"Expected 1 sent to Tier 2, got {metrics['tier2_sent']}"
    assert metrics["kept_total"] == 7, f"Expected 7 kept total, got {metrics['kept_total']}"
    assert len(surviving) == 7, f"Expected 7 surviving profiles, got {len(surviving)}"
    print("[SUCCESS] Full batch filter & Tier 2 safe fallback verified successfully!")

if __name__ == "__main__":
    run_tier1_tests()

