@echo off
REM ============================================================
REM Dong goi main.py -> RobloxFarm.exe   (chay tren Windows)
REM ============================================================

REM B1: EP nang PyInstaller len ban moi. Loi "tuple index out of range" la bug
REM     cua PyInstaller cu khi disassemble bytecode -- ban 6.x da vá.
python -m pip install --upgrade --force-reinstall pyinstaller pyinstaller-hooks-contrib
echo.
echo --- Phien ban PyInstaller (phai >= 6.0) ---
pyinstaller --version
echo.

REM B2: Dong goi.
REM   - KHONG --collect-all adbutils: no keo ca apkutils2 (phan tich APK, minh
REM     KHONG dung) -- chinh module do lam PyInstaller vo khi quet bytecode.
REM     Chi lay binary (adb.exe) + data cua adbutils la du de connect/shell/pull.
REM   - --exclude-module apkutils2/apkutils: chan han khong cho quet.
REM   - Liet ke tay 7 module ldauto vi ldauto dung lazy import.
pyinstaller --onefile --windowed --name RobloxFarm --clean ^
  --paths examples ^
  --hidden-import roblox_flow ^
  --hidden-import ldauto.console ^
  --hidden-import ldauto.farm ^
  --hidden-import ldauto.flow ^
  --hidden-import ldauto.instance ^
  --hidden-import ldauto.accounts ^
  --hidden-import ldauto.cookie ^
  --hidden-import ldauto.window ^
  --hidden-import adbutils ^
  --collect-binaries adbutils ^
  --collect-data adbutils ^
  --exclude-module apkutils2 ^
  --exclude-module apkutils ^
  main.py

echo.
echo === Xong. File o: dist\RobloxFarm.exe ===
echo Chep RobloxFarm.exe ra thu muc lam viec; accounts.db se nam canh no.
pause
