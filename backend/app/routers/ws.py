from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.ws_manager import manager
from app.core.security import decode_access_token
from app.services.user_service import get_user
from app.core.database import SessionLocal

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # token expected in query string: /ws?token=<jwt>
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008)
        return

    try:
        subject = decode_access_token(token)
        if not subject.isdigit():
            await websocket.close(code=1008)
            return
        user_id = int(subject)
    except Exception:
        await websocket.close(code=1008)
        return

    # validate user exists and active
    db = SessionLocal()
    try:
        user = get_user(db, user_id)
        if not user or not user.is_active:
            await websocket.close(code=1008)
            return
    finally:
        db.close()

    await manager.connect(user_id, websocket)
    try:
        # keep connection open; receive text to detect disconnects/pings
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(user_id, websocket)
    except Exception:
        manager.disconnect(user_id, websocket)
