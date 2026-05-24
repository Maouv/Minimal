# context.py — file context manager
# User harus /add file secara eksplisit. State persist di session JSONL.

import aiofiles
from pathlib import Path
from datetime import datetime
from schemas import ContextFile


class ContextManager:
    def __init__(self):
        self.files: dict[str, str] = {}  # path → content
        self.readonly: set[str] = set()  # paths yang read-only
        self.token_counts: dict[str, int] = {}  # path → estimated token count

    async def add(self, path: str, readonly: bool = False) -> str:
        """Tambah file ke context. Return error string kalau gagal."""
        p = Path(path).resolve()
        if not p.exists():
            return f"File not found: {path}"
        if not p.is_file():
            return f"Not a file: {path}"

        try:
            async with aiofiles.open(p, "r", encoding="utf-8", errors="replace") as f:
                content = await f.read()
        except Exception as e:
            return f"Cannot read {path}: {e}"

        key = str(p)
        self.files[key] = content
        self.token_counts[key] = _estimate_tokens(content)
        if readonly:
            self.readonly.add(key)
        elif key in self.readonly:
            self.readonly.discard(key)

        return ""  # empty = success

    def drop(self, path: str) -> str:
        """Hapus file dari context. Return error string kalau tidak ada."""
        p = str(Path(path).resolve())
        if p not in self.files:
            return f"Not in context: {path}"
        del self.files[p]
        self.readonly.discard(p)
        self.token_counts.pop(p, None)
        return ""

    def ls(self) -> list[ContextFile]:
        """List semua files di context."""
        result = []
        for path, content in self.files.items():
            p = Path(path)
            result.append(
                ContextFile(
                    path=path,
                    readonly=path in self.readonly,
                    token_count=self.token_counts.get(path, 0),
                    last_modified=datetime.fromtimestamp(p.stat().st_mtime)
                    if p.exists()
                    else datetime.now(),
                )
            )
        return result

    def total_tokens(self) -> int:
        return sum(self.token_counts.values())

    def get_editable(self) -> dict[str, str]:
        """Return hanya files yang bisa diedit (bukan readonly)."""
        return {p: c for p, c in self.files.items() if p not in self.readonly}

    def get_all(self) -> dict[str, str]:
        return dict(self.files)

    def to_messages(self) -> list[dict]:
        """
        Format file content sebagai messages untuk LLM context.
        Struktur: satu user message per file.
        """
        if not self.files:
            return []

        parts = []
        for path, content in self.files.items():
            label = "read-only" if path in self.readonly else "editable"
            parts.append(f'<file path="{path}" access="{label}">\n{content}\n</file>')

        return [
            {
                "role": "user",
                "content": "Files in context:\n\n" + "\n\n".join(parts),
            }
        ]

    async def reload(self, path: str) -> bool:
        """Reload file content dari disk. Return False kalau gagal."""
        p = Path(path).resolve()
        if not p.exists():
            return False
        try:
            async with aiofiles.open(p, "r", encoding="utf-8", errors="replace") as f:
                content = await f.read()
            key = str(p)
            self.files[key] = content
            self.token_counts[key] = _estimate_tokens(content)
            return True
        except Exception:
            return False


_TIKTOKEN_ENC = None  # None = not tried, encoder object = ready, False = unavailable


def _get_encoder():
    """
    Lazy-load tiktoken encoder. Return None kalau tidak tersedia.
    Cached setelah first call — tidak re-import setiap panggilan.
    """
    global _TIKTOKEN_ENC
    if _TIKTOKEN_ENC is not None:
        return _TIKTOKEN_ENC  # already resolved (encoder or False)
    try:
        import tiktoken  # noqa: PLC0415
        _TIKTOKEN_ENC = tiktoken.get_encoding("cl100k_base")
    except Exception:
        _TIKTOKEN_ENC = False  # type: ignore[assignment]
    return _TIKTOKEN_ENC or None


def _estimate_tokens(text: str) -> int:
    """
    Hitung token count.
    Prioritas: tiktoken cl100k_base (±10% akurat).
    Fallback ke len÷3 kalau tiktoken tidak tersedia.
    """
    enc = _get_encoder()
    if enc is not None:
        return len(enc.encode(text))
    return len(text) // 3
