import os
import re
import sys
from urllib.parse import urlparse
import config

# ---------------------------------------------------------------------------
# Curated Name Dictionaries
# ---------------------------------------------------------------------------

# Unisex / Ambiguous names: MUST NEVER be treated as exclusively female names
UNISEX_NAMES = {
    "alex", "taylor", "jordan", "sam", "casey", "riley", "chris", "pat", 
    "morgan", "jamie", "avery", "cameron", "dakota", "devin", "drew", 
    "dylan", "elliot", "elliott", "emerson", "finley", "frankie", "harper", 
    "hayden", "jesse", "jessie", "kendall", "logan", "parker", "peyton", 
    "quinn", "reese", "rowan", "sage", "shawn", "skylar", "skyler", 
    "sydney", "terry", "dana", "leslie", "tracy", "robin", "shannon", 
    "kelly", "courtney", "ashley", "jean", "lee", "rene", "renee", 
    "ali", "kim", "jan", "angel", "marion", "dominique", "claude", 
    "michel", "andrea", "kai", "eden", "shiloh", "river", "phoenix", 
    "amari", "milan", "lennon", "remy", "sloan", "sloane", "tatum", 
    "oakley", "charlie", "billie", "bobbie", "cleo", "eden", "gene",
    "glenn", "harley", "indiana", "justice", "kerry", "london", "merrill",
    "monroe", "noel", "paris", "perry", "reagan", "reid", "shiloh", "tristan",
    "val", "wynn"
}

# Distinct, unambiguous female first names across international conventions
FEMALE_FIRST_NAMES = {
    # Common English / American
    "sarah", "sara", "jessica", "emily", "amanda", "jennifer", "stephanie", 
    "nicole", "elizabeth", "heather", "rachel", "lauren", "megan", "amber", 
    "brittany", "danielle", "samantha", "rebecca", "kayla", "victoria", 
    "chelsea", "vanessa", "katherine", "christina", "melissa", "laura", 
    "kristen", "hannah", "erica", "olivia", "emma", "sophia", "isabella", 
    "mia", "charlotte", "amelia", "evelyn", "abigail", "mila", "ella", 
    "camila", "aria", "scarlett", "penelope", "chloe", "layla", "grace", 
    "zoey", "nora", "lily", "eleanor", "claire", "lillian", "audrey", 
    "leah", "stella", "allison", "maya", "anna", "savannah", "katelyn", 
    "lucy", "madelyn", "caroline", "genesis", "gabriella", "hailey", 
    "autumn", "clara", "valentina", "ruby", "alice", "eva", "sophie", 
    "sadie", "delilah", "josephine", "adeline", "jade", "piper", "isla", 
    "lydia", "elena", "brielle", "melanie", "alyssa", "faith", "kylie", 
    "ariana", "kaylee", "cloe", "eliana", "fiona", "mary", "patricia", 
    "linda", "barbara", "susan", "karen", "nancy", "lisa", "betty", 
    "margaret", "sandra", "kimberly", "donna", "michelle", "dorothy", 
    "carol", "deborah", "sharon", "cynthia", "kathleen", "amy", "shirley", 
    "angela", "helen", "brenda", "pamela", "christine", "debra", "catherine", 
    "carolyn", "janet", "ruth", "maria", "diane", "virginia", "julie", 
    "joyce", "joan", "judith", "cheryl", "martha", "jacqueline", "frances", 
    "gloria", "ann", "teresa", "kathryn", "janice", "doris", "julia", 
    "judy", "denise", "marilyn", "beverly", "theresa", "marie", "diana", 
    "natalie", "rose", "lori", "tiffany", "tina", "paula", "peggy", 
    "wendy", "shelly", "brooke", "tara", "beth", "katie", "kristin", 
    "alicia", "erika", "heidi", "stacy", "holly", "krista", "tanya", 
    "carla", "monica", "veronica", "gina", "valerie", "sherry", "tammy", 
    "rhonda", "vicki", "jill", "connie", "cindy", "kristy", "bonnie", 
    "sherri", "toni", "marcia", "patty", "claudia", "debbie", "bethany", 
    "sylvia", "sonia", "katrina", "nadia", "elisa", "tatiana",
    # Latin / Hispanic / European
    "lucia", "sofia", "camila", "martina", "luciana", "mariana", "valeria", 
    "gabriela", "daniela", "carolina", "fernanda", "catalina", "paola", 
    "adriana", "alessandra", "beatrice", "chiara", "francesca", "giulia", 
    "federica", "silvia", "elena", "irene", "marta", "carmen", "ana", 
    "pilar", "rocio", "mercedes", "dolores", "esperanza", "ines", "clara",
    # Arabic / South Asian / East Asian
    "fatima", "aisha", "mariam", "zainab", "khadija", "yasmin", "layla", 
    "nour", "zahra", "priya", "ananya", "deepa", "sunita", "pooja", 
    "neha", "kavita", "shweta", "divya", "meera", "sakura", "yuki", 
    "mei", "ling", "xia", "yoko", "haruka", "minh"
}

