"""EU4 국가 아이디어 편집 모듈.

생성물:
  common/ideas/<mod_id>_ideas.txt          # idea_group 정의
  localisation/<mod_id>_ideas_l_korean.yml # 표시명/설명

UI 단순화: 사용자가 9개 슬롯(전통/야망/아이디어1~7) 각각에 modifier 목록을 채움.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


# ========== modifier 카탈로그 ==========
# (modifier_key, 한글명, 추천 기본값)
MODIFIER_CATALOG: dict[str, list[tuple[str, str, float]]] = {
    "군사 (육군)": [
        ("discipline", "군기", 0.05),
        ("land_morale", "육군 사기", 0.15),
        ("infantry_power", "보병 위력", 0.10),
        ("cavalry_power", "기병 위력", 0.10),
        ("artillery_power", "포병 위력", 0.10),
        ("manpower_recovery_speed", "인력 회복 속도", 0.15),
        ("army_tradition", "육군 전통 (연간)", 0.50),
        ("recover_army_morale_speed", "사기 회복 속도", 0.10),
        ("shock_damage", "충격 피해", 0.10),
        ("fire_damage", "사격 피해", 0.10),
        ("siege_ability", "공성 능력", 0.10),
        ("land_forcelimit_modifier", "육군 한도", 0.25),
        ("army_maintenance_factor", "육군 유지비", -0.10),
        ("leader_land_shock", "지휘관 충격", 1),
        ("leader_land_fire", "지휘관 사격", 1),
        ("leader_land_manuever", "지휘관 기동", 1),
        ("mercenary_discipline", "용병 군기", 0.05),
        ("fort_maintenance_modifier", "요새 유지비", -0.20),
        ("global_manpower_modifier", "전역 인력", 0.20),
    ],
    "군사 (해군)": [
        ("naval_morale", "해군 사기", 0.15),
        ("navy_tradition", "해군 전통 (연간)", 0.50),
        ("heavy_ship_power", "대형함 위력", 0.10),
        ("light_ship_power", "경량함 위력", 0.10),
        ("galley_power", "갤리 위력", 0.10),
        ("trade_efficiency", "무역 효율", 0.10),
        ("naval_forcelimit_modifier", "해군 한도", 0.25),
        ("naval_attrition", "해군 손실", -0.10),
        ("blockade_efficiency", "봉쇄 효율", 0.33),
        ("leader_naval_shock", "제독 충격", 1),
        ("leader_naval_fire", "제독 사격", 1),
        ("ship_durability", "함선 내구", 0.05),
    ],
    "외교": [
        ("diplomats", "외교관", 1),
        ("diplomatic_reputation", "외교 평판", 2),
        ("improve_relation_modifier", "관계 개선", 0.25),
        ("ae_impact", "호전성 영향", -0.10),
        ("diplomatic_upkeep", "외교 한도", 2),
        ("vassal_income", "속국 수입", 0.25),
        ("vassal_forcelimit_bonus", "속국 군한도", 0.50),
        ("province_warscore_cost", "지방 전과 비용", -0.10),
        ("unjustified_demands", "부당 요구 영향", -0.25),
    ],
    "행정": [
        ("core_creation", "중핵화 비용", -0.20),
        ("governing_capacity_modifier", "통치 한도", 0.25),
        ("stability_cost_modifier", "안정도 비용", -0.10),
        ("legitimacy", "정당성 (연간)", 1),
        ("prestige", "위신 (연간)", 1),
        ("ruler_cost_factor", "군주 비용 감소", -0.25),
        ("yearly_corruption", "부패 (연간)", -0.05),
        ("global_unrest", "전역 불만", -1),
        ("technology_cost", "기술 비용", -0.05),
        ("adm_tech_cost_modifier", "행정 기술 비용", -0.10),
        ("dip_tech_cost_modifier", "외교 기술 비용", -0.10),
        ("mil_tech_cost_modifier", "군사 기술 비용", -0.10),
    ],
    "경제": [
        ("production_efficiency", "생산 효율", 0.10),
        ("trade_efficiency", "무역 효율", 0.10),
        ("inflation_reduction", "인플레이션 감소 (연간)", 0.10),
        ("global_tax_modifier", "전역 세금", 0.10),
        ("interest", "이자율", -1),
        ("merchants", "상인", 1),
        ("caravan_power", "내륙 무역력", 0.20),
        ("trade_steering", "무역 유도", 0.20),
        ("global_trade_goods_size_modifier", "교역품 생산량", 0.10),
        ("development_cost", "개발 비용", -0.10),
    ],
    "식민 / 탐험": [
        ("colonists", "식민지 개척자", 1),
        ("range", "식민 거리", 0.50),
        ("global_colonial_growth", "식민지 성장", 25),
        ("may_explore", "탐험 가능", 1),
        ("native_uprising_chance", "원주민 봉기 확률", -0.50),
        ("native_assimilation", "원주민 동화", 0.50),
    ],
    "종교 / 문화": [
        ("tolerance_own", "국교 관용도", 2),
        ("tolerance_heretic", "이단 관용", 1),
        ("tolerance_heathen", "이교 관용", 1),
        ("missionaries", "선교사", 1),
        ("missionary_strength", "선교 강도", 0.02),
        ("global_missionary_strength", "전역 선교 강도", 0.02),
        ("num_accepted_cultures", "수용 문화 수", 1),
        ("culture_conversion_cost", "문화 변환 비용", -0.20),
        ("religious_unity", "종교 통합도", 0.25),
    ],
}


def all_modifier_keys() -> list[tuple[str, str, float, str]]:
    """(key, 한글, 기본값, 카테고리) 평탄화."""
    out = []
    for cat, items in MODIFIER_CATALOG.items():
        for k, n, v in items:
            out.append((k, n, v, cat))
    return out


# ========== 데이터 모델 ==========

@dataclass
class IdeaSlot:
    """한 슬롯 (전통/야망/아이디어 1~7) 의 modifier 들."""
    display_name: str = ""           # 게임에 표시될 이름 (한글)
    description: str = ""            # 설명 (선택)
    modifiers: dict[str, float] = field(default_factory=dict)


@dataclass
class IdeaGroupEntry:
    key: str                          # 예: "my_korean_ideas" (영숫자/_)
    display_name: str = ""            # 그룹 표시명
    trigger_tag: str | None = None    # 적용 국가 태그 (없으면 free)
    free: bool = True
    tradition: IdeaSlot = field(default_factory=IdeaSlot)  # start = {}
    ambition: IdeaSlot = field(default_factory=IdeaSlot)   # bonus = {}
    ideas: list[IdeaSlot] = field(default_factory=list)    # 길이 7 기대


def safe_key(s: str) -> str:
    s = re.sub(r"[^0-9A-Za-z_]+", "_", (s or "").strip()).strip("_")
    return s.lower() or "my_ideas"


# ========== 빌드 ==========

def _format_modifiers(mods: dict[str, float], indent: str) -> str:
    if not mods:
        return ""
    lines = []
    for k, v in mods.items():
        # 정수면 정수로, 아니면 소수
        sv = f"{int(v)}" if float(v).is_integer() else f"{v}"
        lines.append(f"{indent}{k} = {sv}")
    return "\n".join(lines)


def write_idea_block(entry: IdeaGroupEntry) -> str:
    lines = [f"{entry.key} = {{"]
    # start
    lines.append("\tstart = {")
    body = _format_modifiers(entry.tradition.modifiers, "\t\t")
    if body:
        lines.append(body)
    lines.append("\t}")
    # bonus
    lines.append("")
    lines.append("\tbonus = {")
    body = _format_modifiers(entry.ambition.modifiers, "\t\t")
    if body:
        lines.append(body)
    lines.append("\t}")
    # trigger
    lines.append("")
    lines.append("\ttrigger = {")
    if entry.trigger_tag:
        lines.append(f"\t\ttag = {entry.trigger_tag.upper()}")
    else:
        lines.append("\t\talways = yes")
    lines.append("\t}")
    # free
    lines.append(f"\tfree = {'yes' if entry.free else 'no'}")
    # ideas 1..7
    for i, slot in enumerate(entry.ideas[:7], start=1):
        lines.append("")
        lines.append(f"\t{entry.key}_{i} = {{")
        body = _format_modifiers(slot.modifiers, "\t\t")
        if body:
            lines.append(body)
        lines.append("\t}")
    lines.append("}")
    return "\n".join(lines)


def _yml_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def write_idea_locs(entry: IdeaGroupEntry) -> list[str]:
    """l_korean YAML 라인들 (앞에 공백 1개 필수)."""
    out = []
    name = entry.display_name or entry.key
    out.append(f' {entry.key}:0 "{_yml_escape(name)}"')
    if entry.tradition.display_name:
        out.append(f' {entry.key}_start:0 '
                   f'"{_yml_escape(entry.tradition.display_name)}"')
    if entry.ambition.display_name:
        out.append(f' {entry.key}_bonus:0 '
                   f'"{_yml_escape(entry.ambition.display_name)}"')
    for i, slot in enumerate(entry.ideas[:7], start=1):
        if slot.display_name:
            out.append(f' {entry.key}_{i}:0 '
                       f'"{_yml_escape(slot.display_name)}"')
        if slot.description:
            out.append(f' {entry.key}_{i}_desc:0 '
                       f'"{_yml_escape(slot.description)}"')
    return out


def build_ideas(mod_dir: Path, mod_id: str,
                entries: Iterable[IdeaGroupEntry]) -> list[str]:
    entries = list(entries)
    if not entries:
        return []
    # common/ideas
    ideas_dir = mod_dir / "common" / "ideas"
    ideas_dir.mkdir(parents=True, exist_ok=True)
    body = "\n\n".join(write_idea_block(e) for e in entries)
    (ideas_dir / f"{mod_id}_ideas.txt").write_text(
        body + "\n", encoding="utf-8-sig")

    # localisation
    loc_dir = mod_dir / "localisation"
    loc_dir.mkdir(parents=True, exist_ok=True)
    yml_lines = ["l_korean:"]
    for e in entries:
        yml_lines.extend(write_idea_locs(e))
    (loc_dir / f"{mod_id}_ideas_l_korean.yml").write_text(
        "\n".join(yml_lines) + "\n", encoding="utf-8-sig")

    return [e.key for e in entries]


# ========== 모드 불러오기: 간단 파서 ==========

_IDEA_GROUP_RE = re.compile(
    r"(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*\{(?P<body>.*?)\n\}\n",
    re.DOTALL)


def parse_idea_groups(mod_dir: Path) -> list[IdeaGroupEntry]:
    ideas_dir = mod_dir / "common" / "ideas"
    if not ideas_dir.is_dir():
        return []
    entries: list[IdeaGroupEntry] = []
    for txt in sorted(ideas_dir.glob("*.txt")):
        try:
            text = txt.read_text(encoding="utf-8-sig", errors="replace")
        except Exception:
            continue
        # 주석 제거
        text = re.sub(r"#.*", "", text)
        # 단순 top-level 그룹 추출
        depth = 0
        buf = []
        groups = []
        i = 0
        while i < len(text):
            ch = text[i]
            buf.append(ch)
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    groups.append("".join(buf))
                    buf = []
            i += 1
        for g in groups:
            m = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\{(.*)\}\s*$",
                         g, re.DOTALL)
            if not m:
                continue
            key, body = m.group(1), m.group(2)
            entry = IdeaGroupEntry(key=key, display_name=key)
            entry.tradition = IdeaSlot(modifiers=_extract_mods(body, "start"))
            entry.ambition = IdeaSlot(modifiers=_extract_mods(body, "bonus"))
            entry.trigger_tag = _extract_trigger_tag(body)
            entry.free = "free = yes" in body
            # idea_1..7
            ideas = []
            for i in range(1, 8):
                slot_mods = _extract_named_block(body, f"{key}_{i}")
                ideas.append(IdeaSlot(modifiers=slot_mods))
            entry.ideas = ideas
            entries.append(entry)
    return entries


def _extract_named_block(body: str, name: str) -> dict[str, float]:
    m = re.search(rf"\b{re.escape(name)}\s*=\s*\{{(.*?)\}}", body, re.DOTALL)
    if not m:
        return {}
    return _parse_mod_block(m.group(1))


def _extract_mods(body: str, name: str) -> dict[str, float]:
    return _extract_named_block(body, name)


def _extract_trigger_tag(body: str) -> str | None:
    m = re.search(r"trigger\s*=\s*\{(.*?)\}", body, re.DOTALL)
    if not m:
        return None
    tag_m = re.search(r"\btag\s*=\s*([A-Z][A-Z_0-9]*)", m.group(1))
    return tag_m.group(1) if tag_m else None


def _parse_mod_block(s: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for line in s.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(-?\d+(?:\.\d+)?)", line)
        if m:
            out[m.group(1)] = float(m.group(2))
    return out
