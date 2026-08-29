import os
import sys
from dotenv import load_dotenv

# Load .env file
load_dotenv()

def test_gemini():
    print("=" * 70)
    print(" [TEST] GOOGLE GEMINI NATIVE API CONNECTION TEST")
    print("=" * 70)

    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()

    if not gemini_key or gemini_key in ("your_gemini_api_key_here", ""):
        print("[WARNING] GEMINI_API_KEY is not set in your .env file.")
        print("Please edit .env and set: GEMINI_API_KEY=AQ.Ab...")
        print("You can run this test again after adding your key.")
        return False

    # Mask key for secure logging
    masked = gemini_key[:7] + "..." + gemini_key[-4:] if len(gemini_key) > 12 else "***"
    print(f"[+] Found GEMINI_API_KEY: {masked} (Length: {len(gemini_key)} chars)")
    print(f"[+] Key Prefix: '{gemini_key[:5]}' (Supports both AQ. and legacy AIza formats)")

    try:
        from google import genai
        print("[+] Initializing native google-genai Client...")
        client = genai.Client(api_key=gemini_key)

        model_name = "gemini-2.0-flash"
        test_prompt = (
            "You are analyzing an Instagram profile to determine if the account owner is definitely a woman. "
            "You must be 100% absolutely certain before answering YES. If there is even the slightest doubt answer NO.\n\n"
            "Full Name: Sarah Jenkins\n"
            "Username: sarahjenkins_coaching\n"
            "Bio: Executive Coach for high-performing female leaders.\n\n"
            "Is this person definitely a woman? Answer only YES or NO."
        )

        print(f"[+] Sending test request to native endpoint with model '{model_name}'...")
        response = client.models.generate_content(
            model=model_name,
            contents=test_prompt
        )

        answer = (response.text or "").strip()
        print(f"[+] Response received from Gemini: '{answer}'")
        print("=" * 70)
        print(" [SUCCESS] Native Gemini API connection is working 100%!")
        print("=" * 70)
        return True

    except Exception as err:
        print(f"\n[ERROR] Gemini API call failed: {err}")
        print("=" * 70)
        return False

if __name__ == "__main__":
    test_gemini()
