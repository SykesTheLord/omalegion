"""Per-key "Spectrum" RGB keyboard (ITE8258), Legion 7(i)/Pro 7 Gen 9/10.

Protocol, keycode tables and effect codes adapted from
alstergee/legion-spectrum-control (MIT, Copyright (c) 2026 alstergee), which
in turn reverse-engineered LenovoLegionToolkit's
SpectrumKeyboardBacklightController. Verified against a Legion 7i Gen 10
(16IAX10) — compatibility probe, profile/brightness readback and effect
writes all confirmed working on that hardware.

Transport: 960-byte HID feature reports, report id 0x07, on the c197
interface. The device's own report descriptor advertises exactly this
(vendor usage page 0xFF89, report id 0x07, 959 payload bytes).

  Frame: [0x07, operation, 0xC0, 0x03] + payload, zero-padded to 960.

  NOTE: byte 2 is the constant 0xC0, *not* the payload length. Sending the
  length there is silently accepted by the firmware and does nothing.

  Operations used here:
    0xD1  compatibility probe (response byte 4 == 0 means supported)
    0xCA  get active profile   / 0xC8 set active profile (0-6)
    0xCD  get brightness       / 0xCE set brightness (0-9)
    0xA5  get logo state       / 0xA6 set logo on/off
    0xC4  key grid size: payload [7] -> response byte 5 rows, byte 6 cols
    0xC5  key page: payload [7, row] (or [8, 0] for keys outside the grid)
          -> response entries from byte 6, 3 bytes each: [index, keycode LE]
    0xCB  apply effects to the active profile

  An 0xCB payload is [profile, 0x01, 0x01] followed by one blob per effect:
    [effect_no]
    [0x06, 0x01, type, 0x02, speed, 0x03, clockwise, 0x04, direction,
     0x05, color_mode, 0x06, 0x00]
    [color_count] + RGB triplets
    [key_count]   + uint16-LE keycodes

Each LED is addressed by a 16-bit keycode (not an x/y matrix position):
the keyboard keys, 28 perimeter accent LEDs and 1 lid logo. How many keys
there are depends on the layout — ISO boards have 0xA8 (the key left of
Enter) and JIS boards 0xA9, which ANSI lacks — so the key list is read from
the controller (0xC4/0xC5, as LenovoLegionToolkit does) instead of assumed.
The reference tool also uses 0x0065 as an "every LED" shortcut, but on the
16IAX10 the firmware accepts effects addressed to it without showing them, so
"all" here is the explicit list of every keycode.

The 4JX/L5P-Keyboard-RGB project explicitly excludes this hardware (it uses
the incompatible 4-zone ITE8291 protocol) — see lighting_4zone.py.

The keyboard also exposes a second interface, c193 ("Lenovo Lighting"), with
its own undocumented protocol. These reports must go to c197; c193 accepts
them without error and does nothing.
"""

from __future__ import annotations

import struct
import time
from pathlib import Path

from . import keyboard_layout, state
from .lighting_common import (
    clamp,
    find_hidraw,
    get_feature_report,
    hex_to_rgb,
    send_feature_report,
)
from .log import get_logger

log = get_logger("perkey")

VID = "048d"
PIDS = {"c197"}

REPORT_LEN = 960
REPORT_ID = 0x07
HEADER_SIZE_BYTE = 0xC0
HEADER_TAIL = 0x03

OP_COMPATIBILITY = 0xD1
OP_PROFILE_CHANGE = 0xC8
OP_PROFILE = 0xCA
OP_EFFECT_CHANGE = 0xCB
OP_GET_BRIGHTNESS = 0xCD
OP_BRIGHTNESS = 0xCE
OP_GET_LOGO = 0xA5
OP_LOGO = 0xA6
OP_KEY_COUNT = 0xC4
OP_KEY_PAGE = 0xC5

BRIGHTNESS_MAX = 9

# Effect type codes. audio-bounce (9) and audio-ripple (10) are omitted:
# they react to system audio and aren't meaningfully controllable here.
EFFECTS = {
    "static": 11,
    "smooth": 6,
    "rainbow-wave": 2,
    "screw-rainbow": 1,
    "color-change": 3,
    "color-pulse": 4,
    "color-wave": 5,
    "rain": 7,
    "ripple": 8,
    "type": 12,
}

