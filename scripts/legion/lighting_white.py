"""White single-zone backlight (e.g. budget LOQ / Y-series models).

No RGB hardware — just the existing generic /sys/class/leds brightness path
already used by input.py. Kept as its own module so the lighting dispatcher
in lighting.py can treat all three keyboard kinds uniformly.
"""

from __future__ import annotations

from .input import get_input, set_backlight


def get_state() -> dict:
    info = get_input()
    return {
        "backend": "white",
        "available": info.get("backlight_available", False),
        "brightness": info.get("backlight_brightness"),
        "brightness_max": info.get("backlight_max"),
    }


def set_brightness(level: int) -> dict:
    return set_backlight(level)
