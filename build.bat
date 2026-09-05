@echo off
REM Dong goi main.py thanh mot file RobloxFarm.exe.
REM Chay tren Windows sau khi: pip install -r requirements.txt

pip install pyinstaller

pyinstaller --onefile --windowed --name RobloxFarm ^
  --paths examples ^
  --hidden-import roblox_flow ^
  --collect-submodules ldauto ^
  --collect-all adbutils ^
  main.py

echo.
echo === Xong. File o: dist\RobloxFarm.exe ===
echo Chep RobloxFarm.exe ra thu muc lam viec; accounts.db se nam canh no.
pause
