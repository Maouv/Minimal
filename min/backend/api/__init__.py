# api/__init__.py — expose all_routers list untuk di-mount di main.py

from api.health import router as health_router
from api.providers import router as providers_router
from api.project import router as project_router
from api.sessions import router as sessions_router
from api.context import router as context_router
from api.prompt import router as prompt_router

all_routers = [
    health_router,
    providers_router,
    project_router,
    sessions_router,
    context_router,
    prompt_router,
]
