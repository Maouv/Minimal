// chat.tsx — scrollable message history + diff display
// Reaktif: tiap message baru → tambah row ke scroll, streaming token → update TextRenderable

import { createEffect } from "solid-js"
import { BoxRenderable, TextRenderable, ScrollBoxRenderable, DiffRenderable } from "@opentui/core"
import type { CliRenderer } from "@opentui/core"
import { state, type Message } from "../state.ts"

// ── Per-message row renderable ────────────────────────────────────────────────

interface MessageRow {
  msgIdx: number
  container: BoxRenderable
  bodyText: TextRenderable
  diffBoxes: DiffRenderable[]
}

// ── Main ─────────────────────────────────────────────────────────────────────

export function createChatView(renderer: CliRenderer): ScrollBoxRenderable {
  const ctx = renderer as any as import("@opentui/core").CliRenderer

  const scroll = new ScrollBoxRenderable(ctx, {
    flexGrow: 1,
    scrollY: true,
    scrollX: false,
    stickyScroll: true,    // auto-scroll ke bawah saat ada token baru
    stickyStart: "bottom",
    backgroundColor: "#1a1b26",
  })

  const rows: MessageRow[] = []

  // Watch messages array — tambah row baru kalau ada message baru
  // Watch message count — tambah row baru
  createEffect(() => {
    const newCount = state.messages.length  // reactive trigger

    for (let i = rows.length; i < newCount; i++) {
      const msg = state.messages[i]
      const row = buildMessageRow(ctx, msg, i)
      scroll.content.add(row.container)
      rows.push(row)
    }
  })

  // Watch streaming content — update token per token
  createEffect(() => {
    if (!state.streaming) return
    const msgs = state.messages
    if (rows.length === 0) return
    const last = rows[rows.length - 1]
    const msg = msgs[last.msgIdx]
    if (msg && !msg.done) {
      last.bodyText.content = msg.content
    }
  })

  // Watch setiap message untuk finalize (done + edits)
  createEffect(() => {
    for (const row of rows) {
      const msg = state.messages[row.msgIdx]
      if (!msg) continue

      // Update text
      row.bodyText.content = msg.content

      // Kalau done + ada edits → render diffs (sekali saja)
      if (msg.done && msg.edits && row.diffBoxes.length === 0) {
        for (const edit of msg.edits) {
          const diffBox = new DiffRenderable(ctx, {
            diff: edit.diff,
            width: "100%",
            view: "unified",
            fg: edit.success ? "#a9b1d6" : "#f7768e",
          })
          row.container.add(diffBox)
          row.diffBoxes.push(diffBox)
        }
      }
    }
  })

  return scroll
}

// ── Build a single message row ────────────────────────────────────────────────

function buildMessageRow(ctx: any, msg: Message, idx: number): MessageRow {
  const isUser = msg.role === "user"
  const isSystem = msg.role === "system"

  // Container per message
  const container = new BoxRenderable(ctx, {
    width: "100%",
    flexDirection: "column",
    paddingX: 2,
    paddingY: 1,
    borderColor: "#3b3d57",
    border: isUser ? [] : ["bottom"],
    backgroundColor: isUser ? "#1e2030" : "#1a1b26",
  })

  // Role label
  const roleLabel = new TextRenderable(ctx, {
    content: rolePrefix(msg.role),
    fg: roleFg(msg.role),
    height: 1,
    flexShrink: 0,
  })

  // Message body — mutable, gets updated via streaming
  const bodyText = new TextRenderable(ctx, {
    content: msg.content,
    fg: isSystem ? "#565f89" : "#c0caf5",
    width: "100%",
    flexWrap: "wrap",
  })

  container.add(roleLabel)
  container.add(bodyText)

  return { msgIdx: idx, container, bodyText, diffBoxes: [] }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function rolePrefix(role: string): string {
  switch (role) {
    case "user":      return "▸ you"
    case "assistant": return "▸ min"
    case "system":    return "▸ sys"
    default:          return "▸ " + role
  }
}

function roleFg(role: string): string {
  switch (role) {
    case "user":      return "#7aa2f7"
    case "assistant": return "#9ece6a"
    case "system":    return "#565f89"
    default:          return "#a9b1d6"
  }
}
