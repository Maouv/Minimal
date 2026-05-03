# api/providers.py — GET /config, /providers, POST /providers/probe, /add, /switch

import os

from fastapi import APIRouter, HTTPException

import config
from schemas import ConfigResponse

router = APIRouter()


@router.get("/config")
async def get_config() -> ConfigResponse:
    return ConfigResponse(
        base_url=config.base_url(),
        model=config.model(),
        models=config.all_models(),
        context_window=config.context_window(),
        timeout=config.timeout(),
        max_tokens=config.max_tokens(),
        configured=config.is_configured(),
    )


@router.get("/providers")
async def list_providers():
    """Return semua providers yang sudah disimpan."""
    return {"providers": config.load_providers()}


@router.post("/providers/probe")
async def probe_provider(req: dict):
    """
    Probe /v1/models dari base_url + api_key.
    api_key "__from_env__" → pakai API key dari .env (untuk existing provider).
    Lookup by provider_name dulu (jika dikirim), fallback ke base_url.
    """
    from probe_models import probe

    base_url = req.get("base_url", "").strip()
    api_key = req.get("api_key", "").strip()
    provider_name = req.get("provider_name", "").strip()
    if not base_url or not api_key:
        raise HTTPException(status_code=400, detail="base_url and api_key required")
    # Resolve __from_env__ ke actual key
    if api_key == "__from_env__":
        providers = config.load_providers()
        provider = None
        if provider_name:
            provider = next((p for p in providers if p["name"] == provider_name), None)
        if not provider:
            provider = next((p for p in providers if p["base_url"] == base_url), None)
        if provider:
            api_key = os.getenv(provider["env_key"], config.api_key())
        else:
            api_key = config.api_key()
    result = await probe(base_url, api_key)
    return result


@router.post("/providers/add")
async def add_provider(req: dict):
    """
    Tambah provider baru + simpan API key ke .env.
    Body: { name, base_url, api_key }
    """
    name = req.get("name", "").strip()
    base_url = req.get("base_url", "").strip()
    api_key = req.get("api_key", "").strip()
    if not name or not base_url or not api_key:
        raise HTTPException(status_code=400, detail="name, base_url, api_key required")
    entry = config.add_provider(name, base_url, api_key)
    return {"ok": True, "provider": entry}


@router.post("/providers/switch")
async def switch_model(req: dict):
    """
    Switch active provider + model.
    Body: { provider_name, model_id }
    Update LLM_BASE_URL, LLM_API_KEY, LLM_MODEL di .env dan reload.
    """
    provider_name = req.get("provider_name", "").strip()
    model_id = req.get("model_id", "").strip()
    if not provider_name or not model_id:
        raise HTTPException(
            status_code=400, detail="provider_name and model_id required"
        )

    providers = config.load_providers()
    provider = next((p for p in providers if p["name"] == provider_name), None)
    if not provider:
        raise HTTPException(
            status_code=404, detail=f"Provider '{provider_name}' not found"
        )

    config.switch_provider_model(provider, model_id)
    return {"ok": True, "model": model_id, "base_url": provider["base_url"]}
