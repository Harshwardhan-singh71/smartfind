"""Tiny check that your Gemini key works. Run: D:\\PYTHON\\python.exe test_gemini.py"""
import os
import sys

MODEL = "gemini-3.8-flash"   # the model name used in Google's current docs


def load_env(path=".env"):
    """Read KEY=value lines from .env (no extra package needed)."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env()
key = os.environ.get("GEMINI_API_KEY", "")
if not key:
    sys.exit("No GEMINI_API_KEY found. Check that the file is named .env and has the line GEMINI_API_KEY=your-key")

try:
    from google import genai
except ImportError:
    sys.exit("The google-genai package is missing. Run: D:\\PYTHON\\python.exe -m pip install google-genai")

try:
    client = genai.Client(api_key=key)
    reply = client.models.generate_content(
        model=MODEL,
        contents="Reply with exactly: SmartFind AI is working",
    )
    print("Gemini says:", reply.text.strip())
except Exception as error:
    print("The call failed:", type(error).__name__)
    print(str(error)[:400])
    print("\nSend me this message (but never the key itself).")
