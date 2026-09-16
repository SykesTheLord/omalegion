# Legion Control Center

An [Omarchy](https://omarchy.org/) bar widget that adds a Lenovo Legion control
center to the shell. Click the bar icon to open a panel with power, GPU,
battery, cooling, and RGB lighting controls synced with your laptop firmware
and Omarchy's battery profile and theme.

This project is a fork of
[tedwester/omalegion](https://github.com/tedwester/omalegion) ("Legion
Toolkit"), extended with automatic keyboard-model detection and lighting
control (keyboard RGB, logo, theme sync) that the original plugin didn't
have. It builds on several community projects — see [Credits](#credits).
License: [MIT](LICENSE).

## Features

### Bar widget

- Compact Legion icon on the bar with live tooltip (power mode, battery
  profile, CPU temperature).
- Icon badge reflects power mode and thermal state (blue = quiet, white =
  balanced, accent = performance, purple = extreme/custom). Optional monochrome
  bar icon in the Misc tab.
- Click to open or close the control panel.

### Overview

- Power mode, CPU/GPU temperatures, fan RPM, battery level, and GPU status at
  a glance.
- Fn lock and keyboard backlight controls.

### Power

- Legion thermal modes (Quiet, Balanced, Performance, Extreme, Custom) via
  `platform_profile`, synced with Omarchy's power-profiles-daemon battery
  panel.
- Custom mode PPT (power limit) tuning when supported.
- The power limits in effect for the current profile.
- Optional password-free profile switching, including Custom (see
  [Switching profiles without a password](#switching-profiles-without-a-password)).

### GPU

- Hybrid / dGPU-only / iGPU-only working modes.
- dGPU deactivate, overclock controls, and active GPU process list.

### Battery

- Charge modes (normal, conservation, rapid charge, overnight).
- Always-on USB charging toggle.

### Cooling

- Fan mode presets and manual fan speed when PWM is available.
- Live thermal sensors and short temperature/fan history charts.

### Lighting

Legion laptops use three incompatible keyboard-lighting hardware families,
none of which have a Linux sysfs/WMI interface today — every control path
goes over raw USB HID feature reports:

| Kind | Example models | What you get |
|------|-----------------|---------------|
| White single-zone | LOQ / budget Y-series | On/off + brightness (reuses the plain `/sys/class/leds` path) |
| 4-zone RGB (ITE8291) | Legion 5 / 5 Pro / Slim 5, 2020–2024 | Brightness, 9 effects, one color per zone |
| Per-key "Spectrum" RGB (ITE8258) | Legion 7(i) / Pro 7, Gen 9/10 | Brightness, effects per zone (keyboard/perimeter/logo), solid color, named key-group presets (WASD, arrows, numpad, F-keys), and a per-key editor drawn as your actual keyboard |

The **model detector** (Overview → "Keyboard Model" on the Lighting tab)
combines two signals, matching how community Legion-lighting tools identify
hardware: it first scans for known Lenovo/ITE USB device IDs (authoritative —
this is what actually determines the protocol), then falls back to matching
the DMI product name/version against a small built-in model table. You can
always override the detected model from the dropdown if your exact model
isn't recognized or you want to force a specific lighting backend.

**Per-key editor**: drawn as your real keyboard. Its physical format (ANSI,
ISO or JIS) is read from the keyboard and decides where keys are and how big
they are. The labels follow the keyboard layout your system is using
(Hyprland's active layout, or `localectl` outside Hyprland), looked up through
libxkbcommon, so a Danish layout shows Æ, Ø, Å and `'`. If the keyboard can't
be read, the format is guessed from the system layout. The JIS layout hasn't
been tested on real hardware.

**Sync to Omarchy theme**: enable this toggle to keep the keyboard's solid
color matched to the active theme. It reads the theme's `keyboard.rgb` file
if present (already an existing Omarchy theme convention — themes like
`tokyo-night` ship one), falling back to the theme's `colors.toml` `accent`
color otherwise, and re-applies automatically whenever you run
`omarchy theme set ...` (installed as a `theme-set` hook the first time you
enable the toggle).

**Known limitations**: the per-key and 4-zone protocols were reverse-engineered
by the community (no vendor documentation), and the 4-zone implementation in
particular couldn't be tested against real hardware for this plugin — if your
4-zone keyboard doesn't respond, the dedicated
[ite8291r3-ctl](https://github.com/pobrn/ite8291r3-ctl) or
[L5P-Keyboard-RGB](https://github.com/4JX/L5P-Keyboard-RGB) tools (which use
raw USB control transfers instead of hidraw feature reports) are the more
battle-tested fallback. The IO-port light bar present on some models is
detected and shown as a capability, but has no known Linux control protocol
yet, so it isn't controllable from here.

### Misc

- Monochrome bar icon toggle.
- Plugin version and quick links.

## Requirements

- Omarchy 4 (Quattro) or newer with the current shell plugin API.
- A Lenovo Legion laptop with Linux sysfs support (`lenovo-wmi-gamezone` or
  equivalent `platform_profile` interface).
- `python3` on `PATH` (used by the bundled hardware engine).
- `pkexec` (PolicyKit) for sysfs writes when direct writes are not permitted,
  and for the one-time lighting-permissions install below.

Optional:

- libxkbcommon (installed with Hyprland) for per-key editor labels that match
  your keyboard layout. Without it, keys are labelled as a US layout.
- The `legion-laptop` kernel module from
  [johnfanv2/LenovoLegionLinux](https://github.com/johnfanv2/LenovoLegionLinux)
  for full PWM fan curves. Without it, fan RPM is read-only on many kernels.
- For lighting: install the udev rule from the Lighting tab's "Install
  lighting permissions" button (one-time, needs your password) so lighting
  changes don't need a password prompt every time. Without it, lighting
  writes will silently fail once your session's own hidraw access runs out
  (typically none by default).

## Installation

```bash
omarchy plugin add <path-or-git-url-to-this-repo> --enable --yes
```

Omarchy clones/copies the plugin into
`~/.config/omarchy/plugins/sykesthelord.legion/` and enables the widget on the
right bar section by default.

If the icon does not appear after install:

```bash
omarchy bar put sykesthelord.legion --section right --after omarchy.tray
```

### Testing a local checkout

From a clone of this repository, re-run this after each change:

```bash
./install.sh                 # copy, validate, enable if needed, restart the shell
./install.sh --no-restart    # same, without restarting the shell
./install.sh --permissions   # also install the lighting udev rule (asks for your password)
```

It copies the checkout into `~/.config/omarchy/plugins/sykesthelord.legion/`
(Omarchy doesn't load symlinked plugins), removes files that no longer exist in
the checkout, checks that the hardware engine runs, and leaves the widget's bar
placement alone if it's already enabled. Requires `jq` and `rsync`.

### Manual installation

Copy the complete plugin directory to
`~/.config/omarchy/plugins/sykesthelord.legion/`, then run:

```bash
omarchy-shell shell rescanPlugins
omarchy plugin enable sykesthelord.legion --section right
```

## Usage

- Click the Legion icon on the bar to open or close the panel.
- Switch tabs: Overview, Power, GPU, Battery, Cooling, Lighting, Misc.
- Changes that write to sysfs may prompt for your password via PolicyKit.
- Press `Escape` to close the panel.

## Switching profiles without a password

Quiet, Balanced and Performance switch through power-profiles-daemon without a
password. Extreme and Custom can only be set by writing a root-only kernel
file, so by default they ask for your password each time. To avoid that:

```bash
./install.sh --profile-helper
# or, from an installed copy:
pkexec ~/.config/omarchy/plugins/sykesthelord.legion/helpers/install-profile-helper.sh
```

This installs two files, owned by root:

- `/usr/local/libexec/legion-set-profile`, a small script that accepts only a
  profile name, writes only the kernel's platform profile file, and refuses
  Performance, Extreme and Custom on battery.
- `/usr/share/polkit-1/actions/com.sykesthelord.legion.set-profile.policy`,
  which lets the person logged in at the laptop run that one script without a
  password. Remote and inactive sessions still need an administrator password.

The plugin only uses the helper when it's owned by root and not writable by
anyone else. The tradeoff: any program running as you can switch profiles
without asking, which could mean heat, fan noise or battery drain, but not
changes to the power limits themselves — those still ask for a password.

## Uninstalling

```bash
omarchy plugin remove sykesthelord.legion --yes
```

This disables the plugin and removes it from the shell. The plugin also stores
rolling thermal history at `~/.config/omarchy/legion_history.json`, panel
state at `~/.config/omarchy/legion_state.json`, and (if you installed lighting
permissions) a udev rule at `/etc/udev/rules.d/99-legion-lighting.rules`.
Delete these manually if you no longer want them; the udev rule needs
`pkexec rm /etc/udev/rules.d/99-legion-lighting.rules`. If theme sync was ever
enabled, also remove
`~/.config/omarchy/hooks/theme-set.d/theme-set-lighting-sync` (there's no
`omarchy hook remove` command; delete the file directly). If you installed the
profile helper, remove it before removing the plugin:
`pkexec ~/.config/omarchy/plugins/sykesthelord.legion/helpers/install-profile-helper.sh --uninstall`.

## What the plugin writes

- Sysfs nodes under `/sys/` (power profile, GPU mode, battery settings, fan
  controls) only when you change a setting in the panel.
- `/dev/hidraw*` feature reports for keyboard/logo lighting, only when you
  change a lighting setting.
- `/etc/udev/rules.d/99-legion-lighting.rules`, only if you click "Install
  lighting permissions".
- `/usr/local/libexec/legion-set-profile` and
  `/usr/share/polkit-1/actions/com.sykesthelord.legion.set-profile.policy`, only
  if you install the profile helper.
- `~/.config/omarchy/hooks/theme-set.d/`, only if you enable "Sync to Omarchy
  theme" (installs one hook script that re-applies the keyboard color on
  theme changes; it no-ops when sync is off).
- `~/.config/omarchy/legion_history.json` for short in-panel temperature and
  fan charts.
- `~/.config/omarchy/legion_state.json` for panel toggles (GPU overclock,
  overnight charging, model override, lighting brightness/effect/color, theme
  sync).

Enabling or disabling the plugin does not modify your bar layout beyond what
Omarchy's plugin enable flow already manages.

## Credits

This tool would not exist without the following projects. Each is listed
with its license and what this plugin took from it.

| Project | License | Used for |
|---------|---------|----------|
| [tedwester/omalegion](https://github.com/tedwester/omalegion) | MIT | The original plugin this is forked from: the bar widget and panel, the Python hardware engine, and the power, GPU, battery, cooling and input features. |
| [alstergee/legion-spectrum-control](https://github.com/alstergee/legion-spectrum-control) | MIT | The per-key "Spectrum" (ITE8258) protocol — report framing, operation codes, effect encoding — plus the keycode tables and key names, adapted into `scripts/legion/lighting_perkey.py`. |
| [LenovoLegionToolkit](https://github.com/LenovoLegionToolkit-Team/LenovoLegionToolkit) (originally [BartoszCichecki/LenovoLegionToolkit](https://github.com/BartoszCichecki/LenovoLegionToolkit)) | GPL-3.0 | The reference implementation the Spectrum protocol was reverse-engineered from. Its key-grid and key-page queries and its ANSI/ISO/JIS layout detection were used as the reference for reading the key list from the keyboard, and its ANSI, ISO and JIS keyboard layouts as the reference for the key positions and sizes in the per-key editor and for which keycode is which key. The bar and panel logo (`assets/logo.png`) also comes from this project, carried over from omalegion. |
| [pobrn/ite8291r3-ctl](https://github.com/pobrn/ite8291r3-ctl) | GPL-2.0-only | Reference for 4-zone (ITE8291) keyboards and their USB device IDs. |
| [4JX/L5P-Keyboard-RGB](https://github.com/4JX/L5P-Keyboard-RGB) | GPL-3.0 | The per-year USB product ID table for 4-zone Legion keyboards, used for model detection. |
| [Lenovo Legion keyboard lights (kaveh.page)](https://kaveh.page/snippets/lenovo-legion-keyboard-lights) | — | Write-up of the 4-zone HID report layout (`0xCC 0x16` header) used by `scripts/legion/lighting_4zone.py`. |
