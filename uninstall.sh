#!/usr/bin/env bash
set -euo pipefail

plugin_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
for command in omameet-calendar omameet-meetings; do
  link="${HOME}/.local/bin/${command}"
  if [[ -L "${link}" && "$(readlink -f -- "${link}")" == "${plugin_dir}/bin/${command}" ]]; then
    unlink "${link}"
  fi
done

echo "Removed OmaMeet command links. Run 'omarchy plugin remove acp.omameet' to remove the plugin."
echo "Your settings, calendar sources, recordings, and notes were kept."
