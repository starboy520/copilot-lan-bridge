#!/usr/bin/env bash
set -euo pipefail

app_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
expected_dir="$HOME/copilot-lan-bridge/study-agent"
unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
unit_file="$unit_dir/study-agent.service"

if [[ "$app_dir" != "$expected_dir" ]]; then
  printf 'The systemd unit expects Study Agent at %s.\n' "$expected_dir" >&2
  printf 'Current directory: %s\n' "$app_dir" >&2
  exit 1
fi

chmod +x "$app_dir/start.sh"
mkdir -p "$unit_dir"
install -m 0644 "$app_dir/scripts/study-agent.service" "$unit_file"

systemctl --user daemon-reload
systemctl --user enable --now study-agent.service

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

printf 'Study Agent is enabled and running.\n'
systemctl --user is-active study-agent.service