# Explicit female keywords found in Instagram usernames
FEMALE_USERNAME_INDICATORS = {
    "mom", "mama", "mrs", "miss", "ms", "girl", "lady", "women", "woman",
    "queen", "femme", "she", "her", "sister", "daughter", "mother", "female"
}

# Explicit phrases in bio indicating female targeting / identity
FEMALE_TARGETING_PHRASES = [
    "i help women", "helping women", "for women", "women entrepreneurs",
    "female founders", "female founder", "for moms", "for mamas",
    "girlboss", "ladies", "sisterhood", "women in business",
    "women leaders", "women executives", "women's coach", "womens coach",
    "empowering women", "women empowerment", "she leads", "female entrepreneur",
    "female leaders", "women in tech", "female empowerment", "women supporting women",
    "women's wellness", "womens health", "women in leadership", "moms in business"
]

FEMALE_SELF_DESC_PATTERNS = [
    r"\b(?:wife|wifey)\b",
    r"\b(?:mama|mom|mother)\s*(?:of|\+|&|\d)",
    r"\b(?:boy\s*mom|girl\s*mom|proud\s*mom|twin\s*mom|working\s*mom)\b",
    r"\bmrs\.?\b",
    r"\b(?:female\s*coach|female\s*mentor|female\s*founder|woman\s*in\s*business|as\s*a\s*woman)\b",
    r"\b(?:motherhood|mompreneur|mamapreneur)\b"
]


# ---------------------------------------------------------------------------
# Snippet & Signal Parsers
# ---------------------------------------------------------------------------

def clean_google_bio(description: str) -> str:
    """
    Strips Google's prepended follower/following stats from description snippet.
    Example:
      '3,420 Followers, 810 Following, 342 Posts - Executive Coach in Austin...'
      -> 'Executive Coach in Austin...'
    """
    if not description:
        return ""
    # Strip "X Followers, Y Following, Z Posts - " prefix
    cleaned = re.sub(
        r"^(?:\d[\d,]*\s*(?:Followers|Following|Posts|Likes)[,\s-]*)+\s*[-–—:]\s*",
        "",
        description.strip(),
        flags=re.IGNORECASE
    )
    return cleaned.strip()


def parse_google_title(title: str) -> tuple[str, str]:
    """
    Extracts (full_name, username) from Google search title.
    Example formats:
      - 'Sarah Jenkins (@sarahjenkins_coaching) • Instagram photos and videos'
      - 'Sarah Jenkins (@sarahjenkins) | Instagram'
      - 'Sarah Jenkins - Executive Coach (@sarahjenkins) on Instagram'
      - 'Summit Leadership Group (@summitleadership) • Instagram'
    """
    if not title:
        return "", ""

    raw = title.strip()
    
    # 1. Extract handle if present in parentheses e.g. (@handle)
    username = ""
    handle_match = re.search(r"\(@([A-Za-z0-9._-]+)\)", raw)
    if handle_match:
        username = handle_match.group(1).strip()

    # 2. Strip standard Instagram title suffixes
    clean_title = re.sub(r"[•|–-]\s*Instagram.*$", "", raw, flags=re.IGNORECASE).strip()
    clean_title = re.sub(r"\(@[A-Za-z0-9._-]+\)", "", clean_title).strip()
    clean_title = re.sub(r"on\s+Instagram.*$", "", clean_title, flags=re.IGNORECASE).strip()

    # 3. If there is a role separator ('|', ' - ', ' – '), take the left-most name part
    if "|" in clean_title:
        clean_title = clean_title.split("|")[0].strip()
    elif " - " in clean_title:
        clean_title = clean_title.split(" - ")[0].strip()
    elif " – " in clean_title:
        clean_title = clean_title.split(" – ")[0].strip()

    full_name = clean_title.strip()
    return full_name, username


def extract_username_from_url(url: str) -> str:
    """Extracts username handle from Instagram URL path."""
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        parts = [p.strip() for p in parsed.path.strip("/").split("/") if p.strip()]
        if parts:
            first = parts[0].lower()
            if first not in ("p", "reel", "stories", "explore", "accounts", "direct", "tv"):
                return parts[0]
    except Exception:
        pass
    return ""


