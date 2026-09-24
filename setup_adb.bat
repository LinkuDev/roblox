@echo off
REM ============================================================
REM Nang adb.exe cua LDPlayer (1.0.31) len ban moi cua Google (~1.0.41).
REM adb moi xu ly nhieu device dong thoi tot hon -> bot "device offline".
REM Chay MOT LAN tren may co LDPlayer. Chay lai khong hai.
REM ============================================================

REM >>> Sua duong dan LDPlayer neu khac <<<
set "LDDIR=C:\LDPlayer\LDPlayer9"

if not exist "%LDDIR%\adb.exe" (
    echo [!] Khong thay "%LDDIR%\adb.exe" -- sua bien LDDIR trong file nay.
    pause & exit /b 1
)

echo === adb hien tai ===
"%LDDIR%\adb.exe" version
echo.

echo Dong LDPlayer + tat adb dang chay...
taskkill /F /IM dnplayer.exe  >nul 2>&1
taskkill /F /IM dnconsole.exe >nul 2>&1
"%LDDIR%\adb.exe" kill-server  >nul 2>&1
taskkill /F /IM adb.exe       >nul 2>&1

echo Tai platform-tools moi nhat...
powershell -NoProfile -Command "try { Invoke-WebRequest 'https://dl.google.com/android/repository/platform-tools-latest-windows.zip' -OutFile \"$env:TEMP\pt.zip\" } catch { exit 1 }"
if errorlevel 1 (
    echo [!] Tai that bai -- kiem tra mang, hoac tai tay platform-tools roi chep adb.exe + 2 DLL vao "%LDDIR%".
    pause & exit /b 1
)
powershell -NoProfile -Command "Expand-Archive -Force \"$env:TEMP\pt.zip\" \"$env:TEMP\pt\""

echo Backup adb cu -^> adb.exe.bak, roi thay ban moi...
copy /Y "%LDDIR%\adb.exe" "%LDDIR%\adb.exe.bak" >nul 2>&1
copy /Y "%TEMP%\pt\platform-tools\adb.exe"          "%LDDIR%\adb.exe"
copy /Y "%TEMP%\pt\platform-tools\AdbWinApi.dll"    "%LDDIR%\" >nul 2>&1
copy /Y "%TEMP%\pt\platform-tools\AdbWinUsbApi.dll" "%LDDIR%\" >nul 2>&1

echo.
echo === adb SAU khi nang ===
"%LDDIR%\adb.exe" version
echo.
echo Xong. Mo lai LDPlayer va chay app.
echo (App se dung dung adb.exe nay neu ban bat tuy chon "dung adb cua LDPlayer".)
pause
