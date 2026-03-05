"""
WebSocket endpoint for real-time alert streaming.

Single responsibility: accept WebSocket connections, keep them alive,
and remove them on disconnect. All broadcasting is handled by the
ConnectionManager — no event logic here.
"""

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.features.stream.manager import manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Stream"])


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Accept a WebSocket connection and hold it open until disconnect.

    Clients connect to ``ws://<host>/api/v1/ws`` and receive JSON
    alert payloads in real time whenever a rule fires.

    The connection is kept alive by waiting for any incoming message
    (ping/pong). If the client disconnects for any reason — network
    drop, tab close, server restart — the connection is cleanly removed
    from the active set without crashing the application.

    Args:
        websocket: Incoming WebSocket connection from the client.

    Returns:
        None
    """
    await manager.connect(websocket)
    try:
        while True:
            # Wait for any client message (acts as a keep-alive ping).
            # We don't process the content — clients may send anything.
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected normally.")
    except Exception as exc:
        logger.warning("WebSocket connection closed unexpectedly: %s", exc)
    finally:
        manager.disconnect(websocket)
