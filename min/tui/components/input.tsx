// input.tsx — prompt input + slash autocomplete + file completion
import { createSignal, For, Show } from "solid-js"
import { useKeyboard } from "@opentui/solid"
import type { InputRenderable } from "@opentui/core"
import { state, setState, pushMessage } from "../state.ts"
import { sendPrompt, abortSession, listProjectFiles } from "../client.ts"
import { consumeStream } from "../stream.ts"

const SLASH_COMMANDS = [
  { cmd: "/add",        desc: "add file to context" },
  { cmd: "/add -r",     desc: "add file as read-only" },
  { cmd: "/drop",       desc: "remove file from context" },
  { cmd: "/ls",         desc: "list context files" },
  { cmd: "/edit-block", desc: "edit with SEARCH/REPLACE" },
  { cmd: "/edit-udiff", desc: "edit with unified diff" },
  { cmd: "/edit-whole", desc: "rewrite entire file" },
  { cmd: "/undo",       desc: "undo last edit" },
  { cmd: "/diff",       desc: "show last diff" },
  { cmd: "/clear",      desc: "clear messages" },
  { cmd: "/reset",      desc: "clear messages + context" },
  { cmd: "/commit",     desc: "git commit" },
  { cmd: "/run",        desc: "run shell command" },
  { cmd: "/tokens",     desc: "show token usage" },
  { cmd: "/model",      desc: "switch model" },
  { cmd: "/help",       desc: "show help" },
]

// Commands yang butuh file completion setelah spasi
const FILE_COMMANDS = new Set(["/add", "/add -r", "/drop"])

type AcMode = "command" | "file"

interface AcItem {
  label: string   // ditampilkan di list
  value: string   // nilai yang di-insert ke input
}