def extract_gender_signals(name: str, username: str, bio: str) -> dict:
    """
    Extracts all 5 gender signals from parsed name, username, and bio.
    """
    name_clean = name.strip().lower()
    bio_lower = bio.lower()
    username_lower = username.lower()

    # --- Signal 1: First Name Analysis ---
    first_name = ""
    if name_clean:
        parts = re.split(r"[\s._-]+", name_clean)
        if parts and parts[0].isalpha():
            first_name = parts[0]

    is_unisex = first_name in UNISEX_NAMES
    is_female_name = (first_name in FEMALE_FIRST_NAMES) and (not is_unisex)

    # --- Signal 2: Username Analysis ---
    # Split username by non-alphanumeric/delimiters
    user_tokens = set(re.findall(r"[a-z]+", username_lower))
    female_user_signals = []
    
    # Check for direct female first name in username tokens
    for token in user_tokens:
        if token in FEMALE_FIRST_NAMES and token not in UNISEX_NAMES:
            female_user_signals.append(token)
        elif token in FEMALE_USERNAME_INDICATORS:
            female_user_signals.append(token)

    has_female_username = len(female_user_signals) > 0

    # --- Signal 3: Pronouns in Bio ---
    # Match: she/her, she/they, her/she, she / her
    pronoun_match = re.search(r"\b(?:she\s*/\s*her|she\s*/\s*they|her\s*/\s*she)\b", bio_lower)
    has_female_pronouns = bool(pronoun_match)
    pronouns_found = pronoun_match.group(0) if pronoun_match else ""

    # --- Signal 4: Targets Women in Bio ---
    matched_target_phrases = []
    for phrase in FEMALE_TARGETING_PHRASES:
        if phrase in bio_lower:
            matched_target_phrases.append(phrase)
    targets_women = len(matched_target_phrases) > 0

    # --- Signal 5: Female Self-Description ---
    matched_self_desc = []
    for pattern in FEMALE_SELF_DESC_PATTERNS:
        match = re.search(pattern, bio_lower)
        if match:
            matched_self_desc.append(match.group(0))
    has_female_self_desc = len(matched_self_desc) > 0

    return {
        "first_name": first_name,
        "is_female_name": is_female_name,
        "is_unisex_name": is_unisex,
        "has_female_username": has_female_username,
        "female_user_signals": female_user_signals,
        "has_female_pronouns": has_female_pronouns,
        "pronouns_found": pronouns_found,
        "targets_women": targets_women,
        "matched_target_phrases": matched_target_phrases,
        "has_female_self_desc": has_female_self_desc,
        "matched_self_desc": matched_self_desc
    }


# ---------------------------------------------------------------------------
# Tier 1: Local Heuristic Evaluation
# ---------------------------------------------------------------------------

def evaluate_tier1(signals: dict, name: str, username: str, bio: str) -> tuple[str, str]:
    """
    Evaluates profile against strict Tier 1 rules.
    Returns:
      ('REMOVE', reason)    -> 100% Confirmed Female with zero ambiguity
      ('KEEP', reason)      -> Confirmed Male / Unisex / Business / No female signs
      ('AMBIGUOUS', reason) -> Needs Tier 2 AI check (e.g. female name alone)
    """
    # 1. 100% Certain Signal: Explicit female pronouns in bio
    if signals["has_female_pronouns"]:
        return "REMOVE", f"Pronouns in bio ({signals['pronouns_found']})"

    # 2. 100% Certain Signal: Explicit female self-description
    if signals["has_female_self_desc"]:
        return "REMOVE", f"Female self-description in bio ({', '.join(signals['matched_self_desc'][:2])})"

    # 3. 100% Certain Signal: Targets women in bio
    if signals["targets_women"]:
        return "REMOVE", f"Bio targets women ({', '.join(signals['matched_target_phrases'][:2])})"

    # 4. Multiple Strong Signals: Female First Name + Female Username Token
    if signals["is_female_name"] and signals["has_female_username"]:
        return "REMOVE", f"Female name '{signals['first_name']}' + female username token '{signals['female_user_signals'][0]}'"

    # 5. Ambiguous: Female first name alone (Could be male in other cultures or agency)
    if signals["is_female_name"]:
        return "AMBIGUOUS", f"Female first name '{signals['first_name']}' alone without supporting bio"

    # 6. Ambiguous: Female username token alone
    if signals["has_female_username"]:
        return "AMBIGUOUS", f"Female username token '{signals['female_user_signals'][0]}' alone"

    # 7. Default: KEEP (Male name, Unisex name, Business, No signals, or Doubt)
    if signals["is_unisex_name"]:
        return "KEEP", f"Unisex name '{signals['first_name']}' with no female indicators"

    return "KEEP", "No female indicators detected (Keep male/business/unclear)"


