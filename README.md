<div align="center">

# ✦ AutoPoster

**โพสต์วิดีโอขึ้น YouTube Shorts และ TikTok อัตโนมัติ**  
*Auto-post videos to YouTube Shorts & TikTok with one click*

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square&logo=python)
![Platform](https://img.shields.io/badge/Platform-Windows-blue?style=flat-square&logo=windows)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

</div>

---

## ✨ Features

- 🎬 **อัพโหลดวิดีโอ** ขึ้น YouTube Shorts และ TikTok พร้อมกันในคลิกเดียว
- ⏰ **ตั้งเวลาโพสต์** ล่วงหน้าได้
- 🏷️ **Hashtag อัตโนมัติ** ตั้งค่าครั้งเดียวใช้ได้ทุกโพสต์
- 🔒 **ตั้ง Visibility** ได้แยกแต่ละ Platform (Public / Unlisted / Private)
- 🍪 **Cookie-based TikTok auth** — ไม่ต้องใช้ API ที่ต้องรอ Approve
- 📊 **Activity log + Progress bar** ดูสถานะ Upload แบบ Real-time
- 🔔 **Windows Notification** แจ้งเตือนเมื่อโพสต์เสร็จ

---

## 📋 Requirements

| | |
|--|--|
| OS | Windows 10/11 |
| Python | 3.10 หรือสูงกว่า |
| Chrome | ติดตั้งอยู่บนเครื่อง (สำหรับ TikTok) |

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

## 🍪 ตั้งค่า TikTok (Cookie Import)

ไม่ต้องใช้ API — ใช้ cookies จาก browser แทน:

1. ติดตั้ง Chrome Extension: **[Cookie-Editor](https://chrome.google.com/webstore/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm)**
2. เปิด [tiktok.com](https://www.tiktok.com) และ Login
3. คลิก Cookie-Editor → **Export** → **Export as JSON** → Copy
4. เปิดแอพ → Tab **Accounts** → Paste ใน textbox → กด **Import**

> ✅ Cookies จะถูกบันทึกไว้อัตโนมัติ — ไม่ต้องกรอกซ้ำทุกครั้ง  
> ⚠️ ต้อง Import ใหม่เมื่อ TikTok Logout หรือ Cookies หมดอายุ (~30-60 วัน)

---

## 🔨 Build เป็น .exe (Optional)

```bat
.\build.bat
```
ไฟล์ `.exe` จะอยู่ที่ `dist\AutoPoster\AutoPoster.exe`

> **หมายเหตุ:** ต้องวาง `credentials.json` ไว้ใน `dist\AutoPoster\` ด้วย

---

## 📁 Project Structure

```
AutoPoster/
├── main.py              # แอพหลัก
├── requirements.txt     # Python dependencies
├── build.bat            # Build script (Windows)
├── AutoPoster.spec      # PyInstaller spec
└── credentials.json     # ← วางเองหลัง clone (ไม่ push ขึ้น git)
```

---

## ⚠️ Important Notes

- `credentials.json` **ห้าม** push ขึ้น GitHub เด็ดขาด (มี `.gitignore` กัน)
- `tiktok_cookies.json` เก็บ session cookie ส่วนตัว — ไม่ควรแชร์
- แอพนี้ใช้ Playwright เปิด Chrome จริง (ไม่ใช่ headless) สำหรับ TikTok

---

## 📄 License

© 2026 [Pillows9](https://github.com/Pillows9) — All Rights Reserved

โค้ดนี้เผยแพร่เพื่อแสดงผลงาน (Portfolio) เท่านั้น  
**ไม่อนุญาต**ให้ copy / ดัดแปลง / แจกจ่าย / ใช้งานเชิงพาณิชย์ โดยไม่ได้รับอนุญาตเป็นลายลักษณ์อักษร

---

<div align="center">
Made with ❤️ — <a href="https://github.com/Pillows9">Pillows9</a>
</div>
