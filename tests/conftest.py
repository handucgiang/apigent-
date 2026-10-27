from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_hrm_app() -> Any:
    path = ROOT / "examples" / "hrm-demo" / "hrm_api.py"
    spec = importlib.util.spec_from_file_location("hrm_api", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["hrm_api"] = mod
    spec.loader.exec_module(mod)
    return mod.app


@pytest.fixture
def hrm_app() -> Any:
    return _load_hrm_app()


@pytest.fixture
def hrm_client(hrm_app: Any) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=hrm_app), base_url="http://localhost:8001"
    )
