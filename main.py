"""EU4 자산 교체 모드 제작기 (한글 GUI).

- 국기 교체 (gfx/flags/<TAG>.tga, 128x128)
- 이벤트 픽처 교체 (gfx/event_pictures/<mod_id>/<KEY>.dds, 512x132)

실행: python main.py   (배포: PyInstaller 단일 exe)
"""

from __future__ import annotations

import json
import os
import re
import sys
import traceback
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

# PyInstaller 한 파일 모드에서도 src 패키지가 임포트되도록
if getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(sys._MEIPASS)))  # type: ignore[attr-defined]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.countries import COUNTRIES
from src.event_pictures import grouped as event_groups, EVENT_PICTURE_SIZE
from src.image_processor import (
    preview_image,
    preview_event_picture,
)
from src.mod_builder import (
    FlagEntry,
    EventPictureEntry,
    build_mod,
    EU4_USER_DIR_DEFAULT,
)
from src.music_builder import (
    MusicEntry,
    CHANCE_PRESETS,
    LABEL_BY_PRESET,
    PRESET_BY_LABEL,
    ffmpeg_path,
    safe_track_name,
    parse_music_assets,
    parse_song_presets,
)
from src.loading_screens import (
    LoadingScreenEntry, LOADING_SCREEN_COUNT, LOADING_SCREEN_SIZE,
)
from src.sounds import SoundEntry, SOUND_GROUPS, parse_sound_assets
from src.ui_icons import IconEntry, ICON_PRESETS, scan_icons_in_mod
from src.ideas import (
    IdeaGroupEntry, IdeaSlot, MODIFIER_CATALOG, safe_key as safe_idea_key,
    parse_idea_groups,
)
from src.localisation import (
    LocEntry, SUPPORTED_LANGUAGES, parse_localisation_dir,
)


# ----------------------------- 환경/설정 -----------------------------

APP_NAME = "EU4FlagModder"

DEFAULT_GAME_DIR = Path(
    "C:/Program Files (x86)/Steam/steamapps/common/Europa Universalis IV"
)

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output"


def settings_path() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    p = Path(base) / APP_NAME / "settings.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def load_settings() -> dict:
    p = settings_path()
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_settings(data: dict) -> None:
    try:
        settings_path().write_text(json.dumps(data, ensure_ascii=False, indent=2),
                                   encoding="utf-8")
    except Exception:
        pass


# ----------------------------- 메인 앱 -----------------------------

