import sys
import config
from email_notifier import send_completion_notification, send_failure_notification, send_email

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

    if not sender or sender.strip().lower() in ("", "your_email@gmail.com", "your_gmail_address@gmail.com"):
        print("[NOTE] EMAIL_ADDRESS is currently set to placeholder in .env.")
        print("To test live email delivery, please edit your .env file and set:")
        print("    EMAIL_ADDRESS=your_email@gmail.com")
        print("    EMAIL_APP_PASSWORD=your_16_digit_app_password")
        print("    RECIPIENT_EMAIL=your_recipient_email@gmail.com")
        print("-" * 70)

        print("[DEMO] Generating email template previews for verification...")
        
        demo_subject = "[TEST] Demo Run Finished - career coach / Connecticut"

        demo_body = (
            "Hello,\n\n"
            "This is a preview of the email notification system:\n"
            "- Niche: career coach\n"
            "- State: Connecticut\n"
            "- Leads Added: 8\n"
            "- Duplicates Skipped: 2\n"
        )
        print(f"\n[SUBJECT PREVIEW]:\n{demo_subject}")
        print(f"\n[BODY PREVIEW]:\n{demo_body}")
        print("=" * 70)
        print(" [NOTE] Please update .env with your email credentials to test live SMTP sending.")
        print("=" * 70)
        return

    print("[+] Sending Test 1: Completion Email Notification...")
    success1 = send_completion_notification(
        niche="career coach",
        state="Connecticut",
        leads_added=8,
        duplicates_skipped=2,
        total_found=10,
        notes="Isolation test email dispatch successful"
    )

    print("\n[+] Sending Test 2: Failure Alert Email Notification...")
    success2 = send_failure_notification(
        niche="career coach",
        state="Connecticut",
        reason="Zero results found during search test"
    )

    print("\n" + "=" * 70)
    if success1 and success2:
        print(" [SUCCESS] Both test emails were dispatched cleanly! Check your inbox.")
    else:
        print(" [WARNING] One or more emails could not be sent. Check SMTP settings/logs.")
    print("=" * 70)

if __name__ == "__main__":
    run_isolated_email_test()
