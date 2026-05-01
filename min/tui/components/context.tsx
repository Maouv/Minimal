// context.tsx — sidebar kiri, daftar context files
import { For, Show } from "solid-js";
import { state } from "../state.ts";
import { C } from "../theme.ts";

function fmtK(n: number): string {
	return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n);
}

export function ContextPanel() {
	return (
		<box
			width={26}
			flexGrow={0}
			flexShrink={0}
			flexDirection="column"
			backgroundColor={C.bg2}
			border={["right"]}
			borderColor={C.border}
		>
			{/* Header */}
			<box width="100%" height={1} paddingLeft={1} backgroundColor={C.bg2}>
				<text fg={C.gray}>context</text>
			</box>

			{/* File list */}
			<scrollbox flexGrow={1} scrollY>
				<box
					width="100%"
					flexDirection="column"
					paddingLeft={1}
					paddingRight={1}
				>
					<Show
						when={state.contextFiles.length > 0}
						fallback={<text fg={C.border}>no files</text>}
					>
						<For each={state.contextFiles}>
							{(f) => {
								const parts = f.path.replace(/\\/g, "/").split("/");
								const name = parts[parts.length - 1];
								const dir =
									parts.length > 1 ? `${parts[parts.length - 2]}/` : "";
								const tok = f.token_count > 0 ? ` ${fmtK(f.token_count)}` : "";
								return (
									<box width="100%" flexDirection="column" marginBottom={0}>
										<text fg={f.readonly ? C.gray : C.green}>
											{(f.readonly ? "○ " : "● ") + name}
										</text>
										<text fg={C.border} paddingLeft={2}>
											{dir + tok}
										</text>
									</box>
								);
							}}
						</For>
					</Show>
				</box>
			</scrollbox>

			{/* Footer token total */}
			<box width="100%" height={1} paddingLeft={1} backgroundColor={C.bg2}>
				<text fg={C.border}>
					{state.totalTokens > 0 ? `${fmtK(state.totalTokens)} tok` : ""}
				</text>
			</box>
		</box>
	);
}
