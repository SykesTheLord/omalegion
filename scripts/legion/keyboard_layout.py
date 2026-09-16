"""Physical keyboard layout and key labels for the per-key lighting editor.

Two separate questions:

* Which physical format the keyboard is (ANSI, ISO or JIS). This decides
  where keys are and how big they are, and is read from the keyboard itself:
  ISO boards report keycode 0xA8 and JIS boards 0xA9 (the same test
  LenovoLegionToolkit uses). Only if the keyboard can't be read is it guessed
  from the system layout.
* What is printed on each key. This follows the keyboard layout the system is
  using (Hyprland's active layout, else localectl), resolved through
  libxkbcommon, so a Danish layout shows Æ Ø Å and ' where a US layout shows
  ; [ ' and \\.

Key positions and sizes were worked out from LenovoLegionToolkit's ANSI, ISO
and JIS Spectrum keyboard layouts. They're stored in LenovoLegionToolkit's
own pixel grid (a standard key is a 36px slot) and converted to key units.
"""

from __future__ import annotations

import ctypes
import json

from . import state
from .log import get_logger
from .sysfs import run_cmd

log = get_logger("layout")

SLOT = 36.0  # pixels per key unit in the source layouts

_F = 28  # function row height
_R1, _R2, _R3, _R4, _R5, _R6 = 28, 64, 100, 136, 172, 208

