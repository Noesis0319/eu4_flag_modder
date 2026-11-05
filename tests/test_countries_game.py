import pytest

from src.countries import COUNTRIES
from src.mod_builder import EU4_GAME_DIR_DEFAULT

# 게임 본체의 태그 목록
TAGS_FILE = EU4_GAME_DIR_DEFAULT / "common" / "country_tags" / "00_countries.txt"


def all_rows():
    return [row for rows in COUNTRIES.values() for row in rows]


def test_tags_are_three_uppercase_letters_without_duplicates():
    tags = [row[0] for row in all_rows()]
    bad = [t for t in tags if not (len(t) == 3 and t.isupper() and t.isalpha())]
    assert bad == []
    assert len(tags) == len(set(tags))


@pytest.mark.skipif(not TAGS_FILE.is_file(), reason="EU4 본체가 이 PC 에 없다")
def test_every_tag_exists_in_game():
    game = set()
    for line in TAGS_FILE.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        head = line.split("#")[0]
        if "=" in head:
            game.add(head.split("=")[0].strip())
    assert [row for row in all_rows() if row[0] not in game] == []
