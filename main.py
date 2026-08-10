import os
import sys
import json
import threading
import tkinter as tk
from tkinter import filedialog
from datetime import datetime
import customtkinter as ctk

# Playwright browser path fix (must run before importing playwright)
_browsers_path = os.path.join(os.environ.get("LOCALAPPDATA", ""), "ms-playwright")
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = _browsers_path

# YouTube API
import google.oauth2.credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# TikTok — Playwright with cookie injection
from playwright.sync_api import sync_playwright

# Windows Toast Notification (optional)
try:
    from plyer import notification as plyer_notify
    HAS_PLYER = True
except ImportError:
    HAS_PLYER = False

# ══════════════════════════════════════════════════════════════════════════
#  LIQUID GLASS DESIGN TOKENS
# ══════════════════════════════════════════════════════════════════════════
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

BG      = "#07070d"
GLASS0  = "#0a0a14"
GLASS1  = "#0e0e1c"
GLASS2  = "#121226"
GLASS3  = "#18182e"
SHIMMER = "#252548"
BORDER0 = "#181832"
BORDER1 = "#22224a"
BORDER2 = "#2e2e6e"
ACCENT  = "#7c3aed"
ACCENTH = "#6d28d9"
ACCENT2 = "#9f64ff"
ACCENT3 = "#c4b5fd"
TEXT    = "#eceeff"
TEXT2   = "#9494c4"
TEXT3   = "#6464a0"
MUTED   = "#3d3d6a"
SUCCESS = "#00e875"
WARNING = "#ffaa00"
ERROR   = "#ff2a50"

# Platform colors
YT    = "#ff3838"
YT_D  = "#d42828"
YT_BG = "#100808"
TT    = "#ff2d55"
TT_D  = "#cc2045"
TT_BG = "#100810"
FB    = "#3a8af7"
FB_D  = "#1f66d4"
FB_BG = "#080e1c"
IG    = "#f02875"
IG_D  = "#c0185a"
IG_BG = "#100810"

# ── FONT LOADING (Anuphan from Google Fonts) ──────────────────────────────
def _init_anuphan_font():
    font_filename = "Anuphan.ttf"
    base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    font_path = os.path.join(base_dir, font_filename)

    if not os.path.exists(font_path):
        try:
            import urllib.request
            url = "https://raw.githubusercontent.com/google/fonts/main/ofl/anuphan/Anuphan%5Bwght%5D.ttf"
            urllib.request.urlretrieve(url, font_path)
        except Exception:
            pass

    if os.path.exists(font_path) and os.name == "nt":
        try:
            import ctypes
            path_buf = ctypes.create_unicode_buffer(os.path.abspath(font_path))
            ctypes.windll.gdi32.AddFontResourceExW(path_buf, 0x10, 0)
        except Exception:
            pass

_init_anuphan_font()
FONT_FAMILY = "Anuphan"
from functools import lru_cache
from PIL import Image

@lru_cache(maxsize=32)
def get_icon(name, size=(18, 18)):
    filename_map = {
        "yt": "yt.png",
        "tt": "tt.png",
        "fb": "fb.png",
        "ig": "ig.png",
        "upload": "upload.png",
        "paste": "paste.png"
    }
    base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    path = os.path.join(base_dir, filename_map.get(name, ""))
    if os.path.exists(path):
        try:
            img = Image.open(path)
            return ctk.CTkImage(light_image=img, dark_image=img, size=size)
        except Exception:
            pass
    return None




@lru_cache(maxsize=64)
def F(size=13, weight="normal"):
    return ctk.CTkFont(family=FONT_FAMILY, size=size + 2, weight=weight)


@lru_cache(maxsize=32)
def Mono(size=11):
    return ctk.CTkFont(family="Consolas", size=size)


def GlassCard(parent, border_color=BORDER1, **kw):
    return ctk.CTkFrame(
        parent,
        fg_color=GLASS1,
        corner_radius=20,
        border_width=1,
        border_color=border_color,
        **kw,
    )


