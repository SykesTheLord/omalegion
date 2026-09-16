"""Legion model detection: which lighting hardware is present.

Detection combines two signals, matching the approach used by community
Legion-lighting tools (ite8291r3-ctl, L5P-Keyboard-RGB, legion-spectrum-control)
and the DMI/BIOS allowlist pattern in the out-of-tree legion-laptop driver:

  1. USB VID/PID probing — authoritative when it matches, since the exact
     lighting chip (and therefore protocol) is what actually determines what
     works, and DMI alone can't distinguish 4-zone from per-key hardware.
  2. DMI product name/version — used as a fallback when no known USB device
     is found (e.g. unlisted/newer model), and to label optional zones (logo,
     IO-port) that don't show up as their own USB device.

The user can always override the detected profile; see `get_override`/
`set_override` below, backed by the shared plugin state file.
"""

from __future__ import annotations

from pathlib import Path

from . import state
from .sysfs import read_text

DMI = Path("/sys/class/dmi/id")
USB_DEVICES = Path("/sys/bus/usb/devices")

LENOVO_VID = "048d"

# USB PID -> keyboard lighting kind. Per-key "Spectrum" (ITE8258) devices
# ship two interfaces on the same physical keyboard: c197 does the actual
# lighting, c193 is a companion control interface used alongside it.
PERKEY_PIDS = {"c197", "c193"}

# 4-zone ITE8291(r3) devices. Legacy ids from pobrn/ite8291r3-ctl plus the
# per-year Legion 5/5 Pro/Slim table from 4JX/L5P-Keyboard-RGB.
FOURZONE_PIDS = {
    "6004", "6006", "600b", "ce00",  # ite8291r3-ctl
    "c955", "c965", "c963", "c975", "c973",
    "c985", "c984", "c983", "c995", "c994", "c993",
}

# Known model profiles, keyed by a lowercase substring match against
# product_name (checked first) then product_version/board_name. Not
# exhaustive — USB probing is tried first and will correctly identify any
# model not listed here.
LEGION_MODELS = {
    "legion 7 16iax10": {
        "label": "Legion 7i Gen 10 (16IAX10)",
        "keyboard": "perkey",
        "logo": True,
        "io_port": True,
    },
    "legion 7 16iax7": {
        "label": "Legion 7i (Gen 7/8, per-key)",
        "keyboard": "perkey",
        "logo": True,
        "io_port": False,
    },
    "legion 5 pro": {
        "label": "Legion 5 Pro (4-zone)",
        "keyboard": "4zone",
        "logo": False,
        "io_port": False,
    },
    "legion 5": {
        "label": "Legion 5 (4-zone)",
        "keyboard": "4zone",
        "logo": False,
        "io_port": False,
    },
    "legion slim 5": {
        "label": "Legion Slim 5 (4-zone)",
        "keyboard": "4zone",
        "logo": False,
        "io_port": False,
    },
    "loq": {
        "label": "LOQ (white backlight)",
        "keyboard": "white",
        "logo": False,
        "io_port": False,
    },
}

DEFAULT_CAPABILITIES = {
    "label": "Unknown Legion model",
    "keyboard": "none",
    "logo": False,
    "io_port": False,
}


def _dmi_identity() -> dict:
    return {
        "product_name": read_text(DMI / "product_name") or "",
        "product_version": read_text(DMI / "product_version") or "",
        "board_name": read_text(DMI / "board_name") or "",
    }


def _dmi_lookup(identity: dict) -> dict | None:
    haystacks = [
        identity.get("product_name", "").lower(),
        identity.get("product_version", "").lower(),
        identity.get("board_name", "").lower(),
    ]
    for needle, profile in LEGION_MODELS.items():
        if any(needle in h for h in haystacks if h):
            return profile
    return None


def _usb_keyboard_kind() -> str | None:
    if not USB_DEVICES.exists():
        return None
    found_perkey = False
    found_4zone = False
    for dev in USB_DEVICES.glob("*"):
        vid = read_text(dev / "idVendor")
        pid = read_text(dev / "idProduct")
        if not vid or not pid or vid.lower() != LENOVO_VID:
            continue
        pid = pid.lower()
        if pid in PERKEY_PIDS:
            found_perkey = True
        elif pid in FOURZONE_PIDS:
            found_4zone = True
    if found_perkey:
        return "perkey"
    if found_4zone:
        return "4zone"
    return None


def detect_model() -> dict:
    """Auto-detect capabilities. Does not consult the user override."""
    identity = _dmi_identity()
    dmi_profile = _dmi_lookup(identity)
    usb_kind = _usb_keyboard_kind()

    if usb_kind:
        capabilities = dict(dmi_profile) if dmi_profile else dict(DEFAULT_CAPABILITIES)
        capabilities["keyboard"] = usb_kind
        source = "usb"
    elif dmi_profile:
        capabilities = dict(dmi_profile)
        source = "dmi"
    else:
        capabilities = dict(DEFAULT_CAPABILITIES)
        source = "unknown"

    label = capabilities.get("label") or identity.get("product_name") or "Unknown Legion model"
    return {
        "source": source,
        "identity": identity,
        "label": label,
        "keyboard": capabilities.get("keyboard", "none"),
        "logo": bool(capabilities.get("logo")),
        "io_port": bool(capabilities.get("io_port")),
    }


def known_model_names() -> list[str]:
    return sorted({"auto", *LEGION_MODELS.keys()})


def get_model() -> dict:
    """Detected or user-overridden model, whichever applies."""
    saved = state.load()
    override = saved.get("model_override")
    detected = detect_model()
    if not override or override == "auto":
        detected["override"] = None
        return detected

    profile = LEGION_MODELS.get(override)
    if profile is None:
        result = dict(DEFAULT_CAPABILITIES)
        result["label"] = override
    else:
        result = dict(profile)
    return {
        "source": "override",
        "identity": detected["identity"],
        "label": result.get("label", override),
        "keyboard": result.get("keyboard", "none"),
        "logo": bool(result.get("logo")),
        "io_port": bool(result.get("io_port")),
        "override": override,
    }


def set_model_override(name: str | None) -> dict:
    saved = state.load()
    saved["model_override"] = name if name and name != "auto" else None
    state.save(saved)
    return get_model()
