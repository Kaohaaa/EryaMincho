This is a tutorial on building Erya Mincho.

Note: Due to the conversion program, you need to delete the Latin part of `EryaMincho.hex` manually first.

When everything is ready, use these commands:
```
>>> cd EryaMincho

>>> tools/build/hex2otf hex=source/EryaMincho.hex out=precompiled/EryaMincho.otf format=truetype
```