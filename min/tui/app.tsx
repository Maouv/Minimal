import { StatusBar, FooterBar } from "./components/status.tsx"
import { ContextPanel } from "./components/context.tsx"
import { ChatView } from "./components/chat.tsx"
import { InputBox } from "./components/input.tsx"
import { MK } from "./theme.ts"

export function App() {
  return (
    <box width="100%" height="100%" flexDirection="column" backgroundColor={MK.bg}>
      <StatusBar />
      <box flexGrow={1} flexDirection="row" overflow="hidden">
        <ContextPanel />
        <ChatView />
      </box>
      <InputBox />
      <FooterBar />
    </box>
  )
}
