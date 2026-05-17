"""EU4 효과음 / 이벤트 사운드 교체 모듈.

게임 본체: sound/*.wav + sound/all_sounds.asset
asset 에 sound = { name="X" file="X.wav" } 로 등록. 코드는 name 으로 참조.

교체 전략: 같은 name 으로 우리 wav 를 덮어쓰는 asset 을 모드에 동봉.
파일 충돌을 막기 위해 우리 파일은 sound/<mod_id>_<sound_key>.wav 로 저장하고
asset 에서 그 파일을 가리킴.

EU4 의 게임 코드에 하드코딩된 sound name 들을 큐레이션해서 제공.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .music_builder import ffmpeg_path


# 자주 교체되는 효과음 키 (카테고리 한글 라벨, [(키, 표시명), ...])
# 키는 EU4 sound asset 의 name 과 일치해야 함.
SOUND_GROUPS: dict[str, list[tuple[str, str]]] = {
    "UI / 메뉴": [
        ("close_window", "창 닫기"),
        ("connecting", "접속 효과음"),
        ("chat_message_received", "채팅 알림"),
        ("alert_new", "새 알림"),
    ],
    "이벤트 / 정치": [
        ("complete_mission", "미션 완료"),
        ("bought_new_idea", "새 아이디어 채택"),
        ("become_papal_controller", "교황령 장악"),
        ("debate_lose", "토론 패배"),
        ("debate_win", "토론 승리"),
        ("electoral_tie_breaker", "선거 결과"),
        ("event_window", "이벤트 창 효과음"),
        ("revolution", "혁명"),
    ],
    "전쟁 / 군사": [
        ("battle_won", "전투 승리"),
        ("battle_lost", "전투 패배"),
        ("siege_won", "공성 승리"),
        ("siege_lost", "공성 패배"),
        ("declare_war", "선전포고"),
        ("peace_treaty", "평화 조약"),
        ("attach_unit_ship", "함대 합류"),
        ("attack_natives", "원주민 공격"),
        ("build_army", "육군 건설"),
        ("build_navy", "해군 건설"),
    ],
    "건설 / 식민": [
        ("build_building", "건물 건설"),
        ("construction_begin", "건설 시작"),
        ("burn_colony", "식민지 약탈"),
        ("change_unit_type", "유닛 종류 변경"),
    ],
    "종교 / DOTF": [
        ("defender_of_the_catholic_faith", "가톨릭 수호자"),
        ("defender_of_the_protestant_faith", "개신교 수호자"),
        ("defender_of_the_reformed_faith", "개혁교회 수호자"),
        ("defender_of_the_orthodox_faith", "정교회 수호자"),
        ("defender_of_the_coptic_faith", "콥트교 수호자"),
        ("defender_of_the_sunni_faith", "수니파 수호자"),
        ("defender_of_the_shiite_faith", "시아파 수호자"),
        ("defender_of_the_ibadi_faith", "이바디파 수호자"),
    ],
    "시대": [
        ("age_of_discovery", "탐험의 시대"),
        ("age_of_reformation", "종교개혁의 시대"),
        ("age_of_absolutism", "절대주의의 시대"),
        ("age_of_revolutions", "혁명의 시대"),
    ],
}


def all_sound_keys() -> list[tuple[str, str, str]]:
    """(key, display, group) 리스트."""
    out = []
    for group, items in SOUND_GROUPS.items():
        for key, name in items:
            out.append((key, name, group))
    return out


@dataclass
class SoundEntry:
    key: str                  # 게임 본체 sound name (덮어쓸 대상)
    source_file: Path         # 사용자 파일 (.wav / 또는 ffmpeg 가능한 형식)


def _convert_to_wav(src: Path, dst: Path, ff: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    # EU4 는 16-bit PCM WAV 를 기대
    cmd = [str(ff), "-y", "-i", str(src),
           "-vn", "-c:a", "pcm_s16le", "-ar", "44100", str(dst)]
    proc = subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        tail = (proc.stderr or "").strip().splitlines()[-5:]
        raise RuntimeError(
            f"ffmpeg 변환 실패 ({src.name}):\n" + "\n".join(tail))


def build_sounds(mod_dir: Path, mod_id: str,
                 entries: list[SoundEntry]) -> list[str]:
    """sound/*.wav 복사 + mod_id.asset 으로 본체 키 덮어쓰기."""
    if not entries:
        return []
    sound_dir = mod_dir / "sound"
    sound_dir.mkdir(parents=True, exist_ok=True)
    ff = ffmpeg_path()

    asset_blocks: list[str] = []
    used_names: set[str] = set()
    overridden: list[str] = []

    for e in entries:
        src = Path(e.source_file)
        if not src.is_file():
            raise RuntimeError(f"사운드 파일을 찾을 수 없음: {src}")
        if e.key in used_names:
            continue
        used_names.add(e.key)

        # 파일명은 본체와 충돌하지 않도록 mod_id 접두어
        safe_key = re.sub(r"[^0-9A-Za-z_]+", "_", e.key)
        target_wav = sound_dir / f"{mod_id}_{safe_key}.wav"

        if src.suffix.lower() == ".wav":
            shutil.copyfile(src, target_wav)
        else:
            if ff is None:
                raise RuntimeError(
                    f"'{src.name}' 변환에 ffmpeg 가 필요합니다.\n"
                    "ffmpeg 를 설치(PATH 등록)하거나 .wav 파일을 준비하세요.")
            _convert_to_wav(src, target_wav, ff)

        asset_blocks.append(
            "sound = {\n"
            f'\tname = {e.key}\n'
            f'\tfile = "{target_wav.name}"\n'
            "}")
        overridden.append(e.key)

    (sound_dir / f"{mod_id}.asset").write_text(
        "\n".join(asset_blocks) + "\n", encoding="utf-8-sig")
    return overridden


# ---- 모드 불러오기: 우리 형식 asset 파싱 ----
_SOUND_ASSET_RE = re.compile(
    r'sound\s*=\s*\{[^}]*?name\s*=\s*([A-Za-z0-9_]+)[^}]*?file\s*=\s*"([^"]+)"',
    re.DOTALL)


def parse_sound_assets(mod_dir: Path) -> list[tuple[str, Path]]:
    sd = mod_dir / "sound"
    if not sd.is_dir():
        return []
    out: list[tuple[str, Path]] = []
    for asset in sorted(sd.glob("*.asset")):
        try:
            text = asset.read_text(encoding="utf-8-sig", errors="replace")
        except Exception:
            continue
        for name, fname in _SOUND_ASSET_RE.findall(text):
            wav = sd / fname
            if wav.is_file():
                out.append((name, wav))
    return out
