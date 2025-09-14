# app/services/redis_service.py
import json
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from app.config import redis_client

# In-memory fallback
VIDEO_GENERATION_STATUS: Dict[str, Dict[str, Any]] = {}
USER_STATE: Dict[str, Dict[str, Any]] = {}
CONVERSATION_CONTEXT: Dict[str, Any] = {}
RATE_LIMITS: Dict[str, float] = {}

JOB_TTL_SECONDS = 60 * 60 * 24  # 24 hours fallback


# Job storage 
def store_job_data(job_id: str, data: dict, user_phone: Optional[str] = None) -> None:
    """Store job data in Redis or in-memory fallback."""
    payload = json.dumps(data)
    if redis_client:
        try:
            redis_client.setex(f"job:{job_id}", JOB_TTL_SECONDS, payload)
            if user_phone:
                clean_phone = user_phone.replace("whatsapp:", "").replace("+", "").replace("-", "").replace(" ", "")
                redis_client.setex(f"user_job:{clean_phone}:{job_id}", JOB_TTL_SECONDS, payload)
            return
        except Exception as e:
            print(f"Redis store failed: {e} — falling back to memory")

    VIDEO_GENERATION_STATUS[job_id] = data
    if user_phone:
        clean_phone = user_phone.replace("whatsapp:", "").replace("+", "").replace("-", "").replace(" ", "")
        USER_STATE.setdefault(clean_phone, {})
        USER_STATE[clean_phone].setdefault("jobs", []).append(job_id)

def get_job_data(job_id: str) -> Optional[dict]:
    """Retrieve job data from Redis or fallback."""
    if redis_client:
        try:
            raw = redis_client.get(f"job:{job_id}")
            if raw:
                return json.loads(raw)
        except Exception as e:
            print(f"Redis get failed: {e} — falling back to memory")
    return VIDEO_GENERATION_STATUS.get(job_id)

def update_job_data(job_id: str, update: dict) -> None:
    """Merge update into existing job data and persist."""
    current = get_job_data(job_id) or {}
    current.update(update)
    store_job_data(job_id, current)

# User state helpers
def store_user_state(user_phone: str, state: dict) -> None:
    clean_phone = user_phone.replace("whatsapp:", "").replace("+", "").replace("-", "").replace(" ", "")
    if redis_client:
        try:
            redis_client.setex(f"user_state:{clean_phone}", JOB_TTL_SECONDS, json.dumps(state))
            return
        except Exception as e:
            print(f"Redis store user state failed: {e} — using memory fallback")
    USER_STATE[clean_phone] = state

def get_user_state(user_phone: str) -> Optional[dict]:
    clean_phone = user_phone.replace("whatsapp:", "").replace("+", "").replace("-", "").replace(" ", "")
    if redis_client:
        try:
            raw = redis_client.get(f"user_state:{clean_phone}")
            if raw:
                return json.loads(raw)
        except Exception as e:
            print(f"Redis get user state failed: {e} — using memory fallback")
    return USER_STATE.get(clean_phone)

def clear_user_state(user_phone: str) -> None:
    clean_phone = user_phone.replace("whatsapp:", "").replace("+", "").replace("-", "").replace(" ", "")
    if redis_client:
        try:
            redis_client.delete(f"user_state:{clean_phone}")
        except Exception as e:
            print(f"Redis delete user state failed: {e}")
    USER_STATE.pop(clean_phone, None)


# Conversation context
def store_conversation_context(user_phone: str, key: str, value: dict) -> None:
    clean_phone = user_phone.replace("whatsapp:", "").replace("+", "").replace("-", "").replace(" ", "")
    if redis_client:
        try:
            redis_client.hset(f"context:{clean_phone}", key, json.dumps(value))
            return
        except Exception as e:
            print(f"Redis hset context failed: {e} — using memory fallback")
    CONVERSATION_CONTEXT.setdefault(clean_phone, {})[key] = value

def get_conversation_context(user_phone: str, key: Optional[str] = None):
    clean_phone = user_phone.replace("whatsapp:", "").replace("+", "").replace("-", "").replace(" ", "")
    if redis_client:
        try:
            if key:
                raw = redis_client.hget(f"context:{clean_phone}", key)
                return json.loads(raw) if raw else None
            else:
                raw = redis_client.hgetall(f"context:{clean_phone}")
                return {k: json.loads(v) for k, v in raw.items()} if raw else {}
        except Exception as e:
            print(f"Redis get context failed: {e} — using memory fallback")
    if key:
        return CONVERSATION_CONTEXT.get(clean_phone, {}).get(key)
    return CONVERSATION_CONTEXT.get(clean_phone, {})


