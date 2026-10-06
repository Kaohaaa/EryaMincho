
#!/usr/bin/env python3

import sys


def fix_hex_file(input_file, output_file):
    with open(input_file, "r", encoding="ascii", newline="") as f:
        lines = f.read().splitlines()

    output_lines = []

    for line in lines:
        # Preserve empty lines
        if not line:
            output_lines.append(line)
            continue

        # HEX format: <unicode>:<glyph>
        try:
            codepoint, glyph = line.split(":", 1)
        except ValueError:
            # Preserve malformed lines as-is
            output_lines.append(line)
            continue

        # 12×16 glyph: 16 rows × 3 hexadecimal characters per row = 48
        if len(glyph) == 48:
            # Add one 0 after every 3 hexadecimal characters,
            # expanding each row from 12 bits to 16 bits
            glyph = "".join(
                glyph[i:i + 3] + "0"
                for i in range(0, 48, 3)
            )

        output_lines.append(f"{codepoint}:{glyph}")

    # Use LF for all output line endings
    with open(output_file, "w", encoding="ascii", newline="\n") as f:
        f.write("\n".join(output_lines))
        f.write("\n")


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <input_file> <output_file>")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    try:
        fix_hex_file(input_file, output_file)
    except FileNotFoundError:
        print(f"Error: input file not found: {input_file}")
        sys.exit(1)
    except OSError as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

