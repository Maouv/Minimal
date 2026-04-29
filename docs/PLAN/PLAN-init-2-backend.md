# Plan 2 — Backend: Endpoint + Command Handler

## Depends on
Plan 1 (`repo.py`) harus sudah ada.

---

## 1. `commands.py`

### Tambah `"init"` ke `Kind` literal di `Command` dataclass:
```python
kind: Literal[
    "add", "drop",
    "edit", "ask",
    "clear", "reset",
    "undo", "diff", "commit",
    "run", "tokens", "model",
    "help", "init",       # ← tambah ini
    "prompt",
]
```

### Tambah ke `SLASH_COMMANDS` list:
```python
"/init",
```

### Tambah parse logic di `parse()` sebelum fallback `unknown`:
```python
if cmd == "/init":
    return Command(kind="init", args=args)
# args bisa: "" | "min/backend" | "--save"
```

### Tambah ke `HELP_TEXT`:
```
  /init [path]         generate MINIMAL.md for current or given dir
  /init --save         write last draft to MINIMAL.md
```

---

## 2. `session.py`

Tambah dua field ke `Session.__init__()`:

```python
self.last_init_draft: str | None = None
self.last_init_path:  str | None = None
```

---

## 3. `main.py` — endpoint baru

```python
@app.post("/repo/map")
async def repo_map(req: dict):
    """
    Scan repo dari path tertentu dan return RepoContext.
    Body: { path?: string }  — default CWD
    Security: path di-resolve relatif ke CWD, tolak kalau keluar CWD.
    """
    import repo as repo_module
    from pathlib import Path
    import os

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
```

---

## 4. `main.py` — `/init` handler di `_handle_prompt()`

Tambah blok ini sebelum LLM dispatch (setelah blok `/model`):

```python
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
    system = prompts.init_system()
    messages = [{"role": "user", "content": context_str}]

    full_response = ""
    async for token, usage in llm.stream_chat(messages, s.model, system):
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
```

---

## 5. `_build_init_context(ctx) -> str`

Helper function di `main.py`:

```python
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
```

---

## 6. `prompts.py` — tambah `init_system()`

Lihat PLAN-init-3-frontend-prompt.md untuk isi lengkap system prompt.

---

## 7. Catatan: `/project/entries` sudah ada

Endpoint `GET /project/entries?path=` sudah diimplementasi saat fix `/add` bug.
Plan 3 frontend bisa langsung pakai `loadEntries()` dari `client.ts` — tidak perlu buat ulang.

---

## Test

```bash
# Test endpoint langsung
curl -X POST http://localhost:4096/repo/map \
  -H "Content-Type: application/json" \
  -d '{"path": "min/backend"}'

# Test via TUI
/init                  → generate untuk CWD
/init min/backend      → generate untuk subdir
/init --save           → tulis ke MINIMAL.md
```
