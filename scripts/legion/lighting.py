"""Capability-gated lighting dispatcher.

Picks the right backend (lighting_perkey / lighting_4zone / lighting_white)
based on the detected/overridden model from model.py, and persists the
user's last-chosen brightness/effect/color/logo/theme-sync preferences in the
shared state file so the panel can show them back without depending on
hardware readback (HID feature reports here are effectively write-only).
"""

from __future__ import annotations

import shlex
import subprocess
import tempfile
from pathlib import Path

from . import lighting_4zone as fourzone
from . import lighting_perkey as perkey
from . import lighting_white as white
from . import model, state, theme_sync
from .log import get_logger

log = get_logger("lighting")

HOOK_NAME = "theme-set"


def _backend_state() -> dict:
    kind = model.get_model().get("keyboard", "none")
    if kind == "perkey":
        return perkey.get_state()
    if kind == "4zone":
        return fourzone.get_state()
    if kind == "white":
        return white.get_state()
    return {"backend": "none", "available": False}


def get_lighting() -> dict:
    saved = state.load()
    m = model.get_model()
    return {
        "model": m,
        "known_models": model.known_model_names(),
        "hardware": _backend_state(),
        "on": saved.get("lighting_on", True),
        "brightness": saved.get("lighting_brightness", 5),
        "effect": saved.get("lighting_effect", "static"),
        "color": saved.get("lighting_color", "#ffffff"),
        "logo_on": saved.get("lighting_logo_on", True),
        "sync_theme": saved.get("sync_theme", False),
        "theme_color": theme_sync.current_theme_color(),
        "permissions_installed": permissions_installed(),
    }


def _valid_effect(kind: str, effect: str) -> str:
    """Effect names are backend-specific, and a name persisted by an older
    version (or by a different backend after a model override) may no longer
    exist. Fall back to static rather than failing the whole apply."""
    known = perkey.EFFECTS if kind == "perkey" else fourzone.EFFECTS if kind == "4zone" else {}
    if not known or effect in known:
        return effect
    return "static"


def _apply_current(saved: dict) -> dict:
    kind = model.get_model().get("keyboard", "none")
    color = saved.get("lighting_color", "#ffffff")
    brightness = saved.get("lighting_brightness", 5)
    effect = _valid_effect(kind, saved.get("lighting_effect", "static"))
    on = saved.get("lighting_on", True)

    if kind == "perkey":
        if not on:
            return perkey.set_brightness(0)
        perkey.set_brightness(brightness)
        # "all" covers keyboard + perimeter accents; the lid logo has its own
        # on/off op and stays independent.
        return perkey.set_zone_effect("all", effect, color)
    if kind == "4zone":
        if not on:
            return fourzone.set_brightness(0)
        return fourzone.set_effect(effect, speed=2, brightness=brightness, colors=[color] * fourzone.ZONE_COUNT)
    if kind == "white":
        return white.set_brightness(brightness if on else 0)
    return {"status": "error", "message": "No lighting hardware detected for this model"}


def set_power(on: bool) -> dict:
    saved = state.load()
    saved["lighting_on"] = bool(on)
    state.save(saved)
    result = _apply_current(saved)
    result["on"] = bool(on)
    return result


def set_brightness(level: int) -> dict:
    saved = state.load()
    saved["lighting_brightness"] = int(level)
    state.save(saved)
    return _apply_current(saved)


def set_effect(effect: str) -> dict:
    saved = state.load()
    saved["lighting_effect"] = effect
    saved["sync_theme"] = False
    state.save(saved)
    return _apply_current(saved)


def set_color(color: str) -> dict:
    saved = state.load()
    saved["lighting_color"] = color
    saved["sync_theme"] = False
    state.save(saved)
    return _apply_current(saved)


def set_logo(on: bool) -> dict:
    kind = model.get_model().get("keyboard", "none")
    if kind != "perkey":
        return {"status": "error", "message": "Logo light control is only available on per-key Spectrum keyboards"}
    saved = state.load()
    saved["lighting_logo_on"] = bool(on)
    state.save(saved)
    return perkey.set_logo(on)


def set_key_group(group: str, color: str) -> dict:
    kind = model.get_model().get("keyboard", "none")
    if kind != "perkey":
        return {"status": "error", "message": "Per-key colors are only available on Spectrum keyboards"}
    return perkey.set_group_color(group, color)


