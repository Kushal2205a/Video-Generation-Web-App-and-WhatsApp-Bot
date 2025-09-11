import re
from typing import Tuple

BANNED_WORDS = [
    "sex","porn","nude","naked","erotic","xxx","adult","nsfw",
    "kill","murder","stab","shoot","attack","assault","bomb","weapon",
    "hate","racist","nazi","fascist","supremacist","bigot",
    "drug","cocaine","heroin","meth","weed","marijuana",
    "damn","hell","crap","stupid","idiot","moron","disgusting","fuck",
    "scam","fraud","cheat","lie","steal","gore","torture","abuse"
]

banned_pattern = re.compile(r'\b(' + '|'.join(re.escape(w) for w in BANNED_WORDS) + r')\b', re.IGNORECASE)

def comprehensive_content_filter(prompt: str) -> Tuple[bool, str]:
    """
    Returns (is_invalid, message)
    is_invalid True => prompt rejected (message explains why)
    is_invalid False => prompt accepted (message may contain suggestions or be empty)
    """
    if not isinstance(prompt, str) or not prompt.strip():
        return True, "Prompt is empty. Please write a descriptive prompt."

    prompt = prompt.strip()

    # length checks
    if len(prompt) < 5:
        return True, "Prompt too short — please describe your video idea in detail."
    if len(prompt) > 1500:
        return True, f"Prompt too long ({len(prompt)} chars). Max 1500."

    # banned words
    m = banned_pattern.search(prompt)
    if m:
        return True, f"Prompt contains disallowed term: '{m.group(0)}'. Please remove it."

    # basic repetition/spam checks
    words = prompt.split()
    if len(words) > 5:
        ratio = len(set(words)) / len(words)
        if ratio < 0.4:
            return True, "Prompt too repetitive — please make it more descriptive."

    # pass
    return False, ""
