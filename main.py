import os
import sys
import json
import queue
import time
import threading
import traceback
import tkinter as tk
from tkinter import filedialog, messagebox
from datetime import datetime, timedelta
from functools import lru_cache
import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont

# Drag & drop support (optional — falls back to Browse button only)
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    HAS_DND = True
except Exception:
    HAS_DND = False

# Playwright browser path fix (must run before importing playwright)
_browsers_path = os.path.join(os.environ.get("LOCALAPPDATA", ""), "ms-playwright")
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = _browsers_path

# YouTube API
import google.oauth2.credentials
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

# TikTok / Facebook / Instagram — Playwright with cookie injection
from playwright.sync_api import sync_playwright

# Windows Toast Notification (optional)
try:
    from plyer import notification as plyer_notify
    HAS_PLYER = True
except ImportError:
    HAS_PLYER = False

APP_NAME    = "AutopostVideo"
APP_VERSION = "2.1"

# Stable base directory — works in dev (python main.py) AND PyInstaller .exe
if getattr(sys, "frozen", False):
    # Running as compiled .exe — use the .exe's directory
    APP_DIR = os.path.dirname(sys.executable)
else:
    # Running as .py script — use the script's directory
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

ASSET_DIR      = os.path.join(APP_DIR, "assets")
YT_TOKEN_PATH  = os.path.join(APP_DIR, "youtube_token.json")
YT_CREDS_PATH  = os.path.join(APP_DIR, "credentials.json")
SETTINGS_PATH  = os.path.join(APP_DIR, "settings.json")
LOG_FILE_PATH  = os.path.join(APP_DIR, "autoposter.log")
YT_SCOPE_UPLOAD   = "https://www.googleapis.com/auth/youtube.upload"
YT_SCOPE_READONLY = "https://www.googleapis.com/auth/youtube.readonly"
VIDEO_EXTS = (".mp4", ".mov", ".m4v", ".webm")


def asset(*parts):
    return os.path.join(ASSET_DIR, *parts)


# Own taskbar icon/grouping instead of python.exe's (must run before any window exists)
if os.name == "nt":
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Pillows9.AutopostVideo")
    except Exception:
        pass

# ══════════════════════════════════════════════════════════════════════════
#  DESIGN TOKENS — keep in sync with DESIGN.md
# ══════════════════════════════════════════════════════════════════════════
ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")

# Brand palette
NAVY         = "#0B1020"   # Deep Navy — H1, wordmark, app icon
PRIMARY      = "#6366F1"   # Primary Purple — primary actions, selection
SKY          = "#3B82F6"   # Sky Blue — logo gradient end, info
PRIMARY_SOFT = "#E0E7FF"   # Light Purple — soft badges, icon circles
TEXT         = "#1F2937"   # Dark Gray — body text
TEXT_3       = "#94A3B8"   # Gray — captions, placeholders, disabled
BG           = "#F1F5F9"   # Light Gray — app background
SUCCESS      = "#10B981"

# Supporting tokens
PRIMARY_H    = "#4F46E5"   # primary hover / pressed
PRIMARY_TINT = "#EEF2FF"   # selected nav, chip hover
PRIMARY_DIS  = "#C7D2FE"   # disabled primary button
TEXT_2       = "#64748B"   # secondary text (AA contrast on white)
SURFACE      = "#FFFFFF"   # cards, sidebar
SURFACE_2    = "#F8FAFC"   # inputs, dropzone
BORDER       = "#E2E8F0"   # card border
BORDER_2     = "#CBD5E1"   # input border, switch track
WARNING      = "#F59E0B"
ERROR        = "#EF4444"
SUCCESS_T, WARNING_T, ERROR_T    = "#047857", "#B45309", "#DC2626"   # text on white
SUCCESS_BG, WARNING_BG, ERROR_BG = "#ECFDF5", "#FFFBEB", "#FEF2F2"
ERROR_BORDER = "#FECACA"
MUTED        = TEXT_3      # neutral status color (status messages / logs)

# Platform brand colors — logos & log accents only, never buttons
YT = "#FF0000"
TT = "#111827"
FB = "#1877F2"
IG = "#E1306C"

# Status kinds → (text color, background, dot color)
STATUS_STYLE = {
    "ok":   (SUCCESS_T, SUCCESS_BG, SUCCESS),
    "warn": (WARNING_T, WARNING_BG, WARNING),
    "err":  (ERROR_T,   ERROR_BG,   ERROR),
    "off":  (TEXT_2,    BG,         BORDER_2),
    "info": (TEXT,      SURFACE,    PRIMARY),
}
COLOR_KIND = {SUCCESS: "ok", WARNING: "warn", ERROR: "err"}
TEXT_SAFE  = {SUCCESS: SUCCESS_T, WARNING: WARNING_T, ERROR: ERROR_T, PRIMARY: PRIMARY_H}


# ── FONTS (IBM Plex Sans Thai — assets/fonts, loaded privately via Windows GDI) ────────
def _init_fonts():
    font_dir = asset("fonts")
    if os.name != "nt" or not os.path.isdir(font_dir):
        return
    try:
        import ctypes
        for name in os.listdir(font_dir):
            if name.lower().endswith((".ttf", ".otf")):
                buf = ctypes.create_unicode_buffer(os.path.join(font_dir, name))
                ctypes.windll.gdi32.AddFontResourceExW(buf, 0x10, 0)   # FR_PRIVATE
    except Exception:
        pass


_init_fonts()
_FONT_FAMILY = {"regular": "IBM Plex Sans Thai", "medium": "IBM Plex Sans Thai Medium",
                "semibold": "IBM Plex Sans Thai SemiBold", "bold": "IBM Plex Sans Thai"}


@lru_cache(maxsize=64)
def F(size=15, weight="regular"):
    """UI font (IBM Plex Sans Thai). weight: regular | medium | semibold | bold (see DESIGN.md §4)."""
    return ctk.CTkFont(family=_FONT_FAMILY.get(weight, _FONT_FAMILY["regular"]), size=size,
                       weight="bold" if weight == "bold" else "normal")


@lru_cache(maxsize=8)
def Mono(size=12):
    return ctk.CTkFont(family="Consolas", size=size)


# ── ICONS ──────────────────────────────────────────────────────────────────
@lru_cache(maxsize=32)
def get_icon(name, size=(18, 18)):
    """Full-color platform logo from assets/icons (yt, tt, fb, ig)."""
    path = asset("icons", f"{name}.png")
    if os.path.exists(path):
        try:
            img = Image.open(path).convert("RGBA")
            return ctk.CTkImage(light_image=img, dark_image=img, size=size)
        except Exception:
            pass
    return None


@lru_cache(maxsize=8)
def brand_image(name, size):
    path = asset("brand", name)
    if os.path.exists(path):
        try:
            img = Image.open(path).convert("RGBA")
            return ctk.CTkImage(light_image=img, dark_image=img, size=size)
        except Exception:
            pass
    return None


@lru_cache(maxsize=1)
def _icon_font_path():
    fonts = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    for name in ("SegoeIcons.ttf", "segmdl2.ttf"):   # Fluent (Win 11) → MDL2 (Win 10)
        path = os.path.join(fonts, name)
        if os.path.exists(path):
            return path
    return None


@lru_cache(maxsize=128)
def glyph(code, color, size=18):
    """Line icon from the Windows icon font, tinted (DESIGN.md §7)."""
    path = _icon_font_path()
    if not path:
        return None
    try:
        px = size * 4
        font = ImageFont.truetype(path, int(px * 0.8))
        img = Image.new("RGBA", (px, px), (0, 0, 0, 0))
        ImageDraw.Draw(img).text((px / 2, px / 2), chr(code), font=font, fill=color, anchor="mm")
        img = img.resize((size * 2, size * 2), Image.LANCZOS)
        return ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))
    except Exception:
        return None


# Glyph code points (Segoe Fluent Icons / MDL2 Assets)
G_ADD, G_SHARE, G_HISTORY, G_SETTINGS = 0xE710, 0xE72D, 0xE81C, 0xE713
G_UPLOAD, G_CLOCK, G_SEND, G_PASTE    = 0xE898, 0xE823, 0xE724, 0xE77F
G_VIDEO, G_EDIT, G_FOLDER, G_DOC      = 0xE714, 0xE70F, 0xE838, 0xE8A5
G_DELETE, G_CLOSE, G_INFO, G_LINK     = 0xE74D, 0xE711, 0xE946, 0xE71B
G_PEOPLE, G_CHECK                     = 0xE716, 0xE73E


# ══════════════════════════════════════════════════════════════════════════
#  UI COMPONENTS (DESIGN.md §6)
# ══════════════════════════════════════════════════════════════════════════
def Card(parent, **kw):
    return ctk.CTkFrame(parent, fg_color=SURFACE, corner_radius=16,
                        border_width=1, border_color=BORDER, **kw)


def PrimaryButton(parent, text, command, height=44, icon=None, **kw):
    return ctk.CTkButton(parent, text=text, command=command, height=height,
        image=glyph(icon, "#FFFFFF", 18) if icon else None, compound="left",
        fg_color=PRIMARY, hover_color=PRIMARY_H, text_color="#FFFFFF",
        text_color_disabled="#FFFFFF", font=F(15, "semibold"), corner_radius=12, **kw)


def SecondaryButton(parent, text, command, height=40, icon=None, **kw):
    return ctk.CTkButton(parent, text=text, command=command, height=height,
        image=glyph(icon, TEXT_2, 16) if icon else None, compound="left",
        fg_color=SURFACE, hover_color=SURFACE_2, text_color=TEXT,
        text_color_disabled=TEXT_3, border_width=1, border_color=BORDER_2,
        font=F(14, "medium"), corner_radius=12, **kw)


def DangerButton(parent, text, command, height=40, **kw):
    return ctk.CTkButton(parent, text=text, command=command, height=height,
        fg_color=SURFACE, hover_color=ERROR_BG, text_color=ERROR_T,
        border_width=1, border_color=ERROR_BORDER,
        font=F(14, "medium"), corner_radius=12, **kw)


