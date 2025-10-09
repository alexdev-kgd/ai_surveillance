from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from video_processor import register_client, unregister_client
from db import get_recent_events

router = APIRouter(tags=["WebSocket Events"])

@router.websocket("/ws/events")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    register_client(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"server received: {data}")
    except WebSocketDisconnect:
        unregister_client(websocket)

@router.get("/events/recent")
def recent_events():
    return get_recent_events(limit=50)
