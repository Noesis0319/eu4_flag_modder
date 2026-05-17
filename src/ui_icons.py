"""EU4 UI 아이콘 교체 모듈.

전략: 게임의 어떤 gfx/interface/* (또는 gfx/* 어디든) 파일이든 같은 상대 경로로
모드 폴더에 동일 사이즈 DDS 로 덮어쓰기. 원본 DDS 의 사이즈를 그대로 따라간다.

UX 큐레이션: 모더가 자주 교체하는 아이콘들을 프리셋 목록으로 제공하되,
사용자가 직접 임의의 게임 내 dds 경로를 추가하는 것도 가능.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from .image_processor import _fit


# 자주 교체되는 아이콘들. (그룹, [(게임 상대 경로, 표시명)])
ICON_PRESETS: dict[str, list[tuple[str, str]]] = {
    "메인 메뉴 / 로고": [
        ("gfx/interface/Eu4_logo.dds", "EU4 로고"),
        ("gfx/interface/Loadingscreen_loadingstatus.dds", "로딩 상태 바"),
        ("gfx/interface/Loadingscreen_loadingtip.dds", "로딩 팁 박스"),
    ],
    "UI 배경": [
        ("gfx/interface/Navy_Panel_bg.dds", "해군 패널 배경"),
        ("gfx/interface/Unit_Panel_bg.dds", "유닛 패널 배경"),
        ("gfx/interface/country_estates_view_bg.dds", "신분 패널 배경"),
    ],
    "종교 / 종교 패널": [
        ("gfx/interface/change_religion_icon.dds", "개종 아이콘"),
        ("gfx/interface/country_icon_religion.dds", "국가 종교 아이콘"),
        ("gfx/interface/advisor_indicator_religion.dds", "고문관 종교 표시"),
    ],
    "버튼 / 액션": [
        ("gfx/interface/abandon_core_button.dds", "중핵 포기 버튼"),
        ("gfx/interface/abandon_state_button.dds", "스테이트 포기 버튼"),
        ("gfx/interface/abdicate_button.dds", "양위 버튼"),
        ("gfx/interface/abandon_idea.dds", "아이디어 포기"),
    ],
    "기타 표시": [
        ("gfx/interface/accepted_cultures.dds", "수용 문화 아이콘"),
    ],
}


def all_icon_paths() -> list[tuple[str, str, str]]:
    """(rel_path, display, group) 리스트."""
    out = []
    for group, items in ICON_PRESETS.items():
        for rel, name in items:
            out.append((rel, name, group))
    return out


@dataclass
class IconEntry:
    game_rel_path: str        # 예: "gfx/interface/Eu4_logo.dds"
    source_image: Path
    fit_mode: str = "cover"


def to_icon_dds(src: Path, dst: Path, target_size: tuple[int, int],
                fit_mode: str = "cover") -> None:
    img = Image.open(src).convert("RGB")
    out = _fit(img, target_size, fit_mode)
    dst.parent.mkdir(parents=True, exist_ok=True)
    out.save(dst, format="DDS")


def build_icons(mod_dir: Path, entries: list[IconEntry],
                game_dir: Path) -> list[str]:
    """원본 dds 의 사이즈를 그대로 따라서 변환. 같은 상대 경로로 저장."""
    if not entries:
        return []
    converted: list[str] = []
    for e in entries:
        # 원본 사이즈 검출 (없으면 256x256 기본)
        original = game_dir / e.game_rel_path
        size = (256, 256)
        if original.is_file():
            try:
                with Image.open(original) as im:
                    size = im.size
            except Exception:
                pass
        dst = mod_dir / e.game_rel_path
        to_icon_dds(Path(e.source_image), dst, size, fit_mode=e.fit_mode)
        converted.append(e.game_rel_path)
    return converted


def scan_icons_in_mod(mod_dir: Path) -> list[tuple[str, Path]]:
    """모드 안의 gfx 폴더에서 dds 파일을 스캔. event_pictures/flags/loadingscreens 는 제외."""
    gfx = mod_dir / "gfx"
    if not gfx.is_dir():
        return []
    out: list[tuple[str, Path]] = []
    exclude_parts = {"event_pictures", "flags", "loadingscreens"}
    for dds in gfx.rglob("*.dds"):
        if any(part in exclude_parts for part in dds.relative_to(mod_dir).parts):
            continue
        rel = dds.relative_to(mod_dir).as_posix()
        out.append((rel, dds))
    return out
