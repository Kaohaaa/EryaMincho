#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
from PIL import Image, ImageDraw


# CJK Unified Ideographs (Basic)
CJK_BASIC_START = 0x4E00
CJK_BASIC_END = 0x9FFF

# CJK Unified Ideographs Extension A
CJK_EXT_A_START = 0x3400
CJK_EXT_A_END = 0x4DBF


# Total number of characters in each range
TOTAL_BASIC = CJK_BASIC_END - CJK_BASIC_START + 1
TOTAL_EXT_A = CJK_EXT_A_END - CJK_EXT_A_START + 1
TOTAL_CJK = TOTAL_BASIC + TOTAL_EXT_A


# Progress bar appearance
BAR_WIDTH = 160
BAR_HEIGHT = 10

FILLED_COLOR = (76, 139, 245)
BACKGROUND_COLOR = (232, 232, 232)


def is_cjk_basic(codepoint):
    """Return True if the codepoint is in CJK Unified Ideographs."""
    return CJK_BASIC_START <= codepoint <= CJK_BASIC_END


def is_cjk_ext_a(codepoint):
    """Return True if the codepoint is in CJK Unified Ideographs Extension A."""
    return CJK_EXT_A_START <= codepoint <= CJK_EXT_A_END


def count_characters(hex_path):
    """
    Read a Unifont .hex file and return two sets:
    - CJK Unified Ideographs
    - CJK Unified Ideographs Extension A
    """

    basic_chars = set()
    ext_a_chars = set()

    with open(hex_path, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()

            if not line or ":" not in line:
                continue

            code_str = line.split(":", 1)[0]

            try:
                codepoint = int(code_str, 16)
            except ValueError:
                continue

            if is_cjk_basic(codepoint):
                basic_chars.add(codepoint)

            elif is_cjk_ext_a(codepoint):
                ext_a_chars.add(codepoint)

    return basic_chars, ext_a_chars


def save_progress_bar(value, total, output_path):
    """
    Create a small PNG progress bar.

    The image contains only two colored blocks:
    filled portion and remaining portion.
    """

    if total <= 0:
        ratio = 0
    else:
        ratio = value / total

    ratio = max(0.0, min(1.0, ratio))

    filled_width = round(BAR_WIDTH * ratio)

    image = Image.new(
        "RGB",
        (BAR_WIDTH, BAR_HEIGHT),
        BACKGROUND_COLOR
    )

    draw = ImageDraw.Draw(image)

    if filled_width > 0:
        draw.rectangle(
            [
                0,
                0,
                filled_width - 1,
                BAR_HEIGHT - 1
            ],
            fill=FILLED_COLOR
        )

    image.save(
        output_path,
        format="PNG",
        optimize=True
    )


def save_missing_list(basic_chars, ext_a_chars, output_path):
    """Save all missing CJK characters to a text file."""

    existing = basic_chars | ext_a_chars

    with open(output_path, "w", encoding="utf-8") as file:

        # CJK Unified Ideographs
        for codepoint in range(
            CJK_BASIC_START,
            CJK_BASIC_END + 1
        ):
            if codepoint not in existing:
                file.write(f"U+{codepoint:04X}\n")

        # CJK Unified Ideographs Extension A
        for codepoint in range(
            CJK_EXT_A_START,
            CJK_EXT_A_END + 1
        ):
            if codepoint not in existing:
                file.write(f"U+{codepoint:04X}\n")


def main():

    if len(sys.argv) < 2:
        print("Usage: python count.py <font.hex>")
        sys.exit(1)

    hex_path = sys.argv[1]

    if not os.path.isfile(hex_path):
        print(f"Error: file not found: {hex_path}")
        sys.exit(1)

    # Output directories
    image_dir = "./images"
    count_dir = "./tools"

    os.makedirs(image_dir, exist_ok=True)
    os.makedirs(count_dir, exist_ok=True)

    # Read and count characters
    basic_chars, ext_a_chars = count_characters(hex_path)

    basic_count = len(basic_chars)
    ext_a_count = len(ext_a_chars)
    total_count = basic_count + ext_a_count

    basic_percent = basic_count / TOTAL_BASIC * 100
    ext_a_percent = ext_a_count / TOTAL_EXT_A * 100
    total_percent = total_count / TOTAL_CJK * 100

    # Save progress bars
    save_progress_bar(
        basic_count,
        TOTAL_BASIC,
        os.path.join(
            image_dir,
            "basic_progress.png"
        )
    )

    save_progress_bar(
        ext_a_count,
        TOTAL_EXT_A,
        os.path.join(
            image_dir,
            "ext_a_progress.png"
        )
    )

    save_progress_bar(
        total_count,
        TOTAL_CJK,
        os.path.join(
            image_dir,
            "total_progress.png"
        )
    )

    # Save missing character list
    save_missing_list(
        basic_chars,
        ext_a_chars,
        os.path.join(
            count_dir,
            "missing.txt"
        )
    )

    # Print report
    print()
    print("Chinese Character Coverage Report")
    print("---------------------------------")

    print(
        f"CJK Unified Ideographs (Basic): "
        f"{basic_count:,} / {TOTAL_BASIC:,} "
        f"({basic_percent:.2f}%)"
    )

    print(
        f"CJK Unified Ideographs Extension A: "
        f"{ext_a_count:,} / {TOTAL_EXT_A:,} "
        f"({ext_a_percent:.2f}%)"
    )

    print(
        f"Total (Basic + Extension A): "
        f"{total_count:,} / {TOTAL_CJK:,} "
        f"({total_percent:.2f}%)"
    )

    print()
    print(
        "Progress bars saved to: "
        f"{os.path.abspath(image_dir)}"
    )

    print(
        "Missing character list saved to: "
        f"{os.path.abspath(os.path.join(count_dir, 'missing.txt'))}"
    )


if __name__ == "__main__":
    main()