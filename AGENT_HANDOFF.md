# AutoPoster v2 — Agent Handoff Log

> **วัตถุประสงค์**: เอกสารนี้เขียนขึ้นเพื่อให้ AI Agent ตัวถัดไปสามารถ pickup งานต่อได้ทันที โดยไม่ต้องอ่านโค้ดใหม่ทั้งหมด

---

## 1. ภาพรวมโปรเจกต์ (Project Overview)

| หัวข้อ | รายละเอียด |
|---|---|
| **ชื่อ** | AutoPoster v2 |
| **วัตถุประสงค์** | GUI Desktop App (Windows) สำหรับ Auto-upload วิดีโอขึ้น YouTube Shorts, TikTok, Facebook Reels, Instagram Reels ในคลิกเดียว |
| **Language** | Python 3.10+ |
| **UI Framework** | CustomTkinter (CTk) — Liquid Glass Dark Theme |
| **Font** | Anuphan (Google Fonts) — โหลด dynamic ผ่าน Windows GDI `AddFontResourceExW` |
| **Icons** | Flaticon PNG (yt.png, tt.png, fb.png, ig.png, upload.png, paste.png) |
| **Platform** | Windows 10/11 only |
| **Entry Point** | `main.py` (~2,000 บรรทัด) |
| **Repository** | `C:\Users\usEr\Documents\Project\Autoposter` / GitHub: Pillows9/AutoPoster |

---

## 2. โครงสร้างโค้ด (Code Architecture)

```
main.py
├── MODULE LEVEL
│   ├── APP_DIR             ← Base path สำหรับทุกไฟล์ (token, cookie, assets)
│   │                          ทำงานถูกต้องทั้ง dev (.py) และ PyInstaller (.exe)
│   │                          if sys.frozen → sys.executable dir
│   │                          else → __file__ dir
│   ├── Design Tokens       ← สีทั้งหมด (BG, GLASS0-3, BORDER0-2, YT/TT/FB/IG colors)
│   ├── _init_anuphan_font()← โหลด Anuphan.ttf จาก APP_DIR ผ่าน Windows GDI
│   ├── get_icon(name)      ← @lru_cache โหลด PNG icons จาก APP_DIR
│   ├── F(size, weight)     ← @lru_cache สร้าง CTkFont Anuphan
│   ├── Mono(size)          ← @lru_cache สร้าง CTkFont Consolas (log terminal)
│   └── GlassCard(parent)   ← Helper สร้าง glass card widget
│
└── class AutoPosterApp(ctk.CTk)
    ├── __init__            ← init ตัวแปร state + build UI + daemon threads
    ├── UI BUILD
    │   ├── _build_header()     ← Logo + Platform pills + Connection dots
    │   ├── _build_tabs()       ← CTkTabview ("  Post  " / "  Accounts  ")
    │   ├── _build_post_tab()   ← Video file, Title, Caption, Hashtags, Settings, Log
    │   ├── _build_accounts_tab() ← YouTube, TikTok, FB, IG cards
    │   ├── _build_action_bar() ← Progress bar + Post Now button
    │   └── _build_statusbar()  ← Status label ด้านล่างสุด
    │
    ├── POSTING LOGIC
    │   ├── _post_now()         ← Validate input + กำหนด posting item + start thread
    │   ├── _run_posting(items) ← Thread: วน upload แต่ละ platform ที่ tick ไว้
    │   ├── _build_hashtags()   ← แปลง textbox → "#tag1 #tag2" string (TikTok/FB/IG)
    │   └── _get_tag_list()     ← แปลง textbox → ["tag1","tag2","Shorts","YouTubeShorts"] list (YouTube API)
    │
    ├── SCHEDULE
    │   ├── _toggle_schedule()
    │   ├── _parse_schedule_datetime()
    │   ├── _get_schedule_datetime()
    │   └── _start_countdown()
    │
    ├── UPLOAD BACKENDS
    │   ├── upload_to_youtube(video_path, title, desc)
    │   │   └── OAuth2 flow → YouTube Data API v3 → resumable upload (chunked 1MB)
    │   ├── upload_to_tiktok(video_path, title)
    │   │   └── Playwright Chromium → Cookie inject → TikTok Studio → file upload
    │   ├── upload_to_facebook(video_path, title, desc)
    │   │   └── Playwright Chromium → Cookie inject → Facebook Reels upload
    │   └── upload_to_instagram(video_path, title)
    │       └── Playwright Chromium → Cookie inject → Instagram Reels upload
    │
    ├── ACCOUNT MANAGEMENT
    │   ├── _fetch_yt_channel_name()   ← Daemon thread: ดึงชื่อ channel YouTube
    │   ├── yt_logout()                ← ลบ token + Confirmation dialog ก่อนลบ
    │   ├── _tt_cookies_path()         ← APP_DIR/tiktok_cookies.json
    │   ├── _fb_cookies_path()         ← APP_DIR/facebook_cookies.json
    │   ├── _ig_cookies_path()         ← APP_DIR/instagram_cookies.json
    │   ├── tt_import_cookies()        ← Parse JSON → clean → save
    │   ├── fb_import_cookies()        ← เรียก _import_cookies_generic()
    │   ├── ig_import_cookies()        ← เรียก _import_cookies_generic()
    │   ├── _import_cookies_generic()  ← Shared helper สำหรับ FB/IG
    │   ├── _paste_clipboard_and_import() ← 1-click: clipboard_get → textbox → import
    │   └── _build_cookie_status()     ← อ่านไฟล์ cookie แสดงวันที่บันทึก + จำนวน
    │
    ├── SYSTEM
    │   ├── update_status(msg, color)  ← Thread-safe: self.after(0, _apply)
    │   ├── _log(msg)                  ← Append to log_box + trim ≤300 บรรทัด
    │   ├── _set_progress(value, label)← Update progress bar
    │   ├── clean_playwright_cache()   ← ลบ orphan %TEMP%\playwright_* dirs
    │   ├── _setup_fast_route_blocking() ← Block Analytics/Ad requests ใน Playwright
    │   └── _notify_windows(title, msg)← Windows Toast (plyer) หรือ fallback msgbox
    │
    └── UI HELPERS
        ├── _section(parent, text, color) ← Section header พร้อม colored dot
        ├── _platform_pill()              ← Platform checkbox pill ใน header
        ├── _update_settings_visibility_rows() ← Show/hide visibility per platform
        ├── _update_post_button_text()    ← Dynamic "Post to YouTube + TikTok" text
        └── browse_file()                 ← filedialog → set video_path
```

