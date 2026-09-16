"""Small persisted plugin state (overnight charge, GPU OC preference)."""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path

STATE_FILE = Path.home() / ".config" / "omarchy" / "legion_state.json"
LOCK_FILE = STATE_FILE.with_suffix(".lock")
DEFAULTS = {
    "overnight": False,
    "overnight_hold_applied": False,
    "gpu_oc": False,
    "last_platform_profile": None,
    "last_ppd": None,
    "model_override": None,
    "lighting_on": True,
    "lighting_brightness": 5,
    "lighting_effect": "static",
    "lighting_color": "#ffffff",
    "lighting_logo_on": True,
    "sync_theme": False,
    "theme_sync_hook_installed": False,
    # Short-lived cache of values read back from the lighting controller.
    # Lives on disk because each engine command is its own process.
    "perkey_status": None,
    "perkey_status_at": 0,
    # Keycodes read from the keyboard itself (differs between ANSI/ISO/JIS).
    "perkey_keymap": None,
    # Key labels computed from the system keyboard layout, reused until the
    # layout or the keyboard format changes.
    "perkey_legends": None,
}


@contextmanager
def _locked():
    # The panel's poll and a user action run as separate engine processes at
    # the same time, so every write to the state file is serialized.
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOCK_FILE, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def load() -> dict:
    data = dict(DEFAULTS)
    if STATE_FILE.exists():
        try:
            saved = json.loads(STATE_FILE.read_text())
            if isinstance(saved, dict):
                data.update(saved)
        except (OSError, json.JSONDecodeError):
            pass
    return data


def _write(data: dict) -> None:
    merged = dict(DEFAULTS)
    merged.update(data)
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    # A per-write temp name; a fixed one let concurrent processes rename it
    # away from each other mid-write.
    fd, tmp = tempfile.mkstemp(dir=STATE_FILE.parent, prefix=".legion_state.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(json.dumps(merged))
        os.replace(tmp, STATE_FILE)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def save(data: dict) -> None:
    with _locked():
        _write(data)


def update(**changes) -> dict:
    """Atomically apply just these keys on top of the current file, so a
    background writer can't overwrite a change another process made between
    its own load() and save()."""
    with _locked():
        data = load()
        data.update(changes)
        _write(data)
        return data
