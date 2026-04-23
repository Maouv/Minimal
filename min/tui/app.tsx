// app.tsx — layout
import { Show } from "solid-js"
import { ChatView } from "./components/chat.tsx"
import { InputBox } from "./components/input.tsx"
import { CtxBar } from "./components/status.tsx"
import { ModelPicker } from "./components/model-picker.tsx"
import { state, setState } from "./state.ts"
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
      <box width="100%" backgroundColor={C.bg} paddingLeft={2} paddingRight={2} paddingBottom={2} paddingTop={1}>
        <box
          width="100%"
          flexDirection="row"
          backgroundColor={C.bg2}
          paddingLeft={2}
          paddingRight={2}
          paddingTop={1}
          paddingBottom={1}
          marginBottom={1}
        >
          <text fg={C.blue} marginRight={1}>✦</text>
          <text fg={C.white} flexWrap="wrap">Can you fix null pointer on context.py line 42?</text>
        </box>
        <box
          width="100%"
          flexDirection="row"
          backgroundColor={C.bg2}
          paddingLeft={2}
          paddingRight={2}
          paddingTop={1}
          paddingBottom={1}
        >
          <text fg={C.blue} marginRight={1}>✦</text>
          <text fg={C.white} flexWrap="wrap">/edit-block fix null pointer in context.py</text>
        </box>
      </box>
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
      {/* ModelPicker muncul di atas InputBox, replace slot yang sama */}
      <Show when={state.showModelPicker} fallback={<InputBox />}>
        <ModelPicker onDone={() => setState("showModelPicker", false)} />
      </Show>
    </box>
  )
}
