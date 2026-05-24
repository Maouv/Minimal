# api/prompt.py — POST /session/{id}/init, SSE helper, _handle_prompt

import asyncio
import json
import os
import subprocess
from pathlib import Path
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

import commands as cmd_parser
import config
import coder
import llm
import repo as repo_module
import prompts
import think as think_engine
from context import _estimate_tokens
from prompts import ask_system_prompt, edit_system_prompt
from schemas import PromptRequest
import session as session_store

router = APIRouter()


def sse(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


@router.post("/session/{session_id}/init")
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
        context_tokens = s.context.total_tokens()
        # Estimasi chat history tokens (semua messages di session)
        chat_tokens = sum(_estimate_tokens(m.get("content", "")) for m in s.messages)
        # Estimasi system prompt: ~200 token base + context overhead
        system_tokens = 200 + context_tokens // 10
        total = context_tokens + chat_tokens + system_tokens
        lines = [
            "Token usage (estimated):",
            f"  context files : {context_tokens:>7,}",
            f"  chat history  : {chat_tokens:>7,}  ({len(s.messages)} messages)",
            f"  system prompt : {system_tokens:>7,}",
            "  ─────────────────────",
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
            target = (
                Path(
                    s.last_init_path
                    or os.environ.get("MINIMAL_PROJECT_ROOT", os.getcwd())
                )
                / "MINIMAL.md"
            )
            target.write_text(s.last_init_draft, encoding="utf-8")
            yield sse("text", {"content": f"✓ Saved to {target}"})
            yield sse("done", {"input_tokens": 0, "output_tokens": 0})
            return

        # Resolve path — default project root (di-set launcher via env)
        root = Path(os.environ.get("MINIMAL_PROJECT_ROOT", os.getcwd()))
        if command.args:
            candidate = (root / command.args).resolve()
            try:
                candidate.relative_to(root)
                root = candidate
            except ValueError:
                yield sse("error", {"message": "Path di luar project."})
                yield sse("done", {"input_tokens": 0, "output_tokens": 0})
                return

        ctx = repo_module.scan(root)
        s.last_init_path = str(root)

        # Build context string (sama logic dengan _build_init_context di health.py)
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
        context_str = "\n".join(parts)

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
                yield sse(
                    "done",
                    {
                        "input_tokens": usage.input_tokens,
                        "output_tokens": usage.output_tokens,
                    },
                )
        return

    if command.kind == "ask":
        s.mode = "ask"
        yield sse("mode", {"mode": "ask"})
        return

    if command.kind == "think":
        # Switch to think mode permanently (stays until /ask or /edit-*)
        s.mode = "think"
        yield sse("mode", {"mode": "think"})

        prompt_text = command.args
        if not prompt_text:
            # No inline prompt — just switch mode, user types next message
            return

        budget = (
            think_engine.DEEP_BUDGET if command.think_deep
            else think_engine.DEFAULT_BUDGET
        )
        async for result in think_engine.run_think_loop(s, prompt_text, budget):
            if result.kind == "token":
                yield sse("token", {"content": result.payload["content"]})
            elif result.kind == "thinking":
                yield sse("thinking", {"content": result.payload["content"]})
            elif result.kind == "tool_start":
                yield sse("think_tool", {
                    "tool": result.payload["tool"],
                    "args": result.payload["args"],
                })
            elif result.kind == "tool_result":
                yield sse("think_tool_done", {
                    "tool": result.payload["tool"],
                    "error": result.payload.get("error"),
                })
            elif result.kind == "done":
                yield sse("done", {
                    "input_tokens": result.payload["input_tokens"],
                    "output_tokens": result.payload["output_tokens"],
                })
            elif result.kind == "error":
                yield sse("error", {"message": result.payload.get("message", "unknown error")})
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
                ["git", "commit", "-m", msg], capture_output=True, text=True
            )
            yield sse("commit", {"output": result.stdout.strip()})
        except Exception as e:
            yield sse("error", {"message": str(e)})
        return

    if command.kind == "run":
        try:
            result = subprocess.run(
                command.args, shell=True, capture_output=True, text=True, timeout=30
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
        if s.mode == "think" and command.kind == "prompt":
            # In think mode — plain prompt → run investigation
            budget = think_engine.DEFAULT_BUDGET
            async for result in think_engine.run_think_loop(s, raw_input, budget):
                if result.kind == "token":
                    yield sse("token", {"content": result.payload["content"]})
                elif result.kind == "thinking":
                    yield sse("thinking", {"content": result.payload["content"]})
                elif result.kind == "tool_start":
                    yield sse("think_tool", {
                        "tool": result.payload["tool"],
                        "args": result.payload["args"],
                    })
                elif result.kind == "tool_result":
                    yield sse("think_tool_done", {
                        "tool": result.payload["tool"],
                        "error": result.payload.get("error"),
                    })
                elif result.kind == "done":
                    yield sse("done", {
                        "input_tokens": result.payload["input_tokens"],
                        "output_tokens": result.payload["output_tokens"],
                    })
                elif result.kind == "error":
                    yield sse("error", {"message": result.payload.get("message", "unknown")})
            return
        elif s.mode != "ask" and command.kind == "prompt":
            # Edit mode permanen aktif — pakai mode itu
            effective_mode = s.mode.replace("edit-", "")
            is_edit = True

    system_prompt = (
        edit_system_prompt(effective_mode, s.context.get_editable())
        if is_edit and effective_mode is not None
        else ask_system_prompt(s.context.get_all())
    )

    messages = s.context.to_messages() + s.get_messages()
    messages.append({"role": "user", "content": command.args or raw_input})

    full_response = ""
    usage = None

    heartbeat_task = asyncio.create_task(_noop_cancellable())

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
        await s.write_message(
            "assistant",
            clean_response,
            {
                "input_tokens": usage.input_tokens if usage else 0,
                "output_tokens": usage.output_tokens if usage else 0,
            },
        )

        # apply edit kalau mode edit
        if is_edit and effective_mode is not None and clean_response:
            _editable = s.context.get_editable()
            edit_results = coder.apply_edits(clean_response, _editable, effective_mode)

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
                        yield sse(
                            "edit",
                            {
                                "file": result.file,
                                "diff": result.diff,
                                "success": True,
                            },
                        )
                    else:
                        coder.rollback(result)
                        await s.write_edit(result.file, result.diff, False)
                        failed_files.append(result.file)
                        yield sse(
                            "edit",
                            {
                                "file": result.file,
                                "diff": "",
                                "success": False,
                                "error": "Edit failed verification — rolled back",
                            },
                        )
                else:
                    failed_files.append(result.file or "?")
                    yield sse("error", {"message": result.error})

            s.last_edit = [r for r in edit_results if r.success]

            # Applied summary
            summary_parts = []
            if applied_files:
                files_str = ", ".join(f.split("/")[-1] for f in applied_files)
                summary_parts.append(
                    f"✓ Applied to {len(applied_files)} file(s): {files_str}"
                )
            if failed_files:
                files_str = ", ".join(f.split("/")[-1] for f in failed_files)
                summary_parts.append(f"✗ Failed: {files_str}")
            if summary_parts:
                yield sse(
                    "applied_summary",
                    {
                        "message": "\n".join(summary_parts),
                        "applied": applied_files,
                        "failed": failed_files,
                    },
                )

            # Follow-up turn — AI acknowledge hasil edit
            if applied_files or failed_files:
                async for chunk in _stream_edit_followup(
                    s, applied_files, failed_files
                ):
                    yield chunk

        yield sse(
            "done",
            {
                "input_tokens": usage.input_tokens if usage else 0,
                "output_tokens": usage.output_tokens if usage else 0,
            },
        )

    except Exception as e:
        yield sse("error", {"message": str(e)})
    finally:
        heartbeat_task.cancel()


async def _stream_edit_followup(
    s, applied_files: list[str], failed_files: list[str]
) -> AsyncIterator[str]:
    """
    Kirim follow-up turn ke AI setelah edits applied.
    AI harus acknowledge perubahan — fix masalah 'AI diam setelah edit'.
    Cost: ~100-200 extra output tokens, worth it untuk UX.
    """
    lines = ["[System] Edit results:"]
    for f in applied_files:
        lines.append(f"- {f.split('/')[-1]}: ✓ applied")
    for f in failed_files:
        lines.append(f"- {f.split('/')[-1]}: ✗ failed (SEARCH block tidak cocok)")
    lines.append("\nBriefly confirm what you changed and note any failures.")

    followup_messages = s.get_messages() + [
        {"role": "user", "content": "\n".join(lines)}
    ]

    followup_response = ""
    followup_usage = None

    async for token, u, thinking in llm.stream_chat(
        messages=followup_messages,
        model=s.model,
        system_prompt="",
    ):
        if thinking:
            yield sse("thinking", {"content": thinking})
        if token:
            followup_response += token
            yield sse("token", {"content": token})
        elif u:
            followup_usage = u

    if followup_response:
        clean = llm.clean_for_history(followup_response)
        s.add_message("assistant", clean)
        await s.write_message("assistant", clean, {
            "input_tokens": followup_usage.input_tokens if followup_usage else 0,
            "output_tokens": followup_usage.output_tokens if followup_usage else 0,
        })


async def _noop_cancellable():
    """Long-sleeping task used solely as a cancellable handle for stream abort."""
    await asyncio.sleep(999_999)
