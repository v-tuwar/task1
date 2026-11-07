import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True)

api_key = os.getenv("GROQ_API_KEY")
if not api_key or api_key == "your_groq_api_key_here":
    print("GROQ_API_KEY not found or placeholder. Set it in your .env file.")
    raise SystemExit(1)

model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
base_url = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
client = OpenAI(api_key=api_key, base_url=base_url, timeout=20)

print("\nChecking Groq API access...\n")
print("Configured model:", model)
print("Base URL:", base_url)
try:
    r = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Reply with only: OK"}],
        max_tokens=10,
    )
    text = (r.choices[0].message.content or "").strip() if r.choices else ""
    print("Success. Model reply:", repr(text))
except Exception as e:
    print("Error:", type(e).__name__, e)
