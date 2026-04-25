// stream.ts — SSE consumer, parse semua event dari backend

import {
  state,
  setState,
  pushMessage,
  appendToken,
  appendThinking,
  finalizeMessage,
  setContextFiles,
  clearMessages,
  resetAll,
  type EditResult,
  type ContextFile,
} from "./state.ts"

// ── Constants ─────────────────────────────────────────────────────────────────

const HEARTBEAT_TIMEOUT_MS = 30_000  // 30s tanpa ping → anggap mati
const TOKEN_FLUSH_MS = 32            // ~30 FPS — flush token buffer ke state

// ── Event payloads ────────────────────────────────────────────────────────────
// Sesuai backend main.py yield sse(...)

interface TokenEvent    { content: string }
interface ThinkingEvent { content: string }
interface EditEvent     { file: string; diff: string; success: boolean; error?: string }
interface DoneEvent     { input_tokens: number; output_tokens: number }
interface ErrorEvent    { message: string }
interface ContextEvent  { files: ContextFile[]; total_tokens?: number }
interface ModelEvent    { model: string }
interface TokensEvent   { context_tokens: number; session_tokens: number }
interface DiffEvent     { diffs: Array<{ file: string; diff: string }> }
interface RunEvent      { output: string; returncode: number }
interface CommitEvent   { output: string }
interface UndoEvent     { files: string[] }
interface TextEvent     { content: string }
interface AppliedSummaryEvent { message: string; applied: string[]; failed: string[] }

// ── Main consumer ─────────────────────────────────────────────────────────────

