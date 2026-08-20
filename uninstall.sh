#!/usr/bin/env bash
set -euo pipefail

plugin_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
for command in omascribe-calendar omascribe-meetings; do
  link="${HOME}/.local/bin/${command}"
  if [[ -L "${link}" && "$(readlink -f -- "${link}")" == "${plugin_dir}/bin/${command}" ]]; then
    unlink "${link}"
  fi
done

echo "Removed OmaScribe command links. Run 'omarchy plugin remove acp.omascribe' to remove the plugin."
echo "Your settings, calendar sources, recordings, and notes were kept."