class FlagModderApp(tk.Tk):
    FLAG_PREVIEW_PX = 192
    EVENT_PREVIEW_W = 384   # 512 * 0.75
    EVENT_PREVIEW_H = 99    # 132 * 0.75

    def __init__(self):
        super().__init__()
        self.title("EU4 모드 제작기 — 국기 / 이벤트 / 음악 / 사운드 / 아이디어 등")
        self.geometry("1200x780")
        self.minsize(1080, 680)

        self.settings = load_settings()

        # 경로 변수
        self.game_dir_var = tk.StringVar(
            value=self.settings.get("game_dir", str(DEFAULT_GAME_DIR)))
        self.user_dir_var = tk.StringVar(
            value=self.settings.get("user_dir", str(EU4_USER_DIR_DEFAULT)))
        self.output_dir_var = tk.StringVar(
            value=self.settings.get("output_dir", str(DEFAULT_OUTPUT_DIR)))
        self.mod_name_var = tk.StringVar(
            value=self.settings.get("mod_name", "내 EU4 모드"))
        self.version_var = tk.StringVar(
            value=self.settings.get("version", "1.37.*"))
        self.install_var = tk.BooleanVar(
            value=self.settings.get("install", True))

        # 상태
        self.flag_selections: dict[str, dict] = {}
        self.event_selections: dict[str, dict] = {}
        self.music_entries: list[dict] = []
        # 신규 자산들
        self.loading_entries: list[dict] = []   # [{index, source, fit_mode}]
        self.icon_selections: dict[str, dict] = {}  # rel_path -> {source, fit_mode}
        self.sound_selections: dict[str, dict] = {}  # sound_key -> {source}
        # 아이디어: [IdeaGroupEntry-like dict]
        self.idea_groups: list[dict] = []
        # 로컬라이제이션: [{language, key, value, version}]
        self.loc_entries: list[dict] = []

        self.current_tag: str | None = None
        self.current_event_key: str | None = None
        self.current_music_iid: str | None = None
        self.current_icon_path: str | None = None
        self.current_sound_key: str | None = None
        self.current_loading_iid: str | None = None
        self.current_idea_idx: int | None = None
        self.current_idea_slot: str | None = None  # 'tradition'|'ambition'|'idea_1'..7
        self.current_loc_iid: str | None = None

        self._preview_imgs: dict[str, ImageTk.PhotoImage] = {}

        self._build_ui()
        self._populate_country_tree()
        self._populate_event_tree()
        self._populate_icons_tree()
        self._populate_sounds_tree()

    # ----- UI 빌드 -----
    def _build_ui(self):
        # 상단 옵션
        top = ttk.Frame(self, padding=8)
        top.pack(fill="x")

        row1 = ttk.Frame(top)
        row1.pack(fill="x")
        ttk.Label(row1, text="모드 이름:").pack(side="left")
        ttk.Entry(row1, textvariable=self.mod_name_var, width=28).pack(
            side="left", padx=(4, 12))
        ttk.Label(row1, text="EU4 버전:").pack(side="left")
        ttk.Entry(row1, textvariable=self.version_var, width=10).pack(
            side="left", padx=(4, 12))
        ttk.Checkbutton(row1, text="EU4 mod 폴더에 자동 설치",
                        variable=self.install_var).pack(side="left", padx=(0, 12))
        ttk.Button(row1, text="모드 생성", command=self.on_build).pack(side="right")
        ttk.Button(row1, text="모드 불러오기…",
                   command=self.on_load_mod).pack(side="right", padx=(0, 8))
        ttk.Button(row1, text="전체 초기화",
                   command=self.on_clear_all).pack(side="right", padx=(0, 8))

        row2 = ttk.Frame(top)
        row2.pack(fill="x", pady=(6, 0))
        ttk.Label(row2, text="EU4 게임 폴더:", width=14).pack(side="left")
        ttk.Entry(row2, textvariable=self.game_dir_var).pack(
            side="left", fill="x", expand=True)
        ttk.Button(row2, text="…", width=3,
                   command=lambda: self._pick_dir(self.game_dir_var)).pack(
            side="left", padx=(4, 0))

        row3 = ttk.Frame(top)
        row3.pack(fill="x", pady=(2, 0))
        ttk.Label(row3, text="EU4 사용자 폴더:", width=14).pack(side="left")
        ttk.Entry(row3, textvariable=self.user_dir_var).pack(
            side="left", fill="x", expand=True)
        ttk.Button(row3, text="…", width=3,
                   command=lambda: self._pick_dir(self.user_dir_var)).pack(
            side="left", padx=(4, 0))

        row4 = ttk.Frame(top)
        row4.pack(fill="x", pady=(2, 0))
        ttk.Label(row4, text="모드 출력 폴더:", width=14).pack(side="left")
        ttk.Entry(row4, textvariable=self.output_dir_var).pack(
            side="left", fill="x", expand=True)
        ttk.Button(row4, text="…", width=3,
                   command=lambda: self._pick_dir(self.output_dir_var)).pack(
            side="left", padx=(4, 0))

        # Notebook (탭)
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=8, pady=(8, 0))

        self.flags_tab = ttk.Frame(self.nb)
        self.events_tab = ttk.Frame(self.nb)
        self.loading_tab = ttk.Frame(self.nb)
        self.icons_tab = ttk.Frame(self.nb)
        self.music_tab = ttk.Frame(self.nb)
        self.sounds_tab = ttk.Frame(self.nb)
        self.ideas_tab = ttk.Frame(self.nb)
        self.loc_tab = ttk.Frame(self.nb)
        self.nb.add(self.flags_tab, text="국기")
        self.nb.add(self.events_tab, text="이벤트 픽처")
        self.nb.add(self.loading_tab, text="로딩 화면")
        self.nb.add(self.icons_tab, text="UI 아이콘")
        self.nb.add(self.music_tab, text="배경 음악")
        self.nb.add(self.sounds_tab, text="효과음")
        self.nb.add(self.ideas_tab, text="국가 아이디어")
        self.nb.add(self.loc_tab, text="로컬라이제이션")

        self._build_flags_tab(self.flags_tab)
        self._build_events_tab(self.events_tab)
        self._build_loading_tab(self.loading_tab)
        self._build_icons_tab(self.icons_tab)
        self._build_music_tab(self.music_tab)
        self._build_sounds_tab(self.sounds_tab)
        self._build_ideas_tab(self.ideas_tab)
        self._build_loc_tab(self.loc_tab)

        # 하단 로그
        self.log = tk.Text(self, height=6, wrap="word")
        self.log.pack(fill="x", padx=8, pady=8)
        self.log.insert("end", "준비됨. 좌측에서 항목을 고르고 이미지를 지정한 뒤"
                               " '모드 생성' 을 누르세요.\n")
        self.log.configure(state="disabled")

    # ----- 국기 탭 -----
    def _build_flags_tab(self, parent: ttk.Frame):
        body = ttk.Panedwindow(parent, orient="horizontal")
        body.pack(fill="both", expand=True, padx=4, pady=4)

        left = ttk.Frame(body)
        body.add(left, weight=1)
        ttk.Label(left, text="국가 선택").pack(anchor="w")

        tree_box = ttk.Frame(left)
        tree_box.pack(fill="both", expand=True)
        self.country_tree = ttk.Treeview(
            tree_box, columns=("status",), show="tree headings")
        self.country_tree.heading("#0", text="국가")
        self.country_tree.heading("status", text="상태")
        self.country_tree.column("#0", width=260)
        self.country_tree.column("status", width=70, anchor="center")
        vsb = ttk.Scrollbar(tree_box, orient="vertical",
                            command=self.country_tree.yview)
        self.country_tree.configure(yscrollcommand=vsb.set)
        self.country_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.country_tree.bind("<<TreeviewSelect>>", self.on_country_select)

        right = ttk.Frame(body)
        body.add(right, weight=2)

        info = ttk.Frame(right)
        info.pack(fill="x", pady=(0, 8))
        self.flag_title_lbl = ttk.Label(info, text="좌측에서 국가를 선택하세요.",
                                        font=("맑은 고딕", 12, "bold"))
        self.flag_title_lbl.pack(anchor="w")
        self.flag_tag_lbl = ttk.Label(info, text="")
        self.flag_tag_lbl.pack(anchor="w")

        preview_row = ttk.Frame(right)
        preview_row.pack(fill="x", pady=8)
        self.flag_orig_box = self._make_preview_box(
            preview_row, "원본 (EU4)", self.FLAG_PREVIEW_PX, self.FLAG_PREVIEW_PX)
        self.flag_orig_box.pack(side="left", padx=(0, 16))
        self.flag_new_box = self._make_preview_box(
            preview_row, "새 국기 (변환 후)",
            self.FLAG_PREVIEW_PX, self.FLAG_PREVIEW_PX)
        self.flag_new_box.pack(side="left")

        ctrl = ttk.Frame(right)
        ctrl.pack(fill="x", pady=8)
        ttk.Button(ctrl, text="이미지 선택…",
                   command=self.on_pick_flag_image).pack(side="left")
        ttk.Button(ctrl, text="제거",
                   command=self.on_remove_flag).pack(side="left", padx=8)
        ttk.Label(ctrl, text="맞춤:").pack(side="left", padx=(16, 4))
        self.flag_fit_var = tk.StringVar(value="cover")
        fit_box = ttk.Combobox(
            ctrl, textvariable=self.flag_fit_var, width=10, state="readonly",
            values=("cover", "contain", "stretch"))
        fit_box.pack(side="left")
        fit_box.bind("<<ComboboxSelected>>",
                     lambda e: self._refresh_flag_new_preview())

        self.flag_path_lbl = ttk.Label(right, text="선택된 이미지: -",
                                       foreground="#555")
        self.flag_path_lbl.pack(anchor="w", pady=(8, 0))

    # ----- 이벤트 픽처 탭 -----
    def _build_events_tab(self, parent: ttk.Frame):
        body = ttk.Panedwindow(parent, orient="horizontal")
        body.pack(fill="both", expand=True, padx=4, pady=4)

        left = ttk.Frame(body)
        body.add(left, weight=1)
        ttk.Label(left, text="이벤트 픽처 선택").pack(anchor="w")

        tree_box = ttk.Frame(left)
        tree_box.pack(fill="both", expand=True)
        self.event_tree = ttk.Treeview(
            tree_box, columns=("status",), show="tree headings")
        self.event_tree.heading("#0", text="이벤트 픽처")
        self.event_tree.heading("status", text="상태")
        self.event_tree.column("#0", width=340)
        self.event_tree.column("status", width=70, anchor="center")
        vsb = ttk.Scrollbar(tree_box, orient="vertical",
                            command=self.event_tree.yview)
        self.event_tree.configure(yscrollcommand=vsb.set)
        self.event_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.event_tree.bind("<<TreeviewSelect>>", self.on_event_select)

        right = ttk.Frame(body)
        body.add(right, weight=2)

        info = ttk.Frame(right)
        info.pack(fill="x", pady=(0, 8))
        self.event_title_lbl = ttk.Label(
            info, text="좌측에서 이벤트 픽처를 선택하세요.",
            font=("맑은 고딕", 12, "bold"))
        self.event_title_lbl.pack(anchor="w")
        self.event_key_lbl = ttk.Label(info, text="")
        self.event_key_lbl.pack(anchor="w")

        preview_col = ttk.Frame(right)
        preview_col.pack(fill="x", pady=8)
        self.event_orig_box = self._make_preview_box(
            preview_col, f"원본 (EU4) {EVENT_PICTURE_SIZE[0]}×"
                         f"{EVENT_PICTURE_SIZE[1]}",
            self.EVENT_PREVIEW_W, self.EVENT_PREVIEW_H)
        self.event_orig_box.pack(anchor="w", pady=(0, 8))
        self.event_new_box = self._make_preview_box(
            preview_col, "새 이벤트 픽처 (변환 후)",
            self.EVENT_PREVIEW_W, self.EVENT_PREVIEW_H)
        self.event_new_box.pack(anchor="w")

        ctrl = ttk.Frame(right)
        ctrl.pack(fill="x", pady=8)
        ttk.Button(ctrl, text="이미지 선택…",
                   command=self.on_pick_event_image).pack(side="left")
        ttk.Button(ctrl, text="제거",
                   command=self.on_remove_event).pack(side="left", padx=8)
        ttk.Label(ctrl, text="맞춤:").pack(side="left", padx=(16, 4))
        self.event_fit_var = tk.StringVar(value="cover")
        fit_box = ttk.Combobox(
            ctrl, textvariable=self.event_fit_var, width=10, state="readonly",
            values=("cover", "contain", "stretch"))
        fit_box.pack(side="left")
        fit_box.bind("<<ComboboxSelected>>",
                     lambda e: self._refresh_event_new_preview())

        self.event_path_lbl = ttk.Label(right, text="선택된 이미지: -",
                                        foreground="#555")
        self.event_path_lbl.pack(anchor="w", pady=(8, 0))

    # ----- 음악 탭 -----
    def _build_music_tab(self, parent: ttk.Frame):
        body = ttk.Frame(parent)
        body.pack(fill="both", expand=True, padx=4, pady=4)

        # 상단: 트랙 리스트
        top = ttk.LabelFrame(body, text="음악 트랙 목록", padding=6)
        top.pack(fill="both", expand=True)

        list_box = ttk.Frame(top)
        list_box.pack(fill="both", expand=True)
        self.music_tree = ttk.Treeview(
            list_box, columns=("preset", "source"),
            show="tree headings", height=8)
        self.music_tree.heading("#0", text="트랙명")
        self.music_tree.heading("preset", text="재생 조건")
        self.music_tree.heading("source", text="원본 파일")
        self.music_tree.column("#0", width=200)
        self.music_tree.column("preset", width=180, anchor="center")
        self.music_tree.column("source", width=460)
        vsb = ttk.Scrollbar(list_box, orient="vertical",
                            command=self.music_tree.yview)
        self.music_tree.configure(yscrollcommand=vsb.set)
        self.music_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.music_tree.bind("<<TreeviewSelect>>", self.on_music_select)

        btn_row = ttk.Frame(top)
        btn_row.pack(fill="x", pady=(6, 0))
        ttk.Button(btn_row, text="+ 트랙 추가",
                   command=self.on_music_add).pack(side="left")
        ttk.Button(btn_row, text="선택 삭제",
                   command=self.on_music_remove).pack(side="left", padx=8)
        ttk.Button(btn_row, text="위로", width=6,
                   command=lambda: self._music_move(-1)).pack(side="left",
                                                              padx=(8, 0))
        ttk.Button(btn_row, text="아래로", width=6,
                   command=lambda: self._music_move(1)).pack(side="left")
        ff = ffmpeg_path()
        ff_text = (f"ffmpeg 사용 가능 (mp3/wav/m4a 자동 변환)"
                   if ff else
                   "ffmpeg 없음 → .ogg 파일만 사용 가능")
        ttk.Label(btn_row, text=ff_text,
                  foreground=("#2a7" if ff else "#a40")).pack(side="right")

        # 하단: 선택 항목 편집
        edit = ttk.LabelFrame(body, text="선택 항목 편집", padding=8)
        edit.pack(fill="x", pady=(8, 0))

        r1 = ttk.Frame(edit); r1.pack(fill="x", pady=2)
        ttk.Label(r1, text="트랙명:", width=10).pack(side="left")
        self.music_name_var = tk.StringVar()
        ttk.Entry(r1, textvariable=self.music_name_var, width=30).pack(
            side="left")
        ttk.Label(r1, text="(영숫자/_ 만 사용. 자동 정제됨)",
                  foreground="#777").pack(side="left", padx=(8, 0))

        r2 = ttk.Frame(edit); r2.pack(fill="x", pady=2)
        ttk.Label(r2, text="원본 파일:", width=10).pack(side="left")
        self.music_path_var = tk.StringVar()
        ttk.Entry(r2, textvariable=self.music_path_var).pack(
            side="left", fill="x", expand=True)
        ttk.Button(r2, text="…", width=3,
                   command=self._pick_music_file).pack(side="left", padx=(4, 0))

        r3 = ttk.Frame(edit); r3.pack(fill="x", pady=2)
        ttk.Label(r3, text="재생 조건:", width=10).pack(side="left")
        self.music_preset_var = tk.StringVar(
            value=LABEL_BY_PRESET["default"])
        ttk.Combobox(
            r3, textvariable=self.music_preset_var, state="readonly", width=30,
            values=list(PRESET_BY_LABEL.keys()),
        ).pack(side="left")
        ttk.Button(r3, text="변경 적용",
                   command=self.on_music_apply).pack(side="left", padx=(12, 0))

    # ----- 로딩 화면 탭 -----
    def _build_loading_tab(self, parent: ttk.Frame):
        body = ttk.Frame(parent); body.pack(fill="both", expand=True, padx=4, pady=4)

        top = ttk.LabelFrame(body, text=f"로딩 화면 (load_N.dds, "
                                        f"{LOADING_SCREEN_SIZE[0]}×"
                                        f"{LOADING_SCREEN_SIZE[1]})", padding=6)
        top.pack(fill="both", expand=True)

        lbox = ttk.Frame(top); lbox.pack(fill="both", expand=True)
        self.loading_tree = ttk.Treeview(
            lbox, columns=("fit", "source"), show="tree headings", height=8)
        self.loading_tree.heading("#0", text="인덱스 (load_N)")
        self.loading_tree.heading("fit", text="맞춤")
        self.loading_tree.heading("source", text="원본 파일")
        self.loading_tree.column("#0", width=120, anchor="center")
        self.loading_tree.column("fit", width=80, anchor="center")
        self.loading_tree.column("source", width=640)
        vsb = ttk.Scrollbar(lbox, orient="vertical",
                            command=self.loading_tree.yview)
        self.loading_tree.configure(yscrollcommand=vsb.set)
        self.loading_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.loading_tree.bind("<<TreeviewSelect>>", self.on_loading_select)

        bar = ttk.Frame(top); bar.pack(fill="x", pady=(6, 0))
        ttk.Button(bar, text="+ 추가", command=self.on_loading_add).pack(
            side="left")
        ttk.Button(bar, text="선택 삭제",
                   command=self.on_loading_remove).pack(side="left", padx=8)
        ttk.Label(bar,
                  text=f"인덱스 0~{LOADING_SCREEN_COUNT - 1} 사이가 안전 "
                       "(게임 본체가 그 범위만 사용)",
                  foreground="#777").pack(side="left", padx=(12, 0))

        edit = ttk.LabelFrame(body, text="편집", padding=8)
        edit.pack(fill="x", pady=(8, 0))

        r1 = ttk.Frame(edit); r1.pack(fill="x", pady=2)
        ttk.Label(r1, text="인덱스:", width=10).pack(side="left")
        self.loading_index_var = tk.StringVar(value="0")
        ttk.Spinbox(r1, from_=0, to=99, textvariable=self.loading_index_var,
                    width=6).pack(side="left")
        ttk.Label(r1, text="맞춤:", width=8).pack(side="left", padx=(16, 0))
        self.loading_fit_var = tk.StringVar(value="cover")
        ttk.Combobox(r1, textvariable=self.loading_fit_var, width=10,
                     state="readonly",
                     values=("cover", "contain", "stretch")).pack(side="left")

        r2 = ttk.Frame(edit); r2.pack(fill="x", pady=2)
        ttk.Label(r2, text="이미지:", width=10).pack(side="left")
        self.loading_path_var = tk.StringVar()
        ttk.Entry(r2, textvariable=self.loading_path_var).pack(
            side="left", fill="x", expand=True)
        ttk.Button(r2, text="…", width=3,
                   command=self._pick_loading_image).pack(side="left", padx=(4, 0))
        ttk.Button(r2, text="변경 적용",
                   command=self.on_loading_apply).pack(side="left", padx=(12, 0))

    # ----- UI 아이콘 탭 -----
    def _build_icons_tab(self, parent: ttk.Frame):
        body = ttk.Panedwindow(parent, orient="horizontal")
        body.pack(fill="both", expand=True, padx=4, pady=4)

        left = ttk.Frame(body); body.add(left, weight=1)
        ttk.Label(left, text="아이콘 선택").pack(anchor="w")
        tbox = ttk.Frame(left); tbox.pack(fill="both", expand=True)
        self.icons_tree = ttk.Treeview(
            tbox, columns=("status",), show="tree headings")
        self.icons_tree.heading("#0", text="아이콘")
        self.icons_tree.heading("status", text="상태")
        self.icons_tree.column("#0", width=320)
        self.icons_tree.column("status", width=70, anchor="center")
        vsb = ttk.Scrollbar(tbox, orient="vertical",
                            command=self.icons_tree.yview)
        self.icons_tree.configure(yscrollcommand=vsb.set)
        self.icons_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.icons_tree.bind("<<TreeviewSelect>>", self.on_icon_select)

        ttk.Button(left, text="+ 임의 경로 추가…",
                   command=self.on_icon_add_custom).pack(fill="x", pady=(4, 0))

        right = ttk.Frame(body); body.add(right, weight=2)
        info = ttk.Frame(right); info.pack(fill="x", pady=(0, 8))
        self.icon_title_lbl = ttk.Label(
            info, text="좌측에서 아이콘을 선택하세요.",
            font=("맑은 고딕", 11, "bold"))
        self.icon_title_lbl.pack(anchor="w")
        self.icon_path_lbl = ttk.Label(info, text="")
        self.icon_path_lbl.pack(anchor="w")

        prv = ttk.Frame(right); prv.pack(fill="x", pady=8)
        self.icon_orig_box = self._make_preview_box(prv, "원본 (EU4)", 200, 200)
        self.icon_orig_box.pack(side="left", padx=(0, 16))
        self.icon_new_box = self._make_preview_box(prv, "새 아이콘 (변환 후)",
                                                    200, 200)
        self.icon_new_box.pack(side="left")

        ctrl = ttk.Frame(right); ctrl.pack(fill="x", pady=8)
        ttk.Button(ctrl, text="이미지 선택…",
                   command=self.on_icon_pick_image).pack(side="left")
        ttk.Button(ctrl, text="제거", command=self.on_icon_remove).pack(
            side="left", padx=8)
        ttk.Label(ctrl, text="맞춤:").pack(side="left", padx=(16, 4))
        self.icon_fit_var = tk.StringVar(value="cover")
        fit = ttk.Combobox(ctrl, textvariable=self.icon_fit_var, width=10,
                           state="readonly",
                           values=("cover", "contain", "stretch"))
        fit.pack(side="left")
        fit.bind("<<ComboboxSelected>>",
                 lambda e: self._refresh_icon_new_preview())

        self.icon_sel_path_lbl = ttk.Label(
            right, text="선택된 이미지: -", foreground="#555")
        self.icon_sel_path_lbl.pack(anchor="w", pady=(8, 0))

    # ----- 효과음 탭 -----
    def _build_sounds_tab(self, parent: ttk.Frame):
        body = ttk.Panedwindow(parent, orient="horizontal")
        body.pack(fill="both", expand=True, padx=4, pady=4)

        left = ttk.Frame(body); body.add(left, weight=1)
        ttk.Label(left, text="효과음 선택").pack(anchor="w")
        tbox = ttk.Frame(left); tbox.pack(fill="both", expand=True)
        self.sounds_tree = ttk.Treeview(
            tbox, columns=("status",), show="tree headings")
        self.sounds_tree.heading("#0", text="사운드 키")
        self.sounds_tree.heading("status", text="상태")
        self.sounds_tree.column("#0", width=320)
        self.sounds_tree.column("status", width=70, anchor="center")
        vsb = ttk.Scrollbar(tbox, orient="vertical",
                            command=self.sounds_tree.yview)
        self.sounds_tree.configure(yscrollcommand=vsb.set)
        self.sounds_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.sounds_tree.bind("<<TreeviewSelect>>", self.on_sound_select)

        ttk.Button(left, text="+ 임의 키 추가…",
                   command=self.on_sound_add_custom).pack(fill="x", pady=(4, 0))

        right = ttk.Frame(body); body.add(right, weight=2)
        self.sound_title_lbl = ttk.Label(
            right, text="좌측에서 효과음을 선택하세요.",
            font=("맑은 고딕", 11, "bold"))
        self.sound_title_lbl.pack(anchor="w")
        self.sound_key_lbl = ttk.Label(right, text="")
        self.sound_key_lbl.pack(anchor="w", pady=(0, 12))

        ttk.Label(right,
                  text="EU4 는 .wav 파일만 인식합니다 (ffmpeg 있으면 자동 변환).",
                  foreground="#777").pack(anchor="w")

        ctrl = ttk.Frame(right); ctrl.pack(fill="x", pady=8)
        ttk.Button(ctrl, text="사운드 파일 선택…",
                   command=self.on_sound_pick_file).pack(side="left")
        ttk.Button(ctrl, text="제거", command=self.on_sound_remove).pack(
            side="left", padx=8)

        self.sound_sel_path_lbl = ttk.Label(
            right, text="선택된 파일: -", foreground="#555")
        self.sound_sel_path_lbl.pack(anchor="w", pady=(8, 0))

    # ----- 국가 아이디어 탭 -----
    def _build_ideas_tab(self, parent: ttk.Frame):
        body = ttk.Panedwindow(parent, orient="horizontal")
        body.pack(fill="both", expand=True, padx=4, pady=4)

        left = ttk.Frame(body); body.add(left, weight=1)
        ttk.Label(left, text="아이디어 그룹").pack(anchor="w")
        gbox = ttk.Frame(left); gbox.pack(fill="both", expand=True)
        self.ideas_tree = ttk.Treeview(
            gbox, columns=("tag",), show="tree headings")
        self.ideas_tree.heading("#0", text="그룹 (표시명 / 키)")
        self.ideas_tree.heading("tag", text="태그")
        self.ideas_tree.column("#0", width=260)
        self.ideas_tree.column("tag", width=60, anchor="center")
        vsb = ttk.Scrollbar(gbox, orient="vertical",
                            command=self.ideas_tree.yview)
        self.ideas_tree.configure(yscrollcommand=vsb.set)
        self.ideas_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.ideas_tree.bind("<<TreeviewSelect>>", self.on_idea_group_select)

        bar = ttk.Frame(left); bar.pack(fill="x", pady=(4, 0))
        ttk.Button(bar, text="+ 새 그룹",
                   command=self.on_idea_group_add).pack(side="left")
        ttk.Button(bar, text="삭제",
                   command=self.on_idea_group_remove).pack(side="left", padx=8)

        right = ttk.Frame(body); body.add(right, weight=3)

        # 그룹 메타
        meta = ttk.LabelFrame(right, text="그룹 정보", padding=6)
        meta.pack(fill="x")
        rr = ttk.Frame(meta); rr.pack(fill="x", pady=2)
        ttk.Label(rr, text="키 (영숫자/_):", width=14).pack(side="left")
        self.idea_key_var = tk.StringVar()
        ttk.Entry(rr, textvariable=self.idea_key_var, width=28).pack(side="left")
        ttk.Label(rr, text="표시명:", width=8).pack(side="left", padx=(12, 0))
        self.idea_name_var = tk.StringVar()
        ttk.Entry(rr, textvariable=self.idea_name_var, width=30).pack(
            side="left")
        rr2 = ttk.Frame(meta); rr2.pack(fill="x", pady=2)
        ttk.Label(rr2, text="적용 국가 태그:", width=14).pack(side="left")
        self.idea_tag_var = tk.StringVar()
        ttk.Entry(rr2, textvariable=self.idea_tag_var, width=10).pack(side="left")
        ttk.Label(rr2, text="(비우면 trigger=always)",
                  foreground="#777").pack(side="left", padx=(8, 0))
        self.idea_free_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(rr2, text="free (전제 그룹 없이 채택)",
                        variable=self.idea_free_var).pack(side="left", padx=(16, 0))
        ttk.Button(rr2, text="그룹 정보 저장",
                   command=self.on_idea_meta_save).pack(side="right")

        # 슬롯 + modifier
        body2 = ttk.Frame(right)
        body2.pack(fill="both", expand=True, pady=(8, 0))

        slot_box = ttk.LabelFrame(body2, text="슬롯", padding=4)
        slot_box.pack(side="left", fill="y")
        self.idea_slot_tree = ttk.Treeview(
            slot_box, columns=(), show="tree", height=14)
        self.idea_slot_tree.column("#0", width=130)
        self.idea_slot_tree.pack()
        for sid, label in [
                ("tradition", "전통 (start)"),
                ("ambition", "야망 (bonus)"),
                ("idea_1", "아이디어 1"),
                ("idea_2", "아이디어 2"),
                ("idea_3", "아이디어 3"),
                ("idea_4", "아이디어 4"),
                ("idea_5", "아이디어 5"),
                ("idea_6", "아이디어 6"),
                ("idea_7", "아이디어 7")]:
            self.idea_slot_tree.insert("", "end", iid=f"slot::{sid}",
                                        text=label)
        self.idea_slot_tree.bind("<<TreeviewSelect>>",
                                  self.on_idea_slot_select)

        slot_edit = ttk.LabelFrame(body2, text="선택된 슬롯", padding=6)
        slot_edit.pack(side="left", fill="both", expand=True, padx=(8, 0))

        r1 = ttk.Frame(slot_edit); r1.pack(fill="x", pady=2)
        ttk.Label(r1, text="슬롯 표시명:", width=12).pack(side="left")
        self.idea_slot_name_var = tk.StringVar()
        ttk.Entry(r1, textvariable=self.idea_slot_name_var, width=40).pack(
            side="left", fill="x", expand=True)
        ttk.Button(r1, text="저장",
                   command=self.on_idea_slot_name_save).pack(side="left",
                                                              padx=(8, 0))

        mod_box = ttk.LabelFrame(slot_edit, text="Modifier 목록", padding=4)
        mod_box.pack(fill="both", expand=True, pady=(6, 0))
        self.idea_mod_tree = ttk.Treeview(
            mod_box, columns=("value",), show="tree headings", height=8)
        self.idea_mod_tree.heading("#0", text="Modifier")
        self.idea_mod_tree.heading("value", text="값")
        self.idea_mod_tree.column("#0", width=280)
        self.idea_mod_tree.column("value", width=80, anchor="e")
        self.idea_mod_tree.pack(fill="both", expand=True)

        add_row = ttk.Frame(slot_edit); add_row.pack(fill="x", pady=(6, 0))
        ttk.Label(add_row, text="카테고리:").pack(side="left")
        self.idea_mod_cat_var = tk.StringVar(
            value=list(MODIFIER_CATALOG.keys())[0])
        cat_cb = ttk.Combobox(add_row, textvariable=self.idea_mod_cat_var,
                              state="readonly", width=14,
                              values=list(MODIFIER_CATALOG.keys()))
        cat_cb.pack(side="left", padx=(4, 8))
        cat_cb.bind("<<ComboboxSelected>>",
                    lambda e: self._refresh_mod_choices())
        ttk.Label(add_row, text="Modifier:").pack(side="left")
        self.idea_mod_key_var = tk.StringVar()
        self.idea_mod_key_cb = ttk.Combobox(
            add_row, textvariable=self.idea_mod_key_var, state="readonly",
            width=36)
        self.idea_mod_key_cb.pack(side="left", padx=(4, 8))
        ttk.Label(add_row, text="값:").pack(side="left")
        self.idea_mod_val_var = tk.StringVar(value="0.1")
        ttk.Entry(add_row, textvariable=self.idea_mod_val_var, width=10).pack(
            side="left", padx=(4, 8))
        ttk.Button(add_row, text="추가/덮어쓰기",
                   command=self.on_idea_mod_add).pack(side="left")
        ttk.Button(add_row, text="선택 삭제",
                   command=self.on_idea_mod_remove).pack(side="left",
                                                          padx=(8, 0))
        self._refresh_mod_choices()

    # ----- 로컬라이제이션 탭 -----
    def _build_loc_tab(self, parent: ttk.Frame):
        body = ttk.Frame(parent); body.pack(fill="both", expand=True,
                                            padx=4, pady=4)

        top = ttk.LabelFrame(body, text="로컬라이제이션 항목", padding=6)
        top.pack(fill="both", expand=True)

        lbox = ttk.Frame(top); lbox.pack(fill="both", expand=True)
        self.loc_tree = ttk.Treeview(
            lbox, columns=("language", "version", "value"),
            show="tree headings", height=10)
        self.loc_tree.heading("#0", text="키")
        self.loc_tree.heading("language", text="언어")
        self.loc_tree.heading("version", text=":N")
        self.loc_tree.heading("value", text="값")
        self.loc_tree.column("#0", width=220)
        self.loc_tree.column("language", width=80, anchor="center")
        self.loc_tree.column("version", width=40, anchor="center")
        self.loc_tree.column("value", width=540)
        vsb = ttk.Scrollbar(lbox, orient="vertical",
                            command=self.loc_tree.yview)
        self.loc_tree.configure(yscrollcommand=vsb.set)
        self.loc_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.loc_tree.bind("<<TreeviewSelect>>", self.on_loc_select)

        edit = ttk.LabelFrame(body, text="편집", padding=8)
        edit.pack(fill="x", pady=(8, 0))

        r1 = ttk.Frame(edit); r1.pack(fill="x", pady=2)
        ttk.Label(r1, text="키:", width=8).pack(side="left")
        self.loc_key_var = tk.StringVar()
        ttk.Entry(r1, textvariable=self.loc_key_var, width=40).pack(
            side="left")
        ttk.Label(r1, text="언어:", width=6).pack(side="left", padx=(12, 0))
        self.loc_lang_var = tk.StringVar(value="korean")
        ttk.Combobox(r1, textvariable=self.loc_lang_var, state="readonly",
                     values=SUPPORTED_LANGUAGES, width=10).pack(side="left")
        ttk.Label(r1, text=":N:", width=4).pack(side="left", padx=(12, 0))
        self.loc_version_var = tk.StringVar(value="0")
        ttk.Spinbox(r1, from_=0, to=99, textvariable=self.loc_version_var,
                    width=4).pack(side="left")

        r2 = ttk.Frame(edit); r2.pack(fill="x", pady=2)
        ttk.Label(r2, text="값:", width=8).pack(side="left", anchor="n")
        self.loc_value_text = tk.Text(r2, height=3, wrap="word")
        self.loc_value_text.pack(side="left", fill="x", expand=True)

        r3 = ttk.Frame(edit); r3.pack(fill="x", pady=(6, 0))
        ttk.Button(r3, text="+ 추가",
                   command=self.on_loc_add).pack(side="left")
        ttk.Button(r3, text="변경 적용 (선택)",
                   command=self.on_loc_apply).pack(side="left", padx=8)
        ttk.Button(r3, text="선택 삭제",
                   command=self.on_loc_remove).pack(side="left")

    # ----- 공통 헬퍼 -----
    @staticmethod
    def _make_preview_box(parent, title: str, w: int, h: int) -> ttk.Frame:
        f = ttk.LabelFrame(parent, text=title, padding=8)
        canvas = tk.Canvas(f, width=w, height=h, bg="#202020",
                           highlightthickness=1, highlightbackground="#888")
        canvas.pack()
        f.canvas = canvas  # type: ignore
        f.size = (w, h)    # type: ignore
        return f

    @staticmethod
    def _clear_canvas(canvas: tk.Canvas):
        canvas.delete("all")

    def _pick_dir(self, var: tk.StringVar):
        d = filedialog.askdirectory(initialdir=var.get() or ".")
        if d:
            var.set(d)

    def _log(self, msg: str):
        self.log.configure(state="normal")
        self.log.insert("end", msg.rstrip() + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    # ----- 트리 populate -----
    def _populate_country_tree(self):
        for region, items in COUNTRIES.items():
            rid = self.country_tree.insert("", "end", text=region, open=False,
                                           values=("",))
            for tag, name in items:
                self.country_tree.insert(rid, "end", iid=f"tag::{tag}",
                                         text=f"{name} ({tag})", values=("",))

    def _populate_event_tree(self):
        groups = event_groups()
        for cat_label, items in groups.items():
            rid = self.event_tree.insert("", "end", text=cat_label, open=False,
                                         values=("",))
            for key, display in items:
                self.event_tree.insert(rid, "end", iid=f"ep::{key}",
                                       text=display, values=("",))

    def _set_country_status(self, tag: str, status: str) -> bool:
        iid = f"tag::{tag}"
        if self.country_tree.exists(iid):
            self.country_tree.set(iid, "status", status)
            return True
        return False

    def _set_event_status(self, key: str, status: str) -> bool:
        iid = f"ep::{key}"
        if self.event_tree.exists(iid):
            self.event_tree.set(iid, "status", status)
            return True
        return False

    # 트리에 없는 태그/키(다른 모드에서 불러오거나 사용자 정의 키)를 동적으로 추가
    EXTRA_GROUP_LABEL = "기타 (불러온 항목)"

    def _ensure_extra_country(self, tag: str):
        iid = f"tag::{tag}"
        if self.country_tree.exists(iid):
            return
        region_iid = "region::__extra__"
        if not self.country_tree.exists(region_iid):
            self.country_tree.insert("", "end", iid=region_iid,
                                     text=self.EXTRA_GROUP_LABEL,
                                     open=True, values=("",))
        self.country_tree.insert(region_iid, "end", iid=iid,
                                 text=f"({tag}) 불러온 태그", values=("",))

    def _ensure_extra_event(self, key: str):
        iid = f"ep::{key}"
        if self.event_tree.exists(iid):
            return
        cat_iid = "cat::__extra__"
        if not self.event_tree.exists(cat_iid):
            self.event_tree.insert("", "end", iid=cat_iid,
                                   text=self.EXTRA_GROUP_LABEL,
                                   open=True, values=("",))
        self.event_tree.insert(cat_iid, "end", iid=iid,
                               text=f"{key} (불러옴)", values=("",))

    # ----- 국기 핸들러 -----
    def on_country_select(self, _evt=None):
        sel = self.country_tree.selection()
        if not sel or not sel[0].startswith("tag::"):
            return
        tag = sel[0].split("::", 1)[1]
        self.current_tag = tag
        name = self.country_tree.item(sel[0], "text")
        self.flag_title_lbl.configure(text=name)
        self.flag_tag_lbl.configure(text=f"태그: {tag}")

        self._show_flag_original(tag)
        data = self.flag_selections.get(tag)
        if data:
            self.flag_fit_var.set(data.get("fit_mode", "cover"))
            self.flag_path_lbl.configure(text=f"선택된 이미지: {data['source']}")
            self._refresh_flag_new_preview()
        else:
            self.flag_fit_var.set("cover")
            self.flag_path_lbl.configure(text="선택된 이미지: -")
            self._clear_canvas(self.flag_new_box.canvas)

    def on_pick_flag_image(self):
        if not self.current_tag:
            messagebox.showinfo("알림", "먼저 좌측에서 국가를 선택하세요.")
            return
        path = filedialog.askopenfilename(
            title="국기로 사용할 이미지 선택",
            filetypes=[("이미지", "*.png *.jpg *.jpeg *.bmp *.webp *.tga *.gif"),
                       ("모든 파일", "*.*")])
        if not path:
            return
        self.flag_selections[self.current_tag] = {
            "source": Path(path), "fit_mode": self.flag_fit_var.get()}
        self.flag_path_lbl.configure(text=f"선택된 이미지: {path}")
        self._set_country_status(self.current_tag, "준비됨")
        self._refresh_flag_new_preview()

    def on_remove_flag(self):
        if not self.current_tag:
            return
        self.flag_selections.pop(self.current_tag, None)
        self._set_country_status(self.current_tag, "")
        self.flag_path_lbl.configure(text="선택된 이미지: -")
        self._clear_canvas(self.flag_new_box.canvas)

    def _show_flag_original(self, tag: str):
        canvas = self.flag_orig_box.canvas
        w, h = self.flag_orig_box.size  # type: ignore
        self._clear_canvas(canvas)
        flags_dir = Path(self.game_dir_var.get()) / "gfx" / "flags"
        path = flags_dir / f"{tag}.tga"
        if not path.is_file():
            canvas.create_text(w // 2, h // 2, text="원본 깃발 없음", fill="#aaa")
            return
        try:
            img = Image.open(path).convert("RGB").resize((w, h), Image.NEAREST)
            photo = ImageTk.PhotoImage(img)
            self._preview_imgs["flag_orig"] = photo
            canvas.create_image(w // 2, h // 2, image=photo)
        except Exception as exc:
            canvas.create_text(w // 2, h // 2, text=f"읽기 실패\n{exc}",
                               fill="#f88")

    def _refresh_flag_new_preview(self):
        if not self.current_tag:
            return
        sel = self.flag_selections.get(self.current_tag)
        if sel:
            sel["fit_mode"] = self.flag_fit_var.get()
        canvas = self.flag_new_box.canvas
        w, h = self.flag_new_box.size  # type: ignore
        self._clear_canvas(canvas)
        if not sel:
            return
        try:
            preview = preview_image(sel["source"], fit_mode=sel["fit_mode"])
            preview = preview.resize((w, h), Image.NEAREST)
            photo = ImageTk.PhotoImage(preview)
            self._preview_imgs["flag_new"] = photo
            canvas.create_image(w // 2, h // 2, image=photo)
        except Exception as exc:
            canvas.create_text(w // 2, h // 2, text=f"변환 실패\n{exc}",
                               fill="#f88")

    # ----- 이벤트 픽처 핸들러 -----
    def on_event_select(self, _evt=None):
        sel = self.event_tree.selection()
        if not sel or not sel[0].startswith("ep::"):
            return
        key = sel[0].split("::", 1)[1]
        self.current_event_key = key
        display = self.event_tree.item(sel[0], "text")
        self.event_title_lbl.configure(text=display)
        self.event_key_lbl.configure(text=f"키: {key}")

        self._show_event_original(key)
        data = self.event_selections.get(key)
        if data:
            self.event_fit_var.set(data.get("fit_mode", "cover"))
            self.event_path_lbl.configure(text=f"선택된 이미지: {data['source']}")
            self._refresh_event_new_preview()
        else:
            self.event_fit_var.set("cover")
            self.event_path_lbl.configure(text="선택된 이미지: -")
            self._clear_canvas(self.event_new_box.canvas)

    def on_pick_event_image(self):
        if not self.current_event_key:
            messagebox.showinfo("알림", "먼저 좌측에서 이벤트 픽처를 선택하세요.")
            return
        path = filedialog.askopenfilename(
            title="이벤트 픽처로 사용할 이미지 선택",
            filetypes=[("이미지", "*.png *.jpg *.jpeg *.bmp *.webp *.tga *.dds *.gif"),
                       ("모든 파일", "*.*")])
        if not path:
            return
        self.event_selections[self.current_event_key] = {
            "source": Path(path), "fit_mode": self.event_fit_var.get()}
        self.event_path_lbl.configure(text=f"선택된 이미지: {path}")
        self._set_event_status(self.current_event_key, "준비됨")
        self._refresh_event_new_preview()

    def on_remove_event(self):
        if not self.current_event_key:
            return
        self.event_selections.pop(self.current_event_key, None)
        self._set_event_status(self.current_event_key, "")
        self.event_path_lbl.configure(text="선택된 이미지: -")
        self._clear_canvas(self.event_new_box.canvas)

    def _show_event_original(self, key: str):
        canvas = self.event_orig_box.canvas
        w, h = self.event_orig_box.size  # type: ignore
        self._clear_canvas(canvas)
        from src.event_pictures import folder_for
        folder = folder_for(key)
        if not folder:
            canvas.create_text(w // 2, h // 2, text="키 정보 없음", fill="#aaa")
            return
        path = (Path(self.game_dir_var.get()) / "gfx" / "event_pictures"
                / folder / f"{key}.dds")
        if not path.is_file():
            canvas.create_text(w // 2, h // 2,
                               text=f"원본 없음\n({path.name})", fill="#aaa")
            return
        try:
            img = Image.open(path).convert("RGB").resize((w, h), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self._preview_imgs["event_orig"] = photo
            canvas.create_image(w // 2, h // 2, image=photo)
        except Exception as exc:
            canvas.create_text(w // 2, h // 2, text=f"읽기 실패\n{exc}",
                               fill="#f88")

    def _refresh_event_new_preview(self):
        if not self.current_event_key:
            return
        sel = self.event_selections.get(self.current_event_key)
        if sel:
            sel["fit_mode"] = self.event_fit_var.get()
        canvas = self.event_new_box.canvas
        w, h = self.event_new_box.size  # type: ignore
        self._clear_canvas(canvas)
        if not sel:
            return
        try:
            preview = preview_event_picture(sel["source"],
                                            fit_mode=sel["fit_mode"])
            preview = preview.resize((w, h), Image.LANCZOS)
            photo = ImageTk.PhotoImage(preview)
            self._preview_imgs["event_new"] = photo
            canvas.create_image(w // 2, h // 2, image=photo)
        except Exception as exc:
            canvas.create_text(w // 2, h // 2, text=f"변환 실패\n{exc}",
                               fill="#f88")

    # ----- 빌드 -----
    def on_build(self):
        has_any = (self.flag_selections or self.event_selections
                   or self.music_entries or self.loading_entries
                   or self.icon_selections or self.sound_selections
                   or self.idea_groups or self.loc_entries)
        if not has_any:
            messagebox.showwarning("알림", "선택된 항목이 없습니다.")
            return

        mod_name = self.mod_name_var.get().strip() or "내 EU4 모드"
        flag_entries = [
            FlagEntry(tag=tag, source_image=d["source"],
                      fit_mode=d.get("fit_mode", "cover"))
            for tag, d in self.flag_selections.items()]
        event_entries = [
            EventPictureEntry(key=key, source_image=d["source"],
                              fit_mode=d.get("fit_mode", "cover"))
            for key, d in self.event_selections.items()]
        music_entries = [
            MusicEntry(track_name=m["track_name"],
                       source_file=Path(m["source"]),
                       chance_preset=m.get("preset", "default"))
            for m in self.music_entries]
        loading_entries = [
            LoadingScreenEntry(index=int(m["index"]),
                               source_image=Path(m["source"]),
                               fit_mode=m.get("fit_mode", "cover"))
            for m in self.loading_entries]
        sound_entries = [
            SoundEntry(key=key, source_file=Path(d["source"]))
            for key, d in self.sound_selections.items()]
        icon_entries = [
            IconEntry(game_rel_path=rel, source_image=Path(d["source"]),
                      fit_mode=d.get("fit_mode", "cover"))
            for rel, d in self.icon_selections.items()]

        # 아이디어: dict → IdeaGroupEntry/IdeaSlot
        idea_entries = []
        for g in self.idea_groups:
            ideas_list = []
            for s in g.get("ideas", []):
                ideas_list.append(IdeaSlot(
                    display_name=s.get("display_name", ""),
                    description=s.get("description", ""),
                    modifiers=dict(s.get("modifiers", {}))))
            idea_entries.append(IdeaGroupEntry(
                key=safe_idea_key(g.get("key", "my_ideas")),
                display_name=g.get("display_name", ""),
                trigger_tag=(g.get("trigger_tag") or None),
                free=bool(g.get("free", True)),
                tradition=IdeaSlot(
                    display_name=g.get("tradition", {}).get("display_name", ""),
                    modifiers=dict(g.get("tradition", {}).get("modifiers", {}))),
                ambition=IdeaSlot(
                    display_name=g.get("ambition", {}).get("display_name", ""),
                    modifiers=dict(g.get("ambition", {}).get("modifiers", {}))),
                ideas=ideas_list,
            ))

        loc_entries = [
            LocEntry(key=e["key"], value=e.get("value", ""),
                     version=int(e.get("version", 0)),
                     language=e.get("language", "korean"))
            for e in self.loc_entries]

        output_root = Path(self.output_dir_var.get())
        output_root.mkdir(parents=True, exist_ok=True)

        try:
            result = build_mod(
                mod_name=mod_name,
                flag_entries=flag_entries,
                event_entries=event_entries,
                music_entries=music_entries,
                loading_entries=loading_entries,
                sound_entries=sound_entries,
                icon_entries=icon_entries,
                idea_entries=idea_entries,
                loc_entries=loc_entries,
                game_dir=Path(self.game_dir_var.get()),
                output_root=output_root,
                install_to_eu4=self.install_var.get(),
                eu4_user_dir=Path(self.user_dir_var.get()),
                supported_version=self.version_var.get().strip() or "1.37.*",
            )
        except Exception as exc:
            self._log("[오류] " + str(exc))
            traceback.print_exc()
            messagebox.showerror("빌드 실패", str(exc))
            return

        self._save_state()
        self._log("--------")
        self._log(f"모드 생성 완료: {result['mod_dir']}")
        for label, key in (
                ("국기", "converted_flags"),
                ("이벤트 픽처", "converted_events"),
                ("음악 트랙", "converted_music"),
                ("UI 아이콘", "converted_icons"),
                ("효과음", "converted_sounds"),
                ("아이디어 그룹", "converted_ideas"),
                ("로컬 파일", "converted_loc_files")):
            items = result.get(key) or []
            if items:
                self._log(f"  {label} {len(items)}개: "
                          + ", ".join(map(str, items)))
        loading = result.get("converted_loading") or []
        if loading:
            self._log(f"  로딩 화면 {len(loading)}개: "
                      + ", ".join(f"load_{i}" for i in loading))
        if result["installed_mod_file"]:
            self._log(f"EU4 에 설치됨: {result['installed_mod_file']}")
            self._log("→ EU4 런처에서 플레이세트에 추가 후 활성화하세요.")
        messagebox.showinfo("완료", "모드가 생성되었습니다. 로그를 확인하세요.")

    # ----- 음악 핸들러 -----
    def _refresh_music_tree(self, select_iid: str | None = None):
        self.music_tree.delete(*self.music_tree.get_children())
        for idx, item in enumerate(self.music_entries):
            iid = f"music::{idx}"
            preset_label = LABEL_BY_PRESET.get(
                item.get("preset", "default"), item.get("preset", "default"))
            self.music_tree.insert("", "end", iid=iid,
                                   text=item.get("track_name", ""),
                                   values=(preset_label, str(item.get("source", ""))))
        if select_iid and self.music_tree.exists(select_iid):
            self.music_tree.selection_set(select_iid)
            self.music_tree.focus(select_iid)

    def _pick_music_file(self):
        path = filedialog.askopenfilename(
            title="음악 파일 선택",
            filetypes=[("음악", "*.ogg *.mp3 *.wav *.flac *.m4a *.aac *.opus *.wma"),
                       ("모든 파일", "*.*")])
        if path:
            self.music_path_var.set(path)
            # 트랙명이 비어 있으면 파일명에서 자동 채움
            if not self.music_name_var.get().strip():
                self.music_name_var.set(safe_track_name(Path(path).stem))

    def on_music_select(self, _evt=None):
        sel = self.music_tree.selection()
        if not sel:
            self.current_music_iid = None
            return
        iid = sel[0]
        self.current_music_iid = iid
        idx = int(iid.split("::", 1)[1])
        item = self.music_entries[idx]
        self.music_name_var.set(item.get("track_name", ""))
        self.music_path_var.set(str(item.get("source", "")))
        self.music_preset_var.set(LABEL_BY_PRESET.get(
            item.get("preset", "default"), LABEL_BY_PRESET["default"]))

    def on_music_add(self):
        name = self.music_name_var.get().strip()
        src = self.music_path_var.get().strip()
        if not src:
            messagebox.showinfo("알림", "음악 파일을 먼저 선택하세요.")
            return
        src_path = Path(src)
        if not src_path.is_file():
            messagebox.showerror("오류", f"파일을 찾을 수 없습니다:\n{src_path}")
            return
        if not name:
            name = safe_track_name(src_path.stem)
        preset = PRESET_BY_LABEL.get(self.music_preset_var.get(), "default")
        self.music_entries.append({
            "track_name": safe_track_name(name),
            "source": src_path,
            "preset": preset,
        })
        new_iid = f"music::{len(self.music_entries) - 1}"
        self._refresh_music_tree(select_iid=new_iid)
        # 폼 정리
        self.music_name_var.set("")
        self.music_path_var.set("")

    def on_music_remove(self):
        sel = self.music_tree.selection()
        if not sel:
            return
        idx = int(sel[0].split("::", 1)[1])
        if 0 <= idx < len(self.music_entries):
            del self.music_entries[idx]
        self.current_music_iid = None
        self._refresh_music_tree()
        self.music_name_var.set("")
        self.music_path_var.set("")

    def on_music_apply(self):
        sel = self.music_tree.selection()
        if not sel:
            messagebox.showinfo("알림",
                                "리스트에서 수정할 트랙을 먼저 선택하세요.")
            return
        idx = int(sel[0].split("::", 1)[1])
        name = self.music_name_var.get().strip()
        src = self.music_path_var.get().strip()
        if not src:
            messagebox.showinfo("알림", "음악 파일이 비어 있습니다.")
            return
        src_path = Path(src)
        if not src_path.is_file():
            messagebox.showerror("오류", f"파일을 찾을 수 없습니다:\n{src_path}")
            return
        preset = PRESET_BY_LABEL.get(self.music_preset_var.get(), "default")
        self.music_entries[idx] = {
            "track_name": safe_track_name(name) if name else
                          safe_track_name(src_path.stem),
            "source": src_path,
            "preset": preset,
        }
        self._refresh_music_tree(select_iid=sel[0])

    def _music_move(self, delta: int):
        sel = self.music_tree.selection()
        if not sel:
            return
        idx = int(sel[0].split("::", 1)[1])
        new_idx = idx + delta
        if not (0 <= new_idx < len(self.music_entries)):
            return
        self.music_entries[idx], self.music_entries[new_idx] = (
            self.music_entries[new_idx], self.music_entries[idx])
        self._refresh_music_tree(select_iid=f"music::{new_idx}")

    # ----- 로딩 화면 핸들러 -----
    def _refresh_loading_tree(self, select_iid: str | None = None):
        self.loading_tree.delete(*self.loading_tree.get_children())
        for idx, item in enumerate(self.loading_entries):
            iid = f"loading::{idx}"
            self.loading_tree.insert(
                "", "end", iid=iid,
                text=f"load_{item['index']}",
                values=(item.get("fit_mode", "cover"),
                        str(item.get("source", ""))))
        if select_iid and self.loading_tree.exists(select_iid):
            self.loading_tree.selection_set(select_iid)

    def _pick_loading_image(self):
        path = filedialog.askopenfilename(
            title="로딩 화면 이미지 선택",
            filetypes=[("이미지",
                        "*.png *.jpg *.jpeg *.bmp *.webp *.tga *.dds"),
                       ("모든 파일", "*.*")])
        if path:
            self.loading_path_var.set(path)

    def on_loading_select(self, _evt=None):
        sel = self.loading_tree.selection()
        if not sel:
            return
        idx = int(sel[0].split("::", 1)[1])
        self.current_loading_iid = sel[0]
        item = self.loading_entries[idx]
        self.loading_index_var.set(str(item["index"]))
        self.loading_path_var.set(str(item["source"]))
        self.loading_fit_var.set(item.get("fit_mode", "cover"))

    def on_loading_add(self):
        path = self.loading_path_var.get().strip()
        if not path:
            messagebox.showinfo("알림", "이미지를 먼저 선택하세요.")
            return
        try:
            idx_int = int(self.loading_index_var.get())
        except ValueError:
            messagebox.showerror("오류", "인덱스는 정수여야 합니다.")
            return
        self.loading_entries.append({
            "index": idx_int, "source": Path(path),
            "fit_mode": self.loading_fit_var.get()})
        new_iid = f"loading::{len(self.loading_entries) - 1}"
        self._refresh_loading_tree(select_iid=new_iid)

    def on_loading_remove(self):
        sel = self.loading_tree.selection()
        if not sel:
            return
        idx = int(sel[0].split("::", 1)[1])
        del self.loading_entries[idx]
        self._refresh_loading_tree()
        self.current_loading_iid = None

    def on_loading_apply(self):
        sel = self.loading_tree.selection()
        if not sel:
            messagebox.showinfo("알림", "수정할 항목을 먼저 선택하세요.")
            return
        idx = int(sel[0].split("::", 1)[1])
        path = self.loading_path_var.get().strip()
        if not path:
            return
        try:
            idx_int = int(self.loading_index_var.get())
        except ValueError:
            messagebox.showerror("오류", "인덱스는 정수여야 합니다.")
            return
        self.loading_entries[idx] = {
            "index": idx_int, "source": Path(path),
            "fit_mode": self.loading_fit_var.get()}
        self._refresh_loading_tree(select_iid=sel[0])

    # ----- UI 아이콘 핸들러 -----
    def _populate_icons_tree(self):
        for group, items in ICON_PRESETS.items():
            rid = self.icons_tree.insert("", "end", text=group, open=False,
                                          values=("",))
            for rel, name in items:
                self.icons_tree.insert(rid, "end", iid=f"icon::{rel}",
                                        text=f"{name}\n  {rel}", values=("",))

    def _ensure_extra_icon(self, rel_path: str, label: str | None = None):
        iid = f"icon::{rel_path}"
        if self.icons_tree.exists(iid):
            return
        extra_iid = "iconcat::__extra__"
        if not self.icons_tree.exists(extra_iid):
            self.icons_tree.insert("", "end", iid=extra_iid,
                                    text="(사용자 추가/불러옴)", open=True,
                                    values=("",))
        self.icons_tree.insert(extra_iid, "end", iid=iid,
                                text=label or rel_path, values=("",))

    def on_icon_add_custom(self):
        from tkinter.simpledialog import askstring
        rel = askstring("아이콘 경로 추가",
                        "게임 폴더 기준 상대 경로 (예: gfx/interface/Eu4_logo.dds)")
        if not rel:
            return
        rel = rel.strip().replace("\\", "/")
        self._ensure_extra_icon(rel)
        self.icons_tree.selection_set(f"icon::{rel}")
        self.on_icon_select()

    def on_icon_select(self, _evt=None):
        sel = self.icons_tree.selection()
        if not sel or not sel[0].startswith("icon::"):
            return
        rel = sel[0].split("::", 1)[1]
        self.current_icon_path = rel
        self.icon_title_lbl.configure(text=rel.split("/")[-1])
        self.icon_path_lbl.configure(text=f"경로: {rel}")
        self._show_icon_original(rel)
        data = self.icon_selections.get(rel)
        if data:
            self.icon_fit_var.set(data.get("fit_mode", "cover"))
            self.icon_sel_path_lbl.configure(text=f"선택된 이미지: {data['source']}")
            self._refresh_icon_new_preview()
        else:
            self.icon_fit_var.set("cover")
            self.icon_sel_path_lbl.configure(text="선택된 이미지: -")
            self._clear_canvas(self.icon_new_box.canvas)

    def _show_icon_original(self, rel: str):
        canvas = self.icon_orig_box.canvas
        w, h = self.icon_orig_box.size  # type: ignore
        self._clear_canvas(canvas)
        path = Path(self.game_dir_var.get()) / rel
        if not path.is_file():
            canvas.create_text(w // 2, h // 2, text="원본 없음", fill="#aaa")
            return
        try:
            img = Image.open(path).convert("RGB")
            # 비율 유지로 리사이즈
            iw, ih = img.size
            ratio = min(w / iw, h / ih)
            img = img.resize((int(iw * ratio), int(ih * ratio)), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self._preview_imgs["icon_orig"] = photo
            canvas.create_image(w // 2, h // 2, image=photo)
        except Exception as exc:
            canvas.create_text(w // 2, h // 2, text=f"읽기 실패\n{exc}",
                                fill="#f88")

    def _refresh_icon_new_preview(self):
        if not self.current_icon_path:
            return
        sel = self.icon_selections.get(self.current_icon_path)
        if sel:
            sel["fit_mode"] = self.icon_fit_var.get()
        canvas = self.icon_new_box.canvas
        w, h = self.icon_new_box.size  # type: ignore
        self._clear_canvas(canvas)
        if not sel:
            return
        try:
            # 원본 사이즈 검출 후 그 사이즈로 변환 시뮬레이션
            from src.image_processor import _fit
            orig_path = (Path(self.game_dir_var.get())
                         / self.current_icon_path)
            target_size = (256, 256)
            if orig_path.is_file():
                with Image.open(orig_path) as om:
                    target_size = om.size
            src_img = Image.open(sel["source"]).convert("RGB")
            converted = _fit(src_img, target_size, sel["fit_mode"])
            iw, ih = converted.size
            ratio = min(w / iw, h / ih)
            preview = converted.resize((int(iw * ratio), int(ih * ratio)),
                                        Image.LANCZOS)
            photo = ImageTk.PhotoImage(preview)
            self._preview_imgs["icon_new"] = photo
            canvas.create_image(w // 2, h // 2, image=photo)
        except Exception as exc:
            canvas.create_text(w // 2, h // 2, text=f"변환 실패\n{exc}",
                                fill="#f88")

    def on_icon_pick_image(self):
        if not self.current_icon_path:
            messagebox.showinfo("알림", "먼저 좌측에서 아이콘을 선택하세요.")
            return
        path = filedialog.askopenfilename(
            title="아이콘으로 사용할 이미지 선택",
            filetypes=[("이미지",
                        "*.png *.jpg *.jpeg *.bmp *.webp *.tga *.dds"),
                       ("모든 파일", "*.*")])
        if not path:
            return
        self.icon_selections[self.current_icon_path] = {
            "source": Path(path), "fit_mode": self.icon_fit_var.get()}
        self.icon_sel_path_lbl.configure(text=f"선택된 이미지: {path}")
        if self.icons_tree.exists(f"icon::{self.current_icon_path}"):
            self.icons_tree.set(f"icon::{self.current_icon_path}",
                                 "status", "준비됨")
        self._refresh_icon_new_preview()

    def on_icon_remove(self):
        if not self.current_icon_path:
            return
        self.icon_selections.pop(self.current_icon_path, None)
        if self.icons_tree.exists(f"icon::{self.current_icon_path}"):
            self.icons_tree.set(f"icon::{self.current_icon_path}", "status", "")
        self.icon_sel_path_lbl.configure(text="선택된 이미지: -")
        self._clear_canvas(self.icon_new_box.canvas)

    # ----- 효과음 핸들러 -----
    def _populate_sounds_tree(self):
        for group, items in SOUND_GROUPS.items():
            rid = self.sounds_tree.insert("", "end", text=group, open=False,
                                          values=("",))
            for key, name in items:
                self.sounds_tree.insert(rid, "end", iid=f"snd::{key}",
                                         text=f"{name}\n  {key}",
                                         values=("",))

    def _ensure_extra_sound(self, key: str):
        iid = f"snd::{key}"
        if self.sounds_tree.exists(iid):
            return
        extra_iid = "sndcat::__extra__"
        if not self.sounds_tree.exists(extra_iid):
            self.sounds_tree.insert("", "end", iid=extra_iid,
                                     text="(사용자 추가/불러옴)", open=True,
                                     values=("",))
        self.sounds_tree.insert(extra_iid, "end", iid=iid,
                                 text=key, values=("",))

    def on_sound_add_custom(self):
        from tkinter.simpledialog import askstring
        key = askstring("사운드 키 추가",
                        "EU4 사운드 키 (예: declare_war)")
        if not key:
            return
        key = key.strip()
        self._ensure_extra_sound(key)
        self.sounds_tree.selection_set(f"snd::{key}")
        self.on_sound_select()

    def on_sound_select(self, _evt=None):
        sel = self.sounds_tree.selection()
        if not sel or not sel[0].startswith("snd::"):
            return
        key = sel[0].split("::", 1)[1]
        self.current_sound_key = key
        self.sound_title_lbl.configure(text=key)
        self.sound_key_lbl.configure(text="이 키를 우리 wav 로 덮어씁니다.")
        data = self.sound_selections.get(key)
        self.sound_sel_path_lbl.configure(
            text=f"선택된 파일: {data['source']}" if data else "선택된 파일: -")

    def on_sound_pick_file(self):
        if not self.current_sound_key:
            messagebox.showinfo("알림", "먼저 좌측에서 사운드 키를 선택하세요.")
            return
        path = filedialog.askopenfilename(
            title="사운드 파일 선택",
            filetypes=[("사운드", "*.wav *.mp3 *.ogg *.flac *.m4a"),
                       ("모든 파일", "*.*")])
        if not path:
            return
        self.sound_selections[self.current_sound_key] = {
            "source": Path(path)}
        self.sound_sel_path_lbl.configure(text=f"선택된 파일: {path}")
        if self.sounds_tree.exists(f"snd::{self.current_sound_key}"):
            self.sounds_tree.set(f"snd::{self.current_sound_key}",
                                  "status", "준비됨")

    def on_sound_remove(self):
        if not self.current_sound_key:
            return
        self.sound_selections.pop(self.current_sound_key, None)
        if self.sounds_tree.exists(f"snd::{self.current_sound_key}"):
            self.sounds_tree.set(f"snd::{self.current_sound_key}",
                                  "status", "")
        self.sound_sel_path_lbl.configure(text="선택된 파일: -")

    # ----- 국가 아이디어 핸들러 -----
    def _refresh_idea_groups_tree(self, select_idx: int | None = None):
        self.ideas_tree.delete(*self.ideas_tree.get_children())
        for i, g in enumerate(self.idea_groups):
            iid = f"grp::{i}"
            disp = g.get("display_name", "") or g.get("key", "")
            self.ideas_tree.insert("", "end", iid=iid,
                                    text=f"{disp}  ({g.get('key', '')})",
                                    values=(g.get("trigger_tag", "") or "",))
        if select_idx is not None and 0 <= select_idx < len(self.idea_groups):
            self.ideas_tree.selection_set(f"grp::{select_idx}")
            self._load_idea_group_form(select_idx)

    def _load_idea_group_form(self, idx: int):
        g = self.idea_groups[idx]
        self.current_idea_idx = idx
        self.idea_key_var.set(g.get("key", ""))
        self.idea_name_var.set(g.get("display_name", ""))
        self.idea_tag_var.set(g.get("trigger_tag", "") or "")
        self.idea_free_var.set(bool(g.get("free", True)))
        # 슬롯이 비어 있으면 초기화
        if "tradition" not in g:
            g["tradition"] = {"display_name": "", "modifiers": {}}
        if "ambition" not in g:
            g["ambition"] = {"display_name": "", "modifiers": {}}
        if "ideas" not in g or len(g.get("ideas", [])) != 7:
            g["ideas"] = [{"display_name": "", "modifiers": {}}
                          for _ in range(7)]
        # 기본 선택 슬롯 = 전통
        self.idea_slot_tree.selection_set("slot::tradition")
        self.on_idea_slot_select()

    def on_idea_group_select(self, _evt=None):
        sel = self.ideas_tree.selection()
        if not sel or not sel[0].startswith("grp::"):
            return
        self._load_idea_group_form(int(sel[0].split("::", 1)[1]))

    def on_idea_group_add(self):
        n = len(self.idea_groups) + 1
        new = {
            "key": safe_idea_key(f"my_ideas_{n}"),
            "display_name": f"내 아이디어 그룹 {n}",
            "trigger_tag": "",
            "free": True,
            "tradition": {"display_name": "전통", "modifiers": {}},
            "ambition": {"display_name": "야망", "modifiers": {}},
            "ideas": [{"display_name": f"아이디어 {i+1}", "modifiers": {}}
                      for i in range(7)],
        }
        self.idea_groups.append(new)
        self._refresh_idea_groups_tree(select_idx=len(self.idea_groups) - 1)

    def on_idea_group_remove(self):
        sel = self.ideas_tree.selection()
        if not sel:
            return
        idx = int(sel[0].split("::", 1)[1])
        del self.idea_groups[idx]
        self.current_idea_idx = None
        self._refresh_idea_groups_tree()

    def on_idea_meta_save(self):
        if self.current_idea_idx is None:
            return
        g = self.idea_groups[self.current_idea_idx]
        g["key"] = safe_idea_key(self.idea_key_var.get())
        g["display_name"] = self.idea_name_var.get().strip()
        tag = self.idea_tag_var.get().strip().upper()
        g["trigger_tag"] = tag or None
        g["free"] = bool(self.idea_free_var.get())
        self._refresh_idea_groups_tree(select_idx=self.current_idea_idx)

    def _current_slot(self) -> dict | None:
        if self.current_idea_idx is None or self.current_idea_slot is None:
            return None
        g = self.idea_groups[self.current_idea_idx]
        if self.current_idea_slot == "tradition":
            return g["tradition"]
        if self.current_idea_slot == "ambition":
            return g["ambition"]
        if self.current_idea_slot.startswith("idea_"):
            n = int(self.current_idea_slot.split("_", 1)[1]) - 1
            return g["ideas"][n]
        return None

    def on_idea_slot_select(self, _evt=None):
        sel = self.idea_slot_tree.selection()
        if not sel:
            return
        slot_id = sel[0].split("::", 1)[1]
        self.current_idea_slot = slot_id
        slot = self._current_slot()
        if slot is None:
            return
        self.idea_slot_name_var.set(slot.get("display_name", ""))
        self._refresh_idea_mod_tree()

    def on_idea_slot_name_save(self):
        slot = self._current_slot()
        if slot is None:
            return
        slot["display_name"] = self.idea_slot_name_var.get().strip()

    def _refresh_idea_mod_tree(self):
        self.idea_mod_tree.delete(*self.idea_mod_tree.get_children())
        slot = self._current_slot()
        if slot is None:
            return
        for k, v in slot.get("modifiers", {}).items():
            self.idea_mod_tree.insert("", "end", iid=f"mod::{k}",
                                       text=k, values=(v,))

    def _refresh_mod_choices(self):
        cat = self.idea_mod_cat_var.get()
        items = MODIFIER_CATALOG.get(cat, [])
        values = [f"{name} ({key})" for key, name, _v in items]
        self.idea_mod_key_cb["values"] = values
        if values:
            self.idea_mod_key_cb.set(values[0])
            self.idea_mod_val_var.set(str(items[0][2]))

    def on_idea_mod_add(self):
        slot = self._current_slot()
        if slot is None:
            messagebox.showinfo("알림", "먼저 슬롯을 선택하세요.")
            return
        sel_text = self.idea_mod_key_var.get()
        m = re.search(r"\(([^)]+)\)\s*$", sel_text)
        if not m:
            messagebox.showinfo("알림", "Modifier 를 선택하세요.")
            return
        key = m.group(1)
        try:
            val = float(self.idea_mod_val_var.get())
        except ValueError:
            messagebox.showerror("오류", "값은 숫자여야 합니다.")
            return
        slot.setdefault("modifiers", {})[key] = val
        self._refresh_idea_mod_tree()

    def on_idea_mod_remove(self):
        sel = self.idea_mod_tree.selection()
        if not sel:
            return
        slot = self._current_slot()
        if slot is None:
            return
        for iid in sel:
            key = iid.split("::", 1)[1]
            slot.get("modifiers", {}).pop(key, None)
        self._refresh_idea_mod_tree()

    # ----- 로컬라이제이션 핸들러 -----
    def _refresh_loc_tree(self, select_iid: str | None = None):
        self.loc_tree.delete(*self.loc_tree.get_children())
        for i, e in enumerate(self.loc_entries):
            iid = f"loc::{i}"
            self.loc_tree.insert("", "end", iid=iid,
                                  text=e.get("key", ""),
                                  values=(e.get("language", "korean"),
                                          str(e.get("version", 0)),
                                          e.get("value", "")))
        if select_iid and self.loc_tree.exists(select_iid):
            self.loc_tree.selection_set(select_iid)

    def on_loc_select(self, _evt=None):
        sel = self.loc_tree.selection()
        if not sel:
            return
        self.current_loc_iid = sel[0]
        idx = int(sel[0].split("::", 1)[1])
        e = self.loc_entries[idx]
        self.loc_key_var.set(e.get("key", ""))
        self.loc_lang_var.set(e.get("language", "korean"))
        self.loc_version_var.set(str(e.get("version", 0)))
        self.loc_value_text.delete("1.0", "end")
        self.loc_value_text.insert("1.0", e.get("value", ""))

    def on_loc_add(self):
        key = self.loc_key_var.get().strip()
        if not key:
            messagebox.showinfo("알림", "키를 입력하세요.")
            return
        val = self.loc_value_text.get("1.0", "end-1c")
        try:
            ver = int(self.loc_version_var.get())
        except ValueError:
            ver = 0
        self.loc_entries.append({
            "key": key, "value": val,
            "language": self.loc_lang_var.get(), "version": ver})
        self._refresh_loc_tree(
            select_iid=f"loc::{len(self.loc_entries) - 1}")

    def on_loc_apply(self):
        sel = self.loc_tree.selection()
        if not sel:
            messagebox.showinfo("알림", "수정할 항목을 먼저 선택하세요.")
            return
        idx = int(sel[0].split("::", 1)[1])
        key = self.loc_key_var.get().strip()
        if not key:
            return
        val = self.loc_value_text.get("1.0", "end-1c")
        try:
            ver = int(self.loc_version_var.get())
        except ValueError:
            ver = 0
        self.loc_entries[idx] = {
            "key": key, "value": val,
            "language": self.loc_lang_var.get(), "version": ver}
        self._refresh_loc_tree(select_iid=sel[0])

    def on_loc_remove(self):
        sel = self.loc_tree.selection()
        if not sel:
            return
        idx = int(sel[0].split("::", 1)[1])
        del self.loc_entries[idx]
        self._refresh_loc_tree()
        self.current_loc_iid = None

    # ----- 모드 불러오기 / 초기화 -----
    def _clear_all_selections(self):
        for tag in list(self.flag_selections):
            self._set_country_status(tag, "")
        for key in list(self.event_selections):
            self._set_event_status(key, "")
        self.flag_selections.clear()
        self.event_selections.clear()
        self.music_entries.clear()
        self.loading_entries.clear()
        # 아이콘 / 사운드 트리의 status 도 비움
        for rel in list(self.icon_selections):
            if self.icons_tree.exists(f"icon::{rel}"):
                self.icons_tree.set(f"icon::{rel}", "status", "")
        for key in list(self.sound_selections):
            if self.sounds_tree.exists(f"snd::{key}"):
                self.sounds_tree.set(f"snd::{key}", "status", "")
        self.icon_selections.clear()
        self.sound_selections.clear()
        self.idea_groups.clear()
        self.loc_entries.clear()

        self._refresh_music_tree()
        self._refresh_loading_tree()
        self._refresh_idea_groups_tree()
        self._refresh_loc_tree()
        self.music_name_var.set("")
        self.music_path_var.set("")
        self._clear_canvas(self.flag_new_box.canvas)
        self._clear_canvas(self.event_new_box.canvas)
        self._clear_canvas(self.icon_new_box.canvas)
        self.flag_path_lbl.configure(text="선택된 이미지: -")
        self.event_path_lbl.configure(text="선택된 이미지: -")
        self.icon_sel_path_lbl.configure(text="선택된 이미지: -")
        self.sound_sel_path_lbl.configure(text="선택된 파일: -")

    def on_clear_all(self):
        if not self.flag_selections and not self.event_selections:
            return
        if not messagebox.askyesno(
                "확인", "현재 선택을 모두 비웁니다. 진행할까요?"):
            return
        self._clear_all_selections()
        self._log("선택 초기화됨.")

    def on_load_mod(self):
        """기존 모드 폴더를 불러와 selections 채움. 이후 수정 후 재빌드."""
        initial = self.user_dir_var.get() or "."
        mod_root = Path(initial) / "mod"
        if mod_root.is_dir():
            initial = str(mod_root)
        elif Path(self.output_dir_var.get()).is_dir():
            initial = self.output_dir_var.get()

        folder = filedialog.askdirectory(
            title="불러올 모드 폴더 선택 (descriptor.mod 가 있는 폴더)",
            initialdir=initial)
        if not folder:
            return

        mod_dir = Path(folder)
        descriptor = mod_dir / "descriptor.mod"
        if not descriptor.is_file():
            messagebox.showerror(
                "오류",
                f"유효한 모드 폴더가 아닙니다.\ndescriptor.mod 가 없습니다:\n{mod_dir}")
            return

        # descriptor 메타 파싱
        try:
            text = descriptor.read_text(encoding="utf-8-sig", errors="replace")
        except Exception as exc:
            messagebox.showerror("오류", f"descriptor.mod 읽기 실패: {exc}")
            return

        m = re.search(r'name\s*=\s*"([^"]+)"', text)
        if m:
            self.mod_name_var.set(m.group(1))
        m = re.search(r'supported_version\s*=\s*"([^"]+)"', text)
        if m:
            self.version_var.set(m.group(1))

        # 기존 selections 비움
        self._clear_all_selections()

        # 국기 스캔
        loaded_flags: list[str] = []
        flags_dir = mod_dir / "gfx" / "flags"
        if flags_dir.is_dir():
            for tga in sorted(flags_dir.glob("*.tga")):
                tag = tga.stem.upper()
                self.flag_selections[tag] = {
                    "source": tga, "fit_mode": "cover"}
                if not self._set_country_status(tag, "불러옴"):
                    self._ensure_extra_country(tag)
                    self._set_country_status(tag, "불러옴")
                loaded_flags.append(tag)

        # 이벤트 픽처 스캔 (모드는 보통 gfx/event_pictures/<mod_id>/*.dds 구조)
        loaded_events: list[str] = []
        ep_dir = mod_dir / "gfx" / "event_pictures"
        if ep_dir.is_dir():
            for dds in sorted(ep_dir.rglob("*.dds")):
                key = dds.stem
                self.event_selections[key] = {
                    "source": dds, "fit_mode": "cover"}
                if not self._set_event_status(key, "불러옴"):
                    self._ensure_extra_event(key)
                    self._set_event_status(key, "불러옴")
                loaded_events.append(key)

        # 음악 트랙 스캔
        loaded_music: list[str] = []
        assets = parse_music_assets(mod_dir)
        presets = parse_song_presets(mod_dir)
        mod_id_guess = mod_dir.name
        for name, ogg_path in assets:
            display = name
            if display.startswith(mod_id_guess + "_"):
                display = display[len(mod_id_guess) + 1:]
            self.music_entries.append({
                "track_name": safe_track_name(display) or safe_track_name(name),
                "source": ogg_path,
                "preset": presets.get(name, "default"),
            })
            loaded_music.append(name)
        self._refresh_music_tree()

        # 로딩 화면 스캔
        loaded_loading: list[int] = []
        ls_dir = mod_dir / "gfx" / "loadingscreens"
        if ls_dir.is_dir():
            for dds in sorted(ls_dir.glob("load_*.dds")):
                m = re.match(r"load_(\d+)$", dds.stem)
                if m:
                    idx = int(m.group(1))
                    self.loading_entries.append({
                        "index": idx, "source": dds, "fit_mode": "cover"})
                    loaded_loading.append(idx)
        self._refresh_loading_tree()

        # UI 아이콘 스캔 (event_pictures/flags/loadingscreens 제외)
        loaded_icons: list[str] = []
        for rel, path in scan_icons_in_mod(mod_dir):
            self.icon_selections[rel] = {"source": path, "fit_mode": "cover"}
            self._ensure_extra_icon(rel)
            if self.icons_tree.exists(f"icon::{rel}"):
                self.icons_tree.set(f"icon::{rel}", "status", "불러옴")
            loaded_icons.append(rel)

        # 효과음 스캔
        loaded_sounds: list[str] = []
        for key, wav in parse_sound_assets(mod_dir):
            self.sound_selections[key] = {"source": wav}
            self._ensure_extra_sound(key)
            if self.sounds_tree.exists(f"snd::{key}"):
                self.sounds_tree.set(f"snd::{key}", "status", "불러옴")
            loaded_sounds.append(key)

        # 아이디어 그룹 스캔
        loaded_ideas: list[str] = []
        for ig in parse_idea_groups(mod_dir):
            self.idea_groups.append({
                "key": ig.key,
                "display_name": ig.display_name,
                "trigger_tag": ig.trigger_tag,
                "free": ig.free,
                "tradition": {
                    "display_name": ig.tradition.display_name,
                    "modifiers": dict(ig.tradition.modifiers)},
                "ambition": {
                    "display_name": ig.ambition.display_name,
                    "modifiers": dict(ig.ambition.modifiers)},
                "ideas": [{"display_name": s.display_name,
                           "modifiers": dict(s.modifiers)}
                          for s in ig.ideas],
            })
            loaded_ideas.append(ig.key)
        self._refresh_idea_groups_tree()

        # 로컬라이제이션 스캔
        loaded_loc = 0
        for e in parse_localisation_dir(mod_dir):
            self.loc_entries.append({
                "key": e.key, "value": e.value,
                "language": e.language, "version": e.version})
            loaded_loc += 1
        self._refresh_loc_tree()

        self._log("--------")
        self._log(f"모드 불러옴: {mod_dir}")
        self._log(f"  국기 {len(loaded_flags)}개  이벤트픽처 {len(loaded_events)}개"
                  f"  로딩화면 {len(loaded_loading)}개"
                  f"  UI아이콘 {len(loaded_icons)}개")
        self._log(f"  음악 {len(loaded_music)}개  효과음 {len(loaded_sounds)}개"
                  f"  아이디어 {len(loaded_ideas)}개  로컬 {loaded_loc}건")
        self._log("좌측에서 항목을 골라 수정/제거하거나 새 항목을 추가한 뒤"
                  " '모드 생성' 을 누르세요.")

        messagebox.showinfo(
            "불러오기 완료",
            f"모드: {mod_dir.name}\n"
            f"국기 {len(loaded_flags)} · 이벤트픽처 {len(loaded_events)} · "
            f"로딩화면 {len(loaded_loading)} · UI아이콘 {len(loaded_icons)}\n"
            f"음악 {len(loaded_music)} · 효과음 {len(loaded_sounds)} · "
            f"아이디어 {len(loaded_ideas)} · 로컬 {loaded_loc}\n\n"
            "수정 후 '모드 생성' 을 누르면 같은 모드 자리에 다시 저장됩니다.")

    def _save_state(self):
        save_settings({
            "game_dir": self.game_dir_var.get(),
            "user_dir": self.user_dir_var.get(),
            "output_dir": self.output_dir_var.get(),
            "mod_name": self.mod_name_var.get(),
            "version": self.version_var.get(),
            "install": bool(self.install_var.get()),
        })


def main():
    app = FlagModderApp()
    app.protocol("WM_DELETE_WINDOW",
                 lambda: (app._save_state(), app.destroy()))
    app.mainloop()


if __name__ == "__main__":
    main()
