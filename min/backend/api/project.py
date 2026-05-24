# api/project.py — GET /project/current, /project/files, /project/dirs, /project/entries

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter()

# Directories skipped when walking project tree
_SKIP_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "build",
    ".next",
    ".nuxt",
    "target",
    ".cargo",
}


@router.get("/project/current")
async def project_current():
    return {"path": os.getcwd()}


@router.get("/project/files")
async def project_files():
    """Walk CWD, return all files only (skip hidden + noise dirs)."""

    def walk(root: Path) -> list[str]:
        results: list[str] = []
        try:
            for entry in sorted(root.iterdir()):
                if entry.name.startswith(".") and entry.name not in {".env"}:
                    continue
                if entry.is_dir():
                    if entry.name in _SKIP_DIRS:
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


@router.get("/project/dirs")
async def project_dirs():
    """Walk CWD recursively, return all dirs (skip hidden + noise). Dipakai /init autocomplete."""

    def walk(root: Path, cwd: Path) -> list[str]:
        results: list[str] = []
        try:
            for entry in sorted(root.iterdir()):
                if entry.name.startswith("."):
                    continue
                if not entry.is_dir():
                    continue
                if entry.name in _SKIP_DIRS:
                    continue
                rel = str(entry.relative_to(cwd)) + "/"
                results.append(rel)
                results.extend(walk(entry, cwd))
        except PermissionError:
            pass
        return results

    cwd = Path(os.getcwd())
    dirs = walk(cwd, cwd)
    return {"dirs": dirs, "cwd": str(cwd)}


@router.get("/project/token-estimate")
async def project_token_estimate(path: str):
    """
    Estimasi token count untuk satu file.
    Dipakai TUI saat browse /add — preview sebelum file masuk context.
    """
    from context import _estimate_tokens  # noqa: PLC0415

    cwd = Path(os.getcwd())
    target = (cwd / path).resolve()

    # Security: jangan keluar dari CWD
    try:
        target.relative_to(cwd)
    except ValueError:
        raise HTTPException(status_code=400, detail="Path outside CWD")

    if not target.is_file():
        raise HTTPException(status_code=400, detail="Not a file")

    try:
        text = target.read_text(encoding="utf-8", errors="replace")
        tokens = _estimate_tokens(text)
        return {"tokens": tokens, "path": path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/project/entries")
async def project_entries(path: str = ""):
    """
    List immediate children (files + dirs) di path tertentu.
    Default: CWD. Dipakai untuk autocomplete drill-down.
    Returns: { entries: [{name, path, is_dir}], cwd }
    """
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
            if entry.is_dir() and entry.name in _SKIP_DIRS:
                continue
            rel = str(entry.relative_to(cwd))
            entries.append(
                {
                    "name": entry.name + ("/" if entry.is_dir() else ""),
                    "path": rel + ("/" if entry.is_dir() else ""),
                    "is_dir": entry.is_dir(),
                }
            )
    except PermissionError:
        pass

    return {"entries": entries, "cwd": str(cwd)}
