from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "source" / "corrected.hex"
FONT_DIR = ROOT / "mcpack" / "assets" / "minecraft" / "font"
FONT_ARCHIVE = FONT_DIR / "eryamincho.zip"
MCPACK_DIR = ROOT / "mcpack"
OUTPUT_DIR = ROOT / "precompiled"
RESOURCE_PACK_ARCHIVE = OUTPUT_DIR / "EryaMincho-ResourcePack.zip"


def create_font_archive():
    if not SOURCE.is_file():
        raise FileNotFoundError(f"HEX source file not found: {SOURCE}")

    FONT_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(FONT_ARCHIVE, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        # Keep the HEX file at the archive root for Minecraft's unihex provider.
        archive.write(SOURCE, arcname=SOURCE.name)

    print(f"Created: {FONT_ARCHIVE.relative_to(ROOT)}")


def create_resource_pack_archive():
    if not MCPACK_DIR.is_dir():
        raise FileNotFoundError(f"Resource pack directory not found: {MCPACK_DIR}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(RESOURCE_PACK_ARCHIVE, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        # Store relative paths so pack.mcmeta and assets/ are at the ZIP root.
        for path in sorted(MCPACK_DIR.rglob("*")):
            if path.is_file():
                archive.write(path, arcname=path.relative_to(MCPACK_DIR).as_posix())

    print(f"Created: {RESOURCE_PACK_ARCHIVE.relative_to(ROOT)}")


def main():
    try:
        create_font_archive()
        create_resource_pack_archive()
    except OSError as error:
        print(f"Build failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
