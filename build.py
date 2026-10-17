from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent

SOURCE = ROOT / "source" / "EryaMincho.bdf"
OUTPUT = ROOT / "precompiled" / "EryaMincho.ttf"
CONVERTER = ROOT / "tools" / "bdf2ttf" / "bdf2ttf.py"
METADATA = ROOT / "tools" / "bdf2ttf" / "metadata.json"
MCPACK_BUILDER = ROOT / "tools" / "mcpack_builder" / "build.py"

def run_command(command, label):
    print(f"\n{label}")
    result = subprocess.run(command, cwd=ROOT)
    if result.returncode != 0:
        print(f"{label} failed.", file=sys.stderr)
        return result.returncode
    return 0

def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    font_command = [
        sys.executable, str(CONVERTER), str(SOURCE), str(OUTPUT),
        "--metadata", str(METADATA),
    ]
    result = run_command(font_command, "Building EryaMincho TTF...")
    if result != 0:
        return result

    mcpack_command = [sys.executable, str(MCPACK_BUILDER)]
    result = run_command(mcpack_command, "Building Minecraft resource pack...")
    if result != 0:
        return result

    print("\nAll builds completed successfully.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
