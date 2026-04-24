// model-picker.tsx — overlay melayang di atas input bar
// mode="switch" → list providers → probe → pilih model → switch
// mode="add"    → list providers + "+ New" → existing: probe → model / new: base URL → API key → model
//
// PENTING: Semua fase yang butuh input teks memakai SATU <input> yang selalu mounted.
// Kalau pakai <Show> per-fase, @opentui destroyRecursively() jalan async (nextTick)
// sedangkan onSubmit masih bisa firing sebelum cleanup selesai → renderer crash.

import { createSignal, For, Show, onMount, createMemo } from "solid-js"
import { useKeyboard } from "@opentui/solid"
import type { InputRenderable } from "@opentui/core"
import { state, setState } from "../state.ts"
import {
  listProviders, probeProvider, addProvider, switchModel, syncSessionModel,
  type Provider,
} from "../client.ts"
import { C } from "../theme.ts"

type Phase = "provider-list" | "new-baseurl" | "new-apikey" | "model-select" | "loading"

const MAX_VISIBLE = 10

interface Props {
  mode: "switch" | "add"
  onDone: () => void
}

export function ModelPicker(props: Props) {
  const [phase, setPhase] = createSignal<Phase>("provider-list")
  const [selIdx, setSelIdx] = createSignal(0)
  const [filter, setFilter] = createSignal("")
  const [error, setError] = createSignal("")
  const [loadingMsg, setLoadingMsg] = createSignal("")

  const [providers, setProviders] = createSignal<Provider[]>([])
  const [newBaseUrl, setNewBaseUrl] = createSignal("")
  const [newApiKey, setNewApiKey] = createSignal("")
  const [newName, setNewName] = createSignal("")
  const [modelList, setModelList] = createSignal<string[]>([])
  const [activeProvider, setActiveProvider] = createSignal<Provider | null>(null)
  const [manualMode, setManualMode] = createSignal(false)

  // Satu ref untuk satu input yang selalu mounted — tidak pernah unmount/remount
  let inputRef: InputRenderable | undefined

  // Apakah fase ini butuh input teks?
  const needsInput = createMemo(() => {
    const ph = phase()
    return ph === "new-baseurl" || ph === "new-apikey" || ph === "model-select"
  })

  // Label di atas input berdasarkan fase
  const inputLabel = createMemo(() => {
    switch (phase()) {
      case "new-baseurl": return "Base URL"
      case "new-apikey":  return `API Key  ${newBaseUrl()}`
      case "model-select": return manualMode() ? `Model ID  ${error()}` : ""
      default: return ""
    }
  })

  // Placeholder input berdasarkan fase
  const inputPlaceholder = createMemo(() => {
    switch (phase()) {
      case "new-baseurl":  return "https://openrouter.ai/api/v1"
      case "new-apikey":   return "sk-or-v1-..."
      case "model-select": return manualMode() ? "openai/gpt-4o" : "filter model..."
      default: return ""
    }
  })

  onMount(() => {
    listProviders().then(p => {
      setProviders(p)
      if (props.mode === "switch" && p.length === 0) {
        setPhase("new-baseurl")
        setTimeout(() => inputRef?.focus?.(), 50)
      }
    }).catch(() => setProviders([]))
  })

  const listItems = () => {
    const existing = providers().map(p => ({ label: p.name, desc: p.base_url, isNew: false, provider: p }))
    if (props.mode === "add") {
      return [{ label: "+ New provider", desc: "tambah provider baru", isNew: true, provider: null as any }, ...existing]
    }
    return existing
  }

  const filteredModels = () => {
    const q = filter().toLowerCase()
    const all = modelList()
    return (q ? all.filter(m => m.toLowerCase().includes(q)) : all).slice(0, MAX_VISIBLE)
  }

  // ── Keyboard ───────────────────────────────────────────────────────────────
  useKeyboard((key) => {
    if (key.name === "escape") { key.preventDefault(); props.onDone(); return }

    const ph = phase()

    if (ph === "provider-list") {
      const items = listItems()
      if (key.name === "up")   { key.preventDefault(); setSelIdx(s => Math.max(0, s - 1)); return }
      if (key.name === "down") { key.preventDefault(); setSelIdx(s => Math.min(items.length - 1, s + 1)); return }
      if (key.name === "return") {
        key.preventDefault()
        const item = items[selIdx()]
        if (!item) return
        if (item.isNew) {
          setPhase("new-baseurl"); setError("")
          setTimeout(() => inputRef?.focus?.(), 50)
        } else {
          setActiveProvider(item.provider)
          setNewApiKey("")
          setNewName("")
          setNewBaseUrl("")
          _probe(item.provider.base_url, "__from_env__")
        }
        return
      }
    }

    if (ph === "model-select" && !manualMode()) {
      const models = filteredModels()
      if (key.name === "up")   { key.preventDefault(); setSelIdx(s => Math.max(0, s - 1)); return }
      if (key.name === "down") { key.preventDefault(); setSelIdx(s => Math.min(models.length - 1, s + 1)); return }
      if (key.name === "return") {
        key.preventDefault()
        const model = models[selIdx()]
        if (model) _selectModel(model)
        return
      }
    }
  })

  // ── Actions ────────────────────────────────────────────────────────────────
  async function _probe(baseUrl: string, apiKey: string) {
    const providerName = activeProvider()?.name ?? newName()
    setPhase("loading")
    setLoadingMsg(`Fetching models${providerName ? ` from ${providerName}` : ""}...`)
    const result = await probeProvider(baseUrl, apiKey, providerName || undefined)
    if (result.ok && result.models.length > 0) {
      setModelList(result.models); setManualMode(false)
      setFilter(""); setSelIdx(0); setError(""); setPhase("model-select")
      setTimeout(() => inputRef?.focus?.(), 50)
    } else {
      setManualMode(true); setModelList([])
      setError(result.error ?? "Provider tidak support /v1/models")
      setPhase("model-select")
      setTimeout(() => inputRef?.focus?.(), 50)
    }
  }

  function _deriveNameFromUrl(url: string): string {
    if (url.includes("openrouter")) return "OpenRouter"
    if (url.includes("openai.com")) return "OpenAI"
    if (url.includes("anthropic"))  return "Anthropic"
    if (url.includes("groq"))       return "Groq"
    try { return new URL(url).hostname.replace(/^www\./, "") } catch { return url }
  }

  // Handler tunggal untuk onSubmit — dispatch berdasarkan fase saat itu
  async function _handleSubmit(val: string) {
    const ph = phase()

    if (ph === "new-baseurl") {
      const url = val.trim(); if (!url) return
      setNewBaseUrl(url); setNewName(_deriveNameFromUrl(url))
      // Reset nilai input sebelum ganti fase — input node TIDAK unmount
      if (inputRef) inputRef.value = ""
      setPhase("new-apikey"); setError("")
      return
    }

    if (ph === "new-apikey") {
      const key = val.trim(); if (!key) return
      setNewApiKey(key)
      setActiveProvider({ name: newName(), base_url: newBaseUrl(), env_key: "" })
      if (inputRef) inputRef.value = ""
      await _probe(newBaseUrl(), key)
      return
    }

    if (ph === "model-select" && manualMode()) {
      const modelId = val.trim(); if (!modelId) return
      await _selectModel(modelId)
      return
    }

    if (ph === "model-select" && !manualMode()) {
      const m = filteredModels()[selIdx()]
      if (m) await _selectModel(m)
      return
    }
  }

  // Handler onInput — hanya relevan di fase model-select filter
  function _handleInput(val: string) {
    if (phase() === "model-select" && !manualMode()) {
      setFilter(val); setSelIdx(0)
    }
  }

  async function _selectModel(modelId: string) {
    const provider = activeProvider(); if (!provider) return
    setPhase("loading"); setLoadingMsg("Switching model...")
    try {
      if (newApiKey()) await addProvider(newName(), newBaseUrl(), newApiKey())
      await switchModel(provider.name, modelId)
      if (state.sessionId) await syncSessionModel(state.sessionId, modelId)
      // Update display state hanya setelah semua backend calls berhasil
      setState("model", modelId)
      props.onDone()
    } catch (e) {
      // Tampilkan error yang jelas supaya tidak silent-fail
      const msg = e instanceof Error ? e.message : String(e)
      setError(msg)
      setPhase("model-select")
      setTimeout(() => inputRef?.focus?.(), 50)
    }
  }

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <box width="100%" backgroundColor={C.bg} paddingLeft={2} paddingRight={2} paddingTop={1}>
      <box width="100%" flexDirection="column" backgroundColor={C.bg2} flexShrink={0}>

        {/* Loading */}
        <Show when={phase() === "loading"}>
          <box width="100%" height={2} flexDirection="row" alignItems="center" paddingLeft={2}>
            <text fg={C.gray}>{loadingMsg()}</text>
          </box>
        </Show>

        {/* Provider list */}
        <Show when={phase() === "provider-list"}>
          <Show when={listItems().length > 0} fallback={
            <box height={2} paddingLeft={2} alignItems="center">
              <text fg={C.gray}>Tidak ada provider. Gunakan /model-add</text>
            </box>
          }>
            <For each={listItems()}>
              {(item, i) => (
                <box width="100%" flexDirection="row" height={1} paddingLeft={2} paddingRight={2}
                  backgroundColor={i() === selIdx() ? C.bg3 : C.bg2}>
                  {item.isNew
                    ? <text fg={C.green} flexGrow={1}>{item.label}</text>
                    : <>
                        <text fg={C.white} width={28}>
                          {item.provider.last_model ?? "—"}
                        </text>
                        <text fg={C.orange} width={16}>{item.provider.name}</text>
                        <text fg={C.gray}>{item.provider.base_url}</text>
                      </>
                  }
                </box>
              )}
            </For>
          </Show>
        </Show>

        {/* Model list (fase model-select, bukan manual) */}
        <Show when={phase() === "model-select" && !manualMode()}>
          <For each={filteredModels()}>
            {(model, i) => (
              <box width="100%" flexDirection="row" height={1} paddingLeft={2} paddingRight={2}
                backgroundColor={i() === selIdx() ? C.bg3 : C.bg2}>
                <text fg={C.orange} flexGrow={1}>{model}</text>
              </box>
            )}
          </For>
          <Show when={modelList().length > MAX_VISIBLE}>
            <box height={1} paddingLeft={2} paddingBottom={1}>
              <text fg={C.gray2}>{`${modelList().length - filteredModels().length} more — ketik untuk filter`}</text>
            </box>
          </Show>
        </Show>

        {/* SATU input — selalu mounted selama needsInput() true, tidak pernah berganti node */}
        <Show when={needsInput()}>
          <box width="100%" flexDirection="column" paddingLeft={2} paddingRight={2} paddingTop={1} paddingBottom={1}>
            <Show when={inputLabel()}>
              <text fg={C.gray} marginBottom={1}>{inputLabel()}</text>
            </Show>
            <input
              ref={inputRef}
              flexGrow={1}
              placeholder={inputPlaceholder()}
              placeholderColor={C.gray2}
              backgroundColor={C.bg2}
              textColor={C.white}
              focusedBackgroundColor={C.bg3}
              focusedTextColor={C.white}
              focused
              onInput={(val: string) => _handleInput(val)}
              onSubmit={(val: string) => _handleSubmit(val)}
            />
            <Show when={!!error()}>
              <text fg={C.pink} marginTop={1}>{error()}</text>
            </Show>
          </box>
        </Show>

        {/* Footer */}
        <box width="100%" paddingLeft={2} paddingRight={2} paddingBottom={1}>
          <text fg={C.gray2}>↑↓ navigate  ↵ select  esc cancel</text>
        </box>

      </box>
    </box>
  )
}
