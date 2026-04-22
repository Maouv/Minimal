# main.py — FastAPI backend, entry point
# 12 endpoints. HTTP localhost port 4096.

import asyncio
import json
import subprocess
from contextlib import asynccontextmanager
from typing import AsyncIterator

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

import config
import session as session_store
import commands as cmd_parser
import coder
import llm
from schemas import (
    ConfigResponse, ProviderUpdateRequest,
    SessionCreateRequest, SessionListResponse, SessionMeta,
    PromptRequest, ContextAddRequest, ContextDropRequest, ContextListResponse,
)
from prompts import ask_system_prompt, edit_system_prompt


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.ensure()
    yield


app = FastAPI(title="minimal", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# --- Health ---

@app.get("/health")
async def health():
    return {"ok": True}


# --- Config ---

@app.get("/config")
async def get_config() -> ConfigResponse:
    return ConfigResponse(
        base_url=config.base_url(),
        model=config.model(),
        models=config.all_models(),
        context_window=config.context_window(),
        timeout=config.timeout(),
        max_tokens=config.max_tokens(),
    )


@app.post("/config/providers")
async def update_provider(req: ProviderUpdateRequest):
    return {"ok": True, "model": req.model}


@app.get("/project/current")
async def project_current():
    import os
    return {"path": os.getcwd()}


@app.get("/project/files")
async def project_files():
    """Walk CWD + home dir, return all files (skip hidden + noise dirs)."""
    import os
    from pathlib import Path

    SKIP_DIRS = {
        ".git", "__pycache__", "node_modules", ".venv", "venv",
        ".mypy_cache", ".ruff_cache", "dist", "build", ".next",
        ".nuxt", "target", ".cargo",
    }

    def walk(root: Path) -> list[str]:
        results: list[str] = []
        try:
            for entry in sorted(root.iterdir()):
                if entry.name.startswith(".") and entry.name not in {".env"}:
                    continue
                if entry.is_dir():
                    if entry.name in SKIP_DIRS:
                        continue
                    results.extend(walk(entry))
                elif entry.is_file():
                    results.append(str(entry.resolve()))
        except PermissionError:
            pass
        return results

    cwd = Path(os.getcwd())
    files: list[str] = walk(cwd)
    return {"files": files, "cwd": str(cwd)}


# --- Session ---

@app.post("/session")
async def create_session(req: SessionCreateRequest = SessionCreateRequest()):
    s = await session_store.create(model=None)
    return {"session_id": s.session_id, "model": s.model, "created_at": s.created_at}


@app.get("/session")
async def list_sessions():
    return SessionListResponse(sessions=[
        SessionMeta(**s) for s in session_store.list_all()
    ])


@app.get("/session/{session_id}")
async def get_session(session_id: str):
    s = await session_store.get_or_load(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session_id": s.session_id,
        "model": s.model,
        "created_at": s.created_at,
        "message_count": len(s.messages),
    }


@app.post("/session/{session_id}/abort")
async def abort_session(session_id: str):
    # TODO: cancel ongoing stream via asyncio task cancellation
    return {"ok": True}


# --- Context endpoints ---

@app.post("/context/add")
async def context_add(req: ContextAddRequest):
    s = await session_store.get_or_load(req.session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    err = await s.context.add(req.path, readonly=req.readonly)
    if err:
        raise HTTPException(status_code=400, detail=err)
    return {"files": [f.model_dump(mode="json") for f in s.context.ls()]}


@app.post("/context/drop")
async def context_drop(req: ContextDropRequest):
    s = await session_store.get_or_load(req.session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    err = s.context.drop(req.path)
    if err:
        raise HTTPException(status_code=400, detail=err)
    return {"files": [f.model_dump(mode="json") for f in s.context.ls()]}


@app.get("/context")
async def context_list(session_id: str):
    s = await session_store.get_or_load(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "files": [f.model_dump(mode="json") for f in s.context.ls()],
        "total_tokens": s.context.total_tokens(),
    }


# --- Prompt + SSE stream ---

@app.post("/session/{session_id}/init")
async def prompt(session_id: str, req: PromptRequest):
    s = await session_store.get_or_load(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")

    return StreamingResponse(
        _handle_prompt(s, req.content),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _handle_prompt(s, raw_input: str) -> AsyncIterator[str]:
    """Core prompt handler. Parse command, dispatch, stream response."""

    def sse(event_type: str, data: dict) -> str:
        return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"

    command = cmd_parser.parse(raw_input)

    # --- Non-LLM commands ---

    if command.kind == "add":
        # Support batch: /add file1 file2 file3 (spasi-separated)
        paths = command.args.split() if command.args else []
        if not paths:
            yield sse("error", {"message": "Usage: /add <file> [file2 ...]"})
            return
        errors = []
        for path in paths:
            err = await s.context.add(path, readonly=command.readonly)
            if err:
                errors.append(f"{path}: {err}")
        if errors:
            yield sse("error", {"message": "; ".join(errors)})
        files = s.context.ls()
        yield sse("context", {"files": [f.model_dump(mode="json") for f in files]})
        await s.write_command(raw_input)
        return

    if command.kind == "drop":
        err = s.context.drop(command.args)
        if err:
            yield sse("error", {"message": err})
        else:
            files = s.context.ls()
            yield sse("context", {"files": [f.model_dump(mode="json") for f in files]})
            await s.write_command(raw_input)
        return

    if command.kind == "clear":
        s.clear_messages()
        yield sse("clear", {})
        return

    if command.kind == "reset":
        s.clear_messages()
        s.context = __import__("context").ContextManager()
        yield sse("reset", {})
        return

    if command.kind == "tokens":
        yield sse("tokens", {
            "context_tokens": s.context.total_tokens(),
            "session_messages": len(s.messages),
        })
        return

    if command.kind == "model":
        s.model = config.resolve_model(command.args)
        yield sse("model", {"model": s.model})
        return

    if command.kind == "ask":
        s.mode = "ask"
        yield sse("mode", {"mode": "ask"})
        return

    if command.kind == "help":
        yield sse("text", {"content": cmd_parser.HELP_TEXT})
        return

    if command.kind == "undo":
        if not s.last_edit:
            yield sse("error", {"message": "Nothing to undo"})
            return
        for result in s.last_edit:
            coder.rollback(result)
        yield sse("undo", {"files": [r.file for r in s.last_edit]})
        s.last_edit = None
        return

    if command.kind == "diff":
        if not s.last_edit:
            yield sse("error", {"message": "No recent edit"})
            return
        diffs = [{"file": r.file, "diff": r.diff} for r in s.last_edit]
        yield sse("diff", {"diffs": diffs})
        return

    if command.kind == "commit":
        msg = command.args or "minimal: apply edits"
        try:
            subprocess.run(["git", "add", "-A"], capture_output=True, text=True)
            result = subprocess.run(
                ["git", "commit", "-m", msg],
                capture_output=True, text=True
            )
            yield sse("commit", {"output": result.stdout.strip()})
        except Exception as e:
            yield sse("error", {"message": str(e)})
        return

    if command.kind == "run":
        try:
            result = subprocess.run(
                command.args, shell=True,
                capture_output=True, text=True, timeout=30
            )
            output = (result.stdout + result.stderr).strip()
            yield sse("run", {"output": output, "returncode": result.returncode})
        except subprocess.TimeoutExpired:
            yield sse("error", {"message": "Command timed out (30s)"})
        except Exception as e:
            yield sse("error", {"message": str(e)})
        return

    # --- LLM calls (prompt + edit) ---

    is_edit = command.kind == "edit"

    if is_edit:
        if command.args:
            # /edit-block <prompt> — sekali pakai, mode tidak berubah
            effective_mode = command.edit_mode
        else:
            # /edit-block tanpa args — switch mode permanen
            s.mode = f"edit-{command.edit_mode}"
            yield sse("mode", {"mode": s.mode})
            return
    else:
        effective_mode = None
        if s.mode != "ask" and command.kind == "prompt":
            # Mode permanen aktif — pakai mode itu
            effective_mode = s.mode.replace("edit-", "")
            is_edit = True

    system_prompt = (
        edit_system_prompt(effective_mode, s.context.get_editable())
        if is_edit
        else ask_system_prompt(s.context.get_all())
    )

    messages = s.context.to_messages() + s.get_messages()
    messages.append({"role": "user", "content": command.args or raw_input})

    full_response = ""
    usage = None

    # heartbeat task — kirim ping setiap 2 detik selama stream aktif
    async def heartbeat():
        while True:
            await asyncio.sleep(2)
            yield sse("ping", {})

    heartbeat_task = asyncio.create_task(_run_heartbeat())

    try:
        async for token, u in llm.stream_chat(
            messages=messages,
            model=s.model,
            system_prompt=system_prompt,
        ):
            if token is not None:
                full_response += token
                yield sse("token", {"content": token})
            elif u is not None:
                usage = u

        # simpan ke history — hanya sekali, setelah stream selesai
        clean_response = llm.clean_for_history(full_response)
        s.add_message("user", command.args or raw_input)
        s.add_message("assistant", clean_response)
        await s.write_message("user", command.args or raw_input)
        await s.write_message("assistant", clean_response, {
            "input_tokens": usage.input_tokens if usage else 0,
            "output_tokens": usage.output_tokens if usage else 0,
        })

        # apply edit kalau mode edit
        if is_edit and clean_response:
            edit_results = coder.apply_edits(
                clean_response, s.context.get_editable(), effective_mode
            )

            for result in edit_results:
                if result.success:
                    written = coder.write_to_disk(result)
                    verified = coder.verify(result) if written else False

                    if verified:
                        await s.context.reload(result.file)
                        await s.write_edit(result.file, result.diff, True)
                        yield sse("edit", {
                            "file": result.file,
                            "diff": result.diff,
                            "success": True,
                        })
                    else:
                        coder.rollback(result)
                        await s.write_edit(result.file, result.diff, False)
                        yield sse("edit", {
                            "file": result.file,
                            "diff": "",
                            "success": False,
                            "error": "Edit failed verification — rolled back",
                        })
                else:
                    yield sse("error", {"message": result.error})

            s.last_edit = [r for r in edit_results if r.success]

        yield sse("done", {
            "input_tokens": usage.input_tokens if usage else 0,
            "output_tokens": usage.output_tokens if usage else 0,
        })

    except Exception as e:
        yield sse("error", {"message": str(e)})
    finally:
        heartbeat_task.cancel()


async def _run_heartbeat():
    """Dummy task untuk di-cancel saat stream selesai."""
    await asyncio.sleep(999999)


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=4096, reload=False)
