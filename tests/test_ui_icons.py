import pytest
from PIL import Image

from src.ui_icons import IconEntry, all_icon_paths, build_icons, scan_icons_in_mod


@pytest.mark.parametrize("rel", [
    "../gfx/interface/x.dds",
    "gfx/../../x.dds",
    "gfx/interface/x.png",
    "C:/gfx/interface/x.dds",
])
def test_rejects_bad_paths(tmp_path, make_image, rel):
    with pytest.raises(ValueError):
        build_icons(tmp_path / "mod", [IconEntry(rel, make_image("a.png"))],
                    tmp_path / "game")
    assert not (tmp_path / "mod").exists()


def test_size_follows_original_and_keeps_alpha(tmp_path, make_image):
    game = tmp_path / "game"
    (game / "gfx" / "interface").mkdir(parents=True)
    Image.new("RGBA", (64, 32)).save(game / "gfx" / "interface" / "x.dds")
    mod = tmp_path / "mod"
    src = make_image("a.png", mode="RGBA", color=(1, 2, 3, 0))
    got = build_icons(mod, [IconEntry("gfx/interface/x.dds", src)], game)
    assert got == ["gfx/interface/x.dds"]
    with Image.open(mod / "gfx" / "interface" / "x.dds") as im:
        assert im.size == (64, 32)
        assert im.mode == "RGBA"
        assert im.getpixel((0, 0))[3] == 0


def test_default_size_without_original(tmp_path, make_image):
    mod = tmp_path / "mod"
    build_icons(mod, [IconEntry("gfx/interface/y.DDS", make_image("a.png"))],
                tmp_path / "game")
    with Image.open(mod / "gfx" / "interface" / "y.DDS") as im:
        assert im.size == (256, 256)


def test_scan_excludes_known_folders(tmp_path):
    for rel in ("gfx/interface/a.dds", "gfx/flags/b.dds",
                "gfx/event_pictures/m/c.dds", "gfx/loadingscreens/d.dds",
                "gfx/interface/sub/e.dds"):
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"")
    got = sorted(rel for rel, _p in scan_icons_in_mod(tmp_path))
    assert got == ["gfx/interface/a.dds", "gfx/interface/sub/e.dds"]
    assert scan_icons_in_mod(tmp_path / "none") == []


def test_preset_paths_are_valid():
    for rel, _name, _group in all_icon_paths():
        assert rel.startswith("gfx/") and rel.lower().endswith(".dds")
        assert ".." not in rel
