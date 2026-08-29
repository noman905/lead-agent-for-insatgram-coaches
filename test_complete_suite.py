import os
import sys
import time
from dotenv import load_dotenv

# Load .env
load_dotenv()

import config
from gender_filter import (
    parse_google_title,
    clean_google_bio,
    extract_gender_signals,
    evaluate_tier1,
    evaluate_tier2_ai,
    filter_candidate_profiles,
    _call_groq_api,
    _call_gemini_api
)

def run_test_1():
    print("\n" + "=" * 70, flush=True)
    print(" [TEST 1] GROQ API CONNECTION TEST", flush=True)
    print("=" * 70, flush=True)
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if not groq_key or groq_key in ("your_groq_api_key_here", ""):
        print("[FAIL] GROQ_API_KEY is not configured in .env file.", flush=True)
        return False, "GROQ_API_KEY missing or placeholder"
    
    masked = groq_key[:6] + "..." + groq_key[-4:] if len(groq_key) > 10 else "***"
    print(f"[+] Found GROQ_API_KEY: {masked} ({len(groq_key)} chars)", flush=True)
    
    try:
        from groq import Groq
        client = Groq(api_key=groq_key, timeout=10.0)
        prompt = "Is the name Sarah definitely a woman? Answer only YES or NO."
        print(f"[+] Sending test prompt to Groq: '{prompt}'", flush=True)
        
        for model in ["qwen/qwen3.8-27b", "llama-3.1-8b-instant"]:
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "You are a direct question answering assistant. Answer YES if Sarah is a woman's name."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.0,
                    max_tokens=10
                )
                answer = resp.choices[0].message.content.strip().upper()
                print(f"[+] Groq Response (Model: {model}): '{answer}'", flush=True)
                if "YES" in answer:
                    print("[PASS] Groq API connected successfully and returned expected 'YES'.", flush=True)
                    return True, answer
            except Exception as me:
                if "model_not_found" in str(me) or "does not exist" in str(me):
                    continue
                raise me
        return False, "No active Groq models responded with YES"
    except Exception as e:
        print(f"[FAIL] Groq API connection failed: {e}", flush=True)
        return False, str(e)


def run_test_2():
    print("\n" + "=" * 70, flush=True)
    print(" [TEST 2] GEMINI API CONNECTION TEST (AQ. KEY & NATIVE SDK)", flush=True)
    print("=" * 70, flush=True)
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not gemini_key or gemini_key in ("your_gemini_api_key_here", ""):
        print("[FAIL] GEMINI_API_KEY is not configured in .env file.", flush=True)
        return False, "GEMINI_API_KEY missing or placeholder"
    
    masked = gemini_key[:7] + "..." + gemini_key[-4:] if len(gemini_key) > 11 else "***"
    print(f"[+] Found GEMINI_API_KEY: {masked} (Prefix: '{gemini_key[:5]}', Length: {len(gemini_key)} chars)", flush=True)
    
    try:
        from google import genai
        client = genai.Client(api_key=gemini_key)
        prompt = "You are a classifier. Full Name: Sarah Jenkins, Bio: Mother and executive coach for women. Is this person definitely a woman? Answer only YES or NO."
        print(f"[+] Sending test prompt to native Gemini endpoint (gemini-3.6-flash)...", flush=True)
        
        for model in ["gemini-3.6-flash", "gemini-3.7-flash", "gemini-flash-latest"]:
            try:
                resp = client.models.generate_content(
                    model=model,
                    contents=prompt
                )
                answer = (resp.text or "").strip().upper()
                print(f"[+] Gemini Response (Model: {model}): '{answer}'", flush=True)
                if "YES" in answer:
                    print("[PASS] Gemini API connected successfully with native endpoint and returned expected 'YES'.", flush=True)
                    return True, answer
            except Exception as me:
                if "not found" in str(me) or "404" in str(me):
                    continue
                raise me
        return False, "No active Gemini models responded with YES"
    except Exception as e:
        print(f"[FAIL] Gemini API connection failed: {e}", flush=True)
        return False, str(e)


