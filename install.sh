#!/usr/bin/env bash
set -euo pipefail
plugin_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "${HOME}/.local/bin"
ln -sfn "${plugin_dir}/bin/omameet-calendar" "${HOME}/.local/bin/omameet-calendar"
ln -sfn "${plugin_dir}/bin/omameet-meetings" "${HOME}/.local/bin/omameet-meetings"
installed_dir="${HOME}/.config/omarchy/plugins/acp.omameet"
if [[ "${plugin_dir}" != "${installed_dir}" ]]; then
  omarchy plugin add "${plugin_dir}" --enable --yes
else
  omarchy plugin enable acp.omameet --yes
fi
echo "OmaMeet is ready. Open the bar icon, then right-click it to add a calendar."
