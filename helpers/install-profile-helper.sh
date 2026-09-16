#!/bin/bash
# Install (or with --uninstall, remove) the passwordless power profile helper.
# Run once as root: pkexec /path/to/install-profile-helper.sh [--uninstall]
set -euo pipefail
export PATH=/usr/bin:/bin

HELPER_DEST=/usr/local/libexec/legion-set-profile
POLICY_DEST=/usr/share/polkit-1/actions/com.sykesthelord.legion.set-profile.policy

fail() {
  echo "install-profile-helper: $*" >&2
  exit 1
}

(( EUID == 0 )) || fail "must run as root (pkexec or sudo)"

case ${1:-} in
  --uninstall)
    rm -f "$HELPER_DEST" "$POLICY_DEST"
    rmdir /usr/local/libexec 2>/dev/null || true
    echo "Removed the profile helper and its polkit policy"
    exit 0
    ;;
  "") ;;
  *) fail "usage: install-profile-helper.sh [--uninstall]" ;;
esac

src=$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)
bash -n "$src/legion-set-profile" || fail "the helper has a syntax error; not installing it"

# The helper runs as root without a password, so it must live somewhere only
# root can modify — never the plugin folder in the user's home.
install -d -o root -g root -m 0755 /usr/local/libexec
install -o root -g root -m 0755 "$src/legion-set-profile" "$HELPER_DEST"
install -o root -g root -m 0644 "$src/com.sykesthelord.legion.set-profile.policy" "$POLICY_DEST"
echo "Installed $HELPER_DEST and $POLICY_DEST"
