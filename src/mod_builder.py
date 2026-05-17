"""EU4 자산 교체 모드 빌더 (국기 + 이벤트 픽처).

생성 구조:
  <mods_root>/<mod_id>/descriptor.mod
  <mods_root>/<mod_id>/thumbnail.png                  (옵션)
  <mods_root>/<mod_id>/gfx/flags/<TAG>.tga            (국기)
  <mods_root>/<mod_id>/gfx/event_pictures/<mod_id>/<KEY>.dds
  <mods_root>/<mod_id>/interface/<mod_id>_event_pictures.gfx

EU4 인식용 (사용자 mod 폴더):
  <user>/mod/<mod_id>.mod  (path= 지정)
  <user>/mod/<mod_id>/...  (모드 본체 복사본)
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .image_processor import to_flag_tga, to_event_picture_dds
from .music_builder import MusicEntry, build_music
from .loading_screens import LoadingScreenEntry, build_loading_screens
from .sounds import SoundEntry, build_sounds
from .ui_icons import IconEntry, build_icons
from .ideas import IdeaGroupEntry, build_ideas
from .localisation import LocEntry, build_localisation


EU4_USER_DIR_DEFAULT = (
    Path.home() / "Documents" / "Paradox Interactive" / "Europa Universalis IV"
)


@dataclass
class FlagEntry:
    tag: str
    source_image: Path
    fit_mode: str = "cover"


@dataclass
class EventPictureEntry:
    key: str                # 예: BATTLE_eventPicture (게임 본체 키를 재정의해 덮어쓰기)
    source_image: Path
    fit_mode: str = "cover"


def safe_mod_id(name: str) -> str:
    s = re.sub(r"[^0-9A-Za-z가-힣_\-]+", "_", name.strip())
    return s or "custom_mod"


def write_descriptor(path: Path, mod_name: str, has_thumb: bool,
                     supported_version: str = "1.37.*") -> None:
    lines = [
        f'name="{mod_name}"',
        f'supported_version="{supported_version}"',
        'tags={',
        '\t"Graphics"',
        '\t"Flags"',
        '\t"Events"',
        '\t"Sound"',
        '}',
    ]
    if has_thumb:
        lines.append('picture="thumbnail.png"')
    path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")


def write_root_mod_file(path: Path, mod_name: str, mod_dir: Path,
                        has_thumb: bool,
                        supported_version: str = "1.37.*") -> None:
    posix_path = str(mod_dir).replace("\\", "/")
    lines = [
        f'name="{mod_name}"',
        f'path="{posix_path}"',
        f'supported_version="{supported_version}"',
        'tags={',
        '\t"Graphics"',
        '\t"Flags"',
        '\t"Events"',
        '\t"Sound"',
        '}',
    ]
    if has_thumb:
        lines.append('picture="thumbnail.png"')
    path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")


def write_event_picture_gfx(path: Path, mod_id: str,
                            entries: list[EventPictureEntry]) -> None:
    """spriteTypes 파일 작성. 게임 본체 같은 키를 우리 dds 로 덮어씀."""
    lines = ["spriteTypes = {"]
    for e in entries:
        rel = f"gfx/event_pictures/{mod_id}/{e.key}.dds"
        lines.append("\tspriteType = {")
        lines.append(f'\t\tname = "{e.key}"')
        lines.append(f'\t\ttexturefile = "{rel}"')
        lines.append('\t\talwaystransparent = yes')
        lines.append("\t}")
    lines.append("}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")


def build_mod(mod_name: str,
              flag_entries: Iterable[FlagEntry] = (),
              event_entries: Iterable[EventPictureEntry] = (),
              music_entries: Iterable[MusicEntry] = (),
              loading_entries: Iterable[LoadingScreenEntry] = (),
              sound_entries: Iterable[SoundEntry] = (),
              icon_entries: Iterable[IconEntry] = (),
              idea_entries: Iterable[IdeaGroupEntry] = (),
              loc_entries: Iterable[LocEntry] = (),
              game_dir: Path | None = None,
              output_root: Path = Path("output"),
              install_to_eu4: bool = True,
              eu4_user_dir: Path | None = None,
              thumbnail: Path | None = None,
              supported_version: str = "1.37.*") -> dict:
    flag_entries = list(flag_entries)
    event_entries = list(event_entries)
    music_entries = list(music_entries)
    loading_entries = list(loading_entries)
    sound_entries = list(sound_entries)
    icon_entries = list(icon_entries)
    idea_entries = list(idea_entries)
    loc_entries = list(loc_entries)

    has_any = any([flag_entries, event_entries, music_entries,
                   loading_entries, sound_entries, icon_entries,
                   idea_entries, loc_entries])
    if not has_any:
        raise ValueError("최소 1개 이상의 자산이 필요합니다.")

    mod_id = safe_mod_id(mod_name)
    mod_dir = output_root / mod_id

    # 기존 출력 폴더 비우기 (안전하게: 같은 모드명 재빌드)
    if mod_dir.exists():
        shutil.rmtree(mod_dir)
    mod_dir.mkdir(parents=True, exist_ok=True)

    converted_flags: list[str] = []
    if flag_entries:
        flags_dir = mod_dir / "gfx" / "flags"
        flags_dir.mkdir(parents=True, exist_ok=True)
        for e in flag_entries:
            tag = e.tag.upper()
            to_flag_tga(e.source_image, flags_dir / f"{tag}.tga",
                        fit_mode=e.fit_mode)
            converted_flags.append(tag)

    converted_events: list[str] = []
    if event_entries:
        ep_dir = mod_dir / "gfx" / "event_pictures" / mod_id
        ep_dir.mkdir(parents=True, exist_ok=True)
        for e in event_entries:
            to_event_picture_dds(e.source_image, ep_dir / f"{e.key}.dds",
                                  fit_mode=e.fit_mode)
            converted_events.append(e.key)
        gfx_file = mod_dir / "interface" / f"{mod_id}_event_pictures.gfx"
        write_event_picture_gfx(gfx_file, mod_id, event_entries)

    converted_music: list[str] = []
    if music_entries:
        converted_music = build_music(mod_dir, mod_id, music_entries)

    converted_loading: list[int] = []
    if loading_entries:
        converted_loading = build_loading_screens(mod_dir, loading_entries)

    converted_sounds: list[str] = []
    if sound_entries:
        converted_sounds = build_sounds(mod_dir, mod_id, sound_entries)

    converted_icons: list[str] = []
    if icon_entries:
        if game_dir is None:
            game_dir = Path(
                "C:/Program Files (x86)/Steam/steamapps/common/Europa Universalis IV")
        converted_icons = build_icons(mod_dir, icon_entries, game_dir)

    converted_ideas: list[str] = []
    if idea_entries:
        converted_ideas = build_ideas(mod_dir, mod_id, idea_entries)

    converted_loc_files: list[str] = []
    if loc_entries:
        converted_loc_files = build_localisation(mod_dir, mod_id, loc_entries)

    has_thumb = False
    if thumbnail and Path(thumbnail).is_file():
        try:
            shutil.copyfile(thumbnail, mod_dir / "thumbnail.png")
            has_thumb = True
        except Exception:
            has_thumb = False

    write_descriptor(mod_dir / "descriptor.mod", mod_name, has_thumb,
                     supported_version)

    installed_mod_file = None
    installed_mod_dir = None
    if install_to_eu4:
        user_dir = Path(eu4_user_dir) if eu4_user_dir else EU4_USER_DIR_DEFAULT
        eu4_mod_dir = user_dir / "mod"
        eu4_mod_dir.mkdir(parents=True, exist_ok=True)
        target_dir = eu4_mod_dir / mod_id
        if target_dir.exists():
            shutil.rmtree(target_dir)
        shutil.copytree(mod_dir, target_dir)
        root_mod_file = eu4_mod_dir / f"{mod_id}.mod"
        write_root_mod_file(root_mod_file, mod_name, target_dir, has_thumb,
                            supported_version)
        installed_mod_file = root_mod_file
        installed_mod_dir = target_dir

    return {
        "mod_id": mod_id,
        "mod_dir": mod_dir,
        "converted_flags": converted_flags,
        "converted_events": converted_events,
        "converted_music": converted_music,
        "converted_loading": converted_loading,
        "converted_sounds": converted_sounds,
        "converted_icons": converted_icons,
        "converted_ideas": converted_ideas,
        "converted_loc_files": converted_loc_files,
        "installed_mod_file": installed_mod_file,
        "installed_mod_dir": installed_mod_dir,
    }
