@echo off
REM ============================================================
REM Dong goi main.py -> RobloxFarm.exe   (chay tren Windows)
REM ============================================================

REM Tat exe cu TRUOC khi build. PyInstaller xoa dist\RobloxFarm.exe roi ghi de;
REM file dang chay thi Windows khoa lai -> PermissionError [WinError 5]. App
REM build voi --windowed nen chay an, khong co cua so console de nhin thay.
taskkill /F /IM RobloxFarm.exe >nul 2>&1
if not errorlevel 1 echo Da tat RobloxFarm.exe dang chay.

pip install -r requirements.txt
pip install pyinstaller

REM ---- Gói adb moi VAO exe -------------------------------------------------
REM May dich thuong con adb 1.0.31 cua LDPlayer. Nhet san ban moi vao exe thi
REM mang sang may nao cung chay duoc ngay, khong phai nang tay tung may.
REM Tai mot lan roi cache trong vendor\ (da bo qua trong .gitignore).
set "VENDOR=%~dp0vendor\platform-tools"
if not exist "%VENDOR%\adb.exe" (
    echo Tai platform-tools de bundle vao exe...
    powershell -NoProfile -Command "try { Invoke-WebRequest 'https://dl.google.com/android/repository/platform-tools-latest-windows.zip' -OutFile \"$env:TEMP\pt.zip\" } catch { exit 1 }"
    if errorlevel 1 (
        echo [!] Tai that bai -- van build tiep, nhung exe SE KHONG kem adb.
        echo     May dich phai tu bam nut "Nang ADB" trong app.
    ) else (
        powershell -NoProfile -Command "Expand-Archive -Force \"$env:TEMP\pt.zip\" \"%~dp0vendor\""
    )
)

set "ADBARGS="
if exist "%VENDOR%\adb.exe" (
    set "ADBARGS=--add-binary "%VENDOR%\adb.exe;adb" --add-binary "%VENDOR%\AdbWinApi.dll;adb" --add-binary "%VENDOR%\AdbWinUsbApi.dll;adb""
    echo adb se duoc bundle vao exe.
) else (
    echo [!] Khong co adb de bundle -- exe se dung adb cua LDPlayer tren may dich.
)

REM YEU CAU: Python >= 3.10.1 (ban 3.10.0 co bug 'dis' lam PyInstaller vo khi
REM quet PIL). Nang Python truoc khi build.
REM
REM Loai cv2/numpy: flow tap theo TOA DO co dinh, chua dung nhan dien anh -> exe
REM   nhe di ~80MB. (cv2/numpy da chuyen sang lazy import trong instance.py nen
REM   bo di van chay; khi nao can tap_image() thi cai lai + bo 2 dong exclude.)
REM   PIL PHAI GIU: adbutils import no o top-level, bo la exe crash luc mo.
REM Loai apkutils2: adbutils keo vao de phan tich APK, minh khong dung.
pyinstaller --onefile --windowed --name RobloxFarm --clean ^
  --paths examples ^
  --hidden-import roblox_flow ^
  --hidden-import roblox_login ^
  --hidden-import ldauto.console ^
  --hidden-import ldauto.farm ^
  --hidden-import ldauto.flow ^
  --hidden-import ldauto.instance ^
  --hidden-import ldauto.accounts ^
  --hidden-import ldauto.cookie ^
  --hidden-import ldauto.window ^
  --hidden-import ldauto.telemetry ^
  --hidden-import ldauto.license ^
  --collect-all adbutils ^
  --exclude-module cv2 ^
  --exclude-module numpy ^
  --exclude-module apkutils2 ^
  --exclude-module apkutils ^
  %ADBARGS% ^
  main.py

REM Phai kiem tra: khong co doan nay thi build hong van in "Xong", va lan sau
REM chay nham exe cu ma khong biet.
if errorlevel 1 goto :hong
if not exist "dist\RobloxFarm.exe" goto :hong

echo.
echo === Xong. File o: dist\RobloxFarm.exe ===
echo Chep RobloxFarm.exe ra thu muc lam viec; accounts.db se nam canh no.
pause
exit /b 0

:hong
echo.
echo === BUILD HONG -- dist\RobloxFarm.exe KHONG duoc tao ra ===
echo.
echo Neu loi la "PermissionError: [WinError 5] Access is denied":
echo   file dang bi khoa. Thu lan luot:
echo     1. taskkill /F /IM RobloxFarm.exe
echo     2. dong cua so Explorer dang mo thu muc dist
echo     3. tam tat Windows Defender realtime scan
echo.
pause
exit /b 1
