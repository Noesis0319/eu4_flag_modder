import logging
import struct
import wave

import pytest

from src.sounds import SOUND_KEY_RE, SoundEntry, build_sounds, parse_sound_assets


def _pcm_wav(path):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * 100)
    return path


def _float_wav(path):
    data = struct.pack("<f", 0.0)
    fmt = struct.pack("<HHIIHH", 3, 1, 44100, 44100 * 4, 4, 32)
    body = (b"WAVE" + b"fmt " + struct.pack("<I", len(fmt)) + fmt
            + b"data" + struct.pack("<I", len(data)) + data)
    path.write_bytes(b"RIFF" + struct.pack("<I", len(body)) + body)
    return path


def test_build_and_parse_round_trip(tmp_path):
    src = _pcm_wav(tmp_path / "in.wav")
    mod = tmp_path / "mod"
    got = build_sounds(mod, "m", [SoundEntry("battle_won", src),
                                  SoundEntry("battle_won", src),
                                  SoundEntry("siege_won", src)])
    assert got == ["battle_won", "siege_won"]
    assert (mod / "sound" / "m_battle_won.wav").read_bytes() == src.read_bytes()
    asset = (mod / "sound" / "m.asset").read_text(encoding="utf-8-sig")
    assert 'name = battle_won\n\tfile = "m_battle_won.wav"' in asset
    assert parse_sound_assets(mod) == [
        ("battle_won", mod / "sound" / "m_battle_won.wav"),
        ("siege_won", mod / "sound" / "m_siege_won.wav")]


def test_empty_entries(tmp_path):
    assert build_sounds(tmp_path, "m", []) == []
    assert not (tmp_path / "sound").exists()


@pytest.mark.parametrize("make", [
    lambda p: p.write_bytes(b"not a wav at all"),
    lambda p: p.write_bytes(b""),
    _float_wav,
], ids=["garbage", "empty", "ieee_float"])
def test_non_pcm_wav_rejected(tmp_path, make):
    src = tmp_path / "bad_sound.wav"
    make(src)
    with pytest.raises(ValueError, match="bad_sound.wav"):
        build_sounds(tmp_path / "mod", "m", [SoundEntry("battle_won", src)])
    assert not (tmp_path / "mod" / "sound" / "m_battle_won.wav").exists()


def test_missing_source(tmp_path):
    with pytest.raises(RuntimeError):
        build_sounds(tmp_path, "m", [SoundEntry("battle_won", tmp_path / "none.wav")])


@pytest.mark.parametrize("key", ["a-b", "a.b", "효과음", "a b", ""])
def test_invalid_key_rejected(tmp_path, key):
    assert not SOUND_KEY_RE.fullmatch(key)
    src = _pcm_wav(tmp_path / "in.wav")
    with pytest.raises(ValueError):
        build_sounds(tmp_path / "mod", "m", [SoundEntry(key, src)])


def test_parse_skips_missing_target_and_unreadable(tmp_path, caplog):
    sd = tmp_path / "sound"
    (sd / "broken.asset").mkdir(parents=True)
    _pcm_wav(sd / "x.wav")
    (sd / "m.asset").write_text(
        'sound = {\n\tname = here\n\tfile = "x.wav"\n}\n'
        'sound = {\n\tname = gone\n\tfile = "missing.wav"\n}\n'
        "sound = { name = nofile }\n",
        encoding="utf-8-sig")
    with caplog.at_level(logging.WARNING, logger="eu4modmaker"):
        got = parse_sound_assets(tmp_path)
    assert got == [("here", sd / "x.wav")]
    assert "broken.asset" in caplog.text


def test_parse_without_sound_dir(tmp_path):
    assert parse_sound_assets(tmp_path) == []
