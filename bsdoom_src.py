# Copyright 2026 - BrotherBoard
# Telegram >> @BroBordd

import os
import ctypes
import bauiv1 as bui

from uuid import uuid4
from shutil import rmtree
from zipfile import ZipFile
from base64 import b85decode
from threading import Thread
from datetime import datetime
from traceback import format_exc
from babase._appmode import AppMode
from atexit import register as reg_trap
from bascenev1 import set_internal_music
from faulthandler import enable as fhandler
from _baclassic import classic_app_mode_activate
from babase._appintent import AppIntentExec, AppIntentDefault
from _babase import empty_app_mode_handle_app_intent_exec, empty_app_mode_handle_app_intent_default


# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

try:
    _SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    _SCRIPT_DIR = bui.app.env.python_directory_user

LOG_PATH  = os.path.join(_SCRIPT_DIR, "bsdoom.log")
_log_file = open(LOG_PATH, "a")
_log_file.write(f"\n\nBSDoom Boot: {datetime.now()}\n")
_log_file.flush()
fhandler(file=_log_file, all_threads=True)


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
    DOOM_W      = 640
    DOOM_H      = 400
    DOOM_ASPECT = DOOM_W / DOOM_H   # 1.6  (16:10)

    DEFAULT_GRID_W = 64
    DEFAULT_GRID_H = 40

    MAX_GRID_W = DOOM_W
    MAX_GRID_H = DOOM_H

    SO_NAME    = "libdoomgeneric.so"
    WAD_NAME   = "DOOM1.WAD"
    DIR_PREFIX = ".bsdoom_"

    # Key map using correct doomkeys.h constants (all single keycodes)
    KEY_MAP = {
        # Movement
        "UP":        [0xAD],        # KEY_UPARROW
        "DOWN":      [0xAF],        # KEY_DOWNARROW
        "TURN_L":    [0xAC],        # KEY_LEFTARROW
        "TURN_R":    [0xAE],        # KEY_RIGHTARROW
        "STRAFE_L":  [0xA0],        # KEY_STRAFE_L
        "STRAFE_R":  [0xA1],        # KEY_STRAFE_R
        # Actions
        "FIRE":      [0xA3],        # KEY_FIRE    (was wrong: 157/29 are evdev codes)
        "USE":       [0xA2],        # KEY_USE
        "RUN":       [0x80 + 0x36], # KEY_RSHIFT  (0xb6 = 182)
        # Navigation
        "ENTER":     [13],          # KEY_ENTER
        "ESCAPE":    [27],          # KEY_ESCAPE
        "MAP":       [9],           # KEY_TAB
        # Weapon slots 1-7 (ASCII digits)
        "WPN_1":     [ord('1')],
        "WPN_2":     [ord('2')],
        "WPN_3":     [ord('3')],
        "WPN_4":     [ord('4')],
        "WPN_5":     [ord('5')],
        "WPN_6":     [ord('6')],
        "WPN_7":     [ord('7')],
        # Automap zoom
        "ZOOM_IN":   [ord('+')],    # KEY_EQUALS / KEYP_PLUS
        "ZOOM_OUT":  [ord('-')],    # KEY_MINUS  / KEYP_MINUS
        # Pause
        "PAUSE":     [0xFF],        # KEY_PAUSE
        # F-keys (save/load/etc)
        "F1":        [0x80 + 0x3b],
        "F2":        [0x80 + 0x3c],
        "F3":        [0x80 + 0x3d],
        "F5":        [0x80 + 0x3f],
        "F6":        [0x80 + 0x40],
        "F7":        [0x80 + 0x41],
        "F9":        [0x80 + 0x43],
        "F10":       [0x80 + 0x44],
    }

    BTN_RELEASE_DELAY = 0.15   # seconds before synthesising a key-release event
    TICK_INTERVAL     = 0.028  # seconds between engine ticks (~35 Hz)

    OVERLAY_HISTORY = 60

    COLOR_RED    = (0.80, 0.15, 0.10)
    COLOR_GREEN  = (0.10, 0.60, 0.20)
    COLOR_BLUE   = (0.10, 0.25, 0.70)
    COLOR_DARK   = (0.08, 0.08, 0.08)
    COLOR_MID    = (0.18, 0.18, 0.18)
    COLOR_LIGHT  = (0.30, 0.30, 0.30)
    COLOR_TEXT   = (0.90, 0.90, 0.90)
    COLOR_DIM    = (0.50, 0.50, 0.50)
    COLOR_ACCENT = (0.85, 0.70, 0.10)


# ---------------------------------------------------------------------------
# Asset Cleanup & pure functions
# ---------------------------------------------------------------------------

def _get_audio_dir(app_py: str) -> str:
    """Returns the absolute path to the game's internal ba_data/sounds folder."""
    try:
        ba_data = os.path.abspath(os.path.join(app_py, os.pardir))
        
        sounds_dir = os.path.join(ba_data, "sounds")
        if os.path.exists(sounds_dir):
            return sounds_dir
            
        audio_dir = os.path.join(ba_data, "audio")
        if os.path.exists(audio_dir):
            return audio_dir
            
        return sounds_dir
    except Exception:
        return os.path.abspath(os.path.join(app_py, "sounds"))


def _sweep_stale_dirs(parent: str) -> None:
    try:
        for entry in os.listdir(parent):
            if entry.startswith(Const.DIR_PREFIX):
                rmtree(os.path.join(parent, entry), ignore_errors=True)
    except Exception:
        pass


