// chat.tsx — scrollable message history + diff display
import { For, Show } from "solid-js"
import { state, type Message } from "../state.ts"

function roleFg(role: string): string {
  switch (role) {
    case "user":      return "#7aa2f7"
    case "assistant": return "#9ece6a"
    default:          return "#565f89"
  }
}

function roleLabel(role: string): string {
  switch (role) {
    case "user":      return "▸ you"
    case "assistant": return "▸ min"
    default:          return "▸ sys"
  }
}

function MessageRow(props: { msg: Message }) {
  const isUser = () => props.msg.role === "user"

  return (
    <box
      width="100%"
      flexDirection="column"
      paddingLeft={2}
      paddingRight={2}
      paddingTop={1}
      paddingBottom={1}
      backgroundColor={isUser() ? "#1e2030" : "#1a1b26"}
    >
      <text fg={roleFg(props.msg.role)}>{roleLabel(props.msg.role)}</text>
      <text fg="#c0caf5" flexWrap="wrap">{props.msg.content}</text>
      <Show when={props.msg.done && props.msg.edits}>
        <For each={props.msg.edits}>
          {(edit) => (
            <diff
              diff={edit.diff}
              width="100%"
              view="unified"
              fg={edit.success ? "#a9b1d6" : "#f7768e"}
            />
          )}
        </For>
      </Show>
    </box>
  )
}

export function ChatView() {
  return (
    <scrollbox flexGrow={1} scrollY stickyScroll backgroundColor="#1a1b26">
      <For each={state.messages}>
        {(msg) => <MessageRow msg={msg} />}
      </For>
    </scrollbox>
  )
}
