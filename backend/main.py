import shutil
import os
import asyncio
import uuid
import json
import redis
from fastapi import FastAPI, HTTPException, Form, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import uvicorn
from huggingface_hub import login
from pathlib import Path
from typing import Dict, Optional
import requests
from twilio.rest import Client
from datetime import datetime
import re 

load_dotenv()

app = FastAPI(title="AI Video Generator API")


def enhance_prompt_free(prompt: str) -> str:
    """Free rule-based prompt enhancement"""
    enhancements = {
        'dance': 'dynamic movement, rhythmic motion, vibrant colors',
        'animal': 'lifelike movement, natural behavior, detailed features',
        'nature': 'natural lighting, serene atmosphere, high detail',
        'space': 'cosmic background, stellar lighting, weightless motion',
        'city': 'urban environment, architectural details, atmospheric'
    }
    
    enhanced_prompt = prompt
    for keyword, enhancement in enhancements.items():
        if keyword in prompt.lower():
            enhanced_prompt = f"{prompt}, {enhancement}, cinematic lighting, smooth motion"
            break
    
    if enhanced_prompt == prompt:  # No specific enhancement
        enhanced_prompt = f"{prompt}, cinematic lighting, 4K quality, smooth motion"
    
    return enhanced_prompt

def store_user_state(user_phone: str, state: str, data: dict):
    """Store user conversation state"""
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



# Comprehensive banned words database
BANNED_WORDS = [
    # Explicit content
    "sex", "porn", "nude", "naked", "erotic", "xxx", "adult", "nsfw",
    
    # Violence & threats  
    "kill", "murder", "stab", "shoot", "attack", "assault", "bomb", "weapon", 
    "gun", "knife", "terror", "threat", "hurt", "harm", "destroy",
    
    # Hate speech
    "hate", "racist", "nazi", "fascist", "supremacist", "bigot", "nigga","nigger","pajeet",
    
    # Drugs & illegal
    "drug", "cocaine", "heroin", "meth", "weed", "marijuana", "illegal",
    
    # Profanity (extend as needed)
    "damn", "hell", "crap", "stupid", "idiot", "moron", "disgusting","fuck",
    
    # Add more categories as needed
    "scam", "fraud", "cheat", "lie", "steal"
]

# Create regex pattern for banned words
banned_pattern = re.compile(r'\b(' + '|'.join(re.escape(word) for word in BANNED_WORDS) + r')\b', re.IGNORECASE)

def comprehensive_content_filter(prompt: str) -> tuple[bool, str]:
    # Length validation (Vidu API limit)
    if len(prompt.strip()) < 5:
        return False, "🤔 **Prompt too short!** Please describe your video idea in detail."
    
    if len(prompt) > 1500:
        return False, f"📝 **Prompt too long!** Vidu accepts max 1500 characters.\n**Current:** {len(prompt)} characters"
    
    # Banned words check
    if banned_pattern.search(prompt):
        return False, "🚫 **Content policy violation.** Please use family-friendly, appropriate language for your video prompt."
    
    # Leetspeak detection
    leetspeak_patterns = [
        r'[s5][e3][x]+',      # s3x, 5ex, etc.
        r'n[u4@][d0o]e?',     # n4de, nu0e, etc.
        r'k[i1]ll',           # k1ll, ki11, etc.
        r'h[a@]te',           # h@te, hate, etc.
    ]
    
    for pattern in leetspeak_patterns:
        if re.search(pattern, prompt, re.IGNORECASE):
            return False, "🚫 **Inappropriate content detected.** Please rephrase your prompt using appropriate language."
    
    # Repetition/spam check
    words = prompt.lower().split()
    if len(words) > 5:
        unique_ratio = len(set(words)) / len(words)
        if unique_ratio < 0.4:
            return False, "🔄 **Too repetitive.** Please make your prompt more varied and descriptive!"
    
    # Character repetition check
    if re.search(r'(.)\1{4,}', prompt):
        return False, "🔤 **Invalid format.** Please avoid excessive character repetition!"
    
    # All checks passed
    return True, ""

    
