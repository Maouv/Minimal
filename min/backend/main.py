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
import os
from pathlib import Path


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


# --- Repo ---

@app.post("/repo/map")
async def repo_map(req: dict):
    """
    Scan repo dari path tertentu dan return RepoContext.
    Body: { path?: string }  — default CWD
    Security: path di-resolve relatif ke CWD, tolak kalau keluar CWD.
    """
    import repo as repo_module

    cwd = Path(os.getcwd())
    raw_path = req.get("path", "").strip()
    if raw_path:
        candidate = (cwd / raw_path).resolve()
        try:
            candidate.relative_to(cwd)
        except ValueError:
            raise HTTPException(status_code=400, detail="Path outside CWD")
        root = candidate
    else:
        root = cwd

    ctx = repo_module.scan(root)
    return ctx.__dict__


def _build_init_context(ctx) -> str:
    parts = []

    if ctx.minimal_mds:
        parts.append("=== EXISTING MINIMAL.md ===")
        for md in ctx.minimal_mds:
            parts.append(f"--- {md['path']} (depth {md['depth']}) ---")
            parts.append(md["content"])

    if ctx.repo_tags:
        parts.append("=== @repo: TAGS ===")
        for entry in ctx.repo_tags:
            for tag in entry["tags"]:
                parts.append(f"{entry['file']}: {tag}")

    if ctx.symbols:
        parts.append("=== REPO MAP ===")
        for entry in ctx.symbols:
            syms = ", ".join(entry["symbols"])
            parts.append(f"{entry['file']}: {syms}")

    if ctx.manifests:
        parts.append("=== MANIFESTS ===")
        for m in ctx.manifests:
            parts.append(f"--- {m['file']} ---")
            parts.append(m["content"])

    return "\n".join(parts)


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


@app.get("/providers")
async def list_providers():
    """Return semua providers yang sudah disimpan."""
    return {"providers": config.load_providers()}


@app.post("/providers/probe")
async def probe_provider(req: dict):
    """
    Probe /v1/models dari base_url + api_key.
    api_key "__from_env__" → pakai API key dari .env (untuk existing provider).
    Lookup by provider_name dulu (jika dikirim), fallback ke base_url.
    """
    from probe_models import probe
    base_url = req.get("base_url", "").strip()
    api_key = req.get("api_key", "").strip()
    provider_name = req.get("provider_name", "").strip()
    if not base_url or not api_key:
        raise HTTPException(status_code=400, detail="base_url and api_key required")
    # Resolve __from_env__ ke actual key
    if api_key == "__from_env__":
        providers = config.load_providers()
        # Prioritaskan lookup by name, fallback ke base_url
        provider = None
        if provider_name:
            provider = next((p for p in providers if p["name"] == provider_name), None)
        if not provider:
            provider = next((p for p in providers if p["base_url"] == base_url), None)
        if provider:
            import os
            api_key = os.getenv(provider["env_key"], config.api_key())
        else:
            api_key = config.api_key()
    result = await probe(base_url, api_key)
    return result


@app.post("/providers/add")
async def add_provider(req: dict):
    """
    Tambah provider baru + simpan API key ke .env.
    Body: { name, base_url, api_key }
    """
    name = req.get("name", "").strip()
    base_url = req.get("base_url", "").strip()
    api_key = req.get("api_key", "").strip()
    if not name or not base_url or not api_key:
        raise HTTPException(status_code=400, detail="name, base_url, api_key required")
    entry = config.add_provider(name, base_url, api_key)
    return {"ok": True, "provider": entry}


@app.post("/providers/switch")
async def switch_model(req: dict):
    """
    Switch active provider + model.
    Body: { provider_name, model_id }
    Update LLM_BASE_URL, LLM_API_KEY, LLM_MODEL di .env dan reload.
    """
    provider_name = req.get("provider_name", "").strip()
    model_id = req.get("model_id", "").strip()
    if not provider_name or not model_id:
        raise HTTPException(status_code=400, detail="provider_name and model_id required")

    providers = config.load_providers()
    provider = next((p for p in providers if p["name"] == provider_name), None)
    if not provider:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_name}' not found")

    config.switch_provider_model(provider, model_id)
    return {"ok": True, "model": model_id, "base_url": provider["base_url"]}


@app.get("/project/current")
async def project_current():
    import os
    return {"path": os.getcwd()}


@app.get("/project/files")
async def project_files():
    """Walk CWD, return all files only (skip hidden + noise dirs)."""
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


