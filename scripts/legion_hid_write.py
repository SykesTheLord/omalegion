#!/usr/bin/env python3
"""Standalone root-side helper for one HID SET_FEATURE write.

Invoked via `pkexec` by lighting_common.py only as a fallback for when the
99-legion-lighting.rules udev ACL hasn't taken effect yet (it doesn't apply
retroactively to a device that was already attached before the rule was
installed — a reboot or re-login is needed for that). Kept intentionally
tiny and dependency-free since it runs as root.
"""

from __future__ import annotations

import fcntl
import sys

_IOC_WRITE = 1
_IOC_READ = 2


def _hidiocsfeature(size: int) -> int:
    return ((_IOC_WRITE | _IOC_READ) << 30) | (ord("H") << 8) | 0x06 | (size << 16)


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: legion_hid_write.py <device> <hex-payload>", file=sys.stderr)
        return 1
    device, hex_payload = sys.argv[1], sys.argv[2]
    try:
        payload = bytes.fromhex(hex_payload)
        with open(device, "r+b", buffering=0) as fh:
            buf = bytearray(payload)
            fcntl.ioctl(fh, _hidiocsfeature(len(buf)), buf)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
