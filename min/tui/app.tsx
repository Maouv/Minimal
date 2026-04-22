// app.tsx — layout sesuai HTML ref:
// [chat - full width, full height]
// [ctx-bar - atas input, conditional]
// [input-zone]
// [status-bar - paling bawah]
import { ChatView } from "./components/chat.tsx"
import { InputBox } from "./components/input.tsx"
import { CtxBar } from "./components/status.tsx"
import { C } from "./theme.ts"

export function App() {
  return (
    <box width="100%" height="100%" flexDirection="column" backgroundColor={C.bg}>
      <ChatView />
      <CtxBar />
      <InputBox />
    </box>
  )
}