---

## 3. ไฟล์สำคัญทั้งหมด (Key Files)

### Source Code
| ไฟล์ | หน้าที่ |
|---|---|
| `main.py` | แอพทั้งหมด (UI + Backend รวมไฟล์เดียว) |
| `requirements.txt` | Python dependencies |
| `build.bat` | Build script → `dist\AutoPoster\AutoPoster.exe` |
| `AutoPoster.spec` | PyInstaller spec (auto-generated) |

### Assets (ต้องอยู่ในโฟลเดอร์เดียวกับ .py หรือ .exe)
| ไฟล์ | หน้าที่ |
|---|---|
| `Anuphan.ttf` | Google Font (โหลด dynamic ผ่าน GDI) |
| `yt.png` | YouTube icon (Flaticon) |
| `tt.png` | TikTok icon (Flaticon) |
| `fb.png` | Facebook icon (Flaticon) |
| `ig.png` | Instagram icon (Flaticon) |
| `upload.png` | Upload cloud icon (Flaticon) |
| `paste.png` | Clipboard paste icon (Flaticon) |

### Runtime Files (สร้างขณะรัน — **ห้ามขึ้น Git**)
| ไฟล์ | หน้าที่ | อายุ |
|---|---|---|
| `credentials.json` | YouTube OAuth2 Client credentials (จาก Google Cloud Console) | ถาวร |
| `youtube_token.json` | YouTube OAuth2 access/refresh token | ~7 วัน (auto-refresh) |
| `tiktok_cookies.json` | TikTok session cookies | ~30-60 วัน |
| `facebook_cookies.json` | Facebook session cookies | ~30-90 วัน |
| `instagram_cookies.json` | Instagram session cookies | ~30-90 วัน |

---

## 4. Design System (Liquid Glass Theme)

```python
BG      = "#07070d"   # Void black background
GLASS0  = "#0a0a14"   # Base surface
GLASS1  = "#0e0e1c"   # Card surface (primary cards)
GLASS2  = "#121226"   # Elevated / inner panels
GLASS3  = "#18182e"   # Hover state
SHIMMER = "#252548"   # Glass edge shimmer
BORDER0 = "#181832"   # Subtle border
BORDER1 = "#22224a"   # Normal border
BORDER2 = "#2e2e6e"   # Active border
ACCENT  = "#7c3aed"   # Purple accent
TEXT    = "#eceeff"   # Cool white text
SUCCESS = "#00e875"   # Neon green
WARNING = "#ffaa00"   # Amber
ERROR   = "#ff2a50"   # Hot red
YT      = "#ff3838"   # YouTube red
TT      = "#ff2d55"   # TikTok pink
FB      = "#3a8af7"   # Facebook blue
IG      = "#f02875"   # Instagram pink
```

