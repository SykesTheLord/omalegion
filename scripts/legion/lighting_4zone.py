"""4-zone RGB keyboard (ITE8291), e.g. Legion 5/5 Pro/Slim, 2020-2024.

Protocol adapted from the public reverse-engineering write-up at
kaveh.page/snippets/lenovo-legion-keyboard-lights and pobrn/ite8291r3-ctl:
a single ~33-byte HID feature report, report id 0xCC, second byte 0x16
("set" marker), then effect/speed/brightness followed by 4 zone RGB triplets.

Community tools (ite8291r3-ctl, 4JX/L5P-Keyboard-RGB) primarily use raw USB
control transfers via pyusb because some ITE8291 firmwares don't expose a
well-formed feature-report descriptor to the kernel's generic HID driver. We
go through /dev/hidraw (see lighting_common.py) to stay dependency-free; if a
particular unit doesn't accept writes this way, it needs the pyusb-based
tools instead — this is a known limitation, not a bug in the color/effect
math below.
"""

from __future__ import annotations

from pathlib import Path

from .lighting_common import clamp, find_hidraw, hex_to_rgb, send_feature_report

VID = "048d"
PIDS = {
    "6004", "6006", "600b", "ce00",
    "c955", "c965", "c963", "c975", "c973",
    "c985", "c984", "c983", "c995", "c994", "c993",
}

REPORT_LEN = 33
REPORT_ID = 0xCC
CMD_SET = 0x16

EFFECTS = {
    "static": 0x01,
    "breathing": 0x03,
    "wave": 0x04,
    "random": 0x05,
    "rainbow": 0x06,
    "ripple": 0x07,
    "marquee": 0x08,
    "raindrop": 0x09,
    "aurora": 0x0A,
    "fireworks": 0x0B,
}

BRIGHTNESS_MAX = 50
ZONE_COUNT = 4


def _device() -> Path | None:
    return find_hidraw(VID, PIDS)


def is_present() -> bool:
    return _device() is not None


def get_state() -> dict:
    return {
        "backend": "4zone",
        "available": is_present(),
        "effects": list(EFFECTS.keys()),
        "zone_count": ZONE_COUNT,
        "brightness_max": BRIGHTNESS_MAX,
    }


def _frame(effect_id: int, speed: int, brightness: int, colors: list[str]) -> bytes:
    body = bytearray([REPORT_ID, CMD_SET, effect_id, clamp(speed, 1, 4), clamp(brightness, 0, BRIGHTNESS_MAX)])
    zones = (colors + ["#ffffff"] * ZONE_COUNT)[:ZONE_COUNT]
    for hex_color in zones:
        body += bytes(hex_to_rgb(hex_color))
    return bytes(body).ljust(REPORT_LEN, b"\x00")


def set_effect(effect: str, speed: int, brightness: int, colors: list[str]) -> dict:
    dev = _device()
    if not dev:
        return {"status": "error", "message": "4-zone RGB keyboard not found"}
    effect_id = EFFECTS.get(effect, EFFECTS["static"])
    ok = send_feature_report(dev, _frame(effect_id, speed, brightness, colors))
    if not ok:
        return {"status": "error", "message": "Failed to write lighting report (check udev permissions)"}
    return {"status": "success", "effect": effect}


def set_solid_color(color: str, brightness: int = BRIGHTNESS_MAX) -> dict:
    return set_effect("static", speed=1, brightness=brightness, colors=[color] * ZONE_COUNT)


def set_zone_colors(colors: list[str], brightness: int = BRIGHTNESS_MAX) -> dict:
    return set_effect("static", speed=1, brightness=brightness, colors=colors)


def set_brightness(level: int) -> dict:
    # ITE8291 has no standalone brightness-only op; re-send static white at
    # the requested brightness only when the caller doesn't care about color.
    return set_solid_color("#ffffff", brightness=level)
