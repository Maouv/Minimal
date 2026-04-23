// input.tsx — input box sesuai HTML ref
// Layout: ✦ <textarea>
//         Ask · glm-5 · minimal   (input-meta)
// Slash menu muncul di atas
import { createSignal, For, Show } from "solid-js"
import { useKeyboard } from "@opentui/solid"
import type { InputRenderable } from "@opentui/core"
import { state, setState, pushMessage } from "../state.ts"
import { sendPrompt, abortSession, listProjectFiles } from "../client.ts"
import { consumeStream } from "../stream.ts"
import { C, MODE_COLOR } from "../theme.ts"

const SLASH_COMMANDS = [
  { cmd: "/add",        desc: "tambah file ke context" },
  { cmd: "/add -r",     desc: "tambah file sebagai read-only" },
  { cmd: "/drop",       desc: "hapus file dari context" },
  { cmd: "/edit-block", desc: "edit dengan SEARCH/REPLACE" },
  { cmd: "/edit-udiff", desc: "edit dengan unified diff" },
  { cmd: "/edit-whole", desc: "rewrite seluruh file" },
  { cmd: "/ask",        desc: "kembali ke ask mode" },
  { cmd: "/undo",       desc: "undo last edit" },
  { cmd: "/diff",       desc: "show last diff" },
  { cmd: "/clear",      desc: "clear messages" },
  { cmd: "/reset",      desc: "clear messages + context" },
  { cmd: "/commit",     desc: "git commit" },
  { cmd: "/run",        desc: "run shell command" },
  { cmd: "/tokens",     desc: "show token usage" },
  { cmd: "/model",      desc: "switch model" },
  { cmd: "/model-add",  desc: "tambah provider & model baru" },
  { cmd: "/help",       desc: "show help" },
]

