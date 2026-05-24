// thinking.tsx — ✦ animated spinner + token counter
// Muncul sebagai placeholder di posisi AI message sebelum token pertama masuk.
// Layout: ✦ · · ·  Ctx 12.4k · Out 847
// Begitu token pertama masuk → komponen ini diganti dengan AiMsg yang actual.

import { createMemo, Show } from "solid-js";
import { state } from "../state.ts";
import { C } from "../theme.ts";

// Frame sequence: ✦ bergerak dari kiri ke kanan, wrap ke frame 0
const FRAMES: ReadonlyArray<string> = [
	"✦ · · ·",
	"· ✦ · ·",
	"· · ✦ ·",
	"· · · ✦",
];

function fmtK(n: number): string {
	return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n);
}

export function ThinkingIndicator() {
	const frame = createMemo(() => FRAMES[state.thinkingFrame] ?? FRAMES[0]);
	const ctxTok = createMemo(() =>
		state.lastInputTokens > 0 ? `Ctx ${fmtK(state.lastInputTokens)}` : "Ctx —",
	);
	const outTok = createMemo(() => `Out ${fmtK(state.liveOutputTokens)}`);

	return (
		<Show when={state.streaming}>
			<box
				width="100%"
				flexDirection="row"
				paddingLeft={3}
				paddingRight={3}
				paddingTop={1}
				paddingBottom={1}
				backgroundColor="transparent"
			>
				<text fg={C.blue} marginRight={2}>
					{frame()}
				</text>
				<text fg={C.gray2}>{ctxTok()}</text>
				<text fg={C.gray3}>{" · "}</text>
				<text fg={C.gray2}>{outTok()}</text>
			</box>
		</Show>
	);
}
