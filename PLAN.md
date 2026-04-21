# minimal — PROJECT PLAN
> Status: PRE-BUILD — semua keputusan dikunci sebelum nulis code

---

## Filosofi
- **Minimal surface, rich capability** — UI sesedikit mungkin, fungsi selengkap mungkin
- **No bloat** — setiap file, dependency, dan fitur harus justify keberadaannya
- **Debuggable** — setiap layer bisa di-inspect sendiri tanpa harus jalanin seluruh stack
- **Owned** — bukan wrapper, bukan fork yang nangung tech debt orang lain

---

## Arsitektur

```
┌─────────────────────────────┐
│         TUI Layer           │
│   Build sendiri (bukan fork)│
│   TypeScript                │
│   @opentui/core — renderer  │
│   solid-js — reactive state │
│   yargs — CLI args          │
│   ~500 baris, owned penuh   │
└──────────┬──────────────────┘
           │ HTTP localhost (plain, no TLS)
           │ port: 4096
┌──────────▼──────────────────┐
│        Backend Layer        │
│   Python — project baru     │
│   FastAPI + uvicorn         │
│                             │
│  ┌─────────┐ ┌───────────┐  │
│  │ context │ │  session  │  │
│  │ manager │ │  manager  │  │
│  └─────────┘ └───────────┘  │
│  ┌─────────┐ ┌───────────┐  │
│  │  coder  │ │    llm    │  │
│  │ engine  │ │  wrapper  │  │
│  └─────────┘ └───────────┘  │
│  ┌─────────┐ ┌───────────┐  │
│  │commands │ │  config   │  │
│  │ /add    │ │  wizard   │  │
│  │ /drop   │ │  .env     │  │
│  │ /ls     │ └───────────┘  │
│  │ /clear  │                │
│  │ /undo   │                │
│  └─────────┘                │
└─────────────────────────────┘
```

---

## TUI Layer — build sendiri (bukan fork)

### Kenapa bukan fork OpenCode
Audit import graph menunjukkan OpenCode tightly coupled — `session/llm.ts`, `provider/provider.ts`, `auth`, `control-plane` saling import satu sama lain. Strip = rewrite 60% codebase. Lebih efisien build dari scratch di atas library yang sama.

### Stack
```
@opentui/core    rendering engine (sama yang OpenCode pakai internally)
solid-js         reactive state management
yargs            CLI argument parsing
```

### Struktur TUI
```
tui/
├── index.ts         entry point, CLI args (yargs), init
├── app.tsx          root component, layout utama
├── components/
│   ├── chat.tsx     message history display
│   ├── input.tsx    prompt input + slash command autocomplete
│   ├── context.tsx  file context panel (/ls display)
│   └── status.tsx   mode indicator, model name, token count
├── client.ts        HTTP client → backend port 4096
├── stream.ts        SSE consumer, heartbeat handler
└── state.ts         solid-js store — session, messages, context files
```

Target: ~500 baris total. Kamu handle design/layout, backend handle semua logic.

### Yang TUI urus
- Render messages (user + assistant + diff display)
- Input handling + slash command autocomplete
- SSE stream consumption + heartbeat timeout
- Mode indicator (ask / edit-block / edit-udiff / edit-whole)
- Token count display
- Session picker

### Yang TUI tidak urus (semua di backend)
- LLM calls
- File editing
- Session persistence
- Command parsing

---

## Backend Layer — struktur file

```
backend/
├── main.py             entry point, FastAPI app, semua routes
├── session.py          session lifecycle, persist ke JSONL
├── context.py          file context (/add /drop /ls tracking)
├── coder.py            edit engine (vendored + extended dari aider)
├── llm.py              litellm wrapper, streaming, provider config
├── commands.py         slash command handler
├── config.py           setup wizard, .env loader, provider registry
└── schemas.py          Pydantic models untuk semua request/response
```

Tidak ada folder-folder — semua flat. Backend ini harus bisa dibaca dalam satu kali scroll.

---

## Session Format — JSONL (seperti Claude Code)

```jsonl
{"type":"meta","session_id":"abc123","created_at":"2025-04-21T10:00:00Z","model":"glm-5","provider":"openrouter"}
{"type":"user","content":"fix the bug in main.py","files":["main.py"],"timestamp":"..."}
{"type":"assistant","content":"...","usage":{"input":450,"output":120},"timestamp":"..."}
{"type":"tool","tool":"edit_file","file":"main.py","diff":"...","timestamp":"..."}
{"type":"user","content":"/add utils.py","timestamp":"..."}
```