# ══════════════════════════════════════════════════════════════════════════
#  MAIN APP
# ══════════════════════════════════════════════════════════════════════════
class AutoPosterApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("AutoPoster")
        self.geometry("900x960")
        self.minsize(820, 880)
        self.configure(fg_color=BG)

        self.video_path     = ""
        self.is_posting     = False
        self.schedule_timer = None

        self._build_ui()

    # ── UI BUILD ──────────────────────────────────────────────────────────
    def _build_ui(self):
        self._build_header()
        self._build_tabs()
        self._build_action_bar()
        self._build_statusbar()

        if os.path.exists("youtube_token.json"):
            threading.Thread(target=self._fetch_yt_channel_name, daemon=True).start()

        # Background clean orphan temp profiles
        threading.Thread(target=self.clean_playwright_cache, daemon=True).start()

        self._update_settings_visibility_rows()
        self._update_post_button_text()

    # ── HEADER ────────────────────────────────────────────────────────────
    def _build_header(self):
        hdr = ctk.CTkFrame(self, fg_color=GLASS1, corner_radius=0, height=76)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        # Bottom shimmer line
        ctk.CTkFrame(hdr, height=1, fg_color=BORDER1, corner_radius=0).place(
            relx=0, rely=1.0, relwidth=1.0, anchor="sw")

        # ── Left: Logo
        logo = ctk.CTkFrame(hdr, fg_color="transparent")
        logo.pack(side="left", padx=(22, 0), fill="y")

        ctk.CTkLabel(logo, text="✦", font=F(18, "bold"),
                     text_color=ACCENT2).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(logo, text="AutoPoster", font=F(17, "bold"),
                     text_color=TEXT).pack(side="left")
        ctk.CTkLabel(logo, text="v2", font=F(9),
                     text_color=TEXT3).pack(side="left", padx=(5, 0), pady=(10, 0))

        # ── Center: Platform pills
        self.var_yt = tk.BooleanVar(value=True)
        self.var_tt = tk.BooleanVar(value=True)
        self.var_fb = tk.BooleanVar(value=False)
        self.var_ig = tk.BooleanVar(value=False)

        pill_frame = ctk.CTkFrame(hdr, fg_color="transparent")
        pill_frame.pack(side="left", fill="y", padx=10, pady=18, expand=True)

        self._platform_pill(pill_frame, "yt", "YouTube",   YT,  self.var_yt, padx=(0, 6))
        self._platform_pill(pill_frame, "tt", "TikTok",    TT,  self.var_tt, padx=(0, 6))
        self._platform_pill(pill_frame, "fb", "Facebook",  FB,  self.var_fb, padx=(0, 6))
        self._platform_pill(pill_frame, "ig", "Instagram", IG,  self.var_ig, padx=(0, 0))

        # ── Right: Glass Connection Badges
        right = ctk.CTkFrame(hdr, fg_color="transparent")
        right.pack(side="right", padx=(0, 22), fill="y")

        for pkey, name, path_check, attr_name in [
            ("yt", "YT", os.path.exists("youtube_token.json"), "dot_yt"),
            ("tt", "TT", os.path.exists(self._tt_cookies_path()), "dot_tt"),
            ("fb", "FB", os.path.exists(self._fb_cookies_path()), "dot_fb"),
            ("ig", "IG", os.path.exists(self._ig_cookies_path()), "dot_ig")
        ]:
            badge = ctk.CTkFrame(right, fg_color=GLASS2, corner_radius=10, border_width=1, border_color=BORDER1)
            badge.pack(side="left", padx=3)

            ic = get_icon(pkey, size=(14, 14))
            if ic:
                ctk.CTkLabel(badge, image=ic, text="").pack(side="left", padx=(6, 2), pady=4)

            dot_color = SUCCESS if path_check else MUTED
            lbl_dot = ctk.CTkLabel(badge, text=f"● {name}", font=F(9, "bold"), text_color=dot_color)
            lbl_dot.pack(side="left", padx=(2, 6), pady=4)
            setattr(self, attr_name, lbl_dot)

    def _platform_pill(self, parent, pkey, label, color, var, padx=(0, 0)):
        on = var.get()
        frame = ctk.CTkFrame(parent, fg_color=GLASS2, corner_radius=14,
                              border_width=1,
                              border_color=color if on else BORDER0)
        frame.pack(side="left", padx=padx)

        ic = get_icon(pkey, size=(16, 16))
        if ic:
            ctk.CTkLabel(frame, image=ic, text="").pack(side="left", padx=(8, 2), pady=4)

        lbl = ctk.CTkLabel(frame, text=label, font=F(10, "bold"),
                           text_color=color if on else TEXT3)
        lbl.pack(side="left", padx=(4, 6), pady=4)

        def _update(*_):
            is_on = var.get()
            frame.configure(border_color=color if is_on else BORDER0)
            lbl.configure(text_color=color if is_on else TEXT3)
            self._update_settings_visibility_rows()
            self._update_post_button_text()

        ctk.CTkSwitch(frame, text="", variable=var, command=_update,
            width=34, height=16, button_color="#ffffff",
            button_hover_color="#ccccee",
            fg_color=BORDER1, progress_color=color,
            onvalue=True, offvalue=False,
        ).pack(side="left", padx=(0, 8), pady=4)

    # ── TABS ──────────────────────────────────────────────────────────────
    def _build_tabs(self):
        self.tabs = ctk.CTkTabview(self,
            fg_color=BG,
            segmented_button_fg_color=GLASS1,
            segmented_button_selected_color=GLASS3,
            segmented_button_selected_hover_color=SHIMMER,
            segmented_button_unselected_color=GLASS1,
            segmented_button_unselected_hover_color=GLASS2,
            text_color=TEXT2,
            text_color_disabled=TEXT3,
            border_color=BORDER1,
            border_width=0,
        )
        self.tabs.pack(fill="both", expand=True)
        self.tabs.add("  Post  ")
        self.tabs.add("  Accounts  ")

        self._build_post_tab(self.tabs.tab("  Post  "))
        self._build_accounts_tab(self.tabs.tab("  Accounts  "))

    # ── POST TAB ──────────────────────────────────────────────────────────
    def _build_post_tab(self, tab):
        tab.configure(fg_color=BG)
        scroll = ctk.CTkScrollableFrame(tab, fg_color=BG,
            scrollbar_button_color=GLASS3,
            scrollbar_button_hover_color=SHIMMER)
        scroll.pack(fill="both", expand=True)

        P = {"padx": 20, "pady": (0, 14)}

        # ── Video File (Dropzone) ──────────────────────────────────────
        self._section(scroll, "VIDEO FILE", color=ACCENT2, top=16)
        file_card = GlassCard(scroll, border_color=BORDER2)
        file_card.pack(fill="x", **P)

        dropzone = ctk.CTkFrame(file_card, fg_color=GLASS2, corner_radius=16, border_width=1, border_color=BORDER1)
        dropzone.pack(fill="x", padx=14, pady=14)

        up_ic = get_icon("upload", size=(32, 32))
        if up_ic:
            ctk.CTkLabel(dropzone, image=up_ic, text="").pack(pady=(14, 4))
        else:
            ctk.CTkLabel(dropzone, text="☁️", font=F(22)).pack(pady=(12, 2))

        self.lbl_drop_title = ctk.CTkLabel(dropzone, text="Drag & Drop Video File Here", font=F(12, "bold"), text_color=TEXT)
        self.lbl_drop_title.pack(pady=(0, 2))

        self.lbl_file = ctk.CTkLabel(dropzone, text="Supports MP4, MOV files", font=F(10), text_color=TEXT3)
        self.lbl_file.pack(pady=(0, 10))

        btn_box = ctk.CTkFrame(dropzone, fg_color="transparent")
        btn_box.pack(pady=(0, 14))

        self.btn_browse = ctk.CTkButton(btn_box,
            text="Browse Video…", command=self.browse_file,
            fg_color=ACCENT, hover_color=ACCENTH,
            text_color="#ffffff",
            height=38, width=140, font=F(11, "bold"), corner_radius=14)
        self.btn_browse.pack(side="left", padx=4)

        self.btn_clear_file = ctk.CTkButton(btn_box,
            text="✖ Clear", command=self.clear_file,
            fg_color=GLASS3, hover_color=SHIMMER,
            text_color=ERROR, border_color=BORDER1, border_width=1,
            height=38, width=80, font=F(11, "bold"), corner_radius=14)

        # ── Title ──────────────────────────────────────────────────────
        self._section(scroll, "TITLE", color=ACCENT2)
        self.entry_title = ctk.CTkEntry(scroll,
            placeholder_text="Enter video title…",
            height=48, font=F(14),
            fg_color=GLASS2,
            border_color=BORDER1, border_width=1,
            text_color=TEXT, placeholder_text_color=MUTED,
            corner_radius=16)
        self.entry_title.pack(fill="x", **P)

        # ── Description + Hashtags ─────────────────────────────────────
        self._section(scroll, "CAPTION & HASHTAGS", color=ACCENT2)
        two_col = ctk.CTkFrame(scroll, fg_color="transparent")
        two_col.pack(fill="x", **P)
        two_col.grid_columnconfigure(0, weight=3)
        two_col.grid_columnconfigure(1, weight=2)

        self.txt_desc = ctk.CTkTextbox(two_col, height=90, font=F(12),
            fg_color=GLASS2, border_color=BORDER1, border_width=1,
            text_color=TEXT, corner_radius=16,
            scrollbar_button_color=GLASS3)
        self.txt_desc.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        ht_card = ctk.CTkFrame(two_col, fg_color=GLASS2,
            border_color=BORDER2, border_width=1, corner_radius=16)
        ht_card.grid(row=0, column=1, sticky="nsew")
        ht_card.grid_rowconfigure(1, weight=1)
        ht_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(ht_card, text="TAGS (space or comma)", font=F(8, "bold"),
            text_color=TEXT3, anchor="w").grid(
            row=0, column=0, padx=14, pady=(12, 2), sticky="w")

        self.txt_hashtags = ctk.CTkTextbox(ht_card, height=58, font=F(12),
            fg_color="transparent", border_width=0,
            text_color=ACCENT2, scrollbar_button_color=GLASS3)
        self.txt_hashtags.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 10))
        self.txt_hashtags.insert("end", "shorts  viral  fyp")

        # ── Settings Card (Visibility + Schedule) ─────────────────────
        self._section(scroll, "SETTINGS", color=ACCENT2)
        settings_card = GlassCard(scroll)
        settings_card.pack(fill="x", **P)

        # YouTube visibility
        self.yt_vis_row = ctk.CTkFrame(settings_card, fg_color="transparent")
        self.yt_vis_row.pack(fill="x", padx=18, pady=(16, 0))
        self.lbl_yt_vis_icon = ctk.CTkLabel(self.yt_vis_row, text="▶", font=F(11, "bold"), text_color=YT, width=20)
        self.lbl_yt_vis_icon.pack(side="left")
        self.lbl_yt_vis_title = ctk.CTkLabel(self.yt_vis_row, text="YouTube", font=F(11), text_color=TEXT2, width=72, anchor="w")
        self.lbl_yt_vis_title.pack(side="left", padx=8)
        self.yt_privacy = tk.StringVar(value="public")
        self.btn_yt_vis = ctk.CTkSegmentedButton(self.yt_vis_row,
            values=["public", "unlisted", "private"],
            variable=self.yt_privacy, font=F(10),
            fg_color=GLASS2, selected_color=YT_D, selected_hover_color=YT,
            unselected_color=GLASS2, unselected_hover_color=GLASS3,
            text_color=TEXT, corner_radius=10, height=30,
        )
        self.btn_yt_vis.pack(side="left", padx=8)

        ctk.CTkFrame(settings_card, height=1, fg_color=BORDER0, corner_radius=0).pack(
            fill="x", padx=18, pady=8)

        # TikTok visibility
        self.tt_vis_row = ctk.CTkFrame(settings_card, fg_color="transparent")
        self.tt_vis_row.pack(fill="x", padx=18, pady=0)
        self.lbl_tt_vis_icon = ctk.CTkLabel(self.tt_vis_row, text="♪", font=F(11, "bold"), text_color=TT, width=20)
        self.lbl_tt_vis_icon.pack(side="left")
        self.lbl_tt_vis_title = ctk.CTkLabel(self.tt_vis_row, text="TikTok", font=F(11), text_color=TEXT2, width=72, anchor="w")
        self.lbl_tt_vis_title.pack(side="left", padx=8)
        self.tt_privacy = tk.StringVar(value="Everyone")
        self.btn_tt_vis = ctk.CTkSegmentedButton(self.tt_vis_row,
            values=["Everyone", "Friends", "Only me"],
            variable=self.tt_privacy, font=F(10),
            fg_color=GLASS2, selected_color=TT_D, selected_hover_color=TT,
            unselected_color=GLASS2, unselected_hover_color=GLASS3,
            text_color=TEXT, corner_radius=10, height=30,
        )
        self.btn_tt_vis.pack(side="left", padx=8)

        ctk.CTkFrame(settings_card, height=1, fg_color=BORDER0, corner_radius=0).pack(
            fill="x", padx=18, pady=8)

        # Facebook visibility
        self.fb_vis_row = ctk.CTkFrame(settings_card, fg_color="transparent")
        self.fb_vis_row.pack(fill="x", padx=18, pady=0)
        self.lbl_fb_vis_icon = ctk.CTkLabel(self.fb_vis_row, text="f", font=F(11, "bold"), text_color=FB, width=20)
        self.lbl_fb_vis_icon.pack(side="left")
        self.lbl_fb_vis_title = ctk.CTkLabel(self.fb_vis_row, text="Facebook", font=F(11), text_color=TEXT2, width=72, anchor="w")
        self.lbl_fb_vis_title.pack(side="left", padx=8)
        self.fb_privacy = tk.StringVar(value="Public")
        self.btn_fb_vis = ctk.CTkSegmentedButton(self.fb_vis_row,
            values=["Public", "Friends", "Only me"],
            variable=self.fb_privacy, font=F(10),
            fg_color=GLASS2, selected_color=FB_D, selected_hover_color=FB,
            unselected_color=GLASS2, unselected_hover_color=GLASS3,
            text_color=TEXT, corner_radius=10, height=30,
        )
        self.btn_fb_vis.pack(side="left", padx=8)

        ctk.CTkFrame(settings_card, height=1, fg_color=BORDER0, corner_radius=0).pack(
            fill="x", padx=18, pady=8)

        # Instagram visibility
        self.ig_vis_row = ctk.CTkFrame(settings_card, fg_color="transparent")
        self.ig_vis_row.pack(fill="x", padx=18, pady=0)
        self.lbl_ig_vis_icon = ctk.CTkLabel(self.ig_vis_row, text="◉", font=F(11, "bold"), text_color=IG, width=20)
        self.lbl_ig_vis_icon.pack(side="left")
        self.lbl_ig_vis_title = ctk.CTkLabel(self.ig_vis_row, text="Instagram", font=F(11), text_color=TEXT2, width=72, anchor="w")
        self.lbl_ig_vis_title.pack(side="left", padx=8)
        self.lbl_ig_vis_desc = ctk.CTkLabel(self.ig_vis_row, text="Public (default)", font=F(10), text_color=TEXT3)
        self.lbl_ig_vis_desc.pack(side="left", padx=8)

        ctk.CTkFrame(settings_card, height=1, fg_color=BORDER0, corner_radius=0).pack(
            fill="x", padx=18, pady=8)

        # Schedule toggle
        sch_top = ctk.CTkFrame(settings_card, fg_color="transparent")
        sch_top.pack(fill="x", padx=18, pady=(0, 14))
        ctk.CTkLabel(sch_top, text="📅", font=F(12), text_color=ACCENT3, width=20).pack(side="left")
        ctk.CTkLabel(sch_top, text="Schedule", font=F(11), text_color=TEXT2, width=72, anchor="w").pack(side="left", padx=8)

        self.var_schedule = tk.BooleanVar(value=False)
        ctk.CTkSwitch(sch_top, text="", variable=self.var_schedule,
            command=self._toggle_schedule,
            width=44, height=22,
            button_color=TEXT, button_hover_color="#ccccdd",
            fg_color=BORDER1, progress_color=ACCENT,
            onvalue=True, offvalue=False).pack(side="left", padx=8)

        # Hidden schedule datetime inputs
        self.sch_inputs = ctk.CTkFrame(settings_card, fg_color="transparent")
        # packed when schedule ON

        ctk.CTkFrame(self.sch_inputs, height=1, fg_color=BORDER0, corner_radius=0).pack(fill="x", padx=18)
        sch_inner = ctk.CTkFrame(self.sch_inputs, fg_color="transparent")
        sch_inner.pack(fill="x", padx=18, pady=12)

        ctk.CTkLabel(sch_inner, text="Date", font=F(10), text_color=TEXT3, width=36, anchor="w").pack(side="left")
        self.entry_date = ctk.CTkEntry(sch_inner,
            placeholder_text=datetime.now().strftime("%Y-%m-%d"),
            height=36, width=130, font=F(12),
            fg_color=GLASS2, border_color=BORDER1, border_width=1,
            text_color=TEXT, placeholder_text_color=MUTED, corner_radius=10)
        self.entry_date.pack(side="left", padx=(4, 16))

        ctk.CTkLabel(sch_inner, text="Time", font=F(10), text_color=TEXT3, width=36, anchor="w").pack(side="left")
        self.entry_time = ctk.CTkEntry(sch_inner,
            placeholder_text="18:00",
            height=36, width=90, font=F(12),
            fg_color=GLASS2, border_color=BORDER1, border_width=1,
            text_color=TEXT, placeholder_text_color=MUTED, corner_radius=10)
        self.entry_time.pack(side="left", padx=4)

        self.lbl_countdown = ctk.CTkLabel(sch_inner, text="",
            font=F(11, "bold"), text_color=ACCENT2, anchor="w")
        self.lbl_countdown.pack(side="left", padx=12)

        # Quick Schedule Presets
        preset_frame = ctk.CTkFrame(self.sch_inputs, fg_color="transparent")
        preset_frame.pack(fill="x", padx=18, pady=(0, 12))

        ctk.CTkLabel(preset_frame, text="Quick:", font=F(9), text_color=TEXT3).pack(side="left", padx=(0, 8))
        for label, val in [("+1 Hr", "+1h"), ("+3 Hrs", "+3h"), ("Tomorrow 09:00", "tomorrow_09"), ("Tomorrow 18:00", "tomorrow_18")]:
            ctk.CTkButton(preset_frame, text=label, command=lambda v=val: self._apply_schedule_preset(v),
                fg_color=GLASS2, hover_color=GLASS3, text_color=ACCENT2,
                height=26, font=F(9, "bold"), corner_radius=8,
                border_width=1, border_color=BORDER1).pack(side="left", padx=3)

        # ── Activity Log ────────────────────────────────────────────────
        self._section(scroll, "ACTIVITY LOG", color=ACCENT2)
        log_card = GlassCard(scroll)
        log_card.pack(fill="x", padx=20, pady=(0, 20))

        self.log_box = ctk.CTkTextbox(log_card, height=140,
            font=Mono(11),
            fg_color=GLASS0,
            border_width=0,
            text_color=TEXT3,
            corner_radius=16,
            state="disabled",
            scrollbar_button_color=GLASS2,
            scrollbar_button_hover_color=GLASS3)
        self.log_box.pack(fill="x", padx=2, pady=2)

        # alias for compat
        self.txt_log = self.log_box

    # ── ACCOUNTS TAB ──────────────────────────────────────────────────────
    def _build_accounts_tab(self, tab):
        tab.configure(fg_color=BG)
        scroll = ctk.CTkScrollableFrame(tab, fg_color=BG,
            scrollbar_button_color=GLASS3,
            scrollbar_button_hover_color=SHIMMER)
        scroll.pack(fill="both", expand=True)

        # ── YouTube ────────────────────────────────────────────────────
        self._section(scroll, "YOUTUBE ACCOUNT", color=YT, top=20)
        yt_card = ctk.CTkFrame(scroll, fg_color=YT_BG,
            corner_radius=20, border_width=1, border_color=YT)
        yt_card.pack(fill="x", padx=20, pady=(6, 14))

        yt_top = ctk.CTkFrame(yt_card, fg_color="transparent")
        yt_top.pack(fill="x", padx=18, pady=18)

        ctk.CTkLabel(yt_top, text="▶", font=F(22, "bold"),
                     text_color=YT, width=34).pack(side="left")

        yt_info = ctk.CTkFrame(yt_top, fg_color="transparent")
        yt_info.pack(side="left", padx=12, fill="x", expand=True)
        ctk.CTkLabel(yt_info, text="YouTube Shorts",
            font=F(13, "bold"), text_color=TEXT, anchor="w").pack(fill="x")
        self.lbl_yt_account = ctk.CTkLabel(yt_info,
            text="Connected  (loading channel…)" if os.path.exists("youtube_token.json") else "Not connected",
            font=F(11), anchor="w",
            text_color=SUCCESS if os.path.exists("youtube_token.json") else MUTED)
        self.lbl_yt_account.pack(fill="x")

        ctk.CTkButton(yt_top, text="Disconnect", command=self.yt_logout,
            fg_color="transparent", hover_color=YT_BG, text_color=YT,
            height=34, width=110, font=F(11), corner_radius=10,
            border_width=1, border_color=YT).pack(side="right")

        ctk.CTkFrame(yt_card, height=1, fg_color=BORDER0, corner_radius=0).pack(fill="x", padx=18)
        ctk.CTkLabel(yt_card,
            text="💡  Login happens automatically on first upload.\n    Token stored locally in  youtube_token.json",
            font=F(10), text_color=MUTED, justify="left", anchor="w").pack(
            fill="x", padx=18, pady=12)

        # ── TikTok ─────────────────────────────────────────────────────
        self._section(scroll, "TIKTOK ACCOUNT", color=TT, top=8)
        _ck_txt, _ck_color = self._build_cookie_status(self._tt_cookies_path(), "tiktok.com")
        _has_tt = os.path.exists(self._tt_cookies_path())

        tt_card = ctk.CTkFrame(scroll, fg_color=TT_BG,
            corner_radius=20, border_width=1, border_color=TT)
        tt_card.pack(fill="x", padx=20, pady=(6, 14))

        tt_top = ctk.CTkFrame(tt_card, fg_color="transparent")
        tt_top.pack(fill="x", padx=18, pady=18)

        ctk.CTkLabel(tt_top, text="♪", font=F(22, "bold"),
                     text_color=TT, width=34).pack(side="left")

        tt_info = ctk.CTkFrame(tt_top, fg_color="transparent")
        tt_info.pack(side="left", padx=12, fill="x", expand=True)
        ctk.CTkLabel(tt_info, text="TikTok",
            font=F(13, "bold"), text_color=TEXT, anchor="w").pack(fill="x")
        self.lbl_tt_status = ctk.CTkLabel(tt_info,
            text=_ck_txt, font=F(11), anchor="w", text_color=_ck_color)
        self.lbl_tt_status.pack(fill="x")

        ctk.CTkButton(tt_top, text="Clear", command=self.tt_clear_cookies,
            fg_color="transparent", hover_color=TT_BG, text_color=TT,
            height=34, width=70, font=F(11), corner_radius=10,
            border_width=1, border_color=TT).pack(side="right")

        ctk.CTkFrame(tt_card, height=1, fg_color=BORDER0, corner_radius=0).pack(fill="x", padx=18)
        ctk.CTkLabel(tt_card,
            text=(
                "👉  Connect via Cookie-Editor:"
                "\n  1. Install Chrome extension «Cookie-Editor»"
                "\n  2. Go to tiktok.com (while logged in)"
                "\n  3. Cookie-Editor → Export → Export as JSON → Copy"
                "\n  4. Paste below → Import"
            ),
            font=Mono(10), text_color=TEXT3, justify="left", anchor="w"
        ).pack(fill="x", padx=18, pady=(12, 6))

        paste_row_tt = ctk.CTkFrame(tt_card, fg_color="transparent")
        paste_row_tt.pack(fill="x", padx=18, pady=(0, 18))

        self.txt_tt_cookies = ctk.CTkTextbox(paste_row_tt, height=72, font=Mono(10),
            fg_color=GLASS2, border_color=BORDER1, border_width=1,
            text_color=TEXT2, corner_radius=10,
            scrollbar_button_color=GLASS3)
        self.txt_tt_cookies.pack(side="left", fill="x", expand=True)
        self.txt_tt_cookies.insert("end", "Paste JSON cookies here (to update)…" if _has_tt else "Paste JSON cookies here…")

        btn_box_tt = ctk.CTkFrame(paste_row_tt, fg_color="transparent")
        btn_box_tt.pack(side="right", padx=(10, 0))

        paste_ic = get_icon("paste", size=(14, 14))
        ctk.CTkButton(btn_box_tt,
            text=" Paste & Import", image=paste_ic,
            command=lambda: self._paste_clipboard_and_import(self.txt_tt_cookies, self.tt_import_cookies),
            fg_color=GLASS3, hover_color=SHIMMER, text_color=TEXT,
            height=34, width=130, font=F(10, "bold"), corner_radius=8,
            border_width=1, border_color=BORDER2).pack(fill="x", pady=(0, 4))

        ctk.CTkButton(btn_box_tt,
            text="Update" if _has_tt else "Import",
            command=self.tt_import_cookies,
            fg_color=TT, hover_color=TT_D,
            text_color="#fff", height=34, width=130,
            font=F(10, "bold"), corner_radius=8).pack(fill="x")

        # ── Facebook ───────────────────────────────────────────────────
        self._section(scroll, "FACEBOOK ACCOUNT", color=FB, top=8)
        _fb_txt, _fb_color = self._build_cookie_status(self._fb_cookies_path(), "facebook.com")
        _has_fb = os.path.exists(self._fb_cookies_path())

        fb_card = ctk.CTkFrame(scroll, fg_color=FB_BG,
            corner_radius=20, border_width=1, border_color=FB)
        fb_card.pack(fill="x", padx=20, pady=(6, 14))

        fb_top = ctk.CTkFrame(fb_card, fg_color="transparent")
        fb_top.pack(fill="x", padx=18, pady=18)

        ctk.CTkLabel(fb_top, text="f", font=F(22, "bold"),
                     text_color=FB, width=34).pack(side="left")

        fb_info = ctk.CTkFrame(fb_top, fg_color="transparent")
        fb_info.pack(side="left", padx=12, fill="x", expand=True)
        ctk.CTkLabel(fb_info, text="Facebook",
            font=F(13, "bold"), text_color=TEXT, anchor="w").pack(fill="x")
        self.lbl_fb_status = ctk.CTkLabel(fb_info,
            text=_fb_txt, font=F(11), anchor="w", text_color=_fb_color)
        self.lbl_fb_status.pack(fill="x")

        ctk.CTkButton(fb_top, text="Clear", command=self.fb_clear_cookies,
            fg_color="transparent", hover_color=FB_BG, text_color=FB,
            height=34, width=70, font=F(11), corner_radius=10,
            border_width=1, border_color=FB).pack(side="right")

        ctk.CTkFrame(fb_card, height=1, fg_color=BORDER0, corner_radius=0).pack(fill="x", padx=18)
        ctk.CTkLabel(fb_card,
            text=(
                "👉  Connect via Cookie-Editor:"
                "\n  1. Install Chrome extension «Cookie-Editor»"
                "\n  2. Go to facebook.com (while logged in)"
                "\n  3. Cookie-Editor → Export → Export as JSON → Copy"
                "\n  4. Paste below → Import"
            ),
            font=Mono(10), text_color=TEXT3, justify="left", anchor="w"
        ).pack(fill="x", padx=18, pady=(12, 6))

        paste_row_fb = ctk.CTkFrame(fb_card, fg_color="transparent")
        paste_row_fb.pack(fill="x", padx=18, pady=(0, 18))

        self.txt_fb_cookies = ctk.CTkTextbox(paste_row_fb, height=72, font=Mono(10),
            fg_color=GLASS2, border_color=BORDER1, border_width=1,
            text_color=TEXT2, corner_radius=10,
            scrollbar_button_color=GLASS3)
        self.txt_fb_cookies.pack(side="left", fill="x", expand=True)
        self.txt_fb_cookies.insert("end", "Paste JSON cookies here (to update)…" if _has_fb else "Paste JSON cookies here…")

        btn_box_fb = ctk.CTkFrame(paste_row_fb, fg_color="transparent")
        btn_box_fb.pack(side="right", padx=(10, 0))

        paste_ic = get_icon("paste", size=(14, 14))
        ctk.CTkButton(btn_box_fb,
            text=" Paste & Import", image=paste_ic,
            command=lambda: self._paste_clipboard_and_import(self.txt_fb_cookies, self.fb_import_cookies),
            fg_color=GLASS3, hover_color=SHIMMER, text_color=TEXT,
            height=34, width=130, font=F(10, "bold"), corner_radius=8,
            border_width=1, border_color=BORDER2).pack(fill="x", pady=(0, 4))

        ctk.CTkButton(btn_box_fb,
            text="Update" if _has_fb else "Import",
            command=self.fb_import_cookies,
            fg_color=FB, hover_color=FB_D,
            text_color="#fff", height=34, width=130,
            font=F(10, "bold"), corner_radius=8).pack(fill="x")

        # ── Instagram ──────────────────────────────────────────────────
        self._section(scroll, "INSTAGRAM ACCOUNT", color=IG, top=8)
        _ig_txt, _ig_color = self._build_cookie_status(self._ig_cookies_path(), "instagram.com")
        _has_ig = os.path.exists(self._ig_cookies_path())

        ig_card = ctk.CTkFrame(scroll, fg_color=IG_BG,
            corner_radius=20, border_width=1, border_color=IG)
        ig_card.pack(fill="x", padx=20, pady=(6, 20))

        ig_top = ctk.CTkFrame(ig_card, fg_color="transparent")
        ig_top.pack(fill="x", padx=18, pady=18)

        ctk.CTkLabel(ig_top, text="◉", font=F(22, "bold"),
                     text_color=IG, width=34).pack(side="left")

        ig_info = ctk.CTkFrame(ig_top, fg_color="transparent")
        ig_info.pack(side="left", padx=12, fill="x", expand=True)
        ctk.CTkLabel(ig_info, text="Instagram",
            font=F(13, "bold"), text_color=TEXT, anchor="w").pack(fill="x")
        self.lbl_ig_status = ctk.CTkLabel(ig_info,
            text=_ig_txt, font=F(11), anchor="w", text_color=_ig_color)
        self.lbl_ig_status.pack(fill="x")

        ctk.CTkButton(ig_top, text="Clear", command=self.ig_clear_cookies,
            fg_color="transparent", hover_color=IG_BG, text_color=IG,
            height=34, width=70, font=F(11), corner_radius=10,
            border_width=1, border_color=IG).pack(side="right")

        ctk.CTkFrame(ig_card, height=1, fg_color=BORDER0, corner_radius=0).pack(fill="x", padx=18)
        ctk.CTkLabel(ig_card,
            text=(
                "👉  Connect via Cookie-Editor:"
                "\n  1. Install Chrome extension «Cookie-Editor»"
                "\n  2. Go to instagram.com (while logged in)"
                "\n  3. Cookie-Editor → Export → Export as JSON → Copy"
                "\n  4. Paste below → Import"
            ),
            font=Mono(10), text_color=TEXT3, justify="left", anchor="w"
        ).pack(fill="x", padx=18, pady=(12, 6))

        paste_row_ig = ctk.CTkFrame(ig_card, fg_color="transparent")
        paste_row_ig.pack(fill="x", padx=18, pady=(0, 18))

        self.txt_ig_cookies = ctk.CTkTextbox(paste_row_ig, height=72, font=Mono(10),
            fg_color=GLASS2, border_color=BORDER1, border_width=1,
            text_color=TEXT2, corner_radius=10,
            scrollbar_button_color=GLASS3)
        self.txt_ig_cookies.pack(side="left", fill="x", expand=True)
        self.txt_ig_cookies.insert("end", "Paste JSON cookies here (to update)…" if _has_ig else "Paste JSON cookies here…")

        btn_box_ig = ctk.CTkFrame(paste_row_ig, fg_color="transparent")
        btn_box_ig.pack(side="right", padx=(10, 0))

        paste_ic = get_icon("paste", size=(14, 14))
        ctk.CTkButton(btn_box_ig,
            text=" Paste & Import", image=paste_ic,
            command=lambda: self._paste_clipboard_and_import(self.txt_ig_cookies, self.ig_import_cookies),
            fg_color=GLASS3, hover_color=SHIMMER, text_color=TEXT,
            height=34, width=130, font=F(10, "bold"), corner_radius=8,
            border_width=1, border_color=BORDER2).pack(fill="x", pady=(0, 4))

        ctk.CTkButton(btn_box_ig,
            text="Update" if _has_ig else "Import",
            command=self.ig_import_cookies,
            fg_color=IG, hover_color=IG_D,
            text_color="#fff", height=34, width=130,
            font=F(10, "bold"), corner_radius=8).pack(fill="x")

        # ── SYSTEM MAINTENANCE ──────────────────────────────────────────
        self._section(scroll, "SYSTEM MAINTENANCE", color=ACCENT2, top=16)
        maint_card = GlassCard(scroll, border_color=BORDER1)
        maint_card.pack(fill="x", padx=20, pady=(6, 24))

        maint_inner = ctk.CTkFrame(maint_card, fg_color="transparent")
        maint_inner.pack(fill="x", padx=18, pady=16)

        maint_text = ctk.CTkFrame(maint_inner, fg_color="transparent")
        maint_text.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(maint_text, text="Playwright Temp Cache", font=F(12, "bold"), text_color=TEXT, anchor="w").pack(fill="x")
        ctk.CTkLabel(maint_text, text="Cleans up temporary Chromium profile & cache files from %TEMP%", font=F(10), text_color=TEXT3, anchor="w").pack(fill="x")

        ctk.CTkButton(maint_inner, text="🧹 Clean Cache", command=self.manual_clean_cache,
            fg_color=GLASS3, hover_color=SHIMMER, text_color=ACCENT2,
            height=38, width=130, font=F(11, "bold"), corner_radius=12,
            border_width=1, border_color=BORDER2).pack(side="right", padx=(10, 0))

    # ── ACTION BAR ────────────────────────────────────────────────────────
    def _build_action_bar(self):
        ctk.CTkFrame(self, height=1, fg_color=BORDER1, corner_radius=0).pack(fill="x")
        bar = ctk.CTkFrame(self, fg_color=GLASS1, corner_radius=0, height=88)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        inner = ctk.CTkFrame(bar, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=20, pady=12)

        # Thin progress bar on top
        self.progress_bar = ctk.CTkProgressBar(inner,
            mode="determinate", height=6, corner_radius=3,
            fg_color=GLASS2, progress_color=ACCENT2)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", pady=(0, 10))

        # Bottom row
        bottom_row = ctk.CTkFrame(inner, fg_color="transparent")
        bottom_row.pack(fill="x")

        self.lbl_progress = ctk.CTkLabel(bottom_row,
            text="Idle", font=F(11), text_color=MUTED, anchor="w")
        self.lbl_progress.pack(side="left", fill="y")

        self.btn_post = ctk.CTkButton(bottom_row,
            text="▶  Post Now",
            command=self._post_now,
            fg_color=ACCENT, hover_color=ACCENTH,
            text_color="#ffffff",
            height=52, width=220, font=F(14, "bold"), corner_radius=24)
        self.btn_post.pack(side="right")

    # ── STATUS BAR ────────────────────────────────────────────────────────
    def _build_statusbar(self):
        ctk.CTkFrame(self, height=1, fg_color=BORDER0, corner_radius=0).pack(fill="x")
        self.lbl_status = ctk.CTkLabel(self,
            text="  Ready", font=F(10), text_color=MUTED,
            fg_color=GLASS0, anchor="w", height=28)
        self.lbl_status.pack(fill="x", ipady=2)

    # ── SECTION HEADER ────────────────────────────────────────────────────
    def _section(self, parent, text, color=None, top=14):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=(top, 6))

        dot_color = color or ACCENT2
        ctk.CTkLabel(row, text="●", font=F(8),
                     text_color=dot_color, width=14).pack(side="left")
        ctk.CTkLabel(row, text=text, font=F(9, "bold"),
                     text_color=TEXT3, anchor="w").pack(side="left", padx=(4, 0))

    # ══════════════════════════════════════════════════════════════════════
    #  SCHEDULE
    # ══════════════════════════════════════════════════════════════════════
    def _toggle_schedule(self):
        if self.var_schedule.get():
            self.sch_inputs.pack(fill="x")
            if not self.entry_date.get():
                self.entry_date.insert(0, datetime.now().strftime("%Y-%m-%d"))
        else:
            self.sch_inputs.pack_forget()
            if self.schedule_timer:
                self.schedule_timer.cancel()
                self.schedule_timer = None
            self.lbl_countdown.configure(text="")

    def _get_schedule_datetime(self):
        if not self.var_schedule.get():
            return None
        date_str = self.entry_date.get().strip() or datetime.now().strftime("%Y-%m-%d")
        time_str = self.entry_time.get().strip() or "00:00"
        try:
            target = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        except ValueError:
            raise ValueError("Invalid date/time — use YYYY-MM-DD and HH:MM")
        if target <= datetime.now():
            raise ValueError("Scheduled time must be in the future")
        return target

    def _parse_schedule_datetime(self):
        return self._get_schedule_datetime()

    def _start_countdown(self, target_dt, callback):
        def tick():
            remaining = target_dt - datetime.now()
            if remaining.total_seconds() <= 0:
                self.lbl_countdown.configure(text="Starting…", text_color=SUCCESS)
                callback()
                return
            h, rem = divmod(int(remaining.total_seconds()), 3600)
            m, s   = divmod(rem, 60)
            self.lbl_countdown.configure(
                text=f"⏰  {h:02d}:{m:02d}:{s:02d}", text_color=ACCENT2)
            self.schedule_timer = threading.Timer(1.0, tick)
            self.schedule_timer.daemon = True
            self.schedule_timer.start()
        tick()

    # ══════════════════════════════════════════════════════════════════════
    #  HASHTAG BUILDER
    # ══════════════════════════════════════════════════════════════════════
    def _build_hashtags(self):
        raw = self.txt_hashtags.get("1.0", tk.END).strip()
        if not raw:
            return ""
        tags = [t.strip().lstrip("#") for t in raw.replace(",", " ").split() if t.strip()]
        return " ".join(f"#{t}" for t in tags if t)

    # ══════════════════════════════════════════════════════════════════════
    #  POSTING
    # ══════════════════════════════════════════════════════════════════════
    def _post_now(self):
        if self.is_posting:
            return

        active = (self.var_yt.get() or self.var_tt.get() or
                  self.var_fb.get() or self.var_ig.get())
        if not active:
            self.update_status("Select at least one platform", ERROR)
            return
        title = self.entry_title.get().strip()
        if not title:
            self.update_status("Title is required", ERROR)
            return
        if not self.video_path:
            self.update_status("Select a video file", ERROR)
            return

        hashtags  = self._build_hashtags()
        desc      = self.txt_desc.get("1.0", tk.END).strip()
        full_desc = f"{desc}\n\n{hashtags}".strip() if hashtags else desc
        item      = {"video_path": self.video_path, "title": title, "desc": full_desc}

        try:
            target_dt = self._get_schedule_datetime()
        except ValueError as e:
            self.update_status(str(e), ERROR)
            return

        self._set_ui_posting(True)

        if target_dt:
            self._log(f"Scheduled for {target_dt.strftime('%Y-%m-%d  %H:%M')}")
            self._start_countdown(target_dt, lambda: threading.Thread(
                target=self._run_posting, args=([item],), daemon=True).start())
        else:
            threading.Thread(target=self._run_posting, args=([item],), daemon=True).start()

    def _set_ui_posting(self, posting: bool):
        self.is_posting = posting
        state = "disabled" if posting else "normal"
        self.btn_post.configure(
            state=state,
            text="Posting…" if posting else "▶  Post Now")
        self.btn_browse.configure(state=state)
        if not posting:
            self.progress_bar.set(0)
            self.lbl_progress.configure(text="Idle", text_color=MUTED)

    def _set_progress(self, value: float, label: str, color=None):
        self.progress_bar.set(max(0.0, min(1.0, value)))
        self.lbl_progress.configure(text=label, text_color=color or TEXT2)
        self.update_idletasks()

    def _run_posting(self, items: list):
        post_yt = self.var_yt.get()
        post_tt = self.var_tt.get()
        post_fb = self.var_fb.get()
        post_ig = self.var_ig.get()
        total   = len(items)

        yt_ok = tt_ok = fb_ok = ig_ok = False

        try:
            for i, item in enumerate(items, 1):
                self._log(f"─── [{i}/{total}]  {os.path.basename(item['video_path'])} ───")

                if post_yt:
                    try:
                        self.update_status("YouTube uploading…", YT)
                        self._set_progress(0, "YouTube — starting…", YT)
                        self.upload_to_youtube(item["video_path"], item["title"], item["desc"])
                        yt_ok = True
                        self._set_progress(1.0, "YouTube ✓", SUCCESS)
                        self.update_status("YouTube upload complete ✓", SUCCESS)
                    except Exception as e:
                        self.update_status(f"YouTube failed: {e}", ERROR)
                        self._set_progress(0, "YouTube error", ERROR)
                        self._log(f"YouTube error detail: {e}")

                if post_tt:
                    try:
                        self.update_status("TikTok uploading…", TT)
                        self._set_progress(0.5 if yt_ok else 0, "TikTok — starting…", TT)
                        self.upload_to_tiktok(item["video_path"], item["title"])
                        tt_ok = True
                        self._set_progress(1.0, "TikTok ✓", SUCCESS)
                        self.update_status("TikTok upload complete ✓", SUCCESS)
                    except Exception as e:
                        self.update_status(f"TikTok failed: {e}", ERROR)
                        self._set_progress(0, "TikTok error", ERROR)
                        self._log(f"TikTok error detail: {e}")

                if post_fb:
                    try:
                        self.update_status("Facebook uploading…", FB)
                        self._set_progress(0, "Facebook — starting…", FB)
                        self.upload_to_facebook(item["video_path"], item["title"], item["desc"])
                        fb_ok = True
                        self._set_progress(1.0, "Facebook ✓", SUCCESS)
                        self.update_status("Facebook upload complete ✓", SUCCESS)
                    except Exception as e:
                        self.update_status(f"Facebook failed: {e}", ERROR)
                        self._set_progress(0, "Facebook error", ERROR)
                        self._log(f"Facebook error detail: {e}")

                if post_ig:
                    try:
                        self.update_status("Instagram uploading…", IG)
                        self._set_progress(0, "Instagram — starting…", IG)
                        self.upload_to_instagram(item["video_path"], item["title"], item["desc"])
                        ig_ok = True
                        self._set_progress(1.0, "Instagram ✓", SUCCESS)
                        self.update_status("Instagram upload complete ✓", SUCCESS)
                    except Exception as e:
                        self.update_status(f"Instagram failed: {e}", ERROR)
                        self._set_progress(0, "Instagram error", ERROR)
                        self._log(f"Instagram error detail: {e}")

        except Exception as e:
            self.update_status(f"Unexpected error: {e}", ERROR)
            self._log(f"Unexpected error: {e}")

        finally:
            results = []
            if post_yt:
                results.append(f"YouTube {'✓' if yt_ok else '✗'}")
            if post_tt:
                results.append(f"TikTok {'✓' if tt_ok else '✗'}")
            if post_fb:
                results.append(f"Facebook {'✓' if fb_ok else '✗'}")
            if post_ig:
                results.append(f"Instagram {'✓' if ig_ok else '✗'}")

            flagged  = [(yt_ok, post_yt), (tt_ok, post_tt), (fb_ok, post_fb), (ig_ok, post_ig)]
            all_ok   = all(v for v, flag in flagged if flag)
            any_ok   = any(v for v, flag in flagged if flag)
            summary  = "Done — " + "  |  ".join(results) if results else "Nothing posted"
            color    = SUCCESS if all_ok else (WARNING if any_ok else ERROR)

            self.update_status(summary, color)
            self._notify_windows("AutoPoster", summary)
            self._set_ui_posting(False)
            self.lbl_countdown.configure(text="")

    # ══════════════════════════════════════════════════════════════════════
    #  WINDOWS NOTIFICATION
    # ══════════════════════════════════════════════════════════════════════
    def _notify_windows(self, title, message):
        def _do():
            if HAS_PLYER:
                try:
                    plyer_notify.notify(title=title, message=message,
                        app_name="AutoPoster", timeout=6)
                    return
                except Exception:
                    pass
            # Fallback: PowerShell toast
            try:
                import subprocess
                safe_msg = message.replace("'", "")
                ps = (
                    f"[void][Windows.UI.Notifications.ToastNotificationManager,"
                    f"Windows.UI.Notifications,ContentType=WindowsRuntime];"
                    f"$x=[Windows.Data.Xml.Dom.XmlDocument,Windows.Data.Xml.Dom,"
                    f"ContentType=WindowsRuntime]::New();"
                    f"$x.LoadXml('<toast><visual><binding template=\"ToastText02\">"
                    f"<text id=\"1\">{title}</text>"
                    f"<text id=\"2\">{safe_msg}</text>"
                    f"</binding></visual></toast>');"
                    f"[Windows.UI.Notifications.ToastNotificationManager]"
                    f"::CreateToastNotifier('AutoPoster')"
                    f".Show([Windows.UI.Notifications.ToastNotification]::New($x))"
                )
                subprocess.Popen(
                    ["powershell", "-WindowStyle", "Hidden", "-Command", ps],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass
        threading.Thread(target=_do, daemon=True).start()

    # ══════════════════════════════════════════════════════════════════════
    #  HELPERS
    # ══════════════════════════════════════════════════════════════════════
    def _log(self, msg):
        ts   = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}]  {msg}\n"
        self.log_box.configure(state="normal")
        self.log_box.insert("end", line)
        try:
            line_count = int(self.log_box.index("end-1c").split(".")[0])
            if line_count > 300:
                self.log_box.delete("1.0", f"{line_count - 300}.0")
        except Exception:
            pass
        self.log_box.see("end")
        self.log_box.configure(state="disabled")
        print(line.strip())

    def update_status(self, text, color=MUTED):
        def _apply():
            self.lbl_status.configure(text=f"  {text}", text_color=color)
            self._log(text)
        self.after(0, _apply)


    # ── UX ENHANCEMENT HELPERS ──────────────────────────────────────────
    def _update_post_button_text(self):
        if self.is_posting:
            self.btn_post.configure(text="Posting…", state="disabled")
            return
        active = []
        if self.var_yt.get(): active.append("YouTube")
        if self.var_tt.get(): active.append("TikTok")
        if self.var_fb.get(): active.append("Facebook")
        if self.var_ig.get(): active.append("Instagram")

        if not active:
            self.btn_post.configure(text="▶ Select a Platform", fg_color=GLASS3, state="disabled")
        elif len(active) == 1:
            self.btn_post.configure(text=f"▶ Post to {active[0]}", fg_color=ACCENT, state="normal")
        else:
            self.btn_post.configure(text=f"▶ Post to {len(active)} Platforms", fg_color=ACCENT, state="normal")

    def _update_settings_visibility_rows(self):
        if hasattr(self, "btn_yt_vis"):
            yt_on = self.var_yt.get()
            self.lbl_yt_vis_icon.configure(text_color=YT if yt_on else MUTED)
            self.lbl_yt_vis_title.configure(text_color=TEXT2 if yt_on else MUTED)
            self.btn_yt_vis.configure(state="normal" if yt_on else "disabled")

        if hasattr(self, "btn_tt_vis"):
            tt_on = self.var_tt.get()
            self.lbl_tt_vis_icon.configure(text_color=TT if tt_on else MUTED)
            self.lbl_tt_vis_title.configure(text_color=TEXT2 if tt_on else MUTED)
            self.btn_tt_vis.configure(state="normal" if tt_on else "disabled")

        if hasattr(self, "btn_fb_vis"):
            fb_on = self.var_fb.get()
            self.lbl_fb_vis_icon.configure(text_color=FB if fb_on else MUTED)
            self.lbl_fb_vis_title.configure(text_color=TEXT2 if fb_on else MUTED)
            self.btn_fb_vis.configure(state="normal" if fb_on else "disabled")

        if hasattr(self, "lbl_ig_vis_icon"):
            ig_on = self.var_ig.get()
            self.lbl_ig_vis_icon.configure(text_color=IG if ig_on else MUTED)
            self.lbl_ig_vis_title.configure(text_color=TEXT2 if ig_on else MUTED)
            self.lbl_ig_vis_desc.configure(text_color=TEXT3 if ig_on else MUTED)

    def _paste_clipboard_and_import(self, textbox, import_func):
        try:
            content = self.clipboard_get().strip()
            if content:
                textbox.delete("1.0", tk.END)
                textbox.insert("end", content)
                import_func()
                self.update_status("Imported from Clipboard ✓", SUCCESS)
            else:
                self.update_status("Clipboard is empty", ERROR)
        except Exception as e:
            self.update_status(f"Clipboard paste failed: {e}", ERROR)

    def _apply_schedule_preset(self, preset_type):
        from datetime import datetime, timedelta
        now = datetime.now()
        if preset_type == "+1h":
            target = now + timedelta(hours=1)
        elif preset_type == "+3h":
            target = now + timedelta(hours=3)
        elif preset_type == "tomorrow_09":
            target = (now + timedelta(days=1)).replace(hour=9, minute=0)
        elif preset_type == "tomorrow_18":
            target = (now + timedelta(days=1)).replace(hour=18, minute=0)
        else:
            return

        self.entry_date.delete(0, tk.END)
        self.entry_date.insert(0, target.strftime("%Y-%m-%d"))
        self.entry_time.delete(0, tk.END)
        self.entry_time.insert(0, target.strftime("%H:%M"))

    def clear_file(self):
        self.video_path = ""
        self.lbl_file.configure(text="Supports MP4, MOV files", text_color=TEXT3)
        if hasattr(self, "btn_clear_file"):
            self.btn_clear_file.pack_forget()


    # ── CACHE MANAGEMENT ────────────────────────────────────────────────
    def clean_playwright_cache(self):
        import glob, shutil
        temp_dir = os.environ.get("TEMP", "")
        freed_bytes = 0
        cleaned_count = 0
        patterns = [
            os.path.join(temp_dir, "playwright*"),
            os.path.join(temp_dir, "puppeteer*"),
        ]
        for pattern in patterns:
            for path in glob.glob(pattern):
                try:
                    if os.path.isdir(path):
                        size = sum(os.path.getsize(os.path.join(dirpath, filename))
                                   for dirpath, _, filenames in os.walk(path)
                                   for filename in filenames)
                        shutil.rmtree(path, ignore_errors=True)
                        freed_bytes += size
                        cleaned_count += 1
                except Exception:
                    pass
        return cleaned_count, freed_bytes / (1024 * 1024)

    def manual_clean_cache(self):
        count, mb = self.clean_playwright_cache()
        if count > 0:
            self.update_status(f"Cleaned {count} Playwright cache folders (Freed {mb:.1f} MB) ✓", SUCCESS)
        else:
            self.update_status("Playwright temp cache is clean ✓", SUCCESS)

    def _setup_fast_route_blocking(self, page):
        """Block heavy tracking/analytics requests to speed up upload page load times by 30-50%."""
        try:
            blocked_keywords = ["google-analytics", "analytics.tiktok", "connect.facebook.net", "doubleclick", "scorecardresearch"]
            page.route(lambda url: any(b in url for b in blocked_keywords), lambda route: route.abort())
        except Exception:
            pass

    def browse_file(self):
        path = filedialog.askopenfilename(
            filetypes=[("Video files", "*.mp4 *.mov *.MP4 *.MOV")])
        if path:
            self.video_path = path
            size_mb = os.path.getsize(path) / (1024 * 1024)
            name    = os.path.basename(path)
            display = f"Selected: {name}  ({size_mb:.1f} MB)"
            self.lbl_file.configure(text=display, text_color=SUCCESS)
            if hasattr(self, "btn_clear_file"):
                self.btn_clear_file.pack(side="left", padx=4)

    def _build_cookie_status(self, cookies_path, domain):
        """Return (status_text, text_color) for a cookie file."""
        if not os.path.exists(cookies_path):
            return "Not connected", MUTED
        try:
            import datetime as _dt
            with open(cookies_path, "r", encoding="utf-8") as f:
                cookies_list = json.load(f)
            count   = len(cookies_list)
            saved   = _dt.datetime.fromtimestamp(
                os.path.getmtime(cookies_path)).strftime("%Y-%m-%d")

            key_names = ("sessionid", "sid_tt", "sid_guard", "passport_auth_token",
                         "c_user", "xs", "sessionid_ss", "csrftoken")
            earliest = None
            for c in cookies_list:
                if c.get("name", "").lower() in key_names:
                    exp = c.get("expirationDate") or c.get("expires")
                    if exp and float(exp) > 0:
                        exp_dt = _dt.datetime.fromtimestamp(float(exp))
                        if earliest is None or exp_dt < earliest:
                            earliest = exp_dt

            if earliest:
                days_left = (earliest - _dt.datetime.now()).days
                if days_left <= 0:
                    return f"Cookies saved ✓  ({count})  · ⚠ Session may be expired", ERROR
                elif days_left <= 7:
                    return f"Cookies saved ✓  ({count})  · expires in {days_left}d", ERROR
                elif days_left <= 14:
                    return f"Cookies saved ✓  ({count})  · expires in {days_left}d", WARNING
                else:
                    return f"Cookies saved ✓  ({count} cookies · {saved})", SUCCESS
            return f"Cookies saved ✓  ({count} cookies · {saved})", SUCCESS
        except Exception:
            return "Cookies present (unreadable)", WARNING

    # ══════════════════════════════════════════════════════════════════════
    #  YOUTUBE ACCOUNT
    # ══════════════════════════════════════════════════════════════════════
    def _fetch_yt_channel_name(self):
        try:
            SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
            creds  = google.oauth2.credentials.Credentials.from_authorized_user_file(
                "youtube_token.json", SCOPES)
            if creds and creds.valid:
                yt    = build("youtube", "v3", credentials=creds)
                resp  = yt.channels().list(part="snippet", mine=True).execute()
                items = resp.get("items", [])
                if items:
                    name = items[0]["snippet"]["title"]
                    self.lbl_yt_account.configure(text=f"● {name}", text_color=SUCCESS)
                    self.dot_yt.configure(text_color=SUCCESS)
                    return
            self.lbl_yt_account.configure(
                text="Token expired — will refresh on next upload", text_color=WARNING)
        except Exception:
            pass

    def yt_logout(self):
        if os.path.exists("youtube_token.json"):
            os.remove("youtube_token.json")
        self.lbl_yt_account.configure(text="Not connected", text_color=MUTED)
        self.dot_yt.configure(text_color=MUTED)
        self._log("YouTube token removed — will re-authenticate on next upload")

    # ══════════════════════════════════════════════════════════════════════
    #  TIKTOK — COOKIE IMPORT
    # ══════════════════════════════════════════════════════════════════════
    def _tt_cookies_path(self):
        base = os.path.dirname(os.path.abspath(sys.argv[0]))
        return os.path.join(base, "tiktok_cookies.json")

    def tt_import_cookies(self):
        raw = self.txt_tt_cookies.get("1.0", tk.END).strip()
        if not raw or raw == "Paste JSON cookies here…":
            self.update_status("กรุณา Paste cookies JSON ก่อน", ERROR)
            return
        try:
            cookies = json.loads(raw)
            # เก็บเฉพาะ field ที่จำเป็น
            clean = [
                {
                    "name":   c["name"],
                    "value":  c["value"],
                    "domain": c.get("domain", ".tiktok.com"),
                    "path":   c.get("path", "/"),
                }
                for c in cookies
                if "name" in c and "value" in c
            ]
            if not clean:
                raise ValueError("No valid cookies found")
            with open(self._tt_cookies_path(), "w", encoding="utf-8") as f:
                json.dump(clean, f, ensure_ascii=False, indent=2)
            # อัปเดต UI
            self.lbl_tt_status.configure(
                text=f"Cookies imported ✓  ({len(clean)} cookies)",
                text_color=SUCCESS)
            self.dot_tt.configure(text_color=SUCCESS)
            self.update_status(
                f"TikTok cookies saved ✓  ({len(clean)} cookies)", SUCCESS)
            self.txt_tt_cookies.delete("1.0", tk.END)
            self.txt_tt_cookies.insert("end", "Paste JSON cookies here…")
            self._log(f"Imported {len(clean)} TikTok cookies")
        except Exception as e:
            self.update_status(f"Import failed: {e}", ERROR)

    def tt_clear_cookies(self):
        path = self._tt_cookies_path()
        if os.path.exists(path):
            os.remove(path)
        if os.path.exists("tiktok_session.json"):
            os.remove("tiktok_session.json")
        self.lbl_tt_status.configure(text="Not connected", text_color=MUTED)
        self.dot_tt.configure(text_color=MUTED)
        self._log("TikTok cookies cleared")

    # ══════════════════════════════════════════════════════════════════════
    #  FACEBOOK — COOKIE IMPORT
    # ══════════════════════════════════════════════════════════════════════
    def _fb_cookies_path(self):
        base = os.path.dirname(os.path.abspath(sys.argv[0]))
        return os.path.join(base, "facebook_cookies.json")

    def fb_import_cookies(self):
        self._import_cookies_generic(
            textbox=self.txt_fb_cookies,
            cookies_path=self._fb_cookies_path(),
            default_domain=".facebook.com",
            status_label=self.lbl_fb_status,
            dot_label=self.dot_fb,
            platform="Facebook",
        )

    def fb_clear_cookies(self):
        path = self._fb_cookies_path()
        if os.path.exists(path):
            os.remove(path)
        self.lbl_fb_status.configure(text="Not connected", text_color=MUTED)
        self.dot_fb.configure(text_color=MUTED)
        self._log("Facebook cookies cleared")

    # ══════════════════════════════════════════════════════════════════════
    #  INSTAGRAM — COOKIE IMPORT
    # ══════════════════════════════════════════════════════════════════════
    def _ig_cookies_path(self):
        base = os.path.dirname(os.path.abspath(sys.argv[0]))
        return os.path.join(base, "instagram_cookies.json")

    def ig_import_cookies(self):
        self._import_cookies_generic(
            textbox=self.txt_ig_cookies,
            cookies_path=self._ig_cookies_path(),
            default_domain=".instagram.com",
            status_label=self.lbl_ig_status,
            dot_label=self.dot_ig,
            platform="Instagram",
        )

    def ig_clear_cookies(self):
        path = self._ig_cookies_path()
        if os.path.exists(path):
            os.remove(path)
        self.lbl_ig_status.configure(text="Not connected", text_color=MUTED)
        self.dot_ig.configure(text_color=MUTED)
        self._log("Instagram cookies cleared")

    # ══════════════════════════════════════════════════════════════════════
    #  GENERIC COOKIE IMPORT HELPER
    # ══════════════════════════════════════════════════════════════════════
    def _import_cookies_generic(self, textbox, cookies_path, default_domain,
                                 status_label, dot_label, platform):
        raw = textbox.get("1.0", tk.END).strip()
        placeholder_texts = ("Paste JSON cookies here…",
                              "Paste JSON cookies here (to update)…")
        if not raw or raw in placeholder_texts:
            self.update_status(f"Please paste {platform} cookies JSON first", ERROR)
            return
        try:
            cookies = json.loads(raw)
            clean = [
                {
                    "name":   c["name"],
                    "value":  c["value"],
                    "domain": c.get("domain", default_domain),
                    "path":   c.get("path", "/"),
                }
                for c in cookies
                if "name" in c and "value" in c
            ]
            if not clean:
                raise ValueError("No valid cookies found")
            with open(cookies_path, "w", encoding="utf-8") as f:
                json.dump(clean, f, ensure_ascii=False, indent=2)
            status_label.configure(
                text=f"Cookies imported ✓  ({len(clean)} cookies)",
                text_color=SUCCESS)
            dot_label.configure(text_color=SUCCESS)
            self.update_status(f"{platform} cookies saved ✓  ({len(clean)} cookies)", SUCCESS)
            textbox.delete("1.0", tk.END)
            textbox.insert("end", "Paste JSON cookies here (to update)…")
            self._log(f"Imported {len(clean)} {platform} cookies")
        except Exception as e:
            self.update_status(f"Import failed: {e}", ERROR)

    # ======================================================================
    #  YOUTUBE UPLOAD
    # ======================================================================
    def upload_to_youtube(self, video_path, title, desc):
        SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
        creds  = None

        if os.path.exists("youtube_token.json"):
            creds = google.oauth2.credentials.Credentials.from_authorized_user_file(
                "youtube_token.json", SCOPES)

        if creds and creds.expired and creds.refresh_token:
            try:
                self._log("Refreshing YouTube token...")
                creds.refresh(Request())
                with open("youtube_token.json", "w") as f:
                    f.write(creds.to_json())
            except Exception:
                self._log("Token refresh failed -- will re-authenticate")
                creds = None

        if not creds or not creds.valid:
            if not os.path.exists("credentials.json"):
                raise Exception(
                    "credentials.json not found -- place it next to the app")
            flow  = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
            with open("youtube_token.json", "w") as f:
                f.write(creds.to_json())
            threading.Thread(target=self._fetch_yt_channel_name, daemon=True).start()

        youtube    = build("youtube", "v3", credentials=creds)
        full_title = title if "#Shorts" in title else f"{title} #Shorts"
        privacy    = self.yt_privacy.get()

        body = {
            "snippet": {
                "title":       full_title,
                "description": desc,
                "tags":        ["Shorts", "YouTubeShorts", "viral"],
                "categoryId":  "22",
            },
            "status": {"privacyStatus": privacy},
        }

        self._log(f"YouTube: \"{full_title}\"  [{privacy}]")
        media   = MediaFileUpload(
            video_path, chunksize=1024 * 1024, resumable=True, mimetype="video/*")
        request = youtube.videos().insert(
            part=",".join(body.keys()), body=body, media_body=media)

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                pct = status.progress()
                self._set_progress(pct * 0.95, f"YouTube  {int(pct * 100)}%", YT)

        video_id = response.get("id", "?")
        self._log(f"YouTube   https://youtu.be/{video_id}")

    # ======================================================================
    #  TIKTOK UPLOAD
    # ======================================================================
    def upload_to_tiktok(self, video_path, title):
        cookies_path = self._tt_cookies_path()
        if not os.path.exists(cookies_path):
            raise Exception(
                "No TikTok cookies -- go to Accounts tab and import cookies first")

        privacy_map = {
            "Everyone": ["\u0e17\u0e38\u0e01\u0e04\u0e19", "Everyone", "Public"],
            "Friends":  ["\u0e40\u0e1e\u0e37\u0e48\u0e2d\u0e19",  "Friends"],
            "Only me":  ["\u0e40\u0e09\u0e1e\u0e32\u0e30\u0e09\u0e31\u0e19", "Only me", "Private"],
        }
        chosen        = self.tt_privacy.get()
        privacy_texts = privacy_map.get(chosen, ["Everyone"])
        hashtags      = self._build_hashtags()
        caption       = f"{title}  {hashtags}".strip() if hashtags else title

        with sync_playwright() as p:
            browser = p.chromium.launch(
                channel="chrome",
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox", "--start-maximized",
                    "--disk-cache-size=1048576", "--media-cache-size=1048576",
                ],
            )
            context = browser.new_context()
            context.add_init_script(
                "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
            )
            with open(cookies_path, "r", encoding="utf-8") as f:
                cookies = json.load(f)
            context.add_cookies(cookies)
            page = context.new_page()
            self._setup_fast_route_blocking(page)

            # -- Verify session ----------------------------------------
            self._log("Verifying TikTok session...")
            page.goto("https://www.tiktok.com")
            page.wait_for_load_state("domcontentloaded")
            if "/login" in page.url or "/signup" in page.url:
                raise Exception(
                    "TikTok session expired -- go to Accounts tab and re-import cookies")
            self._log("Session OK")

            # -- Navigate to upload ------------------------------------
            self._log("Opening TikTok Studio...")
            page.goto("https://www.tiktok.com/tiktokstudio/upload?from=upload")

            # input[type="file"] is hidden -- use 'attached' not 'visible'
            page.locator('input[type="file"]').wait_for(state="attached", timeout=30000)
            page.locator('input[type="file"]').set_input_files(video_path)
            self._log("File sent -- waiting for video to process...")
            self._set_progress(0.2, "TikTok -- encoding video...", TT)

            # -- Wait for Post button to be truly ready ---------------
            # Playwright wait_for only accepts attached/detached/visible/hidden
            # Use JS to check CSS opacity + pointer-events (TikTok greys out btn)
            self._log("Waiting for TikTok video processing...")
            self._set_progress(0.25, "TikTok -- encoding video...", TT)

            JS_BTN_READY = """
                () => {
                    const btns = [...document.querySelectorAll('button')];
                    const btn  = btns.find(b => {
                        const t = b.textContent.trim();
                        return t === 'Post' || t === '\u0e42\u0e1e\u0e2a\u0e15\u0e4c'
                            || t.startsWith('Post ') || t.endsWith(' Post');
                    });
                    if (!btn) return false;
                    const s = window.getComputedStyle(btn);
                    return (
                        parseFloat(s.opacity  || '1') > 0.7 &&
                        s.pointerEvents !== 'none'           &&
                        !btn.disabled                        &&
                        btn.getAttribute('aria-disabled') !== 'true'
                    );
                }
            """
            try:
                page.wait_for_function(JS_BTN_READY, timeout=120000)
                self._log("Post button ready -- video processed OK")
            except Exception:
                self._log("Timeout waiting for Post button -- proceeding anyway")
            self._set_progress(0.5, "TikTok -- filling form...", TT)

            # -- Dismiss tutorial overlay (react-joyride) ---------------
            try:
                page.keyboard.press("Escape")
                page.wait_for_timeout(400)
                page.evaluate(
                    "document.querySelectorAll("
                    "'[data-test-id=\"overlay\"],"
                    ".react-joyride__overlay,"
                    "#react-joyride-portal'"
                    ").forEach(el=>el.remove())"
                )
                self._log("Dismissed tutorial overlay")
            except Exception:
                pass

            # -- Caption -----------------------------------------------
            caption_box = page.locator('div[contenteditable="true"]').first
            caption_box.wait_for(state="visible", timeout=30000)
            caption_box.click(force=True)
            page.wait_for_timeout(400)
            page.keyboard.press("Control+A")
            page.keyboard.press("Backspace")
            page.keyboard.type(caption)
            self._log(f"Caption: {caption[:70]}")

            # -- Privacy -----------------------------------------------
            try:
                sel = page.locator(
                    'div[class*="privacy"], div[class*="audience"], '
                    'button[class*="privacy"], [aria-label*="privacy"], '
                    '[aria-label*="audience"], [aria-label*="Who can"]'
                ).first
                if sel.is_visible(timeout=8000):
                    sel.click(force=True)
                    page.wait_for_timeout(800)
                    for text in privacy_texts:
                        opt = page.get_by_text(text, exact=True).first
                        if opt.is_visible(timeout=2000):
                            opt.click()
                            self._log(f"TikTok visibility: {chosen}")
                            break
            except Exception as exc:
                self._log(f"Privacy not set ({exc}) -- using default")

            # -- Post --------------------------------------------------
            self._set_progress(0.7, "TikTok -- clicking Post...", TT)
            page.wait_for_timeout(1000)

            # Re-check button ready (caption entry may have re-disabled it briefly)
            try:
                page.wait_for_function(JS_BTN_READY, timeout=15000)
            except Exception:
                pass

            # Scroll Post button into view
            page.evaluate("""
                const btns = [...document.querySelectorAll('button')];
                const btn  = btns.find(b => {
                    const t = b.textContent.trim();
                    return t === 'Post' || t === '\u0e42\u0e1e\u0e2a\u0e15\u0e4c'
                        || t.startsWith('Post ') || t.endsWith(' Post');
                });
                if (btn) btn.scrollIntoView({block:'center', behavior:'instant'});
            """)
            page.wait_for_timeout(300)

            # Click via JS to properly fire React's onClick (more reliable than Playwright click)
            page.evaluate("""
                const btns = [...document.querySelectorAll('button')];
                const btn  = btns.find(b => {
                    const t = b.textContent.trim();
                    return t === 'Post' || t === '\u0e42\u0e1e\u0e2a\u0e15\u0e4c'
                        || t.startsWith('Post ') || t.endsWith(' Post');
                });
                if (btn) btn.click();
                else throw new Error('Post button not found');
            """)
            self._log("Post button clicked -- waiting for confirmation...")
            self._set_progress(0.85, "TikTok -- confirming...", TT)

            # Wait for redirect to /content (up to 60s)
            try:
                page.wait_for_url(
                    lambda url: "upload" not in url,
                    timeout=60000,
                )
                self._log(f"Post confirmed  URL: {page.url}")
            except Exception:
                # Check for success modal / toast as fallback
                success_found = False
                try:
                    s_loc = page.locator(
                        ':text("being posted"), :text("Video posted"), '
                        ':text("\u0e42\u0e1e\u0e2a\u0e15\u0e4c\u0e41\u0e25\u0e49\u0e27"), [class*="success"]'
                    ).first
                    if s_loc.is_visible(timeout=5000):
                        success_found = True
                        self._log("Post success indicator detected")
                except Exception:
                    pass

                if not success_found:
                    page.wait_for_timeout(5000)
                    final_url = page.url
                    if "upload" in final_url:
                        raise Exception(
                            "Post may have failed -- URL still on upload page. "
                            "Try again or check TikTok Studio manually.")
                    self._log(f"Post sent (URL: {final_url})")

            self._log("TikTok   post complete")
            browser.close()

    # ======================================================================
    #  FACEBOOK UPLOAD
    # ======================================================================
    def upload_to_facebook(self, video_path, title, desc=None):
        cookies_path = self._fb_cookies_path()
        if not os.path.exists(cookies_path):
            raise Exception(
                "No Facebook cookies -- go to Accounts tab and import cookies first")

        hashtags = self._build_hashtags()
        caption  = f"{title}  {hashtags}".strip() if hashtags else title

        with sync_playwright() as p:
            browser = p.chromium.launch(
                channel="chrome", headless=False,
                args=["--disable-blink-features=AutomationControlled",
                      "--no-sandbox", "--start-maximized",
                      "--disk-cache-size=1048576", "--media-cache-size=1048576"],
            )
            context = browser.new_context()
            context.add_init_script(
                "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
            with open(cookies_path, "r", encoding="utf-8") as f:
                cookies = json.load(f)
            context.add_cookies(cookies)
            page = context.new_page()
            self._setup_fast_route_blocking(page)

            # Verify session
            self._log("Verifying Facebook session...")
            page.goto("https://www.facebook.com")
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(2000)
            if "login" in page.url.lower():
                raise Exception(
                    "Facebook session expired -- re-import cookies in Accounts tab")
            self._log("Session OK")

            # Navigate to Reels creator
            self._log("Opening Facebook Reels creator...")
            page.goto("https://www.facebook.com/reels/create")
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(3000)
            self._set_progress(0.1, "Facebook — loading creator...", FB)

            # Upload video file
            try:
                file_input = page.locator('input[type="file"]').first
                file_input.wait_for(state="attached", timeout=30000)
                file_input.set_input_files(video_path)
            except Exception:
                page.evaluate(
                    "const inp=document.querySelector('input[type=\"file\"]');"
                    "if(inp)inp.click();")
                page.wait_for_timeout(1000)
                page.locator('input[type="file"]').first.set_input_files(video_path)

            self._log("File sent — waiting for FB processing...")
            self._set_progress(0.2, "Facebook — encoding...", FB)

            # Wait for Next/Publish button
            JS_FB_READY = """
                () => {
                    const btns = [...document.querySelectorAll(
                        'div[role="button"], button')];
                    const btn = btns.find(b => {
                        const t = b.textContent.trim();
                        return t === 'Next' || t === 'Share now'
                            || t === 'Publish' || t === 'Post';
                    });
                    if (!btn) return false;
                    const s = window.getComputedStyle(btn);
                    return parseFloat(s.opacity || '1') > 0.7
                        && s.pointerEvents !== 'none';
                }
            """
            try:
                page.wait_for_function(JS_FB_READY, timeout=120000)
                self._log("FB processing done")
            except Exception:
                self._log("Timeout waiting for FB -- continuing")
            self._set_progress(0.5, "Facebook — filling details...", FB)

            # Click through any "Next" steps
            for _ in range(3):
                try:
                    nxt = page.locator(
                        'div[role="button"]:has-text("Next"), '
                        'button:has-text("Next")').first
                    if nxt.is_visible(timeout=3000):
                        nxt.click(force=True)
                        page.wait_for_timeout(1500)
                except Exception:
                    break

            # Fill caption
            try:
                cap = page.locator(
                    'div[contenteditable="true"], '
                    'textarea[placeholder*="caption"], '
                    'textarea[placeholder*="description"]').first
                if cap.is_visible(timeout=8000):
                    cap.click(force=True)
                    page.wait_for_timeout(300)
                    page.keyboard.press("Control+A")
                    page.keyboard.press("Backspace")
                    page.keyboard.type(caption)
                    self._log(f"Caption: {caption[:70]}")
            except Exception as e:
                self._log(f"Caption fill failed: {e}")

            # Set audience
            privacy = self.fb_privacy.get()
            try:
                aud = page.locator(
                    '[aria-label*="audience"], [aria-label*="Who can"], '
                    'div:has-text("Public"), div:has-text("Friends")').first
                if aud.is_visible(timeout=5000):
                    aud.click(force=True)
                    page.wait_for_timeout(800)
                    opt = page.get_by_text(privacy, exact=True).first
                    if opt.is_visible(timeout=3000):
                        opt.click()
                        self._log(f"Audience: {privacy}")
            except Exception as e:
                self._log(f"Audience not set ({e})")

            # Click Share / Publish
            self._set_progress(0.7, "Facebook — posting...", FB)
            page.wait_for_timeout(500)
            page.evaluate("""
                const btns = [...document.querySelectorAll(
                    'div[role="button"], button')];
                const btn = btns.find(b => {
                    const t = b.textContent.trim();
                    return t === 'Share now' || t === 'Publish'
                        || t === 'Post' || t === 'Share';
                });
                if (btn) btn.click();
                else throw new Error('Share button not found');
            """)
            self._log("Clicked Share — waiting for confirmation...")
            self._set_progress(0.85, "Facebook — confirming...", FB)

            try:
                page.wait_for_url(
                    lambda url: "reels/create" not in url, timeout=60000)
                self._log(f"Facebook \u2713  post confirmed  URL: {page.url}")
            except Exception:
                page.wait_for_timeout(8000)
                self._log(f"Facebook post sent  (URL: {page.url})")

            browser.close()

    # ======================================================================
    #  INSTAGRAM UPLOAD
    # ======================================================================
    def upload_to_instagram(self, video_path, title, desc=None):
        cookies_path = self._ig_cookies_path()
        if not os.path.exists(cookies_path):
            raise Exception(
                "No Instagram cookies -- go to Accounts tab and import cookies first")

        hashtags = self._build_hashtags()
        caption  = f"{title}  {hashtags}".strip() if hashtags else title

        with sync_playwright() as p:
            browser = p.chromium.launch(
                channel="chrome", headless=False,
                args=["--disable-blink-features=AutomationControlled",
                      "--no-sandbox",
                      "--disk-cache-size=1048576", "--media-cache-size=1048576"],
            )
            context = browser.new_context(viewport={"width": 1280, "height": 900})
            context.add_init_script(
                "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
            with open(cookies_path, "r", encoding="utf-8") as f:
                cookies = json.load(f)
            context.add_cookies(cookies)
            page = context.new_page()
            self._setup_fast_route_blocking(page)

            # Verify session
            self._log("Verifying Instagram session...")
            page.goto("https://www.instagram.com")
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(2000)
            if "accounts/login" in page.url:
                raise Exception(
                    "Instagram session expired -- re-import cookies in Accounts tab")
            self._log("Session OK")

            # Click "+" / Create
            self._log("Opening Instagram Reels creator...")
            try:
                create = page.locator(
                    '[aria-label="New post"], '
                    '[aria-label="Create"], '
                    'a[href*="/create/"]').first
                create.wait_for(state="visible", timeout=10000)
                create.click()
                page.wait_for_timeout(1500)
            except Exception:
                self._log("Create button not found -- trying direct navigation")
                page.goto("https://www.instagram.com/reels/upload")
                page.wait_for_load_state("domcontentloaded")
                page.wait_for_timeout(3000)

            # Choose "Reel" from menu if shown
            try:
                reel_opt = page.get_by_text("Reel", exact=True).first
                if reel_opt.is_visible(timeout=4000):
                    reel_opt.click()
                    page.wait_for_timeout(1000)
            except Exception:
                pass

            # Upload file
            self._set_progress(0.15, "Instagram — uploading file...", IG)
            try:
                file_input = page.locator('input[type="file"]').first
                file_input.wait_for(state="attached", timeout=30000)
                file_input.set_input_files(video_path)
            except Exception:
                page.locator('[role="button"]:has-text("Select"), '
                             'button:has-text("Select")').first.click(force=True)
                page.wait_for_timeout(1000)
                page.locator('input[type="file"]').first.set_input_files(video_path)

            self._log("File sent — waiting for IG processing...")
            self._set_progress(0.25, "Instagram — processing...", IG)
            page.wait_for_timeout(5000)

            # Step through wizard (Trim → Crop → Next → Caption)
            for step_label in ["Trim", "Crop", "Next", "Next"]:
                try:
                    nxt = page.locator(
                        'button:has-text("Next"), '
                        'div[role="button"]:has-text("Next")').first
                    if nxt.is_visible(timeout=12000):
                        nxt.click(force=True)
                        self._log(f"IG step: {step_label} -> Next")
                        page.wait_for_timeout(2000)
                except Exception:
                    pass

            # Fill caption
            self._set_progress(0.55, "Instagram — filling caption...", IG)
            try:
                cap = page.locator(
                    'textarea[aria-label*="caption"], '
                    'div[aria-label*="caption"][contenteditable], '
                    'textarea[placeholder*="caption"]').first
                if cap.is_visible(timeout=10000):
                    cap.click(force=True)
                    page.wait_for_timeout(300)
                    page.keyboard.type(caption)
                    self._log(f"Caption: {caption[:70]}")
            except Exception as e:
                self._log(f"Caption fill failed: {e}")

            # Click Share
            self._set_progress(0.75, "Instagram — posting...", IG)
            try:
                share = page.locator(
                    'button:has-text("Share"), '
                    'div[role="button"]:has-text("Share")').first
                share.wait_for(state="visible", timeout=15000)
                share.click(force=True)
            except Exception:
                page.evaluate("""
                    const btns = [...document.querySelectorAll(
                        'button, div[role="button"]')];
                    const b = btns.find(b => b.textContent.trim() === 'Share');
                    if (b) b.click();
                """)

            self._log("Clicked Share — waiting...")
            self._set_progress(0.9, "Instagram — confirming...", IG)
            page.wait_for_timeout(10000)
            self._log(f"Instagram \u2713  post sent  (URL: {page.url})")
            browser.close()



# ===========================================================================
if __name__ == "__main__":
    app = AutoPosterApp()
    app.mainloop()
