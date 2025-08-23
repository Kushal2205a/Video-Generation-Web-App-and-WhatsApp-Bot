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

load_dotenv(dotenv_path=".env", verbose=True)

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
    
    # If the Prompt is empty
    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt is required")
    
    # Create a unique job id
    job_id = str(uuid.uuid4())
    
    # Initialize Status
    VIDEO_GENERATION_STATUS[job_id] = {
        "status": "processing",
        "message": "Video generation has started",
        "video_url": None,
        "prompt": request.prompt
    }
    
    # Start a Background Task
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
    
    # Retrieve the stored job details
    job_data = VIDEO_GENERATION_STATUS[job_id]
    
    return Status_Response(
        job_id=job_id,
        status=job_data["status"],
        message=job_data["message"],
        video_url=job_data.get("video_url")
    )

async def video_generation_process(job_id: str, prompt: str):
    """Generate Video"""
    try:
        hf_token = os.getenv("HUGGINGFACE_TOKEN")
        if not hf_token:
            raise Exception("HuggingFace token not found in .env file")
        # Update the message
        VIDEO_GENERATION_STATUS[job_id]["message"] = "Connected to the ModelScope AI model"
        
        # ModelScope Model
        client = Client("ali-vilab/text-to-video-synthesis", hf_token=hf_token)
        
        VIDEO_GENERATION_STATUS[job_id]["message"] = f"Generating video for: '{prompt}'"
        
        result = client.predict(
            prompt=prompt,
            api_name="/predict"
        )
        
        # Update Status with Success
        VIDEO_GENERATION_STATUS[job_id] = {
            "status": "completed",
            "message": "Video generated Successfully",
            "video_url": f"/api/download/{job_id}",
            "video_path": result,
            "prompt": prompt
        }
        
    except Exception as e:
        VIDEO_GENERATION_STATUS[job_id] = {
            "status": "error",
            "message": f"Error Occurred: {str(e)}",
            "video_url": None,
            "prompt": prompt
        }

@app.get("/api/download/{job_id}")
async def download_video(job_id: str):
    """Serve the Video File"""
    if job_id not in VIDEO_GENERATION_STATUS:
        raise HTTPException(status_code=404, detail="Job ID not found")
    
    job_data = VIDEO_GENERATION_STATUS[job_id]
    
    if job_data["status"] != "completed":
        raise HTTPException(status_code=400, detail="Video not ready for download")
    
    video_path = job_data.get("video_path")
    if not video_path:
        raise HTTPException(status_code=500, detail="Video path not found")
    
    return FileResponse(
        video_path,
        media_type="video/mp4",
        filename=f"{job_id}.mp4"
    )

@app.get("/api/health")
async def health_check():
    return {"status": "Good", "message": "The model is running"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
