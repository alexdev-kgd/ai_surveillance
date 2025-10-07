from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import analyze_video, websocket_events, websocket_video

app = FastAPI(title="AI Surveillance System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(analyze_video.router)
app.include_router(websocket_events.router)
app.include_router(websocket_video.router)

@app.get("/")
def root():
    return {"status": "AI surveillance backend running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
