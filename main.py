import os
import sys
import json
import asyncio
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
#  DESIGN TOKENS
# ══════════════════════════════════════════════════════════════════════════
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

BG        = "#09090d"
SURF      = "#111118"
SURF2     = "#18181f"
SURF3     = "#202028"
BORDER    = "#2a2a38"
BORDER2   = "#343445"
ACCENT    = "#7c3aed"
ACCENT_H  = "#6d28d9"
ACCENT2   = "#a78bfa"
TEXT      = "#f4f4f8"
TEXT2     = "#a0a0b8"
MUTED     = "#5a5a72"
SUCCESS   = "#22c55e"
WARNING   = "#f59e0b"
ERROR     = "#ef4444"
YT        = "#ff4444"
YT_BG     = "#1f1010"
TT        = "#fe2c55"
TT_BG     = "#1f1016"

FONT_FAMILY = "Segoe UI Variable"

def F(size=13, weight="normal"):
    return ctk.CTkFont(family=FONT_FAMILY, size=size + 2, weight=weight)

def Div(parent, **kw):
    ctk.CTkFrame(parent, height=1, fg_color=BORDER, corner_radius=0).pack(fill="x", **kw)

def Card(parent, **kw):
    return ctk.CTkFrame(parent, fg_color=SURF, corner_radius=12,
                        border_width=1, border_color=BORDER, **kw)


