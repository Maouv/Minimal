// status.tsx — top status bar: mode | model | tokens | error
import { createMemo } from "solid-js"
import { state } from "../state.ts"

const MODE_COLOR: Record<string, string> = {
  "ask":        "#7aa2f7",
  "edit-block": "#e0af68",
  "edit-udiff": "#bb9af7",
  "edit-whole": "#f7768e",
}

function fmtK(n: number): string {
  return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n)
}

export function StatusBar() {
  const modeColor = createMemo(() => MODE_COLOR[state.mode] ?? "#c0caf5")
  const modelColor = createMemo(() => state.streaming ? "#7dcfff" : "#565f89")
  const tokens = createMemo(() => {
    const t = state.totalTokens > 0 ? `ctx:${fmtK(state.totalTokens)}` : ""
    const io = state.inputTokens > 0
      ? `  in:${fmtK(state.inputTokens)} out:${fmtK(state.outputTokens)}`
      : ""
    return t + io
  })

  return (
    <box
      width="100%"
      height={1}
      flexDirection="row"
      alignItems="center"
      backgroundColor="#1a1b26"
      paddingLeft={1}
      paddingRight={1}
    >
      <text fg={modeColor()}>{state.mode.toUpperCase()}</text>
      <text fg="#3b3d57">{"  │  "}</text>
      <text fg={modelColor()}>{state.model || "—"}</text>
      <box flexGrow={1} />
      {state.error && (
        <text fg="#f7768e">{`⚠ ${state.error.slice(0, 40)}  `}</text>
      )}
      <text fg="#565f89">{tokens()}</text>
    </box>
  )
}
