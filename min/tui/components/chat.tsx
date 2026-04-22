// chat.tsx — message history dengan markdown rendering + styled diff
import { For, Show } from "solid-js"
import { state, type Message } from "../state.ts"
import { MK, getMonokaiStyle } from "../theme.ts"

function roleFg(role: string): string {
  switch (role) {
    case "user":      return MK.green
    case "assistant": return MK.white
    default:          return MK.comment
  }
}

function roleLabel(role: string): string {
  switch (role) {
    case "user":      return "▸ you"
    case "assistant": return "▸ min"
    default:          return "▸ sys"
  }
}

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

function MessageRow(props: { msg: Message }) {
  const isUser = () => props.msg.role === "user"
  const syntaxStyle = getMonokaiStyle()

  return (
    <box
      width="100%"
      flexDirection="column"
      paddingLeft={2}
      paddingRight={2}
      paddingTop={1}
      paddingBottom={1}
      backgroundColor={isUser() ? MK.bg3 : MK.bg}
    >
      <text fg={roleFg(props.msg.role)}>{roleLabel(props.msg.role)}</text>

      <markdown
        content={props.msg.content}
        syntaxStyle={syntaxStyle}
        fg={roleFg(props.msg.role)}
        streaming={!props.msg.done}
        width="100%"
      />

      <Show when={props.msg.done && props.msg.edits && props.msg.edits!.length > 0}>
        <For each={props.msg.edits}>
          {(edit) => (
            <box width="100%" flexDirection="column" marginTop={1}>
              <box
                width="100%"
                flexDirection="row"
                height={1}
                paddingLeft={1}
                paddingRight={1}
                backgroundColor={MK.bgHL}
              >
                <text fg={edit.success ? MK.green : MK.pink}>{edit.success ? "✓" : "✗"}</text>
                <text fg={MK.comment} marginLeft={1}>{edit.file}</text>
                <box flexGrow={1} />
                <text fg={MK.comment}>{edit.success ? "applied" : (edit.error ?? "failed")}</text>
              </box>
              <Show when={edit.diff}>
                <diff
                  diff={edit.diff}
                  width="100%"
                  view="unified"
                  filetype={fileExtension(edit.file)}
                  syntaxStyle={syntaxStyle}
                  showLineNumbers={true}
                  fg={MK.white}
                  addedBg={MK.addedBg}
                  removedBg={MK.removedBg}
                  addedSignColor={MK.addedSign}
                  removedSignColor={MK.removedSign}
                  lineNumberFg={MK.lineNumFg}
                  lineNumberBg={MK.lineNumBg}
                />
              </Show>
            </box>
          )}
        </For>
      </Show>
    </box>
  )
}

export function ChatView() {
  return (
    <scrollbox
      flexGrow={1}
      scrollY
      stickyScroll
      stickyStart="bottom"
      backgroundColor={MK.bg}
    >
      <box width="100%" flexDirection="column">
        <For each={state.messages}>
          {(msg) => <MessageRow msg={msg} />}
        </For>
      </box>
    </scrollbox>
  )
}
