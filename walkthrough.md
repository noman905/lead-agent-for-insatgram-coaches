# Walkthrough: Credit-Limit Failure Handling

The pipeline orchestration has been successfully updated to safely halt the moment you run out of Apify credits, preventing email spam and preserving your un-run queue.

## What Was Changed
- **Bulletproof Error Catching**: Updated the `is_apify_credit_exhausted` function in `run_agent.py` to correctly detect the `"exceeded remaining usage"` string, along with all other Apify billing error variations.
- **Credit Check Before Retry**: Verified that `google_scraper.py` explicitly catches the credit limits and aborts **before** attempting any supplemental retries, saving you from wasting time on dead calls.
- **Accurate Control Tab Updates**: If a row triggers the credit error, that specific row's status is now explicitly set to `Failed (Credit limit exceeded)`. Previously, it was being reset to `Pending`.
- **Queue Preservation & Zero Spam**: The script now immediately `break`s out of the master loop. 
  - All remaining untouched rows naturally stay as `Pending`.
  - It fires **exactly one** alert email (`"Pipeline stopped on [City] due to Apify credits exhausted"`) and entirely skips the generic summary email so you aren't spammed.

> [!TIP]
> **What to do if you hit the limit:**
> If you get the single alert email, you can go into Apify, top up your $5 credits, and simply re-run the script. Because the untouched rows are still `Pending`, it will automatically pick up exactly where it left off!