EFFECTS_WITH_SPEED = {
    "screw-rainbow", "rainbow-wave", "color-change", "color-pulse",
    "color-wave", "smooth", "rain", "ripple", "type",
}
EFFECTS_WITH_DIRECTION = {"color-wave", "rainbow-wave"}

DIRECTIONS = {"up": 1, "down": 2, "right": 3, "left": 4}

# ANSI key table, used only if the controller's own key list can't be read.
FALLBACK_KEYBOARD_KEYS = [
    0x0001, 0x0002, 0x0003, 0x0004, 0x0005, 0x0006, 0x0007, 0x0008,
    0x0009, 0x000A, 0x000B, 0x000C, 0x000D, 0x000E, 0x000F, 0x0010,
    0x0011, 0x0012, 0x0013, 0x0014, 0x0016, 0x0017, 0x0018, 0x0019,
    0x001A, 0x001B, 0x001C, 0x001D, 0x001E, 0x001F, 0x0020, 0x0021,
    0x0022, 0x0026, 0x0027, 0x0028, 0x0029, 0x0038, 0x0040, 0x0042,
    0x0043, 0x0044, 0x0045, 0x0046, 0x0047, 0x0048, 0x0049, 0x004A,
    0x004B, 0x004C, 0x004D, 0x004E, 0x004F, 0x0050, 0x0051, 0x0055,
    0x0058, 0x0059, 0x005A, 0x005B, 0x005C, 0x005D, 0x005F, 0x0068,
    0x006A, 0x006D, 0x006E, 0x006F, 0x0070, 0x0071, 0x0072, 0x0073,
    0x0074, 0x0075, 0x0076, 0x0077, 0x0079, 0x007B, 0x007C, 0x007F,
    0x0080, 0x0082, 0x0083, 0x0087, 0x0088, 0x008D, 0x008E, 0x0090,
    0x0092, 0x0096, 0x0097, 0x0098, 0x009A, 0x009B, 0x009C, 0x009D,
    0x009F, 0x00A1, 0x00A3, 0x00A5, 0x00A7,
]

PERIMETER_KEYS = [
    0x03E9, 0x03EA, 0x03EB, 0x03EC, 0x03ED, 0x03EE, 0x03EF,
    0x03F0, 0x03F1, 0x03F2, 0x03F3, 0x03F4, 0x03F5, 0x03F6,
    0x03F7, 0x03F8, 0x03F9, 0x03FA,
    0x01F5, 0x01F6, 0x01F7, 0x01F8, 0x01F9, 0x01FA,
    0x01FB, 0x01FC, 0x01FD, 0x01FE,
]

LOGO_KEY = 0x05DD

ZONE_NAMES = ("all", "keyboard", "perimeter", "logo")

# Key names by keycode, worked out from the key positions in
# LenovoLegionToolkit's layouts. The names in legion-spectrum-control were
# wrong for the bottom rows, the arrows and the numpad.
KEY_NAMES = keyboard_layout.KEY_NAMES

# Fixed key groups. "all", "keyboard" and "perimeter" are also offered as
# groups but come from the zones, since they depend on the keyboard's layout.
KEY_GROUPS = {
    "wasd": [KEY_NAMES[k] for k in ("w", "a", "s", "d")],
    "arrows": [KEY_NAMES[k] for k in ("up", "down", "left", "right")],
    "numpad": [
        KEY_NAMES[k] for k in (
            "numlock", "numdiv", "nummul", "numsub", "num7", "num8", "num9",
            "numadd", "num4", "num5", "num6", "num1", "num2", "num3", "num0",
            "numdot", "numenter",
        )
    ],
    "fkeys": [KEY_NAMES[f"f{i}"] for i in range(1, 13)],
}


def _device() -> Path | None:
    return find_hidraw(VID, PIDS)


def _frame(op: int, payload: bytes = b"") -> bytes:
    header = bytes([REPORT_ID, op, HEADER_SIZE_BYTE, HEADER_TAIL])
    return (header + payload).ljust(REPORT_LEN, b"\x00")


