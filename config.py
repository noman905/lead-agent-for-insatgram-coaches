import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Centralized configuration settings
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "credentials.json")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN", "")

# SMTP Email Configuration
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SENDER_EMAIL = os.getenv("EMAIL_ADDRESS") or os.getenv("SENDER_EMAIL", "")
SENDER_PASSWORD = os.getenv("EMAIL_APP_PASSWORD") or os.getenv("SENDER_PASSWORD", "")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL") or SENDER_EMAIL



