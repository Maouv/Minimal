# api/sessions.py — POST /session, GET /session, GET /session/{id},
#                   POST /session/{id}/abort, PATCH /session/{id}/model

from fastapi import APIRouter, HTTPException

import session as session_store
from schemas import SessionCreateRequest, SessionListResponse, SessionMeta

router = APIRouter()


@router.post("/session")
async def create_session(req: SessionCreateRequest = SessionCreateRequest()):
    s = await session_store.create(model=None)
    return {"session_id": s.session_id, "model": s.model, "created_at": s.created_at}


@router.get("/session")
async def list_sessions():
    return SessionListResponse(
        sessions=[SessionMeta(**s) for s in session_store.list_all()]
    )


@router.get("/session/{session_id}")
async def get_session(session_id: str):
    s = await session_store.get_or_load(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session_id": s.session_id,
        "model": s.model,
        "created_at": s.created_at,
        "message_count": len(s.messages),
        "messages": [{"role": m["role"], "content": m["content"]} for m in s.messages],
    }


@router.post("/session/{session_id}/abort")
async def abort_session(session_id: str):
    s = await session_store.get_or_load(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    if s.active_task and not s.active_task.done():
        s.active_task.cancel()
        return {"ok": True, "aborted": True}
    return {"ok": True, "aborted": False}


@router.patch("/session/{session_id}/model")
async def update_session_model(session_id: str, req: dict):
    """
    Sync model ke session setelah /model-add atau provider switch dari TUI.
    Body: { model: string }
    """
    s = await session_store.get_or_load(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    model_id = req.get("model", "").strip()
    if not model_id:
        raise HTTPException(status_code=400, detail="model required")
    s.model = model_id
    return {"ok": True, "model": s.model}