# ---------------------------------------------------------------------------
# Tier 2: AI Multi-Model Fallback Engine (Groq -> Gemini -> Keep)
# ---------------------------------------------------------------------------

TIER2_PROMPT_TEMPLATE = """You are analyzing an Instagram profile to determine if the account owner is definitely a woman. You must be 100% absolutely certain before answering YES. If there is even the slightest doubt answer NO.

Here is all available information:
Full Name: {name}
Username: {username}
Bio: {bio}

Is this person definitely a woman? Answer only YES or NO. If uncertain answer NO."""


def _call_groq_api(name: str, username: str, bio: str, api_key: str) -> str | None:
    """
    Calls Groq API with llama-3.1-8b-instant.
    Returns 'YES', 'NO', or None (if failed/quota/error).
    """
    if not api_key or api_key.strip() in ("", "your_groq_api_key_here"):
        return None

    try:
        from groq import Groq
        client = Groq(api_key=api_key.strip())
        prompt = TIER2_PROMPT_TEMPLATE.format(name=name or "N/A", username=username or "N/A", bio=bio or "N/A")
        
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=10
        )
        
        answer = response.choices[0].message.content.strip().upper()
        if "YES" in answer:
            return "YES"
        return "NO"
    except Exception as e:
        print(f"    - [TIER 2 WARNING] Groq API call failed ({e}). Falling back to next tier...")
        return None


def _call_gemini_api(name: str, username: str, bio: str, api_key: str) -> str | None:
    """
    Calls Google Gemini API with gemini-2.0-flash / gemini-1.5-flash.
    Returns 'YES', 'NO', or None (if failed/quota/error).
    """
    if not api_key or api_key.strip() in ("", "your_gemini_api_key_here"):
        return None

    try:
        from google import genai
        client = genai.Client(api_key=api_key.strip())
        prompt = TIER2_PROMPT_TEMPLATE.format(name=name or "N/A", username=username or "N/A", bio=bio or "N/A")
        
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        
        answer = (response.text or "").strip().upper()
        if "YES" in answer:
            return "YES"
        return "NO"
    except Exception as e:
        # Fallback attempt to gemini-1.5-flash if 2.0 has issue
        try:
            from google import genai
            client = genai.Client(api_key=api_key.strip())
            prompt = TIER2_PROMPT_TEMPLATE.format(name=name or "N/A", username=username or "N/A", bio=bio or "N/A")
            response = client.models.generate_content(
                model="gemini-1.5-flash",
                contents=prompt
            )
            answer = (response.text or "").strip().upper()
            if "YES" in answer:
                return "YES"
            return "NO"
        except Exception as e2:
            print(f"    - [TIER 2 WARNING] Gemini API call failed ({e2}). Falling back to safe keep...")
            return None


def evaluate_tier2_ai(
    name: str, 
    username: str, 
    bio: str, 
    groq_api_key: str = None, 
    gemini_api_key: str = None
) -> tuple[str, str, str]:
    """
    Executes Tier 2 AI check in exact priority order:
      Priority 1: Groq (llama-3.1-8b-instant)
      Priority 2: Google Gemini (gemini-2.0-flash / gemini-1.5-flash via native google-genai SDK)
      Priority 3: Safe Keep (Log warning & keep profile)
    Returns: (action, reason, provider) where provider is 'groq', 'gemini', or 'none'
    """
    groq_key = groq_api_key or config.GROQ_API_KEY
    gemini_key = gemini_api_key or config.GEMINI_API_KEY

    # Priority 1: Groq
    groq_res = _call_groq_api(name, username, bio, groq_key)
    if groq_res == "YES":
        return "REMOVE", "Groq (llama-3.1-8b-instant) confirmed 100% female", "groq"
    elif groq_res == "NO":
        return "KEEP", "Groq (llama-3.1-8b-instant) answered NO / uncertain", "groq"

    # Priority 2: Gemini
    gemini_res = _call_gemini_api(name, username, bio, gemini_key)
    if gemini_res == "YES":
        return "REMOVE", "Gemini (gemini-2.0-flash) confirmed 100% female", "gemini"
    elif gemini_res == "NO":
        return "KEEP", "Gemini (gemini-2.0-flash) answered NO / uncertain", "gemini"

    # Priority 3: Fallback Safe Keep
    print("    - [TIER 2 WARNING] All free AI APIs exhausted or unavailable -- remaining ambiguous profiles kept without AI check")
    return "KEEP", "Safe Keep: Free AI APIs unavailable or limits exhausted", "none"


