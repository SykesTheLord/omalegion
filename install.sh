#!/usr/bin/env bash
# Install this working copy into Omarchy for testing.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./install.sh [--no-restart] [--permissions] [--profile-helper]

Copies this checkout into ~/.config/omarchy/plugins/<plugin id>, enables the
widget if it isn't already enabled, and restarts the Omarchy shell.

  --no-restart      Don't restart the shell afterwards.
  --permissions     Also install the udev rule that gives lighting access
                    without a password prompt (asks for your password once).
  --profile-helper  Also install the root-owned helper that switches power
                    profiles, including Custom, without a password prompt
                    (asks for your password once).
  -h, --help        Show this help.
EOF
}

fail() {
  echo "install.sh: $*" >&2
  exit 1
}

restart=1
permissions=0
profile_helper=0
for arg in "$@"; do
  case $arg in
    --no-restart) restart=0 ;;
    --permissions) permissions=1 ;;
    --profile-helper) profile_helper=1 ;;
    -h | --help) usage; exit 0 ;;
    *) usage >&2; fail "unknown option: $arg" ;;
  esac
done

for cmd in omarchy jq rsync python3; do
  command -v "$cmd" >/dev/null || fail "'$cmd' is required"
done

src=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

omarchy plugin validate "$src" || fail "the plugin in $src doesn't pass validation"

id=$(jq -r '.id // empty' "$src/manifest.json")
# The id becomes a directory that rsync --delete writes into, so never let an
# empty or odd id point it at the plugins folder itself.
[[ $id =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ && $id != *..* ]] || fail "unexpected plugin id '$id'"
dest="$HOME/.config/omarchy/plugins/$id"

echo "Installing $id -> $dest"
mkdir -p "$dest"
# Omarchy refuses symlinked plugins, so this is a copy. --delete removes files
# that no longer exist in the checkout, and --delete-excluded also clears
# dev-only files left by an older install (Python regenerates its caches).
rsync -a --delete --delete-excluded \
  --exclude '.git/' \
  --exclude '.gitignore' \
  --exclude '.claude/' \
  --exclude '__pycache__/' \
  --exclude '*.py[cod]' \
  --exclude 'install.sh' \
  --exclude 'tests/' \
  "$src/" "$dest/"

omarchy plugin validate "$dest" || fail "the installed copy doesn't pass validation"

if ! python3 "$dest/scripts/legion_engine.py" | jq -e 'has("power") and has("lighting")' >/dev/null; then
  fail "the hardware engine didn't produce valid output; see ~/.config/omarchy/legion_debug.log"
fi
echo "Engine check passed"

# Enabling places the widget on the bar, so skip it when already enabled to
# keep wherever the widget has been moved to.
if omarchy plugin list --json | jq -e --arg id "$id" 'any(.[]; .id == $id and .enabled)' >/dev/null; then
  echo "$id is already enabled"
else
  omarchy plugin enable "$id"
fi

if (( permissions )); then
  python3 "$dest/scripts/legion_engine.py" --install-lighting-permissions |
    jq -r '"Lighting permissions: " + .status + (if .message then " — " + .message else "" end)'
fi

if (( profile_helper )); then
  pkexec "$dest/helpers/install-profile-helper.sh" || fail "the profile helper wasn't installed"
fi

if (( restart )); then
  if omarchy restart shell; then
    echo "Shell restarted"
  else
    echo "install.sh: the shell wasn't restarted (is the session locked?); run 'omarchy restart shell' later" >&2
  fi
fi

echo "Done"
