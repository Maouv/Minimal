// status.tsx — status bar atas (mode + model) dan footer bawah (tokens + context files)
import { createMemo, For, Show } from "solid-js"
import { state } from "../state.ts"
import { MK, MODE_COLOR } from "../theme.ts"

function fmtK(n: number): string {
  return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n)
}

// Bar atas: MODE │ model name               error
export function StatusBar() {
  const modeColor = createMemo(() => MODE_COLOR[state.mode] ?? MK.white)
  const modelColor = createMemo(() => state.streaming ? MK.orange : MK.comment)

  return (
    <box
      width="100%"
      height={1}
      flexDirection="row"
      alignItems="center"
      backgroundColor={MK.bg2}
      paddingLeft={1}
      paddingRight={1}
    >
      {/* Mode badge */}
      <text fg={modeColor()} bold>{state.mode.toUpperCase()}</text>
      <text fg={MK.border}>{" │ "}</text>
      <text fg={modelColor()}>{state.model || "—"}</text>

      <box flexGrow={1} />

      {/* Error */}
      <Show when={state.error}>
        <text fg={MK.pink}>{`⚠ ${state.error!.slice(0, 50)}`}</text>
      </Show>
    </box>
  )
}

// Footer bawah: context files applied · other.py          3,080 tok
export function FooterBar() {
  const tokStr = createMemo(() => {
    const parts: string[] = []
    if (state.totalTokens > 0) parts.push(`ctx:${fmtK(state.totalTokens)}`)
    if (state.inputTokens > 0) parts.push(`in:${fmtK(state.inputTokens)}`)
    if (state.outputTokens > 0) parts.push(`out:${fmtK(state.outputTokens)}`)
    return parts.join("  ")
  })

  const ctxFiles = createMemo(() => state.contextFiles.slice(0, 3))

  return (
    <box
      width="100%"
      height={1}
      flexDirection="row"
      alignItems="center"
      backgroundColor={MK.bg2}
      paddingLeft={1}
      paddingRight={1}
    >
      {/* Context files — compact list */}
      <Show
        when={ctxFiles().length > 0}
        fallback={<text fg={MK.border}>no context</text>}
      >
        <For each={ctxFiles()}>
          {(f, i) => {
            const parts = f.path.replace(/\\/g, "/").split("/")
            const short = parts.slice(-2).join("/")
            return (
              <box flexDirection="row">
                <Show when={i() > 0}>
                  <text fg={MK.border}>{" · "}</text>
                </Show>
                <text fg={f.readonly ? MK.comment : MK.cyan}>{short}</text>
              </box>
            )
          }}
        </For>
        <Show when={state.contextFiles.length > 3}>
          <text fg={MK.border}>{` +${state.contextFiles.length - 3}`}</text>
        </Show>
      </Show>

      <box flexGrow={1} />

      {/* Token counter */}
      <text fg={MK.comment}>{tokStr()}</text>
    </box>
  )
}