---

## 5. Platform Integration รายละเอียด

### YouTube
- **Method**: YouTube Data API v3 (`videos.insert`) + OAuth2
- **Auth**: `credentials.json` → `youtube_token.json` (auto-refresh)
- **Tags**: ดึงจาก `txt_hashtags` textbox + append `["Shorts","YouTubeShorts"]`
- **Title**: auto-append `#Shorts` ถ้าไม่มี
- **Upload**: Resumable chunked upload (1MB chunks), แสดง % progress

### TikTok
- **Method**: Playwright Chromium (channel="chrome", headless=False)
- **Auth**: Cookie injection จาก `tiktok_cookies.json`
- **Flow**: tiktok.com (verify) → TikTok Studio upload page → set_input_files → wait encode → dismiss overlay → fill caption → set privacy → click Post
- **Overlay**: ตรวจ `got_it_text in ["Got it","ตกลง","OK","Close","ปิด"]` ก่อน → Fallback Escape + DOM removal
- **Timeout**: รอ Post button สูงสุด **5 นาที** (6 × 50s loop พร้อม log progress)
- **Post Confirm**: wait_for_url ออกจาก /upload → fallback ตรวจ success toast

### Facebook
- **Method**: Playwright Chromium + Cookie injection
- **Auth**: `facebook_cookies.json`
- **Flow**: facebook.com/reels/create → upload → fill caption + hashtags → post

### Instagram
- **Method**: Playwright Chromium + Cookie injection
- **Auth**: `instagram_cookies.json`
- **Flow**: instagram.com → new post → Reels → upload → caption → share

### Speed Optimization (ใช้ทุก platform)
```python
def _setup_fast_route_blocking(page):
    # Block analytics, ads, tracking scripts
    # ลดเวลาโหลดหน้า 30-50%
```

---

## 6. Bug Fixes ที่ทำไปแล้ว (ประวัติสำคัญ)

| Bug | สาเหตุ | Fix |
|---|---|---|
| Cookie หายทุกครั้งที่เปิดโปรแกรม | `sys.argv[0]` ชี้คนละ dir | ใช้ `APP_DIR` จาก `__file__` / `sys.executable` |
| YouTube ต้อง Login ใหม่ทุกครั้ง | กด Disconnect พลาด (ไม่มี confirm) | เพิ่ม `messagebox.askyesno()` ก่อนลบ token |
| TikTok Tutorial "Got it" ไม่ถูกปิด | TikTok เพิ่ม Feature Popup ใหม่ | วนลอง click ปุ่ม "Got it"/"ตกลง" + Fallback DOM remove |
| ไฟล์ 4K Timeout แล้ว upload ไม่ผ่าน | รอแค่ 2 นาที (120s) | เพิ่มเป็น **5 นาที** (6×50s) พร้อม log ทุก 50s |
| YouTube Tags ไม่ติด | Hardcode `["Shorts","viral"]` แทน user tags | เพิ่ม `_get_tag_list()` ดึงจาก textbox จริง |
| `__file__` ใช้ไม่ได้ใน .exe | PyInstaller frozen mode | `if sys.frozen: APP_DIR = sys.executable dir` |
| build.bat copy assets ไม่ได้ | `copy >nul` syntax ผิดใน PowerShell | เปลี่ยนเป็น `xcopy /y /q` |

---

## 7. Widget Reference (Backend ใช้ Widget เหล่านี้)

