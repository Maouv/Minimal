// app.tsx — layout
import { Show } from "solid-js"
import { ChatView } from "./components/chat.tsx"
import { InputBox } from "./components/input.tsx"
import { CtxBar } from "./components/status.tsx"
import { state } from "./state.ts"
import { C } from "./theme.ts"

const LOGO = [
  "▄▄▄▄▄▄▄ ✦ ▄▄▄▄ ✦ ▄▄▄▄▄▄▄ ▄▄▄▄ ▄",
  "█░░█░░█ ▄ █░░█ ▄ █░░█░░█ █░░█ █",
  "█  █  █ █ █  █ █ █  █  █ █▀▀█ █",
  " ▀  ▀  ▀ ▀ ▀  ▀ ▀ ▀  ▀  ▀ ▀  ▀ ▀▀▀",
]

function EmptyState() {
  return (
    <box flexGrow={1} flexDirection="column" alignItems="center" justifyContent="center" backgroundColor={C.bg}>
      {LOGO.map(line => (
        <text fg={C.white}>{line}</text>
      ))}
    </box>
  )
}

export function App() {
  return (
    <box width="100%" height="100%" flexDirection="column" backgroundColor={C.bg}>
      <Show when={state.messages.length > 0} fallback={<EmptyState />}>
        <ChatView />
      </Show>
      <CtxBar />
      <InputBox />
    </box>
  )
}
