import logging
import tkinter as tk

import pytest

import main
from src.ideas import loc_keys_of


@pytest.fixture
def make_app(tmp_path, monkeypatch):
    """창을 띄우지 않는 FlagModderApp 생성기와 메시지 상자 호출 기록"""
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    calls: list[tuple[str, str]] = []

    def _record(kind):
        def _fake(title, *_a, **_k):
            calls.append((kind, title))
            return True
        return _fake

    for kind in ("showinfo", "showwarning", "showerror", "askyesno"):
        monkeypatch.setattr(main.messagebox, kind, _record(kind))

    logger = logging.getLogger("eu4modmaker")
    saved_handlers, saved_level = list(logger.handlers), logger.level
    apps: list[main.FlagModderApp] = []

    def _make() -> main.FlagModderApp:
        try:
            app = main.FlagModderApp()
        except tk.TclError as exc:
            pytest.skip(f"Tk 없음: {exc}")
        app.withdraw()
        apps.append(app)
        return app

    _make.calls = calls
    yield _make
    for app in apps:
        app.destroy()
    logger.handlers[:] = saved_handlers
    logger.setLevel(saved_level)


def _idea_group() -> dict:
    return {
        "key": "rt_ideas",
        "display_name": '왕복 "시험" 아이디어',
        "trigger_tag": "KOR",
        "free": False,
        "tradition": {"display_name": "전통",
                      "modifiers": {"discipline": 0.05, "diplomats": 1}},
        "ambition": {"display_name": "야망",
                     "modifiers": {"global_unrest": -1}},
        "ideas": [{"display_name": f"아이디어 {i}",
                   "description": f"설명 {i}\n둘째 줄",
                   "modifiers": {"land_morale": 0.1 * i,
                                 "yearly_corruption": -0.05}}
                  for i in range(1, 8)],
    }


LOC = [
    {"key": "rt_title", "value": "제목", "language": "korean", "version": 0},
    {"key": "rt_body", "value": '본문 "인용"\n다음 줄', "language": "korean",
     "version": 1},
    {"key": "rt_title", "value": "Title", "language": "english", "version": 0},
]


def _loc_sort(entries):
    return sorted(entries, key=lambda e: (e["language"], e["key"]))


def test_build_then_load_restores_state(tmp_path, make_app, make_image):
    out_root = tmp_path / "out"
    flag_src = make_image("flag.png", size=(60, 40))

    app = make_app()
    app.mod_name_var.set("rt_mod")
    app.version_var.set("1.36.*")
    app.output_dir_var.set(str(out_root))
    app.game_dir_var.set(str(tmp_path / "game"))
    app.user_dir_var.set(str(tmp_path / "user"))
    app.install_var.set(False)
    app.flag_selections["FRA"] = {"source": flag_src, "fit_mode": "cover"}
    app.idea_groups.append(_idea_group())
    app.loc_entries.extend(dict(e) for e in LOC)

    app.on_build()
    assert ("showerror", "빌드 실패") not in make_app.calls
    mod_dir = out_root / "rt_mod"
    assert (mod_dir / "descriptor.mod").is_file()

    loaded = make_app()
    loaded.mod_name_var.set("다른 이름")
    loaded.version_var.set("0.0")
    loaded.load_mod_folder(mod_dir)

    assert [k for k, _t in make_app.calls if k == "showerror"] == []
    assert ("showinfo", "불러오기 완료") in make_app.calls
    assert loaded.mod_name_var.get() == "rt_mod"
    assert loaded.version_var.get() == "1.36.*"
    assert loaded.flag_selections == {
        "FRA": {"source": mod_dir / "gfx" / "flags" / "FRA.tga",
                "fit_mode": "cover"}}
    assert loaded.idea_groups == [_idea_group()]
    assert _loc_sort(loaded.loc_entries) == _loc_sort(LOC)
    assert not {e["key"] for e in loaded.loc_entries} & loc_keys_of("rt_ideas")
    assert loaded.event_selections == {}
    assert loaded.music_entries == []
    assert loaded.loading_entries == []
    assert loaded.icon_selections == {}
    assert loaded.sound_selections == {}
