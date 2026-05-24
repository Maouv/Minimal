# REFACTOR v2 — Bottleneck Fixes + New Feature

## 1. TUI Lag di Sesi Panjang

**Problem**: Semakin panjang sesi, TUI makin lag. Bukan RAM — tapi render overhead.

**Root cause**:
- `stripEditBlocks()` di `chat.tsx` dipanggil ulang setiap token masuk (regex on every render)
- `appendToken()` trigger re-render seluruh `<AiMsg>` component
- Solid store diffing tetap jalan untuk semua messages meskipun `MESSAGE_CAP=50`

**Solution**:

1. **Freeze done messages**: Setelah `done=true`, message pakai `displayContent` yang sudah di-compute sekali. Tidak subscribe ke `msg.content` lagi.

2. **Split components**:
   - `<FrozenMsg>` — untuk messages yang sudah done. Tidak reactive, pure render.
   - `<StreamingMsg>` — hanya untuk message terakhir yang sedang streaming. Satu-satunya yang re-render per token.

3. **Batch token flush**: Naikkan `TOKEN_FLUSH_MS` dari 32ms → 80ms (~12 FPS). Text streaming tidak perlu 30 FPS. Kurangi store update frequency 2.5x.

4. **Virtualization**: Hanya mount messages yang visible di viewport. Messages di luar viewport = unmounted. Scroll up → lazy mount.

---

## 2. Startup Lama

**Problem**: Ketik `minimal`, TUI muncul lama. Backend polling 20x @ 0.5s = max 10s.

**Root cause**:
- Python cold start: import `openai`, `fastapi`, `uvicorn` semua eager di module level
- `config.ensure()` di lifespan blocking
- TUI blocked sampai backend fully ready

**Solution**:

1. **Lazy imports**: Pindahkan heavy imports (`openai`, vendor modules) ke dalam fungsi yang membutuhkan. Health endpoint `/health` harus respond tanpa perlu semua module loaded.

2. **Faster polling**: `sleep 0.1` instead of `0.5`, max 30 iterations (3s max). Backend Python seharusnya ready <2s.

3. **Parallel TUI mount**: TUI mount langsung dengan splash/loading state. Poll health di background. Begitu backend ready → enable input. User lihat UI instant, bukan blank terminal.

4. **Persistent backend**: Jangan kill backend saat TUI exit (sudah partially implemented). Reuse across sessions — subsequent launches = instant (no cold start).

---

## 3. AI Diam Setelah Edit

**Problem**: AI implement edit, lalu diam. Tidak komentar apa yang diubah. User harus tanya manual. AI juga tidak tau apakah edit berhasil atau gagal.

**Root cause**: Setelah `stream_chat()` selesai dan edits applied, backend hanya emit `applied_summary` event. Tidak ada feedback loop ke AI.

**Solution — Follow-up turn**:

Setelah edits applied, backend kirim satu follow-up message ke AI:

```
[System] Edit results:
- context.py: ✓ applied (+5 -3)  
- llm.py: ✗ failed (could not find SEARCH block match)

Briefly confirm what you changed and note any failures.
```

Backend stream response AI ini sebagai continuation dari message yang sama.

**Kenapa bukan prompt instruction**: Sudah dicoba, AI sering ignore. Follow-up turn = AI *harus* respond karena ada message baru yang butuh acknowledgment.

**Cost**: ~100-200 extra output tokens. Worth it untuk UX.

**Implementation**:
- Di `api/prompt.py`, setelah edit loop selesai:
  1. Build summary string dari `applied_files` + `failed_files`
  2. Append sebagai system/user message ke conversation
  3. Call `llm.stream_chat()` kedua kali (short, no edit mode)
  4. Stream response ke TUI sebagai continuation

---

## 4. Thinking Indicator

**Problem**: Saat AI mikir, cuma blank atau "thinking..." di pojok. Tidak akurat, tidak informatif.

**Solution — ✦ animated spinner + token counter**:

### Animasi

