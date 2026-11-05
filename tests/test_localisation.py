import logging

import pytest

from src.localisation import (
    KEY_RE, LocEntry, build_localisation, parse_localisation_dir,
    parse_localisation_file,
)


def test_round_trip_escapes_and_versions(tmp_path):
    entries = [
        LocEntry("evt.0.t", '그가 "안녕" 이라 했다'),
        LocEntry("evt.0.d", "첫 줄\n둘째 줄", version=1),
        LocEntry("evt.0.a", "Hello", language="english"),
    ]
    files = build_localisation(tmp_path, "m", entries)
    assert sorted(files) == ["m_l_english.yml", "m_l_korean.yml"]

    got = parse_localisation_dir(tmp_path)
    by_key = {e.key: e for e in got}
    assert by_key["evt.0.t"].value == '그가 "안녕" 이라 했다'
    assert by_key["evt.0.d"].value == "첫 줄\n둘째 줄"
    assert by_key["evt.0.d"].version == 1
    assert by_key["evt.0.a"].language == "english"
    assert by_key["evt.0.t"].language == "korean"


@pytest.mark.parametrize("value", [
    "C:\\new\\x",
    "a\\nb",
    'q"\\"z',
    "끝이 백슬래시\\",
])
def test_round_trip_keeps_backslashes(tmp_path, value):
    build_localisation(tmp_path, "m", [LocEntry("k", value)])
    assert [e.value for e in parse_localisation_dir(tmp_path)] == [value]


def test_written_file_format(tmp_path):
    build_localisation(tmp_path, "m", [LocEntry("k", "a\nb")])
    path = tmp_path / "localisation" / "m_l_korean.yml"
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")
    assert path.read_text(encoding="utf-8-sig") == 'l_korean:\n k:0 "a\\nb"\n'


def test_duplicate_key_last_wins(tmp_path):
    build_localisation(tmp_path, "m", [LocEntry("k", "first"), LocEntry("k", "second")])
    assert [(e.key, e.value) for e in parse_localisation_dir(tmp_path)] == [("k", "second")]


def test_empty_entries_write_nothing(tmp_path):
    assert build_localisation(tmp_path, "m", []) == []
    assert not (tmp_path / "localisation").exists()


@pytest.mark.parametrize("key", ["my_event.0.t", "A-b_9", "x"])
def test_key_re_accepts(key):
    assert KEY_RE.fullmatch(key)


@pytest.mark.parametrize("key", ["한글키", "a b", "a:b", "", 'a"b'])
def test_invalid_key_rejected(tmp_path, key):
    assert not KEY_RE.fullmatch(key)
    with pytest.raises(ValueError):
        build_localisation(tmp_path, "m", [LocEntry(key, "v")])


def test_parse_skips_broken_lines(tmp_path):
    path = tmp_path / "x_l_french.yml"
    path.write_text(
        "l_french:\n"
        "# 주석\n"
        ' ok:0 "bon"\n'
        ' unterminated:0 "oups\n'
        ' noversion "x"\n'
        'noindent:0 "x"\n'
        ' bad"quote:0 "x"\n'
        ' inner:0 "a"b"\n'
        "\n"
        ' ok2:3 "deux"  \n',
        encoding="utf-8-sig")
    lang, entries = parse_localisation_file(path)
    assert lang == "french"
    assert [(e.key, e.value, e.version, e.language) for e in entries] == [
        ("ok", "bon", 0, "french"), ("ok2", "deux", 3, "french")]


def test_parse_dir_missing(tmp_path):
    assert parse_localisation_dir(tmp_path) == []


def test_parse_dir_skips_unreadable_with_warning(tmp_path, caplog):
    loc = tmp_path / "localisation"
    (loc / "broken.yml").mkdir(parents=True)
    (loc / "good.yml").write_text('l_korean:\n k:0 "v"\n', encoding="utf-8-sig")
    with caplog.at_level(logging.WARNING, logger="eu4modmaker"):
        got = parse_localisation_dir(tmp_path)
    assert [e.key for e in got] == ["k"]
    assert "broken.yml" in caplog.text
