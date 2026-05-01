import asyncio
# session.py — session lifecycle + JSONL persistence
# Format JSONL seperti Claude Code. Append-only. Recovery dari korup.

import json
import uuid
import aiofiles
from pathlib import Path
from datetime import datetime, timezone
from context import ContextManager
import config


class Session:
    def __init__(self, session_id: str, model: str):
        self.session_id  = session_id
        self.model       = model
        self.active_task: "asyncio.Task | None" = None
        self.mode: str = "ask"   # ask | edit-block | edit-udiff | edit-whole
        self.created_at = datetime.now(timezone.utc)
        self.context = ContextManager()
        self.messages: list[dict] = []   # chat history (tanpa thinking)
        self.last_edit: list | None = None  # untuk /undo
        self.last_init_draft: str | None = None
        self.last_init_path:  str | None = None
        self._path = config.sessions_dir() / f"{session_id}.jsonl"

    # --- Persistence ---

    async def save_line(self, record: dict):
        """Append satu line ke JSONL."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, default=str) + "\n"
        async with aiofiles.open(self._path, "a", encoding="utf-8") as f:
            await f.write(line)

    async def write_meta(self):
        await self.save_line({
            "type": "meta",
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "model": self.model,
            "base_url": config.base_url(),
        })

    async def write_message(self, role: str, content: str, usage: dict | None = None):
        record: dict[str, object] = {
            "type": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if usage:
            record["usage"] = usage
        await self.save_line(record)

    async def write_edit(self, file: str, diff: str, success: bool):
        await self.save_line({
            "type": "edit",
            "file": file,
            "diff": diff,
            "success": success,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def write_command(self, command: str):
        await self.save_line({
            "type": "command",
            "content": command,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    # --- Message history ---

    def add_message(self, role: str, content: str):
        """Tambah ke in-memory history. Content harus sudah di-strip thinking."""
        self.messages.append({"role": role, "content": content})

    def get_messages(self) -> list[dict]:
        return list(self.messages)

    def clear_messages(self):
        self.messages = []

    # --- Load from disk ---

    @classmethod
    async def load(cls, session_id: str) -> "Session | None":
        """Load session dari JSONL. Skip lines yang korup."""
        # Cari di project-scoped dir dulu, fallback ke root sessions dir
        path = config.sessions_dir() / f"{session_id}.jsonl"
        if not path.exists():
            # Fallback: cari di semua subdir sessions
            from config import _CONFIG_DIR
            for candidate in (_CONFIG_DIR / "sessions").rglob(f"{session_id}.jsonl"):
                path = candidate
                break
        if not path.exists():
            return None

        lines = await _read_jsonl_safe(path)
        if not lines:
            return None

        meta = lines[0] if lines[0].get("type") == "meta" else {}
        model = meta.get("model", config.model())
        session = cls(session_id=session_id, model=model)
        session.created_at = datetime.fromisoformat(
            meta.get("created_at", datetime.now(timezone.utc).isoformat())
        )
        session._path = path

        for line in lines[1:]:
            t = line.get("type")
            if t in ("user", "assistant"):
                session.messages.append({
                    "role": t,
                    "content": line.get("content", ""),
                })

        return session


# --- Session registry ---

_sessions: dict[str, Session] = {}


async def create(model: str | None = None) -> Session:
    session_id = str(uuid.uuid4())[:8]
    m = model or config.model()
    session = Session(session_id=session_id, model=m)
    await session.write_meta()
    _sessions[session_id] = session
    return session


def get(session_id: str) -> Session | None:
    return _sessions.get(session_id)


async def get_or_load(session_id: str) -> Session | None:
    if session_id in _sessions:
        return _sessions[session_id]
    session = await Session.load(session_id)
    if session:
        _sessions[session_id] = session
    return session


def list_all() -> list[dict]:
    sessions_dir = config.sessions_dir()
    result = []
    for path in sorted(sessions_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True):
        session_id = path.stem
        try:
            first_line = path.read_text().split("\n")[0]
            meta = json.loads(first_line)
            result.append({
                "session_id": session_id,
                "created_at": meta.get("created_at"),
                "model": meta.get("model"),
            })
        except Exception:
            continue
    return result


# --- Helpers ---

async def _read_jsonl_safe(path: Path) -> list[dict]:
    """Read JSONL, skip lines yang korup."""
    async with aiofiles.open(path, "r", encoding="utf-8") as f:
        raw = await f.read()

    lines = []
    for line in raw.strip().split("\n"):
        if not line.strip():
            continue
        try:
            lines.append(json.loads(line))
        except json.JSONDecodeError:
            break

    return lines

