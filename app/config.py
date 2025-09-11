# app/config.py
import os
from dotenv import load_dotenv

load_dotenv()

# ---------- Redis ----------
redis_client = None
try:
    import redis
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    # attempt a ping (may raise if unreachable)
    try:
        redis_client.ping()
        print("✅ Redis connected")
    except Exception as e:
        print(f"⚠️ Redis ping failed: {e} — continuing with redis_client=None")
        redis_client = None
except Exception as e:
    print(f"⚠️ redis library not available or failed to init: {e} — continuing with redis_client=None")
    redis_client = None

# ---------- Twilio ----------
twilio_client = None
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")

try:
    if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
        from twilio.rest import Client
        twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        print("✅ Twilio client initialized")
    else:
        print("⚠️ Twilio credentials not set (TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN). twilio_client=None")
except Exception as e:
    print(f"⚠️ Failed to initialize Twilio client: {e}")
    twilio_client = None

# ---------- Other config values (optional) ----------
VIDU_API_KEY = os.getenv("VIDU_API_KEY")
VIDU_BASE_URL = os.getenv("VIDU_BASE_URL", "https://api.vidu.com")
HUGGINGFACE_TOKEN = os.getenv("HUGGINGFACE_TOKEN")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")

# Export __all__ (optional, helps clarity)
__all__ = [
    "redis_client",
    "twilio_client",
    "TWILIO_WHATSAPP_FROM",
    "VIDU_API_KEY",
    "VIDU_BASE_URL",
    "HUGGINGFACE_TOKEN",
    "PUBLIC_BASE_URL",
]
