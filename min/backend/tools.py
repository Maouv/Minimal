# tools.py — tool execution for /think agent loop
# Each tool returns (output: str, error: str | None).
# All tools are sandboxed to project root. No path traversal outside root.

import subprocess
from pathlib import Path


PROJECT_ROOT = Path(".").resolve()

# Cap output sizes — tools talking to LLM must not blow context
_MAX_OUTPUT_CHARS = 8_000
_MAX_FILE_CHARS = 6_000


def _safe_path(raw: str) -> Path | None:
    """
    Resolve path relative to PROJECT_ROOT.
    Return None kalau path traversal ke luar root.
    """
    try:
        p = (PROJECT_ROOT / raw).resolve()
        p.relative_to(PROJECT_ROOT)  # raises ValueError if outside
        return p
    except (ValueError, Exception):
        return None


def _truncate(text: str, limit: int = _MAX_OUTPUT_CHARS) -> str:
    if len(text) <= limit:
        return text
    head = text[:limit]
    return head + f"\n… [truncated, {len(text) - limit} chars omitted]"


def tool_read_file(path: str, lines: str | None = None) -> tuple[str, str | None]:
    """
    Read file content. Optional `lines` = "start-end" (1-indexed, inclusive).
    Returns (content, error).
    """
    p = _safe_path(path)
    if p is None:
        return "", f"Path traversal blocked or invalid: {path}"
    if not p.exists():
        return "", f"File not found: {path}"
    if not p.is_file():
        return "", f"Not a file: {path}"

    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return "", f"Cannot read {path}: {e}"

    if lines:
        text = _slice_lines(text, lines)

    return _truncate(text, _MAX_FILE_CHARS), None


def _slice_lines(text: str, spec: str) -> str:
    """Parse "start-end" or "start" and slice lines (1-indexed)."""
    all_lines = text.splitlines(keepends=True)
    total = len(all_lines)
    try:
        if "-" in spec:
            parts = spec.split("-", 1)
            start = max(1, int(parts[0])) - 1
            end = min(total, int(parts[1]))
        else:
            start = max(1, int(spec)) - 1
            end = min(total, start + 50)  # default: 50 lines from start
    except ValueError:
        return text  # bad spec → return full file
    sliced = all_lines[start:end]
    header = f"[Lines {start + 1}–{end} of {total}]\n"
    return header + "".join(sliced)


def tool_run(cmd: str) -> tuple[str, str | None]:
    """
    Execute shell command in PROJECT_ROOT. Timeout 10s.
    Returns (stdout+stderr, error).
    """
    if not cmd.strip():
        return "", "Empty command"
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=10,
        )
        combined = (result.stdout + result.stderr).strip()
        return _truncate(combined), None
    except subprocess.TimeoutExpired:
        return "", "Command timed out (10s)"
    except Exception as e:
        return "", str(e)


def tool_grep(pattern: str, path: str) -> tuple[str, str | None]:
    """
    grep -rn pattern in path. Bounded to PROJECT_ROOT.
    Returns (matches, error).
    """
    p = _safe_path(path)
    if p is None:
        return "", f"Path traversal blocked or invalid: {path}"

    try:
        result = subprocess.run(
            ["grep", "-rn", "--color=never", pattern, str(p)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        output = (result.stdout + result.stderr).strip()
        return _truncate(output), None
    except subprocess.TimeoutExpired:
        return "", "grep timed out (10s)"
    except Exception as e:
        return "", str(e)


def tool_ls(path: str, depth: int = 1) -> tuple[str, str | None]:
    """
    List directory contents up to `depth` levels.
    Returns (tree, error).
    """
    p = _safe_path(path)
    if p is None:
        return "", f"Path traversal blocked or invalid: {path}"
    if not p.exists():
        return "", f"Path not found: {path}"

    depth = max(1, min(depth, 4))  # cap at 4 to avoid huge output
    lines: list[str] = []
    _walk(p, depth, 0, lines)
    return _truncate("\n".join(lines)), None


def _walk(root: Path, max_depth: int, current: int, lines: list[str]) -> None:
    indent = "  " * current
    try:
        entries = sorted(root.iterdir(), key=lambda e: (e.is_file(), e.name))
    except PermissionError:
        return
    for entry in entries:
        if entry.name.startswith(".") and entry.name not in (".env",):
            continue  # skip hidden except .env
        marker = "" if entry.is_dir() else ""
        lines.append(f"{indent}{marker}{entry.name}")
        if entry.is_dir() and current < max_depth - 1:
            _walk(entry, max_depth, current + 1, lines)
