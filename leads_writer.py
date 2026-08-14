import datetime
import gspread
import config

def get_existing_usernames(sh) -> set[str]:
    """
    Reads the 'Leads' worksheet and returns a set of lowercase existing usernames.
    """
    leads_sheet = sh.worksheet("Leads")
    all_rows = leads_sheet.get_all_values()
    
    existing_usernames = set()
    if not all_rows or len(all_rows) <= 1:
        return existing_usernames

    header = [h.strip().lower() for h in all_rows[0]]
    username_col_idx = 0
    for idx, col_name in enumerate(header):
        if "user" in col_name or "handle" in col_name:
            username_col_idx = idx
            break

    for row in all_rows[1:]:
        if len(row) > username_col_idx and row[username_col_idx].strip():
            existing_usernames.add(row[username_col_idx].strip().lower())

    return existing_usernames


from instagram_scraper import sort_recent_posts_activity

def write_new_leads(sh, profiles: list[dict], niche: str = "", state: str = "") -> tuple[int, int, list[dict]]:
    """
    Deduplicates scraped profiles against existing usernames in the 'Leads' worksheet.
    Appends only new leads into the 'Leads' tab in exact 9-column order:
      1. Profile URL
      2. Username
      3. Full Name
      4. Biography
      5. Followers Count
      6. Recent Posts Activity
      7. Date Added
      8. Niche
      9. State
    """
    leads_sheet = sh.worksheet("Leads")
    existing_usernames = get_existing_usernames(sh)
    
    new_leads_to_write = []
    new_leads_written_info = []
    duplicates_count = 0
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for profile in profiles:
        raw_username = profile.get("username", "").strip()
        if not raw_username:
            continue

        clean_username = raw_username.lower()
        if clean_username in existing_usernames:
            duplicates_count += 1
            print(f"    - [SKIP DUP] Username @{raw_username} is already present in Leads tab.")
        else:
            # Register username to prevent duplicate insertion within the same batch
            existing_usernames.add(clean_username)

            profile_url = profile.get("profile_url") or f"https://www.instagram.com/{raw_username}/"
            name = profile.get("name", "").strip()
            bio = profile.get("bio", "").replace("\n", " ").strip()
            followers = profile.get("followers_count", 0)
            recent_posts_raw = sort_recent_posts_activity(profile.get("recent_posts_activity", ""))
            recent_posts = recent_posts_raw if recent_posts_raw else "No recent posts found"

            row_data = [
                profile_url,
                raw_username,
                name,
                bio,
                followers,
                recent_posts,
                now_str,
                niche,
                state
            ]
            new_leads_to_write.append(row_data)
            new_leads_written_info.append(profile)


    if new_leads_to_write:
        print(f"[+] Appending {len(new_leads_to_write)} new lead row(s) to 'Leads' worksheet...")
        leads_sheet.append_rows(new_leads_to_write)
        print(f"[SUCCESS] Successfully wrote {len(new_leads_to_write)} lead(s) into 'Leads' tab.")
    else:
        print("[NOTE] Zero new leads to write (all profiles were duplicates or empty).")

    return len(new_leads_to_write), duplicates_count, new_leads_written_info

