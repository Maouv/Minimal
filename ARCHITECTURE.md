# Minimal — Architecture & Developer Reference

Dokumen ini mencakup semua modul, komponen, API endpoint, SSE events, dan catatan khusus tentang `@opentui` — library TUI yang masih muda dan dokumentasinya tipis.

---

## Struktur direktori

```
min/
├── backend/                 Python + FastAPI, port 4096
│   ├── main.py              Entry point, semua HTTP endpoints
│   ├── config.py            .env loader, provider management
│   ├── session.py           Session lifecycle + JSONL persistence
│   ├── context.py           Context file manager
│   ├── llm.py               OpenAI-compatible streaming wrapper
│   ├── coder.py             File edit engine (block/udiff/whole)
│   ├── commands.py          Slash command parser
│   ├── prompts.py           System prompt builder
│   ├── schemas.py           Pydantic request/response models
│   ├── probe_models.py      Probe /v1/models dari provider
│   └── vendor/
│       ├── editblock.py     SEARCH/REPLACE parser (aider-derived)
│       ├── search_replace.py
│       ├── udiff.py         Unified diff parser
│       └── wholefile.py     Whole-file rewrite
│
└── tui/                     TypeScript + @opentui/solid + Bun
    ├── index.tsx            Entry point, CLI args, session init
    ├── app.tsx              Root layout component
    ├── state.ts             Global Solid.js store
    ├── client.ts            HTTP client ke backend
    ├── stream.ts            SSE consumer
    ├── theme.ts             Color palette + syntax highlight style
    └── components/
        ├── chat.tsx         Chat view (messages + code rendering)
        ├── input.tsx        Input bar + slash autocomplete
        ├── model-picker.tsx Model/provider selector overlay
        ├── status.tsx       StatusBar + CtxBar
        └── context.tsx      Context panel (unused di layout utama)
```

---

## Backend

### `main.py` — HTTP Endpoints

Semua endpoint di `localhost:4096`. Backend pakai FastAPI dengan CORS allow-all.

#### Health
```
GET /health
→ { ok: true }
```

#### Config
```
GET /config
→ ConfigResponse {
    base_url, model, models: {alias: id},
    context_window, timeout, max_tokens
  }

POST /config/providers
body: { model: string }
→ { ok: true, model }
```

#### Providers
```
GET /providers
→ { providers: Provider[] }
  Provider: { name, base_url, env_key, last_model? }

POST /providers/add
body: { name, base_url, api_key }
→ { ok: true, provider: Provider }
  Simpan ke ~/.minimal/providers.json + API key ke ~/.minimal/.env

POST /providers/probe
body: { base_url, api_key, provider_name? }
  api_key "__from_env__" → resolve dari .env via env_key provider
  Lookup order: provider_name dulu (by name), fallback ke base_url match
→ ProbeResult { ok, models: string[], error: string | null }

POST /providers/switch
body: { provider_name, model_id }
  Update LLM_BASE_URL, LLM_API_KEY, LLM_MODEL di .env
  Simpan last_model ke providers.json
→ { ok: true, model, base_url }
```

#### Project files
```
GET /project/current
→ { path: string }  (CWD)

GET /project/files
→ { files: string[], cwd: string }
  Walk CWD rekursif, skip: .git __pycache__ node_modules .venv dll
  Files dikembalikan sebagai absolute path
```

#### Session
```
POST /session
body: { model?: string }
→ { session_id, model, created_at }

GET /session
→ { sessions: SessionMeta[] }
  SessionMeta: { session_id, created_at, model }

GET /session/:id
→ { session_id, model, created_at, message_count }

POST /session/:id/abort
→ { ok: true }  (TODO: belum benar-benar cancel stream)
```

#### Context
```
POST /context/add
body: { session_id, path, readonly?: bool }
→ { files: ContextFile[] }

POST /context/drop
body: { session_id, path }
→ { files: ContextFile[] }

GET /context?session_id=...
→ { files: ContextFile[], total_tokens: int }

ContextFile: { path, readonly, token_count, last_modified }
```

#### Prompt + SSE Stream
```
POST /session/:id/init
body: { content: string }
→ StreamingResponse (text/event-stream)
  Semua response dikirim sebagai SSE events, lihat bagian SSE Events di bawah
```

---

### SSE Events

Format: `event: <type>\ndata: <json>\n\n`

