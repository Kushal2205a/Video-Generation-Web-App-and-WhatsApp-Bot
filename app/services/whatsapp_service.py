import uuid, asyncio
from app.config import twilio_client, TWILIO_WHATSAPP_FROM, redis_client
from app.services.redis_service import store_job_data, get_job_data, update_job_data
import json

def handle_whatsapp_command(command: str, user_phone: str) -> str:
    """Handle WhatsApp bot commands"""
    command = command.lower().strip()
    
    if command == '/help':
        return """ *AI Video Bot Help*

*Generate Videos:*
/generate <your prompt>

*Commands:*
/help - Show this help
/status - Bot status
/credits - check no of credits left
/history - To show prompt history
/suggestions - Get personalized video prompts based on user history
/clear - Reset conversation history for privacy

*Examples:*
/generate A golden retriever playing in a park
/generate Astronaut floating in space
/generate Ocean waves at sunset

*Tips:*
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

    elif command == '/history':
        if not redis_client:
            return " History unavailable (Redis not connected)"
        
        clean_phone = user_phone.replace("whatsapp:", "").replace("+", "").replace("-", "").replace(" ", "")
        pattern = f"user_job:{clean_phone}:*"
        job_keys = redis_client.keys(pattern)
        
        if not job_keys:
            return " No video history found."
        
        response_lines = [" *Your Recent Prompts:* "]
        
        for key in sorted(job_keys, reverse=True)[:5]:  # Last 5 jobs
            job_data = redis_client.get(key)
            if job_data:
                job = json.loads(job_data)
                status = job.get("status", "unknown").capitalize()
                prompt = job.get("prompt", "")[:30] + ("..." if len(job.get("prompt", "")) > 30 else "")
            
                
                job_id = key.split(":")[-1]
                line = f"- *{status}*: {prompt}"
                response_lines.append(line)
        
        return "\n".join(response_lines)
    
    
    
    
    else:
        return """ Unknown command

Available commands:
/help - Show help
/generate <prompt> - Create video
/status - Check status
/credits - check no of credits left
/history - To show prompt history
/clear - Reset conversation history for privacy
/suggestions - Get personalized video prompts based on user history


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
        print(f" Failed to send WhatsApp message: {e}")
        return None

async def handle_whatsapp_video_generation(prompt: str, user_phone: str):
    """Handle video generation for WhatsApp"""
    try:
        
        send_whatsapp_message(
            user_phone, 
            f" Generating your video: '{prompt}'\n\nThis usually takes around 3 minutes..."
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
        store_job_data(job_id, job_data, user_phone)
        
        # Send progress update
        await asyncio.sleep(5)
        send_whatsapp_message(user_phone, "Your video is being processed...")
        
        from app.services.video_service import video_generation_process
        
        # Generate video
        await video_generation_process(job_id, prompt, user_phone)
        
        # Check final status and send result
        final_job_data = get_job_data(job_id)
        if final_job_data and final_job_data["status"] == "completed":
            PUBLIC_BASE_URL = "https://video-generation-web-app-production.up.railway.app"
            video_url = f"{PUBLIC_BASE_URL}/api/download/{job_id}"
            send_whatsapp_message(user_phone, "Here's your video:", media_url=video_url)
        
        else:
            send_whatsapp_message(
                user_phone,
                " Video generation failed. Please try again with a different prompt."
            )
        
    except Exception as e:
        print(f" WhatsApp video generation failed: {e}")
        send_whatsapp_message(
            user_phone,
            " Sorry, video generation failed. Please try again."
        )

async def send_progress_update(user_phone: str, message: str):
    """Send progress update to user via WhatsApp"""
    if user_phone and twilio_client:
        try:
            send_whatsapp_message(user_phone, message)
            print(f"Progress update sent to {user_phone}: {message}")
        except Exception as e:
            print(f"Failed to send progress update: {e}")
