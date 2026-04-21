# Vendors

Semua code yang di-vendor (copy + modifikasi) dari project lain.
Upgrade = keputusan sadar, bukan auto-pull.

---

## OpenCode (TUI fork)

- **Repo:** https://github.com/sst/opencode
- **Commit:** `a38d53fe2f056e55347861b87f349264e7abec48`
- **Diambil:** TUI layer (packages/opencode/src/cli/cmd/tui, server routes, session, provider display)
- **Dihapus:** auth, share, sync, control-plane, worktree, account, identity, acp, installation, console, desktop, enterprise, slack, storybook
- **Modifikasi:** 18 core files (hapus import dari modules yang dihapus)

## Aider (vendored files)

- **Repo:** https://github.com/Aider-AI/aider
- **Commit:** `f09d70659ae90a0d068c80c288cbb55f2d3c3755`
- **Files di-vendor ke `backend/`:**

| Aider source | Destination | Keterangan |
|---|---|---|
| `aider/coders/search_replace.py` | `backend/vendor/search_replace.py` | SEARCH/REPLACE parser |
| `aider/coders/editblock_coder.py` | `backend/vendor/editblock.py` | editblock apply + verify |
| `aider/coders/udiff_coder.py` | `backend/vendor/udiff.py` | udiff apply |
| `aider/coders/wholefile_coder.py` | `backend/vendor/wholefile.py` | whole file rewrite |
| `aider/sendchat.py` | `backend/vendor/sendchat.py` | message validation |
| `aider/repo.py` | `backend/vendor/repo.py` | git integration |

- **Tidak di-vendor:** `reasoning_tags.py`, `models.py`, `io.py`, `llm.py`, `args.py`, `voice.py`, `gui.py`

