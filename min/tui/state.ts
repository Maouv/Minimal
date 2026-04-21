// state.ts — solid-js store: single source of truth untuk semua TUI state

import { createStore } from "solid-js/store"

// ── Types ────────────────────────────────────────────────────────────────────

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
  content: string            // teks akumulasi (stream token masuk sini)
  edits?: EditResult[]       // kalau assistant message ada edit
  done: boolean              // false = masih streaming
}

export interface AppState {
  // Session
  sessionId: string | null
  model: string

  // Mode & streaming
  mode: Mode
  streaming: boolean

  // Messages
  messages: Message[]

  // Context files
  contextFiles: ContextFile[]
  totalTokens: number

  // Token usage sesi ini
  inputTokens: number
  outputTokens: number

  // Error banner (null = tidak ada)
  error: string | null
}

// ── Initial state ─────────────────────────────────────────────────────────────

const initialState: AppState = {
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
}

// ── Store ─────────────────────────────────────────────────────────────────────

export const [state, setState] = createStore<AppState>(initialState)

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Tambah message baru ke history */
export function pushMessage(role: MessageRole, content: string = ""): number {
  const idx = state.messages.length
  setState("messages", idx, { role, content, done: false })
  return idx
}

/** Append token ke message terakhir (streaming) */
export function appendToken(idx: number, token: string) {
  setState("messages", idx, "content", (prev) => prev + token)
}

/** Tandai message selesai, opsional tambah edits */
export function finalizeMessage(idx: number, edits?: EditResult[]) {
  setState("messages", idx, "done", true)
  if (edits) setState("messages", idx, "edits", edits)
}

/** Update context files dari event backend */
export function setContextFiles(files: ContextFile[], totalTokens: number) {
  setState("contextFiles", files)
  setState("totalTokens", totalTokens)
}

/** Clear semua messages (tapi pertahankan context) */
export function clearMessages() {
  setState("messages", [])
}

/** Reset messages + context */
export function resetAll() {
  setState("messages", [])
  setState("contextFiles", [])
  setState("totalTokens", 0)
}