```
Frame 1: ✦ · · ·
Frame 2: · ✦ · ·
Frame 3: · · ✦ ·
Frame 4: · · · ✦
(loop ke frame 1)
```

Interval: ~180ms. Satu arah, wrap around (tidak bounce).

### Layout

```
✦ · · ·  Ctx 12.4k · Out 847
```

- `Ctx 12.4k` = total context/input tokens yang dikirim ke LLM
- `Out 847` = output tokens sejauh ini (client-side count: chars received ÷ 4)
- Update `Out` real-time selama streaming

### Behavior

| State | Display |
|-------|---------|
| Request sent, no response yet | `✦ · · ·  Ctx 12.4k · Out 0` (animating) |
| Tokens streaming in | Indicator hilang, content muncul. Token counter tetap update di status bar |
| Thinking content (reasoning model) | `· · ✦ ·  Ctx 12.4k · Out 0` (animating, thinking content dimmed di background) |

### Placement

Di area message (bukan status bar). Muncul sebagai placeholder di posisi dimana AI message akan muncul. Begitu token pertama masuk → replace dengan actual content.

---

## 5. Multi-file Edit Kadang Cuma 1 File

**Problem**: Kalau AI edit 2 file sekaligus, kadang cuma file pertama yang ke-apply.

**Root cause** di `coder.py` `_apply_editblock()`:

```python
for fname, block_list in by_file.items():
    for search, replace in block_list:
        new_content = replace_most_similar_chunk(content, search, replace)
        if new_content is None:
            results.append(EditResult(..., success=False, error=...))
            return results  # ← BUG: early return, file lain tidak diproses
```

**Solution**:

```python
for fname, block_list in by_file.items():
    for search, replace in block_list:
        new_content = replace_most_similar_chunk(content, search, replace)
        if new_content is None:
            results.append(EditResult(..., success=False, error=...))
            break  # skip remaining blocks for THIS file, continue to next file
        content = new_content
    else:
        # all blocks succeeded for this file
        diff = make_diff(original_content, content, fname)
        results.append(EditResult(..., success=True))
```

`break` instead of `return`. File lain tetap diproses.

---

## 6. `/think` — Brainstorming / Investigation Mode

**Problem**: Minimal hanya punya `/ask` (no edit) dan `/edit-*` (edit). Tidak ada mode untuk investigasi mendalam — baca file, run command, analisis arsitektur, propose solutions. User harus manual `/add` file, `/run` command, copy-paste results.

### Konsep

`/think [prompt]` — mode agentic investigation. AI bisa:
- Baca file (tanpa harus user `/add` dulu)
- Run shell commands (grep, find, test, dll)
- Analisis output
- Loop sampai punya jawaban confident
- **Tidak edit file** — output = analisis + rekomendasi

### Tool Protocol

Tidak pakai function calling API (tidak semua model support). Pakai text-based structured output:

```xml
<tool>read_file</tool>
<args>{"path": "min/backend/main.py", "lines": "1-30"}</args>
```

```xml
<tool>run</tool>
<args>{"cmd": "grep -rn 'import openai' min/backend/"}</args>
```

```xml
<tool>ls</tool>
<args>{"path": "min/backend/api"}</args>
```

```xml
<tool>grep</tool>
<args>{"pattern": "async def", "path": "min/backend/"}</args>
```

Backend parse tool blocks dari AI response, execute, inject result ke conversation, re-prompt AI.

### Available Tools

| Tool | Args | Description |
|------|------|-------------|
| `read_file` | `path`, `lines?` (e.g. "1-50") | Baca file, optional line range |
| `run` | `cmd` | Execute shell command (timeout 10s) |
| `grep` | `pattern`, `path` | Search pattern in files |
| `ls` | `path`, `depth?` | List directory |

### Token Budget

Default: **20k tokens** (configurable di `~/.minimal/.env` → `THINK_BUDGET=20000`).

**Warning thresholds** — backend inject system message ke AI:

