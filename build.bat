@echo off
title AutoPoster Builder
color 0A
echo.
echo  =============================================
echo    AutoPoster .EXE Builder  v2
echo  =============================================
echo.

echo  [1/5] Installing dependencies...
python -m pip install pyinstaller pillow customtkinter playwright google-auth google-auth-oauthlib google-api-python-client plyer
if %errorlevel% neq 0 (
    echo  [ERROR] pip failed
    pause
    exit /b 1
)

echo.
echo  [2/5] Installing Playwright Chromium...
python -m playwright install chromium
if %errorlevel% neq 0 (
    echo  [ERROR] Playwright install failed
    pause
    exit /b 1
)

echo.
echo  [3/5] Building AutoPoster.exe...
python -m PyInstaller ^
    --noconfirm ^
    --onedir ^
    --windowed ^
    --collect-data customtkinter ^
    --collect-data PIL ^
    --name "AutoPoster" ^
    main.py

if %errorlevel% neq 0 (
    echo  [ERROR] PyInstaller build failed
    pause
    exit /b 1
)

echo.
echo  [4/5] Copying assets to dist\AutoPoster\...

if exist credentials.json (
    copy credentials.json "dist\AutoPoster\credentials.json" ^>nul
    echo  [OK] credentials.json
) else (
    echo  [WARNING] credentials.json not found - copy it manually to dist\AutoPoster\
)

for %%F in (Anuphan.ttf yt.png tt.png fb.png ig.png upload.png paste.png) do (
    if exist %%F (
        copy %%F "dist\AutoPoster\%%F" ^>nul
        echo  [OK] %%F
    ) else (
        echo  [WARNING] %%F not found
    )
)

echo.
echo  [5/5] Verifying build...
for %%F in (AutoPoster.exe Anuphan.ttf yt.png tt.png fb.png ig.png upload.png paste.png) do (
    if exist "dist\AutoPoster\%%F" (
        echo  [PASS] %%F
    ) else (
        echo  [MISSING] %%F  ^<-- copy this file manually
    )
)

echo.
echo  =============================================
echo   BUILD COMPLETE!
echo   Output: dist\AutoPoster\AutoPoster.exe
echo  =============================================
echo.
explorer dist\AutoPoster
pause
