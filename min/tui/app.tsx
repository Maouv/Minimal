// app.tsx — root layout, susun semua components
// Layout: [context sidebar | chat column] + status bar atas + input bawah

import { BoxRenderable } from "@opentui/core"
import type { CliRenderer } from "@opentui/core"
import { createStatusBar } from "./components/status.tsx"
import { createContextPanel } from "./components/context.tsx"
import { createChatView } from "./components/chat.tsx"
import { createInputBox } from "./components/input.tsx"

export function mountApp(renderer: CliRenderer): void {
  const ctx = renderer as any
  const root = renderer.root

  // ── Root container: column (status | body | input) ──────────────────────
  const rootBox = new BoxRenderable(ctx, {
    width: "100%",
    height: "100%",
    flexDirection: "column",
    backgroundColor: "#1a1b26",
  })

  // 1. Status bar (top, fixed 1 row)
  const statusBar = createStatusBar(renderer)

  // 2. Body: row = [context panel | chat view]
  const body = new BoxRenderable(ctx, {
    flexGrow: 1,
    flexDirection: "row",
    overflow: "hidden",
  })

  const contextPanel = createContextPanel(renderer)
  const chatView = createChatView(renderer)

  body.add(contextPanel)
  body.add(chatView)

  // 3. Input box (bottom, shrinks to content)
  const inputBox = createInputBox(renderer)

  rootBox.add(statusBar)
  rootBox.add(body)
  rootBox.add(inputBox)

  root.add(rootBox)
}
