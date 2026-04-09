# BSDoom

Run DOOM inside [Ballistica](https://github.com/efroemling/ballistica) (BombSquad) natively using Python `ctypes`, utilizing a dynamic grid of UI widgets as a custom framebuffer, complete with native audio mapping!

---

## Repository Layout

```text
bsdoom/
├── bsdoom_src.py      # Core Ballistica plugin (gets packed into bsdoom.py)
├── pack_bsdoom.py     # Base85 encodes the .so, WAD, and ZIP into the final script
├── make_sounds.py     # Extracts DMX audio from DOOM, converts to OGG via FFmpeg
├── setup_repo.sh      # Copies doomgeneric source and strips unused files
└── doomgeneric/       # DOOM engine C source tree (added by setup_repo.sh)
```

---

## Build Instructions

### Prerequisites
Before building, ensure you have the following installed:
* **GNU Make** (3.81 or later)
* **FFmpeg** (For converting DOOM's audio to `.ogg`)
* **Android NDK** (r25c or later, if compiling for Android)

### Step 1: Add the DOOM C-Source
Clone the upstream `doomgeneric` repository next to this repo, then run the setup script to copy the necessary files and strip away unused platform code:

```bash
git clone https://github.com/ozkl/doomgeneric ../doomgeneric
bash setup_repo.sh
```

### Step 2: Build `libdoomgeneric.so`
You must compile the engine into a shared library so our Python plugin can hook into it.

**For Native Linux (Desktop Testing):**
```bash
cd doomgeneric
make -f Makefile.python
```

**For Android Cross-Compile (arm64-v8a):**
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

# Strip debug symbols to reduce file size
$STRIP --strip-unneeded libdoomgeneric.so
```

### Step 3: Obtain an IWAD (Game Data)
You need a DOOM Game file (`.WAD`) to play. If you own DOOM on Steam or GOG, you can just grab `DOOM.WAD` or `DOOM2.WAD` from your install folder.

Alternatively, you can instantly download the **Shareware DOOM Episode** directly to the repo folder:
```bash
wget https://distro.ibiblio.org/pub/linux/distributions/slitaz/sources/packages/d/doom1.wad -O DOOM1.WAD
```

### Step 4: Convert Audio Assets
DOOM uses an ancient audio format called `DMX`. Ballistica requires standard `.ogg` files. 
Run the provided sound extractor script to rip the audio out of the WAD, strip the headers, and convert them to OGG using FFmpeg. 
*(Ensure your WAD file is named `DOOM1.WAD` and sits next to the python script).*

```bash
python3 make_sounds.py
```
*This will generate a `sounds.zip` file containing all the converted game audio.*

### Step 5: Pack the Final Plugin
You now have the three required binaries: `libdoomgeneric.so`, `DOOM1.WAD`, and `sounds.zip`. 
Use the pack script to encode them as text directly into the bottom of the Python plugin. 

```bash
python3 pack_bsdoom.py libdoomgeneric.so DOOM1.WAD sounds.zip bsdoom_src.py bsdoom.py
```

The output file **`bsdoom.py`** is now fully self-contained! 
Drop it into your Ballistica/BombSquad `mods` folder. When you activate the plugin in-game, it will unpack the binaries, inject the audio, and boot the engine automatically.

---

## How It Works

1. **Extraction:** On activation, `DoomAppMode` decodes the embedded blobs. The C library and WAD go to a secure temp folder, while the `sounds.zip` extracts directly into Ballistica's native `ba_data/audio` directory.
2. **Execution:** Python utilizes `ctypes` to load the `.so` and run `doomgeneric_Create()`.
3. **The Display:** A background `AppTimer` ticks the engine at 35Hz. Python reads the RGBA byte-array outputted by the DOOM engine (`DG_ScreenBuffer`) and maps the colors mathematically to a grid of Ballistica `imagewidget` objects.
4. **Native Sound Hook:** When a sound triggers in DOOM (like a shotgun blast), our modified C-code fires a callback pointer back to Python. Python translates the sound name and triggers `bui.getsound().play()`, rendering DOOM audio flawlessly through BombSquad's native sound mixer!

---

## Controls
| Button | Action |
|--------|--------|
| **D-Pad** | Move & Turn |
| **Fire** | Primary Attack |
| **Use** | Open Doors / Switches |
| **Enter** | Confirm Menus |
| **Esc** | Toggle DOOM Main Menu |

---

## License
The `bsdoom` plugin code is released under the MIT License. 
The `doomgeneric` library, DOOM engine source, and generated WAD data are subject to their own respective licenses (GPL / ZeniMax Media).
