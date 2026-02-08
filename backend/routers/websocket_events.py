from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from video_processor import register_client, unregister_client

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

