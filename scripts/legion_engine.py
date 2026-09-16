#!/usr/bin/env python3
"""Legion Toolkit hardware engine — CLI for the Omarchy plugin."""

from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from legion.log import get_logger  # noqa: E402

log = get_logger("engine")

from legion import (  # noqa: E402
    apply_theme_color,
    deactivate_dgpu,
    get_battery,
    get_fans,
    get_gpu,
    get_input,
    get_lighting,
    get_power,
    get_system,
    get_thermals,
    install_permissions,
    set_backlight,
    set_battery_mode,
    set_color,
    set_effect,
    set_fan_mode,
    set_fan_speed,
    set_fn_lock,
    set_gpu_mode,
    set_gpu_oc,
    set_key_group,
    set_key_map,
    set_lighting_brightness,
    set_lighting_power,
    set_logo,
    set_model_override,
    set_overnight,
    set_power,
    set_ppt,
    set_theme_sync,
    set_usb_charging,
    update_history,
)


def collect_all() -> dict:
    system = get_system()
    power = get_power()
    fans = get_fans()
    thermals = get_thermals()
    gpu = get_gpu()
    battery = get_battery()
    controls = get_input()
    lighting = get_lighting()
    history = update_history(thermals, fans, gpu)
    return {
        "system": system,
        "power": power,
        "fans": fans,
        "thermals": thermals,
        "gpu": gpu,
        "battery": battery,
        "input": controls,
        "lighting": lighting,
        "history": history,
        "timestamp": time.strftime("%H:%M:%S"),
    }


def _flag(value: str) -> bool:
    return value.lower() in ("1", "true", "on", "yes")


def dispatch(argv: list[str]) -> dict:
    action = argv[0]
    arg = argv[1] if len(argv) > 1 else None
    arg2 = argv[2] if len(argv) > 2 else None

    if action == "--set-power" and arg:
        return set_power(arg)
    if action == "--set-ppt" and arg and arg2:
        return set_ppt(arg, arg2)
    if action == "--set-battery-mode" and arg:
        return set_battery_mode(arg)
    if action == "--set-overnight" and arg:
        return set_overnight(_flag(arg))
    if action == "--set-usb-charging" and arg:
        return set_usb_charging(_flag(arg))
    if action == "--set-fn-lock" and arg:
        return set_fn_lock(_flag(arg))
    if action == "--set-backlight" and arg:
        return set_backlight(int(arg))
    if action == "--set-gpu-mode" and arg:
        return set_gpu_mode(arg)
    if action == "--deactivate-dgpu":
        force = arg and arg.lower() in ("1", "true", "force", "kill", "yes")
        return deactivate_dgpu(kill_processes=force)
    if action == "--set-gpu-oc" and arg:
        return set_gpu_oc(_flag(arg))
    if action == "--set-fan-mode" and arg:
        return set_fan_mode(arg.lower() in ("auto", "1", "true"))
    if action == "--set-fan-speed" and arg:
        return set_fan_speed(int(arg))
    if action == "--set-lighting-power" and arg:
        return set_lighting_power(_flag(arg))
    if action == "--set-lighting-brightness" and arg:
        return set_lighting_brightness(int(arg))
    if action == "--set-lighting-effect" and arg:
        return set_effect(arg)
    if action == "--set-lighting-color" and arg:
        return set_color(arg)
    if action == "--set-lighting-logo" and arg:
        return set_logo(_flag(arg))
    if action == "--set-lighting-group" and arg and arg2:
        return set_key_group(arg, arg2)
    if action == "--set-lighting-keymap" and arg:
        return set_key_map(json.loads(arg))
    if action == "--set-model-override" and arg:
        return set_model_override(None if arg == "auto" else arg)
    if action == "--set-theme-sync" and arg:
        return set_theme_sync(_flag(arg))
    if action == "--theme-sync-apply":
        return apply_theme_color()
    if action == "--install-lighting-permissions":
        return install_permissions()
    log.warning("Unknown action requested: %s (args=%s)", action, argv[1:])
    return {"status": "error", "message": f"Unknown action: {action}"}


def main() -> None:
    try:
        if len(sys.argv) > 1:
            log.debug("dispatch %s", sys.argv[1:])
            result = dispatch(sys.argv[1:])
            if result.get("status") == "error":
                log.warning("command failed: %s -> %s", sys.argv[1:], result)
            print(json.dumps(result))
            return
        print(json.dumps(collect_all(), indent=2))
    except Exception:
        log.error("Unhandled exception:\n%s", traceback.format_exc())
        print(json.dumps({"status": "error", "message": "Internal error, see legion_debug.log"}))


if __name__ == "__main__":
    main()