# ---------------------------------------------------------------------------
# Main Pre-Filter Entry Point
# ---------------------------------------------------------------------------

def filter_candidate_profiles(
    candidates: list[dict],
    groq_api_key: str = None,
    gemini_api_key: str = None
) -> tuple[list[dict], dict]:
    """
    Runs the 2-Tier Gender Pre-Filter on a list of raw Google search candidate items.
    Each candidate dict has: {'url': str, 'title': str, 'description': str}.
    
    Returns:
      (surviving_candidates, metrics)
    """
    surviving = []
    metrics = {
        "total_input": len(candidates),
        "tier1_removed": 0,
        "tier2_sent": 0,
        "tier2_removed": 0,
        "removed_by_groq": 0,
        "removed_by_gemini": 0,
        "kept_api_unavailable": 0,
        "kept_total": 0
    }

    print("\n" + "=" * 70)
    print(f" [GENDER PRE-FILTER] EVALUATING {len(candidates)} CANDIDATE PROFILES")
    print("=" * 70)

    for idx, cand in enumerate(candidates, 1):
        url = cand.get("url", "")
        title = cand.get("title", "")
        desc = cand.get("description", "")

        full_name, user_from_title = parse_google_title(title)
        username = user_from_title or extract_username_from_url(url)
        bio = clean_google_bio(desc)

        signals = extract_gender_signals(full_name, username, bio)
        t1_action, t1_reason = evaluate_tier1(signals, full_name, username, bio)

        if t1_action == "REMOVE":
            metrics["tier1_removed"] += 1
            print(f"  [{idx:2d}/{len(candidates)}] REMOVED (Tier 1 Rule) -> @{username or 'unknown'}: {t1_reason}")
            continue

        if t1_action == "AMBIGUOUS":
            metrics["tier2_sent"] += 1
            print(f"  [{idx:2d}/{len(candidates)}] AMBIGUOUS (Tier 1: {t1_reason}) -> Sending to Tier 2 AI...")
            t2_action, t2_reason, provider = evaluate_tier2_ai(
                name=full_name,
                username=username,
                bio=bio,
                groq_api_key=groq_api_key,
                gemini_api_key=gemini_api_key
            )

            # Respect rate limits: Add 2 second delay between API calls if AI was queried
            if provider in ("groq", "gemini"):
                time.sleep(2.0)

            if t2_action == "REMOVE":
                metrics["tier2_removed"] += 1
                if provider == "groq":
                    metrics["removed_by_groq"] += 1
                elif provider == "gemini":
                    metrics["removed_by_gemini"] += 1
                print(f"       --> REMOVED (Tier 2 AI) -> @{username}: {t2_reason}")
                continue
            else:
                if provider == "none":
                    metrics["kept_api_unavailable"] += 1
                metrics["kept_total"] += 1
                print(f"       --> KEPT (Tier 2 AI) -> @{username}: {t2_reason}")
                cand["parsed_name"] = full_name
                cand["parsed_username"] = username
                cand["parsed_bio"] = bio
                surviving.append(cand)
                continue

        # Kept directly by Tier 1
        metrics["kept_total"] += 1
        print(f"  [{idx:2d}/{len(candidates)}] KEPT (Tier 1 Rule) -> @{username or 'unknown'}: {t1_reason}")
        cand["parsed_name"] = full_name
        cand["parsed_username"] = username
        cand["parsed_bio"] = bio
        surviving.append(cand)

    print("-" * 70)
    print(f" [GENDER PRE-FILTER SUMMARY]")
    print(f"  * Total Profiles Input:                 {metrics['total_input']}")
    print(f"  * Removed by Tier 1 (Strong Signals):   {metrics['tier1_removed']}")
    print(f"  * Sent to Tier 2 AI (Ambiguous):        {metrics['tier2_sent']}")
    print(f"  * Removed by Groq:                      {metrics['removed_by_groq']}")
    print(f"  * Removed by Gemini:                    {metrics['removed_by_gemini']}")
    print(f"  * Kept (APIs Unavailable / Fallback):   {metrics['kept_api_unavailable']}")
    print(f"  * Total Kept for Instagram Scraping:    {metrics['kept_total']}")
    print("=" * 70 + "\n")

    return surviving, metrics