def is_user_rate_limited(user_phone: str) -> bool:
    """Checks if user has exceeded message rate limit"""
    key = f"rate_limit:{user_phone}"
    current_count = redis_client.get(key)
    
    if current_count and int(current_count) >= 10:  # 10 messages per hour
        return True
    
    # Increment counter for this user
    redis_client.incr(key)
    redis_client.expire(key, 3600)  # Reset after 1 hour (3600 seconds)
    return False

def get_rate_limit_message(user_phone: str) -> str:
    """Get friendly rate limit message with remaining time"""
    key = f"rate_limit:{user_phone}"
    ttl = redis_client.ttl(key)  # Time to live in seconds
    
    if ttl > 0:
        minutes = ttl // 60
        return f"""⏳ **Whoa there, speedy!** 

You've hit the rate limit of **10 messages per hour**.

**Try again in:** {minutes} minutes
**Why limits?** Keeps the bot fast for everyone!

Thanks for understanding! 😊"""
    else:
        return "⏳ **Rate limit active.** Please wait a moment before sending more messages."

    
    
# Redis connection
try:
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    redis_client = redis.from_url(redis_url, decode_responses=True)
    redis_client.ping()
    print("Redis connected successfully")
except Exception as e:
    print(f"Redis connection failed: {e}")
    redis_client = None
# Twilio client
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN") 
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")

try:
    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    print("✅ Twilio client initialized")
except Exception as e:
    print(f"❌ Twilio initialization failed: {e}")
    twilio_client = None

# Global job tracking (fallback if Redis unavailable)
VIDEO_GENERATION_STATUS: Dict[str, dict] = {}

# Existing models
class Video_Request(BaseModel):
    prompt: str

class Video_Job_Created_Response(BaseModel):
    job_id: str
    status: str
    message: str

class Status_Response(BaseModel):
    job_id: str
    status: str
    message: str
    video_url: Optional[str] = None

# ========== EXISTING WEB APP ROUTES (UNCHANGED) ==========
@app.get("/", response_class=HTMLResponse)
async def serve_html():
    """Serves the HTML page"""
    try:
        with open("../frontend/index.html", "r") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse("<h1>AI Video Generator</h1><p>Frontend not available</p>")

@app.get("/style.css")
async def serve_css():
    """Serves the CSS file"""
    return FileResponse("../frontend/style.css", media_type="text/css")

@app.get("/script.js")
async def serve_js():
    """Serves the Javascript file"""
    return FileResponse("../frontend/script.js", media_type="text/javascript")

@app.post("/api/generate-video", response_model=Video_Job_Created_Response)
async def generate_video(request: Video_Request):
    """Start the Video Generation Process (for web app)."""
    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt is required")

    job_id = str(uuid.uuid4())
    
    # Store in Redis if available, otherwise use memory
    job_data = {
        "status": "processing",
        "message": "Video generation has started",
        "video_url": None,
        "prompt": request.prompt
    }
    
    store_job_data(job_id, job_data)
    
    asyncio.create_task(video_generation_process(job_id, request.prompt))

    return Video_Job_Created_Response(
        job_id=job_id,
        status="processing",
        message="Video generation has started"
    )

