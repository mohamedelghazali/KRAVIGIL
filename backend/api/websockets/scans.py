import logging
from fastapi import WebSocket, WebSocketDisconnect, Query, Depends
from backend.api.websockets.manager import manager
from backend.core.security import security_service
from backend.database.models.user import User
from backend.database.session import SessionLocal
from sqlalchemy import text

logger = logging.getLogger(__name__)

async def scan_websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    try:
        payload = security_service.decode_token(token)
        user_id = payload.get("sub")
        tenant_id = payload.get("tenant")
        
        if not user_id or not tenant_id:
            await websocket.close(code=1008, reason="Invalid token")
            return
            
        await manager.connect(websocket, tenant_id)
        
        try:
            while True:
                data = await websocket.receive_text()
                if data == "ping":
                    await websocket.send_text("pong")
        except WebSocketDisconnect:
            manager.disconnect(websocket, tenant_id)
            
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.close(code=1011, reason="Internal error")
        except:
            pass
