# api/context.py — POST /context/add, POST /context/drop, GET /context

from fastapi import APIRouter, HTTPException

import session as session_store
from schemas import ContextAddRequest, ContextDropRequest

router = APIRouter()


@router.post("/context/add")
async def context_add(req: ContextAddRequest):
    s = await session_store.get_or_load(req.session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    err = await s.context.add(req.path, readonly=req.readonly)
    if err:
        raise HTTPException(status_code=400, detail=err)
    return {"files": [f.model_dump(mode="json") for f in s.context.ls()]}


@router.post("/context/drop")
async def context_drop(req: ContextDropRequest):
    s = await session_store.get_or_load(req.session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    err = s.context.drop(req.path)
    if err:
        raise HTTPException(status_code=400, detail=err)
    return {"files": [f.model_dump(mode="json") for f in s.context.ls()]}


@router.get("/context")
async def context_list(session_id: str):
    s = await session_store.get_or_load(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "files": [f.model_dump(mode="json") for f in s.context.ls()],
        "total_tokens": s.context.total_tokens(),
    }
