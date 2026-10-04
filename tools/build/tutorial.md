This is a tutorial on building Erya Mincho.

Firstly, you need to make a executable file:
```
>>> cd EryaMincho/tools/build

>>> make all
```

When everything is ready, use these commands:
```
>>> cd EryaMincho

>>> tools/build/hex2otf hex=source/EryaMincho.hex out=precompiled/EryaMincho.otf format=truetype
```

Then you may find EryaMincho.otf in `precompiled` fold.

Note: Due to the conversion program, you need to delete the Latin part of `EryaMincho.hex` manually.
