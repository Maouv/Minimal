# probe_models.py — fetch available models dari OpenAI-compatible /v1/models endpoint
# Return list of model IDs. Caller handles fallback ke manual input.

import httpx
from typing import TypedDict


class ProbeResult(TypedDict):
    ok: bool
    models: list[str]
    error: str | None


async def probe(base_url: str, api_key: str) -> ProbeResult:
    """
    Hit GET /v1/models dengan api_key.
    Return ok=True + list model IDs kalau berhasil.
    Return ok=False + error message kalau gagal (provider tidak support, auth error, dll).
    """
    # Normalize base_url — hapus trailing slash
    url = base_url.rstrip("/") + "/models"

    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers)

        if resp.status_code == 404:
            return {"ok": False, "models": [], "error": "Provider does not support /v1/models"}
        if resp.status_code == 401:
            return {"ok": False, "models": [], "error": "Invalid API key"}
        if resp.status_code == 403:
            return {"ok": False, "models": [], "error": "Access denied"}
        if not resp.is_success:
            return {"ok": False, "models": [], "error": f"HTTP {resp.status_code}"}

        data = resp.json()

        # OpenAI format: { "data": [ { "id": "..." }, ... ] }
        if isinstance(data, dict) and "data" in data:
            models = [m["id"] for m in data["data"] if isinstance(m, dict) and "id" in m]
        # Beberapa provider return list langsung: [ { "id": "..." }, ... ]
        elif isinstance(data, list):
            models = [m["id"] for m in data if isinstance(m, dict) and "id" in m]
        else:
            return {"ok": False, "models": [], "error": "Unexpected response format"}

        models.sort()
        return {"ok": True, "models": models, "error": None}

    except httpx.ConnectError:
        return {"ok": False, "models": [], "error": "Cannot connect to provider"}
    except httpx.TimeoutException:
        return {"ok": False, "models": [], "error": "Connection timed out"}
    except Exception as e:
        return {"ok": False, "models": [], "error": str(e)}