def _sweep_audio_dir(audio_dir: str) -> None:
    """Clears out any .ogg files injected by previous BSDoom runs."""
    try:
        if os.path.exists(audio_dir):
            for entry in os.listdir(audio_dir):
                if entry.startswith("bsdoom_") and entry.endswith(".ogg"):
                    os.remove(os.path.join(audio_dir, entry))
    except Exception:
        pass


def _locate_on_disk(app_py: str, user_dir: str) -> tuple[str, str] | None:
    try:
        base = os.path.abspath(os.path.join(app_py, os.pardir))
    except Exception:
        base = os.path.abspath(user_dir)

    so_path = os.path.join(base, Const.SO_NAME)
    if not os.path.exists(so_path):
        return None

    for name in ("DOOM1.WAD", "doom1.wad", "DOOM.WAD", "doom.wad"):
        wad_path = os.path.join(base, name)
        if os.path.exists(wad_path):
            return os.path.abspath(so_path), os.path.abspath(wad_path)
    return None

def _make_pixel_array_type(w: int, h: int):
    return ctypes.c_uint32 * (w * h)


def _resolve_screenbuffer(lib: ctypes.CDLL, pixel_array_type):
    addr = ctypes.c_void_p.in_dll(lib, "DG_ScreenBuffer").value
    if not addr: return None
    return pixel_array_type.from_address(addr)


def _clamp_grid(gw: int, gh: int) -> tuple[int, int]:
    gw = max(1, min(gw, Const.MAX_GRID_W))
    gh = round(gw / Const.DOOM_ASPECT)
    gh = max(1, min(gh, Const.MAX_GRID_H))
    gw = round(gh * Const.DOOM_ASPECT)
    gw = max(1, min(gw, Const.MAX_GRID_W))
    return gw, gh