def _query(dev: Path, op: int) -> int | None:
    """Run a get-style operation and return the meaningful response byte."""
    if not send_feature_report(dev, _frame(op)):
        return None
    resp = get_feature_report(dev, REPORT_ID, REPORT_LEN)
    return resp[4] if resp else None


def is_present() -> bool:
    return _device() is not None


def get_state() -> dict:
    dev = _device()
    info = {
        "backend": "perkey",
        "available": dev is not None,
        "zones": list(ZONE_NAMES),
        "effects": list(EFFECTS.keys()),
        "effects_with_speed": sorted(EFFECTS_WITH_SPEED),
        "effects_with_direction": sorted(EFFECTS_WITH_DIRECTION),
        "directions": list(DIRECTIONS.keys()),
        "groups": ["all", "keyboard", "perimeter", *KEY_GROUPS],
        "brightness_max": BRIGHTNESS_MAX,
        "keys": [
            {"code": code, "name": _name_for(code)}
            for code in _zone_keys("keyboard", dev) or []
        ],
        "layout": keyboard_layout.describe(_device_keys(dev)),
    }
    if dev is None:
        return info
    info.update(_device_status(dev))
    return info


# The panel polls every few seconds and each device query is a write+read
# pair on the lighting controller, so re-reading on every poll means constant
# traffic — and these reads do occasionally come back as garbage. The cache
# has to live in the state file rather than in memory, because every engine
# command is its own short-lived process.
_STATUS_TTL = 15.0
_CACHE_KEY = "perkey_status"
_CACHE_AT_KEY = "perkey_status_at"


def _device_status(dev: Path) -> dict:
    saved = state.load()
    cached = saved.get(_CACHE_KEY)
    cached_at = saved.get(_CACHE_AT_KEY) or 0
    if isinstance(cached, dict) and (time.time() - cached_at) < _STATUS_TTL:
        return cached

    status: dict = {"supported": _query(dev, OP_COMPATIBILITY) == 0}
    profile = _query(dev, OP_PROFILE)
    if profile is not None:
        status["profile"] = profile
    brightness = _query(dev, OP_GET_BRIGHTNESS)
    if brightness is not None:
        status["device_brightness"] = brightness
    logo = _query(dev, OP_GET_LOGO)
    if logo is not None:
        status["device_logo_on"] = logo == 1

    state.update(**{_CACHE_KEY: status, _CACHE_AT_KEY: time.time()})
    return status


def _invalidate_status() -> None:
    state.update(**{_CACHE_KEY: None, _CACHE_AT_KEY: 0})


# A keyboard's layout never changes, so once a read looks sane it's cached
# for good instead of costing ~10 device round trips per engine command.
_KEYMAP_KEY = "perkey_keymap"


def _read_layout(dev: Path) -> list[int] | None:
    if not send_feature_report(dev, _frame(OP_KEY_COUNT, bytes([0x07]))):
        return None
    resp = get_feature_report(dev, REPORT_ID, REPORT_LEN)
    if not resp:
        return None
    rows, cols = resp[5], resp[6]
    if not (1 <= rows <= 32 and 1 <= cols <= 32):
        log.warning("Implausible key grid %dx%d; using built-in key table", rows, cols)
        return None

    codes: list[int] = []
    # Parameter 0x08 is a page for LEDs outside the grid, such as the lid logo.
    pages = [(0x07, row) for row in range(rows)] + [(0x08, 0)]
    for param, index in pages:
        if not send_feature_report(dev, _frame(OP_KEY_PAGE, bytes([param, index]))):
            return None
        page = get_feature_report(dev, REPORT_ID, REPORT_LEN)
        if not page:
            return None
        for x in range(cols):
            offset = 6 + x * 3
            code = page[offset + 1] | (page[offset + 2] << 8)
            if code and code not in codes:
                codes.append(code)

    # These reads occasionally come back as garbage; don't cache one.
    if KEY_NAMES["esc"] not in codes or len(codes) < len(FALLBACK_KEYBOARD_KEYS) // 2:
        log.warning("Key layout read looks wrong (%d keys); using built-in key table", len(codes))
        return None
    return codes


