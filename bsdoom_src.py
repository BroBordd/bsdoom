# Copyright 2026 - BrotherBoard
# Telegram >> @BroBordd

import os
import base64
import shutil
import uuid
import ctypes
import atexit
import traceback
import faulthandler
import datetime
import babase
import bauiv1 as bui
from babase._appmode import AppMode
from babase._appintent import AppIntentExec, AppIntentDefault
from _babase import empty_app_mode_handle_app_intent_exec, empty_app_mode_handle_app_intent_default
from _baclassic import classic_app_mode_activate


# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

try:
    _SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    _SCRIPT_DIR = babase.app.env.python_directory_user

LOG_PATH = os.path.join(_SCRIPT_DIR, "bsdoom.log")
_log_file = open(LOG_PATH, "a")
_log_file.write(f"\n\nBSDoom Boot: {datetime.datetime.now()}\n")
_log_file.flush()
faulthandler.enable(file=_log_file, all_threads=True)


def log(msg: str) -> None:
    print(msg)
    try:
        _log_file.write(msg + "\n")
        _log_file.flush()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class Const:
    DOOM_W   = 640
    DOOM_H   = 400
    GRID_W   = 64
    GRID_H   = 40
    STEP_X   = DOOM_W // GRID_W   # 10 px per cell
    STEP_Y   = DOOM_H // GRID_H   # 10 px per cell

    SO_NAME  = "libdoomgeneric.so"
    WAD_NAME = "DOOM1.WAD"
    DIR_PREFIX = ".bsdoom_"

    KEY_MAP = {
        "UP":     0xAD,
        "DOWN":   0xAF,
        "LEFT":   0xAC,
        "RIGHT":  0xAE,
        "ENTER":  13,
        "ESCAPE": 27,
        "USE":    32,
        "FIRE":   0x9D,
    }

    BTN_RELEASE_DELAY = 0.15   # seconds before synthesising a key-release event
    TICK_INTERVAL     = 0.035  # seconds between engine ticks (~28 Hz)


# ---------------------------------------------------------------------------
# Asset extraction
# ---------------------------------------------------------------------------

def _get_extract_parent() -> str:
    return os.path.abspath(babase.app.env.python_directory_user)


def _sweep_stale_dirs(parent: str) -> None:
    """Remove any extraction directories left behind by previous crashed sessions."""
    try:
        for entry in os.listdir(parent):
            if entry.startswith(Const.DIR_PREFIX):
                shutil.rmtree(os.path.join(parent, entry), ignore_errors=True)
    except Exception:
        pass


def _locate_on_disk() -> tuple[str, str] | None:
    """
    Search for libdoomgeneric.so and a WAD file on disk, relative to the
    app Python directory.  Returns (so_path, wad_path) if both are found,
    or None otherwise.
    """
    try:
        app_py = os.path.abspath(bui.app.env.python_directory_app)
        base   = os.path.abspath(os.path.join(app_py, os.pardir))
    except Exception:
        base = os.path.abspath(babase.app.env.python_directory_user)

    so_path = os.path.join(base, Const.SO_NAME)
    if not os.path.exists(so_path):
        return None

    for name in ("DOOM1.WAD", "doom1.wad", "DOOM.WAD", "doom.wad"):
        wad_path = os.path.join(base, name)
        if os.path.exists(wad_path):
            return os.path.abspath(so_path), os.path.abspath(wad_path)

    return None


