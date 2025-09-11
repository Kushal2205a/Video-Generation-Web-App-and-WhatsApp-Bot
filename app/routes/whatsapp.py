from fastapi import APIRouter, Form, BackgroundTasks
from app.services.whatsapp_service import (
    send_whatsapp_message,
    handle_whatsapp_command,
    handle_whatsapp_video_generation,
    send_progress_update
)

from app.services.redis_service import (
    store_user_state, get_user_state, clear_user_state,
    store_conversation_context, is_user_rate_limited,
    get_rate_limit_message, generate_contextual_response, get_smart_suggestions
)
from app.utils.filters import comprehensive_content_filter
# inside the block



from app.config import twilio_client, redis_client

router = APIRouter()


# WHATSAPP BOT FUNCTIONALITY 
@router.post("/webhook/whatsapp")
async def whatsapp_webhook(
    background_tasks: BackgroundTasks,
    From: str = Form(...),
    To: str = Form(...),
    Body: str = Form(...),
    MessageSid: str = Form(...),
):
    
    
    """Handle incoming WhatsApp messages"""
    
    if not twilio_client:
        print(" Twilio client not available")
        return {"status": "error", "message": "Service unavailable"}
    
    user_phone = From
    message_text = Body.strip()
    
    print(f" WhatsApp message from {user_phone}: {message_text}")
    
    
    store_conversation_context(user_phone, "user_message", {
        "message": message_text,
        "message_id": MessageSid
    })
    
    if is_user_rate_limited(user_phone):
        rate_limit_msg = get_rate_limit_message(user_phone)
        send_whatsapp_message(user_phone, rate_limit_msg)
        print(f"Rate limited user: {user_phone}")
        return {"status": "rate_limited"}
    
    if not message_text.startswith('/'):
        contextual_response = generate_contextual_response(user_phone, message_text)
        if contextual_response:
            send_whatsapp_message(user_phone, contextual_response)
            return {"status": "contextual_response_sent"}
    
    # Handle /suggestions command
    if message_text.lower() == '/suggestions':
        suggestions = get_smart_suggestions(user_phone)
        send_whatsapp_message(user_phone, f"💡 *Personalized Suggestions:*\n\n{suggestions}")
        return {"status": "suggestions_sent"}
    
    # Handle /clear command
    if message_text.lower() == '/clear':
        context_key = f"context:{user_phone}"
        if redis_client:
            redis_client.delete(context_key)
        clear_response = "🧹 *Conversation history cleared!*\n\nYour chat history has been reset. Fresh start! 🆕"
        send_whatsapp_message(user_phone, clear_response)
        return {"status": "history_cleared"}
 
    # inside the block
    from app.services.video_service import get_vidu_credits, calculate_videos_remaining,enhance_prompt_free
    remaining, package_info = await get_vidu_credits()

    if message_text.lower() == '/credits':
        remaining, package_info = await get_vidu_credits()
        
        if remaining is not None and package_info:
            videos_left = calculate_videos_remaining(remaining)
            
            # Build package details
            package_details = ""
            for pkg in package_info:
                package_details += f"\n• **{pkg['type'].title()} Package:** {pkg['remaining']} credits"
                if pkg['concurrency_limit'] > 0:
                    package_details += f"\n  - Concurrent limit: {pkg['concurrency_limit']}"
                    package_details += f"\n  - Currently using: {pkg['current_concurrency']}"
                    if pkg['queue_count'] > 0:
                        package_details += f"\n  - In queue: {pkg['queue_count']}"
            
            credits_message = f""" *Vidu API Credits Status*

*Total Remaining Credits:* {remaining}

*Package Details:*{package_details}

*🎥 Videos You Can Generate:*
*4-second videos:* {videos_left['No of credits left']} videos left
"""
        
        else:
            credits_message = """ *Unable to check credits*

    Could not connect to Vidu API. Please check:
    - API key is configured correctly
    - Network connection is stable
    - Vidu API service is available

    Try `/help` for other commands or contact support."""

        send_whatsapp_message(user_phone, credits_message)
        return {"status": "credits_sent"}
    if not redis_client.get(f"user_welcomed:{user_phone}"):
        if not Body.strip().startswith("/"):
            welcome_text = """  *Welcome*

*Available Commands:*
• `/generate <prompt>` - Create AI video
• `/help` - Show commands menu  
• `/status` - Check bot status
• `/history` - View recent prompts
• `/credits` - Check no of credits left
• `/suggestions` - Get personalized video prompts based on user history
• `/clear` - Reset conversation history for privacy
 


*Example:*
Just type: `/generate dancing robot`
""" 
            send_whatsapp_message(user_phone, welcome_text)
            redis_client.set(f"user_welcomed:{user_phone}", "1", ex=604800)
        else:
            # mark as welcomed so command isn't blocked next time
            redis_client.set(f"user_welcomed:{user_phone}", "1", ex=604800)
            
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
                        response_msg = f" *Using original prompt:*\n{final_prompt}\n\n Starting video generation..."
                        send_whatsapp_message(user_phone, response_msg)
                        clear_user_state(user_phone)
                        background_tasks.add_task(handle_whatsapp_video_generation, final_prompt, user_phone)
                        return {"status": "generating_original"}
                        
                    else:  # User Chose to edit option 
                        edit_msg = f""" **Edit your prompt:**

    **Current enhanced version:**
    {data['enhanced_prompt']}

    *Type your edited prompt below:* """
                        send_whatsapp_message(user_phone, edit_msg)
                        store_user_state(user_phone, "awaiting_user_edit", {
                            "original_prompt": data["original_prompt"],
                            "enhanced_prompt": data["enhanced_prompt"]
                        })
                        return {"status": "awaiting_edit"}
                else:
                    send_whatsapp_message(user_phone, " Please reply with:\n*1* (YES), *2* (NO) or *3* (EDIT)")
                    return {"status": "invalid_choice"}
            
            elif state == "awaiting_user_edit":
                # User has typed their edited prompt
                edited_prompt = message_text.strip()
                
                if len(edited_prompt) < 5:
                    send_whatsapp_message(user_phone, " Your edited prompt is too short. Please try again:")
                    return {"status": "edit_too_short"}
                
                response_msg = f" *Using your edited prompt:*\n{edited_prompt[:80]}{'...' if len(edited_prompt) > 80 else ''}\n\n Starting video generation..."
                send_whatsapp_message(user_phone, response_msg)
                clear_user_state(user_phone)
                background_tasks.add_task(handle_whatsapp_video_generation, edited_prompt, user_phone)
                return {"status": "generating_edited"}
            
            
        # Handle commands
        if message_text.startswith('/generate '):
            prompt = message_text[10:].strip()
            
            store_conversation_context(user_phone, "video_request", {
                "prompt": prompt,
                "enhanced_prompt": enhance_prompt_free(prompt)
            })
            
            if len(prompt) < 5:
                error_msg = """ Your prompt seems too short.

        Try: /generate A cute cat playing piano in space

        Make it more descriptive for better results """
        
                send_whatsapp_message(user_phone, error_msg)
                return {"status": "prompt_too_short"}
            
            remaining, package_info = await get_vidu_credits()
    
            if remaining is not None:
                if remaining < 4:  # Minimum credits needed
                    low_credits_msg = f""" *Insufficient Credits*

You have *{remaining} credits* remaining, but need at least *4 credits* to generate a video.

 *Options:*
- Wait for credit renewal
- Purchase additional credits at https://platform.vidu.com
- Use `/credits` to check detailed status"""
                    
                    send_whatsapp_message(user_phone, low_credits_msg)
                    return {"status": "insufficient_credits"}
                
                # Show credits info with generation start
                credits_info = f"\n\n *Credits:* ~{remaining-4} remaining after generation"
            else:
                credits_info = "\n\n *Credits:* Unable to check current balance"
                
            
            is_safe, filter_error = comprehensive_content_filter(prompt)
            if not is_safe:
                if filter_error and filter_error.strip():
                    send_whatsapp_message(user_phone, filter_error)
                else:
                    send_whatsapp_message(user_phone, "❌ Content not allowed. Please try a different prompt.")
                print(f"🚫 Content blocked from {user_phone}: {prompt[:50]}...")
                return {"status": "content_blocked"}
            
            # Generate enhanced version
            enhanced_prompt = enhance_prompt_free(prompt)
            
            # Ask user for enhancement choice
            choice_msg = f"""✨ *Enhance your prompt for better video quality?*

        *Original:* {prompt}

        *Enhanced:* {enhanced_prompt[:120]}{'...' if len(enhanced_prompt) > 120 else ''}

        *Choose an option:*
        1️⃣ *YES* - Use enhanced version (recommended)
        2️⃣ *NO* - Keep original
        3️⃣ *EDIT* - Edit enhanced version

        Reply with *1*, *2*, or *3* """
            
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
            help_text = """ Heya there, *Welcome* 

To generate a video, use:
/generate <your prompt>

Example:
/generate A cat playing piano in space

Other commands:
/help - Show help
/status - Bot status
/credits - To show no of credits
/history - To show prompt history
/suggestions - Get personalized video prompts based on user history
/clear - Reset conversation history for privacy"""
            send_whatsapp_message(user_phone, help_text)
            return {"status": "help_sent"}
        
        
        
        # Invalid /generate usage
        send_whatsapp_message(
            user_phone, 
            " Use: /generate <your prompt>\n\nExample: /generate A sunset over mountains"
        )
        return {"status": "invalid_command"}
        
    except Exception as e:
        print(f" WhatsApp webhook error: {e}")
        send_whatsapp_message(user_phone, " Sorry, something went wrong. Please try again.")
        return {"status": "error", "message": str(e)}