export function InputBox() {
  const [acItems, setAcItems] = createSignal<AcItem[]>([])
  const [acSelected, setAcSelected] = createSignal(0)
  const [acMode, setAcMode] = createSignal<AcMode>("command")
  const glyphContent = () => state.streaming ? "⊙" : "✦"
  const glyphColor = () => state.streaming ? "#e0af68" : "#7aa2f7"
  let inputRef: InputRenderable | undefined

  // Cache file list agar tidak fetch ulang setiap keystroke
  let fileCache: string[] = []
  let fileCacheLoaded = false

  async function loadFileCache() {
    if (fileCacheLoaded) return
    try {
      const res = await listProjectFiles()
      fileCache = res.files
      fileCacheLoaded = true
    } catch {
      fileCache = []
    }
  }

  function completeSelected() {
    const items = acItems()
    const selected = items[acSelected()]
    if (!selected || !inputRef) return
    inputRef.value = selected.value
    setAcItems([])
  }

  useKeyboard((key) => {
    const items = acItems()
    if (items.length === 0) return

    if (key.name === "up") {
      setAcSelected(s => Math.max(0, s - 1))
      return
    }
    if (key.name === "down") {
      setAcSelected(s => Math.min(items.length - 1, s + 1))
      return
    }
    if (key.name === "tab" || key.name === "return") {
      completeSelected()
      return
    }
    if (key.name === "escape") {
      setAcItems([])
      return
    }
  })

  async function handleSubmit(value: string) {
    if (acItems().length > 0) {
      completeSelected()
      return
    }

    const raw = value.trim()
    if (!raw) return

    if (state.streaming) {
      if (state.sessionId) await abortSession(state.sessionId).catch(() => {})
      setState("streaming", false)
      return
    }

    if (!state.sessionId) {
      setState("error", "no active session")
      return
    }

    setAcItems([])
    pushMessage("user", raw)

    try {
      const response = await sendPrompt(state.sessionId, raw)
      await consumeStream(response)
    } catch (err) {
      setState("error", String(err))
      setState("streaming", false)
    }
  }

  async function handleInput(value: string) {
    // ── Slash command autocomplete ─────────────────────────────────────────
    if (value.startsWith("/") && !value.includes(" ")) {
      const matches = SLASH_COMMANDS
        .filter(c => c.cmd.startsWith(value))
        .map(c => ({ label: `${c.cmd}  ${c.desc}`, value: c.cmd + " " }))
      setAcMode("command")
      setAcItems(matches)
      setAcSelected(0)
      return
    }

    // ── File completion untuk /add dan /drop ───────────────────────────────
    // Detect: value dimulai dengan file command + spasi
    const fileCmd = ["/add -r ", "/add ", "/drop "].find(p => value.startsWith(p))
    if (fileCmd) {
      await loadFileCache()
      const pattern = value.slice(fileCmd.length).toLowerCase()
      const matches = fileCache
        .filter(f => pattern === "" || f.toLowerCase().includes(pattern))
        .slice(0, 20)  // cap 20 biar tidak overflow
        .map(f => {
          // Tampilkan nama file saja di label, value = full path
          const parts = f.replace(/\\/g, "/").split("/")
          const label = parts.slice(-2).join("/")  // dir/file.ext
          return { label, value: fileCmd + f }
        })
      setAcMode("file")
      setAcItems(matches)
      setAcSelected(0)
      return
    }

    setAcItems([])
  }

  // Warna label berdasarkan mode
  const labelFg = () => acMode() === "file" ? "#9ece6a" : "#7aa2f7"
  const descFg  = () => acMode() === "file" ? "#565f89" : "#565f89"

  return (
    <box
      width="100%"
      flexDirection="column"
      flexShrink={0}
      borderTop
      borderColor="#3b3d57"
      backgroundColor="#1a1b26"
    >
      <Show when={acItems().length > 0}>
        <box
          width="100%"
          flexDirection="column"
          backgroundColor="#1e2030"
          borderBottom
          borderColor="#3b3d57"
        >
          <For each={acItems()}>
            {(item, i) => (
              <box
                width="100%"
                flexDirection="row"
                height={1}
                paddingLeft={2}
                paddingRight={2}
                backgroundColor={i() === acSelected() ? "#2a2b40" : "#1e2030"}
              >
                <text fg={labelFg()}>{item.label}</text>
              </box>
            )}
          </For>
        </box>
      </Show>

      <box
        width="100%"
        flexDirection="row"
        alignItems="center"
        height={3}
        paddingLeft={1}
        paddingRight={1}
      >
        <text fg={glyphColor()} marginRight={1}>{glyphContent()}</text>
        <input
          ref={inputRef}
          flexGrow={1}
          placeholder="ask or /command…"
          placeholderColor="#3b3d57"
          backgroundColor="#1a1b26"
          textColor="#c0caf5"
          focusedBackgroundColor="#1a1b26"
          focusedTextColor="#c0caf5"
          focused
          onInput={(val: string) => handleInput(val)}
          onSubmit={(val: string) => handleSubmit(val)}
        />
      </box>

      <box
        width="100%"
        flexDirection="row"
        paddingLeft={2}
        paddingBottom={1}
      >
        <text fg="#7aa2f7">{state.mode}</text>
        <text fg="#3b3d57">{"  ·  "}</text>
        <text fg="#565f89">{state.model}</text>
      </box>
    </box>
  )
}


const SLASH_COMMANDS = [
  { cmd: "/add",        desc: "add file to context" },
  { cmd: "/add -r",     desc: "add file as read-only" },
  { cmd: "/drop",       desc: "remove file from context" },
  { cmd: "/ls",         desc: "list context files" },
  { cmd: "/edit-block", desc: "edit with SEARCH/REPLACE" },
  { cmd: "/edit-udiff", desc: "edit with unified diff" },
  { cmd: "/edit-whole", desc: "rewrite entire file" },
  { cmd: "/undo",       desc: "undo last edit" },
  { cmd: "/diff",       desc: "show last diff" },
  { cmd: "/clear",      desc: "clear messages" },
  { cmd: "/reset",      desc: "clear messages + context" },
  { cmd: "/commit",     desc: "git commit" },
  { cmd: "/run",        desc: "run shell command" },
  { cmd: "/tokens",     desc: "show token usage" },
  { cmd: "/model",      desc: "switch model" },
  { cmd: "/help",       desc: "show help" },
]