# code: (name, xkb key name, x, y, width, height) in source pixels. ISO is the
# base; ANSI and JIS are expressed as changes to it below.
_ISO: dict[int, tuple[str, str, int, int, int, int]] = {
    0x01: ("esc", "ESC", 0, 0, 32, _F),
    **{0x01 + i: (f"f{i}", f"FK{i:02d}", 32 * i, 0, 32, _F) for i in range(1, 13)},
    0x0E: ("insert", "INS", 416, 0, 32, _F),
    0x0F: ("prtsc", "PRSC", 448, 0, 32, _F),
    0x10: ("delete", "DELE", 480, 0, 36, _F),
    0x11: ("home", "HOME", 516, 0, 36, _F),
    0x12: ("end", "END", 552, 0, 36, _F),
    0x13: ("pgup", "PGUP", 588, 0, 36, _F),
    0x14: ("pgdn", "PGDN", 624, 0, 36, _F),

    0x16: ("grave", "TLDE", 0, _R1, 28, 36),
    **{0x16 + i: (str(i % 10), f"AE{i:02d}", 28 + 36 * (i - 1), _R1, 36, 36) for i in range(1, 11)},
    0x21: ("minus", "AE11", 388, _R1, 36, 36),
    0x22: ("equals", "AE12", 424, _R1, 36, 36),
    0x38: ("backspace", "BKSP", 460, _R1, 56, 36),
    0x26: ("numlock", "NMLK", 516, _R1, 36, 36),
    0x27: ("numdiv", "KPDV", 552, _R1, 36, 36),
    0x28: ("nummul", "KPMU", 588, _R1, 36, 36),
    0x29: ("numsub", "KPSU", 624, _R1, 36, 36),

    0x40: ("tab", "TAB", 0, _R2, 48, 36),
    **{code: (letter, f"AD{i:02d}", 48 + 36 * (i - 1), _R2, 36, 36)
       for i, (code, letter) in enumerate(zip(range(0x42, 0x4C), "qwertyuiop"), start=1)},
    0x4C: ("lbracket", "AD11", 408, _R2, 36, 36),
    0x4D: ("rbracket", "AD12", 444, _R2, 40, 36),
    0x77: ("enter", "RTRN", 484, _R2, 32, 72),
    0x4F: ("num7", "KP7", 516, _R2, 36, 36),
    0x50: ("num8", "KP8", 552, _R2, 36, 36),
    0x51: ("num9", "KP9", 588, _R2, 36, 36),
    0x68: ("numadd", "KPAD", 624, _R2, 36, 72),

    0x55: ("caps", "CAPS", 0, _R3, 60, 36),
    **{code: (letter, f"AC{i:02d}", 60 + 36 * (i - 1), _R3, 36, 36)
       for i, (code, letter) in enumerate(
           zip((0x6D, 0x6E, 0x58, 0x59, 0x5A, 0x71, 0x72, 0x5B, 0x5C), "asdfghjkl"), start=1)},
    0x5D: ("semicolon", "AC10", 384, _R3, 36, 36),
    0x5F: ("quote", "AC11", 420, _R3, 36, 36),
    0xA8: ("iso_hash", "BKSL", 456, _R3, 28, 36),
    0x79: ("num4", "KP4", 516, _R3, 36, 36),
    0x7B: ("num5", "KP5", 552, _R3, 36, 36),
    0x7C: ("num6", "KP6", 588, _R3, 36, 36),

    0x6A: ("lshift", "LFSH", 0, _R4, 42, 36),
    0x4E: ("lsgt", "LSGT", 42, _R4, 36, 36),
    **{code: (letter, f"AB{i:02d}", 78 + 36 * (i - 1), _R4, 36, 36)
       for i, (code, letter) in enumerate(
           zip((0x82, 0x83, 0x6F, 0x70, 0x87, 0x88, 0x73), "zxcvbnm"), start=1)},
    0x74: ("comma", "AB08", 330, _R4, 36, 36),
    0x75: ("period", "AB09", 366, _R4, 36, 36),
    0x76: ("slash", "AB10", 402, _R4, 36, 36),
    0x8D: ("rshift", "RTSH", 438, _R4, 78, 36),
    0x8E: ("num1", "KP1", 516, _R4, 36, 36),
    0x90: ("num2", "KP2", 552, _R4, 36, 36),
    0x92: ("num3", "KP3", 588, _R4, 36, 36),
    0xA7: ("numenter", "KPEN", 624, _R4, 36, 72),

    0x7F: ("lctrl", "LCTL", 0, _R5, 42, 36),
    0x80: ("fn", "FN", 42, _R5, 36, 36),
    0x96: ("super", "LWIN", 78, _R5, 36, 36),
    0x97: ("lalt", "LALT", 114, _R5, 36, 36),
    0x98: ("space", "SPCE", 150, _R5, 180, 36),
    0x9A: ("ralt", "RALT", 330, _R5, 36, 36),
    0x9B: ("rctrl", "RCTL", 366, _R5, 36, 36),
    0x9D: ("up", "UP", 438, _R5, 36, 36),
    0xA3: ("num0", "KP0", 516, _R5, 72, 36),
    0xA5: ("numdot", "KPDL", 588, _R5, 36, 36),

    0x9C: ("left", "LEFT", 402, _R6, 36, 36),
    0x9F: ("down", "DOWN", 438, _R6, 36, 36),
    0xA1: ("right", "RGHT", 474, _R6, 36, 36),
}

# ANSI: no ISO key or <> key; 0x4E is backslash above a wide Enter, and Left
# Shift is full width.
_ANSI_CHANGES = {
    0xA8: None,
    0x4D: ("rbracket", "AD12", 444, _R2, 36, 36),
    0x4E: ("backslash", "BKSL", 480, _R2, 36, 36),
    0x77: ("enter", "RTRN", 456, _R3, 60, 36),
    0x6A: ("lshift", "LFSH", 0, _R4, 78, 36),
}

# JIS: yen key beside a narrower Backspace, @ and [ on the Q row, ] beside
# Enter, and conversion keys around a shorter space bar. No Right Alt.
_JIS_CHANGES = {
    0xA8: ("yen", "AE13", 460, _R1, 28, 36),
    0x38: ("backspace", "BKSP", 488, _R1, 28, 36),
    0x60: ("at", "AD11", 408, _R2, 36, 36),
    0x4C: ("lbracket", "AD12", 444, _R2, 40, 36),
    0x4D: ("rbracket", "BKSL", 456, _R3, 28, 36),
    0xA9: ("muhenkan", "NFER", 150, _R5, 36, 36),
    0x98: ("space", "SPCE", 186, _R5, 108, 36),
    0xAA: ("henkan", "XFER", 294, _R5, 36, 36),
    0xAB: ("kana", "HKTG", 330, _R5, 36, 36),
    0x9A: None,
}