@app.get("/project/entries")
async def project_entries(path: str = ""):
    """
    List immediate children (files + dirs) di path tertentu.
    Default: CWD. Dipakai untuk autocomplete drill-down.
    Returns: { entries: [{name, path, is_dir}], cwd }
    """
    import os
    from pathlib import Path

    SKIP_DIRS = {
        ".git", "__pycache__", "node_modules", ".venv", "venv",
        ".mypy_cache", ".ruff_cache", "dist", "build", ".next",
        ".nuxt", "target", ".cargo",
    }

    cwd = Path(os.getcwd())
    target = (cwd / path).resolve() if path else cwd

    # Security: jangan keluar dari CWD
    try:
        target.relative_to(cwd)
    except ValueError:
        raise HTTPException(status_code=400, detail="Path outside CWD")

    if not target.is_dir():
        raise HTTPException(status_code=400, detail="Not a directory")

    entries = []
    try:
        for entry in sorted(target.iterdir()):
            if entry.name.startswith(".") and entry.name not in {".env"}:
                continue
            if entry.is_dir() and entry.name in SKIP_DIRS:
                continue
            rel = str(entry.relative_to(cwd))
            entries.append({
                "name": entry.name + ("/" if entry.is_dir() else ""),
                "path": rel + ("/" if entry.is_dir() else ""),
                "is_dir": entry.is_dir(),
            })
    except PermissionError:
        pass

    return {"entries": entries, "cwd": str(cwd)}


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
    s = await session_store.get_or_load(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    if s.active_task and not s.active_task.done():
        s.active_task.cancel()
        return {"ok": True, "aborted": True}
    return {"ok": True, "aborted": False}


@app.patch("/session/{session_id}/model")
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

    async def _stream_with_task():
        task = asyncio.current_task()
        s.active_task = task
        try:
            async for chunk in _handle_prompt(s, req.content):
                yield chunk
        except asyncio.CancelledError:
            yield sse("error", {"message": "aborted"})
            yield sse("done", {"input_tokens": 0, "output_tokens": 0})
        finally:
            s.active_task = None

    return StreamingResponse(
        _stream_with_task(),
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
        from context import _estimate_tokens
        context_tokens = s.context.total_tokens()
        # Estimasi chat history tokens (semua messages di session)
        chat_tokens = sum(
            _estimate_tokens(m.get("content", ""))
            for m in s.messages
        )
        # Estimasi system prompt: ~200 token base + context overhead
        system_tokens = 200 + context_tokens // 10
        total = context_tokens + chat_tokens + system_tokens
        lines = [
            "Token usage (estimated):",
            f"  context files : {context_tokens:>7,}",
            f"  chat history  : {chat_tokens:>7,}  ({len(s.messages)} messages)",
            f"  system prompt : {system_tokens:>7,}",
            f"  ─────────────────────",
            f"  total         : {total:>7,}",
        ]
        yield sse("text", {"content": "\n".join(lines)})
        return

    if command.kind == "model":
        s.model = config.resolve_model(command.args)
        yield sse("model", {"model": s.model})
        return

    if command.kind == "init":

        if command.args == "--save":
            if not s.last_init_draft:
                yield sse("error", {"message": "Tidak ada draft. Jalankan /init dulu."})
                yield sse("done", {"input_tokens": 0, "output_tokens": 0})
                return
            target = Path(s.last_init_path or os.getcwd()) / "MINIMAL.md"
            target.write_text(s.last_init_draft, encoding="utf-8")
            yield sse("text", {"content": f"✓ Saved to {target}"})
            yield sse("done", {"input_tokens": 0, "output_tokens": 0})
            return

        # Resolve path — default CWD
        root = Path(os.getcwd())
        if command.args:
            candidate = (root / command.args).resolve()
            try:
                candidate.relative_to(root)
                root = candidate
            except ValueError:
                yield sse("error", {"message": "Path di luar project."})
                yield sse("done", {"input_tokens": 0, "output_tokens": 0})
                return

        import repo as repo_module
        ctx = repo_module.scan(root)
        s.last_init_path = str(root)

        context_str = _build_init_context(ctx)
        import prompts
        system = prompts.init_system()
        messages = [{"role": "user", "content": context_str}]

        full_response = ""
        async for token, usage, thinking in llm.stream_chat(messages, s.model, system):
            if thinking:
                yield sse("thinking", {"content": thinking})
            if token:
                full_response += token
                yield sse("token", {"content": token})
            if usage:
                s.last_init_draft = full_response
                yield sse("done", {
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                })
        return

    if command.kind == "ask":
        s.mode = "ask"
        yield sse("mode", {"mode": "ask"})
        return

    if command.kind == "help":
        yield sse("text", {"content": cmd_parser.HELP_TEXT})
        return

    if command.kind == "exit":
        yield sse("exit", {})
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
    heartbeat_task = asyncio.create_task(_run_heartbeat())

    try:
        async for token, u, thinking in llm.stream_chat(
            messages=messages,
            model=s.model,
            system_prompt=system_prompt,
        ):
            if thinking is not None:
                yield sse("thinking", {"content": thinking})
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

            applied_files = []
            failed_files = []

            for result in edit_results:
                if result.success:
                    written = coder.write_to_disk(result)
                    verified = coder.verify(result) if written else False

                    if verified:
                        await s.context.reload(result.file)
                        await s.write_edit(result.file, result.diff, True)
                        applied_files.append(result.file)
                        yield sse("edit", {
                            "file": result.file,
                            "diff": result.diff,
                            "success": True,
                        })
                    else:
                        coder.rollback(result)
                        await s.write_edit(result.file, result.diff, False)
                        failed_files.append(result.file)
                        yield sse("edit", {
                            "file": result.file,
                            "diff": "",
                            "success": False,
                            "error": "Edit failed verification — rolled back",
                        })
                else:
                    failed_files.append(result.file or "?")
                    yield sse("error", {"message": result.error})

            s.last_edit = [r for r in edit_results if r.success]

            # Applied summary — ringkasan apa yang berubah
            summary_parts = []
            if applied_files:
                files_str = ", ".join(f.split("/")[-1] for f in applied_files)
                summary_parts.append(f"✓ Applied to {len(applied_files)} file(s): {files_str}")
            if failed_files:
                files_str = ", ".join(f.split("/")[-1] for f in failed_files)
                summary_parts.append(f"✗ Failed: {files_str}")
            if summary_parts:
                yield sse("applied_summary", {"message": "\n".join(summary_parts), "applied": applied_files, "failed": failed_files})

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
