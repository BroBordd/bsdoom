# BSDoom

Run DOOM inside [Ballistica](https://github.com/efroemling/ballistica) using a 64×40 widget grid as a framebuffer.

---

## Repository layout

```
bsdoom/
├── bsdoom.py          # Ballistica plugin (self-contained after packing)
├── pack_bsdoom.py     # Encodes assets and appends them to bsdoom.py
├── setup_repo.sh      # Copies doomgeneric source and strips unused files
├── doomgeneric/       # doomgeneric source tree (added by setup_repo.sh)
│   ├── Makefile.python
│   ├── doomgeneric_python.c
│   └── ...
└── README.md
```

---

## Step 1 — Add the doomgeneric source

Clone the upstream doomgeneric repository next to this repo, then run the setup script:

```bash
git clone https://github.com/ozkl/doomgeneric ../doomgeneric
bash setup_repo.sh
```

This copies the source into `doomgeneric/` and removes unused platform backends, Makefiles, and build artifacts.

---

## Step 2 — Build `libdoomgeneric.so`

### Requirements

| Tool | Minimum version |
|------|----------------|
| Android NDK | r25c or later |
| GNU Make | 3.81 or later |
| Python 3 headers | only needed if cross-compiling with the python Makefile |

The NDK can be downloaded from [developer.android.com/ndk/downloads](https://developer.android.com/ndk/downloads) or installed via Android Studio SDK Manager.

### 2a — Native Linux build (for testing on desktop)

```bash
cd doomgeneric

make -f Makefile.python
```

The output is `libdoomgeneric.so` in the same directory.

### 2b — Android cross-compile (arm64-v8a)

Set `NDK` to your NDK installation path, then:

```bash
export NDK=/path/to/android-ndk-r25c
export TOOLCHAIN=$NDK/toolchains/llvm/prebuilt/linux-x86_64
export TARGET=aarch64-linux-android
export API=29

export CC=$TOOLCHAIN/bin/$TARGET$API-clang
export AR=$TOOLCHAIN/bin/llvm-ar
export STRIP=$TOOLCHAIN/bin/llvm-strip

cd doomgeneric

make -f Makefile.python \
    CC="$CC" \
    AR="$AR" \
    EXTRA_CFLAGS="--target=$TARGET$API -fPIC"
```

Strip debug symbols before shipping to save size:

```bash
$STRIP --strip-unneeded libdoomgeneric.so
```

### 2c — Android cross-compile (armeabi-v7a)

Same as above but use a 32-bit target:

```bash
export TARGET=armv7a-linux-androideabi
export CC=$TOOLCHAIN/bin/$TARGET$API-clang

make -f Makefile.python \
    CC="$CC" \
    AR="$AR" \
    EXTRA_CFLAGS="--target=$TARGET$API -fPIC -mfloat-abi=softfp"
```

### Verifying the output

```bash
file libdoomgeneric.so
# Should print: ELF 64-bit LSB shared object, ARM aarch64  (or 32-bit ARM)

nm -D libdoomgeneric.so | grep -E "doomgeneric_Create|doomgeneric_Tick|DG_ScreenBuffer|bs_add_key|bs_frame_ready"
# All five symbols must be present
```

---

## Step 3 — Obtain a WAD file

BSDoom requires an IWAD.  The shareware episode is free:

- **DOOM1.WAD** (shareware, free) — available from [doomworld.com](https://www.doomworld.com/classicdoom/info/shareware.php) and many mirrors.
- **DOOM.WAD / DOOM2.WAD** (commercial) — purchased copies from Steam or GOG work directly.

Rename the file to `DOOM1.WAD` (uppercase) or adjust `Const.WAD_NAME` in `bsdoom.py`.

---

## Step 4 — Pack assets into the plugin

`pack_bsdoom.py` base-85 encodes both binaries and replaces the two sentinel variables at the bottom of `bsdoom.py`:

```bash
python3 pack_bsdoom.py libdoomgeneric.so DOOM1.WAD bsdoom.py bsdoom_packed.py
```

The resulting `bsdoom_packed.py` is fully self-contained — copy it to the Ballistica user scripts directory and it will extract and load the assets on first activation.

```
Android path:  /sdcard/Android/data/<app_package>/files/ba_data/python/
```

---

## How it works

1. On activation `DoomAppMode` decodes the embedded blobs into a UUID-named temporary directory inside the Ballistica user Python directory, which is guaranteed writable and executable on Android.
2. `doomgeneric_Create()` boots the engine. The `argv` array is kept alive as an instance variable to prevent a garbage-collection-induced segfault that would otherwise occur a few seconds into gameplay.
3. An `AppTimer` fires every 35 ms, calls `doomgeneric_Tick()`, then reads the `bs_frame_ready` flag set by `DG_DrawFrame` in the shared library. When a new frame is ready the 64×40 grid of `imagewidget` cells is recoloured by sampling one pixel per cell from `DG_ScreenBuffer`.
4. On deactivation or crash the temporary directory is removed via `atexit` and also swept on the next boot to handle hard kills.

---

## Controls

| Button | Action |
|--------|--------|
| Up / Down / Left / Right | Move and turn |
| Fire | Primary attack |
| Use | Open doors / activate switches |
| Enter | Confirm menus |
| Esc | Open/close menu |

---

## License

BSDoom plugin code is released under the same license as this repository.
The doomgeneric library and DOOM engine source are subject to their own licenses — see `doomgeneric/` and the [doomgeneric repository](https://github.com/ozkl/doomgeneric).