def _device_keys(dev: Path | None) -> list[int] | None:
    """Keycodes the keyboard reported, or None if they couldn't be read."""
    cached = state.load().get(_KEYMAP_KEY)
    if isinstance(cached, list) and cached:
        return cached
    if dev is None:
        return None
    codes = _read_layout(dev)
    if codes:
        state.update(**{_KEYMAP_KEY: codes})
        log.debug("Read %d keycodes from the keyboard", len(codes))
    return codes


def _layout_keys(dev: Path | None) -> list[int]:
    return _device_keys(dev) or FALLBACK_KEYBOARD_KEYS + PERIMETER_KEYS + [LOGO_KEY]


def _zone_keys(zone: str, dev: Path | None) -> list[int] | None:
    if zone == "all":
        return _layout_keys(dev)
    if zone == "keyboard":
        excluded = set(PERIMETER_KEYS) | {LOGO_KEY}
        return [code for code in _layout_keys(dev) if code not in excluded]
    if zone == "perimeter":
        return list(PERIMETER_KEYS)
    if zone == "logo":
        return [LOGO_KEY]
    return None


def _group_keys(group: str, dev: Path | None) -> list[int] | None:
    if group in ZONE_NAMES:
        return _zone_keys(group, dev)
    return KEY_GROUPS.get(group)


_NAME_BY_CODE = {code: name for name, code in KEY_NAMES.items()}


def _name_for(code: int) -> str:
    return _NAME_BY_CODE.get(code, f"0x{code:04x}")


PROFILE_MIN = 1
PROFILE_MAX = 6
DEFAULT_PROFILE = 1


def set_profile(profile: int) -> dict:
    dev = _device()
    if not dev:
        return {"status": "error", "message": "Spectrum keyboard not found"}
    value = clamp(profile, PROFILE_MIN, PROFILE_MAX)
    if not send_feature_report(dev, _frame(OP_PROFILE_CHANGE, bytes([value]))):
        return {"status": "error", "message": "Failed to switch profile"}
    _invalidate_status()
    return {"status": "success", "profile": value}


def _active_profile(dev: Path) -> int:
    """Profile slots are 1-6. The device sometimes reports 0, which is not a
    real slot — and writing effects addressed to profile 0 is accepted but
    has no visible effect, which latches the lighting into a dead state
    (every later write also goes to 0). So treat anything outside 1-6 as
    bad, put the device back on a known-good profile, and use that."""
    profile = _query(dev, OP_PROFILE)
    if profile is not None and PROFILE_MIN <= profile <= PROFILE_MAX:
        return profile
    log.warning("Invalid active profile %r; resetting to %d", profile, DEFAULT_PROFILE)
    send_feature_report(dev, _frame(OP_PROFILE_CHANGE, bytes([DEFAULT_PROFILE])))
    return DEFAULT_PROFILE


def _build_effect(
    effect_no: int,
    effect_type: int,
    colors: list[tuple[int, int, int]],
    keycodes: list[int],
    speed: int = 0,
    direction: int = 0,
    clockwise: int = 0,
) -> bytes:
    color_mode = 0x02 if colors else (0x01 if effect_type != EFFECTS["static"] else 0x00)
    blob = bytes([effect_no])
    blob += bytes([
        0x06, 0x01, effect_type,
        0x02, speed,
        0x03, clockwise,
        0x04, direction,
        0x05, color_mode,
        0x06, 0x00,
    ])
    blob += bytes([len(colors)])
    for r, g, b in colors:
        blob += bytes([r, g, b])
    blob += bytes([len(keycodes)])
    for code in keycodes:
        blob += struct.pack("<H", code)
    return blob


def _send_effects(dev: Path, profile: int, blobs: list[bytes]) -> bool:
    payload = bytes([profile, 0x01, 0x01]) + b"".join(blobs)
    ok = send_feature_report(dev, _frame(OP_EFFECT_CHANGE, payload))
    if ok:
        _invalidate_status()
    return ok


def set_brightness(level: int) -> dict:
    dev = _device()
    if not dev:
        return {"status": "error", "message": "Spectrum keyboard not found"}
    value = clamp(level, 0, BRIGHTNESS_MAX)
    if not send_feature_report(dev, _frame(OP_BRIGHTNESS, bytes([value]))):
        return {"status": "error", "message": "Failed to write brightness"}
    _invalidate_status()
    return {"status": "success", "brightness": value}


