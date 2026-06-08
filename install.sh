#!/usr/bin/env bash
set -euo pipefail

PLUGIN_NAME="hermes-personal-dashboard"
REPO_URL="https://github.com/manimohans/hermes-personal-dashboard.git"
HERMES_HOME="${HERMES_HOME:-"${HOME}/.hermes"}"
TARGET="${HERMES_HOME}/plugins/${PLUGIN_NAME}"
YES=0
COPY_MODE=0
ENABLE=1
RUN_DOCTOR=1

usage() {
  cat <<'EOF'
Install Hermes Personal Dashboard.

Usage:
  ./install.sh [--yes] [--copy] [--no-enable] [--skip-doctor]

Options:
  --yes          Do not prompt before replacing an existing symlink.
  --copy         Copy this checkout instead of symlinking when run locally.
  --no-enable    Do not run `hermes plugins enable hermes-personal-dashboard`.
  --skip-doctor  Do not run the plugin doctor after install.

The script works from a local checkout or through:
  curl -fsSL https://raw.githubusercontent.com/manimohans/hermes-personal-dashboard/main/install.sh | bash
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --yes|-y) YES=1 ;;
    --copy) COPY_MODE=1 ;;
    --no-enable) ENABLE=0 ;;
    --skip-doctor) RUN_DOCTOR=0 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 1 ;;
  esac
  shift
done

mkdir -p "${HERMES_HOME}/plugins"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" >/dev/null 2>&1 && pwd || pwd)"
LOCAL_CHECKOUT=0
if [ -f "${SCRIPT_DIR}/plugin.yaml" ] && [ -f "${SCRIPT_DIR}/personal_dashboard_core.py" ]; then
  LOCAL_CHECKOUT=1
fi

replace_symlink() {
  local source_dir="$1"
  if [ -e "${TARGET}" ] || [ -L "${TARGET}" ]; then
    if [ -L "${TARGET}" ]; then
      if [ "${YES}" -ne 1 ]; then
        printf 'Replace existing symlink %s? [y/N] ' "${TARGET}"
        read -r answer
        case "${answer}" in
          y|Y|yes|YES) ;;
          *) echo "Install cancelled."; exit 1 ;;
        esac
      fi
      rm "${TARGET}"
    elif [ "${TARGET}" != "${source_dir}" ]; then
      echo "Target already exists and is not a symlink: ${TARGET}" >&2
      echo "Move it aside, or run from a fresh Hermes plugins directory." >&2
      exit 1
    fi
  fi
  ln -s "${source_dir}" "${TARGET}"
}

if [ "${LOCAL_CHECKOUT}" -eq 1 ]; then
  if [ "${COPY_MODE}" -eq 1 ]; then
    if [ -e "${TARGET}" ] && [ "${TARGET}" != "${SCRIPT_DIR}" ]; then
      echo "Target already exists: ${TARGET}" >&2
      exit 1
    fi
    mkdir -p "${TARGET}"
    (cd "${SCRIPT_DIR}" && tar --exclude .git -cf - .) | (cd "${TARGET}" && tar -xf -)
  elif [ "${TARGET}" != "${SCRIPT_DIR}" ]; then
    replace_symlink "${SCRIPT_DIR}"
  fi
else
  if ! command -v git >/dev/null 2>&1; then
    echo "git is required to install from ${REPO_URL}." >&2
    echo "Install git, or clone the repository manually and run ./install.sh from the checkout." >&2
    exit 1
  fi
  if [ -d "${TARGET}/.git" ]; then
    git -C "${TARGET}" pull --ff-only
  elif [ -e "${TARGET}" ]; then
    echo "Target already exists and is not a Git checkout: ${TARGET}" >&2
    exit 1
  else
    git clone "${REPO_URL}" "${TARGET}"
  fi
fi

echo "Installed ${PLUGIN_NAME} at ${TARGET}"

if command -v hermes >/dev/null 2>&1; then
  if [ "${ENABLE}" -eq 1 ]; then
    if hermes plugins enable "${PLUGIN_NAME}"; then
      echo "Enabled ${PLUGIN_NAME} in Hermes."
    else
      echo "Could not enable automatically. Run: hermes plugins enable ${PLUGIN_NAME}" >&2
    fi
  fi
else
  echo "Hermes was not found on PATH. Install Hermes, then run:"
  echo "  hermes plugins enable ${PLUGIN_NAME}"
fi

if [ "${RUN_DOCTOR}" -eq 1 ] && [ -x "${TARGET}/scripts/doctor.sh" ]; then
  "${TARGET}/scripts/doctor.sh" || true
fi

cat <<EOF

Next:
  hermes dashboard

Open the Personal Dashboard tab. No configuration is required; it reflects
existing Hermes memory, sessions, cron output, and agent work automatically.
EOF
