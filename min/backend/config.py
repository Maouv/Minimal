# config.py — .env loader + setup wizard
# Config global di ~/.minimal/.env — satu file untuk semua project.
# Wizard jalan sekali saat first run tanpa .env.

import os
from pathlib import Path
from dotenv import load_dotenv

_CONFIG_DIR = Path.home() / ".minimal"
_ENV_FILE = _CONFIG_DIR / ".env"

def ensure():
    """Panggil saat startup. Load .env atau jalankan wizard kalau belum ada."""
    if not _ENV_FILE.exists():
        _run_wizard()
    load_dotenv(_ENV_FILE, override=True)


def _run_wizard():
    """Setup wizard — tanya 3 field, simpan ke ~/.minimal/.env."""
    print("\nNo config found. Quick setup:\n")
    print("(Ctrl+C to abort)\n")

    try:
        default_url = "https://openrouter.ai/api/v1"
        base_url = input("Provider base URL? (enter untuk openrouter): ").strip()
        if not base_url:
            base_url = default_url

        api_key = input("API Key: ").strip()
        model = input("Model: ").strip()
    except KeyboardInterrupt:
        print("\n\nAborted.")
        raise SystemExit(0)

    if not api_key or not model:
        print("API key and model are required.")
        raise SystemExit(1)

    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _ENV_FILE.write_text(
        f"LLM_BASE_URL={base_url}\n"
        f"LLM_API_KEY={api_key}\n"
        f"LLM_MODEL={model}\n"
    )
    print(f"\nConfig saved to {_ENV_FILE}\nStarting...\n")


# --- Getters ---

def base_url() -> str:
    return os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")


def api_key() -> str:
    return os.getenv("LLM_API_KEY", "")


def model() -> str:
    return os.getenv("LLM_MODEL", "")


def timeout() -> int:
    return int(os.getenv("LLM_TIMEOUT", "60"))


def max_tokens() -> int:
    return int(os.getenv("LLM_MAX_TOKENS", "8192"))


def thinking_budget() -> int:
    return int(os.getenv("LLM_THINKING_BUDGET", "5000"))


def context_window(model_alias: str | None = None) -> int:
    """Return context window untuk model alias tertentu, fallback ke default."""
    if model_alias:
        key = f"LLM_CONTEXT_WINDOW_{model_alias.upper()}"
        val = os.getenv(key)
        if val:
            return int(val)
    return int(os.getenv("LLM_CONTEXT_WINDOW", "128000"))


def sessions_dir() -> Path:
    d = _CONFIG_DIR / "sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def all_models() -> dict[str, str]:
    """
    Return semua model aliases dari .env.
    Format: {"fast": "glm-4.7-flash", "reason": "deepseek-r1", ...}
    Primary model tidak masuk sini.
    """
    result = {}
    for key, val in os.environ.items():
        if key.startswith("LLM_MODEL_") and val:
            alias = key[len("LLM_MODEL_"):].lower()
            result[alias] = val
    return result


def resolve_model(name: str) -> str:
    """
    Resolve model alias ke model ID.
    /model fast   → LLM_MODEL_FAST
    /model glm-5  → "glm-5" langsung (fallback)
    """
    if not name:
        return model()
    alias_key = f"LLM_MODEL_{name.upper()}"
    resolved = os.getenv(alias_key)
    return resolved if resolved else name
