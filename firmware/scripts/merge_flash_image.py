"""After an env:sim build, merge bootloader, partition table and app into one
16 MB flash image for Wokwi (wokwi.toml loads .pio/build/sim/wokwi-flash.bin).

Wokwi's own default layout only fits 4 MB, so the full image keeps the same
16 MB partition table as the real board.
"""

import os

Import("env")  # noqa: F821  (provided by PlatformIO)


def merge(source, target, env):
    output = os.path.join(env.subst("$BUILD_DIR"), "wokwi-flash.bin")
    images = []
    for offset, image in env.get("FLASH_EXTRA_IMAGES", []):
        images += [env.subst(offset), env.subst(image)]
    images += [env.subst("$ESP32_APP_OFFSET"), str(target[0])]
    # Platform 8 ships esptool 5 as a standalone program ($OBJCOPY), where the
    # command is merge-bin; older platforms ran esptool.py through Python.
    esptool = env.subst("$OBJCOPY")
    if esptool.endswith(".py"):
        command = ['"$PYTHONEXE"', f'"{esptool}"', "--chip", env.subst("$BOARD_MCU"), "merge_bin",
                   "-o", f'"{output}"', "--flash_size", "16MB"]
    else:
        command = [f'"{esptool}"', "--chip", env.subst("$BOARD_MCU"), "merge-bin",
                   "-o", f'"{output}"', "--flash-size", "16MB"]
    command += [f'"{item}"' for item in images]
    env.Execute(env.VerboseAction(" ".join(command), "Merging the Wokwi flash image"))


env.AddPostAction("$BUILD_DIR/${PROGNAME}.bin", merge)  # noqa: F821
