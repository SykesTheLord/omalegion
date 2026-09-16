"""Shared HID plumbing for Legion RGB lighting.

Legion keyboard/logo lighting has no sysfs or WMI interface on Linux today —
every known open-source controller (ite8291r3-ctl, L5P-Keyboard-RGB,
legion-spectrum-control) talks directly to the lighting chip's USB HID
feature reports. We do the same over /dev/hidraw*, using the HIDIOCSFEATURE/
HIDIOCGFEATURE ioctls, so no third-party dependency (pyusb/hidapi) is needed —
consistent with the rest of this plugin's stdlib-only engine.

Report Legion's own lsusb-visible VID (048d, "Lenovo"/ITE) devices; the
matching PID tells us which chip (and therefore protocol module) to use —
see model.py.
"""

from __future__ import annotations

import fcntl
import struct
import subprocess
from pathlib import Path

from .log import get_logger

log = get_logger("lighting")

HIDRAW_DIR = Path("/sys/class/hidraw")

# linux/ioctl.h direction/size encoding (matches every mainstream Linux arch).
_IOC_WRITE = 1
_IOC_READ = 2
_IOC_NRSHIFT = 0
_IOC_TYPESHIFT = 8
_IOC_SIZESHIFT = 16
_IOC_DIRSHIFT = 30


def _ioc(direction: int, ioc_type: int, nr: int, size: int) -> int:
    return (
        (direction << _IOC_DIRSHIFT)
        | (ioc_type << _IOC_TYPESHIFT)
        | (nr << _IOC_NRSHIFT)
        | (size << _IOC_SIZESHIFT)
    )


def _hidiocsfeature(size: int) -> int:
    return _ioc(_IOC_WRITE | _IOC_READ, ord("H"), 0x06, size)


def _hidiocgfeature(size: int) -> int:
    return _ioc(_IOC_WRITE | _IOC_READ, ord("H"), 0x07, size)


def find_hidraw(vid: str, pids: set[str]) -> Path | None:
    """Return the /dev/hidrawN path for the first Lenovo device matching one
    of `pids` (lowercase hex, no colons)."""
    if not HIDRAW_DIR.exists():
        return None
    for node in HIDRAW_DIR.glob("hidraw*"):
        uevent = node / "device" / "uevent"
        try:
            text = uevent.read_text()
        except OSError:
            continue
        hid_id = None
        for line in text.splitlines():
            if line.startswith("HID_ID="):
                hid_id = line.split("=", 1)[1]
                break
        if not hid_id:
            continue
        parts = hid_id.split(":")
        if len(parts) != 3:
            continue
        _bus, hex_vid, hex_pid = parts
        # HID_ID vendor/product are 8-hex-digit, zero-padded, upper-case.
        found_vid = hex_vid[-4:].lower()
        found_pid = hex_pid[-4:].lower()
        if found_vid == vid.lower() and found_pid in pids:
            return Path("/dev") / node.name
    log.debug("No hidraw device found for vid=%s pids=%s", vid, sorted(pids))
    return None


_HID_WRITE_HELPER = Path(__file__).resolve().parent.parent / "legion_hid_write.py"


def _send_feature_report_pkexec(device: Path, payload: bytes) -> bool:
    """Fallback for when the udev uaccess ACL hasn't applied yet (it doesn't
    apply retroactively to a device already attached before the rule was
    installed — see 99-legion-lighting.rules). Prompts for a password every
    call, so it's a bridge until the user reboots/re-logs in, not a
    replacement for the ACL."""
    try:
        result = subprocess.run(
            ["pkexec", "python3", str(_HID_WRITE_HELPER), str(device), payload.hex()],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            log.warning(
                "pkexec HID write failed device=%s len=%d rc=%d stderr=%s",
                device, len(payload), result.returncode, result.stderr.strip(),
            )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired) as exc:
        log.warning("pkexec HID write raised device=%s: %s", device, exc)
        return False


def send_feature_report(device: Path, payload: bytes) -> bool:
    """Send a HID SET_FEATURE report. `payload[0]` must be the report id."""
    try:
        with open(device, "r+b", buffering=0) as fh:
            buf = bytearray(payload)
            fcntl.ioctl(fh, _hidiocsfeature(len(buf)), buf)
        log.debug("SET_FEATURE ok device=%s report_id=0x%02x len=%d", device, payload[0], len(payload))
        return True
    except PermissionError as exc:
        log.warning(
            "SET_FEATURE denied device=%s report_id=0x%02x len=%d: %s (falling back to pkexec)",
            device, payload[0] if payload else -1, len(payload), exc,
        )
        return _send_feature_report_pkexec(device, payload)
    except OSError as exc:
        log.warning(
            "SET_FEATURE failed device=%s report_id=0x%02x len=%d: %s",
            device, payload[0] if payload else -1, len(payload), exc,
        )
        return False


def get_feature_report(device: Path, report_id: int, length: int) -> bytes | None:
    try:
        with open(device, "r+b", buffering=0) as fh:
            buf = bytearray(length)
            buf[0] = report_id
            fcntl.ioctl(fh, _hidiocgfeature(length), buf)
        return bytes(buf)
    except OSError as exc:
        log.warning("GET_FEATURE failed device=%s report_id=0x%02x: %s", device, report_id, exc)
        return None


def clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, int(value)))


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    v = value.strip().lstrip("#")
    if len(v) != 6:
        return (255, 255, 255)
    try:
        return struct.unpack("BBB", bytes.fromhex(v))
    except ValueError:
        return (255, 255, 255)