ISO_KEY = 0xA8
JIS_KEY = 0xA9


def _geometry(fmt: str) -> dict[int, tuple[str, str, int, int, int, int]]:
    keys = dict(_ISO)
    changes = {"ansi": _ANSI_CHANGES, "jis": _JIS_CHANGES}.get(fmt, {})
    for code, spec in changes.items():
        if spec is None:
            keys.pop(code, None)
        else:
            keys[code] = spec
    return keys


def _build_key_names() -> dict[str, int]:
    names: dict[str, int] = {}
    for fmt in ("iso", "ansi", "jis"):
        for code, (name, *_rest) in _geometry(fmt).items():
            names.setdefault(name, code)
    return names


# Key names by keycode, for addressing keys by name and building key groups.
KEY_NAMES = _build_key_names()

# Labels for keys whose legend doesn't depend on the system layout.
_FIXED_LABELS = {
    "ESC": "Esc", "PRSC": "PrtSc", "INS": "Ins", "DELE": "Del", "HOME": "Home",
    "END": "End", "PGUP": "PgUp", "PGDN": "PgDn", "BKSP": "Bksp", "TAB": "Tab",
    "CAPS": "Caps", "RTRN": "Enter", "LFSH": "Shift", "RTSH": "Shift",
    "LCTL": "Ctrl", "RCTL": "Ctrl", "FN": "Fn", "LWIN": "Super", "LALT": "Alt",
    "RALT": "Alt", "SPCE": "", "UP": "↑", "DOWN": "↓", "LEFT": "←", "RGHT": "→",
    "NMLK": "Num", "KPDV": "/", "KPMU": "*", "KPSU": "-", "KPAD": "+",
    "KPEN": "Enter", "KPDL": ".", "NFER": "無変換", "XFER": "変換", "HKTG": "かな",
    **{f"FK{i:02d}": f"F{i}" for i in range(1, 13)},
    **{f"KP{i}": str(i) for i in range(10)},
}

# Legends that come from the system layout.
_CHAR_KEYS = (
    ["TLDE", "BKSL", "LSGT"]
    + [f"AE{i:02d}" for i in range(1, 14)]
    + [f"AD{i:02d}" for i in range(1, 13)]
    + [f"AC{i:02d}" for i in range(1, 13)]
    + [f"AB{i:02d}" for i in range(1, 12)]
)

# Used when libxkbcommon isn't available.
_US_LABELS = {
    "TLDE": "`", "AE11": "-", "AE12": "=", "AD11": "[", "AD12": "]",
    "AC10": ";", "AC11": "'", "BKSL": "\\", "LSGT": "<", "AB08": ",",
    "AB09": ".", "AB10": "/",
    **{f"AE{i:02d}": str(i % 10) for i in range(1, 11)},
    **{f"AD{i:02d}": c for i, c in enumerate("QWERTYUIOP", start=1)},
    **{f"AC{i:02d}": c for i, c in enumerate("ASDFGHJKL", start=1)},
    **{f"AB{i:02d}": c for i, c in enumerate("ZXCVBNM", start=1)},
}

# Dead keys produce no text of their own; show the accent they add.
_DEAD_KEYS = {
    "dead_grave": "`", "dead_acute": "´", "dead_circumflex": "^",
    "dead_tilde": "~", "dead_diaeresis": "¨", "dead_abovering": "˚",
    "dead_cedilla": "¸", "dead_caron": "ˇ", "dead_macron": "¯",
    "dead_breve": "˘", "dead_abovedot": "˙", "dead_doubleacute": "˝",
    "dead_ogonek": "˛",
}

# Keys whose symbol isn't a character but still has a conventional legend.
_NAMED_KEYSYMS = {
    "Zenkaku_Hankaku": "半/全", "Hiragana_Katakana": "かな",
    "Muhenkan": "無変換", "Henkan_Mode": "変換",
}