@lru_cache(maxsize=8)
def _switch_image(on, hover, w=44, h=24):
    """Anti-aliased switch: knob inset inside an outlined track (DESIGN.md §6)."""
    s = 4                                   # supersample
    W, H = w * s, h * s
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if on:
        track, outline = (PRIMARY_H if hover else PRIMARY), PRIMARY_H
    else:
        track, outline = ("#B6C2D1" if hover else BORDER_2), TEXT_3
    d.rounded_rectangle((0, 0, W - 1, H - 1), radius=H // 2, fill=track, outline=outline, width=s * 2)
    pad = 4 * s
    r = H - 2 * pad
    x0 = W - pad - r if on else pad
    d.ellipse((x0, pad, x0 + r, pad + r), fill="#FFFFFF",
              outline=None if on else TEXT_3, width=s)
    img = img.resize((w * 2, h * 2), Image.LANCZOS)
    return ctk.CTkImage(light_image=img, dark_image=img, size=(w, h))


class Switch(ctk.CTkLabel):
    """On/off switch drawn as an image. CTkSwitch paints its white knob over the
    border, so it vanished on white cards — this one keeps the knob inset with an outline."""

    def __init__(self, parent, variable, command=None):
        super().__init__(parent, text="", width=44, height=24, cursor="hand2")
        self._var, self._command, self._hover = variable, command, False
        self.bind("<Button-1>", self._toggle)
        self.bind("<Enter>", lambda _e: self._set_hover(True))
        self.bind("<Leave>", lambda _e: self._set_hover(False))
        variable.trace_add("write", lambda *_: self._render())
        self._render()

    def get(self):
        return bool(self._var.get())

    def _toggle(self, _e=None):
        self._var.set(not self.get())
        if self._command:
            self._command()

    def _set_hover(self, hover):
        self._hover = hover
        self._render()

    def _render(self):
        try:
            self.configure(image=_switch_image(self.get(), self._hover))
        except tk.TclError:
            pass   # widget already destroyed


def Entry(parent, placeholder="", **kw):
    kw.setdefault("height", 44)
    return ctk.CTkEntry(parent, placeholder_text=placeholder, font=F(15),
        fg_color=SURFACE, border_color=BORDER_2, border_width=1,
        text_color=TEXT, placeholder_text_color=TEXT_3, corner_radius=12, **kw)


def Textbox(parent, height, text_color=TEXT, font=None):
    return ctk.CTkTextbox(parent, height=height, font=font or F(15),
        fg_color=SURFACE, border_color=BORDER_2, border_width=1,
        text_color=text_color, corner_radius=12, wrap="word",
        scrollbar_button_color=BORDER_2, scrollbar_button_hover_color=TEXT_3)


def ScrollPage(parent):
    return ctk.CTkScrollableFrame(parent, fg_color=BG, corner_radius=0,
        scrollbar_button_color=BORDER_2, scrollbar_button_hover_color=TEXT_3)


class ChipGroup(ctk.CTkFrame):
    """Pill-shaped single-choice options (replaces CTkSegmentedButton — DESIGN.md §6)."""

    def __init__(self, master, options, variable, command=None):
        super().__init__(master, fg_color="transparent")
        self._var, self._command, self._buttons = variable, command, {}
        for value, label in options:
            b = ctk.CTkButton(self, text=label, height=32, width=0, corner_radius=16,
                              font=F(13, "medium"), border_width=1,
                              command=lambda v=value: self.set(v))
            b.pack(side="left", padx=(0, 6))
            self._buttons[value] = b
        self._render()

    def set(self, value):
        self._var.set(value)
        self._render()
        if self._command:
            self._command(value)

    def _render(self):
        current = self._var.get()
        for value, b in self._buttons.items():
            if value == current:
                b.configure(fg_color=PRIMARY, hover_color=PRIMARY_H,
                            text_color="#FFFFFF", border_color=PRIMARY)
            else:
                b.configure(fg_color=SURFACE, hover_color=PRIMARY_TINT,
                            text_color=TEXT_2, border_color=BORDER_2)


class StatusBadge(ctk.CTkLabel):
    def __init__(self, master, **kw):
        super().__init__(master, text="", height=26, corner_radius=13,
                         font=F(12, "medium"), **kw)

    def show(self, kind, text):
        fg, bg, _dot = STATUS_STYLE[kind]
        self.configure(text=f"  {text}  ", text_color=fg, fg_color=bg)


# ══════════════════════════════════════════════════════════════════════════
#  SETTINGS / COOKIE HELPERS
# ══════════════════════════════════════════════════════════════════════════
def load_settings():
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_settings(data):
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


_SAMESITE_MAP = {"no_restriction": "None", "none": "None", "lax": "Lax", "strict": "Strict"}


def normalize_cookies(raw_text, default_domain):
    """Parse a Cookie-Editor / EditThisCookie JSON export into Playwright cookies.

    Keeps secure / httpOnly / sameSite / expiry so the session behaves like the
    real browser one (and so expiry warnings in the Platforms page work).
    """
    data = json.loads(raw_text)
    if isinstance(data, dict):
        data = data.get("cookies", [data] if "name" in data else [])
    if not isinstance(data, list):
        raise ValueError("ต้องเป็น JSON array ของ cookies")

    site = default_domain.lstrip(".")
    clean = []
    for c in data:
        if not isinstance(c, dict) or "name" not in c or "value" not in c:
            continue
        name   = str(c["name"])
        domain = c.get("domain") or default_domain
        ck     = {"name": name, "value": str(c["value"])}
        if name.startswith("__Host-"):
            # __Host- cookies must be host-only with path=/
            ck["url"] = f"https://{domain.lstrip('.')}/"
        else:
            ck["domain"] = domain
            ck["path"]   = c.get("path") or "/"
        secure = bool(c.get("secure")) or name.startswith(("__Secure-", "__Host-"))
        ck["secure"]   = secure
        ck["httpOnly"] = bool(c.get("httpOnly"))
        same_site = _SAMESITE_MAP.get(str(c.get("sameSite") or "").lower())
        if same_site == "None" and not secure:
            same_site = None
        if same_site:
            ck["sameSite"] = same_site
        exp = c.get("expirationDate", c.get("expires"))
        if not c.get("session") and isinstance(exp, (int, float)) and exp > 0:
            ck["expires"] = float(exp)
        clean.append(ck)

    if not clean:
        raise ValueError("ไม่พบ cookies ที่ใช้ได้")
    if not any(site in (ck.get("domain") or ck.get("url", "")) for ck in clean):
        raise ValueError(f"cookies นี้ไม่ได้มาจาก {site} — กรุณา export ขณะเปิด {site}")
    return clean


# ══════════════════════════════════════════════════════════════════════════
#  MAIN APP
# ══════════════════════════════════════════════════════════════════════════
PLATFORMS = {
    # key: (name, brand color)
    "yt": ("YouTube",   YT),
    "tt": ("TikTok",    TT),
    "fb": ("Facebook",  FB),
    "ig": ("Instagram", IG),
}
COOKIE_DOMAINS = {"tt": ".tiktok.com", "fb": ".facebook.com", "ig": ".instagram.com"}
COOKIE_FILES   = {"tt": "tiktok_cookies.json", "fb": "facebook_cookies.json",
                  "ig": "instagram_cookies.json"}
# Visibility options: (internal value, Thai label). Internal values are what the uploaders use.
VISIBILITY = {
    "yt": [("public", "สาธารณะ"), ("unlisted", "ไม่เป็นสาธารณะ"), ("private", "ส่วนตัว")],
    "tt": [("Everyone", "ทุกคน"), ("Friends", "เพื่อน"), ("Only me", "เฉพาะฉัน")],
    "fb": [("Public", "สาธารณะ"), ("Friends", "เพื่อน"), ("Only me", "เฉพาะฉัน")],
}
YT_TITLE_MAX   = 100
SHORTS_SUFFIX  = " #Shorts"

_APP_BASES = (ctk.CTk, TkinterDnD.DnDWrapper) if HAS_DND else (ctk.CTk,)


class AutoPosterApp(*_APP_BASES):
    PAGES = [
        # key, nav label, glyph, subtitle
        ("create",    "สร้างโพสต์", G_ADD,      "อัปโหลดวิดีโอครั้งเดียว โพสต์ได้ทุกแพลตฟอร์ม"),
        ("platforms", "แพลตฟอร์ม",  G_SHARE,    "เชื่อมต่อบัญชีที่ต้องการให้โพสต์อัตโนมัติ"),
        ("activity",  "กิจกรรม",    G_HISTORY,  "บันทึกการทำงานล่าสุดของแอป"),
        ("settings",  "ตั้งค่า",     G_SETTINGS, "การดูแลระบบและข้อมูลแอป"),
    ]

    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.configure(fg_color=BG)
        self._set_window_icon()

        self.settings       = load_settings()
        self.video_path     = ""
        self.is_posting     = False
        self._schedule_job  = None   # Tk after-id while a scheduled post is pending
        self._toast_job     = None
        self._progress_prefix = ""
        self._yt_lock       = threading.Lock()
        self._yt_signing_in = False
        self._log_lock      = threading.Lock()
        self._ui_queue      = queue.Queue()
        self._log_tags      = set()
        self._conn_listeners = {k: [] for k in PLATFORMS}
        self._conn_state     = {}

        self.dnd_ready = False
        if HAS_DND:
            try:
                TkinterDnD._require(self)
                self.dnd_ready = True
            except Exception:
                pass

        self._fit_window(1180, 820)
        self._trim_log_file()
        self._build_ui()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.report_callback_exception = self._on_tk_error
        self.after(50, self._drain_ui_queue)

    def _set_window_icon(self):
        ico = asset("brand", "app_icon.ico")
        if os.path.exists(ico):
            try:
                self.iconbitmap(ico)
            except Exception:
                pass

    def _fit_window(self, w, h):
        """Size + center the window so it always fits the screen (incl. 125–150% scaling)."""
        try:
            scale = ctk.ScalingTracker.get_window_scaling(self)
        except Exception:
            scale = 1.0
        sw = self.winfo_screenwidth() / scale
        sh = self.winfo_screenheight() / scale
        w = int(min(w, sw - 40))
        h = int(min(h, sh - 90))
        x = int(max(0, (sw - w) / 2))
        y = int(max(0, (sh - h) / 2 - 20))
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(min(980, w), min(640, h))

    # ── THREAD-SAFE UI ────────────────────────────────────────────────────
    def _ui(self, fn):
        """Run fn on the Tk main thread (Tkinter is not thread-safe)."""
        if threading.current_thread() is threading.main_thread():
            fn()
        else:
            self._ui_queue.put(fn)

    def _drain_ui_queue(self):
        while True:
            try:
                fn = self._ui_queue.get_nowait()
            except queue.Empty:
                break
            try:
                fn()
            except Exception:
                self._write_log_file(traceback.format_exc())
        self.after(50, self._drain_ui_queue)

    def _on_tk_error(self, exc, val, tb):
        detail = "".join(traceback.format_exception(exc, val, tb))
        self._write_log_file(detail)
        self.update_status(f"เกิดข้อผิดพลาดที่ไม่คาดคิด: {val}", ERROR)

    def _on_close(self):
        if self.is_posting or self._schedule_job:
            what = "กำลังอัปโหลดอยู่" if self.is_posting else "มีโพสต์ที่ตั้งเวลาไว้"
            if not messagebox.askyesno(
                    f"ออกจาก {APP_NAME}?",
                    f"{what}\n\nถ้าออกตอนนี้จะถูกยกเลิก ต้องการออกหรือไม่?",
                    icon="warning"):
                return
        self._save_settings()
        self.destroy()

    # ══════════════════════════════════════════════════════════════════════
    #  UI BUILD
    # ══════════════════════════════════════════════════════════════════════
    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()

        main = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)

        self._build_topbar(main)

        host = ctk.CTkFrame(main, fg_color=BG, corner_radius=0)
        host.grid(row=1, column=0, sticky="nsew")
        self.pages = {
            "create":    self._build_create_page(host),
            "platforms": self._build_platforms_page(host),
            "activity":  self._build_activity_page(host),
            "settings":  self._build_settings_page(host),
        }
        self._build_action_bar(main)

        if self.dnd_ready:
            # Register the whole window: a video dropped anywhere on the app is accepted
            try:
                self.drop_target_register(DND_FILES)
                self.dnd_bind("<<DropEnter>>", self._on_drag_enter)
                self.dnd_bind("<<DropLeave>>", self._on_drag_leave)
                self.dnd_bind("<<Drop>>", self._on_drop)
            except Exception:
                self.dnd_ready = False
        self.clear_file()

        self._refresh_all_connections()
        if os.path.exists(YT_TOKEN_PATH):
            threading.Thread(target=self._fetch_yt_channel_name, daemon=True).start()
        # Background clean orphan temp profiles
        threading.Thread(target=self.clean_playwright_cache, daemon=True).start()

        self._update_settings_visibility_rows()
        self._update_post_button_text()
        self._update_title_counter()
        self._show_page("create")

    # ── SIDEBAR ───────────────────────────────────────────────────────────
    def _build_sidebar(self):
        sb = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=0, width=236)
        sb.grid(row=0, column=0, sticky="nsw")
        sb.pack_propagate(False)
        ctk.CTkFrame(sb, width=1, fg_color=BORDER, corner_radius=0).place(
            relx=1.0, rely=0, relheight=1.0, anchor="ne")

        # Logo: mark + "Autopost" (navy) + "Video" (purple)
        logo = ctk.CTkFrame(sb, fg_color="transparent")
        logo.pack(fill="x", padx=18, pady=(26, 26))
        ctk.CTkLabel(logo, text="", image=brand_image("logo_mark.png", (32, 32))).pack(side="left")
        ctk.CTkLabel(logo, text="Autopost", font=F(19, "bold"), text_color=NAVY).pack(side="left", padx=(8, 0))
        ctk.CTkLabel(logo, text="Video", font=F(19, "bold"), text_color=PRIMARY).pack(side="left")

        self.nav_buttons = {}
        for key, label, code, _sub in self.PAGES:
            btn = ctk.CTkButton(sb, text=f"  {label}", image=glyph(code, TEXT_2, 18),
                compound="left", anchor="w", height=44, corner_radius=12,
                font=F(15, "medium"), fg_color="transparent", hover_color=BG,
                text_color=TEXT_2, command=lambda k=key: self._show_page(k))
            btn.pack(fill="x", padx=14, pady=2)
            self.nav_buttons[key] = (btn, code)

        ctk.CTkLabel(sb, text=f"{APP_NAME} v{APP_VERSION}", font=F(12), text_color=TEXT_3).pack(
            side="bottom", pady=(0, 16))

        # Connection summary — always visible (DESIGN.md §2.3)
        conn = ctk.CTkFrame(sb, fg_color=SURFACE_2, corner_radius=14, border_width=1, border_color=BORDER)
        conn.pack(side="bottom", fill="x", padx=14, pady=(0, 12))
        ctk.CTkLabel(conn, text="การเชื่อมต่อ", font=F(13, "semibold"), text_color=TEXT,
                     anchor="w").pack(fill="x", padx=14, pady=(12, 4))
        for pkey, (name, _color) in PLATFORMS.items():
            row = ctk.CTkFrame(conn, fg_color="transparent", cursor="hand2")
            row.pack(fill="x", padx=14, pady=3)
            ic = ctk.CTkLabel(row, text="", image=get_icon(pkey, (16, 16)), width=18)
            ic.pack(side="left")
            nm = ctk.CTkLabel(row, text=name, font=F(13), text_color=TEXT_2, anchor="w")
            nm.pack(side="left", padx=(8, 0))
            dot = ctk.CTkLabel(row, text="●", font=F(12), text_color=BORDER_2, width=14)
            dot.pack(side="right")
            for w in (row, ic, nm, dot):
                w.bind("<Button-1>", lambda _e: self._show_page("platforms"))
            self._conn_listeners[pkey].append(
                lambda kind, short, detail, d=dot: d.configure(text_color=STATUS_STYLE[kind][2]))
        ctk.CTkFrame(conn, height=8, fg_color="transparent").pack()

    def _show_page(self, key):
        for k, page in self.pages.items():
            if k == key:
                page.pack(fill="both", expand=True)
            else:
                page.pack_forget()
        for k, (btn, code) in self.nav_buttons.items():
            active = k == key
            btn.configure(fg_color=PRIMARY_TINT if active else "transparent",
                          hover_color=PRIMARY_TINT if active else BG,
                          text_color=PRIMARY if active else TEXT_2,
                          image=glyph(code, PRIMARY if active else TEXT_2, 18))
        _k, label, _c, sub = next(p for p in self.PAGES if p[0] == key)
        self.lbl_page_title.configure(text=label)
        self.lbl_page_sub.configure(text=sub)
        self.current_page = key

    # ── TOP BAR + TOAST ───────────────────────────────────────────────────
    def _build_topbar(self, main):
        bar = ctk.CTkFrame(main, fg_color=BG, corner_radius=0, height=104)
        bar.grid(row=0, column=0, sticky="ew")
        bar.pack_propagate(False)
        self.lbl_page_title = ctk.CTkLabel(bar, text="", font=F(28, "bold"), text_color=NAVY, anchor="w")
        self.lbl_page_title.pack(fill="x", padx=32, pady=(26, 0))
        self.lbl_page_sub = ctk.CTkLabel(bar, text="", font=F(14), text_color=TEXT_2, anchor="w")
        self.lbl_page_sub.pack(fill="x", padx=32)

        self.toast = ctk.CTkFrame(bar, fg_color=SURFACE, corner_radius=12,
                                  border_width=1, border_color=BORDER)
        self.toast_dot = ctk.CTkLabel(self.toast, text="●", font=F(12), width=12)
        self.toast_dot.pack(side="left", padx=(14, 6), pady=10)
        self.toast_lbl = ctk.CTkLabel(self.toast, text="", font=F(14), wraplength=420,
                                      justify="left", anchor="w")
        self.toast_lbl.pack(side="left", padx=(0, 16), pady=10)

    def _toast(self, text, color):
        kind = COLOR_KIND.get(color, "info")
        fg, bg, dot = STATUS_STYLE[kind]
        if kind == "info":
            dot = color if color not in (MUTED, None) else PRIMARY
        self.toast.configure(fg_color=bg, border_color=BORDER if kind == "info" else dot)
        self.toast_dot.configure(text_color=dot)
        self.toast_lbl.configure(text=text, text_color=fg)
        self.toast.place(relx=1.0, x=-32, y=30, anchor="ne")
        if self._toast_job:
            self.after_cancel(self._toast_job)
        self._toast_job = self.after(7000 if kind == "err" else 4500, self._hide_toast)

    def _hide_toast(self):
        self._toast_job = None
        self.toast.place_forget()

    # ── CARD HELPERS ──────────────────────────────────────────────────────
    def _card_header(self, card, title, subtitle=None):
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=(18, 12 if not subtitle else 2))
        ctk.CTkLabel(row, text=title, font=F(20, "semibold"), text_color=NAVY, anchor="w").pack(side="left")
        if subtitle:
            ctk.CTkLabel(card, text=subtitle, font=F(13), text_color=TEXT_2, anchor="w",
                         justify="left").pack(fill="x", padx=20, pady=(0, 12))
        return row

    def _field_label(self, parent, text, top=0):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=(top, 6))
        ctk.CTkLabel(row, text=text, font=F(15, "medium"), text_color=TEXT, anchor="w").pack(side="left")
        return row

    # ══════════════════════════════════════════════════════════════════════
    #  PAGE: CREATE POST
    # ══════════════════════════════════════════════════════════════════════
    def _build_create_page(self, host):
        page = ScrollPage(host)
        left = ctk.CTkFrame(page, fg_color="transparent")
        right = ctk.CTkFrame(page, fg_color="transparent")
        self._responsive_columns(page, [left, right], gap_y=20)

        # ── Video card ────────────────────────────────────────────────
        card = Card(left)
        card.pack(fill="x", pady=(0, 20))
        self._card_header(card, "วิดีโอ")

        self.dropzone = dz = ctk.CTkFrame(card, fg_color=SURFACE_2, corner_radius=14,
                                          border_width=2, border_color=BORDER_2)
        dz.pack(fill="x", padx=20, pady=(0, 20))

        circle = ctk.CTkFrame(dz, fg_color=PRIMARY_SOFT, corner_radius=28, width=56, height=56)
        circle.pack(pady=(24, 10))
        circle.pack_propagate(False)
        self.lbl_drop_icon = ctk.CTkLabel(circle, text="", image=glyph(G_UPLOAD, PRIMARY, 26))
        self.lbl_drop_icon.place(relx=0.5, rely=0.5, anchor="center")

        self.lbl_drop_title = ctk.CTkLabel(dz, text="", font=F(16, "semibold"), text_color=NAVY)
        self.lbl_drop_title.pack()
        self.lbl_file = ctk.CTkLabel(dz, text="", font=F(13), text_color=TEXT_2)
        self.lbl_file.pack(pady=(2, 14))

        btn_box = ctk.CTkFrame(dz, fg_color="transparent")
        btn_box.pack(pady=(0, 24))
        self.btn_browse = SecondaryButton(btn_box, "เลือกไฟล์วิดีโอ", self.browse_file,
                                          icon=G_FOLDER, width=160)
        self.btn_browse.pack(side="left", padx=4)
        self.btn_clear_file = DangerButton(btn_box, "ล้าง", self.clear_file, width=80)

        for w in (dz, circle, self.lbl_drop_icon, self.lbl_drop_title, self.lbl_file):
            w.configure(cursor="hand2")
            w.bind("<Button-1>", lambda _e: self.browse_file())

        # ── Details card ──────────────────────────────────────────────
        card = Card(left)
        card.pack(fill="x")
        self._card_header(card, "รายละเอียดโพสต์")

        title_row = self._field_label(card, "ชื่อคลิป")
        self.lbl_title_count = ctk.CTkLabel(title_row, text="", font=F(12), text_color=TEXT_3)
        self.lbl_title_count.pack(side="right")
        self.entry_title = Entry(card, "ตั้งชื่อคลิปของคุณ…")
        self.entry_title.pack(fill="x", padx=20)
        self.entry_title.bind("<KeyRelease>", lambda _e: self._update_title_counter())

        self._field_label(card, "คำอธิบาย", top=16)
        self.txt_desc = Textbox(card, height=110)
        self.txt_desc.pack(fill="x", padx=20)
        self._attach_placeholder(self.txt_desc,
            "เขียนคำอธิบายหรือแคปชัน (ไม่บังคับ) — ใช้กับทุกแพลตฟอร์ม", TEXT)

        ht_row = self._field_label(card, "แฮชแท็ก", top=16)
        ctk.CTkLabel(ht_row, text="คั่นด้วยเว้นวรรคหรือจุลภาค", font=F(12),
                     text_color=TEXT_3).pack(side="right")
        self.txt_hashtags = Textbox(card, height=64, text_color=PRIMARY_H)
        self.txt_hashtags.pack(fill="x", padx=20, pady=(0, 20))
        self.txt_hashtags.insert("end", self.settings.get("hashtags", "shorts  viral  fyp"))

        # ── Platforms card ────────────────────────────────────────────
        card = Card(right)
        card.pack(fill="x", pady=(0, 20))
        hdr = self._card_header(card, "แพลตฟอร์ม")
        self.lbl_platform_count = ctk.CTkLabel(hdr, text="", font=F(13), text_color=TEXT_2)
        self.lbl_platform_count.pack(side="right")

        saved = self.settings.get("platforms", {})
        defaults = {"yt": True, "tt": True, "fb": False, "ig": False}
        self.platform_rows = {}
        for i, (pkey, (name, _c)) in enumerate(PLATFORMS.items()):
            var = tk.BooleanVar(value=saved.get(pkey, defaults[pkey]))
            setattr(self, f"var_{pkey}", var)
            if i:
                ctk.CTkFrame(card, height=1, fg_color=BORDER, corner_radius=0).pack(fill="x", padx=20)
            self._build_platform_row(card, pkey, name, var, last=i == len(PLATFORMS) - 1)

        # ── Schedule card ─────────────────────────────────────────────
        card = Card(right)
        card.pack(fill="x")
        hdr = self._card_header(card, "ตั้งเวลาโพสต์",
                                "ปิดไว้ = โพสต์ทันที · ต้องเปิดแอปค้างไว้จนถึงเวลาโพสต์")
        self.var_schedule = tk.BooleanVar(value=False)
        Switch(hdr, self.var_schedule, command=self._toggle_schedule).pack(side="right")

        self.sch_inputs = ctk.CTkFrame(card, fg_color="transparent")   # packed when schedule ON
        grid = ctk.CTkFrame(self.sch_inputs, fg_color="transparent")
        grid.pack(fill="x", padx=18)
        grid.grid_columnconfigure((0, 1), weight=1, uniform="dt")
        ctk.CTkLabel(grid, text="วันที่", font=F(14, "medium"), text_color=TEXT, anchor="w").grid(
            row=0, column=0, sticky="w")
        ctk.CTkLabel(grid, text="เวลา", font=F(14, "medium"), text_color=TEXT, anchor="w").grid(
            row=0, column=1, sticky="w", padx=(12, 0))
        self.entry_date = Entry(grid, "YYYY-MM-DD", height=40)
        self.entry_date.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        self.entry_time = Entry(grid, "HH:MM", height=40)
        self.entry_time.grid(row=1, column=1, sticky="ew", padx=(12, 0), pady=(4, 0))

        presets = ctk.CTkFrame(self.sch_inputs, fg_color="transparent")
        presets.pack(fill="x", padx=18, pady=(12, 0))
        for label, val in [("+1 ชม.", "+1h"), ("+3 ชม.", "+3h"),
                           ("พรุ่งนี้ 09:00", "tomorrow_09"), ("พรุ่งนี้ 18:00", "tomorrow_18")]:
            ctk.CTkButton(presets, text=label, command=lambda v=val: self._apply_schedule_preset(v),
                fg_color=SURFACE, hover_color=PRIMARY_TINT, text_color=PRIMARY_H,
                border_width=1, border_color=PRIMARY_SOFT, height=30, width=0,
                corner_radius=15, font=F(12, "medium")).pack(side="left", padx=(0, 6), pady=(0, 6))

        self.lbl_countdown = ctk.CTkLabel(self.sch_inputs, text="", font=F(14, "semibold"),
                                          text_color=PRIMARY_H, anchor="w")
        self.lbl_countdown.pack(fill="x", padx=18, pady=(6, 18))
        self._sch_spacer = ctk.CTkFrame(card, height=6, fg_color="transparent")
        self._sch_spacer.pack()
        return page

    def _build_platform_row(self, card, pkey, name, var, last):
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=(12, 16 if last else 12))

        top = ctk.CTkFrame(row, fg_color="transparent")
        top.pack(fill="x")
        ctk.CTkLabel(top, text="", image=get_icon(pkey, (26, 26)), width=30).pack(side="left")
        info = ctk.CTkFrame(top, fg_color="transparent")
        info.pack(side="left", padx=(10, 0), fill="x", expand=True)
        ctk.CTkLabel(info, text=name, font=F(15, "medium"), text_color=TEXT, anchor="w",
                     height=20).pack(fill="x")
        status = ctk.CTkLabel(info, text="", font=F(12), anchor="w", height=16, cursor="hand2")
        status.pack(fill="x")
        status.bind("<Button-1>", lambda _e: self._show_page("platforms"))
        self._conn_listeners[pkey].append(
            lambda kind, short, detail, s=status: s.configure(
                text=short, text_color=STATUS_STYLE[kind][0]))

        Switch(top, var, command=lambda: self._on_platform_toggle()).pack(side="right")

        detail = ctk.CTkFrame(row, fg_color="transparent")
        if pkey in VISIBILITY:
            opts = VISIBILITY[pkey]
            saved = self.settings.get(f"{pkey}_privacy")
            values = [v for v, _l in opts]
            if pkey == "yt" and isinstance(saved, str):
                saved = saved.lower()      # older settings stored "Public"
            pv = tk.StringVar(value=saved if saved in values else values[0])
            setattr(self, f"{pkey}_privacy", pv)
            ChipGroup(detail, opts, pv).pack(anchor="w", padx=(40, 0), pady=(10, 0))
        else:
            ctk.CTkLabel(detail, text="ใช้การตั้งค่าความเป็นส่วนตัวของบัญชี Instagram",
                         font=F(12), text_color=TEXT_3, anchor="w").pack(
                anchor="w", padx=(40, 0), pady=(6, 0))
        self.platform_rows[pkey] = detail

    def _on_platform_toggle(self):
        self._update_settings_visibility_rows()
        self._update_post_button_text()
        self._update_title_counter()

    # ══════════════════════════════════════════════════════════════════════
    #  PAGE: PLATFORMS (accounts)
    # ══════════════════════════════════════════════════════════════════════
    def _build_platforms_page(self, host):
        page = ScrollPage(host)
        cells = [self._build_youtube_card(page)] + [
            self._build_cookie_card(page, k, COOKIE_DOMAINS[k].lstrip(".")) for k in ("tt", "fb", "ig")]
        self._responsive_columns(page, cells, gap_y=20)
        return page

    def _responsive_columns(self, page, cells, gap_y=20, breakpoint=860):
        """Two equal columns when the page is wide enough, otherwise stacked (DESIGN.md §5)."""
        page.grid_columnconfigure((0, 1), weight=1, uniform="col")
        state = {"cols": None}

        def layout(width):
            cols = 2 if width >= breakpoint else 1
            if cols == state["cols"]:
                return
            state["cols"] = cols
            for i, w in enumerate(cells):
                w.grid_forget()
                if cols == 2:
                    r, c = divmod(i, 2)
                    w.grid(row=r, column=c, sticky="nsew", pady=(4, gap_y),
                           padx=(22, 10) if c == 0 else (10, 16))
                else:
                    w.grid(row=i, column=0, columnspan=2, sticky="nsew", pady=(4, gap_y), padx=(22, 16))

        layout(2000)
        page.bind("<Configure>", lambda e: layout(e.width), add="+")

    def _platform_card_header(self, card, pkey):
        name = PLATFORMS[pkey][0]
        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=20, pady=(20, 12))
        tile = ctk.CTkFrame(top, fg_color=SURFACE_2, corner_radius=12, width=48, height=48,
                            border_width=1, border_color=BORDER)
        tile.pack(side="left")
        tile.pack_propagate(False)
        ctk.CTkLabel(tile, text="", image=get_icon(pkey, (28, 28))).place(relx=0.5, rely=0.5, anchor="center")

        info = ctk.CTkFrame(top, fg_color="transparent")
        info.pack(side="left", padx=(12, 0), fill="x", expand=True)
        ctk.CTkLabel(info, text=name, font=F(20, "semibold"), text_color=NAVY, anchor="w",
                     height=26).pack(fill="x")
        badge = StatusBadge(info)
        badge.pack(anchor="w", pady=(2, 0))

        detail = ctk.CTkLabel(card, text="", font=F(13), text_color=TEXT_2, anchor="w", justify="left")
        detail.pack(fill="x", padx=20)
        self._conn_listeners[pkey].append(
            lambda kind, short, d_text, b=badge, d=detail: (b.show(kind, short), d.configure(text=d_text)))
        return top

    def _build_youtube_card(self, parent):
        card = Card(parent)
        top = self._platform_card_header(card, "yt")
        self.btn_yt_account = SecondaryButton(top, "", None, width=120)
        self.btn_yt_account.pack(side="right", anchor="n")

        steps = ("1. วาง credentials.json (OAuth Desktop client) ไว้ข้างแอป\n"
                 "2. กด “เข้าสู่ระบบ” แล้วอนุญาตในเบราว์เซอร์\n"
                 "3. แอปจะจำการเข้าสู่ระบบและต่ออายุให้อัตโนมัติ")
        ctk.CTkLabel(card, text=steps, font=F(13), text_color=TEXT_2, justify="left",
                     anchor="w").pack(fill="x", padx=20, pady=(10, 20))
        self._conn_listeners["yt"].append(lambda *_: self._sync_yt_button())
        return card

    def _build_cookie_card(self, parent, pkey, site):
        card = Card(parent)
        top = self._platform_card_header(card, pkey)
        btn_disc = DangerButton(top, "ยกเลิกการเชื่อมต่อ", lambda: self._clear_cookies(pkey), width=120)
        self._conn_listeners[pkey].append(
            lambda kind, *_a, b=btn_disc: b.pack(side="right", anchor="n") if kind != "off" else b.pack_forget())

        steps = (f"1. ติดตั้งส่วนขยาย Chrome «Cookie-Editor»\n"
                 f"2. เปิด {site} และเข้าสู่ระบบ\n"
                 f"3. Cookie-Editor → Export → Export as JSON\n"
                 f"4. กด “วางและนำเข้า” ด้านล่าง")
        ctk.CTkLabel(card, text=steps, font=F(13), text_color=TEXT_2, justify="left",
                     anchor="w").pack(fill="x", padx=20, pady=(10, 12))

        textbox = Textbox(card, height=64, text_color=TEXT_2, font=Mono(11))
        textbox.pack(fill="x", padx=20)
        self._attach_placeholder(textbox, "…หรือวาง cookies JSON ที่นี่ แล้วกด “นำเข้า”", TEXT_2)
        setattr(self, f"txt_{pkey}_cookies", textbox)

        btns = ctk.CTkFrame(card, fg_color="transparent")
        btns.pack(fill="x", padx=20, pady=(12, 20))
        btns.grid_columnconfigure(0, weight=1)
        PrimaryButton(btns, "วางและนำเข้า", lambda: self._paste_clipboard_and_import(pkey),
                      height=40, icon=G_PASTE).grid(row=0, column=0, sticky="ew")
        SecondaryButton(btns, "นำเข้า", lambda: self._import_cookies(pkey), width=90).grid(
            row=0, column=1, padx=(8, 0))
        return card

    # ══════════════════════════════════════════════════════════════════════
    #  PAGE: ACTIVITY
    # ══════════════════════════════════════════════════════════════════════
    def _build_activity_page(self, host):
        page = ctk.CTkFrame(host, fg_color=BG, corner_radius=0)
        card = Card(page)
        card.pack(fill="both", expand=True, padx=(22, 32), pady=(4, 24))
        hdr = self._card_header(card, "บันทึกการทำงาน")
        SecondaryButton(hdr, "ล้างหน้าจอ", self._clear_log_view, height=34, icon=G_DELETE).pack(side="right")
        SecondaryButton(hdr, "เปิดไฟล์ log", self._open_log_file, height=34, icon=G_DOC).pack(
            side="right", padx=(0, 8))

        self.log_box = ctk.CTkTextbox(card, font=Mono(12), fg_color=SURFACE_2,
            border_width=1, border_color=BORDER, text_color=TEXT_2, corner_radius=12,
            state="disabled", wrap="word",
            scrollbar_button_color=BORDER_2, scrollbar_button_hover_color=TEXT_3)
        self.log_box.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.txt_log = self.log_box   # alias for compat
        return page

    def _clear_log_view(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    # ══════════════════════════════════════════════════════════════════════
    #  PAGE: SETTINGS
    # ══════════════════════════════════════════════════════════════════════
    def _build_settings_page(self, host):
        page = ScrollPage(host)
        wrap = ctk.CTkFrame(page, fg_color="transparent")
        wrap.pack(fill="x", padx=(22, 16), pady=(4, 24))

        def setting_row(title, desc, button):
            card = Card(wrap)
            card.pack(fill="x", pady=(0, 16))
            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(fill="x", padx=20, pady=18)
            text = ctk.CTkFrame(inner, fg_color="transparent")
            text.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(text, text=title, font=F(16, "semibold"), text_color=NAVY, anchor="w").pack(fill="x")
            ctk.CTkLabel(text, text=desc, font=F(13), text_color=TEXT_2, anchor="w",
                         justify="left").pack(fill="x")
            b = button(inner)
            b.pack(side="right", padx=(16, 0))
            return b

        self.btn_clean_cache = setting_row(
            "ล้างแคชเบราว์เซอร์",
            "ลบโปรไฟล์เบราว์เซอร์ชั่วคราวของ Playwright ที่ค้างอยู่ใน %TEMP%",
            lambda p: SecondaryButton(p, "ล้างแคช", self.manual_clean_cache, icon=G_DELETE, width=130))
        setting_row(
            "ไฟล์บันทึก (log)",
            "ใช้ตรวจสอบรายละเอียดเมื่อโพสต์ไม่สำเร็จ",
            lambda p: SecondaryButton(p, "เปิดไฟล์ log", self._open_log_file, icon=G_DOC, width=130))
        setting_row(
            "โฟลเดอร์แอป",
            "ที่เก็บ credentials.json, cookies และการตั้งค่า",
            lambda p: SecondaryButton(p, "เปิดโฟลเดอร์", self._open_app_folder, icon=G_FOLDER, width=130))

        about = Card(wrap)
        about.pack(fill="x")
        inner = ctk.CTkFrame(about, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=20)
        ctk.CTkLabel(inner, text="", image=brand_image("app_icon.png", (64, 64))).pack(side="left")
        text = ctk.CTkFrame(inner, fg_color="transparent")
        text.pack(side="left", padx=(16, 0))
        name = ctk.CTkFrame(text, fg_color="transparent")
        name.pack(anchor="w")
        ctk.CTkLabel(name, text="Autopost", font=F(22, "bold"), text_color=NAVY).pack(side="left")
        ctk.CTkLabel(name, text="Video", font=F(22, "bold"), text_color=PRIMARY).pack(side="left")
        ctk.CTkLabel(name, text=f"  v{APP_VERSION}", font=F(13), text_color=TEXT_3).pack(side="left", pady=(6, 0))
        ctk.CTkLabel(text, text="สร้างคอนเทนต์ แล้วให้เราช่วยโพสต์", font=F(15, "medium"),
                     text_color=TEXT, anchor="w").pack(anchor="w")
        ctk.CTkLabel(text, text="ตั้งเวลา  |  โพสต์อัตโนมัติ  |  หลายแพลตฟอร์ม", font=F(13),
                     text_color=TEXT_2, anchor="w").pack(anchor="w")
        return page

    def _open_app_folder(self):
        try:
            os.startfile(APP_DIR)
        except Exception as e:
            self.update_status(f"เปิดโฟลเดอร์ไม่ได้: {e}", ERROR)

    # ── ACTION BAR ────────────────────────────────────────────────────────
    def _build_action_bar(self, main):
        bar = ctk.CTkFrame(main, fg_color=SURFACE, corner_radius=0, height=84)
        bar.grid(row=2, column=0, sticky="ew")
        bar.pack_propagate(False)
        ctk.CTkFrame(bar, height=1, fg_color=BORDER, corner_radius=0).place(
            relx=0, rely=0, relwidth=1.0)

        inner = ctk.CTkFrame(bar, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=32, pady=16)

        self.btn_post = PrimaryButton(inner, "", self._on_post_button, height=50, width=300)
        self.btn_post.configure(font=F(16, "semibold"))
        self.btn_post.pack(side="right")

        left = ctk.CTkFrame(inner, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True, padx=(0, 24))
        self.lbl_progress = ctk.CTkLabel(left, text="", font=F(14, "medium"),
                                         text_color=TEXT_2, anchor="w", height=22)
        self.lbl_progress.pack(fill="x")
        self.progress_bar = ctk.CTkProgressBar(left, mode="determinate", height=6,
            corner_radius=3, fg_color=BORDER, progress_color=PRIMARY)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", pady=(8, 0))
        self._set_idle_progress()

    def _set_idle_progress(self):
        self.progress_bar.set(0)
        self.lbl_progress.configure(text="พร้อมโพสต์", text_color=TEXT_2)

    # ── TEXTBOX PLACEHOLDER ───────────────────────────────────────────────
    def _attach_placeholder(self, tb, text, text_color):
        """Grey hint text that disappears on focus (CTkTextbox has no placeholder)."""
        def show(_e=None):
            if not tb.get("1.0", "end-1c").strip():
                tb.delete("1.0", "end")
                tb.insert("1.0", text)
                tb.configure(text_color=TEXT_3)
                tb._ph_on = True

        def hide(_e=None):
            if getattr(tb, "_ph_on", False):
                tb.delete("1.0", "end")
                tb.configure(text_color=text_color)
                tb._ph_on = False

        tb._ph_on = False
        tb._ph_show, tb._ph_hide = show, hide
        tb.bind("<FocusIn>", hide, add="+")
        tb.bind("<FocusOut>", show, add="+")
        show()

    @staticmethod
    def _textbox_value(tb):
        return "" if getattr(tb, "_ph_on", False) else tb.get("1.0", "end-1c").strip()

    @staticmethod
    def _textbox_reset(tb):
        tb.delete("1.0", "end")
        if hasattr(tb, "_ph_show"):
            tb._ph_show()

    # ══════════════════════════════════════════════════════════════════════
    #  CONNECTION STATUS (sidebar dots, platform rows, platform cards)
    # ══════════════════════════════════════════════════════════════════════
    def _set_conn(self, pkey, kind, short, detail=""):
        """kind: ok | warn | err | off. Must run on the main thread."""
        self._conn_state[pkey] = (kind, short, detail)
        for fn in self._conn_listeners[pkey]:
            fn(kind, short, detail)

    def _refresh_all_connections(self):
        self._refresh_yt_account_ui(loading=True)
        for k in ("tt", "fb", "ig"):
            self._set_conn(k, *self._cookie_status(self._cookies_path(k)))

    def _is_connected(self, pkey):
        if pkey == "yt":
            return os.path.exists(YT_TOKEN_PATH)
        return os.path.exists(self._cookies_path(pkey))

    # ══════════════════════════════════════════════════════════════════════
    #  SCHEDULE
    # ══════════════════════════════════════════════════════════════════════
    def _toggle_schedule(self):
        if self.var_schedule.get():
            self.sch_inputs.pack(fill="x", padx=2, before=self._sch_spacer)
            if not self.entry_date.get():
                self.entry_date.insert(0, datetime.now().strftime("%Y-%m-%d"))
        else:
            self.sch_inputs.pack_forget()
            if self._schedule_job:
                self._cancel_schedule()
            self.lbl_countdown.configure(text="")
        self._update_post_button_text()

    def _get_schedule_datetime(self):
        if not self.var_schedule.get():
            return None
        date_str = self.entry_date.get().strip() or datetime.now().strftime("%Y-%m-%d")
        time_str = self.entry_time.get().strip()
        if not time_str:
            raise ValueError("กรุณาใส่เวลาที่จะโพสต์ (HH:MM)")
        try:
            target = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        except ValueError:
            raise ValueError("วันที่/เวลาไม่ถูกต้อง — ใช้รูปแบบ YYYY-MM-DD และ HH:MM")
        if target <= datetime.now():
            raise ValueError("เวลาที่ตั้งต้องเป็นเวลาในอนาคต")
        return target

    def _start_countdown(self, target_dt, job):
        when = target_dt.strftime("%d/%m/%Y %H:%M")

        def tick():
            remaining = (target_dt - datetime.now()).total_seconds()
            if remaining <= 0:
                self._schedule_job = None
                self.lbl_countdown.configure(text="กำลังเริ่มโพสต์…", text_color=SUCCESS_T)
                self._start_posting(job)
                return
            h, rem = divmod(int(remaining), 3600)
            m, s   = divmod(rem, 60)
            left = f"{h:02d}:{m:02d}:{s:02d}"
            self.lbl_countdown.configure(text=f"⏰  อีก {left}", text_color=PRIMARY_H)
            self.lbl_progress.configure(text=f"ตั้งเวลาโพสต์ไว้ {when}  ·  อีก {left}",
                                        text_color=PRIMARY_H)
            self._schedule_job = self.after(1000, tick)

        tick()

    def _cancel_schedule(self):
        if self._schedule_job:
            self.after_cancel(self._schedule_job)
            self._schedule_job = None
        self.lbl_countdown.configure(text="")
        self._set_ui_state("idle")
        self.update_status("ยกเลิกการตั้งเวลาโพสต์แล้ว", WARNING)

    def _apply_schedule_preset(self, preset_type):
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

    # ══════════════════════════════════════════════════════════════════════
    #  HASHTAG BUILDER
    # ══════════════════════════════════════════════════════════════════════
    def _raw_tags(self):
        raw = self.txt_hashtags.get("1.0", tk.END).strip()
        tags, seen = [], set()
        for t in raw.replace(",", " ").split():
            t = t.strip().lstrip("#")
            if t and t.lower() not in seen:
                seen.add(t.lower())
                tags.append(t)
        return tags

    def _build_hashtags(self):
        return " ".join(f"#{t}" for t in self._raw_tags())

    def _get_tag_list(self):
        """Build YouTube tag list.

        YouTube Data API rules:
        - Each tag: max 100 characters
        - All tags combined: max 500 characters total
        - Tags containing spaces must be quoted (API handles this automatically)
        """
        defaults = ["Shorts", "YouTubeShorts"]

        # Deduplicate (preserve order, case-insensitive)
        combined, seen = [], set()
        for t in self._raw_tags() + defaults:
            if t.lower() not in seen:
                seen.add(t.lower())
                combined.append(t)

        # Enforce per-tag limit (100 chars each)
        combined = [t[:100] for t in combined if t]

        # Enforce total 500 char limit
        result = []
        total = 0
        for t in combined:
            if total + len(t) + (1 if result else 0) > 500:
                self._log(f"YouTube tags: reached 500-char limit, dropped '{t}' and beyond", WARNING)
                break
            total += len(t) + (1 if result else 0)
            result.append(t)
        return result

    # ══════════════════════════════════════════════════════════════════════
    #  POSTING
    # ══════════════════════════════════════════════════════════════════════
    def _selected_platforms(self):
        return [k for k in PLATFORMS if getattr(self, f"var_{k}").get()]

    def _on_post_button(self):
        if self._schedule_job:
            self._cancel_schedule()
        else:
            self._post_now()

    def _post_now(self):
        if self.is_posting or self._schedule_job:
            return

        platforms = self._selected_platforms()
        if not platforms:
            self.update_status("เลือกอย่างน้อย 1 แพลตฟอร์ม", ERROR)
            return
        if not self.video_path:
            self.update_status("กรุณาเลือกไฟล์วิดีโอก่อน", ERROR)
            return
        if not os.path.isfile(self.video_path):
            self.update_status("ไม่พบไฟล์วิดีโอที่เลือกแล้ว — กรุณาเลือกใหม่", ERROR)
            self.clear_file()
            return
        title = self.entry_title.get().strip()
        if not title:
            self.update_status("กรุณาใส่ชื่อคลิป", ERROR)
            self.entry_title.focus_set()
            return

        # Pre-flight: every selected platform must be connected
        missing = []
        if "yt" in platforms and not (os.path.exists(YT_TOKEN_PATH) or os.path.exists(YT_CREDS_PATH)):
            missing.append("YouTube (ไม่พบ credentials.json)")
        for k in ("tt", "fb", "ig"):
            if k in platforms and not os.path.exists(self._cookies_path(k)):
                missing.append(PLATFORMS[k][0])
        if missing:
            self.update_status(f"ยังไม่เชื่อมต่อ: {', '.join(missing)} — ตั้งค่าที่หน้าแพลตฟอร์ม", ERROR)
            self._show_page("platforms")
            return

        try:
            target_dt = self._get_schedule_datetime()
        except ValueError as e:
            self.update_status(str(e), ERROR)
            return

        # Snapshot every form value now — the worker thread must not touch Tk widgets,
        # and edits made while a post is scheduled shouldn't change it.
        job = {
            "video_path": self.video_path,
            "title":      title,
            "caption":    self._textbox_value(self.txt_desc),
            "hashtags":   self._build_hashtags(),
            "yt_tags":    self._get_tag_list() if "yt" in platforms else [],
            "platforms":  platforms,
            "yt_privacy": self.yt_privacy.get(),
            "tt_privacy": self.tt_privacy.get(),
            "fb_privacy": self.fb_privacy.get(),
        }
        self._save_settings()

        if target_dt:
            self._set_ui_state("scheduled")
            self._log(f"Scheduled for {target_dt.strftime('%Y-%m-%d  %H:%M')}", PRIMARY)
            self.update_status(f"ตั้งเวลาโพสต์ไว้ {target_dt.strftime('%d/%m/%Y %H:%M')} แล้ว", SUCCESS)
            self._start_countdown(target_dt, job)
        else:
            self._start_posting(job)

    def _start_posting(self, job):
        self._set_ui_state("posting")
        threading.Thread(target=self._run_posting, args=(job,), daemon=True).start()

    def _set_ui_state(self, mode):
        """mode: 'idle' | 'scheduled' | 'posting'"""
        self.is_posting = mode == "posting"
        self.btn_browse.configure(state="normal" if mode == "idle" else "disabled")
        self.btn_clean_cache.configure(state="disabled" if self.is_posting else "normal")
        if mode == "posting":
            self.btn_post.configure(text="กำลังโพสต์…", state="disabled", image=None,
                                    fg_color=PRIMARY_DIS, border_width=0)
        elif mode == "scheduled":
            self.btn_post.configure(text="ยกเลิกการตั้งเวลา", state="normal",
                                    image=glyph(G_CLOSE, ERROR_T, 16),
                                    fg_color=SURFACE, hover_color=ERROR_BG, text_color=ERROR_T,
                                    border_width=1, border_color=ERROR_BORDER)
        else:
            self._progress_prefix = ""
            self._set_idle_progress()
            self._update_post_button_text()

    def _set_progress(self, value: float, label: str, color=None):
        text = f"{self._progress_prefix}{label}"

        def _apply():
            self.progress_bar.set(max(0.0, min(1.0, value)))
            self.lbl_progress.configure(text=text, text_color=TEXT_SAFE.get(color, color) or TEXT_2)
        self._ui(_apply)

    def _run_posting(self, job):
        uploaders = {
            "yt": self.upload_to_youtube,
            "tt": self.upload_to_tiktok,
            "fb": self.upload_to_facebook,
            "ig": self.upload_to_instagram,
        }
        platforms = job["platforms"]
        results   = {}   # key -> "ok" | "unconfirmed" | "failed"

        self._log(f"─── {os.path.basename(job['video_path'])} ───", PRIMARY)
        try:
            for i, key in enumerate(platforms, 1):
                name = PLATFORMS[key][0]
                self._progress_prefix = f"[{i}/{len(platforms)}]  " if len(platforms) > 1 else ""
                try:
                    self.update_status(f"กำลังอัปโหลดไป {name}…", PRIMARY)
                    self._set_progress(0, f"{name} — กำลังเริ่ม…", PRIMARY)
                    confirmed = uploaders[key](job)
                    if confirmed is False:
                        results[key] = "unconfirmed"
                        self._set_progress(1.0, f"{name} — ส่งแล้ว (ยืนยันไม่ได้)", WARNING)
                        self.update_status(f"{name}: ส่งแล้วแต่ยืนยันไม่ได้ — โปรดตรวจสอบใน {name}", WARNING)
                    else:
                        results[key] = "ok"
                        self._set_progress(1.0, f"{name} ✓", SUCCESS)
                        self.update_status(f"โพสต์ไป {name} สำเร็จ ✓", SUCCESS)
                except Exception as e:
                    results[key] = "failed"
                    self._write_log_file(traceback.format_exc())
                    self.update_status(f"{name} ไม่สำเร็จ: {e}", ERROR)
                    self._set_progress(0, f"{name} ไม่สำเร็จ", ERROR)

        except Exception as e:
            self._write_log_file(traceback.format_exc())
            self.update_status(f"เกิดข้อผิดพลาดที่ไม่คาดคิด: {e}", ERROR)

        finally:
            marks   = {"ok": "✓", "unconfirmed": "?", "failed": "✗"}
            summary = "เสร็จสิ้น — " + "  |  ".join(
                f"{PLATFORMS[k][0]} {marks[results.get(k, 'failed')]}" for k in platforms)
            states  = [results.get(k, "failed") for k in platforms]
            if all(s == "ok" for s in states):
                color = SUCCESS
            elif all(s == "failed" for s in states):
                color = ERROR
            else:
                color = WARNING

            self.update_status(summary, color)
            self._notify_windows(APP_NAME, summary)

            def _finish():
                self._set_ui_state("idle")
                self.lbl_countdown.configure(text="")
                self.lbl_progress.configure(text=summary, text_color=TEXT_SAFE.get(color, color))
                self.progress_bar.set(1.0 if color != ERROR else 0)
            self._ui(_finish)

    # ══════════════════════════════════════════════════════════════════════
    #  WINDOWS NOTIFICATION
    # ══════════════════════════════════════════════════════════════════════
    def _notify_windows(self, title, message):
        def _do():
            if HAS_PLYER:
                try:
                    ico = asset("brand", "app_icon.ico")
                    plyer_notify.notify(title=title, message=message, app_name=APP_NAME,
                        app_icon=ico if os.path.exists(ico) else "", timeout=6)
                    return
                except Exception:
                    pass
            # Fallback: PowerShell toast
            try:
                import subprocess
                safe_msg = (message.replace("'", "").replace("&", "and")
                            .replace("<", "").replace(">", ""))
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
                    f"::CreateToastNotifier('{APP_NAME}')"
                    f".Show([Windows.UI.Notifications.ToastNotification]::New($x))"
                )
                subprocess.Popen(
                    ["powershell", "-WindowStyle", "Hidden", "-Command", ps],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            except Exception:
                pass
        threading.Thread(target=_do, daemon=True).start()

    # ══════════════════════════════════════════════════════════════════════
    #  LOGGING / STATUS (safe to call from any thread)
    # ══════════════════════════════════════════════════════════════════════
    def _log(self, msg, color=None):
        ts   = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}]  {msg}\n"
        self._write_log_file(line)
        self._ui(lambda: self._append_log(line, color))

    def _append_log(self, line, color):
        tags = ()
        if color:
            color = TEXT_SAFE.get(color, color)
            tag = "c" + color.lstrip("#")
            if tag not in self._log_tags:
                self.log_box.tag_config(tag, foreground=color)
                self._log_tags.add(tag)
            tags = (tag,)
        self.log_box.configure(state="normal")
        self.log_box.insert("end", line, tags)
        try:
            line_count = int(self.log_box.index("end-1c").split(".")[0])
            if line_count > 500:
                self.log_box.delete("1.0", f"{line_count - 500}.0")
        except Exception:
            pass
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _write_log_file(self, text):
        try:
            with self._log_lock, open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
                f.write(f"{datetime.now():%Y-%m-%d} {text}" if text.startswith("[") else text)
                if not text.endswith("\n"):
                    f.write("\n")
        except Exception:
            pass

    def _trim_log_file(self, max_bytes=2 * 1024 * 1024):
        try:
            if os.path.getsize(LOG_FILE_PATH) > max_bytes:
                with open(LOG_FILE_PATH, "rb") as f:
                    f.seek(-max_bytes // 2, os.SEEK_END)
                    tail = f.read()
                with open(LOG_FILE_PATH, "wb") as f:
                    f.write(tail)
        except Exception:
            pass

    def _open_log_file(self):
        if not os.path.exists(LOG_FILE_PATH):
            self.update_status("ยังไม่มีไฟล์ log", MUTED)
            return
        try:
            os.startfile(LOG_FILE_PATH)
        except Exception as e:
            self.update_status(f"เปิดไฟล์ log ไม่ได้: {e}", ERROR)

    def update_status(self, text, color=MUTED):
        def _apply():
            self._toast(text, color)
            self._log(text, None if color == MUTED else color)
        self._ui(_apply)

    # ── SETTINGS PERSISTENCE ────────────────────────────────────────────
    def _save_settings(self):
        self.settings.update({
            "platforms":  {k: getattr(self, f"var_{k}").get() for k in PLATFORMS},
            "hashtags":   self.txt_hashtags.get("1.0", "end-1c").strip(),
            "yt_privacy": self.yt_privacy.get(),
            "tt_privacy": self.tt_privacy.get(),
            "fb_privacy": self.fb_privacy.get(),
        })
        save_settings(self.settings)

    # ── UX ENHANCEMENT HELPERS ──────────────────────────────────────────
    def _update_post_button_text(self):
        active = [PLATFORMS[k][0] for k in self._selected_platforms()]
        if hasattr(self, "lbl_platform_count"):
            self.lbl_platform_count.configure(text=f"เลือกแล้ว {len(active)}/{len(PLATFORMS)}")
        if self.is_posting or self._schedule_job:
            return

        scheduled = self.var_schedule.get()
        primary = dict(fg_color=PRIMARY, hover_color=PRIMARY_H, text_color="#FFFFFF",
                       border_width=0, state="normal",
                       image=glyph(G_CLOCK if scheduled else G_SEND, "#FFFFFF", 18))
        if not active:
            self.btn_post.configure(text="เลือกแพลตฟอร์มก่อน", fg_color=PRIMARY_DIS,
                                    border_width=0, image=None, state="disabled")
            return
        target = active[0] if len(active) == 1 else f"{len(active)} แพลตฟอร์ม"
        verb = "ตั้งเวลาโพสต์" if scheduled else "โพสต์เลย"
        self.btn_post.configure(text=f"  {verb} · {target}", **primary)

    def _update_title_counter(self):
        if not hasattr(self, "lbl_title_count"):
            return
        n = len(self.entry_title.get().strip())
        limit = YT_TITLE_MAX - len(SHORTS_SUFFIX)
        if self.var_yt.get() and n > limit:
            self.lbl_title_count.configure(
                text=f"{n} ตัวอักษร · YouTube ใช้ได้ {limit} ตัวแรก (+ #Shorts)", text_color=WARNING_T)
        else:
            self.lbl_title_count.configure(text=f"{n} ตัวอักษร" if n else "", text_color=TEXT_3)

    def _update_settings_visibility_rows(self):
        for pkey, detail in self.platform_rows.items():
            if getattr(self, f"var_{pkey}").get():
                detail.pack(fill="x")
            else:
                detail.pack_forget()

    # ── VIDEO FILE ──────────────────────────────────────────────────────
    def browse_file(self):
        if self.is_posting or self._schedule_job:
            return
        path = filedialog.askopenfilename(
            initialdir=self.settings.get("last_dir") or None,
            filetypes=[("Video files", " ".join(f"*{e} *{e.upper()}" for e in VIDEO_EXTS)),
                       ("All files", "*.*")])
        if path:
            self._set_video(path)

    def _on_drag_enter(self, event):
        self._show_page("create")
        self.dropzone.configure(border_color=PRIMARY, fg_color=PRIMARY_TINT)
        return event.action

    def _on_drag_leave(self, event):
        self.dropzone.configure(border_color=PRIMARY_SOFT if self.video_path else BORDER_2,
                                fg_color=SURFACE_2)
        return event.action

    def _on_drop(self, event):
        if self.is_posting or self._schedule_job:
            self._on_drag_leave(event)
            return event.action
        paths = [p for p in self.tk.splitlist(event.data) if os.path.isfile(p)]
        videos = [p for p in paths if p.lower().endswith(VIDEO_EXTS)]
        if videos:
            self._set_video(videos[0])
            if len(videos) > 1:
                self.update_status("วางหลายไฟล์ — ใช้ไฟล์แรก", WARNING)
        else:
            self.update_status("ไฟล์นี้ไม่ใช่วิดีโอที่รองรับ (MP4, MOV, M4V, WEBM)", ERROR)
        self._on_drag_leave(event)
        return event.action

    def _set_video(self, path):
        if not os.path.isfile(path):
            self.update_status("ไม่พบไฟล์", ERROR)
            return
        self.video_path = path
        self.settings["last_dir"] = os.path.dirname(path)
        size_mb = os.path.getsize(path) / (1024 * 1024)
        folder = os.path.basename(os.path.dirname(path)) or os.path.dirname(path)
        if len(folder) > 32:
            folder = folder[:31] + "…"
        self.lbl_drop_title.configure(text=os.path.basename(path))
        self.lbl_file.configure(text=f"✓  {size_mb:.1f} MB  ·  โฟลเดอร์ {folder}", text_color=SUCCESS_T)
        self.lbl_drop_icon.configure(image=glyph(G_VIDEO, PRIMARY, 26))
        self.dropzone.configure(border_color=PRIMARY_SOFT)
        self.btn_browse.configure(text="เปลี่ยนไฟล์")
        self.btn_clear_file.pack(side="left", padx=4)
        # Suggest a title from the file name if the title is still empty
        if not self.entry_title.get().strip():
            self.entry_title.insert(0, os.path.splitext(os.path.basename(path))[0].replace("_", " "))
            self._update_title_counter()

    def clear_file(self):
        self.video_path = ""
        self.lbl_drop_title.configure(
            text="ลากไฟล์วิดีโอมาวางที่นี่" if self.dnd_ready else "คลิกเพื่อเลือกไฟล์วิดีโอ")
        self.lbl_file.configure(
            text=("หรือคลิกเพื่อเลือกไฟล์  ·  " if self.dnd_ready else "") + "MP4, MOV, M4V, WEBM",
            text_color=TEXT_2)
        self.lbl_drop_icon.configure(image=glyph(G_UPLOAD, PRIMARY, 26))
        self.dropzone.configure(border_color=BORDER_2)
        self.btn_browse.configure(text="เลือกไฟล์วิดีโอ")
        self.btn_clear_file.pack_forget()

    # ── CACHE MANAGEMENT ────────────────────────────────────────────────
    def clean_playwright_cache(self):
        import glob, shutil
        temp_dir = os.environ.get("TEMP", "")
        if not temp_dir:
            return 0, 0.0
        freed_bytes = 0
        cleaned_count = 0
        for path in glob.glob(os.path.join(temp_dir, "playwright*")):
            try:
                if os.path.isdir(path):
                    size = sum(os.path.getsize(os.path.join(dirpath, filename))
                               for dirpath, _, filenames in os.walk(path)
                               for filename in filenames)
                    shutil.rmtree(path, ignore_errors=True)
                    if not os.path.exists(path):
                        freed_bytes += size
                        cleaned_count += 1
            except Exception:
                pass
        return cleaned_count, freed_bytes / (1024 * 1024)

    def manual_clean_cache(self):
        if self.is_posting:
            self.update_status("ล้างแคชระหว่างอัปโหลดไม่ได้", WARNING)
            return
        self.btn_clean_cache.configure(state="disabled", text="กำลังล้าง…")

        def work():
            count, mb = self.clean_playwright_cache()
            if count > 0:
                self.update_status(f"ล้างแคชแล้ว {count} โฟลเดอร์ (คืนพื้นที่ {mb:.1f} MB) ✓", SUCCESS)
            else:
                self.update_status("แคชเบราว์เซอร์สะอาดอยู่แล้ว ✓", SUCCESS)
            self._ui(lambda: self.btn_clean_cache.configure(
                state="disabled" if self.is_posting else "normal", text="ล้างแคช"))
        threading.Thread(target=work, daemon=True).start()

    def _setup_fast_route_blocking(self, page):
        """Block heavy tracking/analytics requests to speed up upload page load times by 30-50%."""
        try:
            blocked_keywords = ["google-analytics", "analytics.tiktok", "connect.facebook.net", "doubleclick", "scorecardresearch"]
            page.route(lambda url: any(b in url for b in blocked_keywords), lambda route: route.abort())
        except Exception:
            pass

    def _launch_browser(self, p, maximized=True):
        """Prefer the installed Google Chrome; fall back to Playwright's bundled Chromium."""
        args = ["--disable-blink-features=AutomationControlled",
                "--disk-cache-size=1048576", "--media-cache-size=1048576"]
        if maximized:
            args.append("--start-maximized")
        try:
            return p.chromium.launch(channel="chrome", headless=False, args=args)
        except Exception as e:
            self._log(f"Google Chrome unavailable ({str(e).splitlines()[0][:80]}) — using bundled Chromium", WARNING)
            return p.chromium.launch(headless=False, args=args)

    @staticmethod
    def _social_caption(job, limit=None):
        """Title + caption + hashtags for TikTok / Facebook / Instagram."""
        title, caption, hashtags = job["title"], job["caption"], job["hashtags"]
        if caption:
            text = "\n".join(p for p in (title, caption, hashtags) if p)
        else:
            text = f"{title}  {hashtags}".strip() if hashtags else title
        return text[:limit] if limit else text

    def _cookie_status(self, cookies_path):
        """Return (kind, short, detail) for a cookie file."""
        if not os.path.exists(cookies_path):
            return "off", "ยังไม่เชื่อมต่อ", "นำเข้า cookies เพื่อเริ่มใช้งาน"
        try:
            with open(cookies_path, "r", encoding="utf-8") as f:
                cookies_list = json.load(f)
            count   = len(cookies_list)
            saved   = datetime.fromtimestamp(
                os.path.getmtime(cookies_path)).strftime("%d/%m/%Y")

            key_names = ("sessionid", "sid_tt", "sid_guard", "passport_auth_token",
                         "c_user", "xs", "sessionid_ss", "csrftoken")
            earliest = None
            for c in cookies_list:
                if c.get("name", "").lower() in key_names:
                    exp = c.get("expirationDate") or c.get("expires")
                    if exp and float(exp) > 0:
                        exp_dt = datetime.fromtimestamp(float(exp))
                        if earliest is None or exp_dt < earliest:
                            earliest = exp_dt

            if earliest:
                days_left = (earliest - datetime.now()).days
                if days_left < 0:
                    return "err", "เซสชันหมดอายุ", "กรุณานำเข้า cookies ใหม่"
                elif days_left <= 7:
                    return "err", "ใกล้หมดอายุ", f"หมดอายุใน {days_left} วัน — ควรนำเข้าใหม่"
                elif days_left <= 14:
                    return "warn", "เชื่อมต่อแล้ว", f"หมดอายุใน {days_left} วัน"
            return "ok", "เชื่อมต่อแล้ว", f"{count} cookies · นำเข้าเมื่อ {saved}"
        except Exception:
            return "warn", "ไฟล์ cookies เสียหาย", "กรุณานำเข้าใหม่"

    # ══════════════════════════════════════════════════════════════════════
    #  YOUTUBE ACCOUNT
    # ══════════════════════════════════════════════════════════════════════
    def _save_yt_creds(self, creds):
        with open(YT_TOKEN_PATH, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

    def _load_yt_creds(self):
        """Saved YouTube credentials (refreshed if expired), or None. Caller holds _yt_lock."""
        if not os.path.exists(YT_TOKEN_PATH):
            return None
        creds = google.oauth2.credentials.Credentials.from_authorized_user_file(YT_TOKEN_PATH)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            self._save_yt_creds(creds)
        return creds

    def _yt_sign_in(self):
        """Interactive OAuth in the user's browser. Caller holds _yt_lock."""
        if not os.path.exists(YT_CREDS_PATH):
            raise Exception("ไม่พบ credentials.json — วางไฟล์ไว้ข้างแอป (ดู README)")
        self._log("Opening your browser for YouTube sign-in…", YT)
        flow = InstalledAppFlow.from_client_secrets_file(
            YT_CREDS_PATH, [YT_SCOPE_UPLOAD, YT_SCOPE_READONLY])
        try:
            creds = flow.run_local_server(
                port=0, timeout_seconds=300,
                success_message=f"{APP_NAME} เชื่อมต่อกับ YouTube แล้ว ปิดแท็บนี้ได้เลย")
        except Exception as e:
            if "Timed out" in str(e):
                raise Exception("หมดเวลาเข้าสู่ระบบ YouTube (5 นาที) — กรุณาลองใหม่")
            raise
        self._save_yt_creds(creds)
        return creds

    def _refresh_yt_account_ui(self, loading=False):
        if os.path.exists(YT_TOKEN_PATH):
            self._set_conn("yt", "ok", "เชื่อมต่อแล้ว",
                           "กำลังโหลดชื่อช่อง…" if loading else "บัญชี YouTube พร้อมใช้งาน")
        elif os.path.exists(YT_CREDS_PATH):
            self._set_conn("yt", "off", "ยังไม่เชื่อมต่อ",
                           "กด “เข้าสู่ระบบ” หรือเข้าสู่ระบบตอนอัปโหลดครั้งแรก")
        else:
            self._set_conn("yt", "err", "ไม่พบ credentials.json",
                           "วาง credentials.json ไว้ข้างแอปก่อน (ดู README)")

    def _sync_yt_button(self):
        if os.path.exists(YT_TOKEN_PATH):
            self.btn_yt_account.configure(text="ยกเลิกการเชื่อมต่อ", command=self.yt_logout,
                fg_color=SURFACE, hover_color=ERROR_BG, text_color=ERROR_T,
                border_color=ERROR_BORDER, state="normal")
        else:
            self.btn_yt_account.configure(text="เข้าสู่ระบบ", command=self.yt_connect,
                fg_color=PRIMARY, hover_color=PRIMARY_H, text_color="#FFFFFF",
                border_color=PRIMARY,
                state="normal" if os.path.exists(YT_CREDS_PATH) and not self._yt_signing_in
                      else "disabled")

    def _fetch_yt_channel_name(self):
        expired = ("warn", "ต้องเข้าสู่ระบบใหม่", "การเข้าสู่ระบบหมดอายุ — จะถามอีกครั้งตอนอัปโหลด")
        try:
            with self._yt_lock:
                creds = self._load_yt_creds()
            if not creds or not creds.valid:
                self._ui(lambda: self._set_conn("yt", *expired))
                return
            if not creds.has_scopes([YT_SCOPE_READONLY]):
                # Older tokens were granted upload-only scope (can't read channel name)
                self._ui(lambda: self._set_conn("yt", "ok", "เชื่อมต่อแล้ว",
                                                "เข้าสู่ระบบใหม่เพื่อแสดงชื่อช่อง"))
                return
            yt    = build("youtube", "v3", credentials=creds, cache_discovery=False)
            resp  = yt.channels().list(part="snippet", mine=True).execute()
            items = resp.get("items", [])
            name  = items[0]["snippet"]["title"] if items else None
            self._ui(lambda: self._set_conn("yt", "ok", "เชื่อมต่อแล้ว",
                                            f"ช่อง: {name}" if name else "บัญชี YouTube พร้อมใช้งาน"))
        except RefreshError:
            self._ui(lambda: self._set_conn("yt", *expired))
        except Exception:
            self._ui(lambda: self._set_conn("yt", "ok", "เชื่อมต่อแล้ว",
                                            "ออฟไลน์ — โหลดชื่อช่องไม่ได้"))

    def yt_connect(self):
        if self._yt_signing_in or self.is_posting:
            return
        self._yt_signing_in = True
        self._set_conn("yt", "warn", "รอเข้าสู่ระบบ…", "ทำต่อในเบราว์เซอร์ที่เปิดขึ้นมา")

        def work():
            try:
                with self._yt_lock:
                    self._yt_sign_in()
                self._yt_signing_in = False
                self.update_status("เชื่อมต่อ YouTube แล้ว ✓", SUCCESS)
                self._ui(self._refresh_yt_account_ui)
                self._fetch_yt_channel_name()
            except Exception as e:
                self._yt_signing_in = False
                self.update_status(f"เข้าสู่ระบบ YouTube ไม่สำเร็จ: {e}", ERROR)
                self._ui(self._refresh_yt_account_ui)
        threading.Thread(target=work, daemon=True).start()

    def yt_logout(self):
        ok = messagebox.askyesno(
            "ยกเลิกการเชื่อมต่อ YouTube",
            "ลบการเข้าสู่ระบบ YouTube ที่บันทึกไว้?\n\nต้องเข้าสู่ระบบใหม่ก่อนอัปโหลดครั้งถัดไป",
            icon="warning")
        if not ok:
            return
        if os.path.exists(YT_TOKEN_PATH):
            os.remove(YT_TOKEN_PATH)
        self._refresh_yt_account_ui()
        self._log("YouTube login removed")

    # ══════════════════════════════════════════════════════════════════════
    #  COOKIE ACCOUNTS (TikTok / Facebook / Instagram)
    # ══════════════════════════════════════════════════════════════════════
    def _cookies_path(self, pkey):
        return os.path.join(APP_DIR, COOKIE_FILES[pkey])

    def _tt_cookies_path(self):
        return self._cookies_path("tt")

    def _fb_cookies_path(self):
        return self._cookies_path("fb")

    def _ig_cookies_path(self):
        return self._cookies_path("ig")

    def _import_cookies(self, pkey):
        name    = PLATFORMS[pkey][0]
        textbox = getattr(self, f"txt_{pkey}_cookies")
        raw     = self._textbox_value(textbox)
        if not raw:
            self.update_status(f"วาง cookies JSON ของ {name} ก่อน", ERROR)
            return False
        try:
            clean = normalize_cookies(raw, COOKIE_DOMAINS[pkey])
        except json.JSONDecodeError:
            self.update_status(f"{name}: ข้อมูลไม่ใช่ JSON — ใช้ Cookie-Editor → Export as JSON", ERROR)
            return False
        except Exception as e:
            self.update_status(f"นำเข้า {name} ไม่สำเร็จ: {e}", ERROR)
            return False

        path = self._cookies_path(pkey)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(clean, f, ensure_ascii=False, indent=2)

        self._set_conn(pkey, *self._cookie_status(path))
        self._textbox_reset(textbox)
        self.update_status(f"เชื่อมต่อ {name} แล้ว ✓  ({len(clean)} cookies)", SUCCESS)
        return True

    def _paste_clipboard_and_import(self, pkey):
        try:
            content = self.clipboard_get().strip()
        except Exception:
            content = ""
        if not content:
            self.update_status("คลิปบอร์ดว่าง — copy cookies จาก Cookie-Editor ก่อน", ERROR)
            return
        textbox = getattr(self, f"txt_{pkey}_cookies")
        textbox._ph_hide()
        textbox.delete("1.0", tk.END)
        textbox.insert("end", content)
        self._import_cookies(pkey)

    def _clear_cookies(self, pkey):
        name = PLATFORMS[pkey][0]
        path = self._cookies_path(pkey)
        if not os.path.exists(path):
            self.update_status(f"{name} ยังไม่ได้เชื่อมต่อ", MUTED)
            return
        if not messagebox.askyesno(f"ยกเลิกการเชื่อมต่อ {name}",
                                   f"ลบ cookies ของ {name} ที่บันทึกไว้?\n\n"
                                   "ต้องนำเข้าใหม่ก่อนโพสต์ครั้งถัดไป",
                                   icon="warning"):
            return
        os.remove(path)
        if pkey == "tt":
            legacy = os.path.join(APP_DIR, "tiktok_session.json")
            if os.path.exists(legacy):
                os.remove(legacy)
        self._set_conn(pkey, *self._cookie_status(path))
        self._log(f"{name} cookies cleared")

    # ======================================================================
    #  YOUTUBE UPLOAD
    # ======================================================================
    def upload_to_youtube(self, job):
        with self._yt_lock:
            try:
                creds = self._load_yt_creds()
            except Exception as e:
                self._log(f"YouTube token refresh failed ({e}) — signing in again", WARNING)
                creds = None
            if not creds or not creds.valid:
                creds = self._yt_sign_in()
                self._ui(self._refresh_yt_account_ui)
                threading.Thread(target=self._fetch_yt_channel_name, daemon=True).start()

        youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)

        # YouTube rejects '<' and '>' and titles over 100 chars / descriptions over 5000 bytes
        title = job["title"].replace("<", "").replace(">", "").strip()
        if "#shorts" not in title.lower():
            title = f"{title[:YT_TITLE_MAX - len(SHORTS_SUFFIX)].rstrip()}{SHORTS_SUFFIX}"
        title = title[:YT_TITLE_MAX]
        desc = "\n\n".join(p for p in (job["caption"], job["hashtags"]) if p)
        desc = desc.replace("<", "").replace(">", "")
        desc = desc.encode("utf-8")[:5000].decode("utf-8", "ignore")
        privacy = job["yt_privacy"]

        body = {
            "snippet": {
                "title":       title,
                "description": desc,
                "tags":        job["yt_tags"],
                "categoryId":  "22",
            },
            "status": {"privacyStatus": privacy},
        }

        self._log(f"YouTube: \"{title}\"  [{privacy}]  tags: {', '.join(job['yt_tags'])}")
        media   = MediaFileUpload(
            job["video_path"], chunksize=8 * 1024 * 1024, resumable=True, mimetype="video/*")
        request = youtube.videos().insert(
            part=",".join(body.keys()), body=body, media_body=media)

        response = None
        retries  = 0
        while response is None:
            try:
                status, response = request.next_chunk()
                retries = 0
            except HttpError as e:
                if e.resp.status not in (500, 502, 503, 504) or retries >= 5:
                    raise
                retries += 1
                self._log(f"YouTube server error {e.resp.status} — retry {retries}/5", WARNING)
                time.sleep(2 ** retries)
                continue
            except (OSError, TimeoutError) as e:
                if retries >= 5:
                    raise
                retries += 1
                self._log(f"Network error ({e}) — retry {retries}/5", WARNING)
                time.sleep(2 ** retries)
                continue
            if status:
                pct = status.progress()
                self._set_progress(pct * 0.95, f"YouTube  {int(pct * 100)}%", YT)

        video_id = response.get("id", "?")
        self._log(f"YouTube ✓  https://youtu.be/{video_id}", SUCCESS)
        return True

    # ======================================================================
    #  TIKTOK UPLOAD
    # ======================================================================
    def upload_to_tiktok(self, job):
        video_path   = job["video_path"]
        cookies_path = self._tt_cookies_path()
        if not os.path.exists(cookies_path):
            raise Exception(
                "ยังไม่ได้เชื่อมต่อ TikTok — นำเข้า cookies ที่หน้าแพลตฟอร์ม")

        privacy_map = {
            "Everyone": ["\u0e17\u0e38\u0e01\u0e04\u0e19", "Everyone", "Public"],
            "Friends":  ["\u0e40\u0e1e\u0e37\u0e48\u0e2d\u0e19",  "Friends"],
            "Only me":  ["\u0e40\u0e09\u0e1e\u0e32\u0e30\u0e09\u0e31\u0e19", "Only me", "Private"],
        }
        chosen        = job["tt_privacy"]
        privacy_texts = privacy_map.get(chosen, ["Everyone"])
        caption       = self._social_caption(job, limit=4000)

        with sync_playwright() as p:
            browser = self._launch_browser(p)
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
                    "เซสชัน TikTok หมดอายุ — นำเข้า cookies ใหม่ที่หน้าแพลตฟอร์ม")
            self._log("Session OK")

            # -- Navigate to upload ------------------------------------
            self._log("Opening TikTok Studio...")
            page.goto("https://www.tiktok.com/tiktokstudio/upload?from=upload")
            page.wait_for_load_state("domcontentloaded")
            if "login" in page.url:
                raise Exception(
                    "เซสชัน TikTok หมดอายุ — นำเข้า cookies ใหม่ที่หน้าแพลตฟอร์ม")

            # input[type="file"] is hidden -- use 'attached' not 'visible'
            page.locator('input[type="file"]').wait_for(state="attached", timeout=30000)
            page.locator('input[type="file"]').set_input_files(video_path)
            self._log("File sent -- waiting for video to process...")
            self._set_progress(0.2, "TikTok — กำลังประมวลผลวิดีโอ…", TT)

            # -- Wait for Post button to be truly ready ---------------
            # Playwright wait_for only accepts attached/detached/visible/hidden
            # Use JS to check CSS opacity + pointer-events (TikTok greys out btn)
            self._log("Waiting for TikTok video processing...")
            self._set_progress(0.25, "TikTok — กำลังประมวลผลวิดีโอ…", TT)

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

            # Wait up to 5 minutes for large 4K files to encode
            post_ready = False
            for attempt in range(6):  # 6 × 50s = 5 minutes
                try:
                    page.wait_for_function(JS_BTN_READY, timeout=50000)
                    self._log("Post button ready -- video processed OK")
                    post_ready = True
                    break
                except Exception:
                    elapsed = (attempt + 1) * 50
                    self._log(f"Still processing... ({elapsed}s elapsed, max 300s)")
                    self._set_progress(0.25 + attempt * 0.04,
                                       f"TikTok — กำลังประมวลผล ({elapsed} วิ)…", TT)

            if not post_ready:
                self._log("Timeout waiting for Post button -- proceeding anyway")
            self._set_progress(0.5, "TikTok — กำลังกรอกข้อมูล…", TT)

            # -- Dismiss tutorial / feature overlay (any modal with 'Got it' or close button)
            try:
                page.wait_for_timeout(600)
                # Try clicking "Got it" / "ตกลง" button in any overlay/modal
                for got_it_text in ["Got it", "ตกลง", "OK", "Close", "ปิด"]:
                    try:
                        btn = page.get_by_role("button", name=got_it_text, exact=True).first
                        if btn.is_visible(timeout=1500):
                            btn.click()
                            self._log(f"Dismissed overlay: '{got_it_text}'")
                            page.wait_for_timeout(400)
                            break
                    except Exception:
                        pass
                # Fallback: press Escape + remove known overlay DOM elements
                page.keyboard.press("Escape")
                page.wait_for_timeout(300)
                page.evaluate(
                    "document.querySelectorAll("
                    "'[data-test-id=\"overlay\"],"
                    ".react-joyride__overlay,"
                    "#react-joyride-portal'"
                    ").forEach(el=>el.remove())"
                )
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
            self._set_progress(0.7, "TikTok — กำลังกดโพสต์…", TT)
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
            self._set_progress(0.85, "TikTok — กำลังยืนยัน…", TT)

            # -- Handle "Continue to post?" copyright check dialog -----------
            # TikTok shows this when Content check lite is still running.
            # Must click "Post now" to confirm and proceed.
            try:
                page.wait_for_timeout(1500)
                for post_now_text in ["Post now", "โพสต์เลย", "Post Now"]:
                    try:
                        btn_postnow = page.get_by_role("button", name=post_now_text, exact=True).first
                        if btn_postnow.is_visible(timeout=3000):
                            btn_postnow.click()
                            self._log(f"Confirmed 'Continue to post?' dialog → clicked '{post_now_text}'")
                            page.wait_for_timeout(500)
                            break
                    except Exception:
                        pass
            except Exception:
                pass

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
                            "อาจโพสต์ไม่สำเร็จ — ยังค้างอยู่ที่หน้าอัปโหลด "
                            "ลองใหม่หรือตรวจสอบใน TikTok Studio")
                    self._log(f"Post sent (URL: {final_url})")

            self._log("TikTok ✓  post complete", SUCCESS)
            browser.close()
            return True

    # ======================================================================
    #  FACEBOOK UPLOAD
    # ======================================================================
    def upload_to_facebook(self, job):
        video_path   = job["video_path"]
        cookies_path = self._fb_cookies_path()
        if not os.path.exists(cookies_path):
            raise Exception(
                "ยังไม่ได้เชื่อมต่อ Facebook — นำเข้า cookies ที่หน้าแพลตฟอร์ม")

        caption = self._social_caption(job)

        with sync_playwright() as p:
            browser = self._launch_browser(p)
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
                    "เซสชัน Facebook หมดอายุ — นำเข้า cookies ใหม่ที่หน้าแพลตฟอร์ม")
            self._log("Session OK")

            # Navigate to Reels creator
            self._log("Opening Facebook Reels creator...")
            page.goto("https://www.facebook.com/reels/create")
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(3000)
            self._set_progress(0.1, "Facebook — กำลังเปิดหน้าสร้าง Reels…", FB)

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
            self._set_progress(0.2, "Facebook — กำลังประมวลผลวิดีโอ…", FB)

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
            self._set_progress(0.5, "Facebook — กำลังกรอกข้อมูล…", FB)

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
            privacy = job["fb_privacy"]
            try:
                # Only target real audience controls — a generic div:has-text("Public")
                # matches huge page containers and force-clicks random spots.
                aud = page.locator(
                    '[aria-label*="audience" i], [aria-label*="Who can" i]').first
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
            self._set_progress(0.7, "Facebook — กำลังโพสต์…", FB)
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
            self._set_progress(0.85, "Facebook — กำลังยืนยัน…", FB)

            confirmed = True
            try:
                page.wait_for_url(
                    lambda url: "reels/create" not in url, timeout=60000)
                self._log(f"Facebook \u2713  post confirmed  URL: {page.url}", SUCCESS)
            except Exception:
                page.wait_for_timeout(8000)
                confirmed = "reels/create" not in page.url
                self._log(f"Facebook post sent  (URL: {page.url})",
                          SUCCESS if confirmed else WARNING)

            browser.close()
            return confirmed

    # ======================================================================
    #  INSTAGRAM UPLOAD
    # ======================================================================
    def upload_to_instagram(self, job):
        video_path   = job["video_path"]
        cookies_path = self._ig_cookies_path()
        if not os.path.exists(cookies_path):
            raise Exception(
                "ยังไม่ได้เชื่อมต่อ Instagram — นำเข้า cookies ที่หน้าแพลตฟอร์ม")

        caption = self._social_caption(job, limit=2200)

        with sync_playwright() as p:
            browser = self._launch_browser(p, maximized=False)
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
                    "เซสชัน Instagram หมดอายุ — นำเข้า cookies ใหม่ที่หน้าแพลตฟอร์ม")
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
            self._set_progress(0.15, "Instagram — กำลังส่งไฟล์…", IG)
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
            self._set_progress(0.25, "Instagram — กำลังประมวลผล…", IG)
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
            self._set_progress(0.55, "Instagram — กำลังกรอกแคปชัน…", IG)
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
            self._set_progress(0.75, "Instagram — กำลังโพสต์…", IG)
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

            # The video is uploaded *after* Share is clicked — closing the browser
            # early aborts it, so wait for Instagram's "shared" confirmation.
            self._log("Clicked Share — waiting for Instagram to finish uploading...")
            self._set_progress(0.9, "Instagram — กำลังอัปโหลด…", IG)
            confirmed = False
            try:
                page.locator(
                    ':text("has been shared"), :text("Reel shared"), '
                    ':text("Post shared"), img[alt*="checkmark" i]'
                ).first.wait_for(state="visible", timeout=300000)
                confirmed = True
                self._log("Instagram ✓  post shared", SUCCESS)
            except Exception:
                self._log("Instagram: no 'shared' confirmation within 5 min — check your profile", WARNING)
            page.wait_for_timeout(2000)
            browser.close()
            return confirmed



# ===========================================================================
if __name__ == "__main__":
    app = AutoPosterApp()
    app.mainloop()
