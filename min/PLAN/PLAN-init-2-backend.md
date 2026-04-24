# Plan 2 — Backend: Endpoint + Command Handler

## Depends on
Plan 1 (`repo.py`) there must be..

## 1. `commands.py`

add `"init"` to `COMMANDS` list and `COMMANDS_NO_SLASH`.

Parse logic:
- `/init` → `Command(kind="init", args="")`
- `/init min/backend` → `Command(kind="init", args="min/backend")`
- `/init --save` → `Command(kind="init", args="--save")`

## 2. `session.py`

Add two field to Session:

```python
self.last_init_draft: str | None = None
self.last_init_path: str | None = None
```

## 3. `main.py` — new endpoint

```
POST /repo/map
body: { path?: string }
→ RepoContext as JSON

Security: resolve path relative to CWD, reject if exit from CWD (sama
e like/project/entries).
```

## 4. `main.py` — `/init` handler in `_handle_prompt()`

Add block before LLM dispatch:

```python
if command.kind == "init":

    # --save: write last draft to disk
    if command.args == "--save":
        if not s.last_init_draft:
            yield sse("error", {"message": "No draft. Run /init first."})
            return
        target = Path(s.last_init_path or os.getcwd()) / "MINIMAL.md"
        target.write_text(s.last_init_draft, encoding="utf-8")
        yield sse("text", {"content": f"✓ saved to {target}"})
        yield sse("done", {"input_tokens": 0, "output_tokens": 0})
        return

    # scan repo
    import repo as repo_module
    root = Path(os.getcwd())
    if command.args:
        candidate = (root / command.args).resolve()
        try:
            candidate.relative_to(root)
            root = candidate
        except ValueError:
            yield sse("error", {"message": "The path is outside of project."})
            return

    ctx = repo_module.scan(root)
    s.last_init_path = str(root)

    # build context string to be injected into the prompt
    context_str = _build_init_context(ctx)   # helper, see below

    # stream to LLM
    system = prompts.init_system()
    messages = [{"role": "user", "content": context_str}]
    full_response = ""
    async for token, usage in llm.stream_chat(messages, s.model, system):
        if token:
            full_response += token
            yield sse("token", {"content": token})
        if usage:
            s.last_init_draft = full_response
            yield sse("done", {"input_tokens": usage.input_tokens,
                               "output_tokens": usage.output_tokens})
    return
```

## 5. `_build_init_context(ctx: RepoContext) -> str`

Helper in `main.py`, arrange context string:

```
=== EXISTING MINIMAL.md ===
[write every minimal_md labeled path + depth]

=== @repo: TAGS ===
[file: tag]
[file: tag]

=== REPO MAP ===
[file: symbol1, symbol2, ...]

=== MANIFESTS ===
[file: contents]
```

The token estimate is already trimmed by `repo.scan()`, so no further trimming is needed here.

## 6. `prompts.py` — add `init_system()`

Contents: system prompt from discussion (see PLAN-init-3-prompt.md).

## test

```bash
curl -X POST http://localhost:4096/repo/map \
  -H "Content-Type: application/json" \
  -d '{"path": "min/backend"}'
```

