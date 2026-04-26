# config.py — .env loader + setup wizard
# Config global di ~/.minimal/.env — satu file untuk semua project.
# Wizard jalan sekali saat first run tanpa .env.
# Providers disimpan di ~/.minimal/providers.json

import json
import os
from pathlib import Path
from dotenv import load_dotenv, set_key

_CONFIG_DIR = Path.home() / ".minimal"
_ENV_FILE = _CONFIG_DIR / ".env"
_PROVIDERS_FILE = _CONFIG_DIR / "providers.json"

def ensure():
    """Panggil saat startup. Load .env kalau ada, skip kalau belum — TUI handle setup."""
    if _ENV_FILE.exists():
        load_dotenv(_ENV_FILE, override=True)


def is_configured() -> bool:
    """Return True kalau sudah ada API key yang valid."""
    return bool(os.getenv("LLM_API_KEY", "").strip())


def save_initial_config(pbase_url: str, papi_key: str, pmodel: str) -> None:
    """Simpan config awal ke .env — dipanggil dari TUI setup flow."""
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _ENV_FILE.write_text(
        f"LLM_BASE_URL={pbase_url}\n"
        f"LLM_API_KEY={papi_key}\n"
        f"LLM_MODEL={pmodel}\n"
    )
    load_dotenv(_ENV_FILE, override=True)


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
    """
    Session path di-scope per project berdasarkan CWD saat backend start.
    CWD /root/minimal   → ~/.minimal/sessions/-root-minimal/
    CWD /home/maou/dlmm → ~/.minimal/sessions/-home-maou-dlmm/
    """
    cwd = Path(os.getenv("MINIMAL_PROJECT_ROOT", os.getcwd()))
    slug = "-" + str(cwd).lstrip("/").replace("/", "-")
    d = _CONFIG_DIR / "sessions" / slug
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


# --- Multi-provider ---
# providers.json: list of { name, base_url, env_key }
# API key disimpan di .env dengan key = env_key

def providers_file() -> Path:
    return _PROVIDERS_FILE


def load_providers() -> list[dict]:
    """
    Load providers dari providers.json.
    Selalu include provider aktif (dari .env) sebagai entry pertama kalau belum ada.
    """
    providers: list[dict] = []

    if _PROVIDERS_FILE.exists():
        try:
            providers = json.loads(_PROVIDERS_FILE.read_text())
        except Exception:
            providers = []

    # Kalau kosong, seed dari .env yang ada sekarang
    if not providers:
        current_url = base_url()
        current_key = api_key()
        if current_url and current_key:
            name = _url_to_name(current_url)
            entry = {"name": name, "base_url": current_url, "env_key": "LLM_API_KEY"}
            providers = [entry]
            _save_providers(providers)

    return providers


def _save_providers(providers: list[dict]) -> None:
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _PROVIDERS_FILE.write_text(json.dumps(providers, indent=2))


def _url_to_name(url: str) -> str:
    """Derive friendly name dari base URL."""
    url = url.rstrip("/")
    if "openrouter" in url:
        return "OpenRouter"
    if "openai" in url:
        return "OpenAI"
    if "anthropic" in url:
        return "Anthropic"
    # Ambil hostname saja
    try:
        from urllib.parse import urlparse
        return urlparse(url).hostname or url
    except Exception:
        return url


def add_provider(name: str, pbase_url: str, papi_key: str) -> dict:
    """
    Tambah provider baru ke providers.json dan simpan API key ke .env.
    Return entry provider yang baru dibuat.
    """
    providers = load_providers()

    # Generate env_key dari nama provider — e.g. "My Provider" → "MY_PROVIDER_API_KEY"
    safe_name = name.upper().replace(" ", "_").replace("-", "_")
    env_key = f"{safe_name}_API_KEY"

    # Kalau nama sudah ada, update saja
    existing = next((p for p in providers if p["name"] == name), None)
    if existing:
        existing["base_url"] = pbase_url
        existing["env_key"] = env_key
    else:
        providers.append({"name": name, "base_url": pbase_url, "env_key": env_key})

    _save_providers(providers)

    # Simpan API key ke .env
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not _ENV_FILE.exists():
        _ENV_FILE.write_text("")
    set_key(str(_ENV_FILE), env_key, papi_key)

    # Reload env
    load_dotenv(_ENV_FILE, override=True)

    return {"name": name, "base_url": pbase_url, "env_key": env_key}


def switch_provider_model(provider: dict, model_id: str) -> None:
    """
    Switch active provider + model — update LLM_BASE_URL, LLM_API_KEY, LLM_MODEL di .env.
    Juga simpan last_model ke providers.json supaya bisa ditampilkan di list.
    """
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not _ENV_FILE.exists():
        _ENV_FILE.write_text("")

    # Resolve API key dari env_key provider
    resolved_key = os.getenv(provider["env_key"], "")

    set_key(str(_ENV_FILE), "LLM_BASE_URL", provider["base_url"])
    set_key(str(_ENV_FILE), "LLM_API_KEY", resolved_key)
    set_key(str(_ENV_FILE), "LLM_MODEL", model_id)

    # Simpan last_model ke providers.json
    providers = load_providers()
    for p in providers:
        if p["name"] == provider["name"]:
            p["last_model"] = model_id
            break
    _save_providers(providers)

    # Reload env supaya getters langsung return nilai baru
    load_dotenv(_ENV_FILE, override=True)
    os.environ["LLM_BASE_URL"] = provider["base_url"]
    os.environ["LLM_API_KEY"] = resolved_key
    os.environ["LLM_MODEL"] = model_id


