from PIL import Image

from src.loading_screens import (
    LOADING_SCREEN_SIZE, LoadingScreenEntry, build_loading_screens,
)


def test_build_loading_screens(tmp_path, make_image):
    mod = tmp_path / "mod"
    got = build_loading_screens(mod, [LoadingScreenEntry(3, make_image("a.png"))])
    assert got == [3]
    with Image.open(mod / "gfx" / "loadingscreens" / "load_3.dds") as im:
        assert im.format == "DDS"
        assert im.size == LOADING_SCREEN_SIZE


def test_empty_entries(tmp_path):
    assert build_loading_screens(tmp_path, []) == []
    assert not (tmp_path / "gfx").exists()
