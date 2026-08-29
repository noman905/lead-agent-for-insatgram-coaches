# Instagram Lead Generation Agent

Automated Instagram lead discovery and scraping pipeline powered by Google Search, Google Sheets, Apify, and a 2-Tier AI Gender Pre-Filter.

---

## Architecture & Pipeline Flow

```
[Google Sheet Control Queue]
            │
            ▼
 Phase 1: Google Search Scraper (apify/google-search-scraper)
          - Discovers candidate Instagram profiles via targeted search queries
          - Extracts snippet metadata: URL, Title (name/handle), and Description (bio)
            │
            ▼
 ★ NEW PHASE: Smart 2-Tier Gender Pre-Filter ★
          - Runs on Google snippet data BEFORE any Instagram scraping
          - Tier 1: Local Heuristic Analysis (pronouns, targeting phrases, self-descriptions, name+handle)
          - Tier 2: Free AI Fallback (Groq llama-3.1-8b-instant -> Gemini 2.0 Flash -> Safe Keep)
          - 100% Rule: ONLY drops profiles with zero doubt. Keeps all ambiguous/male profiles.
            │
            ▼
 Phase 2: Apify Instagram Scraper (apify/instagram-scraper)
          - Scrapes ONLY surviving profiles (saves 100% of Apify scraping credits on women)
            │
            ▼
 Phase 3: Leads Storage & Email Summary
          - Writes new leads to Google Sheets ('Leads' tab)
          - Appends audit logs to 'Run Log' tab
          - Dispatches consolidated email summaries
```

---

## Required GitHub Repository Secrets

Go to **GitHub Repo Settings $\rightarrow$ Secrets and variables $\rightarrow$ Actions** and add the following repository secrets:

| Secret Name | Description | Where to get it |
| :--- | :--- | :--- |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Full JSON content of your Google Cloud Service Account key | Google Cloud Console |
| `GOOGLE_SHEET_ID` | Your Google Spreadsheet ID | Google Sheets URL |
| `APIFY_API_TOKEN` | Apify API token | [console.apify.com/account/integrations](https://console.apify.com/account/integrations) |
| `GROQ_API_KEY` | Free Groq API Key (14,400 req/day) | [console.groq.com/keys](https://console.groq.com/keys) |
| `GEMINI_API_KEY` | Free Google Gemini API Key (1,500 req/day) | [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) |
| `EMAIL_ADDRESS` | Sender Gmail address | Your Gmail account |
| `EMAIL_APP_PASSWORD` | 16-character Gmail App Password | Google Account $\rightarrow$ Security $\rightarrow$ App Passwords |
| `RECIPIENT_EMAIL` | Destination email for summaries & alerts | Your receiving email |

---

## How to Get Free AI API Keys (Under 2 Minutes)

### 1. Groq API Key (Priority 1 — 14,400 Free Requests/Day)
1. Visit: [https://console.groq.com/keys](https://console.groq.com/keys)
2. Sign in with Google or GitHub.
3. Click **"Create API Key"**.
4. Name your key (e.g. `instagram-filter`) and click **Submit**.
5. Copy the generated key (`gsk_...`) into your `.env` and GitHub Secrets as `GROQ_API_KEY`.

### 2. Google Gemini API Key (Priority 2 — 1,500 Free Requests/Day)
1. Visit: [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
2. Sign in with your Google account.
3. Click **"Create API key"** $\rightarrow$ select an existing project or create a new one.
4. Copy the generated key (`AIza...`) into your `.env` and GitHub Secrets as `GEMINI_API_KEY`.

---

## Local Setup & Testing

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Copy environment file:
   ```bash
   cp .env.example .env
   ```
3. Run the Gender Pre-Filter test suite:
   ```bash
   python test_gender_filter.py
   ```
4. Run the full agent:
   ```bash
   python run_agent.py
   ```
