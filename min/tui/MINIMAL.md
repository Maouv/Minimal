# TUI — MINIMAL.md

## Running

```bash
cd min/tui
bun install
bun run index.tsx

# Hot reload (re-runs on file change, useful for layout work)
bun --watch run index.tsx

# With options
bun run index.tsx --session <id>   # resume existing session
bun run index.tsx --model gpt-4o   # override active model for this run
```

Backend must be running on `localhost:4096` first. The TUI checks `/health` on startup and exits immediately if unreachable.

TypeScript typecheck (no emit):

```bash
cd min/tui
bunx tsc --noEmit
```

There are no TUI-side tests currently.

## Architecture

### Boot sequence (`index.tsx`)

```
parse CLI args (yargs)
  → healthCheck() — exits if backend not up
  → getConfig() — get active model
  → createSession() or getSession(--session id)
  → setState({ sessionId, model })
  → render(<App />, { exitOnCtrlC, clearOnShutdown })
```

### Component tree

```
App
├── EmptyState  (fallback when messages === 0, shows logo)
├── ChatView    (scrollbox, renders message list)
├── CtxBar      (1-line bar above input, hidden when no context files)
├── ModelPicker (overlay, rendered only when state.showModelPicker !== false)
└── InputBox    (always mounted at bottom)
```

`ModelPicker` is rendered in the column between `CtxBar` and `InputBox` — it visually floats above the input area. When it's visible, `InputBox` disables its `<input>` (`focused={false}`, grayed out).

### Data flow

```
InputBox.handleSubmit(raw)
  │
  ├─ /model, /model-add  →  setState("showModelPicker", "switch"|"add")
  │                          (ModelPicker takes over, InputBox disables itself)
  │
  └─ everything else     →  sendPrompt(sessionId, raw)  [client.ts]
                              → POST /session/:id/init
                              → Response piped to consumeStream()  [stream.ts]
                                → parses SSE blocks
                                → writes to Solid store (state.ts)
                                → ChatView re-renders reactively
```

### State (`state.ts`)

Single Solid `createStore` — all components read from here, nothing holds local state for shared concerns.

Key fields to know:

| Field | Type | Notes |
|---|---|---|
| `streaming` | `boolean` | True while SSE stream is open. InputBox shows "Thinking..." and Enter aborts instead of sends |
| `showModelPicker` | `"switch" \| "add" \| false` | Controls ModelPicker overlay and InputBox disabled state |
| `messages` | `Message[]` | Append-only during a session. Max 50 rendered in DOM at once (older ones hidden, still in array) |
| `mode` | `Mode` | Ask or edit variant. Updated by `mode` SSE event from backend |
| `contextFiles` | `ContextFile[]` | Updated by `context` SSE event after every /add and /drop |

### SSE stream (`stream.ts`)

`consumeStream(response)` takes the raw `fetch` Response and parses the SSE wire format manually (split on `\n\n`, extract `event:` and `data:` lines).

Two things worth knowing:

**Token throttle**: LLM tokens arrive much faster than the terminal can render. Tokens are buffered in a local string and flushed to Solid state every 32ms (~30 FPS). Without this, hundreds of reactive updates per second cause visible lag.

**Heartbeat**: A 30-second timer resets on every event including `ping`. If it fires, the stream is considered dead and `streaming` is set to false. The backend sends `ping` events every 2 seconds.

### @opentui — critical notes

`@opentui/core` + `@opentui/solid` v0.1.102. Documentation is sparse; the notes below are sourced from the compiled library code.

**Never log to stdout.** `console.log()` corrupts the terminal renderer. Use `console.error()` or write to a file.

**`jsxImportSource` is `@opentui/solid`** (set in `tsconfig.json`). This is required — JSX elements (`<box>`, `<text>`, `<input>`, etc.) are not HTML elements. They map to @opentui renderables.

**The single-input rule.** @opentui's `_removeNode()` calls `destroyRecursively()` via `process.nextTick` (async), but `onSubmit` can still fire before cleanup completes. If two `<input>` nodes briefly co-exist (e.g. inside a `<Show>` that toggles), the renderer crashes at `renderer.ts:2609`. 

**Fix pattern used in `model-picker.tsx`**: use ONE `<input>` that stays mounted across all phases. Switch phases by changing `placeholder` and dispatching in `onSubmit` based on current phase. Reset value manually with `inputRef.value = ""` between phases.

**`useKeyboard` fires before `onSubmit`**. Call `key.preventDefault()` to block the keypress from reaching the focused input — used in `InputBox` to intercept ↑/↓/Tab/Enter for the autocomplete menu.

**`focused` prop + programmatic focus**: The `focused` prop on `<input>` auto-focuses on mount. Programmatic focus must be wrapped in `setTimeout(..., 50)` — the renderer needs one tick to attach the node before focus is accepted.

**Available `<input>` props:**
```tsx
<input
  ref={ref}
  flexGrow={1}
  placeholder="..."
  placeholderColor="#hex"
  backgroundColor="#hex"
  textColor="#hex"
  focusedBackgroundColor="#hex"
  focusedTextColor="#hex"
  focused            // boolean — auto-focus on mount
  onInput={(val: string) => void}   // fires on every keystroke
  onSubmit={(val: string) => void}  // fires on Enter
/>
```

**Layout** uses Yoga (Flexbox). Supported props: `flexDirection`, `flexGrow`, `flexShrink`, `flexWrap`, `alignItems`, `justifyContent`, `width`, `height`, `padding*`, `margin*`. `width="100%"` works; percentage heights generally do not.

**`<scrollbox>`** — scrollable container. Use `scrollY`, `stickyScroll`, `stickyStart="bottom"` for a chat-style view that pins to the bottom as content grows.

**`<markdown>`** — renders markdown with syntax highlighting. Takes `content`, `syntaxStyle`, `fg`, `streaming` (boolean — disables some rendering optimizations while content is still arriving), `conceal` (hides markdown markup characters).

### Autocomplete in `InputBox`

Two modes, selected by `acMode`:

- `command` — triggers when input starts with `/` and has no space. Matches against `SLASH_COMMANDS`. Tab or Enter selects and completes the full command string.
- `file` — triggers after `/add `, `/add -r `, `/drop `. For `/add`, reads from `fileCache` (populated once via `GET /project/files`). For `/drop`, reads from `state.contextFiles`. Enter with a partial last token inserts the selected file and keeps input open for batch add. Enter with a trailing space submits.

`skipNextInput` flag: set to `true` before programmatic `inputRef.value = ""` to suppress the `onInput` handler that fires from the value change.

### Theme (`theme.ts`)

All colors are hex strings — no named colors in @opentui. Import `C` for the palette and `MODE_COLOR` for mode → color mapping. `getMonokaiStyle()` returns a `SyntaxStyle` object for use with `<markdown syntaxStyle={...}>`.
