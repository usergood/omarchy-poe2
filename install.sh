#!/usr/bin/env bash
set -euo pipefail
source_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
plugin_id=usergood.poe2
plugin_dir="${XDG_CONFIG_HOME:-$HOME/.config}/omarchy/plugins/$plugin_id"
for program in python3 omarchy omarchy-shell; do
  command -v "$program" >/dev/null || { echo "Missing required command: $program" >&2; exit 1; }
done
omarchy plugin validate "$source_dir"
if [[ "$source_dir" != "$plugin_dir" ]]; then
  if [[ -d "$plugin_dir" ]]; then
    backup_dir="${XDG_DATA_HOME:-$HOME/.local/share}/omarchy/poe2-addon/plugin-backups/$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$backup_dir"
    cp -a "$plugin_dir/." "$backup_dir/"
  fi
  mkdir -p "$plugin_dir"
  cp "$source_dir/manifest.json" "$source_dir/Panel.qml" "$source_dir/PlainText.qml" "$source_dir/SectionCard.qml" "$source_dir/StatusBadge.qml" "$source_dir/ShortcutRecorder.qml" "$source_dir/ShortcutKeys.js" "$source_dir/RepairPrompt.qml" "$source_dir/backend.py" "$plugin_dir/"
  cp -r "$source_dir/poe2" "$source_dir/i18n" "$source_dir/assets" "$plugin_dir/"
fi
omarchy-shell shell rescanPlugins
# Shell discovery is asynchronous; a catalog read waits for the rescan round trip.
omarchy plugin list --json >/dev/null
omarchy plugin enable "$plugin_id" --section right
# Replace the earlier local prototype only after the new widget is enabled.
if omarchy plugin list --json | python3 -c 'import json,sys;sys.exit(not any(x["id"]=="local.poe2-profiles" for x in json.load(sys.stdin)))'; then
  omarchy plugin disable local.poe2-profiles
fi
printf '%s\n' 'PoE 2 addon enabled. Open the gold waystone II icon in the bar.'
printf '%s\n' 'No game files have been changed. Use Tools in the addon to install FSR4.'