| Event | Payload | Keterangan |
|---|---|---|
| `ping` | `{}` | Heartbeat tiap 2 detik selama stream aktif |
| `token` | `{ content: string }` | Satu chunk teks dari LLM |
| `done` | `{ input_tokens, output_tokens }` | Stream selesai |
| `error` | `{ message: string }` | Error apapun |
| `context` | `{ files: ContextFile[], total_tokens? }` | Update context setelah /add /drop |
| `model` | `{ model: string }` | Setelah /model switch |
| `mode` | `{ mode: string }` | Setelah /edit-* mode switch |
| `tokens` | `{ context_tokens, session_tokens }` | Response /tokens command |
| `text` | `{ content: string }` | Output teks biasa (/help, /run, dll) |
| `edit` | `{ file, diff, success, error? }` | Satu file edit selesai |
| `diff` | `{ diffs: [{file, diff}] }` | Response /diff command |
| `run` | `{ output, returncode }` | Response /run command |
| `commit` | `{ output }` | Response /commit |
| `undo` | `{ files: string[] }` | Response /undo |
| `clear` | `{}` | Response /clear |
| `reset` | `{}` | Response /reset |

**Thinking content** (`<think>...</think>`, `<thinking>...</thinking>`) di-strip otomatis di `llm.py` dan tidak pernah di-yield sebagai token event.

---

### `config.py` — Config & Provider Management

Config global di `~/.minimal/.env`. Providers di `~/.minimal/providers.json`.

**Getters:**
- `config.base_url()` → `LLM_BASE_URL`
- `config.api_key()` → `LLM_API_KEY`
- `config.model()` → `LLM_MODEL`
- `config.timeout()` → `LLM_TIMEOUT` (default 60)
- `config.max_tokens()` → `LLM_MAX_TOKENS` (default 8192)
- `config.thinking_budget()` → `LLM_THINKING_BUDGET` (default 5000)
- `config.context_window(alias?)` → `LLM_CONTEXT_WINDOW` (default 128000), atau `LLM_CONTEXT_WINDOW_{ALIAS}`
- `config.all_models()` → dict semua `LLM_MODEL_*` aliases
- `config.resolve_model(name)` → resolve alias ke model ID, fallback ke name itu sendiri

**Provider functions:**
- `config.load_providers()` — load dari providers.json, seed dari .env kalau kosong
- `config.add_provider(name, base_url, api_key)` — tambah/update entry + simpan API key ke .env
- `config.switch_provider_model(provider, model_id)` — update .env + simpan `last_model` ke providers.json

**Format providers.json:**
```json
[
  {
    "name": "OpenRouter",
    "base_url": "https://openrouter.ai/api/v1",
    "env_key": "OPENROUTER_API_KEY",
    "last_model": "openai/gpt-4o"
  }
]
```
API key disimpan terpisah di `.env` dengan key = `env_key`.

---

### `session.py` — Session & Persistence

Session disimpan sebagai append-only JSONL di `~/.minimal/sessions/<id>.jsonl`.

**Format JSONL (tiap line adalah satu record):**
```jsonl
{"type": "meta", "session_id": "abc123", "created_at": "...", "model": "gpt-4o", "base_url": "..."}
{"type": "user", "content": "fix the bug", "timestamp": "..."}
{"type": "assistant", "content": "...", "timestamp": "...", "usage": {"input_tokens": 100, "output_tokens": 200}}
{"type": "edit", "file": "main.py", "diff": "...", "success": true, "timestamp": "..."}
{"type": "command", "content": "/add src/main.py", "timestamp": "..."}
```

**Session object:**
- `session.model` — model aktif untuk session ini
- `session.mode` — `ask | edit-block | edit-udiff | edit-whole`
- `session.context` — `ContextManager` instance
- `session.messages` — in-memory chat history (tanpa thinking)
- `session.last_edit` — list `EditResult` terakhir (untuk /undo)

---

### `llm.py` — LLM Streaming

Pakai `openai` SDK dengan `base_url` custom — kompatibel dengan semua OpenAI-compatible API.

```python
async for token, usage in llm.stream_chat(messages, model, system_prompt):
    if token:    # string chunk
    if usage:    # Usage(input_tokens, output_tokens) — di akhir stream
```

`clean_for_history(content)` — strip semua `<think>` / `<thinking>` blocks sebelum simpan ke history.

---

### `commands.py` — Slash Command Parser

```python
Command = parse("/add src/main.py")
# Command(kind="add", args="src/main.py", readonly=False, edit_mode=None)
```

