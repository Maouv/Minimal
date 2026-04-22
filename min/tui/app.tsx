import { StatusBar } from "./components/status.tsx"
import { ContextPanel } from "./components/context.tsx"
import { ChatView } from "./components/chat.tsx"
import { InputBox } from "./components/input.tsx"

export function App() {
  return (
    <box width="100%" height="100%" flexDirection="column" backgroundColor="#1a1b26">
      <StatusBar />
      <box flexGrow={1} flexDirection="row" overflow="hidden">
        <ContextPanel />
        <ChatView />
      </box>
      <InputBox />
    </box>
  )
}

// 2. Tambahkan fungsi ini agar index.ts bisa memanggilnya
export function mountApp(renderer: any) {
  return render(() => <App />, renderer)
}

