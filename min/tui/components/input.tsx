// input.tsx — prompt input + slash autocomplete + file completion
import { createSignal, For, Show } from "solid-js"
import { useKeyboard } from "@opentui/solid"
import type { InputRenderable } from "@opentui/core"
import { state, setState, pushMessage } from "../state.ts"
import { sendPrompt, abortSession, listProjectFiles } from "../client.ts"
import { consumeStream } from "../stream.ts"
import { MK, MODE_COLOR } from "../theme.ts"

const SLASH_COMMANDS = [
  { cmd: "/add",        desc: "add file(s) to context" },
  { cmd: "/add -r",     desc: "add file(s) as read-only" },
  { cmd: "/drop",       desc: "remove file from context" },
  { cmd: "/edit-block", desc: "SEARCH/REPLACE mode [prompt]" },
  { cmd: "/edit-udiff", desc: "unified diff mode [prompt]" },
  { cmd: "/edit-whole", desc: "whole-file mode [prompt]" },
  { cmd: "/ask",        desc: "return to ask mode" },
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

type AcMode = "command" | "file"
interface AcItem { label: string; value: string }

export function InputBox() {
  const [acItems, setAcItems] = createSignal<AcItem[]>([])
  const [acSelected, setAcSelected] = createSignal(0)
  const [acMode, setAcMode] = createSignal<AcMode>("command")
  let inputRef: InputRenderable | undefined

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
    handleInput(selected.value)
  }

  useKeyboard((key) => {
    const items = acItems()
    if (items.length === 0) return
    if (key.name === "up") { setAcSelected(s => Math.max(0, s - 1)); return }
    if (key.name === "down") { setAcSelected(s => Math.min(items.length - 1, s + 1)); return }
    if (key.name === "tab") { completeSelected(); return }
    if (key.name === "return" && acMode() === "file") { completeSelected(); return }
    if (key.name === "escape") { setAcItems([]); return }
  })

  async function handleSubmit(value: string) {
    if (acItems().length > 0) { completeSelected(); return }

    const raw = value.trim()
    if (!raw) return

    if (state.streaming) {
      if (state.sessionId) await abortSession(state.sessionId).catch(() => {})
      setState("streaming", false)
      return
    }

    if (!state.sessionId) { setState("error", "no active session"); return }

    if (inputRef) inputRef.value = ""
    setAcItems([])

    const isCommand = raw.startsWith("/")
    if (!isCommand) pushMessage("user", raw)

    try {
      const response = await sendPrompt(state.sessionId, raw)
      await consumeStream(response)
    } catch (err) {
      setState("error", String(err))
      setState("streaming", false)
    }
  }

  async function handleInput(value: string) {
    // Slash command autocomplete
    if (value.startsWith("/") && !value.includes(" ")) {
      const matches = SLASH_COMMANDS
        .filter(c => c.cmd.startsWith(value))
        .map(c => ({ label: c.cmd, value: c.cmd + " " }))
      setAcMode("command")
      setAcItems(matches)
      setAcSelected(0)
      return
    }

    // /drop: dari contextFiles
    if (value.startsWith("/drop ")) {
      const pattern = value.slice("/drop ".length).toLowerCase()
      const matches = state.contextFiles
        .filter(f => pattern === "" || f.path.toLowerCase().includes(pattern))
        .slice(0, 15)
        .map(f => {
          const parts = f.path.replace(/\\/g, "/").split("/")
          return { label: parts.slice(-2).join("/"), value: "/drop " + f.path }
        })
      setAcMode("file")
      setAcItems(matches)
      setAcSelected(0)
      return
    }

    // /add, /add -r: dari filesystem CWD
    const addCmd = ["/add -r ", "/add "].find(p => value.startsWith(p))
    if (addCmd) {
      await loadFileCache()
      const afterCmd = value.slice(addCmd.length)
      const tokens = afterCmd.split(" ")
      const pattern = tokens[tokens.length - 1].toLowerCase()
      const prefix = value.slice(0, value.length - pattern.length)
      const matches = fileCache
        .filter(f => pattern === "" || f.toLowerCase().includes(pattern))
        .slice(0, 15)
        .map(f => {
          const parts = f.replace(/\\/g, "/").split("/")
          return { label: parts.slice(-2).join("/"), value: prefix + f + " " }
        })
      setAcMode("file")
      setAcItems(matches)
      setAcSelected(0)
      return
    }

    setAcItems([])
  }

  const modeColor = () => MODE_COLOR[state.mode] ?? MK.white
  const glyphColor = () => state.streaming ? MK.orange : modeColor()
  const glyphChar  = () => state.streaming ? "⊙" : "❯"

  return (
    <box
      width="100%"
      flexDirection="column"
      flexShrink={0}
      backgroundColor={MK.bg}
    >
      {/* Autocomplete overlay */}
      <Show when={acItems().length > 0}>
        <box
          width="100%"
          flexDirection="column"
          backgroundColor={MK.bg2}
          borderTop
          borderColor={MK.border}
        >
          <For each={acItems()}>
            {(item, i) => (
              <box
                width="100%"
                flexDirection="row"
                height={1}
                paddingLeft={2}
                paddingRight={2}
                backgroundColor={i() === acSelected() ? MK.bgHL : MK.bg2}
              >
                <text fg={acMode() === "file" ? MK.cyan : MK.green}>
                  {i() === acSelected() ? "▸ " : "  "}
                </text>
                <text fg={acMode() === "file" ? MK.white : MK.green}>{item.label}</text>
              </box>
            )}
          </For>
        </box>
      </Show>

      {/* Input row */}
      <box
        width="100%"
        flexDirection="row"
        alignItems="center"
        height={3}
        paddingLeft={1}
        paddingRight={1}
        borderTop
        borderColor={MK.border}
      >
        <text fg={glyphColor()} marginRight={1}>{glyphChar()}</text>
        <input
          ref={inputRef}
          flexGrow={1}
          placeholder="Ask anything..."
          placeholderColor={MK.border}
          backgroundColor={MK.bg}
          textColor={MK.white}
          focusedBackgroundColor={MK.bg}
          focusedTextColor={MK.white}
          focused
          onInput={(val: string) => handleInput(val)}
          onSubmit={(val: string) => handleSubmit(val)}
        />
      </box>
    </box>
  )
}
