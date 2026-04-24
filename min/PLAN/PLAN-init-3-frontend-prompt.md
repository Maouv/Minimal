# Plan 3 — Frontend (TUI) + System Prompt

## Depends on
Plan 1 + Plan 2 harus sudah done.

---

## 1. `commands.py` — tambah `/init`

```python
COMMANDS = [
    ...,
    "/init",
]

# parse: /init → kind="init", args=""
# parse: /init min/backend → kind="init", args="min/backend"  
# parse: /init --save → kind="init", args="--save"
```

---

## 2. `input.tsx` — slash autocomplete

### Tambah ke `SLASH_COMMANDS`:
```ts
{ cmd: "/init",        desc: "generate MINIMAL.md untuk direktori ini" },
{ cmd: "/init --save", desc: "simpan draft ke MINIMAL.md" },
```

### Autocomplete `/init <path>` — dirs only, satu level select:

Tambah blok baru di `handleInput()` setelah blok `/add`:

```ts
if (value.startsWith("/init ") && !value.includes("--")) {
  const afterCmd = value.slice(6)
  const lastSlash = afterCmd.lastIndexOf("/")
  const browseDir = lastSlash >= 0 ? afterCmd.slice(0, lastSlash + 1) : ""
  const filterName = afterCmd.slice(lastSlash + 1).toLowerCase()

  const rawEntries = await loadEntries(browseDir)
  const matches = rawEntries
    .filter(e => e.is_dir)
    .filter(e => filterName === "" || e.name.toLowerCase().includes(filterName))
    .slice(0, 10)
    .map(e => ({
      label: e.name,
      desc: e.path,
      value: "/init " + e.path,
      is_dir: true,
    }))
  setAcMode("dir")
  setAcItems(matches)
  setAcSelected(0)
  return
}
```

### Behavior ketika dir dipilih dari `/init` autocomplete:

Berbeda dari `/add` — `/init` butuh **satu path final**, bukan drill-down terus.
Ketika Enter di `acMode === "dir"` dan command starts with `/init`:

```ts
if (acMode() === "dir") {
  const val = inputRef?.value ?? ""
  if (val.startsWith("/init ")) {
    // Set value final, dismiss list, biarkan onSubmit fire
    key.preventDefault()
    setAcItems([])
    // value sudah benar dari insertFile(), langsung submit
    handleSubmit(val)
    return
  }
  // /add drill-down behavior tetap sama seperti sekarang
}
```

---

## 3. System Prompt — `prompts.py` fungsi `init_system()`

```python
def init_system() -> str:
    return """Analyze the codebase context and write a MINIMAL.md for this directory.
This file will be loaded at the start of every session to give future AI instances
immediate context without re-exploring the codebase.

The context is provided in sections with reliability order:
1. EXISTING MINIMAL.md — ground truth, do not contradict unless repo map shows it outdated
2. @repo: TAGS — developer annotations, high signal
3. REPO MAP — auto-extracted symbols, structural only, no intent
4. MANIFESTS — ground truth for dependencies and run scripts

What to include:
1. Commands — how to run, build, test. Only if verifiable from manifests or existing docs.
   Include how to run a single test if test files exist.
2. Architecture — data flow and module boundaries that require reading multiple files
   to understand. Skip what is obvious from filenames alone.
3. Gotchas — anything from @repo: tags or existing MINIMAL.md marked critical or tricky.
   This is the highest-value section. If empty, omit the section entirely.
4. Non-obvious dependencies — why a library exists, not just that it does.

What to exclude:
- Generic development practices
- File listings discoverable by ls
- Anything you are not confident about — omit rather than guess
- Content already in a parent or sibling MINIMAL.md (it loads separately)

If EXISTING MINIMAL.md is provided:
- Preserve accurate sections as-is
- Only update where repo map clearly shows divergence
- Do not rewrite sections just to paraphrase them

Format:
- Start with exactly:
  # MINIMAL.md
  This file provides guidance to Minimal when working in this repository.
- Maximum 120 lines. If over, cut lowest-confidence sections first.
- No section header if the section has only one item — inline it.
- No nested bullets deeper than one level.

Output as draft only. Do not reference saving or file writing.
User will run /init --save to persist."""
```

---

## 4. Tidak perlu ubah `stream.ts`

`/init` menghasilkan `token` SSE events yang di-render sebagai assistant message biasa.
`/init --save` menghasilkan `text` SSE event — sudah di-handle.

---

## Test end-to-end

```
# Di TUI:
/init                    → generate untuk CWD
/init min/backend        → generate untuk min/backend
/init min/              → autocomplete muncul list dirs
/init --save             → tulis ke CWD/MINIMAL.md
```

Verify:
1. Autocomplete `/init ` muncul dirs (bukan files)
2. Pilih dir → value ter-set langsung, Enter submit (tidak drill-down)
3. Response muncul sebagai assistant message (streaming)
4. `/init --save` menulis file ke path yang benar
5. `/init` di luar CWD project ditolak dengan error message