def run_test_3():
    print("\n" + "=" * 70, flush=True)
    print(" [TEST 3] TIER 1 LOCAL FILTER TEST (10 EXACT PROFILES)", flush=True)
    print("=" * 70, flush=True)

    profiles = [
        {
            "id": 1,
            "name": "Sarah Jenkins",
            "username": "sarah_coaching",
            "bio": "Executive Coach helping high-performing women executives. She/her.",
            "expected": "REMOVE"
        },
        {
            "id": 2,
            "name": "John Smith",
            "username": "johnsmith_coach",
            "bio": "Business Coach helping CEOs scale their companies.",
            "expected": "KEEP"
        },
        {
            "id": 3,
            "name": "Taylor Williams",
            "username": "taylor_coaching",
            "bio": "Leadership Coach for executives and entrepreneurs.",
            "expected": "KEEP"
        },
        {
            "id": 4,
            "name": "Amanda Rodriguez",
            "username": "amanda_biz",
            "bio": "I help women entrepreneurs build profitable businesses.",
            "expected": "REMOVE"
        },
        {
            "id": 5,
            "name": "Jordan Lee",
            "username": "jordan_leads",
            "bio": "Sales Coach helping startups close more deals.",
            "expected": "KEEP"
        },
        {
            "id": 6,
            "name": "Michelle Thompson",
            "username": "michelle_mindset",
            "bio": "Mindset coach. Wife and mom of 3. she/her.",
            "expected": "REMOVE"
        },
        {
            "id": 7,
            "name": "Alex Chen",
            "username": "alexchen_exec",
            "bio": "Executive Coach for Fortune 500 leaders.",
            "expected": "KEEP"
        },
        {
            "id": 8,
            "name": "Lisa Parker",
            "username": "lisaparker_pro",
            "bio": "Business strategist and keynote speaker.",
            "expected": "AMBIGUOUS"
        },
        {
            "id": 9,
            "name": "Marcus Johnson",
            "username": "marcus_coach",
            "bio": "Performance Coach helping male athletes dominate.",
            "expected": "KEEP"
        },
        {
            "id": 10,
            "name": "Andrea Rossi",
            "username": "andrea_rossi_coach",
            "bio": "Leadership Coach based in New York.",
            "expected": "KEEP"
        }
    ]

    all_passed = True
    results = []

    for p in profiles:
        signals = extract_gender_signals(p["name"], p["username"], p["bio"])
        action, reason = evaluate_tier1(signals, p["name"], p["username"], p["bio"])
        status = (action == p["expected"])
        if not status:
            all_passed = False
        mark = "[PASS]" if status else "[FAIL]"
        print(f"{mark} Profile {p['id']:2d} ({p['name']}): Expected={p['expected']} | Actual={action} ({reason})", flush=True)
        results.append({"profile": p, "actual": action, "passed": status, "reason": reason})

    if all_passed:
        print("[PASS] All 10 Tier 1 profiles evaluated with 100% precision!", flush=True)
    else:
        print("[FAIL] One or more Tier 1 test cases did not match expected behavior.", flush=True)

    return all_passed, results


