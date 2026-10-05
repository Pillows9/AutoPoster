@echo off
chcp 65001 >nul
title AutopostVideo Builder
color 0A
set APP=AutopostVideo
set OUT=dist\%APP%
echo.
echo  =============================================
echo    %APP% .EXE Builder  v2.1
echo  =============================================
echo.

echo  [1/5] Installing dependencies...
python -m pip install pyinstaller -r requirements.txt
if %errorlevel% neq 0 ( echo  [ERROR] pip failed & pause & exit /b 1 )

echo.
echo  [2/5] Installing Playwright Chromium...
python -m playwright install chromium
if %errorlevel% neq 0 ( echo  [ERROR] Playwright install failed & pause & exit /b 1 )

echo.
echo  [3/5] Building %APP%.exe...
python -m PyInstaller --noconfirm --onedir --windowed --icon "assets\brand\app_icon.ico" --collect-data customtkinter --collect-data PIL --collect-data googleapiclient --collect-all tkinterdnd2 --name "%APP%" main.py
if %errorlevel% neq 0 ( echo  [ERROR] PyInstaller build failed & pause & exit /b 1 )

echo.
echo  [4/5] Copying assets + your account files to %OUT%\...
xcopy /e /i /y /q assets "%OUT%\assets" >nul
echo  [OK] assets\
REM Account files: from the project folder, or carried over from the old dist\AutoPoster build
for %%F in (credentials.json youtube_token.json tiktok_cookies.json facebook_cookies.json instagram_cookies.json settings.json) do (
    if exist %%F (
        xcopy /y /q %%F "%OUT%\" >nul
        echo  [OK] %%F
    ) else if exist "dist\AutoPoster\%%F" (
        if not exist "%OUT%\%%F" xcopy /y /q "dist\AutoPoster\%%F" "%OUT%\" >nul
        echo  [OK] %%F  ^(from old dist\AutoPoster^)
    )
)

echo.
echo  [5/5] Verifying build...
for %%F in (%APP%.exe credentials.json assets\brand\app_icon.ico assets\fonts\Prompt-Regular.ttf assets\icons\yt.png) do (
    if exist "%OUT%\%%F" (
        echo  [PASS] %%F
    ) else (
        echo  [MISSING] %%F  ^<-- copy this file manually
    )
)

echo.
echo  =============================================
echo   BUILD COMPLETE!
echo   Output: %OUT%\%APP%.exe
echo  =============================================
echo.
explorer %OUT%
pause
