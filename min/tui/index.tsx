// index.tsx — entry point

import { render } from "@opentui/solid";
import yargs from "yargs";
import { hideBin } from "yargs/helpers";
import { App } from "./app.tsx";
import { createSession, getConfig, getSession, healthCheck } from "./client.ts";
import { finalizeMessage, pushMessage, setState } from "./state.ts";

// ── CLI args ──────────────────────────────────────────────────────────────────
const argv = await yargs(hideBin(process.argv))
	.option("session", {
		alias: "s",
		type: "string",
		description: "Resume session ID",
	})
	.option("model", {
		alias: "m",
		type: "string",
		description: "Model override",
	})
	.help()
	.parseAsync();

// ── Backend health check ───────────────────────────────────────────────────────
const ok = await healthCheck();
if (!ok) {
	console.error("minimal: backend not reachable on port 4096. Start it first.");
	process.exit(1);
}

// ── Config + session ──────────────────────────────────────────────────────────
const config = await getConfig();
setState("model", argv.model ?? config.model ?? "");

// Kalau belum configured, buka setup flow di TUI langsung
if (!config.configured) {
	setState("showModelPicker", "add");
}

let sessionId: string;
if (argv.session) {
	const existing = await getSession(argv.session).catch(() => null);
	if (!existing) {
		console.error(`minimal: session '${argv.session}' not found`);
		process.exit(1);
	}
	sessionId = existing.session_id;
	if (existing.model) setState("model", existing.model);
	// Load history ke state
	if (existing.messages && existing.messages.length > 0) {
		for (const msg of existing.messages) {
			const idx = pushMessage(msg.role as "user" | "assistant", msg.content);
			// Set displayContent untuk assistant messages yang sudah done
			if (msg.role === "assistant") {
				const stripped = msg.content
					.replace(
						/^[^\n]*\n?<<<<<<< SEARCH[\s\S]*?>>>>>>> REPLACE[^\n]*/gm,
						"",
					)
					.replace(/<file\s[^>]*>[\s\S]*?<\/file>/g, "")
					.replace(/```(?:diff|udiff)[\s\S]*?```/g, "")
					.replace(/\n{3,}/g, "\n\n")
					.trim();
				setState("messages", idx, "displayContent", stripped);
				finalizeMessage(idx);
			}
		}
	}
} else {
	const session = await createSession(argv.model);
	sessionId = session.session_id;
	if (session.model) setState("model", session.model);
}

setState("sessionId", sessionId);

// Tulis session ID ke file temp supaya launcher bisa tampilkan di exit screen
const sessionFile = process.env.MINIMAL_SESSION_FILE;
if (sessionFile) {
	await Bun.write(sessionFile, sessionId);
}

// ── Mount TUI ─────────────────────────────────────────────────────────────────
render(() => <App />, {
	exitOnCtrlC: true,
	exitSignals: ["SIGTERM"],
	clearOnShutdown: true,
	backgroundColor: "#0d0d0d",
});
