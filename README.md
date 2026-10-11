# ldauto

Tu dong hoa emulator Android -- **LDPlayer 9** va **MEmu Play**: tao may ao theo cau hinh, dieu khien bang ADB + OpenCV.

## Yeu cau

- **Windows** (LDPlayer khong co ban Linux)
- LDPlayer 9
- Python 3.10+

```
pip install -r requirements.txt
```

## LDPlayer hay MEmu

Dua duong dan chuong trinh dong lenh nao thi dung emulator do -- khong can chon tay:

| Emulator | Duong dan thuong gap | Cong ADB |
|---|---|---|
| LDPlayer | `C:\LDPlayer\LDPlayer9\dnconsole.exe` | `5555 + 2*index` |
| MEmu | `C:\Program Files\Microvirt\MEmu\memuc.exe` | `21503 + 10*index` |

```python
from ldauto import open_emulator
emu = open_emulator(r"C:\Program Files\Microvirt\MEmu\memuc.exe")   # -> MemuConsole
```

Khac biet can biet khi dung MEmu:

- **Backend MEmu chua kiem chung tren may that luc viet.** Chay
  `python examples\memu_check.py` truoc -- no in nguyen van output cua `memuc`
  de sua parser neu lech.
- `memuc` tra ve rc=0 ke ca khi loi; backend doc chu `ERROR` trong output.
- Khong co setting "ADB debugging" (MEmu luon bat) va khong co global setting.
- Lay cookie can root: `memuc setconfigex -i <idx> enable_su 1` roi khoi dong lai.
- **Toa do bam do o 400x500 @160 DPI.** May ao MEmu phai dat dung y nhu vay,
  khong thi bam truot het -- Roblox co giao dien theo DPI.

## Cau truc

| File | Vai tro |
|---|---|
| `ldauto/emulator.py` | Mat chung cho moi emulator + `open_emulator()` chon dung backend. |
| `ldauto/console.py` | Backend LDPlayer: wrap `ldconsole.exe` -- tao/sua/bat/tat may ao. |
| `ldauto/memu.py` | Backend MEmu: wrap `memuc.exe`, cung mat voi backend LDPlayer. |
| `ldauto/instance.py` | Dieu khien trong Android -- tap, swipe, chup man hinh, tim anh. |
| `ldauto/farm.py` | Tao hang loat may ao cung cau hinh. |

## Dung nhanh

```python
from ldauto import LDConsole, Farm, Spec

console = LDConsole(r"D:\LDPlayer\LDPlayer9\ldconsole.exe")
farm = Farm(console)

inst = farm.ensure("bot0", Spec(width=540, height=960, dpi=240))
inst.start()                       # launch + doi boot that su + noi adb

inst.start_app("com.roblox.client")
inst.tap_image("images/play.png", timeout=60)
inst.swipe(270, 800, 270, 300)
```

## Vai diem de dinh bay

- **Doi resolution phai luc may ao dang tat.** `Farm.ensure()` tu tat truoc khi goi `modify`.
  Neu tu goi `console.modify()` tay thi phai tu lo phan nay.
- **`isrunning` khong co nghia la Android da san sang** -- no chi bao cua so may ao da mo.
  Dung `console.wait_boot()` (poll `sys.boot_completed`) truoc khi gui lenh adb.
- **Cong ADB** theo quy uoc `5555 + index * 2`. Neu ban doi cong trong settings thi truyen tay:
  `Instance(console, index, adb_port=5601)`.
- **Encoding**: `ldconsole` in ra theo locale Windows (thuong gbk tren may TQ), khong phai utf-8.
  `console.py` da thu lan luot utf-8 -> gbk -> cp1252 -> latin-1.
- **`copy` tra ve ma loi ke ca khi thanh cong.** Tren mot so ban LDPlayer,
  `ldconsole copy` tra ve rc khac 0 nhung VAN tao duoc may ao. Tin returncode
  o day thi thanh vong lap tao-roi-xoa vo tan. `console.copy_from()` xac nhan
  bang thu quan sat duoc: may ao co hien trong `list2` khong, va thu muc o dia
  cua no da ngung phinh chua (copy chay o tien trinh nen).

- **Nhan dien anh phu thuoc resolution.** Anh mau chup o 540x960 se khong khop o 1280x720.
  Chup lai anh mau moi khi doi `Spec`.
