// chat.tsx — full width chat, no sidebar
// Layout: empty state | messages list
// User msg: input-box style (glyph ✦ + text)
// AI msg: plain text body + optional thinking + code/diff blocks
import { createMemo, For, Show } from "solid-js";
import { type EditResult, type Message, state } from "../state.ts";
import { C, getMonokaiStyle } from "../theme.ts";

// ── Empty state ───────────────────────────────────────────────────────────────
function EmptyPromptBox(props: { text: string; dim?: boolean }) {
	return (
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
			<text fg={props.dim ? C.gray : C.white} flexWrap="wrap">{props.text}</text>
		</box>
	);
}

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
			<box flexDirection="row" alignItems="center" marginBottom={3}>
				<text fg={C.blue}>{"✦  "}</text>
				<text fg={C.white}>Minimal</text>
			</box>
			<box flexDirection="column" width={50}>
				<EmptyPromptBox text="Can you fix null pointer on context.py line 42?" />
				<EmptyPromptBox text="/edit-block fix null pointer in context.py" dim />
			</box>
		</box>
	);
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
				<text fg={C.blue} marginRight={1}>
					✦
				</text>
				<text fg={C.white} flexGrow={1} flexWrap="wrap">
					{props.content}
				</text>
			</box>
		</box>
	);
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
			<text fg={C.gray} flexWrap="wrap">
				{props.content}
			</text>
		</box>
	);
}

// ── AI message ────────────────────────────────────────────────────────────────

