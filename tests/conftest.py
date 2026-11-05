from pathlib import Path

import pytest
from PIL import Image


@pytest.fixture
def make_image(tmp_path):
    def _make(name: str, size=(40, 20), mode="RGB", color=(200, 30, 30)) -> Path:
        path = tmp_path / name
        Image.new(mode, size, color).save(path)
        return path
    return _make
