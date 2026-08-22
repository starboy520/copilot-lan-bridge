#!/usr/bin/env bash
set -euo pipefail

config_dir="${XDG_CONFIG_HOME:-$HOME/.config}/copilot-lan-bridge"
key_file="$config_dir/api-key"
venv_dir="${COPILOT_BRIDGE_VENV:-$HOME/.venvs/copilot-lan-bridge}"

mkdir -p "$config_dir"
chmod 700 "$config_dir"

if [[ ! -s "$key_file" ]]; then
  umask 077
  "$venv_dir/bin/python" -c "import secrets; print(secrets.token_hex(32))" > "$key_file"
fi
chmod 600 "$key_file"

export COPILOT_BRIDGE_HOST="${COPILOT_BRIDGE_HOST:-0.0.0.0}"
export COPILOT_BRIDGE_PORT="${COPILOT_BRIDGE_PORT:-18787}"
export COPILOT_BRIDGE_API_KEY="$(<"$key_file")"
export OPENCODE_AUTH_FILE="${OPENCODE_AUTH_FILE:-$HOME/.local/share/opencode/auth.json}"

exec "$venv_dir/bin/copilot-lan-bridge"