function stripEditBlocks(content: string): string {
	// Remove SEARCH/REPLACE blocks (<<<<<<< SEARCH ... >>>>>>> REPLACE)
	let out = content.replace(
		/^.*\n?<<<<<<< SEARCH[\s\S]*?>>>>>>> REPLACE[^\n]*/gm,
		"",
	);
	// Remove <file path="...">...</file> blocks
	out = out.replace(/<file\s[^>]*>[\s\S]*?<\/file>/g, "");
	// Remove bare file paths on their own line (e.g. /root/minimal/min/tests/TEST.md)
	out = out.replace(
		/^\/[^\n]+\.(md|py|ts|tsx|js|jsx|json|yaml|yml|toml|sh|txt|go|rs|c|cpp)\s*$/gm,
		"",
	);
	// Remove ```diff blocks (shown in diff renderable already)
	out = out.replace(/```(?:diff|udiff)[^`]*```/gs, "");
	// Collapse 3+ blank lines to 2
	out = out.replace(/\n{3,}/g, "\n\n");
	return out.trim();
}

// ── Diff renderer ─────────────────────────────────────────────────────────────

type DiffLineData = { type: "added" | "removed" | "context"; lineNo: number; content: string };

function parseDiff(raw: string): DiffLineData[] {
	const lines: DiffLineData[] = [];
	let lineNo = 0;
	for (const line of raw.split("\n")) {
		if (line.startsWith("---") || line.startsWith("+++")) continue;
		if (line.startsWith("@@")) {
			const m = line.match(/@@ [+-]\d+(?:,\d+)? [+-](\d+)/);
			if (m) lineNo = parseInt(m[1], 10) - 1;
			continue;
		}
		if (line === "") continue;
		const sign = line[0];
		const content = line.slice(1);
		if (sign === "+") { lineNo++; lines.push({ type: "added", lineNo, content }); }
		else if (sign === "-") { lines.push({ type: "removed", lineNo: 0, content }); }
		else { lineNo++; lines.push({ type: "context", lineNo, content }); }
	}
	return lines;
}

function DiffLine(props: { line: DiffLineData }) {
	const { type, lineNo, content } = props.line;
	const bg = type === "added" ? "#0d1a00" : type === "removed" ? "#1a0009" : "transparent";
	const signFg = type === "added" ? C.gdim : type === "removed" ? C.pink : C.gray2;
	const textFg = type === "added" ? C.green : type === "removed" ? C.pink : C.gray;
	const sign = type === "added" ? "+" : type === "removed" ? "-" : " ";
	return (
		<box width="100%" flexDirection="row" backgroundColor={bg}>
			<text fg={C.gray2} width={4} marginRight={1}>{type === "removed" ? "" : String(lineNo)}</text>
			<text fg={signFg} width={1} marginRight={1}>{sign}</text>
			<text fg={textFg} flexGrow={1} truncate>{content}</text>
		</box>
	);
}

function DiffBlock(props: { diff: string; file: string }) {
	const parsed = createMemo(() => parseDiff(props.diff));
	return (
		<box width="100%" flexDirection="column">
			<For each={parsed()}>{(line) => <DiffLine line={line} />}</For>
		</box>
	);
}

// ── AI message ────────────────────────────────────────────────────────────────

function DiffHeader(props: { edit: EditResult }) {
	const added = (props.edit.diff.match(/^\+[^+]/gm) ?? []).length;
	const removed = (props.edit.diff.match(/^-[^-]/gm) ?? []).length;
	return (
		<box width="100%" flexDirection="row" height={1} paddingLeft={1} paddingRight={1}
			backgroundColor={C.bg2} overflow="hidden"
		>
			<text fg={C.cyan} flexShrink={1} flexGrow={0}>{props.edit.file.split("/").pop()}</text>
			<text fg={C.gray2}>{`  +${added} -${removed}`}</text>
			<box flexGrow={1} />
			<text fg={props.edit.success ? C.green : C.pink} flexShrink={0}>
				{props.edit.success ? "applied" : (props.edit.error ?? "failed")}
			</text>
		</box>
	);
}

function DiffEntry(props: { edit: EditResult }) {
	return (
		<box width="100%" flexDirection="column" marginTop={1} marginLeft={1}
			marginRight={1} border borderColor={C.border} overflow="hidden"
		>
			<DiffHeader edit={props.edit} />
			<Show when={props.edit.diff}>
				<DiffBlock diff={props.edit.diff} file={props.edit.file} />
			</Show>
		</box>
	);
}

function FrozenMsgDiffs(props: { edits?: Message["edits"] }) {
	return (
		<Show when={props.edits && props.edits.length > 0}>
			{/* biome-ignore lint/style/noNonNullAssertion: guarded by Show */}
			<For each={props.edits!}>{(edit) => <DiffEntry edit={edit} />}</For>
		</Show>
	);
}

// FrozenMsgDiffs — rendered inside AiMsg after message done

// Dispatch: frozen vs streaming.
// CRITICAL: kondisi HARUS di dalam JSX (<Show>) bukan di function body,
// supaya Solid bisa track reactive dependency props.msg.done.
// Function body di Solid hanya di-evaluate sekali saat mount — tidak reaktif.
function AiMsg(props: { msg: Message; isStreaming: boolean }) {
	const syntaxStyle = getMonokaiStyle();
	const frozenContent = createMemo(() =>
		props.msg.displayContent ?? stripEditBlocks(props.msg.content),
	);
	const streamContent = createMemo(() => stripEditBlocks(props.msg.content));

	return (
		<Show
			when={!props.isStreaming && props.msg.done}
			fallback={
				// StreamingMsg — reactive per token flush
				<box
					width="100%"
					flexDirection="column"
					paddingLeft={3}
					paddingRight={3}
					paddingTop={1}
					paddingBottom={1}
					backgroundColor={C.bg}
				>
					<markdown
						content={streamContent()}
						syntaxStyle={syntaxStyle}
						conceal
						fg={C.white}
						streaming={true}
						width="100%"
					/>
				</box>
			}
		>
			{/* FrozenMsg — static, no re-renders */}
			<box
				width="100%"
				flexDirection="column"
				paddingLeft={3}
				paddingRight={3}
				paddingTop={1}
				paddingBottom={1}
				backgroundColor={C.bg}
			>
				<markdown
					content={frozenContent()}
					syntaxStyle={syntaxStyle}
					conceal
					fg={C.white}
					streaming={false}
					width="100%"
				/>
				<FrozenMsgDiffs edits={props.msg.edits} />
			</box>
		</Show>
	);
}

// ── Chat view ─────────────────────────────────────────────────────────────────
const MESSAGE_CAP = 50; // max message di DOM sekaligus

function MessageRow(props: { msg: Message; isStreaming: boolean }) {
	if (props.msg.role === "user") return <UserMsg content={props.msg.content} />;
	if (props.msg.role === "system") return <SystemMsg content={props.msg.content} />;
	return <AiMsg msg={props.msg} isStreaming={props.isStreaming} />;
}

export function ChatView() {
	const hasMessages = createMemo(() => state.messages.length > 0);

	const visibleMessages = createMemo(() => {
		const msgs = state.messages;
		if (msgs.length <= MESSAGE_CAP) return msgs;
		return msgs.slice(msgs.length - MESSAGE_CAP);
	});

	const streamingIdx = createMemo(() => {
		if (!state.streaming) return -1;
		const msgs = state.messages;
		for (let i = msgs.length - 1; i >= 0; i--) {
			if (msgs[i].role === "assistant" && !msgs[i].done) return i;
		}
		return -1;
	});

	const offset = createMemo(
		() => state.messages.length - visibleMessages().length,
	);

	return (
		<scrollbox
			flexGrow={1}
			scrollY
			stickyScroll
			stickyStart="bottom"
			backgroundColor={C.bg}
			verticalScrollbarOptions={{ trackOptions: { foregroundColor: C.bg, backgroundColor: C.bg } }}
		>
			<box width="100%" flexDirection="column">
				<Show when={!hasMessages()}><EmptyState /></Show>
				<For each={visibleMessages()}>
					{(msg, i) => (
						<MessageRow
							msg={msg}
							isStreaming={offset() + i() === streamingIdx()}
						/>
					)}
				</For>
			</box>
		</scrollbox>
	);
}
