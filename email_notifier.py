import smtplib
import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import config

def send_email(subject: str, body_text: str, recipient: str = None) -> bool:
    """
    Sends an email using SMTP configured in config.py / .env.
    """
    smtp_server = config.SMTP_SERVER
    smtp_port = config.SMTP_PORT
    sender_email = config.SENDER_EMAIL
    sender_password = config.SENDER_PASSWORD
    target_email = recipient or config.RECIPIENT_EMAIL or sender_email

    if not sender_email or sender_email.strip() in ("", "your_email@gmail.com"):
        print("[WARNING] SENDER_EMAIL is not configured in .env. Skipping email dispatch.")
        return False

    if not sender_password or sender_password.strip() in ("", "your_email_app_password"):
        print("[WARNING] SENDER_PASSWORD is not configured in .env. Skipping email dispatch.")
        return False

    if not target_email or target_email.strip() in ("", "your_recipient_email@gmail.com"):
        target_email = sender_email

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender_email
        msg["To"] = target_email

        # Attach plain text version
        msg.attach(MIMEText(body_text, "plain"))

        print(f"[+] Connecting to SMTP server '{smtp_server}:{smtp_port}'...")
        with smtplib.SMTP(smtp_server, smtp_port, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, [target_email], msg.as_string())

        print(f"[SUCCESS] Email successfully sent to '{target_email}'. Subject: '{subject}'")
        return True

    except Exception as e:
        print(f"[ERROR] Failed to send email via SMTP: {e}")
        return False


def send_completion_notification(niche: str, state: str, leads_added: int, duplicates_skipped: int, total_found: int, notes: str = "") -> bool:
    """
    Sends a run completion summary email.
    """
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    subject = f"[SUCCESS] Instagram Lead Run Finished - {niche} / {state}"


    body = f"""
Hello,

The Instagram Lead Generation Agent has completed a search run!

==================================================
RUN SUMMARY
==================================================
- Timestamp:          {timestamp}
- Target Niche:       {niche}
- Target State:       {state}
- Total Profiles:     {total_found}
- New Leads Added:    {leads_added}
- Duplicates Skipped: {duplicates_skipped}
==================================================
Notes: {notes if notes else 'Run completed smoothly.'}

All new leads have been saved to your Google Sheet ('Leads' tab).

Best regards,
Instagram Lead Generation Agent
"""
    return send_email(subject, body)


def send_failure_notification(niche: str, state: str, reason: str) -> bool:
    """
    Sends an error / failure notification email.
    """
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    subject = f"[ALERT] Instagram Lead Run Failed - {niche} / {state}"


    body = f"""
Hello,

The Instagram Lead Generation Agent encountered an issue during processing.

==================================================
FAILURE REPORT
==================================================
- Timestamp:    {timestamp}
- Target Niche: {niche}
- Target State: {state}
- Issue/Reason: {reason}
==================================================

Please review your script logs or Google Sheet queue.

Best regards,
Instagram Lead Generation Agent
"""
    return send_email(subject, body)