| Remaining | Injected message |
|-----------|-----------------|
| 50% (10k) | `[System: 50% budget remaining. Focus your investigation.]` |
| 25% (5k) | `[System: 25% budget remaining. Start forming your conclusion.]` |
| 10% (2k) | `[System: Almost out of budget. Conclude now.]` |
| 0% | Force stop stream. Backend emit done event. |

**AI self-terminate**: AI boleh stop kapan saja kalau merasa sudah cukup. Pintar model = stop early, hemat token. Budget = safety net untuk model yang loop.

**User extend**: Setelah AI conclude, user bisa reply lagi → budget reset fresh. Context sebelumnya preserved (progressive summary).

### Progressive Summarization

Setiap 3-4 tool iterations, backend compress accumulated findings:

```
[System summary of investigation so far]:
- backend.sh polls 20x @ 0.5s (max 10s wait)
- main.py imports openai at module level (cold start ~1.5s)
- config.ensure() blocks lifespan

Continue investigating or conclude.
```

Ini prevent context bloat di iteration lanjut. AI punya full picture tanpa re-read semua raw tool outputs.

### Agent Loop (Backend)

```python
async def _handle_think(session, prompt, budget=20000):
    messages = [system_prompt, user_prompt]
    total_output_tokens = 0
    
    while total_output_tokens < budget:
        # Check thresholds, inject warnings
        remaining = budget - total_output_tokens
        inject_warning_if_needed(messages, remaining, budget)
        
        # Stream AI response
        response = ""
        async for token, usage, thinking in llm.stream_chat(messages, model, system):
            if thinking:
                yield sse("thinking", {"content": thinking})
            if token:
                response += token
                # Don't stream tool-request tokens to user
                if not currently_in_tool_block(response):
                    yield sse("token", {"content": token})
        
        total_output_tokens += count_tokens(response)
        
        # Check for tool calls
        tool_calls = parse_tool_blocks(response)
        if not tool_calls:
            # AI self-terminated — final answer
            break
        
        # Execute tools
        for tool in tool_calls:
            yield sse("thinking", {"content": f"running {tool.name}..."})
            result = await execute_tool(tool)
            messages.append({"role": "user", "content": f"[Tool result: {tool.name}]\n{result}"})
        
        # Progressive summarization every 3-4 iterations
        if should_summarize(messages):
            messages = compress_messages(messages)
    
    yield sse("done", {...})
```

### TUI Display

Saat AI investigating:
```
· ✦ · ·  think · Ctx 8.2k · Used 4.1k/20k
```

Saat AI running tool (dimmed, below spinner):
```
· · ✦ ·  think · Ctx 8.2k · Used 4.1k/20k
  ╰─ reading min/backend/main.py...
```

Saat AI streaming final answer:
- Spinner hilang
- Content stream normal
- Token counter tetap update

### System Prompt (`think.md`)

```markdown
You are in investigation/brainstorming mode.

Your job: investigate the codebase, analyze problems, and propose solutions.
Do NOT edit files. Only read, run commands, and reason.

You have tools available. To use them, output:
<tool>tool_name</tool>
<args>{"key": "value"}</args>

Available tools:
- read_file: {"path": "...", "lines": "start-end" (optional)}
- run: {"cmd": "..."}  (timeout 10s, no interactive)
- grep: {"pattern": "...", "path": "..."}
- ls: {"path": "...", "depth": 1}

Rules:
- Use tools to gather evidence before making claims
- Read only what you need (use line ranges for large files)
- Stop when you have enough information to answer confidently
- Structure your final answer with clear options and recommendations
- Be opinionated — recommend the best path
```

### Command Variants

```
/think [prompt]              default budget (20k)
/think --deep [prompt]       extended budget (50k) for complex investigations
```

### Mode State

- `s.mode = "think"` 
- Status bar indicator: `◆ think` (amber/yellow color)
- Stays in think mode until user switches (`/ask`, `/edit-*`)

---

## 7. Token Counting Akurat

