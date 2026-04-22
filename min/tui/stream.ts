// stream.ts — SSE consumer, parse semua event dari backend

import {
  setState,
  pushMessage,
  appendToken,
  finalizeMessage,
  setContextFiles,
  clearMessages,
  resetAll,
  type EditResult,
  type ContextFile,
} from "./state.ts"

// ── Constants ─────────────────────────────────────────────────────────────────

const HEARTBEAT_TIMEOUT_MS = 30_000  // 30s tanpa ping → anggap mati

// ── Event payloads ────────────────────────────────────────────────────────────
// Sesuai backend main.py yield sse(...)

interface TokenEvent   { content: string }
interface EditEvent    { file: string; diff: string; success: boolean; error?: string }
interface DoneEvent    { input_tokens: number; output_tokens: number }
interface ErrorEvent   { message: string }
interface ContextEvent { files: ContextFile[]; total_tokens?: number }
interface ModelEvent   { model: string }
interface TokensEvent  { context_tokens: number; session_tokens: number }
interface DiffEvent    { diffs: Array<{ file: string; diff: string }> }
interface RunEvent     { output: string; returncode: number }
interface CommitEvent  { output: string }
interface TextEvent    { content: string }  // /help output dll

// ── Main consumer ─────────────────────────────────────────────────────────────

let _renderer: any = null

export function setRenderer(r: any) {
  _renderer = r
}

function redraw() {
  if (_renderer) _renderer.intermediateRender()
}

export async function consumeStream(response: Response): Promise<void> {
  const reader = response.body?.getReader()
  if (!reader) throw new Error("Response body is null")

  const decoder = new TextDecoder()
  let buffer = ""
  let heartbeatTimer: ReturnType<typeof setTimeout> | null = null
  let assistantIdx = -1           // index message assistant yang sedang diisi
  const pendingEdits: EditResult[] = []

  function resetHeartbeat() {
    if (heartbeatTimer) clearTimeout(heartbeatTimer)
    heartbeatTimer = setTimeout(() => {
      setState("error", "Connection lost (heartbeat timeout)")
      setState("streaming", false)
    }, HEARTBEAT_TIMEOUT_MS)
  }

  function stopHeartbeat() {
    if (heartbeatTimer) {
      clearTimeout(heartbeatTimer)
      heartbeatTimer = null
    }
  }

  function handleEvent(eventType: string, raw: string) {
    // ping — reset heartbeat, tidak ada payload penting
    if (eventType === "ping") {
      resetHeartbeat()
      return
    }

    let data: Record<string, unknown>
    try {
      data = JSON.parse(raw)
    } catch {
      return
    }

    switch (eventType) {
      case "token": {
        const e = data as unknown as TokenEvent
        if (assistantIdx === -1) {
          // Mulai message assistant baru
          assistantIdx = pushMessage("assistant")
          setState("streaming", true)
          setState("error", null)
        }
        appendToken(assistantIdx, e.content)
        redraw()
        resetHeartbeat()
        break
      }

      case "edit": {
        const e = data as unknown as EditEvent
        pendingEdits.push({
          file: e.file,
          diff: e.diff,
          success: e.success,
          error: e.error,
        })
        resetHeartbeat()
        break
      }

      case "done": {
        const e = data as unknown as DoneEvent
        if (assistantIdx !== -1) {
          finalizeMessage(assistantIdx, pendingEdits.length ? [...pendingEdits] : undefined)
        }
        setState("streaming", false)
        redraw()
        setState("inputTokens", (prev) => prev + (e.input_tokens ?? 0))
        setState("outputTokens", (prev) => prev + (e.output_tokens ?? 0))
        assistantIdx = -1
        pendingEdits.length = 0
        stopHeartbeat()
        break
      }

      case "error": {
        const e = data as unknown as ErrorEvent
        setState("error", e.message)
        setState("streaming", false)
        redraw()
        if (assistantIdx !== -1) {
          finalizeMessage(assistantIdx)
          assistantIdx = -1
        }
        stopHeartbeat()
        break
      }

      case "context": {
        const e = data as unknown as ContextEvent
        setContextFiles(
          e.files as ContextFile[],
          e.total_tokens ?? e.files.reduce((s, f) => s + (f.token_count ?? 0), 0)
        )
        redraw()
        break
      }

      case "model": {
        const e = data as unknown as ModelEvent
        setState("model", e.model)
        redraw()
        break
      }

      case "tokens": {
        const e = data as unknown as TokensEvent
        setState("totalTokens", e.context_tokens)
        break
      }

      case "clear": {
        clearMessages()
        redraw()
        break
      }

      case "reset": {
        resetAll()
        redraw()
        break
      }

      case "text": {
        // Output teks biasa dari commands (/help, /run, dll)
        const e = data as unknown as TextEvent
        const idx = pushMessage("assistant", e.content)
        finalizeMessage(idx)
        redraw()
        break
      }

      case "diff":
      case "commit":
      case "run":
      case "undo":
        // Tampilkan sebagai system message
        {
          const content = JSON.stringify(data, null, 2)
          const idx = pushMessage("system", content)
          finalizeMessage(idx)
          redraw()
        }
        break
    }
  }

  // ── Parse loop ──────────────────────────────────────────────────────────────
  resetHeartbeat()

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })

      // SSE format: "event: <type>\ndata: <json>\n\n"
      const blocks = buffer.split("\n\n")
      buffer = blocks.pop() ?? ""   // sisa yang belum complete

      for (const block of blocks) {
        if (!block.trim()) continue

        let eventType = "message"
        let dataLine = ""

        for (const line of block.split("\n")) {
          if (line.startsWith("event: ")) {
            eventType = line.slice(7).trim()
          } else if (line.startsWith("data: ")) {
            dataLine = line.slice(6)
          }
        }

        if (dataLine) handleEvent(eventType, dataLine)
      }
    }
  } finally {
    stopHeartbeat()
    reader.releaseLock()
  }
}
