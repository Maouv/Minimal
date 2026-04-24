## MINIMAL.md backend

This file is summary of min/backend directory use for Minimal ai to understand more about this directory.
file located at [MINIMAL.md](./min/backend/MINIMAL.md)

## How to run

```bash
cd min/backend
pip install -r requirements.txt
python main.py
# FastAPI on localhost:4096, auto-reloads not enabled — restart manually after changes
```

## Run test

Live test in [./min/tests](./min/tests)

```bash
# From repo root
python -m pytest min/tests/
python -m pytest min/tests/test_coder.py   # single file
python -m pytest min/tests/ -v
```

`conftest.py` inserts `min/backend` into `sys.path` so flat imports (`from coder import ...`) work in tests without a package.

```
POST /session/:id/init
  → cmd_parser.parse(raw_input)     # returns Command(kind, args, edit_mode)
  → dispatch to handler in _handle_prompt()
      ├── non-LLM commands (add, drop, run, commit, …) → yield SSE event, return
      ├── non-LLM commands (add, drop, run, commit, …) → yield SSE event, return
      └── LLM commands (prompt, edit)
            → prompts.py builds system prompt
            → context.to_messages() prepends files as XML <files> blocks
            → llm.stream_chat() yields (token, None)* then (None, Usage)
            → each token → yield sse("token", …)
            → after stream: coder.apply_edits() if edit mode
            → yield sse("done", …)
```

All responses are SSE (`text/event-stream`). There is no JSON response body for the prompt endpoint — only the stream. See `ARCHITECTURE.md` at repo root for the full SSE event table.

### Tree directory

```
├── MINIMAL.md <--- this file
├── coder.py
├── commands.py
├── config.py
├── context.py
├── llm.py
├── main.py
├── probe_models.py
├── prompts.py
├── requirements.txt
├── schemas.py
├── session.py
└── vendor
    ├── __init__.py
    ├── __pycache__
    ├── editblock.py
    ├── repo.py
    ├── search_replace.py
    ├── sendchat.py
    ├── udiff.py
    ├── udiff.py.bak
    └── wholefile.py
```

### Module responsiblity

| Module | Responsibility |
|---|---|
| `main.py` | All HTTP endpoints, `_handle_prompt()` dispatcher |
| `config.py` | `.env` read/write, `providers.json` management |
| `session.py` | Session object, JSONL persistence, in-memory registry |
| `context.py` | File loading, token estimation, formatting files for LLM |
| `llm.py` | OpenAI SDK wrapper, thinking-tag stripping, usage tracking |
| `coder.py` | Parses LLM response for edits, writes to disk, rollback |
| `commands.py` | Slash command tokenizer → `Command` dataclass |
| `prompts.py` | System prompt strings for ask and all three edit modes |
| `probe_models.py` | `GET /v1/models` probe for provider discovery |
| `schemas.py` | Pydantic models for all request/response types |
| `vendor/` | Edit format parsers from aider (search and replace, udiff, wholefile) |

### Edit pipeline (`coder.py`)

Three modes, all go through `apply_edits(response, files, mode)`:

- `block` → `vendor/search_replace.py` — finds `<<<<<<< SEARCH / ======= / >>>>>>> REPLACE` blocks
- `udiff` → `vendor/udiff.py` — parses unified diff hunks from ` ```diff ` fences
- `whole` → `vendor/wholefile.py` — finds `filename\n```lang\n...\n```\` pattern

`coder.rollback(result)` restores `result.original` to disk — used by `/undo`.

### Session JSONL format

Each session is `~/.minimal/sessions/<8-char-uuid>.jsonl`. Line types:

```
meta        — first line, stores model + base_url at creation time
user        — user message
assistant   — assistant reply (thinking stripped)
edit        — one file edit (file, diff, success)
command     — slash commands like /add
```

### Config files

`~/.minimal/.env` — single source for active provider credentials and all `LLM_*` env vars.

`~/.minimal/providers.json` — list of known providers: `{ name, base_url, env_key, last_model? }`. API keys are stored in `.env` under the `env_key` field value, not inside this JSON.

### Thinking tag stripping

`llm.py` tracks open vs closed `<think>` / `<thinking>` tags across the stream. Tokens inside thinking blocks are consumed but never yielded to the SSE stream or stored in session history.