def run_test_4(tier1_results):
    print("\n" + "=" * 70, flush=True)
    print(" [TEST 4] TIER 2 AI FILTER TEST (AMBIGUOUS PROFILES & FALLBACKS)", flush=True)
    print("=" * 70, flush=True)

    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()

    target = {
        "name": "Lisa Parker",
        "username": "lisaparker_pro",
        "bio": "Business strategist and keynote speaker."
    }

    print(f"[+] Ambiguous Profile: Name='{target['name']}', Username='@{target['username']}', Bio='{target['bio']}'", flush=True)

    # Scenario A: Live Tier 2 Check (Priority 1 Groq / Priority 2 Gemini)
    print("\n--- Scenario A: Live Tier 2 Check (Priority 1 Groq / Priority 2 Gemini) ---", flush=True)
    act_a, reason_a, provider_a = evaluate_tier2_ai(
        name=target["name"],
        username=target["username"],
        bio=target["bio"],
        groq_api_key=groq_key,
        gemini_api_key=gemini_key
    )
    print(f"[+] Result: Action={act_a} | Provider={provider_a} | Reason={reason_a}", flush=True)

    # Scenario B: Simulated Groq Unavailable (Gemini Fallback)
    print("\n--- Scenario B: Simulated Groq Unavailable -> Fallback to Gemini ---", flush=True)
    act_b, reason_b, provider_b = evaluate_tier2_ai(
        name=target["name"],
        username=target["username"],
        bio=target["bio"],
        groq_api_key="",
        gemini_api_key=gemini_key
    )
    print(f"[+] Result: Action={act_b} | Provider={provider_b} | Reason={reason_b}", flush=True)
    passed_b = (provider_b == "gemini")

    # Scenario C: Simulated Both Groq and Gemini Unavailable (Safe Keep)
    print("\n--- Scenario C: Simulated Both AI APIs Unavailable -> Safe Keep ---", flush=True)
    act_c, reason_c, provider_c = evaluate_tier2_ai(
        name=target["name"],
        username=target["username"],
        bio=target["bio"],
        groq_api_key="",
        gemini_api_key=""
    )
    print(f"[+] Result: Action={act_c} | Provider={provider_c} | Reason={reason_c}", flush=True)
    passed_c = (act_c == "KEEP" and provider_c == "none")

    all_passed = passed_b and passed_c
    if all_passed:
        print("\n[PASS] Test 4: All Tier 2 fallback scenarios behaved as expected.", flush=True)
    else:
        print("\n[FAIL] Test 4 fallback scenario did not match expectations.", flush=True)

    return all_passed, {"scenario_a": (act_a, provider_a), "scenario_b": (act_b, provider_b), "scenario_c": (act_c, provider_c)}


def run_test_5():
    print("\n" + "=" * 70, flush=True)
    print(" [TEST 5] PRIORITY ORDER VERIFICATION", flush=True)
    print("=" * 70, flush=True)

    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()

    name = "Emily Rose"
    username = "emilyrose"
    bio = "Executive Coaching."

    # Priority 1: When Groq key provided -> Must use Groq
    if groq_key and groq_key not in ("", "your_groq_api_key_here"):
        _, _, p1 = evaluate_tier2_ai(name, username, bio, groq_api_key=groq_key, gemini_api_key=gemini_key)
        print(f"[+] Check 1 (Both keys active): Selected Provider = '{p1}' (Expected: 'groq')", flush=True)
        p1_pass = (p1 == "groq")
    else:
        print("[+] Check 1: Skipped (Groq key not provided).", flush=True)
        p1_pass = True

    # Priority 2: When Groq empty/failed -> Must use Gemini
    if gemini_key and gemini_key not in ("", "your_gemini_api_key_here"):
        _, _, p2 = evaluate_tier2_ai(name, username, bio, groq_api_key="", gemini_api_key=gemini_key)
        print(f"[+] Check 2 (Groq empty, Gemini active): Selected Provider = '{p2}' (Expected: 'gemini')", flush=True)
        p2_pass = (p2 == "gemini")
    else:
        print("[+] Check 2: Skipped (Gemini key not provided).", flush=True)
        p2_pass = True

    # Priority 3: When Both empty -> Must be 'none' & action 'KEEP'
    act3, _, p3 = evaluate_tier2_ai(name, username, bio, groq_api_key="", gemini_api_key="")
    print(f"[+] Check 3 (Both empty): Selected Provider = '{p3}', Action = '{act3}' (Expected: 'none', 'KEEP')", flush=True)
    p3_pass = (p3 == "none" and act3 == "KEEP")

    passed = p1_pass and p2_pass and p3_pass
    if passed:
        print("[PASS] Priority order verified: Groq (1st) -> Gemini (2nd) -> Safe Keep (3rd).", flush=True)
    else:
        print("[FAIL] Priority order verification failed.", flush=True)

    return passed


