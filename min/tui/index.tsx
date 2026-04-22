// index.tsx — entry point
import yargs from "yargs"
import { hideBin } from "yargs/helpers"
import { render } from "@opentui/solid"
import { setState } from "./state.ts"
import { healthCheck, getConfig, createSession, getSession } from "./client.ts"
import { App } from "./app.tsx"

// ── CLI args ──────────────────────────────────────────────────────────────────
const argv = await yargs(hideBin(process.argv))
  .option("session", { alias: "s", type: "string", description: "Resume session ID" })
  .option("model",   { alias: "m", type: "string", description: "Model override" })
  .help()
  .parseAsync()

// ── Backend health check ───────────────────────────────────────────────────────
const ok = await healthCheck()
if (!ok) {
  console.error("minimal: backend not reachable on port 4096. Start it first.")
  process.exit(1)
}

// ── Config + session ──────────────────────────────────────────────────────────
const config = await getConfig()
setState("model", argv.model ?? config.model ?? "")

let sessionId: string
if (argv.session) {
  const existing = await getSession(argv.session).catch(() => null)
  if (!existing) {
    console.error(`minimal: session '${argv.session}' not found`)
    process.exit(1)
  }
  sessionId = existing.session_id
  if (existing.model) setState("model", existing.model)
} else {
  const session = await createSession(argv.model)
  sessionId = session.session_id
  if (session.model) setState("model", session.model)
}

setState("sessionId", sessionId)

// ── Mount TUI ─────────────────────────────────────────────────────────────────
render(() => <App />, {
  exitOnCtrlC: true,
  exitSignals: ["SIGTERM"],
  clearOnShutdown: true,
  backgroundColor: "#1a1b26",
})
