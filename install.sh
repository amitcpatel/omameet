#!/usr/bin/env bash
set -euo pipefail
plugin_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "${HOME}/.local/bin"
ln -sfn "${plugin_dir}/bin/omameet-calendar" "${HOME}/.local/bin/omameet-calendar"
ln -sfn "${plugin_dir}/bin/omameet-meetings" "${HOME}/.local/bin/omameet-meetings"
omarchy plugin add "${plugin_dir}" --enable --yes
echo "Installed acp.omameet. Right-click its bar icon to manage calendars."
