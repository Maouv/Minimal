// state.ts — solid-js store: single source of truth
import { createStore } from "solid-js/store";

export type Mode = "ask" | "edit-block" | "edit-udiff" | "edit-whole" | "think";
export type MessageRole = "user" | "assistant" | "system";

export interface ContextFile {
	path: string;
	readonly: boolean;
	token_count: number;
}

export interface EditResult {
	file: string;
	diff: string;
	success: boolean;
	error?: string;
}

export interface Message {
	role: MessageRole;
	content: string;
	displayContent?: string; // content setelah strip edit blocks — di-set saat finalize
	thinking?: string; // thinking/reasoning content dari model
	edits?: EditResult[];
	done: boolean;
}

export interface AppState {
	sessionId: string | null;
	model: string;
	mode: Mode;
	streaming: boolean;
	messages: Message[];
	contextFiles: ContextFile[];
	totalTokens: number;
	inputTokens: number;
	outputTokens: number;
	// ── Session output tokens — accumulated dari semua AI turns ──────────────
	// Ini yang di-merge ke Ctx display setiap turn selesai.
	// Reset saat /reset atau /clear. Tidak pernah berkurang.
	sessionOutputTokens: number;
	// ── Thinking indicator state ──────────────────────────────────────────────
	// Updated externally by stream.ts ticker
	thinkingFrame: number;        // 0-3, cycles for ✦ · · · animation
	liveOutputTokens: number;     // estimated output tokens so far (chars ÷ 4)
	lastInputTokens: number;      // input_tokens from last done event
	// ── Think mode state ─────────────────────────────────────────────────────
	thinkActiveTool: string | null;  // tool name currently executing, null if none
	thinkUsedTokens: number;         // accumulated output tokens this think session
	// ─────────────────────────────────────────────────────────────────────────
	error: string | null;
	showModelPicker: "switch" | "add" | false;
	ctxBarExpanded: boolean;  // ctrl+x toggle expand context bar
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
	sessionOutputTokens: 0,
	thinkingFrame: 0,
	liveOutputTokens: 0,
	lastInputTokens: 0,
	thinkActiveTool: null,
	thinkUsedTokens: 0,
	error: null,
	showModelPicker: false,
	ctxBarExpanded: false,
});

export function pushMessage(role: MessageRole, content = ""): number {
	const idx = state.messages.length;
	setState("messages", idx, { role, content, done: false });
	return idx;
}

export function appendToken(idx: number, token: string) {
	setState("messages", idx, "content", (prev) => prev + token);
}

export function appendThinking(idx: number, chunk: string) {
	setState("messages", idx, "thinking", (prev) => (prev ?? "") + chunk);
}

export function finalizeMessage(idx: number, edits?: EditResult[]) {
	setState("messages", idx, "done", true);
	if (edits) setState("messages", idx, "edits", edits);
}

export function setContextFiles(files: ContextFile[], totalTokens: number) {
	setState("contextFiles", files);
	setState("totalTokens", totalTokens);
}

export function clearMessages() {
	setState("messages", []);
}

export function resetAll() {
	setState("messages", []);
	setState("contextFiles", []);
	setState("totalTokens", 0);
	setState("sessionOutputTokens", 0);
}
