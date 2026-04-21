// context.tsx — file context panel: daftar /ls dari state
// Tampil di sidebar kiri, update reaktif saat contextFiles berubah

import { createEffect } from "solid-js"
import { BoxRenderable, TextRenderable, ScrollBoxRenderable } from "@opentui/core"
import type { CliRenderer } from "@opentui/core"
import { state } from "../state.ts"

export function createContextPanel(renderer: CliRenderer): BoxRenderable {
  const ctx = renderer as any

  // Outer box — fixed width sidebar
  const panel = new BoxRenderable(ctx, {
    width: 28,
    flexGrow: 0,
    flexShrink: 0,
    flexDirection: "column",
    backgroundColor: "#16161e",
    border: ["right"],
    borderColor: "#3b3d57",
  })

  // Header
  const header = new TextRenderable(ctx, {
    content: "context",
    fg: "#565f89",
    height: 1,
    paddingX: 1,
  })

  // Scrollable file list
  const scroll = new ScrollBoxRenderable(ctx, {
    flexGrow: 1,
    scrollY: true,
    scrollX: false,
    stickyScroll: false,
  })

  // Content box inside scroll — gets rebuilt on state change
  const fileList = new BoxRenderable(ctx, {
    width: "100%",
    flexDirection: "column",
    paddingX: 1,
  })

  scroll.content.add(fileList)
  panel.add(header)
  panel.add(scroll)

  // Track rendered rows so we can clear/rebuild
  let rows: TextRenderable[] = []

  createEffect(() => {
    const files = state.contextFiles  // reactive read

    // Clear old rows
    for (const row of rows) {
      fileList.remove(row.id)
    }
    rows = []

    if (files.length === 0) {
      const empty = new TextRenderable(ctx, {
        content: "no files",
        fg: "#3b3d57",
        height: 1,
      })
      fileList.add(empty)
      rows.push(empty)
      return
    }

    for (const f of files) {
      const label = formatFile(f.path, f.readonly, f.token_count)
      const row = new TextRenderable(ctx, {
        content: label,
        fg: f.readonly ? "#565f89" : "#a9b1d6",
        height: 1,
      })
      fileList.add(row)
      rows.push(row)
    }
  })

  // Token total footer
  const footer = new TextRenderable(ctx, {
    content: "",
    fg: "#565f89",
    height: 1,
    paddingX: 1,
  })
  panel.add(footer)

  createEffect(() => {
    const total = state.totalTokens
    footer.content = total > 0 ? `${fmtK(total)} tokens` : ""
  })

  return panel
}

function formatFile(path: string, readonly: boolean, tokens: number): string {
  // Show only last 2 path segments to fit narrow panel
  const parts = path.replace(/\\/g, "/").split("/")
  const short = parts.slice(-2).join("/")
  const icon = readonly ? "○" : "●"
  const tok = tokens > 0 ? ` ${fmtK(tokens)}` : ""
  // Truncate to fit width=28 minus padding(2) minus icon(2) minus tok
  const maxName = 22 - tok.length
  const name = short.length > maxName ? "…" + short.slice(-(maxName - 1)) : short
  return `${icon} ${name}${tok}`
}

function fmtK(n: number): string {
  return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n)
}
