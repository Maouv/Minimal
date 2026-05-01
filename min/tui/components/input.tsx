// input.tsx — input box sesuai HTML ref
// Layout: ✦ <textarea>
//         Ask · glm-5 · minimal   (input-meta)
// Slash menu muncul di atas
import { createSignal, For, Show } from "solid-js"
import { useKeyboard } from "@opentui/solid"
import type { InputRenderable } from "@opentui/core"
import { state, setState, pushMessage } from "../state.ts"
import { sendPrompt, abortSession, listProjectFiles, listProjectEntries, listProjectDirs } from "../client.ts"
import { consumeStream } from "../stream.ts"
import { C, MODE_COLOR } from "../theme.ts"

const SLASH_COMMANDS = [
  { cmd: "/add",        desc: "add file to context" },
  { cmd: "/add -r",     desc: "add file as read only" },
  { cmd: "/drop",       desc: "delete file from context" },
  { cmd: "/edit-block", desc: "edit with SEARCH/REPLACE" },
  { cmd: "/edit-udiff", desc: "edit with unified diff" },
  { cmd: "/edit-whole", desc: "rewrite whole file" },
  { cmd: "/ask",        desc: "back to ask mode" },
  { cmd: "/undo",       desc: "undo last edit" },
  { cmd: "/diff",       desc: "show last diff" },
  { cmd: "/clear",      desc: "clear messages" },
  { cmd: "/reset",      desc: "clear messages + context" },
  { cmd: "/commit",     desc: "git commit" },
  { cmd: "/run",        desc: "run shell command" },
  { cmd: "/tokens",     desc: "show token usage" },
  { cmd: "/model",      desc: "switch model" },
  { cmd: "/model-add",  desc: "add new provider" },
  { cmd: "/help",       desc: "show help" },
  { cmd: "/init",       desc: "generate MINIMAL.md for current dir" },
  { cmd: "/init --save", desc: "save draft to MINIMAL.md" },
  { cmd: "/exit",       desc: "exit from minimal" },
]

type AcMode = "command" | "file" | "dir"
interface AcItem { label: string; desc: string; value: string; is_dir?: boolean }

let _globalInputRef: import("@opentui/core").InputRenderable | undefined
export function focusInput() {
  setTimeout(() => _globalInputRef?.focus?.(), 50)
}