@app.get("/api/status/{job_id}", response_model=Status_Response)
async def get_status(job_id: str):
    """Get the status of Video generation"""
    job_data = get_job_data(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Job ID not found")

    return Status_Response(
        job_id=job_id,
        status=job_data["status"],
        message=job_data["message"],
        video_url=job_data.get("video_url")
    )

@app.get("/api/download/{job_id}")
async def download_video(job_id: str):
    """Serve the Video File (real or mock)"""
    job_data = get_job_data(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Job ID not found")

    if job_data["status"] != "completed":
        raise HTTPException(status_code=400, detail="Video not ready for download")

    video_path = job_data.get("video_path")
    if not video_path or not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video file not found")

    return FileResponse(
        video_path,
        media_type="video/mp4",
        headers={
            "Content-Disposition": f"inline; filename={job_id}.mp4",
            "Accept-Ranges": "bytes"
        }
    )

# ========== NEW WHATSAPP BOT FUNCTIONALITY ==========

@app.post("/webhook/whatsapp")
async def whatsapp_webhook(
    background_tasks: BackgroundTasks,
    From: str = Form(...),
    To: str = Form(...),
    Body: str = Form(...),
    MessageSid: str = Form(...),
):
    
    
    """Handle incoming WhatsApp messages"""
    
    if not twilio_client:
        print("❌ Twilio client not available")
        return {"status": "error", "message": "Service unavailable"}
    
    user_phone = From
    message_text = Body.strip()
    
    print(f"📱 WhatsApp message from {user_phone}: {message_text}")
    
    if is_user_rate_limited(user_phone):
        rate_limit_msg = get_rate_limit_message(user_phone)
        send_whatsapp_message(user_phone, rate_limit_msg)
        print(f"Rate limited user: {user_phone}")
        return {"status": "rate_limited"}
    
    if not redis_client.get(f"user_welcomed:{user_phone}"):
        welcome_text = """ **Welcome to AI Video Bot!**

🎬 **Available Commands:**
• `/generate <prompt>` - Create AI video
• `/help` - Show commands menu  
• `/status` - Check your videos
• `/history` - View recent videos
• `/enhance <prompt>` - Auto-improve prompt

💡 **Quick Start:**
Just type: `/generate dancing robot`

Let's create amazing videos together! ✨"""
        
        send_whatsapp_message(user_phone, welcome_text)
        
        # Mark user as welcomed
        redis_client.set(f"user_welcomed:{user_phone}", "1", ex=604800)
    
    try:
            # NEW: Check if user is in a conversation state
        user_state = get_user_state(user_phone)
        
        # Handle state-based responses
        if user_state:
            state = user_state.get("state")
            data = user_state.get("data", {})
            
            if state == "awaiting_enhancement_choice":
                if message_text in ['1', '2', '3']:
                    if message_text == '1':
                        # User chose enhanced prompt
                        final_prompt = data["enhanced_prompt"]
                        response_msg = f"✨ **Using enhanced prompt:**\n{final_prompt[:80]}{'...' if len(final_prompt) > 80 else ''}\n\n🎬 Starting video generation..."
                        send_whatsapp_message(user_phone, response_msg)
                        clear_user_state(user_phone)
                        background_tasks.add_task(handle_whatsapp_video_generation, final_prompt, user_phone)
                        return {"status": "generating_enhanced"}
                        
                    elif message_text == '2':
                        # User chose original prompt
                        final_prompt = data["original_prompt"]
                        response_msg = f"📝 **Using original prompt:**\n{final_prompt}\n\n🎬 Starting video generation..."
                        send_whatsapp_message(user_phone, response_msg)
                        clear_user_state(user_phone)
                        background_tasks.add_task(handle_whatsapp_video_generation, final_prompt, user_phone)
                        return {"status": "generating_original"}
                        
                    else:  # message_text == '3' - Edit option
                        edit_msg = f"""✏️ **Edit your prompt:**

    **Current enhanced version:**
    {data['enhanced_prompt']}

    **Type your edited prompt below:** 👇"""
                        send_whatsapp_message(user_phone, edit_msg)
                        store_user_state(user_phone, "awaiting_user_edit", {
                            "original_prompt": data["original_prompt"],
                            "enhanced_prompt": data["enhanced_prompt"]
                        })
                        return {"status": "awaiting_edit"}
                else:
                    send_whatsapp_message(user_phone, "❓ Please reply with:\n**1** (YES), **2** (NO) or **3** (EDIT)")
                    return {"status": "invalid_choice"}
            
            elif state == "awaiting_user_edit":
                # User has typed their edited prompt
                edited_prompt = message_text.strip()
                
                if len(edited_prompt) < 5:
                    send_whatsapp_message(user_phone, "❓ Your edited prompt is too short. Please try again:")
                    return {"status": "edit_too_short"}
                
                response_msg = f"📝 **Using your edited prompt:**\n{edited_prompt[:80]}{'...' if len(edited_prompt) > 80 else ''}\n\n🎬 Starting video generation..."
                send_whatsapp_message(user_phone, response_msg)
                clear_user_state(user_phone)
                background_tasks.add_task(handle_whatsapp_video_generation, edited_prompt, user_phone)
                return {"status": "generating_edited"}
        # Handle commands
        
        if message_text.startswith('/generate '):
            prompt = message_text[10:].strip()  # Remove '/generate '
            
            if len(prompt) < 5:
                error_msg = """🤔 Your prompt seems too short!

        Try: /generate A cute cat playing piano in space

        Make it more descriptive for better results!"""
                send_whatsapp_message(user_phone, error_msg)
                return {"status": "prompt_too_short"}
            
            is_safe, filter_error = comprehensive_content_filter(prompt)
            if not is_safe:
                send_whatsapp_message(user_phone, filter_error)
                print(f"🚫 Content blocked from {user_phone}: {prompt[:50]}...")
                return {"status": "content_blocked"}
            
            # Generate enhanced version
            enhanced_prompt = enhance_prompt_free(prompt)
            
            # Ask user for enhancement choice
            choice_msg = f"""✨ **Enhance your prompt for better video quality?**

        **Original:** {prompt}

        **Enhanced:** {enhanced_prompt[:120]}{'...' if len(enhanced_prompt) > 120 else ''}

        **Choose an option:**
        1️⃣ **YES** - Use enhanced version (recommended)
        2️⃣ **NO** - Keep original
        3️⃣ **EDIT** - Edit enhanced version

        Reply with **1**, **2**, or **3**"""
            
            # Store state
            store_user_state(user_phone, "awaiting_enhancement_choice", {
                "original_prompt": prompt,
                "enhanced_prompt": enhanced_prompt
            })
            
            send_whatsapp_message(user_phone, choice_msg)
            return {"status": "enhancement_choice_sent"}

        
        elif message_text.startswith('/'):
            response = handle_whatsapp_command(message_text, user_phone)
            send_whatsapp_message(user_phone, response)
            return {"status": "success"}
        
        # If not a command, suggest using /generate
        if not message_text.startswith('/generate'):
            help_text = """👋 Welcome to the AI Video Bot!

To generate a video, use:
/generate <your prompt>

Example:
/generate A cat playing piano in space

Other commands:
/help - Show help
/status - Bot status"""
            send_whatsapp_message(user_phone, help_text)
            return {"status": "help_sent"}
        
        
        
        # Invalid /generate usage
        send_whatsapp_message(
            user_phone, 
            "❓ Use: /generate <your prompt>\n\nExample: /generate A sunset over mountains"
        )
        return {"status": "invalid_command"}
        
    except Exception as e:
        print(f"❌ WhatsApp webhook error: {e}")
        send_whatsapp_message(user_phone, "❌ Sorry, something went wrong. Please try again.")
        return {"status": "error", "message": str(e)}

def handle_whatsapp_command(command: str, user_phone: str) -> str:
    """Handle WhatsApp bot commands"""
    command = command.lower().strip()
    
    if command == '/help':
        return """🤖 **AI Video Bot Help**

**Generate Videos:**
/generate <your prompt>

**Commands:**
/help - Show this help
/status - Bot status

**Examples:**
/generate A golden retriever playing in a park
/generate Astronaut floating in space
/generate Ocean waves at sunset

**Tips:**
• Be descriptive (min 5 words)
• Include actions, settings, objects
• Videos take around 3 minutes to generate"""
    
    elif command == '/status':
        redis_status = "✅ Connected" if redis_client else "❌ Disconnected"
        twilio_status = "✅ Connected" if twilio_client else "❌ Disconnected"
        
        return f"""🟢 **Bot Status: Online**

**Services:**
Redis: {redis_status}
Twilio: {twilio_status}
Video API: ✅ Ready

Type /help for usage instructions"""
    
    else:
        return """❓ Unknown command

Available commands:
/help - Show help
/generate <prompt> - Create video
/status - Check status

Example: /generate A cat dancing"""

def send_whatsapp_message(to: str, body: str, media_url: str = None):
    """Send WhatsApp message with optional media attachment"""
    try:
        message_data = {
            'from_': TWILIO_WHATSAPP_FROM,
            'body': body,
            'to': to
        }
        
        # Add media URL if provided
        if media_url:
            message_data['media_url'] = [media_url]  # Must be a list
        
        message = twilio_client.messages.create(**message_data)
        print(f"📤 WhatsApp message sent to {to}: {message.sid}")
        return message
        
    except Exception as e:
        print(f"❌ Failed to send WhatsApp message: {e}")
        return None

async def handle_whatsapp_video_generation(prompt: str, user_phone: str):
    """Handle video generation workflow for WhatsApp"""
    try:
        # Send acknowledgment
        send_whatsapp_message(
            user_phone, 
            f"🎬 Generating your video: '{prompt}'\n\nThis usually takes around 3 minutes..."
        )
        
        # Create job
        job_id = str(uuid.uuid4())
        job_data = {
            "status": "processing",
            "message": "Processing request...",
            "video_url": None,
            "prompt": prompt,
            "user_phone": user_phone
        }
        store_job_data(job_id, job_data)
        
        # Send progress update
        await asyncio.sleep(5)
        send_whatsapp_message(user_phone, "🤖 AI model is working on your video...")
        
        # Generate video
        await video_generation_process(job_id, prompt, user_phone)
        
        # Check final status and send result
        final_job_data = get_job_data(job_id)
        if final_job_data and final_job_data["status"] == "completed":
            PUBLIC_BASE_URL = "https://d2a0b53073b1.ngrok-free.app"
            video_url = f"{PUBLIC_BASE_URL}/api/download/{job_id}"
            send_whatsapp_message(user_phone, "Here's your video:", media_url=video_url)
        
        else:
            send_whatsapp_message(
                user_phone,
                "❌ Video generation failed. Please try again with a different prompt."
            )
        
    except Exception as e:
        print(f"❌ WhatsApp video generation failed: {e}")
        send_whatsapp_message(
            user_phone,
            "❌ Sorry, video generation failed. Please try again."
        )

# ========== HELPER FUNCTIONS ==========

def store_job_data(job_id: str, data: dict):
    """Store job data in Redis or fallback to memory"""
    if redis_client:
        try:
            redis_client.setex(f"job:{job_id}", 3600, json.dumps(data))
            return
        except Exception as e:
            print(f"Redis store failed: {e}")
    
    # Fallback to memory
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
        store_job_data(job_id, current_data)

# ========== VIDEO GENERATION (UPDATED WITH VIDU API) ==========

async def video_generation_process(job_id: str, prompt: str, user_phone: str = None):
    """Generate Video using Vidu API with proper error handling"""
    task_id = None  # ✅ Initialize task_id upfront
    
    try:
        print(f"🎬 Starting video generation: {prompt}")
        
        # Update status
        update_job_data(job_id, {
            "message": "🤖 Connecting to Vidu AI model...",
            "status": "processing"
        })
        
        # Try Vidu API
        vidu_api_key = os.getenv("VIDU_API_KEY")
        vidu_base_url = os.getenv("VIDU_BASE_URL", "https://api.vidu.com")
        
        if not vidu_api_key:
            raise Exception("Missing Vidu API key")
        
        headers = {
            "Authorization": f"Token {vidu_api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "vidu1.5",
            "prompt": prompt,
            "duration": 4,
            "aspect_ratio": "16:9",
            "resolution": "720p",
            "movement_amplitude": "small"
        }
        
        print("📡 Sending request to Vidu API...")
        response = requests.post(
            f"{vidu_base_url}/ent/v2/text2video",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        print(f"📝 Vidu API Response Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            task_id = result.get("task_id")  # ✅ Assign task_id safely
            
            if not task_id:
                raise Exception("No task_id in Vidu API response")
                
            print(f"✅ Vidu task created: {task_id}")
            
            # Poll for completion with CORRECT endpoint
            video_path = await poll_vidu_task(task_id, job_id, vidu_api_key, vidu_base_url)
            
            if video_path:
                PUBLIC_BASE_URL = "https://d2a0b53073b1.ngrok-free.app"
                update_job_data(job_id, {
                    "status": "completed",
                    "message": "✅ Video generated successfully!",
                    "video_url": f"{PUBLIC_BASE_URL}/api/download/{job_id}",
                    "video_path": video_path
                })
                return
        
    
        raise Exception(f"Vidu API failed: {response.status_code} - {response.text}")
        
    except Exception as vidu_error:
        print(f"⚠️ Vidu API failed: {vidu_error}")
        
    
        if task_id:
            print(f"🔄 Failed task ID: {task_id}")
        
        
        print("📼 Using HuggingFace fallback")
        await use_huggingface_fallback(job_id, prompt)

async def poll_vidu_task(task_id: str, job_id: str, api_key: str, base_url: str):
    """Poll Vidu task until video is ready"""
    headers = {"Authorization": f"Token {api_key}"}

    for attempt in range(120):  
        try:
            response = requests.get(
                f"{base_url}/ent/v2/tasks/{task_id}/creations",
                headers=headers,
                timeout=15
            )

            if response.status_code != 200:
                print(f"HTTP {response.status_code} error")
                await asyncio.sleep(5)
                continue

            data = response.json()
            state = data.get("state", "")
            print(f"Attempt {attempt + 1}: {state}")

            if state == "success":
                creations = data.get("creations", [])
                if creations:
                    video_url = creations[0].get("url")
                    if video_url:
                        return await download_vidu_video(video_url, job_id)
                return None
                
            elif state == "failed":
                print("Generation failed")
                return None
                
            else:
                await asyncio.sleep(5)
                
        except Exception as e:
            print(f"Polling error: {e}")
            await asyncio.sleep(5)

    print("Polling timeout")
    return None

async def download_vidu_video(url: str, job_id: str):
    """Download video and save locally"""
    try:
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        
        os.makedirs("./videos", exist_ok=True)
        video_path = f"./videos/{job_id}.mp4"
        
        with open(video_path, "wb") as f:
            f.write(response.content)
            
        print(f"Video downloaded: {video_path}")
        return video_path
        
    except Exception as e:
        print(f"Download failed: {e}")
        return None


async def use_huggingface_fallback(job_id: str, prompt: str):
    """Fallback to HuggingFace (your original implementation)"""
    try:
        from gradio_client import Client
        
        hf_token = os.getenv("HUGGINGFACE_TOKEN")
        if hf_token:
            login(hf_token)
            
        update_job_data(job_id, {"message": "🤖 Using HuggingFace model..."})
        
        client = Client("hysts/zeroscope-v2")
        result = client.predict(
            prompt=prompt,
            seed=0,
            num_frames=24,
            num_inference_steps=25,
            api_name="/run"
        )
        
        
        if isinstance(result, dict) and 'video' in result:
            temp_video_path = result['video']
        else:
            temp_video_path = result
        
        videos_dir = "./videos"
        os.makedirs(videos_dir, exist_ok=True)
        permanent_video_path = f"{videos_dir}/{job_id}.mp4"
        
        if os.path.exists(temp_video_path):
            shutil.copy2(temp_video_path, permanent_video_path)
            
            update_job_data(job_id, {
                "status": "completed",
                "message": "✅ Video generated successfully!",
                "video_url": f"/api/download/{job_id}",
                "video_path": permanent_video_path
            })
        else:
            raise Exception("HuggingFace video not found")
            
    except Exception as hf_error:
        print(f"⚠️ HuggingFace fallback failed: {hf_error}")
        await use_mock_video_fallback(job_id, prompt)

async def use_mock_video_fallback(job_id: str, prompt: str):
    """Final fallback to mock video"""
    try:
        videos_dir = "./videos"
        mock_video_path = f"{videos_dir}/mock_video.mp4"
        final_path = f"{videos_dir}/{job_id}.mp4"
        
        if os.path.exists(mock_video_path):
            shutil.copy2(mock_video_path, final_path)
            
            update_job_data(job_id, {
                "status": "completed",
                "message": "✅ Demo video ready (using placeholder)",
                "video_url": f"/api/download/{job_id}",
                "video_path": final_path
            })
        else:
            raise Exception("No mock video available")
            
    except Exception as e:
        update_job_data(job_id, {
            "status": "error",
            "message": f"❌ All video generation methods failed",
            "video_url": None
        })

if __name__ == "__main__":
    """Run the FastAPI app with Uvicorn"""
    port = int(os.getenv("PORT", 8000))
    print(f"Starting AI Video Generator with WhatsApp Bot on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port, timeout_keep_alive=900, timeout_graceful_shutdown=30)