type AcMode = "command" | "file"
interface AcItem { label: string; desc: string; value: string }

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
    } catch { fileCache = [] }
  }

  let skipNextInput = false

  // Untuk command mode: complete dan re-trigger handleInput
  function completeSelected() {
    const items = acItems()
    const sel = items[acSelected()]
    if (!sel || !inputRef) return
    skipNextInput = true
    inputRef.value = sel.value
    setAcItems([])
    if (acMode() === "command") {
      skipNextInput = false
      handleInput(sel.value)
    }
  }

  // Untuk file mode: insert file ke input, refresh list untuk batch add
  // TIDAK submit — user perlu Enter lagi (tanpa suggestion) untuk submit
  function insertFile() {
    const items = acItems()
    const sel = items[acSelected()]
    if (!sel || !inputRef) return
    // sel.value sudah berupa "/add path/to/file " (trailing space)
    skipNextInput = false  // kita MAU trigger handleInput untuk refresh list
    inputRef.value = sel.value
    setAcSelected(0)
    // handleInput akan dipanggil via onInput yang di-fire oleh set value
    // Kalau opentui tidak fire onInput programmatically, panggil manual:
    handleInput(sel.value)
  }

  useKeyboard((key) => {
    if (acItems().length === 0) return
    if (key.name === "up")    { key.preventDefault(); setAcSelected(s => Math.max(0, s - 1)); return }
    if (key.name === "down")  { key.preventDefault(); setAcSelected(s => Math.min(acItems().length - 1, s + 1)); return }
    if (key.name === "tab")   { key.preventDefault(); completeSelected(); return }
    if (key.name === "escape"){ key.preventDefault(); setAcItems([]); return }
    if (key.name === "return") {
      if (acMode() === "command") { key.preventDefault(); completeSelected(); return }
      if (acMode() === "file") {
        const val = inputRef?.value ?? ""
        const addCmd = ["/add -r ", "/add "].find(p => val.startsWith(p))
        const lastToken = addCmd
          ? val.slice(addCmd.length).split(" ").pop() ?? ""
          : ""
        if (lastToken !== "") {
          key.preventDefault()  // pattern ada → pilih file, block onSubmit
          insertFile()
          return
        }
        // lastToken kosong (trailing space) → dismiss list, biarkan onSubmit fire
        setAcItems([])
      }
    }
  })

  async function handleSubmit(value: string) {
    const raw = value.trim()
    if (!raw) return

    // /model-add → buka ModelPicker dalam mode add-provider
    if (raw === "/model-add" || raw === "/model-add ") {
      skipNextInput = true
      if (inputRef) inputRef.value = ""
      setAcItems([])
      setState("showModelPicker", "add")
      return
    }

    // /model → buka ModelPicker dalam mode switch
    if (raw === "/model" || raw === "/model ") {
      skipNextInput = true
      if (inputRef) inputRef.value = ""
      setAcItems([])
      setState("showModelPicker", "switch")
      return
    }

    if (state.streaming) {
      if (state.sessionId) await abortSession(state.sessionId).catch(() => {})
      setState("streaming", false)
      return
    }
    if (!state.sessionId) { setState("error", "no active session"); return }

    skipNextInput = true
    if (inputRef) inputRef.value = ""
    setAcItems([])

    const isCommand = raw.startsWith("/")
    // Edit commands dengan prompt tetap tampilkan sebagai user message
    const isEditWithPrompt = /^\/(edit-block|edit-udiff|edit-whole)\s+\S/.test(raw)
    if (!isCommand || isEditWithPrompt) pushMessage("user", raw)

    try {
      const response = await sendPrompt(state.sessionId, raw)
      await consumeStream(response)
    } catch (err) {
      setState("error", String(err))
      setState("streaming", false)
    }
  }

  async function handleInput(value: string) {
    if (skipNextInput) { skipNextInput = false; return }

    // Slash command menu
    if (value.startsWith("/") && !value.includes(" ")) {
      const matches = SLASH_COMMANDS
        .filter(c => c.cmd.startsWith(value))
        .map(c => ({ label: c.cmd, desc: c.desc, value: c.cmd + " " }))
      setAcMode("command")
      setAcItems(matches)
      setAcSelected(0)
      return
    }

    // /drop — dari contextFiles
    if (value.startsWith("/drop ")) {
      const pattern = value.slice(6).toLowerCase()
      const matches = state.contextFiles
        .filter(f => pattern === "" || f.path.toLowerCase().includes(pattern))
        .slice(0, 12)
        .map(f => {
          const parts = f.path.replace(/\\/g, "/").split("/")
          const short = parts.slice(-2).join("/")
          return { label: short, desc: f.path, value: "/drop " + f.path }
        })
      setAcMode("file")
      setAcItems(matches)
      setAcSelected(0)
      return
    }

    // /add — dari filesystem CWD, batch support
    const addCmd = ["/add -r ", "/add "].find(p => value.startsWith(p))
    if (addCmd) {
      await loadFileCache()
      const afterCmd = value.slice(addCmd.length)
      const tokens = afterCmd.split(" ")
      const pattern = tokens[tokens.length - 1].toLowerCase()
      const prefix = value.slice(0, value.length - pattern.length)
      // File yang sudah ada di input (sebelum pattern terakhir) — exclude dari list
      const alreadyAdded = new Set(tokens.slice(0, -1).filter(Boolean))
      const matches = fileCache
        .filter(f => !alreadyAdded.has(f))
        .filter(f => pattern === "" || f.toLowerCase().includes(pattern))
        .slice(0, 12)
        .map(f => {
          const parts = f.replace(/\\/g, "/").split("/")
          const short = parts.slice(-2).join("/")
          return { label: short, desc: f, value: prefix + f + " " }
        })
      setAcMode("file")
      setAcItems(matches)
      setAcSelected(0)
      return
    }

    setAcItems([])
  }

  const modeLabel = () => {
    if (state.streaming) return "Thinking..."
    const m: Record<string, string> = {
      "ask": "Ask", "edit-block": "Edit", "edit-udiff": "Edit", "edit-whole": "Edit",
    }
    return m[state.mode] ?? state.mode
  }
  const modeColor = () => state.streaming ? C.green : (MODE_COLOR[state.mode] ?? C.cyan)
  const isDisabled = () => !!state.showModelPicker

  return (
    <box width="100%" flexDirection="column" flexShrink={0} backgroundColor={C.bg}>

      {/* Slash menu */}
      <Show when={acItems().length > 0 && !isDisabled()}>
        <box width="100%" backgroundColor={C.bg} paddingLeft={2} paddingRight={2} paddingTop={2}>
          <box width="100%" flexDirection="column" backgroundColor={C.bg2} flexShrink={0}>
            <For each={acItems()}>
              {(item, i) => (
                <box
                  width="100%"
                  flexDirection="row"
                  height={1}
                  paddingLeft={2}
                  paddingRight={2}
                  backgroundColor={i() === acSelected() ? C.bg3 : C.bg2}
                >
                  <text fg={C.orange} width={16}>{item.label}</text>
                  <text fg={C.gray}>{item.desc}</text>
                </box>
              )}
            </For>
          </box>
        </box>
      </Show>

      {/* Input box */}
      <box width="100%" backgroundColor={C.bg} paddingLeft={2} paddingRight={2} paddingBottom={2}>
        <box
          width="100%"
          flexDirection="column"
          backgroundColor={isDisabled() ? C.bg3 : C.bg2}
          paddingLeft={2}
          paddingRight={2}
          paddingTop={1}
          paddingBottom={1}
        >
          <box width="100%" flexDirection="row" alignItems="center" marginBottom={1}>
            <text fg={isDisabled() ? C.gray2 : C.blue} marginRight={1}>✦</text>
            <input
              ref={inputRef}
              flexGrow={1}
              placeholder={isDisabled() ? "" : 'Ask anything... "Whats the tech stack of this project?"'}
              placeholderColor={C.gray2}
              backgroundColor={isDisabled() ? C.bg3 : C.bg2}
              textColor={isDisabled() ? C.gray2 : C.white}
              focusedBackgroundColor={isDisabled() ? C.bg3 : C.bg2}
              focusedTextColor={isDisabled() ? C.gray2 : C.white}
              focused={!isDisabled()}
              onInput={(val: string) => { if (!isDisabled()) handleInput(val) }}
              onSubmit={(val: string) => { if (!isDisabled()) handleSubmit(val) }}
            />
          </box>

          {/* Meta: mode · model */}
          <box width="100%" flexDirection="row">
            <text fg={isDisabled() ? C.gray2 : modeColor()}>{isDisabled() ? "—" : modeLabel()}</text>
            <text fg={C.gray2}>{" · "}</text>
            <text fg={C.gray}>{state.model || "—"}</text>
          </box>
        </box>
      </box>
    </box>
  )
}
