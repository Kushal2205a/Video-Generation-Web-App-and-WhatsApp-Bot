import shutil
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
import os
from gradio_client import Client
from dotenv import load_dotenv
import asyncio
import uuid
import json
from typing import Dict, Optional
import uvicorn
from huggingface_hub import login
from pathlib import Path

load_dotenv()

app = FastAPI(title="AI Video Generator API")

VIDEO_GENERATION_STATUS: Dict[str, dict] = {}

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

@app.get("/", response_class=HTMLResponse)
async def serve_html():
    """Serves the HTML page"""
    with open("../frontend/index.html", "r") as f:
        return HTMLResponse(content=f.read())

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
    """Start the Video Generation Process."""
    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt is required")
    
    job_id = str(uuid.uuid4())
    
    # Initialize Status - FIXED
    VIDEO_GENERATION_STATUS[job_id] = {
        "status": "processing",
        "message": "Video generation has started",
        "video_url": None,
        "prompt": request.prompt
    }
    
    asyncio.create_task(video_generation_process(job_id, request.prompt))
    
    return Video_Job_Created_Response(
        job_id=job_id,
        status="processing",
        message="Video generation has started"
    )

@app.get("/api/status/{job_id}", response_model=Status_Response)
async def get_status(job_id: str):
    """Get the status of Video generation"""
    if job_id not in VIDEO_GENERATION_STATUS:
        raise HTTPException(status_code=404, detail="Job ID not found")
    
    job_data = VIDEO_GENERATION_STATUS[job_id]
    
    return Status_Response(
        job_id=job_id,
        status=job_data["status"],
        message=job_data["message"],
        video_url=job_data.get("video_url")
    )

async def video_generation_process(job_id: str, prompt: str):
    """Generate Video with mock fallback for quota limits"""
    try:
        env_file = Path(__file__).parent / '.env'
        load_dotenv(dotenv_path=env_file)
        hf_token = os.getenv("HUGGINGFACE_TOKEN")
        login(hf_token)
        
        if not hf_token:
            raise Exception("HuggingFace token not found in .env file")
        
        VIDEO_GENERATION_STATUS[job_id]["message"] = "🤖 Connecting to AI model..."
        
        # Hugging Face Model
        client = Client("hysts/zeroscope-v2")
        result = client.predict(
            prompt=prompt,
            seed=0,
            num_frames=24,
            num_inference_steps=25,
            api_name="/run"
        )
        
        # Real generation succeeded
        if isinstance(result, dict) and 'video' in result:
            temp_video_path = result['video']
        else:
            temp_video_path = result
        
        videos_dir = "./videos"
        os.makedirs(videos_dir, exist_ok=True)
        permanent_video_path = f"{videos_dir}/{job_id}.mp4"
        
        if os.path.exists(temp_video_path):
            shutil.copy2(temp_video_path, permanent_video_path)
            message = "Video generated successfully!"
        else:
            raise Exception(f"Generated video not found at: {temp_video_path}")
        
    except Exception as e:
        # Check if it's a quota error
        if "exceeded your GPU quota" in str(e) or "quota" in str(e).lower():
            
            # mock video 
            videos_dir = "./videos"
            mock_video_path = f"{videos_dir}/mock_video.mp4"
            
            if os.path.exists(mock_video_path):
                VIDEO_GENERATION_STATUS[job_id] = {
                    "status": "completed",
                    "message": "Demo: Using pre-generated video due to API quota limits",
                    "video_url": f"/api/download/{job_id}",
                    "video_path": mock_video_path,
                    "prompt": prompt
                }
                return
        
        # Regular error handling
        VIDEO_GENERATION_STATUS[job_id] = {
            "status": "error",
            "message": f"Error: {str(e)}",
            "video_url": None,
            "prompt": prompt
        }
        return
    
    # Success with real generation
    VIDEO_GENERATION_STATUS[job_id] = {
        "status": "completed",
        "message": message,
        "video_url": f"/api/download/{job_id}",
        "video_path": permanent_video_path,
        "prompt": prompt
    }


@app.get("/api/download/{job_id}")
async def download_video(job_id: str):
    """Serve the Video File (real or mock)"""
    
    # Ensure the job ID exists
    if job_id not in VIDEO_GENERATION_STATUS:
        raise HTTPException(status_code=404, detail="Job ID not found")
    
    job_data = VIDEO_GENERATION_STATUS[job_id]
    
    # Ensure the job has completed successfully
    if job_data["status"] != "completed":
        raise HTTPException(status_code=400, detail="Video not ready for download")
    
    video_path = job_data.get("video_path")

    # Ensure the video file path is valid and exists
    if not video_path or not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video file not found")
    
    # Serve the file as an MP4 with streaming and range support
    return FileResponse(
        video_path,
        media_type="video/mp4",
        headers={
            "Content-Disposition": f"inline; filename={job_id}.mp4", # Display inline with filename
            "Accept-Ranges": "bytes" # Allow Partial Requests
        }
    )

if __name__ == "__main__":
    """Run the FastAPI app with Uvicorn"""
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port,timeout_keep_alive=900,timeout_graceful_shutdown=30)
