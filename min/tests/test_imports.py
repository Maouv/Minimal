# min/tests/test_imports.py — T2: Import Integrity

import sys
from pathlib import Path

import pytest
from fastapi.routing import APIRouter

BACKEND_DIR = Path(__file__).parent.parent / "backend"


def test_no_old_prompts_py():
    assert not (BACKEND_DIR / "prompts.py").exists(), (
        "prompts.py masih ada — seharusnya sudah dihapus"
    )


def test_prompts_package_importable():
    from prompts import ask_system_prompt, edit_system_prompt, init_system
    assert callable(ask_system_prompt)
    assert callable(edit_system_prompt)
    assert callable(init_system)


def test_api_package_importable():
    from api import all_routers
    assert len(all_routers) > 0


def test_all_routers_are_routers():
    from api import all_routers
    for r in all_routers:
        assert isinstance(r, APIRouter), f"{r!r} bukan APIRouter"


def test_main_importable():
    import main
    assert hasattr(main, "app")