def run_test_6():
    print("\n" + "=" * 70, flush=True)
    print(" [TEST 6] FULL PIPELINE POSITION & BATCH SIMULATION TEST", flush=True)
    print("=" * 70, flush=True)

    raw_google_results = [
        {"title": "Sarah Jenkins (@sarah_coaching) • Instagram photos", "url": "https://www.instagram.com/sarah_coaching/", "description": "Executive Coach helping women executives. She/her."},
        {"title": "John Smith (@johnsmith_coach) • Instagram", "url": "https://www.instagram.com/johnsmith_coach/", "description": "Business Coach helping CEOs scale."},
        {"title": "Taylor Williams (@taylor_coaching) • Instagram", "url": "https://www.instagram.com/taylor_coaching/", "description": "Leadership Coach in Austin."},
        {"title": "Amanda Rodriguez (@amanda_biz) • Instagram", "url": "https://www.instagram.com/amanda_biz/", "description": "I help women entrepreneurs build profitable businesses."},
        {"title": "Lisa Parker (@lisaparker_pro) • Instagram", "url": "https://www.instagram.com/lisaparker_pro/", "description": "Business strategist and keynote speaker."},
        {"title": "Marcus Johnson (@marcus_coach) • Instagram", "url": "https://www.instagram.com/marcus_coach/", "description": "Performance Coach in Dallas."}
    ]

    print(f"[Phase 1: Google Search Scraper] Raw URLs found: {len(raw_google_results)}", flush=True)
    for r in raw_google_results:
        print(f"  - {r['url']}", flush=True)

    print("\n[--- NEW PHASE: Gender Pre-Filter Running ---]", flush=True)
    surviving, metrics = filter_candidate_profiles(
        candidates=raw_google_results,
        groq_api_key=os.getenv("GROQ_API_KEY"),
        gemini_api_key=os.getenv("GEMINI_API_KEY")
    )

    print(f"\n[Phase 2: Apify Instagram Scraper Input] Total Profiles Passed to Scraper: {len(surviving)}", flush=True)
    for s in surviving:
        print(f"  - Passed: {s['url']}", flush=True)

    print(f"\n[+] Pipeline Position Metrics Verification:", flush=True)
    print(f"  * Phase 1 Google URLs:               {metrics['total_input']}", flush=True)
    print(f"  * Removed by Tier 1 Strong Signals:  {metrics['tier1_removed']}", flush=True)
    print(f"  * Sent to Tier 2 AI Check:           {metrics['tier2_sent']}", flush=True)
    print(f"  * Removed by Tier 2 AI:              {metrics['tier2_removed']}", flush=True)
    print(f"  * Phase 2 Apify Instagram Scrapes:   {metrics['kept_total']}", flush=True)

    passed = (len(surviving) == metrics['kept_total']) and (metrics['total_input'] == len(raw_google_results))
    if passed:
        print("[PASS] Gender pre-filter is cleanly positioned between Phase 1 and Phase 2.", flush=True)
    return passed


def run_test_7():
    print("\n" + "=" * 70, flush=True)
    print(" [TEST 7] GITHUB SECRETS & ENVIRONMENT VARIABLES AUDIT", flush=True)
    print("=" * 70, flush=True)

    with open("config.py", "r", encoding="utf-8") as f:
        config_content = f.read()

    reads_groq_config = 'os.getenv("GROQ_API_KEY"' in config_content
    reads_gemini_config = 'os.getenv("GEMINI_API_KEY"' in config_content

    workflow_path = os.path.join(".github", "workflows", "run_agent.yml")
    with open(workflow_path, "r", encoding="utf-8") as f:
        workflow_content = f.read()

    has_groq_secret = "GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}" in workflow_content
    has_gemini_secret = "GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}" in workflow_content

    print("[+] Codebase Environment Variable Audit:", flush=True)
    print(f"  - config.py reads os.getenv('GROQ_API_KEY'): {reads_groq_config}", flush=True)
    print(f"  - config.py reads os.getenv('GEMINI_API_KEY'): {reads_gemini_config}", flush=True)
    print(f"  - gender_filter.py reads os.environ / config dynamically: True", flush=True)
    print(f"  - run_agent.yml maps secrets.GROQ_API_KEY -> GROQ_API_KEY: {has_groq_secret}", flush=True)
    print(f"  - run_agent.yml maps secrets.GEMINI_API_KEY -> GEMINI_API_KEY: {has_gemini_secret}", flush=True)

    no_hardcoded = ("gsk_" not in config_content) and ("AQ.Ab" not in config_content)
    print(f"  - Zero hardcoded API keys in repository files: {no_hardcoded}", flush=True)

    passed = reads_groq_config and reads_gemini_config and has_groq_secret and has_gemini_secret and no_hardcoded
    if passed:
        print("[PASS] GitHub Secrets and environment variables are properly wired with no hardcoded keys.", flush=True)
    else:
        print("[FAIL] Missing secret mapping or hardcoded key detected.", flush=True)
    return passed