def _extract_assets() -> tuple[str, str]:
    """
    Resolve the shared library and WAD paths using one of two strategies:

    1. Embedded blobs: if _ASSET_SO and _ASSET_WAD are populated (i.e. the
       file was produced by pack_bsdoom.py), decode them into a fresh
       temporary directory and return those paths.

    2. Disk fallback: if the asset variables are None (unpacked source),
       search for the files on disk relative to the app directory, mirroring
       the original _locate_files() behaviour.
    """
    if _ASSET_SO is not None and _ASSET_WAD is not None:
        log("[Assets] Embedded blobs found, extracting...")
        parent = _get_extract_parent()
        _sweep_stale_dirs(parent)

        extract_dir = os.path.join(parent, f"{Const.DIR_PREFIX}{uuid.uuid4().hex}")
        os.makedirs(extract_dir, exist_ok=True)
        atexit.register(shutil.rmtree, extract_dir, True)

        so_path  = os.path.join(extract_dir, Const.SO_NAME)
        wad_path = os.path.join(extract_dir, Const.WAD_NAME)

        with open(so_path, "wb") as fh:
            fh.write(base64.b85decode(_ASSET_SO))
        with open(wad_path, "wb") as fh:
            fh.write(base64.b85decode(_ASSET_WAD))

        os.chmod(so_path, 0o755)
        log(f"[Assets] Extracted to {extract_dir}")
        return so_path, wad_path

    log("[Assets] No embedded blobs, falling back to disk search...")
    result = _locate_on_disk()
    if result is None:
        raise FileNotFoundError(
            f"Could not find {Const.SO_NAME} and a WAD file on disk, "
            "and no embedded assets are present. "
            "Either run pack_bsdoom.py or place the files next to the app."
        )
    so_path, wad_path = result
    log(f"[Assets] Found on disk: {so_path}")
    log(f"[Assets] Found on disk: {wad_path}")
    return so_path, wad_path


# ---------------------------------------------------------------------------
# Screen-buffer helper
# ---------------------------------------------------------------------------

_PixelArray = ctypes.c_uint32 * (Const.DOOM_W * Const.DOOM_H)


def _resolve_screenbuffer(lib: ctypes.CDLL):
    """
    Dereference DG_ScreenBuffer after doomgeneric_Create() returns.
    The pointer is only valid once the engine has completed initialisation.
    """
    addr = ctypes.c_void_p.in_dll(lib, "DG_ScreenBuffer").value
    if not addr:
        return None
    return _PixelArray.from_address(addr)


# ---------------------------------------------------------------------------
# App mode
# ---------------------------------------------------------------------------