def set_key_map(key_colors: dict[str, str]) -> dict:
    kind = model.get_model().get("keyboard", "none")
    if kind != "perkey":
        return {"status": "error", "message": "Per-key colors are only available on Spectrum keyboards"}
    saved = state.load()
    return perkey.set_key_colors(key_colors, base_color=saved.get("lighting_color", "#000000"))


def set_model_override(name: str | None) -> dict:
    return model.set_model_override(name)


UDEV_RULE_DEST = "/etc/udev/rules.d/99-legion-lighting.rules"


def _udev_rule_source() -> str:
    from pathlib import Path
    return str((Path(__file__).resolve().parent.parent.parent / "udev" / "99-legion-lighting.rules"))


def permissions_installed() -> bool:
    """True only if the installed rule matches what this plugin ships —
    not just present, so a bundled rule update (e.g. switching from the
    uaccess approach to a plain MODE) gets picked up automatically instead
    of being masked by a stale copy of the old rule."""
    from pathlib import Path

    dest = Path(UDEV_RULE_DEST)
    if not dest.is_file():
        return False
    try:
        return dest.read_text() == Path(_udev_rule_source()).read_text()
    except OSError:
        return False


def install_permissions() -> dict:
    import subprocess

    if permissions_installed():
        return {"status": "success", "message": "Already installed"}
    source = _udev_rule_source()
    try:
        result = subprocess.run(
            ["pkexec", "sh", "-c", f"cp '{source}' '{UDEV_RULE_DEST}' && udevadm control --reload-rules && udevadm trigger"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "error", "message": str(exc)}
    if result.returncode != 0:
        return {"status": "error", "message": result.stderr.strip() or "Failed to install udev rule"}
    return {"status": "success", "message": "Lighting permissions installed and applied immediately (MODE-based, no reboot needed)."}


HOOK_FILENAME = "theme-set-lighting-sync"
HOOK_INSTALLED_PATH = Path.home() / ".config" / "omarchy" / "hooks" / f"{HOOK_NAME}.d" / HOOK_FILENAME


def _hook_script() -> str:
    # `omarchy hook install` copies the file into hooks/theme-set.d/, so the
    # script can't locate the engine relative to itself — bake in the path.
    engine = Path(__file__).resolve().parent.parent / "legion_engine.py"
    return (
        "#!/bin/bash\n"
        "# Installed by the Legion plugin's \"Sync to Omarchy theme\" toggle.\n"
        "# Safe to leave installed: the engine no-ops while sync is off.\n"
        f"exec python3 {shlex.quote(str(engine))} --theme-sync-apply\n"
    )


def _ensure_theme_hook_installed() -> None:
    expected = _hook_script()
    try:
        if HOOK_INSTALLED_PATH.read_text() == expected:
            return
    except OSError:
        pass
    # Reinstall whenever the content differs, which also replaces copies
    # left by older versions or a moved plugin directory.
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / HOOK_FILENAME
        script.write_text(expected)
        script.chmod(0o755)
        result = subprocess.run(
            ["omarchy", "hook", "install", HOOK_NAME, str(script)],
            capture_output=True, text=True, timeout=15,
        )
    if result.returncode != 0:
        log.warning("theme-set hook install failed rc=%d: %s", result.returncode, result.stderr.strip())
        return
    state.update(theme_sync_hook_installed=True)


def apply_theme_color() -> dict:
    """Push the active Omarchy theme's color to the keyboard. Called both
    from the panel toggle and from the theme-set hook script."""
    saved = state.load()
    if not saved.get("sync_theme"):
        return {"status": "skipped", "message": "Theme sync is disabled"}
    color = theme_sync.current_theme_color()
    if not color:
        return {"status": "error", "message": "Active theme has no keyboard.rgb or accent color"}
    saved["lighting_color"] = color
    saved["lighting_effect"] = "static"
    state.save(saved)
    result = _apply_current(saved)
    result["color"] = color
    return result


def set_theme_sync(enabled: bool) -> dict:
    saved = state.load()
    saved["sync_theme"] = bool(enabled)
    state.save(saved)
    if enabled:
        _ensure_theme_hook_installed()
        return apply_theme_color()
    return {"status": "success", "sync_theme": False}
