@echo off
REM ============================================================
REM Dong goi main.py -> RobloxFarm.exe
REM Chay tren Windows, sau khi: pip install -r requirements.txt
REM ============================================================

REM B1: CAP NHAT PyInstaller. Ban cu bi loi "tuple index out of range"
REM     khi quet bytecode -- day la bug cua PyInstaller, khong phai code.
pip install -U pyinstaller pyinstaller-hooks-contrib

REM B2: Dong goi.
REM   - Khong dung --collect-submodules ldauto (chinh no kich hoat cai bug quet
REM     bytecode). Thay bang liet ke tay 7 module cua ldauto -- an toan hon.
REM   - --clean: xoa cache build cu, tranh loi vat vuong.
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
  --collect-all adbutils ^
  main.py

echo.
echo === Xong. File o: dist\RobloxFarm.exe ===
echo Chep RobloxFarm.exe ra thu muc lam viec; accounts.db se nam canh no.
pause