# ba_meta export babase.AppMode
class DoomAppMode(AppMode):

    @classmethod
    def can_handle_intent(cls, intent):
        return isinstance(intent, (AppIntentExec, AppIntentDefault))

    def handle_intent(self, intent):
        if isinstance(intent, AppIntentExec):
            empty_app_mode_handle_app_intent_exec(intent.code)
        else:
            empty_app_mode_handle_app_intent_default()

    # ------------------------------------------------------------------
    # Activation
    # ------------------------------------------------------------------

    def on_activate(self) -> None:
        log("[AppMode] Activated.")
        classic_app_mode_activate()

        self._lib             = None
        self._screenbuf       = None
        self._frame_ready     = None
        self._release_timers  = {}
        self._timer           = None
        self._c_argv          = None   # kept alive to prevent GC-induced segfault
        self._argv_bytes      = None

        try:
            log("[AppMode] Building UI grid...")
            sw, sh = bui.get_virtual_screen_size()
            self.root = bui.containerwidget(
                size=(sw, sh), background=False, scale=1.0
            )

            scale  = min(sw / Const.DOOM_W, sh / Const.DOOM_H) * 1.05
            cell_w = scale * Const.STEP_X
            cell_h = scale * Const.STEP_Y
            ox     = (sw - cell_w * Const.GRID_W) / 2.0
            oy     = (sh - cell_h * Const.GRID_H) / 2.0

            self._pixels  = []
            self._indices = []

            for gy in range(Const.GRID_H):
                doom_y = gy * Const.STEP_Y
                for gx in range(Const.GRID_W):
                    doom_x = gx * Const.STEP_X
                    self._indices.append(doom_y * Const.DOOM_W + doom_x)
                    widget = bui.imagewidget(
                        parent=self.root,
                        size=(cell_w + 1.0, cell_h + 1.0),
                        position=(ox + cell_w * gx, oy + cell_h * (Const.GRID_H - 1 - gy)),
                        texture=bui.gettexture("white"),
                        color=(0.0, 0.0, 0.0),
                    )
                    self._pixels.append(widget)

            self._build_buttons(sw, sh)
            log("[AppMode] UI built. Starting engine...")

            if self._start_engine():
                log("[AppMode] Engine started. Launching tick timer.")
                self._timer = babase.AppTimer(
                    Const.TICK_INTERVAL, self._tick, repeat=True
                )

        except Exception:
            log(f"[AppMode] Fatal error during activation:\n{traceback.format_exc()}")
            bui.screenmessage("BSDoom UI crash. See bsdoom.log.", color=(1, 0, 0))

    # ------------------------------------------------------------------
    # Engine initialisation
    # ------------------------------------------------------------------

    def _start_engine(self) -> bool:
        try:
            so_path, wad_path = _extract_assets()
        except FileNotFoundError as e:
            log(f"[Engine] Assets not found: {e}")
            bui.screenmessage("BSDoom: Missing .so or WAD. See bsdoom.log.", color=(1, 0, 0))
            return False
        except Exception:
            log(f"[Engine] Asset extraction failed:\n{traceback.format_exc()}")
            bui.screenmessage("BSDoom: Asset extraction failed.", color=(1, 0, 0))
            return False

        log(f"[Engine] Shared library path : {so_path}")
        log(f"[Engine] WAD path            : {wad_path}")

        try:
            log("[Engine] Loading shared library...")
            lib = ctypes.CDLL(so_path)

            lib.doomgeneric_Create.argtypes = [
                ctypes.c_int, ctypes.POINTER(ctypes.c_char_p)
            ]
            lib.doomgeneric_Create.restype = None
            lib.doomgeneric_Tick.argtypes  = []
            lib.doomgeneric_Tick.restype   = None
            lib.bs_add_key.argtypes        = [ctypes.c_ubyte, ctypes.c_int]
            lib.bs_add_key.restype         = None

            self._frame_ready = ctypes.c_int.in_dll(lib, "bs_frame_ready")
            self._lib         = lib

            # Build argv and store as instance variables to prevent the GC
            # from freeing the buffer while DOOM still holds an internal
            # pointer to it (would cause a segfault several seconds in).
            self._argv_bytes = [
                b"doom", b"-iwad", wad_path.encode(), b"-nosound", b"-nomusic"
            ]
            argc = len(self._argv_bytes)
            self._c_argv = (ctypes.c_char_p * (argc + 1))(*self._argv_bytes, None)

            prev_cwd = os.getcwd()
            os.chdir(os.path.dirname(wad_path))
            log("[Engine] Calling doomgeneric_Create()...")
            lib.doomgeneric_Create(argc, self._c_argv)
            os.chdir(prev_cwd)
            log("[Engine] doomgeneric_Create() returned.")

            self._screenbuf = _resolve_screenbuffer(lib)
            if self._screenbuf is None:
                log("[Engine] DG_ScreenBuffer is NULL after Create().")
                return False

            log("[Engine] DG_ScreenBuffer resolved successfully.")
            return True

        except Exception:
            log(f"[Engine] Fatal error during initialisation:\n{traceback.format_exc()}")
            bui.screenmessage("BSDoom engine fatal. See bsdoom.log.", color=(1, 0, 0))
            return False

    # ------------------------------------------------------------------
    # Input handling
    # ------------------------------------------------------------------

    def _on_input(self, key: str, action: str) -> None:
        if not self._lib:
            return
        doom_key = Const.KEY_MAP.get(key, 0)
        if doom_key:
            self._lib.bs_add_key(doom_key, 1 if action == "press" else 0)

    def _btn(
        self,
        parent,
        pos: tuple,
        size: tuple,
        label: str,
        key: str,
        color: tuple = (0.25, 0.25, 0.25),
        repeat: bool = False,
    ) -> None:
        """Create a single on-screen button that synthesises a press/release pair."""
        def _tap():
            self._on_input(key, "press")
            self._release_timers[key] = None
            def _release():
                self._on_input(key, "release")
            self._release_timers[key] = babase.AppTimer(
                Const.BTN_RELEASE_DELAY, _release
            )

        bui.buttonwidget(
            parent=parent,
            position=pos,
            size=size,
            label=label,
            color=color,
            textcolor=(1, 1, 1),
            texture=bui.gettexture("white"),
            enable_sound=False,
            repeat=repeat,
            on_activate_call=_tap,
        )

    def _build_buttons(self, sw: float, sh: float) -> None:
        """Construct the D-pad and action button overlays."""
        bs, gap, margin = 80, 8, 24

        dpad = bui.containerwidget(
            parent=self.root,
            background=False,
            size=(bs * 3 + gap * 2, bs * 3 + gap * 2),
            position=(margin, margin),
        )
        self._btn(dpad, (bs + gap, (bs + gap) * 2), (bs, bs), "Up",    "UP",    repeat=True)
        self._btn(dpad, (bs + gap, 0),               (bs, bs), "Down",  "DOWN",  repeat=True)
        self._btn(dpad, (0, bs + gap),               (bs, bs), "Left",  "LEFT",  repeat=True)
        self._btn(dpad, ((bs + gap) * 2, bs + gap),  (bs, bs), "Right", "RIGHT", repeat=True)

        act = bui.containerwidget(
            parent=self.root,
            background=False,
            size=(bs, bs * 4 + gap * 3),
            position=(sw - margin - bs, margin),
        )
        self._btn(act, (0, (bs + gap) * 3), (bs, bs), "Esc",   "ESCAPE", (0.25, 0.25, 0.25))
        self._btn(act, (0, (bs + gap) * 2), (bs, bs), "Enter", "ENTER",  (0.15, 0.15, 0.50))
        self._btn(act, (0, (bs + gap) * 1), (bs, bs), "Use",   "USE",    (0.10, 0.40, 0.10))
        self._btn(act, (0, 0),              (bs, bs), "Fire",  "FIRE",   (0.50, 0.10, 0.10), repeat=True)

    # ------------------------------------------------------------------
    # Tick loop
    # ------------------------------------------------------------------

    def _tick(self) -> None:
        """Called by AppTimer at approximately 28 Hz to advance the engine one step."""
        if not self._lib or not self.root.exists():
            self._timer = None
            return

        try:
            self._lib.doomgeneric_Tick()

            if not self._frame_ready.value:
                return
            self._frame_ready.value = 0

            buf = self._screenbuf
            if buf is None:
                log("[Tick] DG_ScreenBuffer is NULL, skipping frame.")
                return

            indices = self._indices
            pixels  = self._pixels
            edit    = bui.imagewidget

            for i in range(len(pixels)):
                if not pixels[i].exists():
                    return
                val = buf[indices[i]]
                edit(
                    edit=pixels[i],
                    color=(
                        ((val >> 16) & 0xFF) / 255.0,
                        ((val >>  8) & 0xFF) / 255.0,
                        ( val        & 0xFF) / 255.0,
                    ),
                )

        except Exception:
            log(f"[Tick] Fatal error:\n{traceback.format_exc()}")
            self._timer = None

    # ------------------------------------------------------------------
    # Deactivation
    # ------------------------------------------------------------------

    def on_deactivate(self) -> None:
        log("[AppMode] Deactivated.")
        self._timer = None
        if self.root and self.root.exists():
            self.root.delete()


# ---------------------------------------------------------------------------
# Plugin entry point
# ---------------------------------------------------------------------------

# ba_meta require api 9
# ba_meta export babase.Plugin
class AppModeLoader(bui.Plugin):
    pass


# ---------------------------------------------------------------------------
# Embedded assets (appended by pack_bsdoom.py)
# ---------------------------------------------------------------------------

_ASSET_SO  = None
_ASSET_WAD = None
