# MINIMAL.md

This file is summary of min directory use for Minimal ai to understand more about this directory.
file located at [MINIMAL.md](./min/MINIMAL.md)

## Running project

Both processes must run simultaneously in separate terminals or session:

```Bash
# Session 1 run backend (use tmux)
cd min/backend
pip install -r requirements.txt
python main.py
# Listen on localhost:4096

# Session 2 run TUI (not use tmux)
cd min/tui
bun install
bun run index.tsx

# TUI with flag (optional)
bun run index.tsx --session <id>   # resume an existing session
bun run index.tsx --model gpt-4o   # override active model
```

First run without `~/.minimal/.env` triggers an interactive setup wizard (asks for base URL, API key, model). Env persists globally at `~/.minimal/.env`, for base URL and model persists globally at `~/.minimal/providers.json`, not per project.

## Run test

```bash
# From the repo root
python -m pytest min/tests/

# Single test file
python -m pytest min/tests/test_coder.py

# Verbose
python -m pytest min/tests/ -v
```

`conftest.py` adds `min/backend` to `sys.path` so backend modules import without a package structure.

There are currently no TUI-side tests.

## Architecture overview

Tree project structure:

```
├── MINIMAL.md <--- this file
├── backend
│   ├── MINIMAL.md
│   ├── __pycache__
│   ├── coder.py
│   ├── commands.py
│   ├── config.py
│   ├── context.py
│   ├── llm.py
│   ├── main.py
│   ├── probe_models.py
│   ├── prompts.py
│   ├── requirements.txt
│   ├── schemas.py
│   ├── session.py
│   └── vendor
│       ├── __init__.py
│       ├── __pycache__
│       ├── editblock.py
│       ├── repo.py
│       ├── search_replace.py
│       ├── sendchat.py
│       ├── udiff.py
│       ├── udiff.py.bak
│       └── wholefile.py
├── requirements.txt
├── tests
│   ├── Akwkw.md
│   ├── TEST.md
│   ├── __pycache__
│   ├── conftest.py
│   ├── test.txt
│   ├── test_coder.py
│   └── test_coder.py.bak
└── tui
    ├── MINIMAL.md
    ├── app.tsx
    ├── app.tsx.bak
    ├── bun.lock
    ├── bunfig.toml
    ├── client.ts
    ├── components
    ├── index.tsx
    ├── logo-and-minimal.md
    ├── node_modules
    ├── package-lock.json
    ├── package.json
    ├── state.ts
    ├── stream.ts
    ├── theme.ts
    └── tsconfig.json
```
## flow process

Two completely separate processes connected only via HTTP on port 4096.

```
TUI (Bun/TypeScript)  ──HTTP──▶  Backend (Python/FastAPI)
      │                                  │
  @opentui/solid                    OpenAI SDK
  (terminal renderer)           (any OpenAI-compatible API)
```

**Data flow for a Prompt**

1. User types in `InputBox`, presses Enter
2. `handleSubmit` in `input.tsx` — if slash command for `/model`/`/model-add`, opens `ModelPicker` overlay; otherwise calls `sendPrompt()`
3. `client.ts` → `POST /session/:id/init` → backend returns SSE stream.
4. `stream.ts` `consumeStream()` parses events and writes to Solid store (`state.ts`)
5. `chat.tsx` reactively re-renders from store.


**Edit flow** (`/edit-block`, `/edit-udiff`, `/edit-whole`):

- Backend sends the prompt to LLM with an edit-mode system prompt
- LLM response contains edit blocks (SEARCH/REPLACE, unified diff, or whole file)
- `coder.py` parses and applies edits, then streams `edit` SSE events with diffs back to TUI

**Sessions presisten**

Every session writes append-only JSONL to `~/.minimal/sessions/<id>.jsonl`. The TUI only holds the session ID; all history lives in the backend. Sessions can be resumed with `--session <id>`.

**provider/models**

- Active provider is always `LLM_BASE_URL` + `LLM_API_KEY` + `LLM_MODEL` in `.env`
- Multiple providers are stored in `~/.minimal/providers.json` with per-provider `env_key` and `last_model`
- Switching provider updates `.env` in-place via `python-dotenv`'s `set_key()`