def system_layout() -> dict:
    """The keyboard layout the system is currently using."""
    raw = run_cmd(["hyprctl", "devices", "-j"], timeout=2.0)
    if raw:
        try:
            keyboards = json.loads(raw).get("keyboards") or []
            kb = next((k for k in keyboards if k.get("main")), keyboards[0] if keyboards else None)
            if kb and kb.get("layout"):
                index = max(0, int(kb.get("active_layout_index") or 0))
                layouts = kb["layout"].split(",")
                variants = (kb.get("variant") or "").split(",")
                return {
                    "layout": layouts[min(index, len(layouts) - 1)].strip(),
                    "variant": variants[index].strip() if index < len(variants) else "",
                    "model": kb.get("model") or "",
                    "options": kb.get("options") or "",
                    "name": kb.get("active_keymap") or "",
                    "source": "hyprland",
                }
        except (ValueError, TypeError, AttributeError) as exc:
            log.debug("Couldn't parse hyprctl devices: %s", exc)

    raw = run_cmd(["localectl", "status"], timeout=2.0)
    if raw:
        fields = {}
        for line in raw.splitlines():
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
        if fields.get("X11 Layout"):
            return {
                "layout": fields["X11 Layout"].split(",")[0],
                "variant": fields.get("X11 Variant", "").split(",")[0],
                "model": fields.get("X11 Model", ""),
                "options": fields.get("X11 Options", ""),
                "name": "",
                "source": "localectl",
            }

    return {"layout": "us", "variant": "", "model": "", "options": "", "name": "", "source": "default"}


def physical_format(device_codes: list[int] | None, system: dict) -> tuple[str, str]:
    """(format, source) — source is "keyboard" or "system"."""
    if device_codes:
        codes = set(device_codes)
        if JIS_KEY in codes:
            return "jis", "keyboard"
        if ISO_KEY in codes:
            return "iso", "keyboard"
        return "ansi", "keyboard"
    # Without the keyboard's own key list, a US layout is almost always on an
    # ANSI board and most other Latin layouts on ISO.
    if system["layout"] == "jp" or system["model"].startswith("jp"):
        return "jis", "system"
    if system["layout"] == "us":
        return "ansi", "system"
    return "iso", "system"


class _RuleNames(ctypes.Structure):
    _fields_ = [(field, ctypes.c_char_p) for field in ("rules", "model", "layout", "variant", "options")]


def _load_xkb():
    try:
        lib = ctypes.CDLL("libxkbcommon.so.0")
    except OSError as exc:
        log.warning("libxkbcommon unavailable, using US key labels: %s", exc)
        return None
    vp, u32 = ctypes.c_void_p, ctypes.c_uint32
    lib.xkb_context_new.restype = vp
    lib.xkb_context_new.argtypes = [ctypes.c_int]
    lib.xkb_context_unref.argtypes = [vp]
    lib.xkb_context_set_log_level.argtypes = [vp, ctypes.c_int]
    lib.xkb_keymap_new_from_names.restype = vp
    lib.xkb_keymap_new_from_names.argtypes = [vp, ctypes.POINTER(_RuleNames), ctypes.c_int]
    lib.xkb_keymap_unref.argtypes = [vp]
    lib.xkb_keymap_key_by_name.restype = u32
    lib.xkb_keymap_key_by_name.argtypes = [vp, ctypes.c_char_p]
    lib.xkb_keymap_key_get_syms_by_level.restype = ctypes.c_int
    lib.xkb_keymap_key_get_syms_by_level.argtypes = [vp, u32, u32, u32, ctypes.POINTER(ctypes.POINTER(u32))]
    lib.xkb_keysym_to_utf32.restype = u32
    lib.xkb_keysym_to_utf32.argtypes = [u32]
    lib.xkb_keysym_get_name.restype = ctypes.c_int
    lib.xkb_keysym_get_name.argtypes = [u32, ctypes.c_char_p, ctypes.c_size_t]
    return lib


