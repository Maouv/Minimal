// context.tsx — sidebar file list
import { For, createMemo } from "solid-js"
import { state } from "../state.ts"

function fmtK(n: number): string {
  return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n)
}

function formatFile(path: string, readonly: boolean, tokens: number): string {
  const parts = path.replace(/\\/g, "/").split("/")
  const short = parts.slice(-2).join("/")
  const icon = readonly ? "○" : "●"
  const tok = tokens > 0 ? ` ${fmtK(tokens)}` : ""
  const maxName = 22 - tok.length
  const name = short.length > maxName ? "…" + short.slice(-(maxName - 1)) : short
  return `${icon} ${name}${tok}`
}

export function ContextPanel() {
  const total = createMemo(() => state.totalTokens)

  return (
    <box
      width={28}
      flexGrow={0}
      flexShrink={0}
      flexDirection="column"
      backgroundColor="#16161e"
      borderRight
      borderColor="#3b3d57"
    >
      <text fg="#565f89" paddingLeft={1}>context</text>
      <scrollbox flexGrow={1} scrollY>
        <box width="100%" flexDirection="column" paddingLeft={1} paddingRight={1}>
          {state.contextFiles.length === 0 ? (
            <text fg="#3b3d57">no files</text>
          ) : (
            <For each={state.contextFiles}>
              {(f) => (
                <text fg={f.readonly ? "#565f89" : "#a9b1d6"}>
                  {formatFile(f.path, f.readonly, f.token_count)}
                </text>
              )}
            </For>
          )}
        </box>
      </scrollbox>
      <text fg="#565f89" paddingLeft={1}>
        {total() > 0 ? `${fmtK(total())} tokens` : ""}
      </text>
    </box>
  )
}