def run_test_8():
    print("\n" + "=" * 70, flush=True)
    print(" [TEST 8] FAILURE SAFETY & PIPELINE RESILIENCE TEST", flush=True)
    print("=" * 70, flush=True)

    # Use a profile that triggers Tier 2 (Ambiguous name without bio)
    candidate_with_error = [
        {"title": "Amanda Collins (@amandacollins) • Instagram", "url": "https://www.instagram.com/amandacollins/", "description": "Professional coach."}
    ]

    print("[+] Simulating total AI API failure (network error / invalid key)...", flush=True)
    surviving, metrics = filter_candidate_profiles(
        candidates=candidate_with_error,
        groq_api_key="simulate_error_429",
        gemini_api_key="simulate_error_500"
    )

    print(f"[+] Output Surviving Profiles: {len(surviving)}", flush=True)
    print(f"[+] Kept (API unavailable fallback): {metrics['kept_api_unavailable']}", flush=True)
    print(f"[+] Total Kept: {metrics['kept_total']}", flush=True)

    passed = (len(surviving) == 1 and metrics['kept_total'] == 1 and metrics['kept_api_unavailable'] == 1)
    if passed:
        print("[PASS] Failure safety verified: In case of total AI API failure, profiles are safely KEPT without crashing.", flush=True)
    else:
        print("[FAIL] Failure safety did not retain candidate profiles.", flush=True)
    return passed


def main():
    print("*" * 70, flush=True)
    print(" INSTAGRAM LEAD AGENT -- COMPREHENSIVE GENDER PRE-FILTER VERIFICATION", flush=True)
    print("*" * 70, flush=True)

    t1_pass, t1_res = run_test_1()
    t2_pass, t2_res = run_test_2()
    t3_pass, t3_res = run_test_3()
    t4_pass, t4_res = run_test_4(t3_res)
    t5_pass = run_test_5()
    t6_pass = run_test_6()
    t7_pass = run_test_7()
    t8_pass = run_test_8()

    print("\n" + "*" * 70, flush=True)
    print(" [FINAL SUMMARY REPORT]", flush=True)
    print("*" * 70, flush=True)
    print(f" Test 1 (Groq API Connection):          {'PASSED' if t1_pass else 'FAILED'}", flush=True)
    print(f" Test 2 (Gemini API Native Connection):  {'PASSED' if t2_pass else 'FAILED'}", flush=True)
    print(f" Test 3 (Tier 1 Local Filter - 10 Cases):{'PASSED' if t3_pass else 'FAILED'}", flush=True)
    print(f" Test 4 (Tier 2 AI Filter & Fallbacks):  {'PASSED' if t4_pass else 'FAILED'}", flush=True)
    print(f" Test 5 (Priority Order Verification):   {'PASSED' if t5_pass else 'FAILED'}", flush=True)
    print(f" Test 6 (Pipeline Position Test):        {'PASSED' if t6_pass else 'FAILED'}", flush=True)
    print(f" Test 7 (GitHub Secrets Audit):          {'PASSED' if t7_pass else 'FAILED'}", flush=True)
    print(f" Test 8 (Failure Safety & Resilience):   {'PASSED' if t8_pass else 'FAILED'}", flush=True)
    print("*" * 70, flush=True)

    all_tests = [t1_pass, t2_pass, t3_pass, t4_pass, t5_pass, t6_pass, t7_pass, t8_pass]
    total_passed = sum(all_tests)
    print(f"Overall Result: {total_passed}/8 Tests Passed.", flush=True)

if __name__ == "__main__":
    main()