```python
self.entry_title        # CTkEntry — ชื่อวิดีโอ
self.txt_desc           # CTkTextbox — คำอธิบาย
self.txt_hashtags       # CTkTextbox — แฮชแท็ก (default: "shorts  viral  fyp")
self.yt_privacy         # StringVar — "public"/"unlisted"/"private"
self.tt_privacy         # StringVar — "Everyone"/"Friends"/"Only me"
self.fb_privacy         # StringVar — "Public"/"Friends"/"Only me"
self.lbl_file           # Label แสดงชื่อไฟล์
self.btn_browse         # ปุ่มเลือกไฟล์
self.btn_post           # ปุ่มโพสต์
self.progress_bar       # CTkProgressBar
self.lbl_progress       # Label แสดง % progress
self.lbl_status         # Status bar ด้านล่าง
self.lbl_countdown      # แสดง countdown ถ้าตั้ง schedule
self.lbl_yt_account     # แสดงชื่อ YouTube channel
self.lbl_tt_status      # แสดงสถานะ TikTok cookie
self.lbl_fb_status      # แสดงสถานะ Facebook cookie
self.lbl_ig_status      # แสดงสถานะ Instagram cookie
self.dot_yt/tt/fb/ig    # Header connection dots (สีแดง/เทา)
self.txt_tt_cookies     # CTkTextbox สำหรับ paste JSON cookie TikTok
self.txt_fb_cookies     # CTkTextbox สำหรับ paste JSON cookie Facebook
self.txt_ig_cookies     # CTkTextbox สำหรับ paste JSON cookie Instagram
self.var_yt/tt/fb/ig    # BooleanVar — เลือกโพสต์ platform ไหน
self.var_schedule       # BooleanVar — เปิด/ปิด schedule
self.entry_time         # CTkEntry — เวลาโพสต์ "HH:MM"
self.log_box            # CTkTextbox — Activity Log (max 300 บรรทัด)
self.video_path         # str — path ไฟล์วิดีโอที่เลือก
self.is_posting         # bool — กำลัง posting อยู่หรือไม่
self.schedule_timer     # threading.Timer หรือ None
```

---

## 8. Build & Deploy

### Run จาก Source
```bash
cd C:\Users\usEr\Documents\Autoposter
pip install -r requirements.txt
playwright install chromium
python main.py
```

### Build เป็น .exe
```bat
build.bat
```
ขั้นตอน: install deps → install chromium → PyInstaller --onedir --windowed → xcopy assets → verify

### โครงสร้าง dist หลัง Build
```
dist\AutoPoster\
├── AutoPoster.exe       ← เปิดใช้งาน
├── _internal\           ← Python runtime (อย่าลบ)
├── credentials.json     ← YouTube OAuth credentials
├── Anuphan.ttf
├── yt.png / tt.png / fb.png / ig.png
├── upload.png / paste.png
└── [runtime] youtube_token.json / tiktok_cookies.json / ...
```

> **หมายเหตุ**: `credentials.json` ต้องวางด้วยตนเอง ไม่ได้ขึ้น Git

---

## 8.5 Finalize Pass (2026-10-05)

**ระบบ (Threading / ความถูกต้อง)**
- Worker thread ไม่แตะ Tk widget ตรงๆ แล้ว — ทุก UI update ผ่าน `self._ui(fn)` → queue → main thread (`_drain_ui_queue`)
- `_post_now()` snapshot ค่าทุกฟิลด์ลง `job` dict ก่อนเริ่ม → upload functions รับ `job` (ไม่เรียก `.get()` จาก thread)
- Schedule ใช้ `self.after()` แทน `threading.Timer` + ปุ่ม Post กลายเป็น **Cancel Schedule** (เดิมปิด schedule แล้วปุ่มค้าง disabled ถาวร)
- path `youtube_token.json` ใช้ `APP_DIR` ทุกจุด (เดิมบางจุดอิง cwd)
- YouTube: ขอ scope `youtube.readonly` เพิ่ม (เดิม `channels.list` โดน 403 → ชื่อช่องไม่เคยขึ้น), refresh token ตอนเปิดแอพ, OAuth timeout 5 นาที, ตัด title ≤100 ตัว / ลบ `< >`, retry chunk เมื่อ 5xx/เน็ตหลุด
- Cookie import เก็บ `secure/httpOnly/sameSite/expires` (เดิมทิ้ง → เตือนหมดอายุไม่เคยทำงาน) + เช็คว่า cookies ตรงโดเมน
- Caption ในช่อง "Caption" ถูกส่งไป TikTok/FB/IG แล้ว (เดิมไปแค่ YouTube)
- Instagram รอข้อความ "shared" สูงสุด 5 นาที (เดิมปิด browser หลัง 10 วิ → upload ใหญ่โดนตัด)
- Facebook ลบ selector `div:has-text("Public")` ที่ force-click กลางหน้าจอแบบสุ่ม
- FB/IG ที่ยืนยันไม่ได้ → สถานะ "?" (unconfirmed) แทนที่จะรายงานว่าสำเร็จ
- ไม่มี Google Chrome → fallback เป็น Playwright Chromium