**kind values:** `add`, `drop`, `ls`, `clear`, `reset`, `tokens`, `model`, `ask`, `help`, `undo`, `diff`, `commit`, `run`, `edit`, `prompt`

Untuk edit commands: `kind="edit"`, `edit_mode="block"|"udiff"|"whole"`, `args` = prompt teks.

---

## TUI

### `@opentui` — Catatan Penting

`@opentui` adalah library TUI untuk Node/Bun yang masih sangat baru. Docs-nya tipis, banyak yang harus di-cari dari source. Berikut yang sudah dipelajari dari source langsung (`@opentui/core` v0.1.102, `@opentui/solid` v0.1.102):

#### Render system

- Renderer pakai native binary (Zig) untuk output ke terminal
- `writeOut()` jalan di thread terpisah, menulis lewat stream
- **Jangan pernah log ke stdout** — akan merusak render. Gunakan `console.error()` kalau perlu debug, atau tulis ke file

#### Focus management

- Hanya satu node yang bisa focused pada satu waktu — tracked di `renderer._currentFocusedRenderable`
- `focus()` mendaftarkan `keypressHandler` ke `ctx._internalKeyInput`
- `blur()` menghapus `keypressHandler` dari `ctx._internalKeyInput`
- `_removeNode()` memanggil `destroyRecursively()` via **`process.nextTick`** (async!)

**⚠️ Bug kritis**: Kalau `<input>` dibungkus `<Show>` dan fase berubah, node lama di-unmount tapi `destroyRecursively()` jalan nextTick. Sebelum nextTick selesai, `keypressHandler` node lama masih terdaftar dan bisa firing → crash di `renderer.ts:2609` (emit → addChunk → readableAddChunkPushByteMode).

**Solusi**: Gunakan satu `<input>` yang selalu mounted. Ganti props-nya (placeholder, onSubmit) sesuai fase — bukan mount/unmount node berbeda. Lihat implementasi `ModelPicker` di `model-picker.tsx`.

#### Props yang tersedia untuk `<input>`

```tsx
<input
  ref={inputRef}            // InputRenderable | undefined
  flexGrow={1}              // layout flex
  placeholder="..."
  placeholderColor="#hex"
  backgroundColor="#hex"
  textColor="#hex"
  focusedBackgroundColor="#hex"
  focusedTextColor="#hex"
  focused                   // boolean — auto-focus saat mount
  onInput={(val: string) => void}    // tiap keystroke
  onSubmit={(val: string) => void}   // Enter ditekan
/>
```

`inputRef.value = ""` — reset isi input secara programmatic (tidak trigger `onInput`).
`inputRef.focus?.()` — focus programmatic. Butuh `setTimeout(..., 50)` karena mount tidak langsung sync dengan renderer frame.

#### Hooks yang tersedia (`@opentui/solid`)

```ts
import { useKeyboard, render } from "@opentui/solid"

// Global keyboard handler — tangkap key events sebelum sampai ke focused input
useKeyboard((key) => {
  // key.name: "up" | "down" | "return" | "escape" | "tab" | "backspace" | string
  // key.ctrl, key.shift, key.alt: boolean
  key.preventDefault()  // block key dari sampai ke input
})

// Render SolidJS app ke terminal
render(() => <App />, {
  exitOnCtrlC: true,
  exitSignals: ["SIGTERM"],
  clearOnShutdown: true,    // hapus terminal saat exit
  backgroundColor: "#hex",
})
```

**Urutan event**: `useKeyboard` fires dulu, baru `onSubmit`/`onInput` di focused input. Kalau `key.preventDefault()` dipanggil di `useKeyboard`, `onSubmit` tidak akan firing.

#### Layout system

Pakai Flexbox (Yoga layout engine). Props yang didukung:

```
flexDirection="row|column"
flexGrow={1}
flexShrink={0}
flexWrap="wrap"
alignItems="center|flex-start|flex-end"
justifyContent="center|flex-start|flex-end"
width="100%"|{number}
height={number}
paddingLeft/Right/Top/Bottom={number}
marginLeft/Right/Top/Bottom={number}
```

#### JSX elements

- `<box>` — container div (Flexbox)
- `<text fg="#hex" marginRight={1}>content</text>` — text node, `fg` = foreground color
- `<input>` — editable text field (lihat props di atas)
- `<scrollbox flexGrow={1} scrollY>` — scrollable container

#### Fragments dan Show

