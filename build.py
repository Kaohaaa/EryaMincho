
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent

HEX_CORRECTOR = ROOT / "tools" / "hex_corrector" / "correct.py"
CONVERTER = ROOT / "tools" / "bdf2ttf" / "bdf2ttf.py"
SOURCE = ROOT / "source" / "EryaMincho.bdf"
OUTPUT = ROOT / "precompiled" / "EryaMincho.ttf"
METADATA = ROOT / "tools" / "bdf2ttf" / "metadata.json"
MCPACK_BUILDER = ROOT / "tools" / "mcpack_builder" / "build.py"


def run_command(command, label):
    print(f"\n{label}", flush=True)
    result = subprocess.run(command, cwd=ROOT)

    if result.returncode != 0:
        print(
            f"{label} failed with exit code {result.returncode}.",
            file=sys.stderr,
        )
        return result.returncode

    return 0


def main():
    # Step 1: Correct the HEX file.
    result = run_command(
        [sys.executable, str(HEX_CORRECTOR)],
        "Correcting HEX source...",
    )
    if result != 0:
        return result

    # Step 2: Build the TrueType font.
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    font_command = [
        sys.executable,
        str(CONVERTER),
        str(SOURCE),
        str(OUTPUT),
        "--metadata",
        str(METADATA),
    ]

    result = run_command(font_command, "Building EryaMincho TTF...")
    if result != 0:
        return result

    # Step 3: Build the Minecraft resource pack.
    result = run_command(
        [sys.executable, str(MCPACK_BUILDER)],
        "Building Minecraft resource pack...",
    )
    if result != 0:
        return result

    print("\nAll builds completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
