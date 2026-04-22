// status.tsx — status bar paling bawah: Ask · glm-5          minimal
// + ctx-bar di atas input: src/context.py applied · src/llm.py    3,080 tok
import { createMemo, For, Show } from "solid-js"
import { state } from "../state.ts"
import { C, MODE_COLOR } from "../theme.ts"

function fmtK(n: number): string {
  return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n)
}

// ── Status bar — paling bawah ─────────────────────────────────────────────────
// Ask · glm-5                                              minimal
export function StatusBar() {
  const modeColor = createMemo(() => MODE_COLOR[state.mode] ?? C.cyan)
  const modeLabel = createMemo(() => {
    if (state.streaming) return "Thinking..."
    const m: Record<string, string> = {
      "ask": "Ask", "edit-block": "Edit", "edit-udiff": "Edit", "edit-whole": "Edit",
    }
    return m[state.mode] ?? state.mode
  })

  return (
    <box
      width="100%"
      height={1}
      flexDirection="row"
      alignItems="center"
      backgroundColor={C.bg}
      paddingLeft={2}
      paddingRight={2}
    >
      <text fg={modeColor()}>{modeLabel()}</text>
      <text fg={C.gray2}>{" · "}</text>
      <text fg={C.gray}>{state.model || "—"}</text>
      <Show when={state.error}>
        <text fg={C.gray2}>{" · "}</text>
        <text fg={C.pink}>{state.error!.slice(0, 40)}</text>
      </Show>
      <box flexGrow={1} />
      <text fg={C.gray3}>minimal</text>
    </box>
  )
}

// ── Context bar — di atas input ───────────────────────────────────────────────
// src/context.py applied · src/llm.py                      3,080 tok
export function CtxBar() {
  const hasFiles = createMemo(() => state.contextFiles.length > 0)
  const tokStr   = createMemo(() =>
    state.totalTokens > 0 ? `${fmtK(state.totalTokens)} tok` : ""
  )

  return (
    <Show when={hasFiles()}>
      <box
        width="100%"
        height={1}
        flexDirection="row"
        alignItems="center"
        backgroundColor={C.bg}
        paddingLeft={2}
        paddingRight={2}
      >
        <For each={state.contextFiles}>
          {(f, i) => {
            const parts = f.path.replace(/\\/g, "/").split("/")
            const short = parts.slice(-2).join("/")
            return (
              <box flexDirection="row">
                <Show when={i() > 0}>
                  <text fg={C.gray3}>{" · "}</text>
                </Show>
                <text fg={C.gray}>{short}</text>
              </box>
            )
          }}
        </For>
        <box flexGrow={1} />
        <text fg={C.gray2}>{tokStr()}</text>
      </box>
    </Show>
  )
}
