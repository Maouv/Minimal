// status.tsx — status bar paling bawah: Ask · glm-5  Out 0→...  minimal
// + ctx-bar di atas input: context.py · llm.py +2   12.4k tok
import { createMemo, For, Show } from "solid-js";
import { state } from "../state.ts";
import { C, MODE_COLOR } from "../theme.ts";

const SPINNER_FRAMES = ["✦ · · ·", "· ✦ · ·", "· · ✦ ·", "· · · ✦"] as const;

function fmtK(n: number): string {
	return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n);
}

// ── Status bar — paling bawah ─────────────────────────────────────────────────
// Ask · glm-5  Out 847  [sess:abc123]                    minimal
// Saat streaming: mode label jadi spinner ✦ · · ·
// Saat think + tool aktif: spinner + nama tool
export function StatusBar() {
	const modeColor = createMemo(() => MODE_COLOR[state.mode] ?? C.cyan);

	const modeLabel = createMemo(() => {
		if (state.streaming) {
			const frame = SPINNER_FRAMES[state.thinkingFrame] ?? SPINNER_FRAMES[0];
			if (state.mode === "think" && state.thinkActiveTool) {
				return `${frame}  ${state.thinkActiveTool}…`;
			}
			return frame;
		}
		const m: Record<string, string> = {
			ask: "Ask",
			"edit-block": "Edit",
			"edit-udiff": "Edit",
			"edit-whole": "Edit",
			think: "◆ Think",
		};
		return m[state.mode] ?? state.mode;
	});

	const shortSession = createMemo(() => {
		const sid = state.sessionId;
		if (!sid) return "";
		return sid.length > 8 ? sid.slice(-8) : sid;
	});

	// liveOutputTokens streaming naik 0→1→2→... per token flush
	const outStr = createMemo(() =>
		state.streaming ? `Out ${fmtK(state.liveOutputTokens)}` : "",
	);

	return (
		<box
			width="100%"
			height={1}
			flexDirection="row"
			alignItems="center"
			backgroundColor={C.bg}
			paddingLeft={2}
			paddingRight={2}
		>
			<text fg={modeColor()}>{modeLabel()}</text>
			<text fg={C.gray2}>{" · "}</text>
			<text fg={C.gray}>{state.model || "—"}</text>
			<Show when={state.streaming}>
				<text fg={C.gray2}>{"  "}</text>
				<text fg={C.gray}>{outStr()}</text>
			</Show>
			<Show when={shortSession()}>
				<text fg={C.gray3}>{`  [${shortSession()}]`}</text>
			</Show>
			<Show when={state.error}>
				<text fg={C.gray2}>{" · "}</text>
				<text fg={C.pink}>{state.error?.slice(0, 40)}</text>
			</Show>
			<box flexGrow={1} />
			<text fg={C.gray3}>minimal</text>
		</box>
	);
}

// ── Context bar — di atas input ───────────────────────────────────────────────
// context.py · llm.py · coder.py +4 more     12.4k tok

const CTX_MAX_DISPLAY = 3;

function resolveDisplayName(path: string, allPaths: string[]): string {
	const parts = path.replace(/\\/g, "/").split("/");
	const base = parts[parts.length - 1];
	const parent = parts[parts.length - 2] ?? "";
	// show parent/base only if another file shares the same basename
	const collision = allPaths.some((p) => {
		if (p === path) return false;
		const b = p.replace(/\\/g, "/").split("/").pop();
		return b === base;
	});
	return collision && parent ? `${parent}/${base}` : base;
}

export function CtxBar() {
	const hasFiles = createMemo(() => state.contextFiles.length > 0);
	const tokStr = createMemo(() =>
		state.totalTokens > 0 ? `${fmtK(state.totalTokens)} tok` : "",
	);
	const allPaths = createMemo(() => state.contextFiles.map((f) => f.path));
	const visible = createMemo(() =>
		state.contextFiles.slice(0, CTX_MAX_DISPLAY),
	);
	const overflow = createMemo(
		() => state.contextFiles.length - CTX_MAX_DISPLAY,
	);

	return (
		<Show when={hasFiles()}>
			<box
				width="100%"
				height={1}
				flexDirection="row"
				alignItems="center"
				overflow="hidden"
				backgroundColor={C.bg}
				paddingLeft={2}
				paddingRight={2}
			>
				<For each={visible()}>
					{(f, i) => (
						<box flexDirection="row">
							<Show when={i() > 0}>
								<text fg={C.gray3}>{" · "}</text>
							</Show>
							<text fg={C.gray} truncate>
								{resolveDisplayName(f.path, allPaths())}
							</text>
						</box>
					)}
				</For>
				<Show when={overflow() > 0}>
					<text fg={C.gray3}>{` +${overflow()}`}</text>
				</Show>
				<box flexGrow={1} />
				<text fg={C.gray2}>{tokStr()}</text>
			</box>
		</Show>
	);
}
