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
    # switch model mid-session tidak perlu restart
    # model disimpan per-session, bukan global
    return {"ok": True, "model": req.model}


@app.get("/project/current")
async def project_current():
    import os
    return {"path": os.getcwd()}


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

    async def sse(event_type: str, data: dict) -> str:
        return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"

    async def ping_loop():
        """Heartbeat setiap 2 detik selama stream aktif."""
        while True:
            await asyncio.sleep(2)
            yield f"event: ping\ndata: {{}}\n\n"

    command = cmd_parser.parse(raw_input)

    # --- Non-LLM commands ---

    if command.kind == "add":
        err = await s.context.add(command.args, readonly=command.readonly)
        if err:
            yield await sse("error", {"message": err})
        else:
            files = s.context.ls()
            yield await sse("context", {"files": [f.model_dump() for f in files]})
            await s.write_command(raw_input)
        return

    if command.kind == "drop":
        err = s.context.drop(command.args)
        if err:
            yield await sse("error", {"message": err})
        else:
            files = s.context.ls()
            yield await sse("context", {"files": [f.model_dump() for f in files]})
            await s.write_command(raw_input)
        return

    if command.kind == "ls":
        files = s.context.ls()
        yield await sse("context", {
            "files": [f.model_dump() for f in files],
            "total_tokens": s.context.total_tokens(),
        })
        return

    if command.kind == "clear":
        s.clear_messages()
        yield await sse("clear", {})
        return

    if command.kind == "reset":
        s.clear_messages()
        s.context = __import__("context").ContextManager()
        yield await sse("reset", {})
        return

    if command.kind == "tokens":
        total_input = sum(m.get("usage", {}).get("input_tokens", 0) for m in s.messages if isinstance(m, dict))
        yield await sse("tokens", {
            "context_tokens": s.context.total_tokens(),
            "session_messages": len(s.messages),
        })
        return

    if command.kind == "model":
        s.model = config.resolve_model(command.args)
        yield await sse("model", {"model": s.model})
        return

    if command.kind == "help":
        yield await sse("text", {"content": cmd_parser.HELP_TEXT})
        return

    if command.kind == "undo":
        if not s.last_edit:
            yield await sse("error", {"message": "Nothing to undo"})
            return
        for result in s.last_edit:
            coder.rollback(result)
        yield await sse("undo", {"files": [r.file for r in s.last_edit]})
        s.last_edit = None
        return

    if command.kind == "diff":
        if not s.last_edit:
            yield await sse("error", {"message": "No recent edit"})
            return
        diffs = [{"file": r.file, "diff": r.diff} for r in s.last_edit]
        yield await sse("diff", {"diffs": diffs})
        return

    if command.kind == "commit":
        msg = command.args or "minimal: apply edits"
        try:
            result = subprocess.run(
                ["git", "add", "-A"],
                capture_output=True, text=True
            )
            result = subprocess.run(
                ["git", "commit", "-m", msg],
                capture_output=True, text=True
            )
            yield await sse("commit", {"output": result.stdout.strip()})
        except Exception as e:
            yield await sse("error", {"message": str(e)})
        return

    if command.kind == "run":
        try:
            result = subprocess.run(
                command.args, shell=True,
                capture_output=True, text=True, timeout=30
            )
            output = (result.stdout + result.stderr).strip()
            yield await sse("run", {"output": output, "returncode": result.returncode})
        except subprocess.TimeoutExpired:
            yield await sse("error", {"message": "Command timed out (30s)"})
        except Exception as e:
            yield await sse("error", {"message": str(e)})
        return

    # --- LLM calls (prompt + edit) ---

    is_edit = command.kind == "edit"
    system_prompt = (
        edit_system_prompt(command.edit_mode, s.context.get_editable())
        if is_edit
        else ask_system_prompt(s.context.get_all())
    )

    # build messages: context files + history + current input
    messages = s.context.to_messages() + s.get_messages()
    messages.append({"role": "user", "content": command.args or raw_input})

    await s.write_message("user", command.args or raw_input)

    # stream dengan heartbeat
    full_response = ""
    tokens: list[str] = []

    ping_task = asyncio.create_task(_heartbeat())

    try:
        def on_token(token: str):
            tokens.append(token)

        usage = await llm.stream_chat(
            messages=messages,
            model=s.model,
            on_token=on_token,
            system_prompt=system_prompt,
        )

        # flush tokens
        for token in tokens:
            full_response += token
            yield await sse("token", {"content": token})

        # strip thinking sebelum simpan ke history
        clean_response = llm.clean_for_history(full_response)
        s.add_message("user", command.args or raw_input)
        s.add_message("assistant", clean_response)
        await s.write_message("assistant", clean_response, {
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
        })

        # apply edit kalau mode edit
        if is_edit and clean_response:
            edit_results = coder.apply_edits(
                clean_response, s.context.get_editable(), command.edit_mode
            )

            for result in edit_results:
                if result.success:
                    written = coder.write_to_disk(result)
                    verified = coder.verify(result) if written else False

                    if verified:
                        s.context.reload(result.file)
                        await s.write_edit(result.file, result.diff, True)
                        yield await sse("edit", {
                            "file": result.file,
                            "diff": result.diff,
                            "success": True,
                        })
                    else:
                        coder.rollback(result)
                        await s.write_edit(result.file, result.diff, False)
                        yield await sse("edit", {
                            "file": result.file,
                            "diff": "",
                            "success": False,
                            "error": "Edit failed verification — rolled back",
                        })
                else:
                    yield await sse("error", {"message": result.error})

            s.last_edit = [r for r in edit_results if r.success]

        yield await sse("done", {
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
        })

    except Exception as e:
        yield await sse("error", {"message": str(e)})
    finally:
        ping_task.cancel()


async def _heartbeat():
    """Dummy task — heartbeat dikirim via SSE ping di loop utama."""
    await asyncio.sleep(999999)


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=4096, reload=False)

