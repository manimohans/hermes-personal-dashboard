#!/usr/bin/env bash
set -euo pipefail

PLUGIN_NAME="hermes-personal-dashboard"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
HERMES_HOME="${HERMES_HOME:-"${HOME}/.hermes"}"
TARGET="${HERMES_HOME}/plugins/${PLUGIN_NAME}"

mkdir -p "${HERMES_HOME}/plugins"

if [ -e "${TARGET}" ] && [ ! -L "${TARGET}" ]; then
  echo "Target already exists and is not a symlink: ${TARGET}" >&2
  echo "Move it aside or install manually." >&2
  exit 1
fi

ln -sfn "${PLUGIN_DIR}" "${TARGET}"

echo "Installed ${PLUGIN_NAME} -> ${TARGET}"

if command -v hermes >/dev/null 2>&1; then
  echo
  echo "Next steps:"
  echo "  ./scripts/doctor.sh"
  echo "  hermes plugins enable ${PLUGIN_NAME}"
  echo "  hermes dashboard"
  echo
  echo "Then open the Personal Dashboard tab."
  echo "It scans existing Hermes memory and sessions automatically."
else
  echo
  echo "Hermes was not found on PATH."
  echo "After installing Hermes Agent, run:"
  echo "  hermes plugins enable ${PLUGIN_NAME}"
  echo "  hermes dashboard"
fi
