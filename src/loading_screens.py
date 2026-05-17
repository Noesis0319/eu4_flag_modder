"""EU4 로딩 화면 교체 모듈.

게임 본체: gfx/loadingscreens/load_N.dds (N=0..37), 2048x1536 RGB DDS.
모드에서 같은 이름으로 덮어쓰면 교체됨.

추가 슬롯도 지원 (load_38, load_39 ...) 하지만, 본체가 0..37 안에서만 랜덤 선택
하므로 새 인덱스를 추가해도 게임이 인식하지 못할 수 있음. 안전하게는 0..37 범위 교체.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .image_processor import _fit


LOADING_SCREEN_SIZE = (2048, 1536)
LOADING_SCREEN_COUNT = 38  # 게임 본체가 load_0..load_37 사용


@dataclass
class LoadingScreenEntry:
    index: int                # 0..37 (또는 그 이상)
    source_image: Path
    fit_mode: str = "cover"


def to_loading_screen_dds(src: Path, dst: Path, fit_mode: str = "cover") -> None:
    from PIL import Image
    img = Image.open(src).convert("RGB")
    out = _fit(img, LOADING_SCREEN_SIZE, fit_mode)
    dst.parent.mkdir(parents=True, exist_ok=True)
    out.save(dst, format="DDS")


def build_loading_screens(mod_dir: Path,
                          entries: list[LoadingScreenEntry]) -> list[int]:
    if not entries:
        return []
    ls_dir = mod_dir / "gfx" / "loadingscreens"
    ls_dir.mkdir(parents=True, exist_ok=True)
    converted: list[int] = []
    for e in entries:
        dst = ls_dir / f"load_{e.index}.dds"
        to_loading_screen_dds(Path(e.source_image), dst, fit_mode=e.fit_mode)
        converted.append(e.index)
    return converted