def _grid_from_width(gw: int) -> tuple[int, int]:
    return _clamp_grid(gw, round(gw / Const.DOOM_ASPECT))


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

    def on_activate(self) -> None:
        log("[AppMode] Activated.")
        classic_app_mode_activate()

        set_internal_music(None)
        for w in ('squad_button','menu_button'):
            bui.get_special_widget(w).delete()

        self._lib            = None
        self._screenbuf      = None
        self._frame_ready    = None
        self._c_argv         = None
        self._c_args_buffers = None
        self._timer          = None
        self._res_timer      = None
        self._release_timers = {}
        
        # Keep pointer to C function callback alive
        self._c_snd_cb       = None 

        self._grid_w           = Const.DEFAULT_GRID_W
        self._grid_h           = Const.DEFAULT_GRID_H
        self._pixels           = []
        self._indices          = []
        self._pixel_array_type = None

        self._overlay_enabled = False
        self._frame_count     = 0
        self._tick_history    = []
        self._last_fps_sample = datetime.now()
        self._overlay_timer   = None
        self._ov_container    = None
        self._ov_bars         = []

        self._opt_show_overlays = False
        self._opt_tick_hz       = 35
        self._opt_scale_mode    = "fit"

        self._adv_visible   = False
        self._adv_container = None
        
        self._load_root = None

        try:
            sw, sh = bui.get_virtual_screen_size()
            self.root = bui.containerwidget(size=(sw, sh), background=False, scale=1.0)
            self._build_main_menu(sw, sh)
        except Exception:
            log(f"[AppMode] Fatal error during activation:\n{format_exc()}")
            bui.screenmessage("BSDoom: UI crash. See bsdoom.log.", color=(1, 0, 0))


    def _build_main_menu(self, sw: float, sh: float) -> None:
        log("[Menu] Building main menu...")
        tex_w = bui.gettexture("white")

        bui.imagewidget(parent=self.root, position=(0, 0), size=(sw, sh), texture=tex_w, color=Const.COLOR_DARK, opacity=0.96)
        bui.imagewidget(parent=self.root, position=(0, sh - 6), size=(sw, 6), texture=tex_w, color=Const.COLOR_RED)

        bui.textwidget(parent=self.root, position=(sw / 2, sh - 80), size=(0, 0), text="DOOM", big=True, scale=3.2, color=Const.COLOR_RED, h_align="center", v_align="center", shadow=1.4, flatness=0.0)
        
        bui.textwidget(parent=self.root, position=(sw / 2, sh - 137), size=(0, 0), text="for Ballistica BombSquad", scale=0.72, color=Const.COLOR_DIM, h_align="center", v_align="center")
        bui.imagewidget(parent=self.root, position=(sw / 2 - 160, sh - 152), size=(320, 1), texture=tex_w, color=Const.COLOR_LIGHT, opacity=0.4)

        panel_w, panel_h = 360, 190
        panel_x = sw / 2 - panel_w / 2
        panel_y = sh / 2 - 25

        bui.imagewidget(parent=self.root, position=(panel_x, panel_y), size=(panel_w, panel_h), texture=tex_w, color=Const.COLOR_MID, opacity=0.92)
        bui.imagewidget(parent=self.root, position=(panel_x, panel_y + panel_h - 3), size=(panel_w, 3), texture=tex_w, color=Const.COLOR_ACCENT)

        bui.textwidget(parent=self.root, position=(sw / 2, panel_y + panel_h - 24), size=(0, 0), text="RENDER RESOLUTION", scale=0.58, color=Const.COLOR_ACCENT, h_align="center", v_align="center")

        bui.textwidget(parent=self.root, position=(panel_x + 28, panel_y + panel_h - 60), size=(0, 0), text="Grid Width", scale=0.62, color=Const.COLOR_TEXT, h_align="left", v_align="center")
        self._field_w = bui.textwidget(parent=self.root, position=(panel_x + 196, panel_y + panel_h - 78), size=(88, 36), text=str(self._grid_w), scale=0.78, color=Const.COLOR_TEXT, h_align="center", v_align="center", editable=True, padding=4, glow_type='uniform', allow_clear_button=False, on_return_press_call=self._on_res_commit)

        bui.textwidget(parent=self.root, position=(panel_x + 28, panel_y + panel_h - 100), size=(0, 0), text="Grid Height  (auto)", scale=0.62, color=Const.COLOR_DIM, h_align="left", v_align="center")
        self._field_h = bui.textwidget(parent=self.root, position=(panel_x + 196, panel_y + panel_h - 118), size=(88, 36), text=str(self._grid_h), scale=0.78, color=Const.COLOR_DIM, h_align="center", v_align="center", editable=False, padding=4)

        self._res_info = bui.textwidget(parent=self.root, position=(sw / 2, panel_y + panel_h - 128), size=(0, 0), text=self._res_info_str(), scale=0.52, color=Const.COLOR_DIM, h_align="center", v_align="center")

        presets = [(32, 20, "32×20"), (64, 40, "64×40"), (128, 80, "128×80")]
        slot_w  = panel_w / len(presets)
        for i, (pw, ph, lbl) in enumerate(presets):
            bui.buttonwidget(parent=self.root, position=(panel_x + 12 + i * slot_w, panel_y + 10), size=(slot_w - 24, 28), label=lbl, color=Const.COLOR_LIGHT, textcolor=Const.COLOR_TEXT, texture=tex_w, enable_sound=False, on_activate_call=lambda pw=pw, ph=ph: self._apply_preset(pw, ph))

        btn_y = panel_y - 70

        self._adv_btn = bui.buttonwidget(parent=self.root, position=(sw / 2 - 230, btn_y), size=(220, 50), label="Advanced Options", color=Const.COLOR_LIGHT, textcolor=Const.COLOR_DIM, texture=tex_w, enable_sound=False, on_activate_call=self._toggle_advanced)
        bui.buttonwidget(parent=self.root, position=(sw / 2 + 10, btn_y), size=(220, 50), label="LAUNCH DOOM", color=Const.COLOR_RED, textcolor=(1.0, 1.0, 1.0), texture=tex_w, enable_sound=False, on_activate_call=self._on_launch)
        bui.textwidget(parent=self.root, position=(sw / 2, 16), size=(0, 0), text="BSDoom  \u2022  BrotherBoard  \u2022  @BroBordd", scale=0.48, color=Const.COLOR_LIGHT, h_align="center", v_align="center")

        self._last_field_w_text = str(self._grid_w)
        self._res_timer = bui.AppTimer(0.01, self._check_res_update, repeat=True)

    def _check_res_update(self) -> None:
        if not self._field_w or not self._field_w.exists(): return
        try: txt = bui.textwidget(query=self._field_w)
        except Exception: return

        if txt != self._last_field_w_text:
            self._last_field_w_text = txt
            if not txt.strip(): return
            try: val = int(txt)
            except ValueError: return
            
            clamped_val = max(1, min(val, Const.MAX_GRID_W))
            if val != clamped_val:
                val = clamped_val
                bui.textwidget(edit=self._field_w, text=str(val))
                self._last_field_w_text = str(val)

            self._grid_w, self._grid_h = _grid_from_width(val)
            bui.textwidget(edit=self._field_h, text=str(self._grid_h))
            bui.textwidget(edit=self._res_info, text=self._res_info_str())

    def _res_info_str(self) -> str:
        gw, gh = self._grid_w, self._grid_h
        sx = Const.DOOM_W // gw
        sy = Const.DOOM_H // gh
        return f"{gw} \u00d7 {gh} cells  \u2022  1 cell = {sx}\u00d7{sy} px  \u2022  {gw * gh:,} widgets"

    def _apply_preset(self, gw: int, gh: int) -> None:
        try: bui.getsound('deek').play()
        except Exception: pass
        self._grid_w, self._grid_h = _clamp_grid(gw, gh)
        self._refresh_res_fields()
        self._last_field_w_text = str(self._grid_w)

    def _on_res_commit(self) -> None:
        try: bui.getsound('deek').play()
        except Exception: pass
        try: gw = int(bui.textwidget(query=self._field_w).strip())
        except Exception: gw = Const.DEFAULT_GRID_W
        gw = max(1, min(gw, Const.MAX_GRID_W))
        self._grid_w, self._grid_h = _grid_from_width(gw)
        self._refresh_res_fields()
        self._last_field_w_text = str(self._grid_w)

    def _refresh_res_fields(self) -> None:
        bui.textwidget(edit=self._field_w, text=str(self._grid_w))
        bui.textwidget(edit=self._field_h, text=str(self._grid_h))
        bui.textwidget(edit=self._res_info, text=self._res_info_str())

    def _build_advanced_panel(self, sw: float, sh: float, panel_y: float) -> None:
        adv_w, adv_h = 460, 160
        adv_x = sw / 2 - adv_w / 2
        btn_y = panel_y - 70
        adv_y = btn_y - adv_h - 15
        tex_w = bui.gettexture("white")

        self._adv_container = bui.containerwidget(parent=self.root, position=(adv_x, adv_y), size=(adv_w, adv_h), background=False)
        bui.imagewidget(parent=self._adv_container, position=(0, 0), size=(adv_w, adv_h), texture=tex_w, color=Const.COLOR_MID, opacity=0.88)
        bui.imagewidget(parent=self._adv_container, position=(0, adv_h - 3), size=(adv_w, 3), texture=tex_w, color=Const.COLOR_BLUE)
        bui.textwidget(parent=self._adv_container, position=(adv_w / 2, adv_h - 20), size=(0, 0), text="ADVANCED OPTIONS", scale=0.56, color=(0.55, 0.70, 1.0), h_align="center", v_align="center")

        def _row(y, label, field_widget_fn, btn_widget_fn=None):
            bui.textwidget(parent=self._adv_container, position=(18, y + 17), size=(0, 0), text=label, scale=0.58, color=Const.COLOR_TEXT, h_align="left", v_align="center")
            return field_widget_fn(y), (btn_widget_fn(y) if btn_widget_fn else None)

        row_y = adv_h - 58
        gap   = 42

        def _hz_field(y): return bui.textwidget(parent=self._adv_container, position=(adv_w - 110, y), size=(88, 34), text=str(self._opt_tick_hz), scale=0.68, color=Const.COLOR_TEXT, h_align="center", v_align="center", editable=True, padding=4, glow_type='uniform', allow_clear_button=False)
        self._field_hz, _ = _row(row_y, "Engine tick rate (Hz)", _hz_field)

        row_y -= gap

        def _scale_lbl(y): return bui.textwidget(parent=self._adv_container, position=(adv_w - 160, y + 17), size=(0, 0), text=self._opt_scale_mode.upper(), scale=0.58, color=Const.COLOR_ACCENT, h_align="center", v_align="center")
        def _scale_btn(y): return bui.buttonwidget(parent=self._adv_container, position=(adv_w - 110, y), size=(88, 34), label="Toggle", color=Const.COLOR_LIGHT, textcolor=Const.COLOR_TEXT, texture=tex_w, enable_sound=False, on_activate_call=self._toggle_scale_mode)
        self._scale_mode_lbl, _ = _row(row_y, "Scale mode", _scale_lbl, _scale_btn)

        row_y -= gap

        def _ov_lbl(y): return bui.textwidget(parent=self._adv_container, position=(adv_w - 160, y + 17), size=(0, 0), text="ON" if self._opt_show_overlays else "OFF", scale=0.58, color=Const.COLOR_GREEN if self._opt_show_overlays else Const.COLOR_DIM, h_align="center", v_align="center")
        def _ov_btn(y): return bui.buttonwidget(parent=self._adv_container, position=(adv_w - 110, y), size=(88, 34), label="Toggle", color=Const.COLOR_LIGHT, textcolor=Const.COLOR_TEXT, texture=tex_w, enable_sound=False, on_activate_call=self._toggle_overlays_opt)
        self._overlay_lbl, _ = _row(row_y, "Live overlays  (FPS, tick ms, bar graph)", _ov_lbl, _ov_btn)

    def _toggle_advanced(self) -> None:
        try: bui.getsound('deek').play()
        except Exception: pass
        self._adv_visible = not self._adv_visible
        if self._adv_visible:
            bui.buttonwidget(edit=self._adv_btn, color=Const.COLOR_MID, textcolor=Const.COLOR_ACCENT)
            sw, sh = bui.get_virtual_screen_size()
            self._build_advanced_panel(sw, sh, sh / 2 - 25)
        else:
            bui.buttonwidget(edit=self._adv_btn, color=Const.COLOR_LIGHT, textcolor=Const.COLOR_DIM)
            if self._adv_container and self._adv_container.exists():
                try: self._opt_tick_hz = max(1, min(int(bui.textwidget(query=self._field_hz).strip()), 120))
                except Exception: pass
                self._adv_container.delete()
                self._adv_container = None

    def _toggle_scale_mode(self) -> None:
        try: bui.getsound('deek').play()
        except Exception: pass
        self._opt_scale_mode = "fill" if self._opt_scale_mode == "fit" else "fit"
        bui.textwidget(edit=self._scale_mode_lbl, text=self._opt_scale_mode.upper())

    def _toggle_overlays_opt(self) -> None:
        try: bui.getsound('deek').play()
        except Exception: pass
        self._opt_show_overlays = not self._opt_show_overlays
        on = self._opt_show_overlays
        bui.textwidget(edit=self._overlay_lbl, text="ON" if on else "OFF", color=Const.COLOR_GREEN if on else Const.COLOR_DIM)

    def _on_launch(self) -> None:
        try: bui.getsound('deek').play()
        except Exception: pass
        self._res_timer = None 
        self._on_res_commit()

        if self._adv_visible and self._adv_container and self._adv_container.exists():
            try: self._opt_tick_hz = max(1, min(int(bui.textwidget(query=self._field_hz).strip()), 120))
            except Exception: pass

        self._overlay_enabled = self._opt_show_overlays

        if self.root.exists(): self.root.delete()

        sw, sh = bui.get_virtual_screen_size()
        
        # 1. Build the game rendering layer
        self.root = bui.containerwidget(size=(sw, sh), background=False, scale=1.0)
        self._build_game_ui(sw, sh)

        # 2. Build the blocking loading layer on top
        self._build_loading_overlay(sw, sh)

        # Cache paths before we thread, just to be thread-safe
        app_py = os.path.abspath(bui.app.env.python_directory_app)
        usr_dir = os.path.abspath(bui.app.env.python_directory_user)

        # 3. Start extraction sequence in the background
        Thread(target=self._extraction_thread_main, args=(app_py, usr_dir), daemon=True).start()

    def _build_loading_overlay(self, sw: float, sh: float) -> None:
        tex_w = bui.gettexture("white")
        self._load_root = bui.containerwidget(parent=self.root, size=(sw, sh), background=False)
        
        bui.imagewidget(parent=self._load_root, position=(0, 0), size=(sw, sh), texture=tex_w, color=(0, 0, 0), opacity=0.45)
        
        panel_w, panel_h = 440, 170
        px, py = sw / 2 - panel_w / 2, sh / 2 - panel_h / 2
        
        bui.imagewidget(parent=self._load_root, position=(px, py), size=(panel_w, panel_h), texture=tex_w, color=Const.COLOR_MID, opacity=0.95)
        bui.imagewidget(parent=self._load_root, position=(px, py + panel_h - 4), size=(panel_w, 4), texture=tex_w, color=Const.COLOR_ACCENT)
        
        bui.textwidget(parent=self._load_root, position=(px + panel_w / 2, py + panel_h - 35), size=(0, 0), text="EXTRACTING ASSETS", scale=0.7, color=Const.COLOR_ACCENT, h_align="center", v_align="center")
        self._load_log = bui.textwidget(parent=self._load_root, position=(px + panel_w / 2, py + 80), size=(0, 0), text="Preparing...", scale=0.55, color=Const.COLOR_TEXT, h_align="center", v_align="center")
        
        bar_w, bar_h = 380, 14
        bx, by = px + (panel_w - bar_w) / 2, py + 35
        bui.imagewidget(parent=self._load_root, position=(bx, by), size=(bar_w, bar_h), texture=tex_w, color=Const.COLOR_DARK)
        self._load_bar = bui.imagewidget(parent=self._load_root, position=(bx, by), size=(0, bar_h), texture=tex_w, color=Const.COLOR_GREEN)
        self._load_bar_w = bar_w

    def _update_loading_ui(self, pct: float, msg: str) -> None:
        if not self._load_root or not self._load_root.exists(): return
        bui.textwidget(edit=self._load_log, text=msg)
        bui.imagewidget(edit=self._load_bar, size=(self._load_bar_w * max(0.0, min(1.0, pct)), 14))
        log(f"[Extract] {msg}")

    def _extraction_thread_main(self, app_py: str, user_dir: str) -> None:
        """Runs in background thread to unblock UI during massive base64 decodes."""
        def set_prog(p, m):
            bui.pushcall(lambda pct=p, msg=m: self._update_loading_ui(pct, msg), from_other_thread=True)
            
        try:
            if _ASSET_SO is None:
                set_prog(0.5, "Searching disk for DOOM assets...")
                res = _locate_on_disk(app_py, user_dir)
                if not res:
                    raise FileNotFoundError("Could not find DOOM binaries. Run pack_bsdoom.py.")
                set_prog(1.0, "Ready.")
                bui.pushcall(lambda s=res[0], w=res[1]: self._finalize_launch(s, w), from_other_thread=True)
                return

            set_prog(0.1, "Cleaning up old data...")
            try:
                parent = os.path.abspath(os.path.join(app_py, os.pardir))
            except Exception:
                parent = user_dir

            _sweep_stale_dirs(parent)
            if user_dir != parent:
                _sweep_stale_dirs(user_dir)

            extract_dir = os.path.join(parent, f"{Const.DIR_PREFIX}{uuid4().hex}")
            os.makedirs(extract_dir, exist_ok=True)
            reg_trap(rmtree, extract_dir, True)

            so_path  = os.path.join(extract_dir, Const.SO_NAME)
            wad_path = os.path.join(extract_dir, Const.WAD_NAME)

            set_prog(0.2, "Decoding engine binary...")
            with open(so_path, "wb") as fh:
                fh.write(b85decode(_ASSET_SO))
            os.chmod(so_path, 0o755)

            set_prog(0.4, "Decoding DOOM1.WAD... (This takes a moment)")
            with open(wad_path, "wb") as fh:
                fh.write(b85decode(_ASSET_WAD))

            if _ASSET_SOUNDS is not None:
                set_prog(0.7, "Extracting audio assets...")
                audio_dir = _get_audio_dir(app_py)
                _sweep_audio_dir(audio_dir)
                os.makedirs(audio_dir, exist_ok=True)

                zip_path = os.path.join(extract_dir, "sounds.zip")
                with open(zip_path, "wb") as fh:
                    fh.write(b85decode(_ASSET_SOUNDS))

                set_prog(0.85, "Installing audio assets...")
                with ZipFile(zip_path, 'r') as z:
                    z.extractall(audio_dir)

                reg_trap(_sweep_audio_dir, audio_dir)

            set_prog(1.0, "Booting DOOM Engine...")
            bui.pushcall(lambda s=so_path, w=wad_path: self._finalize_launch(s, w), from_other_thread=True)

        except Exception as e:
            trace = format_exc()
            bui.pushcall(lambda m=str(e), t=trace: self._on_extraction_failed(m, t), from_other_thread=True)

    def _on_extraction_failed(self, err_msg: str, trace: str) -> None:
        log(f"[Engine] Extraction failed:\n{trace}")
        bui.screenmessage(f"BSDoom Init Error: {err_msg}", color=(1, 0, 0))
        if self._load_root and self._load_root.exists():
            self._load_root.delete()

    def _finalize_launch(self, so_path: str, wad_path: str) -> None:
        """Called back onto the main thread once extraction is done."""
        if self._load_root and self._load_root.exists():
            self._load_root.delete()
        self._load_root = None
        
        if self._start_engine(so_path, wad_path):
            interval = 1.0 / self._opt_tick_hz
            self._timer = bui.AppTimer(interval, self._tick, repeat=True)
            if self._overlay_enabled:
                sw, sh = bui.get_virtual_screen_size()
                self._build_overlay(sw, sh)
                self._overlay_timer = bui.AppTimer(0.25, self._update_overlay, repeat=True)
        else:
            bui.screenmessage("BSDoom: Engine failed to start.", color=(1, 0, 0))

    def _build_game_ui(self, sw: float, sh: float) -> None:
        tex_w = bui.gettexture("white")
        gw, gh = self._grid_w, self._grid_h

        scale = max(sw / Const.DOOM_W, sh / Const.DOOM_H) if self._opt_scale_mode == "fill" else min(sw / Const.DOOM_W, sh / Const.DOOM_H) * 1.05

        cell_w, cell_h = scale * (Const.DOOM_W / gw), scale * (Const.DOOM_H / gh)
        ox, oy = (sw - cell_w * gw) / 2.0, (sh - cell_h * gh) / 2.0
        step_x, step_y = Const.DOOM_W // gw, Const.DOOM_H // gh

        self._pixel_array_type = _make_pixel_array_type(Const.DOOM_W, Const.DOOM_H)
        self._pixels, self._indices = [], []

        for gy in range(gh):
            doom_y = gy * step_y
            for gx_i in range(gw):
                self._indices.append(doom_y * Const.DOOM_W + gx_i * step_x)
                self._pixels.append(bui.imagewidget(parent=self.root, size=(cell_w + 1.0, cell_h + 1.0), position=(ox + cell_w * gx_i, oy + cell_h * (gh - 1 - gy)), texture=tex_w, color=(0, 0, 0)))

        self._build_buttons(sw, sh)

    def _start_engine(self, so_path: str, wad_path: str) -> bool:
        try:
            lib = ctypes.CDLL(so_path)
            lib.doomgeneric_Create.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_char_p)]
            lib.doomgeneric_Create.restype = None
            lib.doomgeneric_Tick.argtypes  = []
            lib.doomgeneric_Tick.restype   = None
            
            # FIX: first arg is unsigned char in C, must use c_ubyte — not c_int
            # Using c_int caused keycode corruption for values >= 128 (FIRE=0xa3, etc.)
            lib.bs_add_key.argtypes        = [ctypes.c_ubyte, ctypes.c_int]
            lib.bs_add_key.restype         = None

            SOUND_CB_TYPE = ctypes.CFUNCTYPE(None, ctypes.c_char_p)
            self._c_snd_cb = SOUND_CB_TYPE(self._on_sound)
            lib.bs_set_sound_callback.argtypes = [SOUND_CB_TYPE]
            lib.bs_set_sound_callback.restype = None
            lib.bs_set_sound_callback(self._c_snd_cb)

            self._frame_ready = ctypes.c_int.in_dll(lib, "bs_frame_ready")
            self._lib = lib

            extract_dir = os.path.dirname(wad_path)
            
            args = [b"doom", b"-iwad", Const.WAD_NAME.encode()]
            self._c_args_buffers = [ctypes.create_string_buffer(a) for a in args]
            argc = len(self._c_args_buffers)
            
            c_char_p_array = (ctypes.c_char_p * (argc + 1))()
            for i, buf in enumerate(self._c_args_buffers):
                c_char_p_array[i] = ctypes.cast(buf, ctypes.c_char_p)
            c_char_p_array[argc] = None
            
            self._c_argv = c_char_p_array

            prev_cwd = os.getcwd()
            os.chdir(extract_dir)
            lib.doomgeneric_Create(argc, self._c_argv)
            os.chdir(prev_cwd)

            self._screenbuf = _resolve_screenbuffer(lib, self._pixel_array_type)
            if self._screenbuf is None: return False
            return True
        except Exception:
            log(f"[Engine] Fatal error during initialisation:\n{format_exc()}")
            bui.screenmessage("BSDoom engine fatal. See bsdoom.log.", color=(1, 0, 0))
            return False

    def _on_sound(self, name_bytes: bytes) -> None:
        """Called directly by DOOM engine's I_StartSound via ctypes!"""
        if not name_bytes:
            return
        try:
            name = name_bytes.decode('utf-8').lower()
            bui.getsound(f"bsdoom_ds{name}").play()
        except Exception:
            pass

    def _on_input(self, key: str, action: str) -> None:
        if not self._lib: return
        doom_keys = Const.KEY_MAP.get(key, [])
        state = 1 if action == "press" else 0
        for dk in doom_keys:
            self._lib.bs_add_key(dk, state)

    def _btn(self, parent, pos: tuple, size: tuple, label: str, key: str,
             color: tuple = (0.25, 0.25, 0.25), repeat: bool = False) -> None:
        def _tap():
            self._on_input(key, "press")
            def _release():
                self._on_input(key, "release")
                self._release_timers.pop(key, None)
            self._release_timers[key] = bui.AppTimer(Const.BTN_RELEASE_DELAY, _release)

        bui.buttonwidget(parent=parent, position=pos, size=size, label=label,
                         color=color, textcolor=(1, 1, 1),
                         texture=bui.gettexture("white"),
                         enable_sound=False, repeat=repeat,
                         on_activate_call=_tap)

    def _build_buttons(self, sw: float, sh: float) -> None:
        """
        Layout:
          TOP-LEFT:      [Map] [Run] [Pause]  (horizontal)
          LEFT side:     D-pad + USE  (bottom-left)
          RIGHT side:    Aim pad + FIRE  (bottom-right, unchanged)
          FAR-RIGHT col: F-keys + Esc  (vertical, top-to-bottom, top btn lowered by bs/2)
          RIGHT-MID col: Weapons 1-7 + Enter  (vertical, just left of f-key col)
        """
        tex_w  = bui.gettexture("white")
        bs     = 68    # base button size
        gap    = 8
        margin = 20

        # ── colour palette ──────────────────────────────────────────────────
        col_move   = (0.10, 0.22, 0.38)
        col_aim    = (0.38, 0.12, 0.10)
        col_fire   = (0.75, 0.08, 0.08)
        col_use    = (0.10, 0.45, 0.18)
        col_run    = (0.40, 0.28, 0.06)
        col_util   = (0.18, 0.18, 0.22)
        col_wpn    = (0.22, 0.18, 0.28)
        col_map    = (0.14, 0.14, 0.14)
        col_esc    = (0.28, 0.10, 0.10)
        col_pause  = (0.20, 0.20, 0.14)
        col_enter  = (0.10, 0.38, 0.18)

        # ── TOP-LEFT: Map / Run / Pause ─────────────────────────────────────
        top_y = sh - margin - bs
        tl = bui.containerwidget(parent=self.root, background=False,
                                  size=(bs * 3 + gap * 2, bs),
                                  position=(margin, top_y))
        self._btn(tl, (0,          0), (bs, bs), "Map", "MAP",   col_map)
        self._btn(tl, (bs + gap,   0), (bs, bs), "Run", "RUN",   col_run, repeat=True)
        self._btn(tl, ((bs+gap)*2, 0), (bs, bs), "||",  "PAUSE", col_pause)

        # ── BOTTOM-LEFT: Movement D-pad (unchanged) ─────────────────────────
        dpad_size = bs * 3 + gap * 2
        dpad = bui.containerwidget(parent=self.root, background=False,
                                    size=(dpad_size, dpad_size),
                                    position=(margin, margin))
        self._btn(dpad, (bs + gap,   (bs+gap)*2), (bs, bs), "Fwd",  "UP",       col_move, repeat=True)
        self._btn(dpad, (bs + gap,   0),           (bs, bs), "Back", "DOWN",     col_move, repeat=True)
        self._btn(dpad, (0,          bs + gap),    (bs, bs), "<St",  "STRAFE_L", col_move, repeat=True)
        self._btn(dpad, ((bs+gap)*2, bs + gap),    (bs, bs), "St>",  "STRAFE_R", col_move, repeat=True)
        self._btn(dpad, (bs + gap,   bs + gap),    (bs, bs), "USE",  "USE",      col_use)

        # ── BOTTOM-RIGHT: Aim pad + Fire (unchanged) ────────────────────────
        fire_w = bs * 2 + gap
        # Push aim pad left to make room for the two right-side vertical columns
        wsz  = 52   # weapon button size
        wgap = 6
        col_w = wsz + gap          # width of one vertical column
        aim_x = sw - margin - fire_w - col_w * 2 - gap * 2
        aim_pad = bui.containerwidget(parent=self.root, background=False,
                                       size=(fire_w, bs * 2 + gap + 10),
                                       position=(aim_x, margin))
        self._btn(aim_pad, (0,        bs + gap + 10), (bs, bs), "<Aim", "TURN_L", col_aim, repeat=True)
        self._btn(aim_pad, (bs + gap, bs + gap + 10), (bs, bs), "Aim>", "TURN_R", col_aim, repeat=True)
        self._btn(aim_pad, (0,        0),              (fire_w, bs), "FIRE", "FIRE", col_fire, repeat=True)

        # ── RIGHT-MID vertical column: Weapons 1-7 + Enter ──────────────────
        # Positioned just left of the f-key column.
        # Starts from top (sh - margin - bs/2) going downward.
        wkeys = ["WPN_1","WPN_2","WPN_3","WPN_4","WPN_5","WPN_6","WPN_7"]
        wlbls = ["1 Fist","2 Pist","3 Shot","4 Chn","5 Rok","6 Plas","7 BFG"]
        wcol_x = sw - margin - col_w * 2 - gap

        # Top of column lowered by bs/2 from the very top margin
        wcol_top = sh - margin - bs // 2
        for i, (wk, wl) in enumerate(zip(wkeys, wlbls)):
            y = wcol_top - i * (wsz + wgap)
            self._btn(self.root, (wcol_x, y), (wsz, wsz), wl, wk, col_wpn)

        # Enter below weapons
        enter_y = wcol_top - len(wkeys) * (wsz + wgap) - gap
        self._btn(self.root, (wcol_x, enter_y), (wsz, wsz + 10), "ENTER", "ENTER", col_enter)

        # ── FAR-RIGHT vertical column: F-keys + Esc ─────────────────────────
        # [Help(F1)] [Save(F2)] [Load(F3)] [Gamma(F5)] [Esc]
        # Top button lowered by bs/2 from screen top.
        f_labels = [("Help","F1"),("Save","F2"),("Load","F3"),("Gamma","F5"),("Esc","ESCAPE")]
        fcol_x = sw - margin - col_w + gap // 2
        fcol_top = sh - margin - bs // 2
        for i, (lbl, key) in enumerate(f_labels):
            y = fcol_top - i * (wsz + wgap)
            c = col_esc if key == "ESCAPE" else col_util
            self._btn(self.root, (fcol_x, y), (wsz, wsz), lbl, key, c)

    def _tick(self) -> None:
        if not self._lib or not self.root.exists():
            self._timer = None
            return

        try:
            t0 = datetime.now()
            self._lib.doomgeneric_Tick()
            tick_ms = (datetime.now() - t0).total_seconds() * 1000.0

            if not self._frame_ready.value: return
            self._frame_ready.value = 0
            self._frame_count += 1

            buf = self._screenbuf
            if buf is None: return

            indices, pixels, edit = self._indices, self._pixels, bui.imagewidget

            for i in range(len(pixels)):
                if not pixels[i].exists(): return
                val = buf[indices[i]]
                edit(edit=pixels[i], color=(((val >> 16) & 0xFF) / 255.0, ((val >> 8) & 0xFF) / 255.0, (val & 0xFF) / 255.0))

            if self._overlay_enabled:
                self._tick_history.append(tick_ms)
                if len(self._tick_history) > Const.OVERLAY_HISTORY: self._tick_history.pop(0)

        except Exception:
            self._timer = None

    def _build_overlay(self, sw: float, sh: float) -> None:
        tex_w = bui.gettexture("white")
        ov_w, ov_h, ov_x, ov_y = 240, 168, 10, sh - 168 - 10

        self._ov_container = bui.containerwidget(parent=self.root, position=(ov_x, ov_y), size=(ov_w, ov_h), background=False)
        bui.imagewidget(parent=self._ov_container, position=(0, 0), size=(ov_w, ov_h), texture=tex_w, color=(0, 0, 0), opacity=0.68)
        bui.imagewidget(parent=self._ov_container, position=(0, ov_h - 2), size=(ov_w, 2), texture=tex_w, color=Const.COLOR_GREEN)
        bui.textwidget(parent=self._ov_container, position=(ov_w / 2, ov_h - 14), size=(0, 0), text="DIAGNOSTICS", scale=0.48, color=Const.COLOR_GREEN, h_align="center", v_align="center")

        lx = 10
        self._ov_fps = bui.textwidget(parent=self._ov_container, position=(lx, ov_h - 34), size=(0, 0), text="FPS: --", scale=0.55, color=Const.COLOR_TEXT, h_align="left", v_align="center")
        self._ov_tick_avg = bui.textwidget(parent=self._ov_container, position=(lx, ov_h - 52), size=(0, 0), text="Tick avg: -- ms", scale=0.55, color=Const.COLOR_TEXT, h_align="left", v_align="center")
        self._ov_tick_max = bui.textwidget(parent=self._ov_container, position=(lx, ov_h - 70), size=(0, 0), text="Tick max: -- ms", scale=0.55, color=Const.COLOR_TEXT, h_align="left", v_align="center")
        self._ov_frames = bui.textwidget(parent=self._ov_container, position=(lx, ov_h - 88), size=(0, 0), text="Frames: 0", scale=0.55, color=Const.COLOR_TEXT, h_align="left", v_align="center")
        self._ov_grid_lbl = bui.textwidget(parent=self._ov_container, position=(lx, ov_h - 106), size=(0, 0), text=f"Grid: {self._grid_w}\u00d7{self._grid_h}  ({len(self._pixels)} widgets)", scale=0.50, color=Const.COLOR_DIM, h_align="left", v_align="center")

        bar_count, bar_gap = 30, 1
        bar_w = (ov_w - 20) / bar_count - bar_gap
        self._ov_bars, self._ov_bar_w, self._ov_graph_h, self._ov_bar_count = [], bar_w, 40, bar_count

        for i in range(bar_count):
            self._ov_bars.append(bui.imagewidget(parent=self._ov_container, position=(10 + i * (bar_w + bar_gap), 4), size=(bar_w, 2), texture=tex_w, color=Const.COLOR_LIGHT))

    def _update_overlay(self) -> None:
        if not self._overlay_enabled or not self._ov_bars: return
        now = datetime.now()
        elapsed = (now - self._last_fps_sample).total_seconds()
        
        if elapsed >= 0.5:
            fps = self._frame_count / elapsed if elapsed > 0 else 0.0
            self._frame_count, self._last_fps_sample = 0, now
        else: fps = 0.0

        history = self._tick_history
        avg_tick = sum(history) / len(history) if history else 0.0
        max_tick = max(history) if history else 0.0
        fps_color = Const.COLOR_GREEN if fps >= 28 else Const.COLOR_ACCENT if fps >= 15 else Const.COLOR_RED

        try:
            bui.textwidget(edit=self._ov_fps, text=f"FPS: {fps:.1f}", color=fps_color)
            bui.textwidget(edit=self._ov_tick_avg, text=f"Tick avg: {avg_tick:.1f} ms")
            bui.textwidget(edit=self._ov_tick_max, text=f"Tick max: {max_tick:.1f} ms")
            bui.textwidget(edit=self._ov_frames, text=f"Frames rendered: {len(history)}")

            window, peak = history[-self._ov_bar_count:], max(max(history[-self._ov_bar_count:]) if history[-self._ov_bar_count:] else 1.0, 1.0)
            for i, bar in enumerate(self._ov_bars):
                if i < len(window):
                    ms = window[i]
                    bui.imagewidget(edit=bar, size=(self._ov_bar_w, max(2.0, min(ms / peak, 1.0) * self._ov_graph_h)), color=Const.COLOR_GREEN if ms < 20 else Const.COLOR_ACCENT if ms < 40 else Const.COLOR_RED)
                else: bui.imagewidget(edit=bar, size=(self._ov_bar_w, 2), color=Const.COLOR_LIGHT)
        except Exception: pass

    def on_deactivate(self) -> None:
        log("[AppMode] Deactivated.")
        self._timer = self._res_timer = self._overlay_timer = self._c_snd_cb = None
        if self.root and self.root.exists(): self.root.delete()

# brobord collide grass
# ba_meta require api 9
# ba_meta export babase.Plugin
class AppModeLoader(bui.Plugin): pass

# ---------------------------------------------------------------------------

_ASSET_SO = None
_ASSET_WAD = None
_ASSET_SOUNDS = None
