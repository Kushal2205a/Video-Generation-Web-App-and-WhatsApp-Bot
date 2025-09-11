# app/routes/web.py
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from pathlib import Path
import os
import uuid
import asyncio

from app.models import Video_Request, Video_Job_Created_Response, Status_Response
from app.services.video_service import video_generation_process
from app.services.redis_service import store_job_data, get_job_data

router = APIRouter()

# Compute STATIC_DIR robustly relative to this file:
BASE_DIR = Path(__file__).resolve().parents[1]  # <project_root>/app
STATIC_DIR = BASE_DIR / "static"

def _static_path(filename: str) -> Path:
    """Return resolved static path if exists, else None."""
    candidate = (STATIC_DIR / filename).resolve()
    # ensure the resolved path is still within STATIC_DIR (safety)
    try:
        if STATIC_DIR.resolve() in candidate.parents or candidate == STATIC_DIR.resolve():
            if candidate.exists():
                return candidate
    except Exception:
        pass
    return None

@router.get("/", response_class=HTMLResponse)
async def serve_html():
    """Serves the HTML page"""
    index_file = _static_path("index.html")
    if index_file:
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>AI Video Generator</h1><p>Frontend not available</p>")

@router.get("/style.css")
async def serve_css():
    """Serves the CSS file"""
    css = _static_path("style.css")
    if css:
        return FileResponse(str(css), media_type="text/css")
    raise HTTPException(status_code=404, detail="style.css not found")

@router.get("/script.js")
async def serve_js():
    """Serves the Javascript file"""
    js = _static_path("script.js")
    if js:
        return FileResponse(str(js), media_type="text/javascript")
    raise HTTPException(status_code=404, detail="script.js not found")

@router.post("/api/generate-video", response_model=Video_Job_Created_Response)
async def generate_video(request: Video_Request):
    """Start the Video Generation Process (for web app)."""
    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt is required")

    job_id = str(uuid.uuid4())

    # Store in Redis / fallback
    job_data = {
        "status": "processing",
        "message": "Video generation has started",
        "video_url": None,
        "prompt": request.prompt
    }

    store_job_data(job_id, job_data)

    # Start generation in background (non-blocking)
    asyncio.create_task(video_generation_process(job_id, request.prompt))

    return Video_Job_Created_Response(
        job_id=job_id,
        status="processing",
        message="Video generation has started"
    )

@router.get("/api/status/{job_id}", response_model=Status_Response)
async def get_status(job_id: str):
    """Get the status of Video generation"""
    job_data = get_job_data(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Job ID not found")

    return Status_Response(
        job_id=job_id,
        status=job_data.get("status", "unknown"),
        message=job_data.get("message", ""),
        video_url=job_data.get("video_url")
    )

@router.get("/api/download/{job_id}")
async def download_video(job_id: str):
    """Serve the Video File (real or mock)"""
    job_data = get_job_data(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Job ID not found")

    if job_data.get("status") != "completed":
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