export async function consumeStream(response: Response): Promise<void> {
  const reader = response.body?.getReader()
  if (!reader) throw new Error("Response body is null")

  const decoder = new TextDecoder()
  let buffer = ""
  let heartbeatTimer: ReturnType<typeof setTimeout> | null = null
  let assistantIdx = -1           // index message assistant yang sedang diisi
  const pendingEdits: EditResult[] = []

  // ── Token throttle buffer ──────────────────────────────────────────────────
  let tokenBuffer = ""
  let thinkingBuffer = ""
  let flushTimer: ReturnType<typeof setTimeout> | null = null

  function flushTokens() {
    flushTimer = null
    if (assistantIdx === -1) return
    if (tokenBuffer !== "") {
      appendToken(assistantIdx, tokenBuffer)
      tokenBuffer = ""
    }
    if (thinkingBuffer !== "") {
      appendThinking(assistantIdx, thinkingBuffer)
      thinkingBuffer = ""
    }
  }

  function scheduleFlush() {
    if (flushTimer === null) {
      flushTimer = setTimeout(flushTokens, TOKEN_FLUSH_MS)
    }
  }

  function flushImmediate() {
    if (flushTimer !== null) {
      clearTimeout(flushTimer)
      flushTimer = null
    }
    flushTokens()
  }

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

  function ensureAssistantMessage() {
    if (assistantIdx === -1) {
      flushImmediate()
      assistantIdx = pushMessage("assistant")
      setState("streaming", true)
      setState("error", null)
    }
  }

  function handleEvent(eventType: string, raw: string) {
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
        ensureAssistantMessage()
        tokenBuffer += e.content
        scheduleFlush()
        resetHeartbeat()
        break
      }

      case "thinking": {
        const e = data as unknown as ThinkingEvent
        ensureAssistantMessage()
        thinkingBuffer += e.content
        scheduleFlush()
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

      case "applied_summary": {
        const e = data as unknown as AppliedSummaryEvent
        flushImmediate()
        const idx = pushMessage("system", e.message)
        finalizeMessage(idx)
        break
      }

      case "exit": {
        // Backend minta TUI keluar
        flushImmediate()
        setState("streaming", false)
        stopHeartbeat()
        process.exit(0)
        break
      }

      case "done": {
        const e = data as unknown as DoneEvent
        flushImmediate()
        if (assistantIdx !== -1) {
          const idx = assistantIdx
          const edits = pendingEdits.length ? [...pendingEdits] : undefined
          finalizeMessage(idx, edits)
          // Set displayContent sekali — computed saat finalize, tidak re-compute saat scroll
          const rawContent = state.messages[idx]?.content ?? ""
          const stripped = rawContent
            .replace(/^[^\n]*\n?<<<<<<< SEARCH[\s\S]*?>>>>>>> REPLACE[^\n]*/gm, "")
            .replace(/<file\s[^>]*>[\s\S]*?<\/file>/g, "")
            .replace(/^\/[^\n]+\.(md|py|ts|tsx|js|jsx|json|yaml|yml|toml|sh|txt|go|rs|c|cpp)\s*$/gm, "")
            .replace(/```(?:diff|udiff)[\s\S]*?```/g, "")
            .replace(/\n{3,}/g, "\n\n")
            .trim()
          setState("messages", idx, "displayContent", stripped)
        }
        setState("streaming", false)
        setState("inputTokens", state.inputTokens + (e.input_tokens ?? 0))
        setState("outputTokens", state.outputTokens + (e.output_tokens ?? 0))
        assistantIdx = -1
        pendingEdits.length = 0
        stopHeartbeat()
        break
      }

      case "error": {
        const e = data as unknown as ErrorEvent
        flushImmediate()
        setState("error", e.message)
        setState("streaming", false)
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
        setState("error", null)
        break
      }

      case "model": {
        const e = data as unknown as ModelEvent
        setState("model", e.model)
        break
      }

      case "mode": {
        const e = data as unknown as { mode: string }
        setState("mode", e.mode as any)
        break
      }

      case "tokens": {
        const e = data as unknown as TokensEvent
        setState("totalTokens", e.context_tokens)
        break
      }

      case "clear": {
        clearMessages()
        break
      }

      case "reset": {
        resetAll()
        break
      }

      case "text": {
        const e = data as unknown as TextEvent
        const idx = pushMessage("assistant", e.content)
        finalizeMessage(idx)
        break
      }

      case "diff": {
        const e = data as unknown as DiffEvent
        if (e.diffs && e.diffs.length > 0) {
          const lines = e.diffs.map(d => `── ${d.file} ──\n${d.diff}`).join("\n\n")
          const idx = pushMessage("system", lines)
          finalizeMessage(idx)
        }
        break
      }

      case "commit": {
        const e = data as unknown as CommitEvent
        const idx = pushMessage("system", `✓ committed\n${e.output}`)
        finalizeMessage(idx)
        break
      }

      case "run": {
        const e = data as unknown as RunEvent
        const prefix = e.returncode === 0 ? "✓" : `✗ (exit ${e.returncode})`
        const idx = pushMessage("system", `${prefix}\n${e.output}`)
        finalizeMessage(idx)
        break
      }

      case "undo": {
        const e = data as unknown as UndoEvent
        const list = e.files.join(", ")
        const idx = pushMessage("system", `↩ undone: ${list}`)
        finalizeMessage(idx)
        break
      }
    }
  }

  // ── Parse loop ──────────────────────────────────────────────────────────────
  resetHeartbeat()

      try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        const blocks = buffer.split("\n\n");
        buffer = blocks.pop() ?? "";

        for (const block of blocks) {
          if (!block.trim()) continue;

          let eventType = "message";
          let dataLine = "";

          for (const line of block.split("\n")) {
            if (line.startsWith("event: ")) {
              eventType = line.slice(7).trim();
            } else if (line.startsWith("data: ")) {
              dataLine = line.slice(6);
            }
          }

          if (dataLine) handleEvent(eventType, dataLine);
        }
      }
    } finally {
      flushImmediate();
      stopHeartbeat();
      reader.releaseLock();
      setState("streaming", false);
    }
  }; // Penutup fungsi utama (seperti handleStream)


