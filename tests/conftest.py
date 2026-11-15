from __future__ import annotations

import pytest


@pytest.fixture
def api_version() -> str:
    return "v21.0"
