from src.ideas import (
    IdeaGroupEntry, IdeaSlot, build_ideas, parse_idea_groups, safe_key,
)


def _sample() -> IdeaGroupEntry:
    return IdeaGroupEntry(
        key="kor_ideas",
        display_name='조선 "전통" 아이디어',
        trigger_tag="kor",
        free=False,
        tradition=IdeaSlot(display_name="전통",
                           modifiers={"discipline": 0.05, "diplomats": 1}),
        ambition=IdeaSlot(display_name="야망",
                          modifiers={"global_unrest": -1}),
        ideas=[IdeaSlot(display_name=f"아이디어 {i}",
                        description=f"설명 {i}\n둘째 줄",
                        modifiers={"land_morale": 0.15 * i,
                                   "yearly_corruption": -0.00005})
               for i in range(1, 8)],
    )


def test_round_trip_keeps_all_values(tmp_path):
    src = _sample()
    build_ideas(tmp_path, "m", [src])
    [got] = parse_idea_groups(tmp_path)

    assert got.key == src.key
    assert got.display_name == src.display_name
    assert got.trigger_tag == "KOR"
    assert got.free is False
    assert got.tradition == src.tradition
    assert got.ambition == src.ambition
    assert got.ideas == src.ideas


def test_round_trip_free_without_tag(tmp_path):
    src = IdeaGroupEntry(key="free_ideas", ideas=[IdeaSlot()] * 7)
    build_ideas(tmp_path, "m", [src])
    [got] = parse_idea_groups(tmp_path)
    assert got.trigger_tag is None
    assert got.free is True
    assert got.display_name == "free_ideas"


def test_round_trip_several_groups(tmp_path):
    a = IdeaGroupEntry(key="a_ideas", tradition=IdeaSlot(modifiers={"prestige": 1}))
    b = IdeaGroupEntry(key="b_ideas", ambition=IdeaSlot(modifiers={"merchants": 2}))
    build_ideas(tmp_path, "m", [a, b])
    got = parse_idea_groups(tmp_path)
    assert [g.key for g in got] == ["a_ideas", "b_ideas"]
    assert got[0].tradition.modifiers == {"prestige": 1}
    assert got[1].ambition.modifiers == {"merchants": 2}


def test_parse_without_ideas_dir(tmp_path):
    assert parse_idea_groups(tmp_path) == []


def test_safe_key():
    assert safe_key(" My Korean-Ideas! ") == "my_korean_ideas"
    assert safe_key("") == "my_ideas"
    assert safe_key("###") == "my_ideas"


def test_loc_keys_of_matches_written_keys():
    from src.ideas import IdeaGroupEntry, IdeaSlot, loc_keys_of, write_idea_locs
    entry = IdeaGroupEntry(key="kor_ideas", display_name="조선")
    entry.tradition = IdeaSlot(display_name="전통")
    entry.ambition = IdeaSlot(display_name="야망")
    entry.ideas = [IdeaSlot(display_name=f"아이디어 {i}", description=f"설명 {i}") for i in range(1, 8)]
    written = {line.strip().split(":")[0] for line in write_idea_locs(entry)}
    assert written == loc_keys_of("kor_ideas")

