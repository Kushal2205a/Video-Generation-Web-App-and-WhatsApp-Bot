import re
from typing import Tuple

# Refined banned words list - removed potentially problematic words
BANNED_WORDS = [
    "sex", "porn", "nude", "naked", "erotic", "xxx", "adult", "nsfw",
    "kill", "murder", "stab", "shoot", "attack", "assault", "bomb", "weapon",
    "hate", "racist", "nazi", "fascist", "supremacist", "bigot",
    "drug", "cocaine", "heroin", "meth", "weed", "marijuana",
    "damn", "hell", "crap", "stupid", "idiot", "disgusting", "fuck",
    "scam", "fraud", "gore", "torture", "abuse"
]

# Ensure proper word boundary matching
banned_pattern = re.compile(r'\b(' + '|'.join(re.escape(w) for w in BANNED_WORDS) + r')\b', re.IGNORECASE)

def comprehensive_content_filter(prompt: str) -> Tuple[bool, str]:
    """
    Returns (is_safe, error_message)
    is_safe False => prompt rejected (error_message explains why)
    is_safe True => prompt accepted
    """
    if not isinstance(prompt, str) or not prompt.strip():
        return False, "Prompt is empty. Please write a descriptive prompt."
    
    prompt = prompt.strip()
    
    # Length checks
    if len(prompt) < 5:
        return False, "Prompt too short — please describe your video idea in detail."
    
    if len(prompt) > 1500:
        return False, f"Prompt too long ({len(prompt)} chars). Max 1500."
    
    # Banned words check with proper logging
    match = banned_pattern.search(prompt)
    if match:
        print(f"🚫 Content blocked - found banned word: '{match.group(0)}' in prompt: '{prompt[:50]}...'")
        return False, f"Prompt contains disallowed term: '{match.group(0)}'. Please remove it."
    
    # Repetition check
    words = prompt.split()
    if len(words) > 5:
        ratio = len(set(words)) / len(words)
        if ratio < 0.4:
            return False, "Prompt too repetitive — please make it more descriptive."
    
    # All checks passed
    print(f"✅ Content approved: '{prompt[:50]}...'")
    return True, ""
