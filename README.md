# minimal

A minimal AI coding assistant. Token-efficient by design.

## Philosophy
- Ask by default — AI answers only, no file edits
- Explicit edit commands — `/edit-block`, `/edit-udiff`, `/edit-whole`
- No tool calls — all inline response text
- One `.env` file, no YAML, no nested configs

## Stack
- **TUI:** TypeScript — `@opentui/core` + `solid-js` (build sendiri, ~500 baris)
- **Backend:** Python + FastAPI — port 4096
- **LLM:** OpenAI-compatible SDK — any provider via `base_url`

## Quick start
```bash
# Backend
cd backend
pip install -r requirements.txt
python main.py

# TUI (separate terminal)
cd tui
npm install
npm start
```

First run without `~/.minimal/.env` triggers setup wizard.

## Config — `~/.minimal/.env`
```env
# Required
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_API_KEY=sk-or-...
LLM_MODEL=glm-5

# Optional model aliases
LLM_MODEL_FAST=glm-4.7-flash
LLM_MODEL_REASON=deepseek-r1

# Optional overrides
LLM_TIMEOUT=60
LLM_MAX_TOKENS=8192
LLM_THINKING_BUDGET=5000
LLM_CONTEXT_WINDOW=128000
```

## Commands
```
/add <file>          add file to context
/add -r <file>       add as read-only
/drop <file>         remove from context
/ls                  list context files + token count
/edit-block <prompt> edit with SEARCH/REPLACE
/edit-udiff <prompt> edit with unified diff
/edit-whole <prompt> rewrite entire file
/undo                rollback last edit
/diff                show last diff
/commit              git commit changes
/run <cmd>           run shell command
/tokens              show session token usage
/model <name>        switch model
/clear               clear chat history
/reset               clear chat + context
/help                list all commands
```

