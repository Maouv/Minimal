// status.tsx — 1-baris status bar: mode | model | tokens
// Pattern: createEffect watches state → update TextRenderable property

import { createEffect } from "solid-js"
import { BoxRenderable, TextRenderable } from "@opentui/core"
import type { CliRenderer } from "@opentui/core"
import { state } from "../state.ts"

const MODE_COLOR: Record<string, string> = {
  "ask":        "#7aa2f7",
  "edit-block": "#e0af68",
  "edit-udiff": "#bb9af7",
  "edit-whole": "#f7768e",
}

export function createStatusBar(renderer: CliRenderer): BoxRenderable {
  const ctx = renderer as any

  const bar = new BoxRenderable(ctx, {
    width: "100%",
    height: 1,
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#1a1b26",
    paddingX: 1,
  })

  const modeText = new TextRenderable(ctx, {
    content: state.mode.toUpperCase(),
    fg: MODE_COLOR[state.mode] ?? "#c0caf5",
    flexShrink: 0,
  })

  const sep1 = new TextRenderable(ctx, { content: "  │  ", fg: "#3b3d57", flexShrink: 0 })

  const modelText = new TextRenderable(ctx, {
    content: state.model || "—",
    fg: "#565f89",
    flexShrink: 0,
  })

  const spacer = new BoxRenderable(ctx, { flexGrow: 1 })

  const errText = new TextRenderable(ctx, { content: "", fg: "#f7768e", flexShrink: 0, visible: false })

  const tokenText = new TextRenderable(ctx, {
    content: "",
    fg: "#565f89",
    flexShrink: 0,
  })

  bar.add(modeText)
  bar.add(sep1)
  bar.add(modelText)
  bar.add(spacer)
  bar.add(errText)
  bar.add(tokenText)

  createEffect(() => {
    const mode = state.mode
    modeText.content = mode.toUpperCase()
    modeText.fg = MODE_COLOR[mode] ?? "#c0caf5"
  })

  createEffect(() => { modelText.content = state.model || "—" })

  createEffect(() => {
    tokenText.content = formatTokens(state.totalTokens, state.inputTokens, state.outputTokens)
  })

  createEffect(() => {
    const err = state.error
    if (err) {
      errText.content = `⚠ ${trunc(err, 40)}  `
      errText.visible = true
    } else {
      errText.visible = false
    }
  })

  createEffect(() => {
    modelText.fg = state.streaming ? "#7dcfff" : "#565f89"
  })

  return bar
}

function formatTokens(total: number, input: number, output: number): string {
  if (total === 0 && input === 0) return ""
  const t = total > 0 ? `ctx:${fmtK(total)}` : ""
  const io = input > 0 ? `  in:${fmtK(input)} out:${fmtK(output)}` : ""
  return t + io
}

function fmtK(n: number): string {
  return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n)
}

function trunc(s: string, max: number): string {
  return s.length > max ? s.slice(0, max) + "…" : s
}