**Problem**: Sekarang token count pakai `len(text) // 4` — bisa off 30-50%. Untuk `/think` budget system, ini critical. Warning thresholds jadi meaningless kalau counting ngaco.

**Current state**:
- `context.py` → `_estimate_tokens()` = `len(text) // 4`
- `done` event dari backend sudah report `input_tokens` + `output_tokens` (dari API response, akurat)
- Tapi pre-request estimation (context files, chat history) masih kasar

**Solution**:

1. **Post-request (display)**: Pakai `usage` dari API response — sudah ada, 100% akurat. Ini yang ditampilkan di `Ctx X · Out Y`.

2. **Pre-request estimation (budget)**: Install `tiktoken` (lightweight, ~2MB). Pakai `cl100k_base` encoding sebagai universal approximation.
   ```python
   import tiktoken
   _enc = tiktoken.get_encoding("cl100k_base")
   
   def count_tokens(text: str) -> int:
       return len(_enc.encode(text))
   ```
   Akurat ±10% untuk semua model (vs ±50% dengan `÷4`).

3. **Cache token counts**: Saat `/add` file, hitung sekali dengan tiktoken, simpan di `ContextManager.token_counts`. Tidak perlu re-count setiap request.

4. **Budget tracking di `/think`**: Pakai tiktoken untuk hitung accumulated tool results + AI responses. Warning thresholds jadi akurat.

5. **Fallback**: Kalau tiktoken tidak available (install gagal), fallback ke `len(text) // 3` (slightly better than `÷4` untuk code).

---

## 8. Context File List Overflow

**Problem**: `CtxBar` render semua files dalam 1 baris (`height={1}`). Kalau 5+ files di-add, teks overflow horizontal — numpuk, tidak kebaca, menghalangi layar.

**Root cause**: Tidak ada truncation, tidak ada max display count, tidak ada overflow handling.

**Solution**:

1. **Max 3 files displayed**, sisanya collapsed:
   ```
   context.py · llm.py · coder.py +4 more     12.4k tok
   ```

2. **Basename only** (bukan 2-segment path) kecuali ada name collision:
   ```
   // Before (current):
   backend/context.py · backend/llm.py · backend/coder.py
   
   // After:
   context.py · llm.py · coder.py
   ```
   Kalau ada collision (e.g. `backend/config.py` + `tui/config.py`), baru tampilkan parent:
   ```
   backend/config.py · tui/config.py
   ```

3. **Overflow protection**: Container pakai `overflow="hidden"` + file terakhir yang visible pakai `truncate`.

4. **Implementation** di `CtxBar`:
   ```tsx
   const MAX_DISPLAY = 3;
   const visible = files.slice(0, MAX_DISPLAY);
   const remaining = files.length - MAX_DISPLAY;
   
   // render visible files...
   {remaining > 0 && <text fg={C.gray3}>{` +${remaining}`}</text>}
   ```

---

## Priority & Effort

| # | Feature | Impact | Effort |
|---|---------|--------|--------|
| 5 | Multi-file fix | High (data correctness) | Trivial |
| 7 | Token counting akurat | High (foundation for #6) | Low |
| 8 | Context list overflow | Medium (visual bug) | Low |
| 3 | Post-edit AI response | High (UX) | Low |
| 4 | ✦ thinking indicator | Medium (UX polish) | Low |
| 1 | TUI lag fix | High (usability) | Medium |
| 2 | Startup speed | Medium (DX) | Medium |
| 6 | `/think` mode | High (new capability) | High |

## Implementation Order

1. **#5** — one-line fix, immediate
2. **#7** — tiktoken integration, replace `÷4` estimator
3. **#8** — truncate CtxBar, max 3 files + overflow
4. **#3** — follow-up turn in `api/prompt.py`
5. **#4** — ✦ spinner component + token counter
6. **#1** — refactor chat.tsx + state.ts (FrozenMsg/StreamingMsg split)
7. **#2** — refactor launcher + main.py (lazy imports, parallel mount)
8. **#6** — `/think` command, agent loop, tools, budget system
