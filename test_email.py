import sys
import config
from email_notifier import (
    send_summary_notification,
    send_apify_credits_alert,
    send_completion_notification,
    send_failure_notification,
    send_email
)

def run_isolated_email_test():
    print("=" * 70)
    print(" [TEST] STEP 5: EMAIL NOTIFICATION SYSTEM (ISOLATION TEST)")
    print("=" * 70)

    sender = config.SENDER_EMAIL
    pwd = config.SENDER_PASSWORD
    recipient = config.RECIPIENT_EMAIL or sender

    print(f"[+] Checking Email Settings from .env / config.py:")
    print(f"    - SMTP Server:     {config.SMTP_SERVER}:{config.SMTP_PORT}")
    print(f"    - Sender Email:    {sender if sender else '[NOT SET]'}")
    print(f"    - Sender Password: {'*****' if pwd else '[NOT SET]'}")
    print(f"    - Recipient Email: {recipient if recipient else '[NOT SET]'}")
    print("-" * 70)

    # Sample batch data
    sample_done = [
        {"row_number": 2, "niche": "career coach", "state": "Connecticut", "leads_added": 8, "duplicates_skipped": 2, "total_found": 10},
        {"row_number": 4, "niche": "life coach", "state": "Florida", "leads_added": 12, "duplicates_skipped": 3, "total_found": 15}
    ]
    sample_failed = [
        {"row_number": 3, "niche": "business coach", "state": "Texas", "error": "Google Search actor returned 0 results for this query."}
    ]

    if not sender or sender.strip().lower() in ("", "your_email@gmail.com", "your_gmail_address@gmail.com"):
        print("[NOTE] EMAIL_ADDRESS is currently set to placeholder in .env.")
        print("To test live email delivery, please edit your .env file and set:")
        print("    EMAIL_ADDRESS=your_email@gmail.com")
        print("    EMAIL_APP_PASSWORD=your_16_digit_app_password")
        print("    RECIPIENT_EMAIL=your_recipient_email@gmail.com")
        print("-" * 70)

        print("[DEMO] Generating Summary Email Preview:")
        print("-" * 50)
        # Mock send_email to print template
        old_send_email = getattr(config, "_mock", None)
        send_summary_notification(done_jobs=sample_done, failed_jobs=sample_failed, total_leads_added=20)
        print("-" * 50)
        print("[DEMO] Generating Apify Credits Alert Preview:")
        print("-" * 50)
        send_apify_credits_alert(niche="career coach", state="Connecticut", reason="Monthly usage limit exceeded (402 Payment Required)")
        print("=" * 70)
        print(" [NOTE] Please update .env with your email credentials to test live SMTP sending.")
        print("=" * 70)
        return

    print("[+] Sending Test 1: Consolidated Summary Email Notification...")
    success1 = send_summary_notification(
        done_jobs=sample_done,
        failed_jobs=sample_failed,
        total_leads_added=20
    )

    print("\n[+] Sending Test 2: Urgent Apify Credits Alert Email...")
    success2 = send_apify_credits_alert(
        niche="career coach",
        state="Connecticut",
        reason="Monthly usage limit exceeded (HTTP 402)"
    )

    print("\n" + "=" * 70)
    if success1 and success2:
        print(" [SUCCESS] Both summary and alert test emails were dispatched cleanly! Check your inbox.")
    else:
        print(" [WARNING] One or more emails could not be sent. Check SMTP settings/logs.")
    print("=" * 70)

if __name__ == "__main__":
    run_isolated_email_test()
