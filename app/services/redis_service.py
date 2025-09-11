from main import VIDEO_GENERATION_STATUS
import redis
import os
import json
from datetime import datetime
from typing import Optional
import json
from datetime import datetime
from app.config import redis_client


def store_user_state(user_phone: str, state: str, data: dict):
    """Store user conversation state"""
    if not redis_client:
        return 
    state_key = f"user_state:{user_phone}"
    state_data = {
        "state": state,
        "data": data,
        "timestamp": datetime.now().isoformat()
    }
    redis_client.set(state_key, json.dumps(state_data), ex=300)  # 5 minutes expiry

def get_user_state(user_phone: str) -> dict:
    """Get user conversation state"""
    state_key = f"user_state:{user_phone}"
    state_data = redis_client.get(state_key)
    return json.loads(state_data) if state_data else None

def clear_user_state(user_phone: str):
    """Clear user conversation state"""
    redis_client.delete(f"user_state:{user_phone}")

def store_conversation_context(user_phone: str, message_type: str, content: dict):
    """Enhanced conversation storage with context"""
    if not redis_client:
        return
    
    context_key = f"context:{user_phone}"
    
    # Create context entry
    context_entry = {
        "type": message_type,  # 'user_message', 'video_request', 'video_completed', 'command'
        "content": content,
        "timestamp": datetime.now().isoformat()
    }
    
    # Get existing context
    existing_context = redis_client.get(context_key)
    if existing_context:
        context = json.loads(existing_context)
    else:
        context = {"history": [], "preferences": {}, "stats": {}}
    
    # Add new entry
    context["history"].append(context_entry)
    
    # Keep only last 50 entries to prevent bloat
    if len(context["history"]) > 50:
        context["history"] = context["history"][-50:]
    
    # Update user stats
    if message_type == "video_completed":
        context["stats"]["total_videos"] = context["stats"].get("total_videos", 0) + 1
        context["stats"]["last_video_date"] = datetime.now().isoformat()
    
    # Store back with 7-day expiry
    redis_client.set(context_key, json.dumps(context), ex=604800)

def get_conversation_context(user_phone: str) -> dict:
    """Get full conversation context for user"""
    if not redis_client:
        return {"history": [], "preferences": {}, "stats": {}}
    
    context_key = f"context:{user_phone}"
    context_data = redis_client.get(context_key)
    
    if context_data:
        return json.loads(context_data)
    return {"history": [], "preferences": {}, "stats": {}}

def analyze_user_preferences(user_phone: str) -> dict:
    """Analyze user's video generation patterns"""
    context = get_conversation_context(user_phone)
    
    # Analyze video requests
    video_requests = [entry for entry in context["history"] if entry["type"] == "video_request"]
    
    preferences = {
        "favorite_themes": [],
        "common_keywords": [],
        "preferred_time": None,
        "total_requests": len(video_requests)
    }
    
    if video_requests:
        # Extract common themes
        all_prompts = " ".join([req["content"].get("prompt", "") for req in video_requests])
        
        # Simple keyword analysis
        words = all_prompts.lower().split()
        word_freq = {}
        for word in words:
            if len(word) > 3:  # Skip short words
                word_freq[word] = word_freq.get(word, 0) + 1
        
        # Get top keywords
        preferences["common_keywords"] = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Analyze themes
        themes = ["dance", "animal", "nature", "space", "city", "music", "food", "travel"]
        for theme in themes:
            if theme in all_prompts.lower():
                preferences["favorite_themes"].append(theme)
    
    return preferences

def generate_contextual_response(user_phone: str, current_message: str) -> str:
    """Generate responses based on conversation history"""
    context = get_conversation_context(user_phone)
    preferences = analyze_user_preferences(user_phone)
    
    # Check if user is repeating similar requests
    recent_requests = [entry for entry in context["history"][-5:] if entry["type"] == "video_request"]
    
    if recent_requests:
        last_prompt = recent_requests[-1]["content"].get("prompt", "").lower()
        if last_prompt and last_prompt in current_message.lower():
            return """🔄 *I notice you're requesting something similar to before!* """
    
    return None  # Return None if no contextual response needed

def get_smart_suggestions(user_phone: str) -> str:
    """Get personalized suggestions based on history"""
    context = get_conversation_context(user_phone)
    stats = context.get("stats", {})
    
    suggestions = []
    
    if stats.get("total_videos", 0) == 0:
        suggestions = [
            "🌟 *First time?* Try: 'A golden retriever playing in a park'",
            "🎭 *Creative?* Try: 'A dancer silhouette against sunset'", 
            "🌸 *Nature lover?* Try: 'Cherry blossoms falling in slow motion'"
        ]
    else:
        preferences = analyze_user_preferences(user_phone)
        if preferences["favorite_themes"]:
            theme = preferences["favorite_themes"][0]
            suggestions = [
                f"🎬 *More {theme}:* Try adding 'cinematic lighting' to your {theme} prompts",
                f"✨ *Variation:* Combine {theme} with 'golden hour lighting'",
                f"🎨 *Creative twist:* Try '{theme} in an artistic style'"
            ]
    
    return "\n".join(suggestions)

def is_user_rate_limited(user_phone: str) -> bool:
    """Checks if user has exceeded message rate limit"""
    if not redis_client:
        return False  # No rate limiting if Redis unavailable
    key = f"rate_limit:{user_phone}"
    current_count = redis_client.get(key)
    
    if current_count and int(current_count) >= 10:  # 10 messages per hour
        return True
    
    # Increment counter for this user
    redis_client.incr(key)
    redis_client.expire(key, 3)  # Reset after 1 hour (3600 seconds)
    return False

def get_rate_limit_message(user_phone: str) -> str:
    """Get friendly rate limit message with remaining time"""
    key = f"rate_limit:{user_phone}"
    ttl = redis_client.ttl(key)  # Time to live in seconds
    
    if ttl > 0:
        minutes = ttl // 60
        return f""" *Whoa there,* 

You've hit the rate limit of *10 messages per hour*.

*Try again in:* {minutes} minutes
*Why limits?* Keeps the bot fast for everyone

Thanks for understanding"""
    else:
        return " *Rate limit active.* Please wait a moment before sending more messages."

def store_job_data(job_id: str, data: dict, user_phone: str = None):
    """Store job data in Redis or fallback to memory with user association"""
    if redis_client:
        try:
            # Store job data 
            redis_client.setex(f"job:{job_id}", 3600, json.dumps(data))
            
        
            if user_phone:
            
                clean_phone = user_phone.replace("whatsapp:", "").replace("+", "").replace("-", "").replace(" ", "")
                # Store user-job association with same expiry
                redis_client.setex(f"user_job:{clean_phone}:{job_id}", 3600, json.dumps(data))
            
            return
        except Exception as e:
            print(f"Redis store failed: {e}")
    
    # Fallback to memory (if redis not working)
    VIDEO_GENERATION_STATUS[job_id] = data


def get_job_data(job_id: str) -> Optional[dict]:
    """Get job data from Redis or fallback to memory"""
    if redis_client:
        try:
            data = redis_client.get(f"job:{job_id}")
            if data:
                return json.loads(data)
        except Exception as e:
            print(f"Redis get failed: {e}")
    
    # Fallback to memory
    return VIDEO_GENERATION_STATUS.get(job_id)

def update_job_data(job_id: str, updates: dict):
    """Update job data"""
    current_data = get_job_data(job_id)
    if current_data:
        current_data.update(updates)
        user_phone=current_data.get("user_phone")
        store_job_data(job_id, current_data,user_phone)
