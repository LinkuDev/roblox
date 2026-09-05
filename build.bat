@echo off
REM ============================================================
REM Dong goi main.py -> RobloxFarm.exe   (chay tren Windows)
REM ============================================================

pip install pyinstaller

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
  --exclude-module cv2 ^
  --exclude-module numpy ^
  --exclude-module apkutils2 ^
  --exclude-module apkutils ^
  main.py

echo.
echo === Xong. File o: dist\RobloxFarm.exe ===
echo Chep RobloxFarm.exe ra thu muc lam viec; accounts.db se nam canh no.
pause
