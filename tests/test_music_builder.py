import logging

import pytest

from src.music_builder import (
    CHANCE_PRESETS, MusicEntry, build_music, parse_music_assets,
    parse_song_presets, safe_track_name,
)


@pytest.fixture
def ogg(tmp_path):
    path = tmp_path / "in.ogg"
    path.write_bytes(b"OggS fake")
    return path


@pytest.mark.parametrize("raw, expected", [
    ("My Song!", "My_Song"),
    ("  __a--b__ ", "a_b"),
    ("한글", "track"),
    ("", "track"),
])
def test_safe_track_name(raw, expected):
    assert safe_track_name(raw) == expected


def test_build_and_parse_round_trip(tmp_path, ogg):
    mod = tmp_path / "mod"
    presets = list(CHANCE_PRESETS)
    entries = [MusicEntry(f"t{i}", ogg, p) for i, p in enumerate(presets)]
    names = build_music(mod, "m", entries)
    assert names == [f"m_t{i}" for i in range(len(presets))]
    assert parse_music_assets(mod) == [
        (n, mod / "music" / f"{n}.ogg") for n in names]
    assert parse_song_presets(mod) == dict(zip(names, presets))


def test_name_collision_and_unknown_preset(tmp_path, ogg):
    mod = tmp_path / "mod"
    names = build_music(mod, "m", [MusicEntry("a", ogg, "nope"),
                                   MusicEntry("a", ogg),
                                   MusicEntry("a", ogg)])
    assert names == ["m_a", "m_a_2", "m_a_3"]
    assert set(parse_song_presets(mod).values()) == {"default"}


def test_empty_entries(tmp_path):
    assert build_music(tmp_path, "m", []) == []
    assert not (tmp_path / "music").exists()


def test_missing_source(tmp_path):
    with pytest.raises(RuntimeError):
        build_music(tmp_path, "m", [MusicEntry("a", tmp_path / "none.ogg")])


def test_parse_skips_broken_files(tmp_path, caplog):
    md = tmp_path / "music"
    (md / "broken.asset").mkdir(parents=True)
    (md / "broken_songs.txt").mkdir()
    (md / "x.ogg").write_bytes(b"OggS")
    (md / "m.asset").write_text(
        'music = {\n\tname = "here"\n\tfile = "x.ogg"\n}\n'
        'music = {\n\tname = "gone"\n\tfile = "missing.ogg"\n}\n',
        encoding="utf-8-sig")
    (md / "m_songs.txt").write_text(
        'song = {\n\tname = "here"\n\tchance = {\n'
        "\t\tmodifier = { factor = 3 }\n\t}\n}\n"
        'song = {\n\tname = "odd"\n\tchance = {\n'
        "\t\tmodifier = { factor = 7 }\n\t}\n}\n",
        encoding="utf-8-sig")
    with caplog.at_level(logging.WARNING, logger="eu4modmaker"):
        assets = parse_music_assets(tmp_path)
        presets = parse_song_presets(tmp_path)
    assert assets == [("here", md / "x.ogg")]
    assert presets == {"here": "often"}
    assert "broken.asset" in caplog.text
    assert "broken_songs.txt" in caplog.text


def test_parse_without_music_dir(tmp_path):
    assert parse_music_assets(tmp_path) == []
    assert parse_song_presets(tmp_path) == {}
