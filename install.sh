#!/usr/bin/env bash
set -euo pipefail
plugin_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "${HOME}/.local/bin"

commands=(omameet-calendar omameet-meetings)

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

for command in "${commands[@]}"; do
  target="${plugin_dir}/bin/${command}"
  link="${HOME}/.local/bin/${command}"
  [[ -L "${link}" ]] || ln -s -- "${target}" "${link}"
done
installed_dir="${HOME}/.config/omarchy/plugins/acp.omameet"
if [[ "${plugin_dir}" != "${installed_dir}" ]]; then
  omarchy plugin add "${plugin_dir}" --enable --yes
else
  omarchy plugin enable acp.omameet
fi
echo "OmaMeet is ready. Open the bar icon, then use the gear to connect Google Calendar."
