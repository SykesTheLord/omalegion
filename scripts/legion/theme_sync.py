"""Sync keyboard lighting color to the active Omarchy theme.

Omarchy themes already carry a `keyboard.rgb` file alongside colors.toml
(cloned themes preserve it, and stock themes like tokyo-night ship one) —
this is an existing Omarchy convention for exactly this purpose, so we read
it first and only fall back to colors.toml's `accent` for themes that don't
define one.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

CURRENT_THEME_DIR = Path.home() / ".local" / "state" / "omarchy" / "current" / "theme"


def _normalize_hex(value: str) -> str | None:
    v = value.strip().lstrip("#")
    if len(v) != 6:
        return None
    try:
        int(v, 16)
    except ValueError:
        return None
    return "#" + v.lower()


def current_theme_color() -> str | None:
    kbd_file = CURRENT_THEME_DIR / "keyboard.rgb"
    if kbd_file.is_file():
        color = _normalize_hex(kbd_file.read_text())
        if color:
            return color

    colors_file = CURRENT_THEME_DIR / "colors.toml"
    if colors_file.is_file():
        try:
            data = tomllib.loads(colors_file.read_text())
            accent = data.get("accent")
            if isinstance(accent, str):
                return _normalize_hex(accent)
        except (OSError, tomllib.TOMLDecodeError):
            pass
    return None
