// input.tsx — prompt textarea + slash command autocomplete
// Paling complex: handle submit, slash detection, autocomplete overlay

import { createEffect, createSignal } from "solid-js"
import { BoxRenderable, TextRenderable, InputRenderable } from "@opentui/core"
import type { CliRenderer } from "@opentui/core"
import { state, setState, pushMessage } from "../state.ts"
import { sendPrompt, abortSession, contextAdd, contextDrop } from "../client.ts"
import { consumeStream, setRenderer } from "../stream.ts"

// ── Slash commands ─────────────────────────────────────────────────────────────

const SLASH_COMMANDS = [
  { cmd: "/add",   desc: "add file to context" },
  { cmd: "/drop",  desc: "remove file from context" },
  { cmd: "/ls",    desc: "list context files" },
  { cmd: "/clear", desc: "clear messages" },
  { cmd: "/undo",  desc: "undo last edit" },
  { cmd: "/help",  desc: "show help" },
  { cmd: "/mode",  desc: "switch edit mode" },
]

// ── Main ─────────────────────────────────────────────────────────────────────

export function createInputBox(renderer: CliRenderer): BoxRenderable {
  const ctx = renderer as any as import("@opentui/core").CliRenderer

  // Outer: input area at bottom
  const wrapper = new BoxRenderable(ctx, {
    width: "100%",
    flexDirection: "column",
    flexShrink: 0,
    border: ["top"],
    borderColor: "#3b3d57",
    backgroundColor: "#1a1b26",
  })

  // Autocomplete overlay — shown above input when typing /
  const autocomplete = new BoxRenderable(ctx, {
    width: "100%",
    flexDirection: "column",
    backgroundColor: "#1e2030",
    border: ["bottom"],
    borderColor: "#3b3d57",
    visible: false,
  })

  // Input row: prompt glyph + textarea
  const inputRow = new BoxRenderable(ctx, {
    width: "100%",
    flexDirection: "row",
    alignItems: "center",
    height: 3,
    paddingX: 1,
  })

  // Prompt glyph
  const glyph = new TextRenderable(ctx, {
    content: "›",
    fg: "#7aa2f7",
    flexShrink: 0,
    marginRight: 1,
    height: 1,
  })

  // Single-line input
  const input = new InputRenderable(ctx, {
    flexGrow: 1,
    placeholder: "ask or /command…",
    placeholderColor: "#3b3d57",
    backgroundColor: "#1a1b26",
    textColor: "#c0caf5",
    focusedBackgroundColor: "#1a1b26",
    focusedTextColor: "#c0caf5",
  })

  input.on("enter", () => handleSubmit())
  input.on("return", () => handleSubmit())

  inputRow.add(glyph)
  inputRow.add(input)
  wrapper.add(autocomplete)
  wrapper.add(inputRow)

  // ── Autocomplete rows ───────────────────────────────────────────────────────
  const [acItems, setAcItems] = createSignal<typeof SLASH_COMMANDS>([])
  const [acSelected, setAcSelected] = createSignal(0)
  let acRows: BoxRenderable[] = []

  createEffect(() => {
    const items = acItems()

    // Clear old rows
    for (const row of acRows) {
      autocomplete.remove(row.id)
    }
    acRows = []

    autocomplete.visible = items.length > 0

    items.forEach((item, i) => {
      const row = new BoxRenderable(ctx, {
        width: "100%",
        flexDirection: "row",
        height: 1,
        paddingX: 2,
        backgroundColor: i === acSelected() ? "#2a2b40" : "#1e2030",
      })
      const cmdT = new TextRenderable(ctx, { content: item.cmd, fg: "#7aa2f7", flexShrink: 0, marginRight: 2 })
      const descT = new TextRenderable(ctx, { content: item.desc, fg: "#565f89", flexGrow: 1 })
      row.add(cmdT)
      row.add(descT)
      autocomplete.add(row)
      acRows.push(row)
    })
  })

  // ── Input change → slash detection ─────────────────────────────────────────
  input.on("input", () => {
    const val: string = input.value

    if (val.startsWith("/") && !val.includes(" ")) {
      const matches = SLASH_COMMANDS.filter(c => c.cmd.startsWith(val))
      setAcItems(matches)
      setAcSelected(0)
    } else {
      setAcItems([])
    }
  })

  // ── Key handling for autocomplete navigation ────────────────────────────────
  renderer.keyInput.on("keypress", (key) => {
    const items = acItems()
    if (items.length === 0) return false

    if (key.name === "up") {
      setAcSelected(s => Math.max(0, s - 1))
      return true
    }
    if (key.name === "down") {
      setAcSelected(s => Math.min(items.length - 1, s + 1))
      return true
    }
    if (key.name === "tab") {
      // Complete the slash command
      input.value = items[acSelected()].cmd + " "
      setAcItems([])
      return true
    }
    if (key.name === "escape") {
      setAcItems([])
      return true
    }
    return false
  })

  // ── Disable input while streaming ──────────────────────────────────────────
  createEffect(() => {
    if (state.streaming) {
      glyph.fg = "#e0af68"
      glyph.content = "⊙"
    } else {
      glyph.fg = "#7aa2f7"
      glyph.content = "›"
    }
  })

  // ── Submit handler ─────────────────────────────────────────────────────────
  async function handleSubmit() {
    const raw = input.value.trim()
    process.stderr.write(`[debug] handleSubmit called, raw="${raw}"\n`)
    if (!raw) return
    if (state.streaming) {
      // Ctrl+C style abort
      if (state.sessionId) await abortSession(state.sessionId).catch(() => {})
      setState("streaming", false)
      return
    }

    input.value = ""
    setAcItems([])

    // Slash command — send as prompt (backend handles /commands)
    if (!state.sessionId) {
      setState("error", "no active session")
      return
    }

    const idx = pushMessage("user", raw)
    process.stderr.write(`[debug] pushMessage idx=${idx}, messages.length=${state.messages.length}\n`)

    try {
      const response = await sendPrompt(state.sessionId, raw)
      process.stderr.write(`[debug] sendPrompt ok, consuming stream...\n`)
      await consumeStream(response)
      process.stderr.write(`[debug] consumeStream done\n`)
    } catch (err) {
      process.stderr.write(`[debug] error: ${err}\n`)
      setState("error", String(err))
      setState("streaming", false)
    }
  }

  // Pass renderer to stream for manual redraw
  setRenderer(renderer)

  // Auto-focus input on mount
  input.focus()

  return wrapper
}