Lokasi: `~/.minimal/sessions/{session_id}.jsonl`
Resume: `--session {id}` atau TUI session picker

---

## Context Management — aider style

User harus `/add` file secara eksplisit setiap sesi.
State disimpan di session JSONL, bisa di-resume.

```python
# context.py
class ContextManager:
    files: dict[str, str]      # path → content (read-only)
    editable: set[str]         # files yang bisa di-edit AI
    
    def add(self, path, readonly=False)
    def drop(self, path)
    def ls(self) → list
    def get_messages(self) → list[dict]   # format untuk LLM prompt
```

---

## Edit Engine — multi-strategy (dari aider + extended)

### Phase 1 (MVP)
- **editblock** — SEARCH/REPLACE blocks (aider default)
- **whole file** — rewrite full file (untuk file kecil < 200 baris)
- **udiff** — unified diff format

### Phase 2 (setelah MVP jalan)
- **grep-based** — AI generate grep command → locate → patch (untuk codebase besar)
- **AST-aware** — python-specific, pakai `ast` module untuk surgical edit
- **script** — AI tulis Python script yang memodifikasi file, lalu dieksekusi

Masalah yang ini solve: tools sekarang kirim full file content untuk codebase besar → context window meledak + cost tinggi. Strategi grep+patch = AI cuma perlu tau lokasi, bukan seluruh file.

```python
# coder.py
class EditEngine:
    strategy: Literal["editblock", "whole", "udiff", "grep", "script"]
    
    def apply(self, response: str, files: dict) → list[EditResult]
    def validate(self, edit: EditResult) → bool
    def rollback(self, edit: EditResult)
```

---

## LLM Layer — provider agnostic

```python
# llm.py — pakai openai SDK dengan custom base_url
# semua provider modern OpenAI-compatible: OpenRouter, GLM, DeepSeek, dll
async def stream_chat(
    messages: list,
    model: str,           # model alias dari .env
    on_token: callable,   # streaming callback
) → Usage

# client init — satu instance, reused
client = openai.AsyncOpenAI(
    base_url=config.LLM_BASE_URL,
    api_key=config.LLM_API_KEY,
)
```

### Config — `~/.minimal/.env` (global, semua project)

```env
# Primary — wajib
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_API_KEY=sk-or-...
LLM_MODEL=glm-5

# Model aliases — optional, bebas berapa banyak
LLM_MODEL_FAST=glm-4.7-flash
LLM_MODEL_REASON=deepseek-r1
LLM_MODEL_CODE=qwen2.5-coder-32b

# Per-model context window override — optional
LLM_CONTEXT_WINDOW=128000        # default untuk primary model
LLM_CONTEXT_WINDOW_FAST=32000    # override untuk model FAST

# Request settings — optional, semua ada default
LLM_TIMEOUT=60
LLM_MAX_TOKENS=8192
LLM_THINKING_BUDGET=5000         # max tokens untuk reasoning/thinking
```

### Setup wizard — jalan sekali, first run tanpa `.env`

```
$ minimal

No config found. Quick setup:

Provider base URL? (enter untuk openrouter): 
API Key: 
Model: 

Config saved to ~/.minimal/.env
Starting...
```

Tiga field saja. Wizard **tidak** tanya context window, timeout, aliases — semua itu edit `.env` manual setelah setup.

### Multi-model mid-session

```
/model fast      → switch ke LLM_MODEL_FAST
/model reason    → switch ke LLM_MODEL_REASON  
/model glm-5     → langsung pakai sebagai model ID (fallback kalau alias tidak ada)
```

**Tidak ada YAML. Tidak ada nested config. Satu file `.env` untuk semua.**

---

## HTTP API — endpoints yang TUI butuhkan

```
GET  /health                     → {"ok": true}
GET  /event                      → SSE stream (TUI subscribe)
GET  /project/current            → {"path": "/home/user/myproject"}
GET  /config                     → current provider+model
POST /config/providers           → set provider/model

POST /session                    → buat session baru
GET  /session                    → list semua session
GET  /session/{id}               → session detail
POST /session/{id}/init          → kirim prompt, stream response via SSE
POST /session/{id}/abort         → stop generation

POST /context/add                → /add file ke context
POST /context/drop               → /drop file
GET  /context                    → /ls — list current context files
```

