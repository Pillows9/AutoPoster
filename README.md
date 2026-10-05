<div align="center">

<img src="assets/brand/app_icon.png" width="96" alt="AutopostVideo" />

# AutopostVideo

**สร้างคอนเทนต์ แล้วให้เราช่วยโพสต์** — ตั้งเวลา · โพสต์อัตโนมัติ · หลายแพลตฟอร์ม

**โพสต์วิดีโอขึ้น YouTube Shorts, TikTok, Facebook Reels และ Instagram Reels อัตโนมัติ**  
*Auto-post videos to YouTube Shorts, TikTok, Facebook & Instagram Reels with one click*

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square&logo=python)
![Platform](https://img.shields.io/badge/Platform-Windows-blue?style=flat-square&logo=windows)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

</div>

---

## ✨ Features

- 🎬 **อัพโหลดวิดีโอ** ขึ้น YouTube Shorts / TikTok / Facebook / Instagram พร้อมกันในคลิกเดียว
- 🖱️ **Drag & Drop** ลากไฟล์วิดีโอวางบนหน้าต่างได้เลย
- ⏰ **ตั้งเวลาโพสต์** ล่วงหน้าได้ (ยกเลิกได้ทุกเมื่อ)
- 🏷️ **Hashtag + ค่าที่ตั้งไว้ถูกจำไว้** ใช้ซ้ำได้ทุกครั้งที่เปิดแอพ (`settings.json`)
- 🔒 **ตั้ง Visibility** ได้แยกแต่ละ Platform
- 🍪 **Cookie-based auth** สำหรับ TikTok / Facebook / Instagram — พร้อมเตือนเมื่อ cookies ใกล้หมดอายุ
- 📊 **Activity log + Progress bar** ดูสถานะแบบ Real-time และบันทึกลง `autoposter.log`
- 🔔 **Windows Notification** แจ้งเตือนเมื่อโพสต์เสร็จ

---

## 📋 Requirements

| | |
|--|--|
| OS | Windows 10/11 |
| Python | 3.10 หรือสูงกว่า |
| Chrome | แนะนำให้ติดตั้ง (ถ้าไม่มีจะใช้ Chromium ของ Playwright แทน) |

---

## 🚀 Installation (Run from Source)

### 1. Clone โปรเจค
```bash
git clone https://github.com/Pillows9/AutoPoster.git
cd AutoPoster
```

### 2. ติดตั้ง Dependencies
```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. ตั้งค่า YouTube API
> ต้องทำครั้งเดียว — ใช้ได้ตลอด

1. ไปที่ [Google Cloud Console](https://console.cloud.google.com/)
2. สร้าง Project ใหม่
3. เปิดใช้ **YouTube Data API v3**
4. สร้าง **OAuth 2.0 Client ID** (Desktop App)
5. ดาวน์โหลด `credentials.json` แล้ววางไว้ในโฟลเดอร์เดียวกับ `main.py`

### 4. รันแอพ
```bash
python main.py
```

---

## 🍪 ตั้งค่า TikTok / Facebook / Instagram (Cookie Import)

ไม่ต้องใช้ API — ใช้ cookies จาก browser แทน:

1. ติดตั้ง Chrome Extension: **[Cookie-Editor](https://chrome.google.com/webstore/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm)**
2. เปิดเว็บของ Platform นั้น (เช่น [tiktok.com](https://www.tiktok.com)) และ Login
3. คลิก Cookie-Editor → **Export** → **Export as JSON** (จะ copy ลง clipboard)
4. เปิดแอพ → Tab **Accounts** → กด **Paste & Import**

> ✅ Cookies จะถูกบันทึกไว้อัตโนมัติ — ไม่ต้องกรอกซ้ำทุกครั้ง  
> ⚠️ ต้อง Import ใหม่เมื่อ Logout หรือ Cookies หมดอายุ (แอพจะเตือนล่วงหน้า 14 วัน)

## ▶️ ตั้งค่า YouTube

วาง `credentials.json` ไว้ข้างแอพ แล้วไปที่ Tab **Accounts** → **Sign in** (หรือจะ Login ตอนอัปโหลดครั้งแรกก็ได้)

---

## 🔨 Build เป็น .exe (Optional)

```bat
.\build.bat
```
ไฟล์ `.exe` จะอยู่ที่ `dist\AutopostVideo\AutopostVideo.exe` (build จะ copy โฟลเดอร์ `assets\`, `credentials.json` และไฟล์บัญชีจาก build เก่า `dist\AutoPoster\` ให้อัตโนมัติ)

---

## 📁 Project Structure

```
AutoPoster/
├── main.py                     # แอพหลัก (UI + uploaders)
├── DESIGN.md                   # หลักการออกแบบ / design tokens — อ่านก่อนแก้ UI
├── assets/
│   ├── brand/                  # โลโก้ + ไอคอนแอป (สร้างด้วย tools/make_brand_assets.py)
│   ├── fonts/                  # ฟอนต์ Prompt (OFL)
│   └── icons/                  # โลโก้แพลตฟอร์ม
├── docs/brand-board.webp       # Brand Board ต้นฉบับ
├── tools/make_brand_assets.py  # สร้างโลโก้/ไอคอนใหม่
├── requirements.txt
├── build.bat                   # Build .exe (Windows)
└── credentials.json            # ← วางเองหลัง clone (ไม่ push ขึ้น git)
```

---

## ⚠️ Important Notes

- `credentials.json` **ห้าม** push ขึ้น GitHub เด็ดขาด (มี `.gitignore` กัน)
- `*_cookies.json` / `youtube_token.json` เก็บ session ส่วนตัว — ไม่ควรแชร์
- แอพนี้ใช้ Playwright เปิด Chrome จริง (ไม่ใช่ headless) สำหรับ TikTok / Facebook / Instagram
- ถ้าโพสต์ไม่สำเร็จ กด **Open log file** ในหน้า Post เพื่อดูรายละเอียด error

---

## 📄 License

© 2026 [Pillows9](https://github.com/Pillows9) — All Rights Reserved

โค้ดนี้เผยแพร่เพื่อแสดงผลงาน (Portfolio) เท่านั้น  
**ไม่อนุญาต**ให้ copy / ดัดแปลง / แจกจ่าย / ใช้งานเชิงพาณิชย์ โดยไม่ได้รับอนุญาตเป็นลายลักษณ์อักษร

---

<div align="center">
Made with ❤️ — <a href="https://github.com/Pillows9">Pillows9</a>
</div>
