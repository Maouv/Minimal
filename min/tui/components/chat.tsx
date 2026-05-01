// chat.tsx — full width chat, no sidebar
// Layout: empty state | messages list
// User msg: input-box style (glyph ✦ + text)
// AI msg: plain text body + optional thinking + code/diff blocks
import { For, Show, createMemo } from "solid-js"
import { state, type Message } from "../state.ts"
import { C, getMonokaiStyle } from "../theme.ts"


// ── Empty state ───────────────────────────────────────────────────────────────
// Center: logo ✦ besar + "minimal", lalu 2 history preview box
function EmptyState() {
  return (
    <box
      width="100%"
      flexGrow={1}
      flexDirection="column"
      alignItems="center"
      justifyContent="center"
      backgroundColor={C.bg}
      marginTop={3}
    >
      {/* Logo + brand */}
      <box flexDirection="row" alignItems="center" marginBottom={3}>
        <text fg={C.blue}>{"✦  "}</text>
        <text fg={C.white}>Minimal</text>
      </box>

      {/* History preview items — sama style dengan user message */}
      <box flexDirection="column" width={50}>
        <box
          width="100%"
          flexDirection="row"
          backgroundColor={C.bg2}
          paddingLeft={2}
          paddingRight={2}
          paddingTop={1}
          paddingBottom={1}
          marginBottom={1}
        >
          <text fg={C.blue} marginRight={1}>✦</text>
          <text fg={C.white} flexWrap="wrap">Can you fix null pointer on context.py line 42?</text>
        </box>
        <box
          width="100%"
          flexDirection="row"
          backgroundColor={C.bg2}
          paddingLeft={2}
          paddingRight={2}
          paddingTop={1}
          paddingBottom={1}
        >
          <text fg={C.blue} marginRight={1}>✦</text>
          <text fg={C.gray} flexWrap="wrap">/edit-block fix null pointer in context.py</text>
        </box>
      </box>
    </box>
  )
}

// ── User message ──────────────────────────────────────────────────────────────
// Box bg2 sama persis dengan input bar: margin 1, glyph ✦, teks
function UserMsg(props: { content: string }) {
  return (
    <box width="100%" backgroundColor={C.bg} paddingLeft={1} paddingRight={3}>
      <box
        width="100%"
        flexDirection="row"
        paddingLeft={1}
        paddingTop={1}
        paddingRight={3}
        paddingBottom={1}
        marginLeft={1}
        marginRight={1}
        marginTop={1}
        backgroundColor={C.bg2}
      >
        <text fg={C.blue} marginRight={1}>✦</text>
        <text fg={C.white} flexGrow={1} flexWrap="wrap">{props.content}</text>
      </box>
    </box>
  )
}

// ── System message ────────────────────────────────────────────────────────────
// Untuk output /run, /undo, /diff, /commit — monospace, dim
function SystemMsg(props: { content: string }) {
  return (
    <box
      width="100%"
      paddingLeft={3}
      paddingRight={3}
      paddingTop={1}
      paddingBottom={1}
      backgroundColor={C.bg}
    >
      <text fg={C.gray} flexWrap="wrap">{props.content}</text>
    </box>
  )
}

// ── AI message ────────────────────────────────────────────────────────────────

