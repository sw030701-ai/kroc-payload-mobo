from pathlib import Path

import pytest

from kroc_mobo.config import load_config


@pytest.fixture
def config():
    return load_config(Path(__file__).resolve().parents[1] / "configs" / "illustrative.toml", smoke=True)
