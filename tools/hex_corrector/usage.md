> This program is used to correct 12px wide glyphs to 16px wide and replace CRLF with LF.

Syntax: `correct.py [<input_file> <output_file>]`

If no parameters are passed, it will automatically use the default input path `source/EryaMincho.hex` and output path `source/corrected.hex`.

Thus you can use these commands to quick generate the corrected hex file:
```

>>> cd EryaMincho

>>> python tools/hex_corrector/correct.py

```