function stripEditBlocks(content: string): string {
  // Remove SEARCH/REPLACE blocks (<<<<<<< SEARCH ... >>>>>>> REPLACE)
  let out = content.replace(/^.*\n?<<<<<<< SEARCH[\s\S]*?>>>>>>> REPLACE[^\n]*/gm, "")
  // Remove <file path="...">...</file> blocks
  out = out.replace(/<file\s[^>]*>[\s\S]*?<\/file>/g, "")
  // Remove bare file paths on their own line (e.g. /root/minimal/min/tests/TEST.md)
  out = out.replace(/^\/[^\n]+\.(md|py|ts|tsx|js|jsx|json|yaml|yml|toml|sh|txt|go|rs|c|cpp)\s*$/gm, "")
  // Remove ```diff blocks (shown in diff renderable already)
  out = out.replace(/```(?:diff|udiff)[^`]*```/gs, "")
  // Collapse 3+ blank lines to 2
  out = out.replace(/\n{3,}/g, "\n\n")
  return out.trim()
}

// ── Diff renderer — claude code style: line numbers + truncate ────────────────
// Tidak ada scrollbar. Teks panjang truncate dengan … di ujung.
// Line number di kiri abu-abu, sign +/- di tengah, konten di kanan.
function DiffBlock(props: { diff: string; file: string }) {
  const parsed = createMemo(() => {
    const lines: Array<{ type: "added"|"removed"|"context"; lineNo: number; content: string }> = []
    let lineNo = 0
    for (const raw of props.diff.split("\n")) {
      if (raw.startsWith("---") || raw.startsWith("+++")) continue
      if (raw.startsWith("@@")) {
        // Extract starting line number dari @@ -x,y +a,b @@
        const m = raw.match(/@@ [+-]\d+(?:,\d+)? [+-](\d+)/)
        if (m) lineNo = parseInt(m[1]) - 1
        continue
      }
      if (raw === "") continue
      const sign = raw[0]
      const content = raw.slice(1)
      if (sign === "+") {
        lineNo++
        lines.push({ type: "added", lineNo, content })
      } else if (sign === "-") {
        lines.push({ type: "removed", lineNo: 0, content })
      } else {
        lineNo++
        lines.push({ type: "context", lineNo, content })
      }
    }
    return lines
  })

  return (
    <box width="100%" flexDirection="column">
      <For each={parsed()}>
        {(line) => (
          <box
            width="100%"
            flexDirection="row"
            backgroundColor={
              line.type === "added"   ? "#0d1a00" :
              line.type === "removed" ? "#1a0009" : "transparent"
            }
          >
            {/* line number */}
            <text fg={C.gray2} width={4} marginRight={1}>
              {line.type === "removed" ? "" : String(line.lineNo)}
            </text>
            {/* sign */}
            <text fg={line.type === "added" ? C.gdim : line.type === "removed" ? C.pink : C.gray2} width={1} marginRight={1}>
              {line.type === "added" ? "+" : line.type === "removed" ? "-" : " "}
            </text>
            {/* content — truncate kalau terlalu panjang */}
            <text
              fg={line.type === "added" ? C.green : line.type === "removed" ? C.pink : C.gray}
              flexGrow={1}
              truncate
            >
              {line.content}
            </text>
          </box>
        )}
      </For>
    </box>
  )
}

// ── AI message ────────────────────────────────────────────────────────────────
function AiMsg(props: { msg: Message }) {
  const syntaxStyle = getMonokaiStyle()

  // Saat streaming: strip tiap update.
  // Setelah done: pakai displayContent yang sudah di-compute sekali di state level.
  const isDone = createMemo(() => props.msg.done)
  const content = createMemo(() => {
    if (isDone() && props.msg.displayContent !== undefined) {
      return props.msg.displayContent
    }
    return stripEditBlocks(props.msg.content)
  })
  // Frozen edits snapshot — setelah done tidak perlu re-subscribe
  let _frozenEdits: typeof props.msg.edits = undefined
  const edits = createMemo(() => {
    if (isDone()) {
      if (_frozenEdits === undefined) _frozenEdits = props.msg.edits
      return _frozenEdits
    }
    return props.msg.edits
  })

  return (
    <box
      width="100%"
      flexDirection="column"
      paddingLeft={3}
      paddingRight={3}
      paddingTop={1}
      paddingBottom={1}
      backgroundColor={C.bg}
    >
      {/* Content — markdown dengan syntax highlight */}
      <markdown
        content={content()}
        syntaxStyle={syntaxStyle}
        conceal
        fg={C.white}
        streaming={!isDone()}
        width="100%"
      />

      {/* Diff blocks — hanya render setelah done */}
      <Show when={isDone() && edits() && edits()!.length > 0}>
        <For each={edits()}>
          {(edit) => {
            const added   = (edit.diff.match(/^\+[^+]/mg) ?? []).length
            const removed = (edit.diff.match(/^-[^-]/mg) ?? []).length
            return (
              <box
                width="100%"
                flexDirection="column"
                marginTop={1}
                marginLeft={1}
                marginRight={1}
                border
                borderColor={C.border}
                overflow="hidden"
              >
                {/* diff header */}
                <box
                  width="100%"
                  flexDirection="row"
                  height={1}
                  paddingLeft={1}
                  paddingRight={1}
                  backgroundColor={C.bg2}
                  overflow="hidden"
                >
                  <text fg={C.cyan} flexShrink={1} flexGrow={0}>{edit.file.split("/").pop()}</text>
                  <text fg={C.gray2}>{`  +${added} -${removed}`}</text>
                  <box flexGrow={1} />
                  <text fg={edit.success ? C.green : C.pink} flexShrink={0}>
                    {edit.success ? "applied" : (edit.error ?? "failed")}
                  </text>
                </box>
                {/* diff body — horizontal scroll + syntax highlight */}
                <Show when={edit.diff}>
                  <DiffBlock diff={edit.diff} file={edit.file} />
                </Show>
              </box>
            )
          }}
        </For>
      </Show>
    </box>
  )
}

// ── Chat view ─────────────────────────────────────────────────────────────────
const MESSAGE_CAP = 50  // max message di DOM sekaligus

export function ChatView() {
  const hasMessages = createMemo(() => state.messages.length > 0)

  // Hanya render MESSAGE_CAP message terakhir.
  // Semua message tetap ada di state (tidak hilang), tapi
  // yang lama tidak di-mount ke DOM → tidak ada layout cost.
  const visibleMessages = createMemo(() => {
    const msgs = state.messages
    if (msgs.length <= MESSAGE_CAP) return msgs
    return msgs.slice(msgs.length - MESSAGE_CAP)
  })

  return (
    <scrollbox
      flexGrow={1}
      scrollY
      stickyScroll
      stickyStart="bottom"
      backgroundColor={C.bg}
      verticalScrollbarOptions={{
        trackOptions: {
          foregroundColor: C.bg,
          backgroundColor: C.bg,
        },
      }}
    >
      <box width="100%" flexDirection="column">
        <Show when={!hasMessages()}>
          <EmptyState />
        </Show>
        <For each={visibleMessages()}>
          {(msg) => (
            <Show
              when={msg.role === "user"}
              fallback={
                <Show
                  when={msg.role === "system"}
                  fallback={<AiMsg msg={msg} />}
                >
                  <SystemMsg content={msg.content} />
                </Show>
              }
            >
              <UserMsg content={msg.content} />
            </Show>
          )}
        </For>
      </box>
    </scrollbox>
  )
}