export function InputBox() {
  const [acItems, setAcItems] = createSignal<AcItem[]>([])
  const [acSelected, setAcSelected] = createSignal(0)
  const [acMode, setAcMode] = createSignal<AcMode>("command")
  let inputRef: InputRenderable | undefined
  // sync ke module-level ref supaya app.tsx bisa refocus setelah ModelPicker tutup
  const setInputRef = (el: InputRenderable) => { inputRef = el; _globalInputRef = el }

  let fileCache: string[] = []
  let fileCacheLoaded = false
  let dirCache: string[] = []
  let dirCacheLoaded = false
  let dirCacheRoot = "./"

  async function loadFileCache() {
    if (fileCacheLoaded) return
    try {
      const res = await listProjectFiles()
      fileCache = res.files
      fileCacheLoaded = true
    } catch { fileCache = [] }
  }

  async function loadDirCache() {
    if (dirCacheLoaded) return
    try {
      const res = await listProjectDirs()
      dirCache = res.dirs
      const parts = res.cwd.split("/").filter(Boolean)
      dirCacheRoot = (parts[parts.length - 1] || "root") + "/"
      dirCacheLoaded = true
    } catch { dirCache = []; dirCacheRoot = "./" }
  }

  // Drill-down entries untuk /add dan /init — list immediate children
  async function loadEntries(dirPath: string): Promise<Array<{name: string, path: string, is_dir: boolean}>> {
    try {
      const res = await listProjectEntries(dirPath)
      return res.entries
    } catch { return [] }
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
  // Kalau item adalah dir → drill-down (refresh list di dir tersebut)
  // Kalau item adalah file → insert path, siap submit
  function insertFile() {
    const items = acItems()
    const sel = items[acSelected()]
    if (!sel || !inputRef) return
    // skipNextInput = true supaya handleInput tidak re-trigger autocomplete
    skipNextInput = true
    inputRef.value = sel.value
    setAcSelected(0)
    // Kalau dir: re-trigger manual supaya list drill-down muncul
    // Kalau file: jangan trigger — user tinggal Enter untuk submit atau spasi untuk batch
    if (sel.is_dir) {
      skipNextInput = false
      handleInput(sel.value)
    }
  }

  useKeyboard((key) => {
    if (acItems().length === 0) return
    if (key.name === "up")    { key.preventDefault(); setAcSelected(s => Math.max(0, s - 1)); return }
    if (key.name === "down")  { key.preventDefault(); setAcSelected(s => Math.min(acItems().length - 1, s + 1)); return }
    if (key.name === "tab")   { key.preventDefault(); completeSelected(); return }
    if (key.name === "escape"){ key.preventDefault(); setAcItems([]); return }
    if (key.name === "return") {
      if (acMode() === "command") { key.preventDefault(); completeSelected(); return }
      if (acMode() === "file" || acMode() === "dir") {
        const items = acItems()
        const sel = items[acSelected()]
        if (sel) {
          key.preventDefault()
          if (acMode() === "dir") {
            // /init dir mode — set value final, dismiss list, langsung submit
            const val = inputRef?.value ?? ""
            if (val.startsWith("/init ")) {
              setAcItems([])
              handleSubmit(sel.value)
              return
            }
          }
          if (sel.is_dir) {
            // /add drill-down behavior
            insertFile()
          } else {
            // File → insert path, dismiss list
            insertFile()
            setAcItems([])
          }
          return
        }
        // List ada tapi tidak ada selection yang valid → dismiss, submit
        setAcItems([])
        // Biarkan onSubmit fire di tick berikutnya
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

    // /add — drill-down entries, files only untuk insert, dirs untuk navigasi
    const addCmd = ["/add -r ", "/add "].find(p => value.startsWith(p))
    if (addCmd) {
      const afterCmd = value.slice(addCmd.length)
      const tokens = afterCmd.split(" ")
      const lastToken = tokens[tokens.length - 1]
      const prefix = value.slice(0, value.length - lastToken.length)
      const alreadyAdded = new Set(tokens.slice(0, -1).filter(Boolean))

      // Tentukan dir yang sedang di-browse dari lastToken
      const lastSlash = lastToken.lastIndexOf("/")
      const browseDir = lastSlash >= 0 ? lastToken.slice(0, lastSlash + 1) : ""
      const filterName = lastToken.slice(lastSlash + 1).toLowerCase()

      const rawEntries = await loadEntries(browseDir)
      const matches = rawEntries
        .filter(e => !alreadyAdded.has(e.path))
        .filter(e => filterName === "" || e.name.toLowerCase().includes(filterName))
        .slice(0, 12)
        .map(e => ({
          label: e.name,          // "main.py" atau "backend/"
          desc: e.path,
          value: prefix + e.path, // dirs punya trailing /, files tidak
          is_dir: e.is_dir,
        }))

      setAcMode("file")
      setAcItems(matches)
      setAcSelected(0)
      return
    }

    // /init — dirs only, satu level select
    if (value.startsWith("/init ") && !value.includes("--")) {
      await loadDirCache()
      const filter = value.slice(6).toLowerCase()
      const allDirs = [{ label: dirCacheRoot, desc: "./", value: "/init ./" }, ...dirCache.map(d => {
          const parts = d.replace(/\/+$/, "").split("/")
          const name = parts[parts.length - 1] || "root"
          return { label: name + "/", desc: d, value: "/init " + d }
        })]
      const matches = allDirs
        .filter(d => filter === "" || d.desc.toLowerCase().includes(filter) || d.label.toLowerCase().includes(filter))
        .slice(0, 12)
        .map(d => ({ ...d, is_dir: true }))
      setAcMode("dir")
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
              ref={setInputRef}
              flexGrow={1}
              placeholder={isDisabled() ? "" : 'Ask anything... "Whats the tech stack of this project?"'}
              placeholderColor={C.gray2}
              backgroundColor={isDisabled() ? C.bg3 : C.bg2}
              textColor={isDisabled() ? C.gray2 : C.white}
              focusedBackgroundColor={isDisabled() ? C.bg3 : C.bg2}
              focusedTextColor={isDisabled() ? C.gray2 : C.white}
              focused={!isDisabled()}
              onInput={(val: string) => { if (!isDisabled()) handleInput(val) }}
              onSubmit={() => { if (!isDisabled()) handleSubmit(inputRef?.value ?? "") }}
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

