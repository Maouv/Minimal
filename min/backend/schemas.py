# schemas.py — Pydantic models untuk semua request/response

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


# --- Config ---

class ConfigResponse(BaseModel):
    base_url: str
    model: str
    models: dict[str, str]
    context_window: int
    timeout: int
    max_tokens: int


class ProviderUpdateRequest(BaseModel):
    model: str


# --- Session ---

class SessionCreateRequest(BaseModel):
    model: Optional[str] = None


class SessionMeta(BaseModel):
    session_id: str
    created_at: Optional[str] = None
    model: Optional[str] = None


class SessionListResponse(BaseModel):
    sessions: list[SessionMeta]


# --- Prompt ---

class PromptRequest(BaseModel):
    content: str


# --- Context ---

class ContextFile(BaseModel):
    path: str
    readonly: bool
    token_count: int
    last_modified: datetime


class ContextAddRequest(BaseModel):
    session_id: str
    path: str
    readonly: bool = False


class ContextDropRequest(BaseModel):
    session_id: str
    path: str


class ContextListResponse(BaseModel):
    files: list[ContextFile]
    total_tokens: int
