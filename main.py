from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.routes import web, whatsapp

app = FastAPI(title="AI Video Generator API")

# Mount static frontend
app.mount("/static", StaticFiles(directory="static"), name="static")

# Attach routers
app.include_router(web.router)
app.include_router(whatsapp.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
