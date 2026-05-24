# think.py — /think agent loop
# Agentic investigation: AI bisa baca file, run command, grep, ls.
# Tidak edit file. Output = analisis + rekomendasi.
# Budget system: warn at 50%/25%/10%, hard stop at 0%.

import json
import re
from dataclasses import dataclass
from typing import AsyncIterator

import llm
from context import _estimate_tokens
from prompts.loader import load_prompt
from tools import tool_grep, tool_ls, tool_read_file, tool_run

# ── Constants ──────────────────────────────────────────────────────────────────

DEFAULT_BUDGET = 20_000   # output tokens
DEEP_BUDGET    = 50_000

_WARN_THRESHOLDS = [
    (0.50, "50% of your token budget remains. Stay focused."),
    (0.25, "25% of your token budget remains. Start forming your conclusion."),
    (0.10, "Almost out of budget. Conclude now."),
]

# After this many tool iterations, compress prior results to save context.
_SUMMARIZE_EVERY = 4

# ── Dataclasses ────────────────────────────────────────────────────────────────


@dataclass
class ToolCall:
    name: str
    args: dict


@dataclass
class ThinkResult:
    """Yielded by run_think_loop for each streaming event."""
    kind: str   # "token" | "thinking" | "tool_start" | "tool_result" | "done" | "error"
    payload: dict


# ── Tool XML parser ────────────────────────────────────────────────────────────

_TOOL_RE = re.compile(
    r"<tool>\s*(\w+)\s*</tool>\s*<args>(.*?)</args>",
    re.DOTALL,
)


def parse_tool_calls(text: str) -> list[ToolCall]:
    """Extract all <tool>/<args> pairs from AI response text."""
    calls = []
    for match in _TOOL_RE.finditer(text):
        name = match.group(1).strip()
        raw_args = match.group(2).strip()
        try:
            args = json.loads(raw_args)
        except json.JSONDecodeError:
            args = {"raw": raw_args}
        calls.append(ToolCall(name=name, args=args))
    return calls


def strip_tool_blocks(text: str) -> str:
    """Remove <tool>/<args> blocks from text before streaming to user."""
    return _TOOL_RE.sub("", text).strip()


# ── Tool dispatcher ────────────────────────────────────────────────────────────


def dispatch_tool(call: ToolCall) -> tuple[str, str | None]:
    """
    Execute one tool call. Return (output, error).
    Unknown tools return an error string — not a crash.
    """
    name = call.name
    args = call.args

    if name == "read_file":
        return tool_read_file(args.get("path", ""), args.get("lines"))
    if name == "run":
        return tool_run(args.get("cmd", ""))
    if name == "grep":
        return tool_grep(args.get("pattern", ""), args.get("path", "."))
    if name == "ls":
        return tool_ls(args.get("path", "."), int(args.get("depth", 1)))

    return "", f"Unknown tool: {name}"


# ── Budget helpers ─────────────────────────────────────────────────────────────


def _budget_warning(used: int, budget: int) -> str | None:
    """Return warning message if we just crossed a threshold, else None."""
    if budget <= 0:
        return None
    ratio_remaining = 1.0 - (used / budget)
    for threshold, msg in _WARN_THRESHOLDS:
        # Fire when remaining drops below threshold — check with 5% hysteresis
        prev_ratio = 1.0 - ((used - 200) / budget)  # approx previous
        if ratio_remaining < threshold <= prev_ratio:
            return f"[System: {msg}]"
    return None


def _over_budget(used: int, budget: int) -> bool:
    return used >= budget


# ── Progressive summarization ──────────────────────────────────────────────────


def _compress_tool_results(messages: list[dict]) -> list[dict]:
    """
    Compress accumulated tool result messages into a single summary message.
    Keeps the initial system + user messages untouched.
    Tool result messages = role "user" with content starting with "[Tool result:".
    """
    head = []
    tool_parts = []

    for msg in messages:
        if msg["role"] == "user" and msg["content"].startswith("[Tool result:"):
            tool_parts.append(msg["content"])
        else:
            head.append(msg)

    if not tool_parts:
        return messages

    summary_lines = ["[System summary of investigation so far]:"]
    for part in tool_parts:
        # Take first 200 chars of each tool result as a summary entry
        first_line = part.split("\n")[0]
        summary_lines.append(f"  • {first_line[:200]}")
    summary_lines.append("\nContinue investigating or conclude.")

    compressed = head + [{"role": "user", "content": "\n".join(summary_lines)}]
    return compressed


