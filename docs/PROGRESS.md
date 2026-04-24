# PROGRESS

Status kerja per sesi. Update setiap kali ada perubahan signifikan.

---

## Struktur Repo

```
minimal/
├── PLAN.md              — spesifikasi lengkap, semua keputusan arsitektur
├── VENDORS.md           — commit hash aider files yang di-vendor
├── PROGRESS.md          — file ini
├── strip_vendors.py     — script untuk strip aider imports (jalanin dari root)
│
└── min/
    ├── requirements.txt
    ├── backend/
    │   ├── main.py        ✅ selesai
    │   ├── llm.py         ✅ selesai
    │   ├── session.py     ✅ selesai
    │   ├── coder.py       ✅ selesai
    │   ├── commands.py    ✅ selesai
    │   ├── context.py     ✅ selesai
    │   ├── prompts.py     ✅ selesai
    │   ├── config.py      ✅ selesai
    │   ├── schemas.py     ✅ selesai
    │   └── vendor/        ✅ selesai (stripped dari aider)
    │       ├── editblock.py
    │       ├── search_replace.py
    │       ├── udiff.py
    │       ├── wholefile.py
    │       ├── sendchat.py
    │       └── repo.py
    │
    ├── tui/               ⬜ belum dimulai
    │   ├── package.json   (kosong)
    │   ├── tsconfig.json  (kosong)
    │   ├── index.ts       (kosong)
    │   ├── app.tsx        (missing — belum dibuat)
    │   ├── state.ts       (kosong)
    │   ├── client.ts      (kosong)
    │   ├── stream.ts      (kosong)
    │   └── components/
    │       ├── chat.tsx   (kosong)
    │       ├── input.tsx  (kosong)
    │       ├── status.tsx (kosong)
    │       └── context.tsx(kosong)
    │
    └── tests/
        └── test_coder.py  ✅ udiff test pass
```

---

## Phase Status

| Phase | Status | Catatan |
|-------|--------|---------|
| Phase 0 — Foundation | ✅ selesai | repo, vendors, struktur |
| Phase 1 — Backend MVP | ✅ selesai | semua 12 endpoints jalan |
| Phase 2 — TUI Build | ⬜ belum dimulai | semua file masih kosong |
| Phase 3 — Polish | ⬜ belum dimulai | |
| Phase 4 — Extended Edit | ⬜ belum dimulai | |

---

## Keputusan Penting Yang Sudah Dibuat

- **Streaming**: `llm.py` pakai async generator `(token, None) / (None, Usage)`, bukan callback
- **Vendor strategy**: class aider di-strip, hanya fungsi standalone yang dipakai
- **`udiff.py`**: ditulis ulang lebih simpel (owner), bukan copy aider
- **`wholefile.py`**: diganti `parse_whole_edits()` standalone
- **`repo.py`**: diganti 4 fungsi git standalone (`git_commit`, `git_diff`, `git_undo`, `git_dirty_files`)
- **`search_replace.py`**: `git_cherry_pick_*` dihapus, `all_preprocs` + strategy lists ditambah manual
- **Session write**: pure append-only ke JSONL, tidak ada tmp file

---

## Yang Perlu Diperhatikan Sesi Berikutnya

### TUI — mulai dari sini
Urutan build sesuai PLAN:
1. `package.json` + `tsconfig.json` — setup project
2. `state.ts` — solid-js store
3. `client.ts` — HTTP client ke backend port 4096
4. `stream.ts` — SSE consumer
5. `components/status.tsx` — paling simple, mulai dari sini
6. `components/context.tsx`
7. `components/chat.tsx`
8. `components/input.tsx` — paling kompleks (slash command autocomplete)
9. `app.tsx` — root layout, wiring semua
10. `index.ts` — entry point, CLI args

### Dependencies TUI (dari PLAN)
```
@opentui/core    rendering engine
solid-js         reactive state
yargs            CLI args
```

### Backend — hal kecil yang belum sempurna
- `/session/{id}/abort` masih stub (TODO di main.py)
- `context.reload()` pakai sync read, inkonsisten dengan async context lainnya (minor)
- `_apply_whole` di coder.py — regex parse agak fragile, belum ditest
