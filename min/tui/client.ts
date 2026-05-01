// client.ts — HTTP client ke backend port 4096

const BASE = "http://localhost:4096";

async function req<T>(
	method: string,
	path: string,
	body?: unknown,
): Promise<T> {
	const res = await fetch(`${BASE}${path}`, {
		method,
		headers: body ? { "Content-Type": "application/json" } : {},
		body: body ? JSON.stringify(body) : undefined,
	});
	if (!res.ok) {
		const text = await res.text().catch(() => res.statusText);
		throw new Error(`${method} ${path} → ${res.status}: ${text}`);
	}
	return res.json() as Promise<T>;
}

// ── Health ────────────────────────────────────────────────────────────────────

export async function healthCheck(): Promise<boolean> {
	try {
		const data = await req<{ ok: boolean }>("GET", "/health");
		return data.ok === true;
	} catch {
		return false;
	}
}

// ── Config ────────────────────────────────────────────────────────────────────

export interface ConfigResponse {
	base_url: string;
	model: string;
	models: Record<string, string>;
	context_window: number;
	timeout: number;
	max_tokens: number;
	configured: boolean;
}

export async function getConfig(): Promise<ConfigResponse> {
	return req("GET", "/config");
}

export async function setModel(model: string): Promise<void> {
	await req("POST", "/config/providers", { model });
}

// ── Session ───────────────────────────────────────────────────────────────────

export interface SessionMeta {
	session_id: string;
	created_at: string | null;
	model: string | null;
	messages?: { role: string; content: string }[];
}

export async function createSession(model?: string): Promise<SessionMeta> {
	return req("POST", "/session", model ? { model } : {});
}

export async function listSessions(): Promise<SessionMeta[]> {
	const data = await req<{ sessions: SessionMeta[] }>("GET", "/session");
	return data.sessions;
}

export async function getSession(id: string): Promise<SessionMeta> {
	return req("GET", `/session/${id}`);
}

// ── Prompt (returns Response for SSE, caller handles stream) ──────────────────

export async function sendPrompt(
	sessionId: string,
	content: string,
): Promise<Response> {
	const res = await fetch(`${BASE}/session/${sessionId}/init`, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({ content }),
	});
	if (!res.ok) {
		const text = await res.text().catch(() => res.statusText);
		throw new Error(`POST /session/${sessionId}/init → ${res.status}: ${text}`);
	}
	return res; // caller pipes ke stream.ts
}

export async function abortSession(sessionId: string): Promise<void> {
	await req("POST", `/session/${sessionId}/abort`, {});
}

// ── Context ───────────────────────────────────────────────────────────────────

export interface ContextFile {
	path: string;
	readonly: boolean;
	token_count: number;
	last_modified: string;
}

export interface ContextListResponse {
	files: ContextFile[];
	total_tokens: number;
}

export async function contextAdd(
	sessionId: string,
	path: string,
	readonly = false,
): Promise<void> {
	await req("POST", "/context/add", { session_id: sessionId, path, readonly });
}

export async function contextDrop(
	sessionId: string,
	path: string,
): Promise<void> {
	await req("POST", "/context/drop", { session_id: sessionId, path });
}

export async function contextList(
	sessionId: string,
): Promise<ContextListResponse> {
	return req("GET", `/context?session_id=${sessionId}`);
}

// ── Project files ─────────────────────────────────────────────────────────────

export interface ProjectFilesResponse {
	files: string[];
	cwd: string;
}

export async function listProjectFiles(): Promise<ProjectFilesResponse> {
	return req("GET", "/project/files");
}

export interface ProjectEntry {
	name: string; // display name, dirs have trailing /
	path: string; // relative to CWD, dirs have trailing /
	is_dir: boolean;
}

export interface ProjectEntriesResponse {
	entries: ProjectEntry[];
	cwd: string;
}

export async function listProjectEntries(
	path = "",
): Promise<ProjectEntriesResponse> {
	const q = path ? `?path=${encodeURIComponent(path)}` : "";
	return req("GET", `/project/entries${q}`);
}

export interface ProjectDirsResponse {
	dirs: string[];
	cwd: string;
}

export async function listProjectDirs(): Promise<ProjectDirsResponse> {
	return req("GET", "/project/dirs");
}

// ── Providers ─────────────────────────────────────────────────────────────────

export interface Provider {
	name: string;
	base_url: string;
	env_key: string;
	last_model?: string;
}

export interface ProbeResult {
	ok: boolean;
	models: string[];
	error: string | null;
}

export async function listProviders(): Promise<Provider[]> {
	const data = await req<{ providers: Provider[] }>("GET", "/providers");
	return data.providers;
}

export async function probeProvider(
	base_url: string,
	api_key: string,
	provider_name?: string,
): Promise<ProbeResult> {
	return req("POST", "/providers/probe", {
		base_url,
		api_key,
		...(provider_name ? { provider_name } : {}),
	});
}

export async function addProvider(
	name: string,
	base_url: string,
	api_key: string,
): Promise<void> {
	await req("POST", "/providers/add", { name, base_url, api_key });
}

export async function switchModel(
	provider_name: string,
	model_id: string,
): Promise<void> {
	await req("POST", "/providers/switch", { provider_name, model_id });
}

export async function syncSessionModel(
	session_id: string,
	model_id: string,
): Promise<void> {
	await req("PATCH", `/session/${session_id}/model`, { model: model_id });
}