```tsx
// Fragment — boleh dipakai dalam JSX
<>
  <text>A</text>
  <text>B</text>
</>

// Show — conditional rendering
<Show when={someSignal()}>
  <box>...</box>
</Show>

// Show dengan fallback
<Show when={condition} fallback={<text>empty</text>}>
  <text>content</text>
</Show>
```

**Ingat**: Setiap kali `when` berubah, child di dalam `<Show>` mount/unmount. Jangan taruh `<input>` di dalam `<Show>` yang sering toggle — gunakan single always-mounted input dengan props yang berubah.

#### Warna

Semua warna pakai hex string: `fg="#f8f8f2"`, `backgroundColor="#141414"`. Tidak ada named colors.

---

### `state.ts` — Global Store

```ts
interface AppState {
  sessionId: string | null
  model: string
  mode: "ask" | "edit-block" | "edit-udiff" | "edit-whole"
  streaming: boolean
  messages: Message[]
  contextFiles: ContextFile[]
  totalTokens: number
  inputTokens: number
  outputTokens: number
  error: string | null
  showModelPicker: "switch" | "add" | false
}
```

**Helper functions:**
- `pushMessage(role, content?)` → tambah message, return index
- `appendToken(idx, token)` → append ke message[idx].content (untuk streaming)
- `finalizeMessage(idx, edits?)` → set done = true
- `setContextFiles(files, totalTokens)` → update context display
- `clearMessages()` → kosongkan chat
- `resetAll()` → kosongkan chat + context + tokens

---

### `stream.ts` — SSE Consumer

`consumeStream(response: Response)` — parse SSE stream dari backend, dispatch semua events ke state.

**Token throttling**: Token dari LLM di-buffer 32ms sebelum flush ke Solid state (~30 FPS). Ini mencegah ratusan reactive updates per detik yang bisa bikin TUI lag.

**Heartbeat**: Timeout 30 detik. Kalau tidak ada event (termasuk `ping`) selama 30 detik, dianggap connection lost dan streaming = false.

---

### `client.ts` — HTTP Client

Base URL: `http://localhost:4096`

```ts
// Provider management
listProviders(): Promise<Provider[]>
probeProvider(base_url, api_key, provider_name?): Promise<ProbeResult>
addProvider(name, base_url, api_key): Promise<void>
switchModel(provider_name, model_id): Promise<void>

// Session
createSession(model?): Promise<SessionMeta>
listSessions(): Promise<SessionMeta[]>
getSession(id): Promise<SessionMeta>
abortSession(id): Promise<void>

// Prompt — returns raw Response untuk di-pipe ke consumeStream
sendPrompt(sessionId, content): Promise<Response>

// Context
contextAdd(sessionId, path, readonly?): Promise<void>
contextDrop(sessionId, path): Promise<void>
contextList(sessionId): Promise<ContextListResponse>

// Files
listProjectFiles(): Promise<ProjectFilesResponse>

// Config
getConfig(): Promise<ConfigResponse>
healthCheck(): Promise<boolean>
```

---

### `theme.ts` — Color Palette

```ts
C.bg     = "#0d0d0d"   // background utama
C.bg2    = "#141414"   // card / input / overlay
C.bg3    = "#1a1a1a"   // hover / selection
C.border = "#242424"
C.green  = "#a8ff60"
C.orange = "#fd971f"   // filename, provider name
C.pink   = "#f92672"   // error, keyword
C.purple = "#ae81ff"
C.cyan   = "#66d9e8"   // Ask mode
C.blue   = "#89d4f5"   // glyph ✦, user icon
C.white  = "#f8f8f2"   // teks utama
C.gray   = "#6b6b6b"   // teks sekunder
C.gray2  = "#3d3d3d"   // placeholder, dim
C.gray3  = "#2a2a2a"   // sangat dim
```

`MODE_COLOR` map: ask → cyan, edit-block → orange, edit-udiff → purple, edit-whole → pink.

`createMonokaiStyle()` / `getMonokaiStyle()` — `SyntaxStyle` object untuk syntax highlighting di chat. Monokai-based, cover semua token types + markdown markup.

---

### Components

#### `app.tsx`

Root layout. Column: `ChatView | EmptyState` → `CtxBar` → `ModelPicker (overlay)` → `InputBox`.

`ModelPicker` di-render hanya saat `state.showModelPicker !== false`, di-overlay di atas `InputBox`.

#### `chat.tsx`

