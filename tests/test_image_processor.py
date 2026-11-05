import pytest
from PIL import Image

from src.image_processor import (
    EVENT_PICTURE_SIZE, FLAG_SIZE, _fit, _open, to_event_picture_dds,
    to_flag_tga,
)


@pytest.mark.parametrize("mode", ["cover", "contain", "stretch"])
def test_fit_keeps_rgba_and_size(mode):
    src = Image.new("RGBA", (40, 20), (10, 20, 30, 128))
    out = _fit(src, (32, 32), mode)
    assert out.mode == "RGBA"
    assert out.size == (32, 32)


def test_fit_contain_pads_rgba_with_transparent():
    src = Image.new("RGBA", (40, 20), (10, 20, 30, 255))
    out = _fit(src, (32, 32), "contain")
    assert out.getpixel((0, 0))[3] == 0
    assert out.getpixel((16, 16))[3] == 255


def test_fit_contain_pads_rgb_with_bg_color():
    src = Image.new("RGB", (40, 20), (255, 255, 255))
    out = _fit(src, (32, 32), "contain", bg_color=(1, 2, 3))
    assert out.mode == "RGB"
    assert out.getpixel((0, 0)) == (1, 2, 3)


def test_open_applies_exif_orientation(tmp_path):
    path = tmp_path / "phone.jpg"
    exif = Image.Exif()
    exif[0x0112] = 6
    Image.new("RGB", (40, 20), (50, 60, 70)).save(path, exif=exif)
    with Image.open(path) as raw:
        assert raw.size == (40, 20)
    assert _open(path).size == (20, 40)


def test_open_without_exif(make_image):
    assert _open(make_image("plain.png")).size == (40, 20)


def test_flag_tga(tmp_path, make_image):
    dst = tmp_path / "out" / "KOR.tga"
    to_flag_tga(make_image("in.png", mode="RGBA", color=(1, 2, 3, 4)), dst)
    with Image.open(dst) as im:
        assert im.format == "TGA"
        assert im.size == FLAG_SIZE
        assert im.mode == "RGB"


def test_event_picture_dds(tmp_path, make_image):
    dst = tmp_path / "out" / "X.dds"
    to_event_picture_dds(make_image("in.png"), dst, fit_mode="contain")
    with Image.open(dst) as im:
        assert im.format == "DDS"
        assert im.size == EVENT_PICTURE_SIZE
