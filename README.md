# Video Generation Web App

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-async%20API-green)
![HuggingFace](https://img.shields.io/badge/HuggingFace-Zeroscope--v2-orange)


---

## Overview

The **Video Generation Web App** enables users to generate short videos from text prompts using the state-of-the-art [Zeroscope-v2](https://huggingface.co/hysts/zeroscope-v2) model on HuggingFace through **Gradio’s Python client**.  

With a modern frontend, asynchronous FastAPI backend, job queue management, and graceful fallbacks for quota limits, this project is built for both **demonstration** and **production-ready** environments.

---
## Features

- **Responsive Frontend** – Pure HTML/CSS/JS, dark/light switch friendly  
- **Async FastAPI Backend** – Handles job creation, status polling, and video streaming  
- **Job Queue & Tracking** – Real-time updates on video generation progress  
- **Organized Video Storage** – Clean `/videos` directory for generated & fallback videos  
- **Quota Fallback** – Serves a mock video seamlessly if HuggingFace API limits are hit  
- **Deployment Ready** – Secure `.env`, compatible with Render, Railway, etc.  

---

## Architecture

![Architecture](assets/VGWA_architecture.svg)

---

## Model Choice

- **Model Used:** `hysts/zeroscope-v2` (HuggingFace Space)  
- **Why this model?**  
  - Open-source, widely supported, and optimized for **short text-to-video generation**  
  - Accepts descriptive prompts → returns authentic short videos  
  - Stable API integration via `gradio_client`  
  - Actively maintained and documented for **research + production use cases**  

---

## API & Code Structure

| Endpoint                  | Method | Purpose                                 |
|---------------------------|--------|-----------------------------------------|
| `/`                       | GET    | Serves `index.html`                     |
| `/style.css`              | GET    | Stylesheet for UI                       |
| `/script.js`              | GET    | Frontend JS logic                       |
| `/api/generate-video`     | POST   | Start video generation, returns `job_id`|
| `/api/status/{job_id}`    | GET    | Poll for job status/progress            |
| `/api/download/{job_id}`  | GET    | Streams generated video file            |

**Backend (`main.py`)**  
- Job manager, async task system, HuggingFace API integration, and file serving  

**Frontend**  
- Plain HTML + CSS + JS (Courier New aesthetic)  
- Async polling & video download logic  

---

## Environment Variables & Security

Secrets are **never committed**.  

- `.env` is excluded via `.gitignore`  
- Uses `python-dotenv` locally  
- On production (Render, Railway, etc.), set environment variables in dashboard  

**Example `.env` (not in repo):**
```env
HUGGINGFACE_TOKEN=hf_XXXXXXXXXXXXXXXX
***

## Local Development

### Prerequisites

```bash
Python 3.8+
pip                            # Package manager
```

### Setup

1. **Clone the repo:**
    ```bash
    git clone https://github.com/YourUsername/Video-Generator-WebApp.git
    cd Video-Generator-WebApp
    ```

2. **Create virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate   # On Windows: venv\Scripts\activate
    ```

3. **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4. **Setup environment variables:**  
   Create a `.env` and add your HuggingFace API Key.
    ```
    HUGGINGFACE_TOKEN=hf_XXXXXXXXXXXXXXXX
    ```

5. **Run the server:**
    ```bash
    python main.py
    ```

***

## Deployment

### Quick Start (e.g., Render/Railway)

- **Push code (without `.env`) to GitHub.**
- On Render/Railway:
  - Build: `pip install -r requirements.txt`
  - Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
  - Add environment variable: `HUGGINGFACE_TOKEN`
- Make sure `/videos` directory exists (for generated and fallback videos)

### Production Notes

- Video serving is secured, with streaming and proper MIME.
- Mock video fallback is built-in for quota handling.
- Logging and error handling included for production review.

***

## Placeholder Video & Quota Fallback

When HuggingFace GPU quotas are exhausted, the backend serves a sample video with a clear status—demonstrating robust error handling and continuous user experience.

***

## Technology Stack

- **Backend:** Python 3.8+, FastAPI, Uvicorn, python-dotenv
- **Front-end:** HTML, CSS, JavaScript (no frontend framework)
- **Model API:** HuggingFace Zeroscope-v2 via gradio_client

***


## Credits

Made by Kushal Panchali



