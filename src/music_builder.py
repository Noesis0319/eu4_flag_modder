"""EU4 음악 모드 빌드.

생성 구조 (모드 폴더 기준):
  music/<mod_id>_<track>.ogg                # 실제 음악 파일
  music/<mod_id>.asset                      # music = { name=".." file=".." } 등록
  music/<mod_id>_songs.txt                  # song = { name=".." chance = {...} }
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


# 재생 조건 프리셋: (한글 라벨, EU4 modifier 블록 본문)
# EU4 song chance 의 modifier 는 factor 와 trigger 조건을 함께 갖는다.
CHANCE_PRESETS: dict[str, tuple[str, str]] = {
    "default":   ("기본 (보통 빈도)",       "modifier = { factor = 1 }"),
    "often":     ("자주 재생 (×3)",          "modifier = { factor = 3 }"),
    "rare":      ("드물게 재생 (×0.3)",     "modifier = { factor = 0.3 }"),
    "war":       ("전쟁 시 자주 재생",       "modifier = { factor = 2 is_at_war = yes }"),
    "peace":     ("평시에 자주 재생",         "modifier = { factor = 2 is_at_war = no }"),
    "menu_only": ("메인 메뉴 전용 (게임 중 X)", "modifier = { factor = 0 }"),
}

PRESET_BY_LABEL = {label: key for key, (label, _) in CHANCE_PRESETS.items()}
LABEL_BY_PRESET = {key: label for key, (label, _) in CHANCE_PRESETS.items()}


@dataclass
class MusicEntry:
    track_name: str          # 사용자가 지정하는 트랙 이름 (영숫자/_ 만 유지됨)
    source_file: Path        # 원본 파일 (.ogg / .mp3 / .wav / .m4a / .flac …)
    chance_preset: str = "default"


def safe_track_name(s: str) -> str:
    s = re.sub(r"[^0-9A-Za-z_]+", "_", (s or "").strip())
    s = s.strip("_")
    return s or "track"


def ffmpeg_path() -> Path | None:
    """PATH 에서 ffmpeg(.exe) 찾기. 없으면 None."""
    sep = os.pathsep
    candidates = ("ffmpeg.exe", "ffmpeg")
    for part in (os.environ.get("PATH") or "").split(sep):
        if not part:
            continue
        for c in candidates:
            p = Path(part) / c
            if p.is_file():
                return p
    return None


def _convert_to_ogg(src: Path, dst: Path, ff: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    # libvorbis q5 ≈ 160kbps; 게임 음악으로 충분
    cmd = [str(ff), "-y", "-i", str(src),
           "-vn", "-c:a", "libvorbis", "-q:a", "5", str(dst)]
    proc = subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        tail = (proc.stderr or "").strip().splitlines()[-5:]
        raise RuntimeError(
            f"ffmpeg 변환 실패 ({src.name}):\n" + "\n".join(tail))


def build_music(mod_dir: Path, mod_id: str,
                entries: list[MusicEntry]) -> list[str]:
    """음악 트랙들을 모드 폴더에 빌드. 등록된 풀네임 목록을 반환."""
    if not entries:
        return []

    music_dir = mod_dir / "music"
    music_dir.mkdir(parents=True, exist_ok=True)
    ff = ffmpeg_path()

    full_names: list[str] = []
    asset_blocks: list[str] = []
    song_blocks: list[str] = []

    # 트랙명 충돌 방지
    used: set[str] = set()
    for e in entries:
        src = Path(e.source_file)
        if not src.is_file():
            raise RuntimeError(f"음악 파일을 찾을 수 없음: {src}")

        base = safe_track_name(e.track_name) or safe_track_name(src.stem)
        # 동일 이름 충돌이면 _2, _3 … 추가
        candidate = base
        i = 2
        while candidate in used:
            candidate = f"{base}_{i}"
            i += 1
        used.add(candidate)

        full_name = f"{mod_id}_{candidate}"
        target_ogg = music_dir / f"{full_name}.ogg"

        if src.suffix.lower() == ".ogg":
            shutil.copyfile(src, target_ogg)
        else:
            if ff is None:
                raise RuntimeError(
                    f"'{src.name}' 변환에 ffmpeg 가 필요합니다.\n"
                    "ffmpeg 를 설치(PATH 등록)하거나 .ogg 파일을 준비하세요.")
            _convert_to_ogg(src, target_ogg, ff)

        preset = e.chance_preset if e.chance_preset in CHANCE_PRESETS else "default"
        _label, modifier_block = CHANCE_PRESETS[preset]

        asset_blocks.append(
            "music = {\n"
            f'\tname = "{full_name}"\n'
            f'\tfile = "{target_ogg.name}"\n'
            "}")
        song_blocks.append(
            "song = {\n"
            f'\tname = "{full_name}"\n'
            "\tchance = {\n"
            f"\t\t{modifier_block}\n"
            "\t}\n"
            "}")
        full_names.append(full_name)

    (music_dir / f"{mod_id}.asset").write_text(
        "\n\n".join(asset_blocks) + "\n", encoding="utf-8-sig")
    (music_dir / f"{mod_id}_songs.txt").write_text(
        "\n\n".join(song_blocks) + "\n", encoding="utf-8-sig")

    return full_names


# ---------------- 모드 불러오기용: 기존 .asset 파싱 ----------------

_ASSET_BLOCK = re.compile(
    r'music\s*=\s*\{[^}]*?name\s*=\s*"([^"]+)"[^}]*?file\s*=\s*"([^"]+)"',
    re.DOTALL)
_SONG_BLOCK = re.compile(
    r'song\s*=\s*\{(?P<body>[^}]*?(?:\{[^}]*\}[^}]*?)*)\}',
    re.DOTALL)


def parse_music_assets(mod_dir: Path) -> list[tuple[str, Path]]:
    """모드의 music 폴더에서 (name, ogg_path) 리스트 반환."""
    music_dir = mod_dir / "music"
    if not music_dir.is_dir():
        return []
    found: list[tuple[str, Path]] = []
    for asset in sorted(music_dir.glob("*.asset")):
        try:
            text = asset.read_text(encoding="utf-8-sig", errors="replace")
        except Exception:
            continue
        for name, fname in _ASSET_BLOCK.findall(text):
            ogg = music_dir / fname
            if ogg.is_file():
                found.append((name, ogg))
    return found


def parse_song_presets(mod_dir: Path) -> dict[str, str]:
    """songs.txt 들을 파싱해서 트랙 → 프리셋 키 매핑 추정."""
    music_dir = mod_dir / "music"
    if not music_dir.is_dir():
        return {}
    result: dict[str, str] = {}
    for songs in sorted(music_dir.glob("*_songs.txt")):
        try:
            text = songs.read_text(encoding="utf-8-sig", errors="replace")
        except Exception:
            continue
        # 간단한 두 번째 파싱: 각 song 블록의 name + modifier 문자열 비교
        for m in re.finditer(
                r'song\s*=\s*\{\s*name\s*=\s*"([^"]+)"\s*'
                r'chance\s*=\s*\{\s*(modifier\s*=\s*\{[^}]*\})\s*\}\s*\}',
                text, re.DOTALL):
            name = m.group(1)
            mod_block = re.sub(r"\s+", " ", m.group(2)).strip()
            preset = _match_preset(mod_block)
            if preset:
                result[name] = preset
    return result


def _match_preset(mod_block: str) -> str | None:
    norm = re.sub(r"\s+", " ", mod_block).strip().lower()
    for key, (_label, body) in CHANCE_PRESETS.items():
        ref = re.sub(r"\s+", " ", body).strip().lower()
        if norm == ref:
            return key
    return None