Total: 12 endpoints. Tidak lebih.

---

## Slash Commands

### Edit commands (trigger edit mode, one-shot, kembali ke ask setelah selesai)
```
/edit-block  <prompt>    edit dengan SEARCH/REPLACE (aider default)
/edit-udiff  <prompt>    edit dengan unified diff
/edit-whole  <prompt>    rewrite seluruh file
```

### Context commands
```
/add <file>              tambah file ke context (editable)
/add -r <file>           tambah file sebagai read-only
/drop <file>             hapus dari context
/ls                      list context files + token count
```

### Session & utility
```
/clear                   clear chat history (pertahankan context)
/reset                   clear chat + context
/undo                    rollback edit terakhir
/diff                    show diff dari edit terakhir
/commit                  git commit perubahan
/run <cmd>               jalankan shell command, output masuk context
/tokens                  tampilkan token usage sesi ini
/model <n>            ganti model mid-session
/help                    list semua commands
```

### Tidak diambil dari aider
```
/voice  /web  /paste  /architect  /report  /editor  /settings
```
---

## Build Phases

### Phase 0 — Foundation (sebelum nulis code)
- [ ] Setup repo structure (monorepo: `backend/` + `tui/`)
- [ ] Buat `VENDORS.md` — catat commit hash setiap aider file yang di-vendor
- [ ] Audit aider files yang di-vendor (trace imports, identifikasi yang bisa di-strip)
- [ ] Setup TUI project — `npm init`, install `@opentui/core`, `solid-js`, `yargs`

### Phase 1 — Backend MVP
- [ ] `main.py` — FastAPI + semua 12 endpoints (stub dulu)
- [ ] `config.py` — .env loader + setup wizard
- [ ] `llm.py` — litellm streaming wrapper
- [ ] `schemas.py` — semua Pydantic models
- [ ] `session.py` — create, persist JSONL, resume
- [ ] `context.py` — add/drop/ls
- [ ] `commands.py` — slash command parser + handler
- [ ] `coder.py` — editblock MVP (vendor dari aider search_replace.py)

Target: backend bisa menerima prompt, edit file, stream response. Test dengan `curl`.

### Phase 2 — TUI Build
- [ ] `tui/index.ts` — entry point, CLI args, launch
- [ ] `tui/state.ts` — solid-js store (session, messages, context, mode)
- [ ] `tui/client.ts` — HTTP client ke backend port 4096
- [ ] `tui/stream.ts` — SSE consumer + heartbeat timeout handler
- [ ] `tui/components/chat.tsx` — message history render
- [ ] `tui/components/input.tsx` — prompt input + slash command autocomplete
- [ ] `tui/components/status.tsx` — mode indicator + model + token count
- [ ] `tui/components/context.tsx` — file context panel
- [ ] `tui/app.tsx` — root layout, wiring semua components
- [ ] Test end-to-end: TUI → backend → LLM → file edit → TUI render

### Phase 3 — Polish
- [ ] Session picker di TUI
- [ ] Token usage display
- [ ] `/undo` dengan rollback yang reliable
- [ ] Edit strategy: udiff + whole file
- [ ] Error handling yang informatif (bukan stacktrace mentah)

### Phase 4 — Extended Edit Strategies
- [ ] grep-based editing untuk codebase besar
- [ ] Script-based editing
- [ ] AST-aware untuk Python files

---

## Dependencies

### Backend (Python)
```
fastapi          HTTP server
uvicorn          ASGI runner
openai           LLM client — OpenAI-compatible SDK (ganti litellm)
pydantic         schema validation
python-dotenv    .env loader
aiofiles         async file I/O
```
Total: 6 dependencies. Tidak lebih untuk Phase 1.

**Kenapa openai SDK bukan litellm:**
- Lebih ringan, tidak ada puluhan transitive dependencies
- Tidak ada breaking changes litellm antar minor version
- Semua provider target (OpenRouter, GLM-5, DeepSeek, Qwen) OpenAI-compatible
- Custom `base_url` + `api_key` = connect ke provider manapun
- Anthropic native tidak didukung — user pakai via OpenRouter saja

### TUI (TypeScript — build sendiri)
```
@opentui/core    rendering engine
solid-js         reactive state
yargs            CLI args
```
Total: 3 dependencies. Tidak ada warisan node_modules OpenCode.

---

## Mode & Edit Flow

### Dua mode, eksplisit dan jelas

