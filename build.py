
from pathlib import Path
import subprocess
import sys

# Project root directory
ROOT = Path(__file__).resolve().parent

# Build configuration
SOURCE = ROOT / "source" / "EryaMincho.bdf"
OUTPUT = ROOT / "precompiled" / "EryaMincho.ttf"
CONVERTER = ROOT / "tools" / "bdf2ttf" / "bdf2ttf.py"
METADATA = ROOT / "tools" / "bdf2ttf" / "metadata.json"


def main():
    # Ensure the output directory exists
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    # Construct the build command
    command = [
        sys.executable,
        str(CONVERTER),
        str(SOURCE),
        str(OUTPUT),
        "--metadata",
        str(METADATA),
    ]

    print("Building EryaMincho...")
    result = subprocess.run(command, cwd=ROOT)

    if result.returncode != 0:
        print("Build failed.", file=sys.stderr)
        return result.returncode

    print(f"Build completed: {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
