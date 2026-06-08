#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://raw.githubusercontent.com/manimohans/hermes-personal-dashboard/main/run.sh"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" >/dev/null 2>&1 && pwd || pwd)"

if [ -x "${SCRIPT_DIR}/run.sh" ]; then
  exec "${SCRIPT_DIR}/run.sh" "$@"
fi

if command -v curl >/dev/null 2>&1; then
  curl -fsSL "${REPO_URL}" | bash -s -- "$@"
elif command -v wget >/dev/null 2>&1; then
  wget -qO- "${REPO_URL}" | bash -s -- "$@"
else
  echo "curl or wget is required to fetch run.sh." >&2
  exit 1
fi