export function InputBox() {
  const [acItems, setAcItems] = createSignal<typeof SLASH_COMMANDS>([])
  const [acSelected, setAcSelected] = createSignal(0)
  const glyphContent = () => state.streaming ? "⊙" : "✦"
  const glyphColor = () => state.streaming ? "#e0af68" : "#7aa2f7"
  let inputRef: InputRenderable | undefined

  function completeSelected() {
    const items = acItems()
    const selected = items[acSelected()]
    if (!selected || !inputRef) return
    inputRef.value = selected.cmd + " "
    setAcItems([])
  }

  // Handle autocomplete keyboard navigation
  useKeyboard((key) => {
    const items = acItems()
    if (items.length === 0) return

    if (key.name === "up") {
      setAcSelected(s => Math.max(0, s - 1))
      return
    }
    if (key.name === "down") {
      setAcSelected(s => Math.min(items.length - 1, s + 1))
      return
    }
    if (key.name === "tab" || key.name === "return") {
      completeSelected()
      return
    }
    if (key.name === "escape") {
      setAcItems([])
      return
    }
  })

  async function handleSubmit(value: string) {
    // Kalau autocomplete aktif, return = complete, bukan submit
    if (acItems().length > 0) {
      completeSelected()
      return
    }

    const raw = value.trim()
    if (!raw) return

    if (state.streaming) {
      if (state.sessionId) await abortSession(state.sessionId).catch(() => {})
      setState("streaming", false)
      return
    }

    if (!state.sessionId) {
      setState("error", "no active session")
      return
    }

    setAcItems([])
    pushMessage("user", raw)

    try {
      const response = await sendPrompt(state.sessionId, raw)
      await consumeStream(response)
    } catch (err) {
      setState("error", String(err))
      setState("streaming", false)
    }
  }

  function handleInput(value: string) {
    if (value.startsWith("/") && !value.includes(" ")) {
      const matches = SLASH_COMMANDS.filter(c => c.cmd.startsWith(value))
      setAcItems(matches)
      setAcSelected(0)
    } else {
      setAcItems([])
    }
  }

  return (
    <box
      width="100%"
      flexDirection="column"
      flexShrink={0}
      borderTop
      borderColor="#3b3d57"
      backgroundColor="#1a1b26"
    >
      <Show when={acItems().length > 0}>
        <box
          width="100%"
          flexDirection="column"
          backgroundColor="#1e2030"
          borderBottom
          borderColor="#3b3d57"
        >
          <For each={acItems()}>
            {(item, i) => (
              <box
                width="100%"
                flexDirection="row"
                height={1}
                paddingLeft={2}
                paddingRight={2}
                backgroundColor={i() === acSelected() ? "#2a2b40" : "#1e2030"}
              >
                <text fg="#7aa2f7" marginRight={2}>{item.cmd}</text>
                <text fg="#565f89">{item.desc}</text>
              </box>
            )}
          </For>
        </box>
      </Show>

      <box
        width="100%"
        flexDirection="row"
        alignItems="center"
        height={3}
        paddingLeft={1}
        paddingRight={1}
      >
        <text fg={glyphColor()} marginRight={1}>{glyphContent()}</text>
        <input
          ref={inputRef}
          flexGrow={1}
          placeholder="ask or /command…"
          placeholderColor="#3b3d57"
          backgroundColor="#1a1b26"
          textColor="#c0caf5"
          focusedBackgroundColor="#1a1b26"
          focusedTextColor="#c0caf5"
          focused
          onInput={(val: string) => handleInput(val)}
          onSubmit={(val: string) => handleSubmit(val)}
        />
      </box>

      <box
        width="100%"
        flexDirection="row"
        paddingLeft={2}
        paddingBottom={1}
      >
        <text fg="#7aa2f7">{state.mode}</text>
        <text fg="#3b3d57">{"  ·  "}</text>
        <text fg="#565f89">{state.model}</text>
      </box>
    </box>
  )
}
