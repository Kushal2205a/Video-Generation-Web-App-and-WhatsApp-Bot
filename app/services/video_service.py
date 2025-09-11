
import os, shutil, subprocess, asyncio, requests, uuid
from app.services.redis_service import update_job_data, store_conversation_context
from app.config import twilio_client
from huggingface_hub import login

async def compress_video(input_path: str, output_path: str, quality: str = "medium") -> str:
    
    # Check if FFmpeg is available
    ffmpeg_cmd = shutil.which('ffmpeg')
    if not ffmpeg_cmd:
        print("FFmpeg not found in PATH")
        return input_path
    
    print(f"Using FFmpeg at: {ffmpeg_cmd}")
    
    # Quality presets
    compression_settings = {
        "whatsapp": [
            "-c:v", "libx264",
            "-crf", "28",
            "-preset", "medium",
            "-vf", "scale='min(720,iw)':'min(720,ih)':force_original_aspect_ratio=decrease",
            "-c:a", "aac",
            "-b:a", "128k",
            "-maxrate", "1M",
            "-bufsize", "2M"
        ],
        "medium": [
            "-c:v", "libx264",
            "-crf", "23",
            "-preset", "medium",
            "-vf", "scale=720:-2",
            "-c:a", "aac",
            "-b:a", "128k"
        ]
    }
    
    settings = compression_settings.get(quality, compression_settings["whatsapp"])
    
    try:
        
        cmd = [
            ffmpeg_cmd,
            "-i", input_path,
            "-y",  
            "-loglevel", "error" 
        ] + settings + [output_path]
        
        print(f" Running compression: {' '.join(cmd[:5])}...")
        
        # Run compression
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  
        )
        
        if result.returncode == 0:
            if os.path.exists(output_path):
                original_size = os.path.getsize(input_path)
                compressed_size = os.path.getsize(output_path)
                compression_ratio = (1 - compressed_size/original_size) * 100
                
                print(f"Compression successful!")
                print(f"Size: {original_size/1024/1024:.1f}MB → {compressed_size/1024/1024:.1f}MB ({compression_ratio:.1f}% reduction)")
                
                return output_path
            else:
                print("Compression failed - output file not created")
                return input_path
        else:
            print(f"FFmpeg failed with code {result.returncode}")
            print(f"Error: {result.stderr}")
            return input_path
            
    except subprocess.TimeoutExpired:
        print("Compression timeout after 5 minutes")
        return input_path
    except Exception as e:
        print(f"Compression exception: {e}")
        return input_path

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