# Rate limiting 
def is_user_rate_limited(user_phone: str, window_seconds: int = 60, max_calls: int = 6) -> bool:
    clean_phone = user_phone.replace("whatsapp:", "").replace("+", "").replace("-", "").replace(" ", "")
    now_ts = time.time()
    if redis_client:
        try:
            key = f"rate:{clean_phone}"
            redis_client.lpush(key, now_ts)
            length = redis_client.llen(key)
            if length > max_calls:
                redis_client.lpop(key)
                redis_client.expire(key, window_seconds)
                return True
            redis_client.ltrim(key, 0, max_calls - 1)
            redis_client.expire(key, window_seconds)
            return False 
        except Exception as e:
            print(f"Redis rate limit failed: {e} — falling back to memory")
    # memory fallback
    timestamps = RATE_LIMITS.get(clean_phone, [])
    timestamps = [t for t in timestamps if now_ts - t < window_seconds]
    timestamps.append(now_ts)
    RATE_LIMITS[clean_phone] = timestamps
    return len(timestamps) > max_calls

def get_rate_limit_message(user_phone: str) -> str:
    return "You're sending requests too quickly. Please wait a moment."

def analyze_user_preferences(user_phone: str) -> dict:
    """
    returns a summary of recent prompts and counts.
    """
    clean_phone = user_phone.replace("whatsapp:", "").replace("+", "").replace("-", "").replace(" ", "")
    # try Redis list, fallback to memory USER_STATE
    prompts = []
    if redis_client:
        try:
            keys = redis_client.keys(f"user_job:{clean_phone}:*")
            for k in sorted(keys, reverse=True)[:10]:
                raw = redis_client.get(k)
                if raw:
                    job = json.loads(raw)
                    p = job.get("prompt")
                    if p:
                        prompts.append(p)
        except Exception:
            pass
    else:
        state = USER_STATE.get(clean_phone, {})
        for jid in state.get("jobs", [])[-10:]:
            job = VIDEO_GENERATION_STATUS.get(jid)
            if job:
                p = job.get("prompt")
                if p:
                    prompts.append(p)

    return {
        "recent_prompts": prompts,
        "prompt_count": len(prompts)
    }

def get_smart_suggestions(user_phone: str, n: int = 3) -> list:
    """
    Return n simple prompt-suggestions based on recent prompts.
    This is intentionally naive: it appends style tweaks to recent prompts.
    """
    prefs = analyze_user_preferences(user_phone)
    base = prefs.get("recent_prompts", [])
    suggestions = []
    for p in base[:n]:
        suggestions.append(f"{p} — cinematic lighting, smooth motion")
        
    generic = [
        "A golden retriever playing in a park, cinematic lighting",
        "Astronaut floating in space, stars in the background, slow motion",
        "Ocean waves at sunset with seagulls flying"
    ]
    gen_index = 0 
    while len(suggestions) < n:
        suggestions.append(generic[gen_index % len(generic)])
        gen_index += 1
    return suggestions

def generate_contextual_response(user_phone: str, prompt: str = None) -> str:
    """Only provide contextual responses for appropriate scenarios"""

    
    if prompt is None or prompt.startswith('/'):
        return None

    
    prefs = analyze_user_preferences(user_phone)
    if prefs.get("prompt_count", 0) == 0:
        return None  
    
    context = get_conversation_context(user_phone) or {}
    suggestions = get_smart_suggestions(user_phone, n=2)
    
    lines = []
    lines.append(f"Got your prompt: \"{prompt}\".")
    
    if prefs.get("prompt_count", 0) > 0:
        lines.append(f"You've made {prefs['prompt_count']} recent prompts. Here are suggestions:")
        lines += [f"- {s}" for s in suggestions]
    
    return "\n".join(lines) if lines else None

__all__ = [
    "VIDEO_GENERATION_STATUS",
    "store_job_data",
    "get_job_data",
    "update_job_data",
    "store_user_state",
    "get_user_state",
    "clear_user_state",
    "store_conversation_context",
    "get_conversation_context",
    "is_user_rate_limited",
    "get_rate_limit_message",
]
