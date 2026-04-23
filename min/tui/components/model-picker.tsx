// model-picker.tsx — overlay melayang di atas input bar
// mode="switch" → list providers → probe → pilih model → switch
// mode="add"    → list providers + "+ New" → existing: probe → model / new: base URL → API key → model

import { createSignal, For, Show, onMount } from "solid-js"
import { useKeyboard } from "@opentui/solid"
import type { InputRenderable } from "@opentui/core"
import { setState } from "../state.ts"
import {
  listProviders, probeProvider, addProvider, switchModel,
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

  let inputRef: InputRenderable | undefined

  onMount(() => {
    listProviders().then(p => {
      setProviders(p)
      // Kalau switch mode dan tidak ada provider, langsung ke add new
      if (props.mode === "switch" && p.length === 0) setPhase("new-baseurl")
    }).catch(() => setProviders([]))
  })

  // provider-list items:
  // switch mode → hanya existing providers
  // add mode    → "+ New provider" + existing providers
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

  async function _submitBaseUrl(val: string) {
    const url = val.trim(); if (!url) return
    setNewBaseUrl(url); setNewName(_deriveNameFromUrl(url))
    setPhase("new-apikey"); setError("")
    setTimeout(() => inputRef?.focus?.(), 50)
  }

  async function _submitApiKey(val: string) {
    const key = val.trim(); if (!key) return
    setNewApiKey(key)
    setActiveProvider({ name: newName(), base_url: newBaseUrl(), env_key: "" })
    await _probe(newBaseUrl(), key)
  }

  async function _selectModel(modelId: string) {
    const provider = activeProvider(); if (!provider) return
    setPhase("loading"); setLoadingMsg("Switching model...")
    try {
      if (newApiKey()) await addProvider(newName(), newBaseUrl(), newApiKey())
      await switchModel(provider.name, modelId)
      setState("model", modelId)
      props.onDone()
    } catch (e) {
      setError(String(e))
      setPhase("model-select")
      setTimeout(() => inputRef?.focus?.(), 50)
    }
  }

  async function _submitManualModel(val: string) {
    const modelId = val.trim(); if (!modelId) return
    await _selectModel(modelId)
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
                  <text fg={item.isNew ? C.green : C.orange} width={22}>{item.label}</text>
                  <text fg={C.gray}>{item.desc}</text>
                </box>
              )}
            </For>
          </Show>
        </Show>

        {/* Base URL */}
        <Show when={phase() === "new-baseurl"}>
          <box width="100%" flexDirection="column" paddingLeft={2} paddingRight={2} paddingTop={1} paddingBottom={1}>
            <text fg={C.gray} marginBottom={1}>Base URL</text>
            <input ref={inputRef} flexGrow={1}
              placeholder="https://openrouter.ai/api/v1" placeholderColor={C.gray2}
              backgroundColor={C.bg2} textColor={C.white}
              focusedBackgroundColor={C.bg3} focusedTextColor={C.white}
              focused onSubmit={(val: string) => _submitBaseUrl(val)} />
            <Show when={error()}><text fg={C.pink} marginTop={1}>{error()}</text></Show>
          </box>
        </Show>

        {/* API Key */}
        <Show when={phase() === "new-apikey"}>
          <box width="100%" flexDirection="column" paddingLeft={2} paddingRight={2} paddingTop={1} paddingBottom={1}>
            <text fg={C.gray} marginBottom={1}>API Key  <text fg={C.gray2}>{newBaseUrl()}</text></text>
            <input ref={inputRef} flexGrow={1}
              placeholder="sk-or-v1-..." placeholderColor={C.gray2}
              backgroundColor={C.bg2} textColor={C.white}
              focusedBackgroundColor={C.bg3} focusedTextColor={C.white}
              focused onSubmit={(val: string) => _submitApiKey(val)} />
            <Show when={error()}><text fg={C.pink} marginTop={1}>{error()}</text></Show>
          </box>
        </Show>

        {/* Model list + filter */}
        <Show when={phase() === "model-select" && !manualMode()}>
          <box width="100%" flexDirection="column">
            <box width="100%" paddingLeft={2} paddingRight={2} paddingTop={1} paddingBottom={1}>
              <input ref={inputRef} flexGrow={1}
                placeholder="filter model..." placeholderColor={C.gray2}
                backgroundColor={C.bg2} textColor={C.white}
                focusedBackgroundColor={C.bg2} focusedTextColor={C.white}
                focused
                onInput={(val: string) => { setFilter(val); setSelIdx(0) }}
                onSubmit={() => { const m = filteredModels()[selIdx()]; if (m) _selectModel(m) }} />
            </box>
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
          </box>
        </Show>

        {/* Manual fallback */}
        <Show when={phase() === "model-select" && manualMode()}>
          <box width="100%" flexDirection="column" paddingLeft={2} paddingRight={2} paddingTop={1} paddingBottom={1}>
            <text fg={C.gray} marginBottom={1}>Model ID  <text fg={C.pink}>{error()}</text></text>
            <input ref={inputRef} flexGrow={1}
              placeholder="openai/gpt-4o" placeholderColor={C.gray2}
              backgroundColor={C.bg2} textColor={C.white}
              focusedBackgroundColor={C.bg3} focusedTextColor={C.white}
              focused onSubmit={(val: string) => _submitManualModel(val)} />
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