# ── Main agent loop ────────────────────────────────────────────────────────────


async def run_think_loop(
    session,
    prompt: str,
    budget: int = DEFAULT_BUDGET,
) -> AsyncIterator[ThinkResult]:
    """
    Core agent loop for /think mode.

    Yields ThinkResult events:
      - "token"       → text token to display
      - "thinking"    → reasoning content (dimmed)
      - "tool_start"  → AI is about to call a tool
      - "tool_result" → tool executed, result injected
      - "done"        → finished, payload has token counts
      - "error"       → something broke
    """
    system = load_prompt("think")

    # Seed context: existing context files if any
    context_msgs = session.context.to_messages()
    history = session.get_messages()

    messages: list[dict] = context_msgs + history + [
        {"role": "user", "content": prompt}
    ]

    total_output_tokens = 0
    total_input_tokens = 0
    iteration = 0

    while not _over_budget(total_output_tokens, budget):
        # Inject budget warning if needed
        warn = _budget_warning(total_output_tokens, budget)
        if warn:
            messages.append({"role": "user", "content": warn})

        # Stream one AI turn
        full_response = ""
        turn_usage = None

        async for token, usage, thinking in llm.stream_chat(
            messages=messages,
            model=session.model,
            system_prompt=system,
        ):
            if thinking is not None:
                yield ThinkResult("thinking", {"content": thinking})

            if token is not None:
                full_response += token
                # Only stream tokens that are not inside a tool block
                visible = _visible_token(full_response, token)
                if visible:
                    yield ThinkResult("token", {"content": visible})

            elif usage is not None:
                turn_usage = usage

        if turn_usage:
            total_output_tokens += turn_usage.output_tokens
            total_input_tokens += turn_usage.input_tokens

        # Budget hard stop
        if _over_budget(total_output_tokens, budget):
            yield ThinkResult("token", {
                "content": "\n\n[Budget exhausted — investigation stopped.]"
            })
            break

        # Parse tool calls from full response
        tool_calls = parse_tool_calls(full_response)

        if not tool_calls:
            # AI self-terminated — done
            break

        # Add AI response to messages (strip tool blocks for cleanliness)
        clean_response = strip_tool_blocks(full_response)
        if clean_response:
            messages.append({"role": "assistant", "content": clean_response})

        # Execute each tool call, inject results
        for call in tool_calls:
            yield ThinkResult("tool_start", {
                "tool": call.name,
                "args": call.args,
            })

            output, error = dispatch_tool(call)

            if error:
                result_text = f"[Tool result: {call.name}]\nError: {error}"
            else:
                result_text = f"[Tool result: {call.name}]\n{output}"

            yield ThinkResult("tool_result", {
                "tool": call.name,
                "output": output,
                "error": error,
            })

            messages.append({"role": "user", "content": result_text})

            # Rough token estimate for tool result
            total_output_tokens += _estimate_tokens(result_text) // 4

        iteration += 1

        # Progressive summarization
        if iteration % _SUMMARIZE_EVERY == 0:
            messages = _compress_tool_results(messages)

    # Persist final response to session history
    final_content = llm.clean_for_history(full_response)
    if final_content:
        session.add_message("user", prompt)
        session.add_message("assistant", final_content)
        await session.write_message("user", prompt)
        await session.write_message(
            "assistant",
            final_content,
            {
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
            },
        )

    yield ThinkResult("done", {
        "input_tokens": total_input_tokens,
        "output_tokens": total_output_tokens,
    })


# ── Streaming helper — hide tool blocks from user output ──────────────────────

_IN_TOOL = False
_TOOL_OPEN = "<tool>"
_ARGS_CLOSE = "</args>"


def _visible_token(accumulated: str, token: str) -> str:
    """
    Return the visible portion of `token` (strip tool XML from user stream).
    Stateless approximation: if the accumulated response contains an unclosed
    <tool> block, suppress tokens until </args> is closed.
    Simple but sufficient — tool calls are on their own lines.
    """
    # Count open vs closed tool blocks in full accumulated text
    open_count = accumulated.count(_TOOL_OPEN)
    close_count = accumulated.count(_ARGS_CLOSE)

    if open_count > close_count:
        # We are inside a tool block — suppress this token
        return ""

    # Token is after a completed tool block — but might be part of the
    # closing tag itself. Return token unless it's part of the XML.
    if any(tag in token for tag in ("<tool>", "</tool>", "<args>", "</args>")):
        return ""

    return token
