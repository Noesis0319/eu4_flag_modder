"""이미지 변환 유틸.

- 국기:    24-bit TGA, 128x128
- 이벤트 픽처: DDS (Pillow 의 무압축 RGB DDS), 512x132
"""

from pathlib import Path
from PIL import Image

FLAG_SIZE = (128, 128)
EVENT_PICTURE_SIZE = (512, 132)


def _fit(src: Image.Image, size: tuple[int, int], fit_mode: str,
         bg_color=(0, 0, 0)) -> Image.Image:
    sw, sh = src.size
    tw, th = size
    if fit_mode == "stretch":
        return src.resize(size, Image.LANCZOS)
    if fit_mode == "contain":
        scale = min(tw / sw, th / sh)
        nw, nh = max(1, int(sw * scale)), max(1, int(sh * scale))
        resized = src.resize((nw, nh), Image.LANCZOS)
        out = Image.new("RGB", size, bg_color)
        out.paste(resized, ((tw - nw) // 2, (th - nh) // 2))
        return out
    # cover
    scale = max(tw / sw, th / sh)
    nw, nh = max(1, int(sw * scale)), max(1, int(sh * scale))
    resized = src.resize((nw, nh), Image.LANCZOS)
    left = (nw - tw) // 2
    top = (nh - th) // 2
    return resized.crop((left, top, left + tw, top + th))


# ---------------- 국기 (TGA 128x128) ----------------

def to_flag_tga(src_path: str | Path, dst_path: str | Path,
                fit_mode: str = "cover", bg_color=(0, 0, 0)) -> None:
    src = Image.open(src_path).convert("RGB")
    out = _fit(src, FLAG_SIZE, fit_mode, bg_color)
    dst_path = Path(dst_path)
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    out.save(dst_path, format="TGA")


def preview_image(src_path: str | Path, fit_mode: str = "cover",
                  bg_color=(0, 0, 0)) -> Image.Image:
    src = Image.open(src_path).convert("RGB")
    return _fit(src, FLAG_SIZE, fit_mode, bg_color)


# ---------------- 이벤트 픽처 (DDS 512x132) ----------------

def to_event_picture_dds(src_path: str | Path, dst_path: str | Path,
                          fit_mode: str = "cover",
                          bg_color=(0, 0, 0)) -> None:
    src = Image.open(src_path).convert("RGB")
    out = _fit(src, EVENT_PICTURE_SIZE, fit_mode, bg_color)
    dst_path = Path(dst_path)
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    out.save(dst_path, format="DDS")


def preview_event_picture(src_path: str | Path, fit_mode: str = "cover",
                          bg_color=(0, 0, 0)) -> Image.Image:
    src = Image.open(src_path).convert("RGB")
    return _fit(src, EVENT_PICTURE_SIZE, fit_mode, bg_color)
