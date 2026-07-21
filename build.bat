@echo off
title AutoPoster Builder
color 0A
echo.
echo  =============================================
echo    AutoPoster .EXE Builder
echo  =============================================
echo.

echo  [1/4] กำลังติดตั้ง PyInstaller...
python -m pip install pyinstaller
if %errorlevel% neq 0 (
    echo.
    echo  [ERROR] pip ล้มเหลว ตรวจสอบ Python อีกครั้ง
    pause
    exit /b 1
)

echo.
echo  [2/4] กำลังติดตั้ง Chromium สำหรับ Playwright...
python -m playwright install chromium
if %errorlevel% neq 0 (
    echo.
    echo  [ERROR] ติดตั้ง Chromium ล้มเหลว
    pause
    exit /b 1
)

echo.
echo  [3/4] กำลัง Build AutoPoster.exe ...
python -m PyInstaller ^
    --noconfirm ^
    --onedir ^
    --windowed ^
    --collect-data customtkinter ^
    --name "AutoPoster" ^
    main.py

if %errorlevel% neq 0 (
    echo.
    echo  [ERROR] Build ล้มเหลว ดูข้อความ error ด้านบน
    pause
    exit /b 1
)

echo.
echo  [4/4] คัดลอก credentials.json ไปยัง dist...
if exist credentials.json (
    copy credentials.json "dist\AutoPoster\credentials.json" >nul
    echo  คัดลอก credentials.json สำเร็จ
) else (
    echo  [WARNING] ไม่พบ credentials.json - โปรดวางไว้ใน dist\AutoPoster\ เอง
)

echo.
echo  =============================================
echo   BUILD สำเร็จ!
echo   ไฟล์อยู่ที่: dist\AutoPoster\AutoPoster.exe
echo  =============================================
echo.
explorer dist\AutoPoster
pause
