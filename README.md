# minimal

A minimal AI coding assistant. Token-efficient by design.

## Philosophy
- Ask by default — AI answers only, no file edits
- Explicit edit commands — `/edit-block`, `/edit-udiff`, `/edit-whole`
- No tool calls — all inline response text
- One `.env` file, no YAML, no nested configs

## Stack
- **TUI:** TypeScript — `@opentui/core` + `solid-js` (Bun runtime)
- **Backend:** Python + FastAPI — port 4096
- **LLM:** OpenAI-compatible SDK — any provider via `base_url`

## Quick start
```bash
# Backend
cd min/backend
pip install -r requirements.txt
python main.py

# TUI (terminal separated)
cd min/tui
bun install
bun run index.tsx

# CLI flags
bun run index.tsx --session <id>   # resume session
bun run index.tsx --model gpt-4o   # override model
```
First run without `~/.minimal/.env` → Input Base url, Api key.model. Once get in to TUI, you can also add more provider, more model by /model-add or swtich to mode /model.

## Slash Commands
```
/add <file> <file2>     add file batch support
/add -r <file>          read only file
/drop <file>            remove file from context
/edit-block [prompt]    edit with SEARCH & REPLACE
/edit-udiff [prompt]    edit with unified diff
/edit-whole [prompt]    edit whole file
/ask [question?]        ask mode, no edit file
/undo                   undo ai change last edit
/diff                   show last diff
/commit [message]       commit change wirh costum message
/run <cmd>              run shell command
/tokens                 usage token
/model                  switch model or provider
/model-add              add new model or nee provider
/clear                  clear history 
/reset                  reset + context + clear history
/help                   help command
```
## Coonfig
```
~/.minima/.env

OPENROUTER_API_KEY=sk-or-v1-....

~/.minimal/providers.json
{
  {
    "name": "OpenRouter",
    "base_url": "https://openrouter.ai/api/v1",
    "env_key": "OPENROUTER_API_KEY",
    "last_model": "minimax/minimax-m2.5:free"
  },
}
```

For more documentation please read **[ARCHITECTURE.md] (./ARCHITECTURE.md)** (provide all module, sse event, API endpoint, @opentui internals).


