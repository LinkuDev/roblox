"""Vi du: tao 3 may ao 540x960, cai APK, mo app, lam vai thao tac."""

from pathlib import Path

from ldauto import Farm, LDConsole, Spec

LDCONSOLE = r"D:\LDPlayer\LDPlayer9\ldconsole.exe"
APK = r"D:\apk\roblox.apk"
PACKAGE = "com.roblox.client"
IMG = Path(__file__).parent / "images"


def main() -> None:
    console = LDConsole(LDCONSOLE)

    # Bot tai nguyen khi chay nhieu may ao song song.
    console.global_setting(fps=30, audio=False, fast_play=True)

    farm = Farm(console)
    spec = Spec(width=540, height=960, dpi=240, cpu=2, memory=2048)
    instances = farm.ensure_many("bot", 3, spec)

    for inst in instances:
        print(f"[{inst.index}] dang khoi dong...")
        inst.start()                      # launch + doi boot_completed + noi adb
        console.down_cpu(inst.index, 60)  # gioi han CPU 60%

        console.install_apk(inst.index, APK)
        inst.start_app(PACKAGE)

        # Cho man hinh dang nhap roi thao tac
        inst.tap_image(IMG / "login_btn.png", timeout=60)
        inst.text("username")
        inst.tap(270, 620)
        inst.swipe(270, 800, 270, 300)

        print(f"[{inst.index}] xong -> {inst.serial}")


if __name__ == "__main__":
    main()
