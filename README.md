# Omarchy PoE 2

A local-first Omarchy bar addon for Path of Exile 2: launch the game and Scalpel,
open the official trade site, switch original/FSR4 rendering, and maintain the
OptiScaler setup after Steam patches.

## What it does

- Launches native Steam PoE 2, optionally starting Scalpel once alongside it.
- Opens PoE 2 Trade in your desktop's default browser.
- Finds PoE 2 across native Steam libraries, including libraries on other drives.
- Installs OptiScaler from its official stable GitHub release, with SHA-256 verification.
- Installs a user-owned Scalpel AppImage, or uses an existing `scalpel-poe` launcher.
- Checks both upstream releases on demand; no background network polling.
- Restores original game files and graphics preferences without resetting other Steam apps.
- Repairs missing files, graphics settings and the Steam DLL override after game updates.
- Keeps your FSR4 quality, watermark, menu key and logging preferences separate from
  OptiScaler's rewritten INI files, so `auto` values cannot silently become the saved preference.
- Stages changes with persistent backups and crash recovery; retains the previous
  OptiScaler release for rollback.

The addon is independent of Grinding Gear Games, OptiScaler and Scalpel. It is not an
upstream OptiScaler manager. No third-party binaries are redistributed in this repository.

## Requirements

- Omarchy's plugin-capable Quickshell bar on Hyprland; Linux x86_64.
- Python 3.10+, native Steam, `xdg-utils`, and `libarchive` (`bsdtar`).
- PoE 2 installed through Steam. Launch it once and exit before setting up FSR4.
- A recent GE-Proton or Proton Experimental selected in Steam's Compatibility settings.
- For FSR4: suitable GPU support and current Vulkan drivers. This release's preset targets
  **AMD RDNA2/3 INT8**, tested with an RX 6700 XT, Mesa 26.2.5 and GE-Proton 11-12.
  Mesa 25.2+ is the documented baseline. Other GPUs are not validated by this addon.
- Scalpel and the game should run through XWayland for the existing input hooks.
  The addon forces X11 only for Scalpel; it does not change the desktop session or Steam's environment.

On Omarchy, missing system dependencies can be installed with:

```bash
omarchy pkg add python steam libarchive xdg-utils
```

The Scalpel AppImage normally uses FUSE 2. If needed:

```bash
omarchy pkg add fuse2
```

Flatpak Steam, non-Steam installations, automatic Proton installation and automatic
GPU-driver upgrades are outside the supported setup. The addon never installs the
paid game or signs into accounts on your behalf.

## Install

With Omarchy's plugin manager:

```bash
omarchy plugin add https://github.com/usergood/omarchy-poe2 --enable --yes
```

Or from a reviewed local checkout:

```bash
git clone https://github.com/usergood/omarchy-poe2.git
cd omarchy-poe2
./install.sh
```

The local installer enables the new widget and disables the earlier
`local.poe2-profiles` prototype if present. The plugin-manager installation does not
run `install.sh`; if migrating, disable that prototype yourself to avoid duplicate widgets:

```bash
omarchy plugin disable local.poe2-profiles
```

Installing the plugin changes no game files. The addon itself makes no update or SDK download requests until you ask it to.

## First use

1. Install PoE 2 through native Steam, select a current Proton, launch the game once,
   then exit the game and fully exit Steam.
2. Open the gamepad icon in the bar. **Play** offers the game, Scalpel and trade site.
3. Under **Tools**, select **Install / Update FSR4**. The addon finds the game,
   downloads and verifies the official archive, backs up existing files, installs the
   SDKs, sets the DLL override for this game only, and selects the FSR4 profile.
4. Use an existing Scalpel installation, or select **Install / Update Scalpel AppImage**.
   The latter downloads a verified user-owned copy and leaves system packages intact.
5. Choose **Original** or **FSR4** under Play, then launch PoE 2.

Missing game, prefix or Steam-account settings produce actionable messages rather
than partially installing a mod. The **Install PoE 2 in Steam** button opens Steam's
own installation flow when the game is absent.

### Profiles and performance

**Original** restores game files and the graphics settings captured before the mod.
It normally uses Vulkan, but the addon preserves your actual original renderer.
**FSR4** selects DirectX 12, uses DLSS as OptiScaler's input, forces the SDK's INT8 model,
turns off dynamic resolution, and keeps frame generation disabled.

FSR4 improves image reconstruction but is not guaranteed to improve FPS. INT8 processing
on RDNA2 costs GPU time; the renderer and scaling preset also affect the comparison.
Under **Settings**, compare Quality, Balanced and Performance in the same scene.
First-run shader compilation can cause additional stutter. The addon does not silently
change graphics quality to conceal a performance regression.

The watermark is **off** and logging is **off** by default. Enable the watermark
briefly after an upgrade to verify `FSR4`/`FSR4-i8` rather than `FSR3` fallback.
Selecting FSR4 or seeing its DLL loaded alone does not establish that the model runs.
Diagnostic logging is Info-level only; per-frame Trace logging is never enabled.