**UX/UI**
- Header ไม่ล้นแล้ว (รวม connection dot เข้าไปใน pill, คลิก dot → ไป Accounts)
- หน้าต่างปรับขนาดตามจอ (รองรับ 125–150% scaling), ปิดแอพระหว่างโพสต์มี confirm
- Drag & Drop จริง (`tkinterdnd2`, mixin `DnDWrapper` บน root) + คลิก dropzone เพื่อ browse
- Placeholder จริงใน textbox (เดิม paste ต่อท้าย placeholder → JSON error)
- Pre-flight: เช็ค account ที่ยังไม่ connect ก่อนเริ่มโพสต์
- จำค่า platforms / hashtags / privacy / โฟลเดอร์ล่าสุด ใน `settings.json`
- Log มีสี + เขียนลง `autoposter.log` (ปุ่ม Open log file), ตัวนับความยาว title
- Accounts: การ์ด cookie 3 อันรวมเป็น `_build_cookie_card()`, ปุ่ม Sign in YouTube, confirm ก่อน Disconnect

## 8.6 Redesign → AutopostVideo (2026-10-06)

> **กฎ: ทุกการแก้ UI ต้องทำตาม [`DESIGN.md`](DESIGN.md)** (สรุปจาก Brand Board `docs/brand-board.webp`)

- แบรนด์ใหม่ **AutopostVideo** — โลโก้/ไอคอนสร้างจาก `tools/make_brand_assets.py` → `assets/brand/` (ห้ามแก้ภาพมือ)
- Light theme: sidebar ขาว (โลโก้, เมนู 4 หน้า, กล่อง "การเชื่อมต่อ") + พื้นที่หลัก `#F1F5F9` + การ์ดขาว + action bar ล่าง
- หน้า: **สร้างโพสต์** / **แพลตฟอร์ม** / **กิจกรรม** (log) / **ตั้งค่า** — `self._show_page(key)`
- ฟอนต์ Prompt (`assets/fonts`) ผ่าน `F(size, weight)` weight = regular|medium|semibold|bold
- ไอคอน UI = glyph จาก Segoe Fluent Icons / MDL2 ผ่าน `glyph(code, color, size)`
- Components: `Card`, `PrimaryButton`, `SecondaryButton`, `DangerButton`, `Switch`, `Entry`, `Textbox`, `ChipGroup`, `StatusBadge`
- สถานะการเชื่อมต่อรวมศูนย์ที่ `_set_conn(pkey, kind, short, detail)` → แจ้งทุก widget ที่ลงทะเบียนใน `_conn_listeners`
- ข้อความแจ้งเตือนเป็น toast มุมขวาบน (`update_status` → `_toast`) — ไม่มี status bar แล้ว
- Layout responsive: `_responsive_columns()` 2 คอลัมน์ ≥ 860px ไม่งั้นเรียงแถวเดียว
- UI ภาษาไทยทั้งหมด (log เทคนิคยังเป็นอังกฤษได้)
- assets ย้ายเข้า `assets/` แล้ว; ลบ Anuphan.ttf, upload.png, paste.png; exe ชื่อ `AutopostVideo.exe`

## 9. สถานะปัจจุบัน (Last Known State — 2026-08-18)

- ✅ YouTube upload ทำงานปกติ (ทดสอบสำเร็จ — เห็น URL `youtu.be/...` ใน log)
- ✅ TikTok cookie import สำเร็จ (20 cookies)
- ⚠️ TikTok post ยังอยู่ระหว่างทดสอบหลัง fix overlay + timeout
- ✅ Facebook / Instagram — โค้ดพร้อม ยังไม่ได้ทดสอบครบ
- ✅ Build `.exe` สำเร็จ assets ครบ พร้อมใช้งาน

---

## 10. สิ่งที่ยังไม่ได้ทำ / Future Ideas

1. **Batch Upload Queue** — เลือกหลายคลิปพร้อมกัน ตั้งช่วงเวลา auto-post
2. **Hashtag Presets** — บันทึกชุดแฮชแท็กที่ใช้บ่อย
3. **Multi-Account Profiles** — สลับหลายบัญชีต่อ platform
4. **AI Caption Generator** — ใช้ AI ช่วยเจน Caption + Tags จากชื่อไฟล์

---

## 11. Credentials ที่ต้องรู้

| สิ่งที่ต้องการ | วิธีได้มา |
|---|---|
| `credentials.json` | Google Cloud Console → YouTube Data API v3 → OAuth 2.0 Client ID (Desktop App) |
| TikTok cookies | Chrome Extension "Cookie-Editor" → Export as JSON จาก tiktok.com |
| Facebook cookies | Chrome Extension "Cookie-Editor" → Export as JSON จาก facebook.com |
| Instagram cookies | Chrome Extension "Cookie-Editor" → Export as JSON จาก instagram.com |

---

*เอกสารนี้อัปเดตล่าสุด: 2026-10-06 · โดย Claude Code (Redesign — ดู §8.6 และ DESIGN.md)*
