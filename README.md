# BSDoom

DOOM running inside [Ballistica](https://github.com/efroemling/ballistica) (BombSquad). The engine is loaded as a native `.so` via Python `ctypes`, and the framebuffer gets blasted out to a grid of `imagewidget` objects. Sound hooks fire C callbacks straight into BombSquad's native audio mixer.

Yeah, it actually works.

![BSDoom running in BombSquad](https://github.com/user-attachments/assets/3ebe5ba1-bfe3-4ddc-b271-30131211d231)

---

## Repo Layout

```
bsdoom/
├── bsdoom_src.py      # main plugin source (gets packed into bsdoom.py)
├── pack_bsdoom.py     # base85-encodes the .so, WAD, and sounds zip into the final script
├── make_sounds.py     # rips DMX audio from the WAD, converts to .ogg via FFmpeg
├── setup_repo.sh      # pulls in doomgeneric source and strips platform junk
└── doomgeneric/       # DOOM engine C source (populated by setup_repo.sh)
```

---

## Build

### What you need
- **GNU Make** 3.81+
- **FFmpeg** (for audio conversion)
- **Android NDK** r25c+ (only if you're cross-compiling for Android)

### 1. Get the DOOM source

Clone `doomgeneric` next to this repo, then run the setup script to copy over what we need:

```bash
git clone https://github.com/ozkl/doomgeneric ../doomgeneric
bash setup_repo.sh
```

### 2. Build the shared library

The engine has to be compiled as a `.so` so the Python plugin can `ctypes` into it.

**Linux (for local testing):**
```bash
cd doomgeneric
make -f Makefile.python
```

**Android cross-compile (arm64-v8a):**
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

$STRIP --strip-unneeded libdoomgeneric.so
```

### 3. Get a WAD

You need an IWAD. If you own DOOM on Steam or GOG, just grab `DOOM.WAD` or `DOOM2.WAD` from the install directory.

Or grab the shareware episode right now:
```bash
wget https://distro.ibiblio.org/pub/linux/distributions/slitaz/sources/packages/d/doom1.wad -O DOOM1.WAD
```

### 4. Convert the audio

DOOM's sound format (DMX) is ancient and Ballistica only knows `.ogg`, so we have to convert. Put your WAD next to `make_sounds.py` and run:

```bash
python3 make_sounds.py
```

This spits out a `sounds.zip` with all the game audio converted and ready to go.

### 5. Pack everything into one file

Now you've got the three pieces: `libdoomgeneric.so`, `DOOM1.WAD`, `sounds.zip`. The pack script encodes them all directly into the bottom of the plugin:

```bash
python3 pack_bsdoom.py libdoomgeneric.so DOOM1.WAD sounds.zip bsdoom_src.py bsdoom.py
```

The output `bsdoom.py` is fully self-contained. Drop it into your Ballistica `mods` folder, activate the plugin in-game, and it'll unpack itself, inject the audio, and boot the engine.

---

## How it works

1. **Startup** — `DoomAppMode` decodes the embedded blobs on activation. The `.so` and WAD go to a temp folder, the sounds extract into `ba_data/audio`.
2. **Engine** — `ctypes` loads the library and calls `doomgeneric_Create()`. A background `AppTimer` ticks the engine at ~35Hz.
3. **Rendering** — Each tick, the engine writes to `DG_ScreenBuffer` (a raw RGBA array). Python reads that buffer and maps the pixel colors onto a grid of `imagewidget` objects. Grid resolution is configurable from the launch menu.
4. **Audio** — Modified C code fires a callback pointer to Python whenever DOOM plays a sound. Python looks up the sound name and calls `bui.getsound().play()` — so you get real BombSquad audio, no hacks.

---

## Controls

### Movement
| Button | Action |
|--------|--------|
| **Fwd / Back** | Walk forward / backward |
| **<St / St>** | Strafe left / right |
| **<Aim / Aim>** | Turn left / right |

### Actions
| Button | Action |
|--------|--------|
| **USE** | Open doors / activate switches |
| **FIRE** | Shoot |
| **Run** | Hold to run |

### Weapons
| Button | Weapon |
|--------|--------|
| **1 Fist** | Fist / Chainsaw |
| **2 Pist** | Pistol |
| **3 Shot** | Shotgun |
| **4 Chn** | Chaingun |
| **5 Rok** | Rocket Launcher |
| **6 Plas** | Plasma Rifle |
| **7 BFG** | BFG 9000 |

### System
| Button | Action |
|--------|--------|
| **Map** | Toggle automap |
| **+  /  -** | Zoom automap in / out |
| **ENTER** | Confirm menus |
| **Esc** | DOOM main menu |
| **\|\|** | Pause |
| **Help (F1)** | Help screen |
| **Save (F2)** | Save game |
| **Load (F3)** | Load game |
| **Gamma (F5)** | Cycle gamma correction |

---

## Launch Options

The launch menu (shown before the engine boots) lets you configure a few things:

- **Grid Width** — how many cells wide the framebuffer is. Height is calculated automatically to keep the 16:10 aspect ratio. Presets for 32×20, 64×40, and 128×80 are included. Higher = sharper but heavier.
- **Advanced Options:**
  - **Engine tick rate** — defaults to 35Hz, you can bump it up or slow it down
  - **Scale mode** — toggle between fit and fill
  - **Live overlays** — enables an FPS counter, tick time stats, and a bar graph in the corner. Useful for tuning grid resolution.

---

## License

The `bsdoom` plugin code is MIT licensed. The `doomgeneric` library and DOOM engine source are GPL. WAD data belongs to ZeniMax — you'll need your own copy of the game files, or use the shareware WAD.
