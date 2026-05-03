# api/health.py — GET /health, POST /repo/map

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("/health")
async def health():
    return {"ok": True}


@router.post("/repo/map")
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