Render semua messages. User message: box bg2 + glyph ✦. Assistant message: plain text dengan syntax highlighting via `@opentui/core`'s `Code` / `Markdown` renderables. Edit result (diff) ditampilkan setelah message selesai.

#### `input.tsx` — InputBox

Layout: slash menu (atas, conditional) + input box (bawah).

Input box berisi: glyph ✦ + `<input>` + meta row (mode · model).

**Slash autocomplete**: Dua mode — `command` (match `/...` tanpa spasi) dan `file` (match path setelah `/add` atau `/drop`). Tab → complete selection. Enter di command mode → complete. Enter di file mode dengan partial token → insert file, lanjut. Enter di file mode dengan trailing space → dismiss list, submit.

**`skipNextInput` flag**: Set true sebelum programmatic `inputRef.value = ""` untuk skip `handleInput` yang di-fire oleh perubahan value.

**Keyboard guard**: Seluruh input dinonaktifkan (`isDisabled()`) saat `ModelPicker` overlay aktif.

#### `model-picker.tsx` — ModelPicker

Overlay untuk dua mode: `add` (tambah provider baru) dan `switch` (pilih dari existing providers).

**Phases**: `provider-list → new-baseurl → new-apikey → loading → model-select`

**Single input pattern** (penting — lihat catatan @opentui di atas): Satu `<input>` untuk semua fase input teks. `_handleSubmit()` dispatch berdasarkan `phase()` saat itu. `inputRef.value = ""` reset manual antara fase.

**Provider list display**: model (kiri, putih) · nama provider (orange) · base_url (gray). `last_model` diambil dari `providers.json` via `/providers` endpoint.

#### `status.tsx`

`StatusBar` — satu baris paling bawah: mode · model · error (truncated 40 char) · "minimal" (kanan).

`CtxBar` — satu baris di atas InputBox, tampil hanya kalau ada context files. Daftar nama file (2 level terakhir) + total tokens (kanan). Hidden kalau context kosong.

---

## Slash Commands

| Command | Keterangan |
|---|---|
| `/add <file> [file2...]` | Tambah file ke context (batch support) |
| `/add -r <file>` | Tambah sebagai read-only |
| `/drop <file>` | Hapus dari context |
| `/ls` | List context files + token count |
| `/edit-block [prompt]` | Edit dengan SEARCH/REPLACE. Tanpa prompt → switch mode permanen |
| `/edit-udiff [prompt]` | Edit dengan unified diff |
| `/edit-whole [prompt]` | Rewrite seluruh file |
| `/ask` | Kembali ke ask mode |
| `/undo` | Rollback last edit |
| `/diff` | Tampilkan diff terakhir |
| `/commit [message]` | `git add -A && git commit -m ...` |
| `/run <cmd>` | Jalankan shell command (timeout 30s) |
| `/tokens` | Estimasi token usage |
| `/model` | Buka model picker (switch) |
| `/model-add` | Buka model picker (add provider) |
| `/clear` | Clear chat history |
| `/reset` | Clear chat + context |
| `/help` | Tampilkan help text |

---

## Config file format

**`~/.minimal/.env`**
```env
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_API_KEY=sk-or-...
LLM_MODEL=openai/gpt-4o

# Model aliases — /model fast, /model reason, dll
LLM_MODEL_FAST=glm-4.7-flash
LLM_MODEL_REASON=deepseek-r1

# Optional
LLM_TIMEOUT=60
LLM_MAX_TOKENS=8192
LLM_THINKING_BUDGET=5000
LLM_CONTEXT_WINDOW=128000
LLM_CONTEXT_WINDOW_FAST=32000   # per-alias override

# Provider API keys (di-generate otomatis oleh /model-add)
OPENROUTER_API_KEY=sk-or-...
MY_CUSTOM_PROVIDER_API_KEY=...
```

**`~/.minimal/providers.json`**
```json
[
  {
    "name": "OpenRouter",
    "base_url": "https://openrouter.ai/api/v1",
    "env_key": "OPENROUTER_API_KEY",
    "last_model": "openai/gpt-4o"
  }
]
```

---

## Quick start

```bash
# Backend
cd min/backend
pip install -r requirements.txt
python main.py

# TUI (terminal terpisah)
cd min/tui
bun install
bun run index.tsx

# CLI flags
bun run index.tsx --session <id>   # resume session
bun run index.tsx --model gpt-4o   # override model
```

First run tanpa `~/.minimal/.env` → wizard tanya base URL, API key, model.