# VIDEO GENERATION
async def video_generation_process(job_id: str, prompt: str, user_phone: str = None):
    from app.services.whatsapp_service import send_progress_update
    """Generate Video using Vidu API"""
    task_id = None  # Initialize task_id
    final_video_path = None # Initialize final_video_path
    
    try:
        print(f" Starting video generation: {prompt}")
        

        
        if user_phone:
            await send_progress_update(user_phone, 
                f""" *Video Generation Started*
                
*Your prompt:* {prompt}

*Status:* Connecting to AI model...
*Estimated time:* 2-3 minutes
I'll keep you updated""")
        
        # Status Update 1 
        update_job_data(job_id, {
            "message": "Connecting to Vidu AI model...",
            "status": "processing",
            "progress" : 10
        })
        
        # Vidu API
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
        
        # Status Update 2
        update_job_data(job_id, {
            "message": "Sending request to AI model...",
            "status": "processing",
            "progress": 20
        })
        
        if user_phone:
            await send_progress_update(user_phone, 
                " *Connected* Sending your video request...")
        
        print(" Sending request to Vidu API...")
        response = requests.post(
            f"{vidu_base_url}/ent/v2/text2video",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        print(f" Vidu API Response Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            task_id = result.get("task_id")  #Assign task_id safely
            
            if not task_id:
                raise Exception("No task_id in Vidu API response")
            
            update_job_data(job_id, {
                "message": "Your video is being generated...",
                "status": "processing",
                "progress": 30
            })

        if user_phone:
            await send_progress_update(user_phone, 
                    f""" *Video Generation In Progress*
*AI Model:* Vidu 1.5
*Task ID:* `{task_id[:8]}...`
*Creating:* {prompt}
*Next update:* ~90 seconds""")

            print(f"Vidu task created: {task_id}")
        
            
            # Poll for completion
            video_path = await poll_vidu_task(task_id, job_id, vidu_api_key, vidu_base_url)
            
            if video_path:
                final_video_path = video_path
                print("Starting video compression...")
                update_job_data(job_id, {
                    "message": "Compressing video for optimal delivery...",
                    "status": "processing",
                    "progress": 80
                })
                
                if user_phone:
                    await send_progress_update(user_phone, 
                        " *Video Generated Successfully!* Now optimizing for WhatsApp...")

                print("Starting video compression...")
                 
                # Check file size 
                original_file_size = os.path.getsize(video_path)
                original_file_size = original_file_size / (1024 * 1024)
                
                # Aggressive compression if still too large
                if original_file_size > 15:  # 15MB
                    print(f"File still large ({original_file_size:.1f}MB), applying aggressive compression...")
                    base_name = os.path.splitext(video_path)[0]
                    compressed_path = f"{base_name}_ultra.mp4"
                    final_video_path = await compress_video(video_path, compressed_path, "whatsapp")
                
                    
                    
                if final_video_path != video_path and os.path.exists(video_path):
                    try:
                        os.remove(video_path)
                        print("Cleaned up original uncompressed file")
                    except:
                        pass
                    
                PUBLIC_BASE_URL = "https://video-generation-web-app-production.up.railway.app"
                update_job_data(job_id, {
                    "status": "completed",
                    "message": "Yay, Video generated successfully!",
                    "video_url": f"{PUBLIC_BASE_URL}/api/download/{job_id}",
                    "video_path": video_path
                })
                
                store_conversation_context(user_phone, "video_completed", {
                    "job_id": job_id,
                    "prompt": prompt,
                    "video_url": f"{PUBLIC_BASE_URL}/api/download/{job_id}" 
                })
                return
        
    
        raise Exception(f"Vidu API failed: {response.status_code} - {response.text}")
        
    except Exception as vidu_error:
        print(f" Vidu API failed: {vidu_error}")
        
    
        if task_id:
            print(f" Failed task ID: {task_id}")
        
        
        print("Using HuggingFace fallback")
        await use_huggingface_fallback(job_id, prompt)

async def get_vidu_credits():
    """Check remaining Vidu API credits using official endpoint"""
    try:
        headers = {
            "Authorization": f"Token {os.getenv('VIDU_API_KEY')}",
            "Content-Type": "application/json"
        }
        
        # Official Vidu API endpoint
        response = requests.get(
            "https://api.vidu.com/ent/v2/credits",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # Extract total remaining credits from all packages
            total_remaining = 0
            package_info = []
            
            for package in data.get('remains', []):
                remaining = package.get('credit_remain', 0)
                package_type = package.get('type', 'unknown')
                total_remaining += remaining
                package_info.append({
                    'type': package_type,
                    'remaining': remaining,
                    'concurrency_limit': package.get('concurrency_limit', 0),
                    'current_concurrency': package.get('current_concurrency', 0),
                    'queue_count': package.get('queue_count', 0)
                })
            
            return total_remaining, package_info
        else:
            print(f"Vidu API error: {response.status_code} - {response.text}")
            return None, None
            
    except Exception as e:
        print(f"Failed to get Vidu credits: {e}")
        return None, None
    


def calculate_videos_remaining(credits: int) -> dict:
    """Calculate how many videos can be generated with remaining credits"""
    if not credits:
        return {"No of credits left": 0}

    return {
        "No of credits left": credits // 4,
        
    }

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
