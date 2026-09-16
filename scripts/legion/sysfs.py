"""Safe sysfs helpers. Never write outside /sys."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from .log import get_logger

log = get_logger("sysfs")

_SAFE_VALUE = re.compile(r"^[A-Za-z0-9._+-]+$")


def read_text(path: Path | str) -> str | None:
    try:
        p = Path(path)
        if p.is_file():
            return p.read_text().strip()
    except OSError:
        pass
    return None


def read_int(path: Path | str) -> int | None:
    raw = read_text(path)
    if raw is None:
        return None
    try:
        return int(raw.split()[0], 0)
    except (ValueError, IndexError):
        return None


def write_direct(path: Path, value: str) -> bool:
    try:
        if path.is_file():
            path.write_text(str(value))
            return True
    except OSError as exc:
        log.debug("Direct write failed path=%s value=%s: %s", path, value, exc)
    return False


def write_pkexec(path: Path, value: str) -> bool:
    if not str(path).startswith("/sys/") or not _SAFE_VALUE.match(str(value)):
        log.warning("Refused pkexec write outside /sys or unsafe value: path=%s value=%r", path, value)
        return False
    try:
        result = subprocess.run(
            ["pkexec", "tee", str(path)],
            input=str(value) + "\n",
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            log.warning(
                "pkexec write failed path=%s value=%s rc=%d stderr=%s",
                path, value, result.returncode, result.stderr.strip(),
            )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired) as exc:
        log.warning("pkexec write raised path=%s value=%s: %s", path, value, exc)
        return False


def safe_write(path: Path | str, value: str) -> dict:
    p = Path(path)
    if write_direct(p, value):
        return {"status": "success", "method": "direct"}
    if write_pkexec(p, value):
        return {"status": "success", "method": "pkexec"}
    log.warning("safe_write exhausted all methods path=%s value=%s", p, value)
    return {"status": "error", "message": f"Failed to write {value} to {p}"}


def first_existing(*paths: Path | str) -> Path | None:
    for raw in paths:
        p = Path(raw)
        if p.exists():
            return p
    return None


def external_power_online() -> bool:
    """True when the laptop is running from a charger.

    Match on the supply's type, not its name: the barrel adapter is AC* on
    some Legions but ADP0 on others (e.g. the 16IAX10), and a USB-C charger
    shows up as a type=USB supply."""
    for supply in Path("/sys/class/power_supply").iterdir():
        if read_text(supply / "type") in ("Mains", "USB") and read_text(supply / "online") == "1":
            return True
    return False


def run_cmd(args: list[str], timeout: float = 2.0) -> str | None:
    try:
        res = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        if res.returncode == 0:
            return res.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None
