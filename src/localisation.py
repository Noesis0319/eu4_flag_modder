"""EU4 로컬라이제이션 (YAML) 편집 모듈.

EU4 YAML 형식:
  l_korean:
   KEY:0 "값"
   KEY2:1 "다른 값"

- UTF-8 BOM 필수
- 첫 줄 `l_<언어>:` 이후 각 라인은 공백 1칸 들여쓰기
- 값 안의 따옴표는 \" 로 이스케이프
- :숫자 는 게임 내부 버전 번호 (대개 0)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


SUPPORTED_LANGUAGES = ["korean", "english", "french", "german", "spanish"]


@dataclass
class LocEntry:
    key: str            # 로컬 키 (예: my_event.0.t)
    value: str          # 표시 텍스트
    version: int = 0    # :N 의 N
    language: str = "korean"


def _yml_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def build_localisation(mod_dir: Path, mod_id: str,
                       entries: Iterable[LocEntry]) -> list[str]:
    """언어별로 파일을 묶어 작성. 파일명: <mod_id>_l_<lang>.yml"""
    entries = list(entries)
    if not entries:
        return []
    loc_dir = mod_dir / "localisation"
    loc_dir.mkdir(parents=True, exist_ok=True)

    by_lang: dict[str, list[LocEntry]] = {}
    for e in entries:
        by_lang.setdefault(e.language or "korean", []).append(e)

    written_files: list[str] = []
    for lang, items in by_lang.items():
        lines = [f"l_{lang}:"]
        # 키 중복 방지: 같은 키는 마지막 정의가 이김
        seen: dict[str, str] = {}
        for it in items:
            seen[it.key] = (
                f' {it.key}:{it.version} "{_yml_escape(it.value)}"')
        lines.extend(seen.values())
        fname = f"{mod_id}_l_{lang}.yml"
        (loc_dir / fname).write_text("\n".join(lines) + "\n",
                                      encoding="utf-8-sig")
        written_files.append(fname)
    return written_files


# 형식: " key:0 \"value\""  (앞 공백 1+개, 콜론 뒤 숫자, 따옴표 안의 값)
_LINE_RE = re.compile(
    r'^\s+([A-Za-z0-9_.\-]+)\s*:\s*(\d+)\s+"((?:[^"\\]|\\.)*)"\s*$')


def parse_localisation_file(path: Path) -> tuple[str, list[LocEntry]]:
    """단일 yml 파싱. 반환: (lang, entries)"""
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    lang = "korean"
    entries: list[LocEntry] = []
    for raw in text.splitlines():
        line = raw.rstrip("\r\n")
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m_lang = re.match(r"^\s*l_([a-z_]+)\s*:\s*$", line)
        if m_lang:
            lang = m_lang.group(1)
            continue
        m = _LINE_RE.match(line)
        if m:
            key, ver, val = m.group(1), int(m.group(2)), m.group(3)
            # 역이스케이프
            val = val.replace('\\"', '"').replace("\\\\", "\\")
            entries.append(LocEntry(
                key=key, value=val, version=ver, language=lang))
    return lang, entries


def parse_localisation_dir(mod_dir: Path) -> list[LocEntry]:
    loc_dir = mod_dir / "localisation"
    if not loc_dir.is_dir():
        return []
    out: list[LocEntry] = []
    for yml in sorted(loc_dir.glob("*.yml")):
        try:
            _lang, entries = parse_localisation_file(yml)
            out.extend(entries)
        except Exception:
            continue
    return out