The default OptiScaler menu key is `0xDC`: **§ on a Swedish layout**. It is a Windows
virtual key, not a Unicode character. Other layouts may map it differently. To change it:

```bash
python3 ~/.config/omarchy/plugins/usergood.poe2/backend.py configure --menu-key 0x79
```

`0x79` is F10. Restart the game after changing settings. Exit Steam first because
profile and preference changes may update game files and Steam's launch options.

### Steam updates and repair

The addon records the Steam build and ownership/hash of every installed file.
A changed build or missing/changed mod file is shown as **Profile needs repair**.
**Repair selected profile** reapplies the locally saved payload without a download.
**Install / Update FSR4** checks the latest official stable release, verifies its
archive, stages it, checks the supported INI schema, and applies it.

When a new Steam build replaces a file that originally belonged to the game, repair
keeps the newer Steam file as the original backup before reapplying OptiScaler. It
will not later restore the old game's DLL over that new version. Unexpected changes
to mod-owned binaries stop the operation rather than overwriting another mod.

A future OptiScaler release with an incompatible INI schema is deliberately rejected
before touching the game. Update this addon for a supported migration; the current
working release remains available. **Previous OptiScaler version** restores the
previous payload while retaining current backups of Steam-owned files.

Scalpel's system package is never overwritten. Managed AppImages live in your user
data directory; an existing Scalpel process must exit before replacement. Existing
Scalpel settings are preserved. On a clean first launch the addon seeds PoE 2-only
preferences. The launcher uses `XDG_SESSION_TYPE=x11` and `--ozone-platform=x11`.

### Other Steam libraries and accounts

Library paths are read from Steam's `libraryfolders.vdf`; no user or mount path is
hardcoded. The most recently used Steam account is preferred if multiple accounts
contain the game. If that is ambiguous, select the account explicitly:

```bash
python3 ~/.config/omarchy/plugins/usergood.poe2/backend.py configure --account 12345678
```

For an unusual native Steam root, use `configure --steam-root /path/to/Steam` before
installing FSR4. Library/account changes after setup are blocked until the original
installation is restored. After choosing Original, you can reset the registry before
selecting a different library or account (old backups remain available):

```bash
python3 ~/.config/omarchy/plugins/usergood.poe2/backend.py reset-setup
``` Data from another machine should not be copied over an
existing installation registry; install the addon there and initialize it normally.

## Data, network access and removal

State is stored under `~/.local/share/omarchy/poe2-addon/` (or `POE2_ADDON_DATA` for CLI tests):

- `preferences.json`: chosen quality, menu key, watermark and startup choices.
- `installation.json`: game build, selected profile, release and file ownership.
- `blobs/`: immutable content-addressed backups and SDK payloads.
- `payloads/`, `cache/`: verified releases for offline repair and rollback.
- `transaction.json`: recovery journal only while changing files.
- `scalpel-launch.log`: bounded launcher diagnostics, not game/chat contents.

No scheduled network access or telemetry is added. Update buttons contact only
`api.github.com`, the official upstream repositories and GitHub's release-asset hosts.
Launching Scalpel permits that application's own normal network behavior and update checks.
The trade shortcut opens `https://www.pathofexile.com/trade2` in the default browser.

To remove the game integration, exit PoE 2 and Steam and choose **Original** first.
Then remove the plugin:

```bash
omarchy plugin remove usergood.poe2 --yes
```

Keep the state directory until you are sure no backup or rollback is needed. Removing
the plugin itself does not automatically restore modified game files or delete backups.

## Troubleshooting and safety

OptiScaler's upstream warns against online/anti-cheat use. PoE 2 has an upstream
compatibility entry, but that is not a guarantee against account-policy changes.
Read the upstream documentation and decide whether to use the mod for your account.

If a switch was interrupted, exit Steam and the game and run:

```bash
python3 ~/.config/omarchy/plugins/usergood.poe2/backend.py recover
```

An unrecognized `dxgi.dll` is never overwritten. The earlier local prototype can be
adopted using its saved original-file backups when its binary hash matches; unrelated
mods require restoring their original files first. The addon does not run downloaded
setup scripts, silently enable frame generation, delete an unknown mod, or reset
unrelated Steam settings.

This is a local integration tool, not a guarantee of GPU/game performance. A supported
release still needs an in-game check for stability, price-checker focus and FSR4 output.

## Development

The backend uses only Python's standard library and external `bsdtar` for 7z archives.
It returns bounded JSON to QML; external text is shown using `Text.PlainText`, never rich text.

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q backend.py poe2
omarchy plugin validate .
```

Tests use temporary Steam libraries and synthetic SDK payloads. They cover fresh
setup, VDF escaping/scoping, restored settings, new Steam builds, missing files,
unknown-mod rejection, download integrity, archive paths and failed-write/crash recovery.
No CI test downloads or executes the actual game, OptiScaler or Scalpel.

Upstreams: [OptiScaler](https://github.com/optiscaler/OptiScaler),
[PoE 2 compatibility](https://github.com/optiscaler/OptiScaler/wiki/Path-of-Exile-2),
[Scalpel](https://github.com/scalpelpoe/scalpel). Their licenses remain their own.
