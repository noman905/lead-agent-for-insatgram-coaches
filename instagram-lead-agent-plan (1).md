# Instagram Lead Generation Agent — Build Plan

## Goal
Build a Python automation agent that searches Google (via Apify) for Instagram
profiles matching a niche + state, scrapes their profile data (via Apify),
writes new leads into a Google Sheet, skips duplicates, and sends a
completion email when the run finishes.

## Trigger
Run manually from PowerShell, e.g.:
```
python run_agent.py
```

## Inputs (read from Google Sheet "Control" queue tab)
The Control tab holds a queue of search jobs arranged in columns:
1. **Niche** — e.g. `career coach`
2. **State** — e.g. `Connecticut`
3. **Pages** — e.g. `3`
4. **Status** — `Pending`, `Running`, `Done`, or `Failed`

## Audit Log ("Run Log" tab)
Each job execution appends a detail row to the `Run Log` tab:
`Timestamp` | `Niche` | `State` | `Pages Searched` | `Total Profiles Found` | `Leads Added (New)` | `Duplicates Skipped` | `Garbage/Invalid Skipped` | `Status` | `Notes`

## Step-by-Step Flow

### 1. Read Control Queue & Update Job Status
- Connect to Google Sheets API using the service account JSON key.
- Parse all rows in `Control` tab where `Status == "Pending"`.
- Set row status to `Running` before starting, and to `Done` (or `Failed`) upon completion.
- Write full audit details to `Run Log` tab for every processed job.

### 2. Build search query
Construct the query string dynamically:
```
site:instagram.com "{niche}" "{state}"
```
Example: `site:instagram.com "career coach" "Connecticut"`

### 3. Run Apify Google Search Scraper actor
- Call the actor with the query string and the number of pages requested.
- The actor returns Instagram profile URLs directly (no post/reel/hashtag
  junk — confirmed from prior use, so no extra URL filtering step needed).

### 4. Deduplicate against existing sheet data
- Before scraping profiles, read the existing usernames already present in
  the "Leads" tab.
- Filter out any newly found profile URLs whose username already exists in
  the sheet, so Apify credits aren't wasted re-scraping known leads.

### 5. Run Apify Instagram Scraper actor
- Feed the deduplicated list of profile URLs into the actor.
- Extract at minimum:
  - Username
  - Name
  - Bio
- Design the data-extraction step so additional fields (follower count,
  external link/website, post count, private/public status, etc.) can be
  added later with a one-line change — the user will confirm which extra
  fields to include in a future iteration.

> **Note**: Link-in-Bio / Linktree destination extraction has been removed from this pipeline.

### 6. Write results to Google Sheet
- Append one row per new lead into the "Leads" tab.
- Include a timestamp column and the niche/state used for that run, so
  leads are traceable back to the search that found them.

### 7. Send completion email
- Use the existing email-sending method/credentials from the prior pipeline.
- Email subject/body should report:
  - Number of new leads added
  - Number of duplicates skipped
  - Niche + State used for the run

### 8. Error handling
- If the Google Search actor or Instagram Scraper actor fails, times out, or
  returns zero results:
  - Log the error clearly (console + optional log file)
  - Still send a status email so the user isn't left wondering if the run
    silently died (email should say "Run failed" or "Zero results found"
    with the reason if available)

## Notes for future iterations (not needed now)
- Extra Instagram fields (follower count, external link) — to be decided
  and added later
- Possible future enhancement: filter/skip clearly irrelevant profiles
  (e.g. multi-coach agencies, businesses rather than solo coaches) —
  not required in this version

## Tech constraints
- Python 3.10+
- Apify API token (existing account, reused)
- Google Sheets API service account (existing credentials, reused)
- No local ML/heavy compute — all scraping happens via Apify's cloud actors,
  so this is a lightweight, mostly I/O-bound script safe to run on modest
  hardware (confirmed: not CPU-intensive)
