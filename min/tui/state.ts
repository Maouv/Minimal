// state.ts — solid-js store: single source of truth
import { createStore } from "solid-js/store"

export type Mode = "ask" | "edit-block" | "edit-udiff" | "edit-whole"
export type MessageRole = "user" | "assistant" | "system"

export interface ContextFile {
  path: string
  readonly: boolean
  token_count: number
}

export interface EditResult {
  file: string
  diff: string
  success: boolean
  error?: string
}

export interface Message {
  role: MessageRole
  content: string
  thinking?: string      // thinking/reasoning content dari model
  edits?: EditResult[]
  done: boolean
}

export interface AppState {
  sessionId: string | null
  model: string
  mode: Mode
  streaming: boolean
  messages: Message[]
  contextFiles: ContextFile[]
  totalTokens: number
  inputTokens: number
  outputTokens: number
  error: string | null
  showModelPicker: "switch" | "add" | false
}

export const [state, setState] = createStore<AppState>({
  sessionId: null,
  model: "",
  mode: "ask",
  streaming: false,
  messages: [],
  contextFiles: [],
  totalTokens: 0,
  inputTokens: 0,
  outputTokens: 0,
  error: null,
  showModelPicker: false,
})

export function pushMessage(role: MessageRole, content = ""): number {
  const idx = state.messages.length
  setState("messages", idx, { role, content, done: false })
  return idx
}

export function appendToken(idx: number, token: string) {
  setState("messages", idx, "content", (prev) => prev + token)
}

export function appendThinking(idx: number, chunk: string) {
  setState("messages", idx, "thinking", (prev) => (prev ?? "") + chunk)
}

export function finalizeMessage(idx: number, edits?: EditResult[]) {
  setState("messages", idx, "done", true)
  if (edits) setState("messages", idx, "edits", edits)
}

export function setContextFiles(files: ContextFile[], totalTokens: number) {
  setState("contextFiles", files)
  setState("totalTokens", totalTokens)
}

export function clearMessages() {
  setState("messages", [])
}

export function resetAll() {
  setState("messages", [])
  setState("contextFiles", [])
  setState("totalTokens", 0)
}