# ══════════════════════════════════════════════════════════════════════════
#  MAIN APP
# ══════════════════════════════════════════════════════════════════════════
class AutoPosterApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("AutoPoster")
        self.geometry("760x900")
        self.minsize(700, 820)
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

        # โหลดชื่อช่อง YouTube หลังจาก UI พร้อมแล้ว
        if os.path.exists("youtube_token.json"):
            threading.Thread(target=self._fetch_yt_channel_name, daemon=True).start()

    # ── HEADER ────────────────────────────────────────────────────────────
    def _build_header(self):
        hdr = ctk.CTkFrame(self, fg_color=SURF, corner_radius=0, height=60)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        # Logo
        logo = ctk.CTkFrame(hdr, fg_color="transparent")
        logo.pack(side="left", padx=20, fill="y")
        ctk.CTkLabel(logo, text="✦  AutoPoster", font=F(17, "bold"), text_color=TEXT).pack(side="left")
        ctk.CTkLabel(logo, text="v1", font=F(10), text_color=MUTED).pack(side="left", padx=(4, 20), pady=(8, 0))

        # Platform pills
        pill_frame = ctk.CTkFrame(hdr, fg_color="transparent")
        pill_frame.pack(side="left", fill="y", pady=14)
        self.var_yt = tk.BooleanVar(value=True)
        self.var_tt = tk.BooleanVar(value=True)
        self._platform_pill(pill_frame, "▶  YT Shorts", YT, self.var_yt)
        self._platform_pill(pill_frame, "♪  TikTok",    TT, self.var_tt, padx=(8, 0))

        # Connection status
        right = ctk.CTkFrame(hdr, fg_color="transparent")
        right.pack(side="right", padx=20, fill="y")
        ctk.CTkLabel(right, text="Connected:", font=F(10), text_color=MUTED).pack(side="right")
        self.dot_tt = ctk.CTkLabel(right, text="  ● TT", font=F(11),
            text_color=SUCCESS if os.path.exists(self._tt_cookies_path()) else MUTED)
        self.dot_tt.pack(side="right")
        self.dot_yt = ctk.CTkLabel(right, text="  ● YT", font=F(11),
            text_color=SUCCESS if os.path.exists("youtube_token.json") else MUTED)
        self.dot_yt.pack(side="right")

        Div(self)

    def _platform_pill(self, parent, label, color, var, padx=(0, 0)):
        frame = ctk.CTkFrame(parent, fg_color=SURF3, corner_radius=20,
                             border_width=1, border_color=color if var.get() else BORDER2)
        frame.pack(side="left", padx=padx)

        lbl = ctk.CTkLabel(frame, text=label, font=F(11, "bold"),
                           text_color=color if var.get() else MUTED)
        lbl.pack(side="left", padx=(10, 4), pady=5)

        def _update(*_):
            on = var.get()
            frame.configure(border_color=color if on else BORDER2)
            lbl.configure(text_color=color if on else MUTED)

        ctk.CTkSwitch(frame, text="", variable=var, command=_update,
            width=36, height=18, button_color="#ffffff", button_hover_color="#dddddd",
            fg_color=BORDER2, progress_color=color, onvalue=True, offvalue=False
        ).pack(side="left", padx=(0, 8), pady=5)

    # ── TABS ──────────────────────────────────────────────────────────────
    def _build_tabs(self):
        self.tabs = ctk.CTkTabview(self,
            fg_color=BG,
            segmented_button_fg_color=SURF,
            segmented_button_selected_color=SURF3,
            segmented_button_selected_hover_color=BORDER,
            segmented_button_unselected_color=SURF,
            segmented_button_unselected_hover_color=SURF2,
            text_color=TEXT2,
            text_color_disabled=MUTED,
            border_color=BORDER,
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
            scrollbar_button_color=SURF3, scrollbar_button_hover_color=BORDER)
        scroll.pack(fill="both", expand=True)

        P = {"padx": 20, "pady": (0, 14)}

        # ── File picker ────────────────────────────────────────────────
        self._section(scroll, "🎬  Video File")
        file_card = Card(scroll)
        file_card.pack(fill="x", **P)

        file_inner = ctk.CTkFrame(file_card, fg_color="transparent")
        file_inner.pack(fill="x", padx=16, pady=14)

        self.btn_browse = ctk.CTkButton(file_inner,
            text="Browse…", command=self.browse_file,
            fg_color=SURF3, hover_color=BORDER, text_color=TEXT,
            border_color=BORDER2, border_width=1,
            height=40, width=110, font=F(12), corner_radius=8)
        self.btn_browse.pack(side="left")

        self.lbl_file = ctk.CTkLabel(file_inner,
            text="No file selected", font=F(12), text_color=MUTED, anchor="w")
        self.lbl_file.pack(side="left", padx=14, fill="x", expand=True)

        # ── Title ──────────────────────────────────────────────────────
        self._section(scroll, "✏️  Title")
        self.entry_title = ctk.CTkEntry(scroll,
            placeholder_text="Enter video title…",
            height=46, font=F(14), fg_color=SURF,
            border_color=BORDER, border_width=1,
            text_color=TEXT, placeholder_text_color=MUTED, corner_radius=10)
        self.entry_title.pack(fill="x", **P)

        # ── Description + Hashtags (2-column) ─────────────────────────
        self._section(scroll, "📝  Description  &  # Hashtags")
        two_col = ctk.CTkFrame(scroll, fg_color="transparent")
        two_col.pack(fill="x", **P)
        two_col.grid_columnconfigure(0, weight=3)
        two_col.grid_columnconfigure(1, weight=2)

        self.txt_desc = ctk.CTkTextbox(two_col, height=100, font=F(12),
            fg_color=SURF, border_color=BORDER, border_width=1,
            text_color=TEXT, corner_radius=10, scrollbar_button_color=SURF3)
        self.txt_desc.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        # Hashtag card
        ht_card = ctk.CTkFrame(two_col, fg_color=SURF,
            border_color=BORDER, border_width=1, corner_radius=10)
        ht_card.grid(row=0, column=1, sticky="nsew")
        ht_card.grid_rowconfigure(1, weight=1)
        ht_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(ht_card, text="Tags (space or comma)", font=F(10),
            text_color=MUTED, anchor="w").grid(row=0, column=0, padx=12, pady=(10, 2), sticky="w")

        self.txt_hashtags = ctk.CTkTextbox(ht_card, height=68, font=F(12),
            fg_color="transparent", border_width=0,
            text_color=ACCENT2, scrollbar_button_color=SURF3)
        self.txt_hashtags.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 8))
        self.txt_hashtags.insert("end", "shorts  viral  fyp")

        # ── Visibility ─────────────────────────────────────────────────
        self._section(scroll, "🔒  Visibility")
        vis_card = Card(scroll)
        vis_card.pack(fill="x", **P)

        yt_row = ctk.CTkFrame(vis_card, fg_color="transparent")
        yt_row.pack(fill="x", padx=16, pady=(14, 8))
        ctk.CTkLabel(yt_row, text="▶", font=F(12, "bold"), text_color=YT, width=22).pack(side="left")
        ctk.CTkLabel(yt_row, text="YouTube", font=F(12), text_color=TEXT2, width=75, anchor="w").pack(side="left", padx=6)
        self.yt_privacy = tk.StringVar(value="public")
        ctk.CTkSegmentedButton(yt_row,
            values=["public", "unlisted", "private"],
            variable=self.yt_privacy, font=F(11),
            fg_color=SURF2, selected_color=YT, selected_hover_color="#cc3333",
            unselected_color=SURF2, unselected_hover_color=SURF3,
            text_color=TEXT, corner_radius=8, height=32,
        ).pack(side="left", padx=10)

        Div(vis_card)

        tt_row = ctk.CTkFrame(vis_card, fg_color="transparent")
        tt_row.pack(fill="x", padx=16, pady=(8, 14))
        ctk.CTkLabel(tt_row, text="♪", font=F(12, "bold"), text_color=TT, width=22).pack(side="left")
        ctk.CTkLabel(tt_row, text="TikTok", font=F(12), text_color=TEXT2, width=75, anchor="w").pack(side="left", padx=6)
        self.tt_privacy = tk.StringVar(value="Everyone")
        ctk.CTkSegmentedButton(tt_row,
            values=["Everyone", "Friends", "Only me"],
            variable=self.tt_privacy, font=F(11),
            fg_color=SURF2, selected_color=TT, selected_hover_color="#c9214a",
            unselected_color=SURF2, unselected_hover_color=SURF3,
            text_color=TEXT, corner_radius=8, height=32,
        ).pack(side="left", padx=10)

        # ── Schedule ───────────────────────────────────────────────────
        self._section(scroll, "📅  Schedule")
        sch_card = Card(scroll)
        sch_card.pack(fill="x", **P)

        sch_top = ctk.CTkFrame(sch_card, fg_color="transparent")
        sch_top.pack(fill="x", padx=16, pady=14)

        ctk.CTkLabel(sch_top, text="Post immediately",
            font=F(12), text_color=TEXT, anchor="w").pack(side="left")
        ctk.CTkLabel(sch_top, text="Schedule",
            font=F(12), text_color=MUTED).pack(side="right", padx=(0, 8))

        self.var_schedule = tk.BooleanVar(value=False)
        ctk.CTkSwitch(sch_top, text="", variable=self.var_schedule,
            command=self._toggle_schedule, width=44, height=22,
            button_color=TEXT, button_hover_color="#ccccdd",
            fg_color=BORDER2, progress_color=ACCENT,
            onvalue=True, offvalue=False).pack(side="right")

        # Hidden datetime row
        self.sch_inputs = ctk.CTkFrame(sch_card, fg_color="transparent")
        # (packed when switch turns ON)
        Div(self.sch_inputs)

        sch_inner = ctk.CTkFrame(self.sch_inputs, fg_color="transparent")
        sch_inner.pack(fill="x", padx=16, pady=14)

        ctk.CTkLabel(sch_inner, text="Date", font=F(11), text_color=MUTED, width=40, anchor="w").pack(side="left")
        self.entry_date = ctk.CTkEntry(sch_inner,
            placeholder_text=datetime.now().strftime("%Y-%m-%d"),
            height=36, width=130, font=F(12), fg_color=SURF2,
            border_color=BORDER, border_width=1, text_color=TEXT,
            placeholder_text_color=MUTED, corner_radius=8)
        self.entry_date.pack(side="left", padx=(4, 18))

        ctk.CTkLabel(sch_inner, text="Time", font=F(11), text_color=MUTED, width=40, anchor="w").pack(side="left")
        self.entry_time = ctk.CTkEntry(sch_inner,
            placeholder_text="18:00",
            height=36, width=100, font=F(12), fg_color=SURF2,
            border_color=BORDER, border_width=1, text_color=TEXT,
            placeholder_text_color=MUTED, corner_radius=8)
        self.entry_time.pack(side="left", padx=4)

        self.lbl_countdown = ctk.CTkLabel(sch_inner, text="",
            font=F(11, "bold"), text_color=ACCENT2, anchor="w")
        self.lbl_countdown.pack(side="left", padx=12)

        # ── Upload Progress ────────────────────────────────────────────
        self._section(scroll, "📊  Upload Progress")
        prog_card = Card(scroll)
        prog_card.pack(fill="x", **P)

        prog_inner = ctk.CTkFrame(prog_card, fg_color="transparent")
        prog_inner.pack(fill="x", padx=16, pady=16)

        self.progress_bar = ctk.CTkProgressBar(prog_inner,
            mode="determinate", height=8, corner_radius=4,
            fg_color=SURF3, progress_color=ACCENT)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", pady=(0, 8))

        self.lbl_progress = ctk.CTkLabel(prog_inner,
            text="Idle", font=F(11), text_color=MUTED, anchor="w")
        self.lbl_progress.pack(fill="x")

        # ── Activity Log ───────────────────────────────────────────────
        self._section(scroll, "🗒️  Activity Log")
        self.txt_log = ctk.CTkTextbox(scroll, height=130,
            font=ctk.CTkFont(family="Consolas", size=12),
            fg_color="#080810", border_color=BORDER, border_width=1,
            text_color="#5a5a8a", corner_radius=10, state="disabled",
            scrollbar_button_color=SURF3)
        self.txt_log.pack(fill="x", padx=20, pady=(0, 20))

    # ── ACCOUNTS TAB ──────────────────────────────────────────────────────
    def _build_accounts_tab(self, tab):
        tab.configure(fg_color=BG)
        scroll = ctk.CTkScrollableFrame(tab, fg_color=BG, scrollbar_button_color=SURF3)
        scroll.pack(fill="both", expand=True)

        # ── YouTube ────────────────────────────────────────────────────
        self._section(scroll, "▶  YouTube Account", top=20)
        yt_card = ctk.CTkFrame(scroll, fg_color=YT_BG,
            corner_radius=12, border_width=1, border_color=YT)
        yt_card.pack(fill="x", padx=20, pady=(6, 16))

        yt_top = ctk.CTkFrame(yt_card, fg_color="transparent")
        yt_top.pack(fill="x", padx=16, pady=16)

        ctk.CTkLabel(yt_top, text="▶", font=F(22, "bold"), text_color=YT, width=32).pack(side="left")

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
            height=34, width=110, font=F(11), corner_radius=8,
            border_width=1, border_color=YT).pack(side="right")

        Div(yt_card)
        ctk.CTkLabel(yt_card,
            text="💡  Login happens automatically on first upload.\n    Token stored locally in  youtube_token.json",
            font=F(10), text_color=MUTED, justify="left", anchor="w").pack(
            fill="x", padx=16, pady=10)

        # ── TikTok ─────────────────────────────────────────────────────
        _ck_path     = self._tt_cookies_path()   # ใช้ absolute path เสมอ
        _has_cookies = os.path.exists(_ck_path)

        # อ่าน cookie count + วันที่ save + วันหมดอายุของ sessionid
        _ck_count, _ck_date = 0, ""
        _ck_expiry_txt, _ck_expiry_color, _ck_days_left = "", SUCCESS, 999
        if _has_cookies:
            try:
                import datetime as _dt
                with open(_ck_path, "r", encoding="utf-8") as _f:
                    _cookies_list = json.load(_f)
                _ck_count = len(_cookies_list)
                _ck_date  = _dt.datetime.fromtimestamp(
                    os.path.getmtime(_ck_path)).strftime("%Y-%m-%d")

                # หา sessionid หรือ cookie ที่สำคัญ แล้วดูวันหมดอายุ
                _key_names = ("sessionid", "sid_tt", "sid_guard", "passport_auth_token")
                _earliest  = None
                for _c in _cookies_list:
                    if _c.get("name", "").lower() in _key_names:
                        _exp = _c.get("expirationDate") or _c.get("expires")
                        if _exp and float(_exp) > 0:
                            _exp_dt = _dt.datetime.fromtimestamp(float(_exp))
                            if _earliest is None or _exp_dt < _earliest:
                                _earliest = _exp_dt

                if _earliest:
                    _ck_days_left = (_earliest - _dt.datetime.now()).days
                    if _ck_days_left > 0:
                        _ck_expiry_txt = (
                            f"  ·  หมดอายุ {_earliest.strftime('%Y-%m-%d')}"
                            f"  ({_ck_days_left} วัน)"
                        )
                        _ck_expiry_color = (
                            SUCCESS  if _ck_days_left > 14 else
                            WARNING  if _ck_days_left > 7  else
                            ERROR
                        )
                    else:
                        _ck_expiry_txt   = "  ·  ⚠ Session อาจหมดอายุแล้ว"
                        _ck_expiry_color = ERROR
                        _ck_days_left    = 0
            except Exception:
                pass

        self._section(scroll, "♪  TikTok Account", top=8)
        tt_card = ctk.CTkFrame(scroll, fg_color=TT_BG,
            corner_radius=12, border_width=1, border_color=TT)
        tt_card.pack(fill="x", padx=20, pady=(6, 16))

        tt_top = ctk.CTkFrame(tt_card, fg_color="transparent")
        tt_top.pack(fill="x", padx=16, pady=16)

        ctk.CTkLabel(tt_top, text="♪", font=F(22, "bold"), text_color=TT, width=32).pack(side="left")

        tt_info = ctk.CTkFrame(tt_top, fg_color="transparent")
        tt_info.pack(side="left", padx=12, fill="x", expand=True)
        ctk.CTkLabel(tt_info, text="TikTok",
            font=F(13, "bold"), text_color=TEXT, anchor="w").pack(fill="x")

        if _has_cookies:
            _status_txt = f"Cookies saved  ✓   ({_ck_count} cookies · saved {_ck_date})"
        else:
            _status_txt = "Not connected"
        self.lbl_tt_status = ctk.CTkLabel(tt_info,
            text=_status_txt,
            font=F(11), anchor="w",
            text_color=SUCCESS if _has_cookies else MUTED)
        self.lbl_tt_status.pack(fill="x")

        # แสดงวันหมดอายุ sessionid (line แยก, เปลี่ยนสีตาม urgency)
        if _has_cookies and _ck_expiry_txt:
            self.lbl_tt_expiry = ctk.CTkLabel(tt_info,
                text=_ck_expiry_txt,
                font=F(10), anchor="w",
                text_color=_ck_expiry_color)
            self.lbl_tt_expiry.pack(fill="x")

        ctk.CTkButton(tt_top,
            text="Clear",
            command=self.tt_clear_cookies,
            fg_color="transparent", hover_color=TT_BG, text_color=TT,
            height=34, width=70, font=F(11), corner_radius=8,
            border_width=1, border_color=TT).pack(side="right")

        Div(tt_card)

        # แสดง notice ว่า cookies ถูก save ไว้แล้ว (ไม่ต้องกรอกใหม่ทุกครั้ง)
        if _has_cookies:
            if _ck_days_left <= 0:
                _notice_txt   = "⚠️  Session อาจหมดอายุแล้ว — กรุณา Import cookies ใหม่"
                _notice_color = ERROR
            elif _ck_days_left <= 7:
                _notice_txt   = f"⚠️  Cookies จะหมดอายุใน {_ck_days_left} วัน — ควร Import ใหม่เร็วๆ นี้"
                _notice_color = ERROR
            elif _ck_days_left <= 14:
                _notice_txt   = f"⌛  Cookies จะหมดอายุใน {_ck_days_left} วัน — เตรียม Import ใหม่ไว้"
                _notice_color = WARNING
            else:
                _notice_txt   = (
                    "✅  Cookies ถูกบันทึกไว้แล้ว — ไม่ต้องกรอกใหม่ทุกครั้ง\n"
                    "    Import ใหม่เฉพาะเมื่อ TikTok logout หรือหมดอายุ"
                )
                _notice_color = SUCCESS
            ctk.CTkLabel(tt_card,
                text=_notice_txt,
                font=F(10), text_color=_notice_color, justify="left", anchor="w"
            ).pack(fill="x", padx=16, pady=(12, 4))
            Div(tt_card)

        ctk.CTkLabel(tt_card,
            text=(
                "👉  วิธีเชื่อมต่อ / อัปเดต Cookies:"
                "\n  1.  ติดตั้ง Chrome extension: «Cookie-Editor»"
                "\n  2.  ไปที่  tiktok.com  (ที่ login อยู่แล้ว)"
                "\n  3.  คลิก Cookie-Editor → Export → Export as JSON → Copy to clipboard"
                "\n  4.  Paste ในช่องด้านล่าง  →  กด Import"
            ),
            font=F(10), text_color=MUTED, justify="left", anchor="w"
        ).pack(fill="x", padx=16, pady=(12, 6))

        paste_row = ctk.CTkFrame(tt_card, fg_color="transparent")
        paste_row.pack(fill="x", padx=16, pady=(0, 16))

        self.txt_tt_cookies = ctk.CTkTextbox(paste_row, height=72, font=F(10),
            fg_color=SURF2, border_color=BORDER, border_width=1,
            text_color=TEXT2, corner_radius=8,
            scrollbar_button_color=SURF3)
        self.txt_tt_cookies.pack(side="left", fill="x", expand=True)
        placeholder = "Paste JSON cookies here (to update)…" if _has_cookies else "Paste JSON cookies here…"
        self.txt_tt_cookies.insert("end", placeholder)

        ctk.CTkButton(paste_row,
            text="Update" if _has_cookies else "Import",
            command=self.tt_import_cookies,
            fg_color=TT, hover_color="#c9214a",
            text_color="#fff", height=72, width=80,
            font=F(11, "bold"), corner_radius=8).pack(side="right", padx=(8, 0))



    # ── ACTION BAR ────────────────────────────────────────────────────────
    def _build_action_bar(self):
        Div(self)
        bar = ctk.CTkFrame(self, fg_color=SURF, corner_radius=0, height=72)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        inner = ctk.CTkFrame(bar, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=16, pady=12)

        self.btn_post = ctk.CTkButton(inner,
            text="▶  Post Now",
            command=self._post_now,
            fg_color=ACCENT, hover_color=ACCENT_H,
            text_color="#ffffff",
            height=46, font=F(14, "bold"), corner_radius=10)
        self.btn_post.pack(fill="x", expand=True)

    # ── STATUS BAR ────────────────────────────────────────────────────────
    def _build_statusbar(self):
        Div(self)
        self.lbl_status = ctk.CTkLabel(self,
            text="  Ready", font=F(11), text_color=MUTED,
            fg_color=SURF, anchor="w", height=28)
        self.lbl_status.pack(fill="x", ipady=2)

    # ── UI HELPER ─────────────────────────────────────────────────────────
    def _section(self, parent, text, top=14):
        ctk.CTkLabel(parent, text=text, font=F(11, "bold"),
            text_color=TEXT2, anchor="w").pack(fill="x", padx=20, pady=(top, 5))

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

        # Validation
        if not self.var_yt.get() and not self.var_tt.get():
            self.update_status("Select at least one platform", ERROR)
            return
        title = self.entry_title.get().strip()
        if not title:
            self.update_status("Title is required", ERROR)
            return
        if not self.video_path:
            self.update_status("Select a video file", ERROR)
            return

        # Build item
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
        total   = len(items)
        done    = 0

        try:
            for i, item in enumerate(items, 1):
                self._log(f"─── [{i}/{total}]  {os.path.basename(item['video_path'])} ───")
                yt_ok = tt_ok = False

                if post_yt:
                    try:
                        self.update_status(f"YouTube uploading…", YT)
                        self._set_progress(0, "YouTube — starting…", YT)
                        self.upload_to_youtube(item["video_path"], item["title"], item["desc"])
                        yt_ok = True
                        self._set_progress(1.0, "YouTube ✓", SUCCESS)
                        self.update_status("YouTube upload complete ✓", SUCCESS)
                    except Exception as e:
                        self.update_status(f"YouTube failed: {e}", ERROR)
                        self._set_progress(0, f"YouTube error", ERROR)
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
                        self._set_progress(0, f"TikTok error", ERROR)
                        self._log(f"TikTok error detail: {e}")

                if yt_ok or tt_ok:
                    done += 1

        except Exception as e:
            self.update_status(f"Unexpected error: {e}", ERROR)
            self._log(f"Unexpected error: {e}")

        finally:
            if post_yt and post_tt:
                if yt_ok and tt_ok:
                    summary = "Done — posted to both platforms ✓"
                    color   = SUCCESS
                elif yt_ok:
                    summary = "Done — YouTube ✓  |  TikTok ✗"
                    color   = WARNING
                elif tt_ok:
                    summary = "Done — TikTok ✓  |  YouTube ✗"
                    color   = WARNING
                else:
                    summary = "Both platforms failed"
                    color   = ERROR
            elif post_yt:
                summary = "YouTube ✓" if yt_ok else "YouTube failed"
                color   = SUCCESS if yt_ok else ERROR
            else:
                summary = "TikTok ✓" if tt_ok else "TikTok failed"
                color   = SUCCESS if tt_ok else ERROR

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
        self.txt_log.configure(state="normal")
        self.txt_log.insert("end", line)
        self.txt_log.see("end")
        self.txt_log.configure(state="disabled")
        print(line.strip())

    def update_status(self, text, color=MUTED):
        self.lbl_status.configure(text=f"  {text}", text_color=color)
        self._log(text)
        self.update_idletasks()

    def browse_file(self):
        path = filedialog.askopenfilename(
            filetypes=[("Video files", "*.mp4 *.mov *.MP4 *.MOV")])
        if path:
            self.video_path = path
            size_mb = os.path.getsize(path) / (1024 * 1024)
            name    = os.path.basename(path)
            display = f"{name}  ({size_mb:.1f} MB)"
            self.lbl_file.configure(text=display, text_color=TEXT)

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



# ===========================================================================
if __name__ == "__main__":
    app = AutoPosterApp()
    app.mainloop()
