#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
unit_file="$unit_dir/copilot-lan-bridge.service"

if [[ "$repo_dir" != "$HOME/copilot-lan-bridge" ]]; then
  printf 'The systemd unit expects the repository at %s/copilot-lan-bridge.\n' "$HOME" >&2
  printf 'Current repository: %s\n' "$repo_dir" >&2
  exit 1
fi

mkdir -p "$unit_dir"
install -m 0644 "$repo_dir/scripts/copilot-lan-bridge.service" "$unit_file"

systemctl --user daemon-reload
systemctl --user enable --now copilot-lan-bridge.service

if command -v loginctl >/dev/null 2>&1; then
  if ! loginctl show-user "$USER" -p Linger --value 2>/dev/null | grep -qx yes; then
    if sudo -n loginctl enable-linger "$USER" 2>/dev/null; then
      printf 'Enabled systemd linger for %s.\n' "$USER"
    else
      printf 'Run this once to enable startup before login:\n' >&2
      printf '  sudo loginctl enable-linger %q\n' "$USER" >&2
    fi
  fi
fi

printf 'Copilot LAN Bridge is enabled and running.\n'
systemctl --user is-active copilot-lan-bridge.service