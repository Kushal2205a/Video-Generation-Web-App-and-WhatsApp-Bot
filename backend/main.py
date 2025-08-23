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
from typing import Dict


load_dotenv() #load environment variables

app = FastAPI(title = "Video Generation API")

VIDEO_GENERATION_STATUS :Dict[str,dict] = {}

class Video_Request(BaseModel):
    prompt : str
    
class Video_Job_Created_Response(BaseModel):
    job_id : str
    status : str
    message : str

class Status_Response(BaseModel):
    job_id: str
    status:str
    message:str
    video_url : str = None 
 
@app.get("/", response_class=HTMLResponse) 
#Serves the HTML page
async def serve_html():
    with open("../frontend/index.html", "r") as f : 
        return HTMLResponse(content= f.read())
    
@app.get("/style.css", response_class=FileResponse) 
#Serves the CSS file
async def serve_css(): 
    return FileResponse("../frontend/style.css", media_type="text/css")    

@app.get("/script.js", response_class=FileResponse)
#Serves the Javascript file 
async def serve_js():
    return FileResponse("../frontend/script.js", media_type = "text/javascript")

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
        "status" : "processing", 
        "message": "Video generation has started",
        "video_url": None,
        "prompt" : request.prompt
        
    }
    
    # Start a Background Task 
    asyncio.create_task(video_generation_process(job_id,request.prompt)) 
    
    return Video_Job_Created_Response(
        job_id= job_id, 
        status="processing", 
        message="Video generation has started"
                                      
    )
    
@app.get("/api/status/{job_id}", response_model ="Status_Response")
async def get_status(job_id:str):
    if job_id not in VIDEO_GENERATION_STATUS:
        raise HTTPException(status_code=404, detail= "Job ID not found")
    
    status = VIDEO_GENERATION_STATUS[job_id]
    
    return Status_Response(
        job_id= job_id,
        status = status["status"]
        message= status["message"]
        video_url= status.get("video_url")
         
        
        
    )    
    
    
    

    