// chat.tsx — full width chat, no sidebar
// Layout: empty state | messages list
// User msg: input-box style (glyph ✦ + text)
// AI msg: plain text body + optional thinking + code/diff blocks
import { For, Show, createMemo } from "solid-js"
import { state, type Message } from "../state.ts"
import { C, getMonokaiStyle } from "../theme.ts"

function fileExtension(path: string): string {
  const ext = path.split(".").pop()?.toLowerCase() ?? ""
  const map: Record<string, string> = {
    py: "python", ts: "typescript", tsx: "typescript",
    js: "javascript", jsx: "javascript",
    rs: "rust", go: "go", c: "c", cpp: "cpp",
    json: "json", yaml: "yaml", yml: "yaml",
    md: "markdown", sh: "bash", toml: "toml",
  }
  return map[ext] ?? ext
}

// ── Empty state ───────────────────────────────────────────────────────────────
function EmptyState() {
  return (
    <box
      width="100%"
      flexGrow={1}
      flexDirection="column"
      alignItems="center"
      justifyContent="center"
      backgroundColor={C.bg}
    >
      <text fg={C.blue}>✦  minimal</text>
      <box height={2} />
      <text fg={C.gray}>ask anything or type / for commands</text>
    </box>
  )
}

// ── User message ──────────────────────────────────────────────────────────────
// Box bg2 sama persis dengan input bar: margin 1, glyph ✦, teks
function UserMsg(props: { content: string }) {
  return (
    <box
      width="100%"
      flexDirection="row"
      paddingLeft={2}
      paddingRight={2}
      paddingTop={1}
      paddingBottom={1}
      marginLeft={1}
      marginRight={1}
      marginTop={1}
      backgroundColor={C.bg2}
    >
      <text fg={C.blue} marginRight={1}>✦</text>
      <text fg={C.white} flexGrow={1} flexWrap="wrap">{props.content}</text>
    </box>
  )
}

// ── AI message ────────────────────────────────────────────────────────────────
function AiMsg(props: { msg: Message }) {
  const syntaxStyle = getMonokaiStyle()

  return (
    <box
      width="100%"
      flexDirection="column"
      paddingLeft={2}
      paddingRight={2}
      paddingTop={1}
      paddingBottom={1}
      backgroundColor={C.bg}
    >
      {/* Content — markdown dengan syntax highlight */}
      <markdown
        content={props.msg.content}
        syntaxStyle={syntaxStyle}
        fg={C.white}
        streaming={!props.msg.done}
        width="100%"
      />

      {/* Diff blocks */}
      <Show when={props.msg.done && props.msg.edits && props.msg.edits!.length > 0}>
        <For each={props.msg.edits}>
          {(edit) => {
            const added   = (edit.diff.match(/^\+[^+]/mg) ?? []).length
            const removed = (edit.diff.match(/^-[^-]/mg) ?? []).length
            return (
              <box
                width="100%"
                flexDirection="column"
                marginTop={1}
                marginLeft={1}
                marginRight={1}
                border
                borderColor={C.border}
              >
                {/* diff-top */}
                <box
                  width="100%"
                  flexDirection="row"
                  height={1}
                  paddingLeft={1}
                  paddingRight={1}
                  backgroundColor={C.bg2}
                >
                  <text fg={C.cyan}>{edit.file}</text>
                  <text fg={C.gray2}>{`  +${added} -${removed}`}</text>
                  <box flexGrow={1} />
                  <text fg={C.gray}>
                    {edit.success ? `Applied to ${edit.file}` : (edit.error ?? "failed")}
                  </text>
                </box>
                {/* diff body */}
                <Show when={edit.diff}>
                  <diff
                    diff={edit.diff}
                    width="100%"
                    view="unified"
                    filetype={fileExtension(edit.file)}
                    syntaxStyle={syntaxStyle}
                    showLineNumbers={false}
                    fg={C.white}
                    addedBg="#0d1a00"
                    removedBg="#1a0009"
                    contextBg={C.bg}
                    addedSignColor={C.gdim}
                    removedSignColor={C.pink}
                  />
                </Show>
              </box>
            )
          }}
        </For>
      </Show>
    </box>
  )
}

// ── Chat view ─────────────────────────────────────────────────────────────────
export function ChatView() {
  const hasMessages = createMemo(() => state.messages.length > 0)

  return (
    <scrollbox
      flexGrow={1}
      scrollY
      stickyScroll
      stickyStart="bottom"
      backgroundColor={C.bg}
    >
      <box width="100%" flexDirection="column">
        <Show when={!hasMessages()}>
          <EmptyState />
        </Show>
        <For each={state.messages}>
          {(msg) => (
            <Show
              when={msg.role === "user"}
              fallback={<AiMsg msg={msg} />}
            >
              <UserMsg content={msg.content} />
            </Show>
          )}
        </For>
      </box>
    </scrollbox>
  )
}