def _xkb_labels(system: dict) -> dict[str, str] | None:
    lib = _load_xkb()
    if lib is None:
        return None
    ctx = lib.xkb_context_new(0)
    if not ctx:
        return None
    # xkbcommon prints its own errors to stderr, which lands in the shell's
    # log; a bad layout is already reported through our log below.
    lib.xkb_context_set_log_level(ctx, 10)  # XKB_LOG_LEVEL_CRITICAL
    names = _RuleNames(
        b"evdev",
        system["model"].encode() or None,
        system["layout"].encode() or None,
        system["variant"].encode() or None,
        system["options"].encode() or None,
    )
    keymap = lib.xkb_keymap_new_from_names(ctx, ctypes.byref(names), 0)
    if not keymap:
        log.warning("xkbcommon couldn't compile layout %r; using US key labels", system)
        lib.xkb_context_unref(ctx)
        return None

    def symbol(key: str, level: int) -> tuple[str, str]:
        keycode = lib.xkb_keymap_key_by_name(keymap, key.encode())
        if not keycode:
            return "", ""
        syms = ctypes.POINTER(ctypes.c_uint32)()
        if lib.xkb_keymap_key_get_syms_by_level(keymap, keycode, 0, level, ctypes.byref(syms)) < 1:
            return "", ""
        sym = syms[0]
        codepoint = lib.xkb_keysym_to_utf32(sym)
        name = ctypes.create_string_buffer(64)
        lib.xkb_keysym_get_name(sym, name, 64)
        return (chr(codepoint) if codepoint >= 0x20 else ""), name.value.decode(errors="replace")

    labels: dict[str, str] = {}
    try:
        for key in _CHAR_KEYS:
            char, name = symbol(key, 0)
            if not char:
                char = _DEAD_KEYS.get(name) or _NAMED_KEYSYMS.get(name) or symbol(key, 1)[0]
            if char:
                # Keycaps show capitals, but some letters (ß) have no
                # single-character capital.
                upper = char.upper()
                labels[key] = upper if len(upper) == 1 else char
        # Numpad decimal follows the locale's separator (e.g. "," on Danish).
        decimal = symbol("KPDL", 1)[0]
        if decimal:
            labels["KPDL"] = decimal
        # AltGr layouts put a third level on Right Alt.
        if symbol("RALT", 0)[1] == "ISO_Level3_Shift":
            labels["RALT"] = "AltGr"
    finally:
        lib.xkb_keymap_unref(keymap)
        lib.xkb_context_unref(ctx)
    return labels


def _labels(fmt: str, system: dict) -> dict[str, str]:
    cache_key = "|".join((fmt, system["layout"], system["variant"], system["model"], system["options"]))
    cached = state.load().get("perkey_legends")
    if isinstance(cached, dict) and cached.get("key") == cache_key:
        return cached.get("labels") or {}
    labels = dict(_FIXED_LABELS)
    labels.update(_xkb_labels(system) or _US_LABELS)
    state.update(perkey_legends={"key": cache_key, "labels": labels})
    return labels


def describe(device_codes: list[int] | None) -> dict:
    """Everything the lighting UI needs to draw the keyboard."""
    system = system_layout()
    fmt, source = physical_format(device_codes, system)
    labels = _labels(fmt, system)
    present = set(device_codes) if device_codes else None

    keys = []
    for code, (name, xkb, x, y, w, h) in _geometry(fmt).items():
        if present is not None and code not in present:
            continue
        keys.append({
            "code": code,
            "name": name,
            "label": labels.get(xkb, name),
            "x": round(x / SLOT, 3),
            "y": round(y / SLOT, 3),
            "w": round(w / SLOT, 3),
            "h": round(h / SLOT, 3),
        })
    keys.sort(key=lambda k: (k["y"], k["x"]))

    return {
        "format": fmt,
        "format_source": source,
        "os_layout": system["layout"] + (f"({system['variant']})" if system["variant"] else ""),
        "os_layout_name": system["name"],
        "os_layout_source": system["source"],
        "width": round(max((k["x"] + k["w"] for k in keys), default=0), 3),
        "height": round(max((k["y"] + k["h"] for k in keys), default=0), 3),
        "keys": keys,
    }
