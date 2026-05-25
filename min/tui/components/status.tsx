// status.tsx — CtxBar di atas input: context files list + token count
import { createMemo, For, Show } from "solid-js";
import { state } from "../state.ts";
import { C, MODE_COLOR } from "../theme.ts";

const SPINNER_FRAMES = ["✦ · · ·", "· ✦ · ·", "· · ✦ ·", "· · · ✦"] as const;

function fmtK(n: number): string {
	return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n);
}

// ── StatusBar — tidak dipakai di app.tsx saat ini, tapi dipertahankan ─────────
export function StatusBar() {
	const modeColor = createMemo(() => MODE_COLOR[state.mode] ?? C.cyan);
	const modeLabel = createMemo(() => {
		if (state.streaming) return SPINNER_FRAMES[state.thinkingFrame] ?? SPINNER_FRAMES[0];
		const m: Record<string, string> = { ask: "Ask", "edit-block": "Edit", "edit-udiff": "Edit", "edit-whole": "Edit", think: "◆ Think" };
		return m[state.mode] ?? state.mode;
	});
	return (
		<box width="100%" height={1} flexDirection="row" alignItems="center" backgroundColor={C.bg} paddingLeft={2} paddingRight={2}>
			<text fg={modeColor()}>{modeLabel()}</text>
			<text fg={C.gray2}>{" · "}</text>
			<text fg={C.gray}>{state.model || "—"}</text>
			<box flexGrow={1} />
			<text fg={C.gray3}>minimal</text>
		</box>
	);
}

// ── CtxBar — di atas input, selalu render ────────────────────────────────────
// Collapsed (default): context.py · llm.py  +4 more    ^x expand
// Expanded (ctrl+x):   context.py
//                      llm.py (read-only)
//                      coder.py
//                      ...

const CTX_MAX_COLLAPSED = 3;

function resolveDisplayName(path: string, allPaths: string[]): string {
	const parts = path.replace(/\\/g, "/").split("/");
	const base = parts[parts.length - 1];
	const parent = parts[parts.length - 2] ?? "";
	const collision = allPaths.some((p) => {
		if (p === path) return false;
		return p.replace(/\\/g, "/").split("/").pop() === base;
	});
	return collision && parent ? `${parent}/${base}` : base;
}

export function CtxBar() {
	const files = createMemo(() => state.contextFiles);
	const allPaths = createMemo(() => files().map((f) => f.path));
	const expanded = createMemo(() => state.ctxBarExpanded);
	const overflow = createMemo(() => Math.max(0, files().length - CTX_MAX_COLLAPSED));
	const visibleCollapsed = createMemo(() => files().slice(0, CTX_MAX_COLLAPSED));

	return (
		<Show when={files().length > 0}>
			<box
				width="100%"
				flexDirection="column"
				backgroundColor={C.bg}
				paddingLeft={2}
				paddingRight={2}
			>
				<Show
					when={expanded()}
					fallback={
						/* Collapsed row */
						<box width="100%" height={1} flexDirection="row" alignItems="center" overflow="hidden">
							<For each={visibleCollapsed()}>
								{(f, i) => (
									<box flexDirection="row">
										<Show when={i() > 0}>
											<text fg={C.gray3}>{" · "}</text>
										</Show>
										<text fg={f.readonly ? C.gray3 : C.gray} truncate>
											{resolveDisplayName(f.path, allPaths())}
										</text>
									</box>
								)}
							</For>
							<Show when={overflow() > 0}>
								<text fg={C.gray3}>{`  +${overflow()} more`}</text>
							</Show>
							<box flexGrow={1} />
							<text fg={C.gray3}>{"^x"}</text>
						</box>
					}
				>
					{/* Expanded — one file per row */}
					<For each={files()}>
						{(f) => (
							<box width="100%" height={1} flexDirection="row" alignItems="center">
								<text fg={f.readonly ? C.gray3 : C.gray}>
									{resolveDisplayName(f.path, allPaths())}
								</text>
								<Show when={f.readonly}>
									<text fg={C.gray3}>{" (ro)"}</text>
								</Show>
								<text fg={C.gray3}>{`  ${fmtK(f.token_count ?? 0)}`}</text>
							</box>
						)}
					</For>
					<box width="100%" height={1} flexDirection="row">
						<box flexGrow={1} />
						<text fg={C.gray3}>{"^x collapse"}</text>
					</box>
				</Show>
			</box>
		</Show>
	);
}