**Ask mode (default)**
- AI jawab pertanyaan, explain, debug — tapi TIDAK boleh edit file
- Tidak ada tools, tidak ada edit instructions di response
- Token usage minimum karena system prompt lebih pendek

**Edit mode (user trigger)**
```
/edit-udiff   <prompt>    → AI edit dengan unified diff format
/edit-whole   <prompt>    → AI rewrite seluruh file
/edit-block   <prompt>    → AI edit dengan SEARCH/REPLACE blocks
```

Setelah edit selesai → **otomatis kembali ke ask mode**. Tidak sticky.

### Contoh flow
```
user:  /add src/main.py
user:  gimana cara fix null pointer di line 42?
ai:    [explain saja, no edit]

user:  /edit-udiff fix the null pointer in line 42
ai:    [apply udiff edit ke main.py] + [explain apa yang diubah]
       → kembali ke ask mode
```

### Kenapa tidak ada `/mode` persistent?
Karena persistent mode = user lupa mode aktif = edit tidak sengaja. Explicit per-command lebih aman dan lebih minimal.

---

## System Prompt — vendor dari aider

System prompt di-vendor langsung dari aider, bukan tulis dari scratch. Aider sudah battle-tested untuk format ini. Struktur:

**Ask mode system prompt:**
```
- Kamu adalah coding assistant
- Kamu TIDAK boleh mengedit file
- Jawab pertanyaan, explain code, debug secara verbal
- Files yang tersedia: {context_files}
```

**Edit mode system prompt (per /edit-<mode>):**
```
- Kamu adalah coding assistant yang sedang dalam mode edit
- Format edit: {mode} (udiff / whole / editblock)
- [instruksi format spesifik — vendor dari aider prompts]
- Files yang boleh diedit: {editable_files}
- Setelah edit, jelaskan apa yang diubah
```

Retry logic: kalau parse format gagal → silent retry max 2x → baru error ke user.

---

## Aider Bugs yang Di-fix di minimal

### 1. Thinking content leak → infinite loop
Aider `reasoning_tags.py` incomplete untuk beberapa model. Thinking content bocor ke message history → AI baca thinking sendiri → loop.

**Fix:** strip thinking content (`<think>`, `reasoning_content`) **sebelum** masuk message history. Hard rule — thinking tidak pernah boleh ada di context.

### 2. False "applied" — AI ngaku sukses padahal gagal parse
Aider lanjut tanpa rollback kalau parse gagal. User kira file sudah diedit.

**Fix:** setelah apply edit, verify langsung — baca file, cek apakah SEARCH block sudah tidak ada. Gagal → rollback otomatis → kasih tau user dengan jelas.

### 3. Provider config tidak user-friendly
`openai/glm-5`, `openrouter/deepseek-r1` — user harus tau litellm prefix convention.

**Fix:** user cukup isi base URL + model name. Backend pakai openai SDK dengan custom `base_url` — tidak ada prefix convention, tidak ada internal string format yang perlu diketahui user.

### 4. Thinking loop / timeout
Model reasoning kadang thinking infinite tanpa output.

**Fix:** `LLM_THINKING_BUDGET` batasi token thinking. Timeout per request (`LLM_TIMEOUT`). Kalau hit limit → interrupt + kasih user opsi retry.

---

## Aider — vendor vs tulis ulang

### Di-vendor (copy lalu modifikasi)
```
coders/search_replace.py    edit parsing — SEARCH/REPLACE blocks
coders/editblock_coder.py   editblock apply + verify
coders/udiff_coder.py       udiff apply
coders/wholefile_coder.py   whole file rewrite
sendchat.py                 message validation, alternating roles
repo.py                     git integration (commit, diff, undo)
```

### Tulis ulang (aider punya bug/bloat di sini)
```
reasoning_tags.py  → tulis ulang: strip thinking SEBELUM masuk history
models.py          → ganti: config.py + .env wizard yang simple
io.py              → tidak perlu: TUI handle semua display
llm.py             → ganti: litellm wrapper kita sendiri
args.py            → tidak perlu: config dari .env
```

---

## Yang sengaja TIDAK dibangun (anti-features)
- Tidak ada cloud sync
- Tidak ada user accounts / auth
- Tidak ada web UI / browser interface
- Tidak ada voice
- Tidak ada multi-workspace routing
- Tidak ada plugin system (Phase 1-3)
- Tidak ada analytics / telemetry
- Tidak ada tool calls (semua inline di response text)