def set_zone_effect(
    zone: str,
    effect: str,
    color: str | None,
    speed: int = 2,
    direction: str | None = None,
) -> dict:
    dev = _device()
    if not dev:
        return {"status": "error", "message": "Spectrum keyboard not found"}
    keycodes = _zone_keys(zone, dev)
    if keycodes is None:
        return {"status": "error", "message": f"Unknown zone: {zone}"}
    effect_type = EFFECTS.get(effect)
    if effect_type is None:
        return {"status": "error", "message": f"Unknown effect: {effect}"}

    colors = [hex_to_rgb(color)] if color else []
    if effect == "static" and not colors:
        colors = [(255, 255, 255)]

    blob = _build_effect(
        1,
        effect_type,
        colors,
        keycodes,
        speed=clamp(speed, 1, 3) if effect in EFFECTS_WITH_SPEED else 0,
        direction=DIRECTIONS.get(direction or "", 0) if effect in EFFECTS_WITH_DIRECTION else 0,
    )
    if not _send_effects(dev, _active_profile(dev), [blob]):
        return {"status": "error", "message": "Failed to apply zone effect"}
    return {"status": "success", "zone": zone, "effect": effect, "color": color}


def set_solid_color(color: str) -> dict:
    return set_zone_effect("all", "static", color)


def set_logo(on: bool) -> dict:
    dev = _device()
    if not dev:
        return {"status": "error", "message": "Spectrum keyboard not found"}
    if not send_feature_report(dev, _frame(OP_LOGO, bytes([1 if on else 0]))):
        return {"status": "error", "message": "Failed to toggle logo light"}
    _invalidate_status()
    return {"status": "success", "logo": bool(on)}


def set_key_colors(key_colors: dict[str, str], base_color: str | None = None) -> dict:
    """key_colors maps a keycode (int, "0x0042" or a key name) to a hex color.
    Keys left out keep whatever the profile already shows unless base_color
    is given, in which case the rest of the keyboard is set to it first."""
    dev = _device()
    if not dev:
        return {"status": "error", "message": "Spectrum keyboard not found"}

    # One effect blob per distinct color, so a whole-keyboard paint is a
    # single report rather than one per key.
    by_color: dict[tuple[int, int, int], list[int]] = {}
    if base_color:
        by_color[hex_to_rgb(base_color)] = list(_zone_keys("keyboard", dev) or [])

    for key, color in key_colors.items():
        code = resolve_key(key)
        if code is None:
            continue
        rgb = hex_to_rgb(color)
        for codes in by_color.values():
            if code in codes:
                codes.remove(code)
        by_color.setdefault(rgb, []).append(code)

    blobs = [
        _build_effect(i, EFFECTS["static"], [rgb], codes)
        for i, (rgb, codes) in enumerate(
            ((rgb, codes) for rgb, codes in by_color.items() if codes), start=1
        )
    ]
    if not blobs:
        return {"status": "error", "message": "No valid keys given"}
    if not _send_effects(dev, _active_profile(dev), blobs):
        return {"status": "error", "message": "Failed to write key colors"}
    return {"status": "success", "keys_set": len(key_colors)}


def resolve_key(key: str | int) -> int | None:
    if isinstance(key, int):
        return key
    name = str(key).strip().lower()
    if name in KEY_NAMES:
        return KEY_NAMES[name]
    try:
        return int(name, 16) if name.startswith("0x") else int(name)
    except ValueError:
        log.debug("Unresolvable key: %r", key)
        return None


def set_group_color(group: str, color: str) -> dict:
    dev = _device()
    if not dev:
        return {"status": "error", "message": "Spectrum keyboard not found"}
    keycodes = _group_keys(group, dev)
    if keycodes is None:
        return {"status": "error", "message": f"Unknown key group: {group}"}
    blob = _build_effect(1, EFFECTS["static"], [hex_to_rgb(color)], keycodes)
    if not _send_effects(dev, _active_profile(dev), [blob]):
        return {"status": "error", "message": "Failed to apply group color"}
    return {"status": "success", "group": group, "color": color}
