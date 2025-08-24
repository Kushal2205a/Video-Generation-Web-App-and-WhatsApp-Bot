***

# Video Generation Web App

![Python](https://img.shields.io/badge/pythonapigginggenerator with async FastAPI backend, robust HuggingFace integration, and a clean browser interface.

***

## Overview

The Video Generation Web App enables users to generate short videos from prompts using the state-of-the-art [Zeroscope-v2](https://huggingface.co/hysts/zeroscope-v2) model on HuggingFace through Gradio’s Python client. With clear job tracking, robust file serving, and graceful fallback for quota/resource limits, it is designed for both demonstration and production environments.

***

## Features

- **Modern Responsive Frontend:** Pure HTML/CSS/JS, designed minimal and dark/light switch friendly
- **Async FastAPI Backend:** Handles video jobs, status polling, and secure downloads
- **Job Queue & Status:** Real-time job management and progress feedback for users
- **Video Storage:** Organized `/videos` dir for generated and placeholder outputs
- **Resource Fallback:** Switches to a mock video seamlessly if API quota is hit
- **Deployment Ready:** Secure secrets, `.env` never in git, deploys easily on Render, Railway, etc.

***

## Architecture

![Architecture](assets/VGWA_architecture.svg)


***

## Model Choice

- **Model Used:** `hysts/zeroscope-v2` (HuggingFace Space)
- **Why This Model?**  
  Zeroscope-v2 is a leading open-source text-to-video model hosted on HuggingFace.  
  - It accepts descriptive prompts and returns authentic, short videos.
  - Public API endpoints via `gradio_client` enable stable, fast integration and error handling.
  - The model is supported and well-documented for both research and production scenarios.

***

## API & Code Structure

| Endpoint                  | Method | Purpose                                 |
|---------------------------|--------|-----------------------------------------|
| `/`                       | GET    | Returns index.html                      |
| `/style.css`              | GET    | CSS file for UI                         |
| `/script.js`              | GET    | Minimalist frontend logic               |
| `/api/generate-video`     | POST   | Start video gen job, returns `job_id`   |
| `/api/status/{job_id}`    | GET    | Polls for job status/progress           |
| `/api/download/{job_id}`  | GET    | Streams finished video file to browser  |

- **Backend (`main.py`)**: Job manager, async task system, API endpoints, secure file handling, HuggingFace integration.
- **Frontend**: Plain HTML + CSS (Courier New), JS for async polling and download.

***

## Environment Variables & Security

**Keep secrets safe:**  
- `.env` is **excluded** from git (`.gitignore`).
- Locally, credentials (such as `HUGGINGFACE_TOKEN`) are loaded via python-dotenv.
- **Production:** Set environment variables using your deploy platform’s dashboard for secure usage.

**Sample `.env` (NOT in repo):**
```
HUGGINGFACE_TOKEN=hf_XXXXXXXXXXXXXXXX
```

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

6. **Access:**  
   Open [http://localhost:8000](http://localhost:8000) in your browser.

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
- **Storage:** Local `/videos` directory

***

## License

MIT

***

## Credits

Made by Kushal Panchali

***

*Minimal. Robust. Real-world ready.*

***

You can directly copy and adapt this. Place your architecture image as `VGWA_architecture.jpg` in the repo for best rendering on GitHub. Adjust any repo/user details or add further deployment/cloud/usage notes as needed!

[1](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/85803672/42540aad-9dd6-4e70-a356-ca1726d2338f/script.js)
[2](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/85803672/bd5601fc-894e-4e97-ac88-25a5aa906dd8/main.py)
[3](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/images/85803672/6453c7e6-8596-4a9c-82ee-85e9fd724a38/VGWA_architecture.jpg)
[4](https://img.shields.io/badge/python-v3.8+-blue.svg)
[5](https://img.shields.io/badge/flask-v2.0+-green.svg)
[6](https://img.shields.io/badge/google--api--python--clien)
