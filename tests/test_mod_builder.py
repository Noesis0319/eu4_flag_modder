import pytest

from src.localisation import LocEntry
from src.mod_builder import FlagEntry, build_mod, replace_dir, safe_mod_id


def _loc():
    return [LocEntry("k", "v")]


@pytest.mark.parametrize("raw, expected", [
    ("내 모드 v1.0", "내_모드_v1_0"),
    ("a-b_c", "a-b_c"),
    ("   ", "custom_mod"),
])
def test_safe_mod_id(raw, expected):
    assert safe_mod_id(raw) == expected


def test_descriptor_content(tmp_path):
    out = tmp_path / "out"
    result = build_mod('My "Mod"', loc_entries=_loc(), output_root=out,
                       install_to_eu4=False, supported_version="1.36.*")
    assert result["mod_id"] == "My_Mod_"
    mod_dir = out / "My_Mod_"
    assert result["mod_dir"] == mod_dir
    descriptor = mod_dir / "descriptor.mod"
    assert descriptor.read_bytes().startswith(b"\xef\xbb\xbf")
    assert descriptor.read_text(encoding="utf-8-sig") == (
        "name=\"My 'Mod'\"\n"
        'supported_version="1.36.*"\n'
        "tags={\n"
        '\t"Graphics"\n\t"Flags"\n\t"Events"\n\t"Sound"\n'
        "}\n")
    assert result["installed_mod_file"] is None
    assert sorted(p.name for p in out.iterdir()) == ["My_Mod_"]


def test_thumbnail_line(tmp_path, make_image):
    out = tmp_path / "out"
    build_mod("m", loc_entries=_loc(), output_root=out, install_to_eu4=False,
              thumbnail=make_image("thumb.png"))
    text = (out / "m" / "descriptor.mod").read_text(encoding="utf-8-sig")
    assert text.endswith('picture="thumbnail.png"\n')
    assert (out / "m" / "thumbnail.png").is_file()


def test_no_assets_rejected(tmp_path):
    with pytest.raises(ValueError):
        build_mod("m", output_root=tmp_path, install_to_eu4=False)


def test_rebuild_replaces_old_and_clears_staging(tmp_path, make_image):
    out = tmp_path / "out"
    old = out / "m"
    old.mkdir(parents=True)
    (old / "stale.txt").write_text("x")
    (out / "m.building").mkdir()
    (out / "m.building" / "junk.txt").write_text("x")
    (out / "m.old").mkdir()

    result = build_mod("m", flag_entries=[FlagEntry("kor", make_image("f.png"))],
                       output_root=out, install_to_eu4=False)
    assert result["converted_flags"] == ["KOR"]
    assert (old / "gfx" / "flags" / "KOR.tga").is_file()
    assert not (old / "stale.txt").exists()
    assert sorted(p.name for p in out.iterdir()) == ["m"]


def test_failed_build_keeps_existing_mod(tmp_path):
    out = tmp_path / "out"
    build_mod("m", loc_entries=_loc(), output_root=out, install_to_eu4=False)
    before = (out / "m" / "localisation" / "m_l_korean.yml").read_bytes()
    with pytest.raises(ValueError):
        build_mod("m", loc_entries=[LocEntry("bad key", "v")], output_root=out,
                  install_to_eu4=False)
    assert (out / "m" / "localisation" / "m_l_korean.yml").read_bytes() == before


def test_replace_dir(tmp_path):
    new, dest = tmp_path / "new", tmp_path / "dest"
    new.mkdir()
    (new / "a.txt").write_text("new")
    dest.mkdir()
    (dest / "b.txt").write_text("old")
    replace_dir(new, dest)
    assert [p.name for p in dest.iterdir()] == ["a.txt"]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["dest"]


def test_replace_dir_without_existing_dest(tmp_path):
    new, dest = tmp_path / "new", tmp_path / "dest"
    new.mkdir()
    replace_dir(new, dest)
    assert dest.is_dir() and not new.exists()


def test_install_copies_to_user_mod_dir(tmp_path):
    out, user = tmp_path / "out", tmp_path / "user"
    result = build_mod("m", loc_entries=_loc(), output_root=out,
                       install_to_eu4=True, eu4_user_dir=user)
    target = user / "mod" / "m"
    assert result["installed_mod_dir"] == target
    assert (target / "descriptor.mod").is_file()
    assert (out / "m" / "descriptor.mod").is_file()
    assert sorted(p.name for p in (user / "mod").iterdir()) == ["m", "m.mod"]
    text = (user / "mod" / "m.mod").read_text(encoding="utf-8-sig")
    assert f'path="{target.as_posix()}"' in text


def test_install_skips_copy_when_output_is_install_dir(tmp_path):
    user = tmp_path / "user"
    out = user / "mod"
    result = build_mod("m", loc_entries=_loc(), output_root=out,
                       install_to_eu4=True, eu4_user_dir=user)
    assert result["installed_mod_dir"] == out / "m"
    assert (out / "m" / "localisation" / "m_l_korean.yml").is_file()
    assert sorted(p.name for p in out.iterdir()) == ["m", "m.mod"]
