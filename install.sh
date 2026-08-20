#!/usr/bin/env bash
set -euo pipefail
plugin_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "${HOME}/.local/bin"

# OmaMeet was renamed before its marketplace listing. Preserve data from local
# development installs without deleting or overwriting the legacy copy.
migrate_tree() {
  local legacy="$1"
  local current="$2"
  if [[ -d "${legacy}" && ! -e "${current}" ]]; then
    mkdir -p "$(dirname -- "${current}")"
    cp -a -- "${legacy}" "${current}"
    find "${current}" -type d -exec chmod 700 {} +
    find "${current}" -type f -exec chmod 600 {} +
    echo "Migrated existing data: ${legacy} -> ${current}"
  fi
}

commands=(omascribe-calendar omascribe-meetings)

# Validate every destination before changing any of them. Existing links are
# accepted only when they already resolve to this exact plugin checkout.
for command in "${commands[@]}"; do
  target="${plugin_dir}/bin/${command}"
  link="${HOME}/.local/bin/${command}"
  if [[ -e "${link}" || -L "${link}" ]]; then
    if [[ ! -L "${link}" || "$(readlink -f -- "${link}")" != "${target}" ]]; then
      echo "Refusing to replace existing command path: ${link}" >&2
      echo "Move or remove that path explicitly, then run install.sh again." >&2
      exit 1
    fi
  fi
done

migrate_tree "${XDG_CONFIG_HOME:-${HOME}/.config}/omarchy-meetings" \
  "${XDG_CONFIG_HOME:-${HOME}/.config}/omascribe"
migrate_tree "${XDG_STATE_HOME:-${HOME}/.local/state}/omarchy-meetings" \
  "${XDG_STATE_HOME:-${HOME}/.local/state}/omascribe"
migrate_tree "${XDG_CONFIG_HOME:-${HOME}/.config}/omarchy-calendar" \
  "${XDG_CONFIG_HOME:-${HOME}/.config}/omascribe-calendar"
migrate_tree "${XDG_STATE_HOME:-${HOME}/.local/state}/omarchy-calendar" \
  "${XDG_STATE_HOME:-${HOME}/.local/state}/omascribe-calendar"

for command in "${commands[@]}"; do
  target="${plugin_dir}/bin/${command}"
  link="${HOME}/.local/bin/${command}"
  [[ -L "${link}" ]] || ln -s -- "${target}" "${link}"
done
installed_dir="${HOME}/.config/omarchy/plugins/acp.omascribe"
if [[ "${plugin_dir}" != "${installed_dir}" ]]; then
  omarchy plugin add "${plugin_dir}" --enable --yes
else
  omarchy plugin enable acp.omascribe
fi
echo "OmaScribe is ready. Open the bar icon, then use the gear to connect Google Calendar."
