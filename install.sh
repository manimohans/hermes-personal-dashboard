#!/usr/bin/env bash
set -euo pipefail

APP_NAME="hermes-personal-dashboard"
REPO_URL="https://github.com/manimohans/hermes-personal-dashboard.git"
HERMES_HOME="${HERMES_HOME:-"${HOME}/.hermes"}"
INSTALL_ROOT="${HERMES_PRODUCTS_HOME:-"${HERMES_HOME}/products"}"
APP_TARGET="${INSTALL_ROOT}/${APP_NAME}"
PLUGIN_TARGET="${HERMES_HOME}/plugins/${APP_NAME}"
RUN_DIR="${HERMES_HOME}/run"
PID_FILE="${RUN_DIR}/${APP_NAME}.pid"
LOG_FILE="${RUN_DIR}/${APP_NAME}.log"
LAUNCHER_DIR="${HOME}/.local/bin"
LAUNCHER="${LAUNCHER_DIR}/${APP_NAME}"

YES=0
COPY_MODE=0
RUN_DOCTOR=1
START_SERVER=1
WITH_PLUGIN=0
ENABLE_PLUGIN=1
REMOVE_EXISTING=0
HOST="0.0.0.0"
PORT="9119"

usage() {
  cat <<'EOF'
Install Hermes Personal Dashboard as a standalone web app.

Usage:
  ./install.sh [options]

Options:
  --host HOST             Host to bind. Default: 0.0.0.0
  --port PORT             Port to serve. Default: 9119
  --no-start              Install only; do not start the server.
  --copy                  Copy this checkout instead of symlinking when run locally.
  --with-plugin           Also install as a Hermes dashboard/plugin tool bundle.
  --no-enable             With --with-plugin, do not run `hermes plugins enable`.
  --skip-doctor           Do not run the doctor after install.
  --remove-existing       Stop and remove existing standalone/plugin installs first.
  --uninstall             Stop and remove existing installs, then exit.
  --yes, -y               Do not prompt.
  --help, -h              Show this help.

One-line install:
  curl -fsSL https://raw.githubusercontent.com/manimohans/hermes-personal-dashboard/main/install.sh | bash
EOF
}

UNINSTALL_ONLY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --host) HOST="${2:?Missing host}"; shift ;;
    --port) PORT="${2:?Missing port}"; shift ;;
    --no-start) START_SERVER=0 ;;
    --copy) COPY_MODE=1 ;;
    --with-plugin) WITH_PLUGIN=1 ;;
    --no-enable) ENABLE_PLUGIN=0 ;;
    --skip-doctor) RUN_DOCTOR=0 ;;
    --remove-existing) REMOVE_EXISTING=1 ;;
    --uninstall) REMOVE_EXISTING=1; UNINSTALL_ONLY=1 ;;
    --yes|-y) YES=1 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 1 ;;
  esac
  shift
done

mkdir -p "${INSTALL_ROOT}" "${RUN_DIR}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" >/dev/null 2>&1 && pwd || pwd)"
LOCAL_CHECKOUT=0
if [ -f "${SCRIPT_DIR}/plugin.yaml" ] && [ -f "${SCRIPT_DIR}/personal_dashboard_core.py" ]; then
  LOCAL_CHECKOUT=1
fi
RUNNING_FROM_APP_TARGET=0
if [ "${SCRIPT_DIR}" = "${APP_TARGET}" ]; then
  RUNNING_FROM_APP_TARGET=1
fi

python_cmd() {
  if command -v python3 >/dev/null 2>&1; then
    command -v python3
  elif command -v python >/dev/null 2>&1; then
    command -v python
  else
    echo "python3 is required." >&2
    exit 1
  fi
}

stop_running() {
  if [ -f "${PID_FILE}" ]; then
    local pid
    pid="$(cat "${PID_FILE}" 2>/dev/null || true)"
    if [ -n "${pid}" ] && kill -0 "${pid}" >/dev/null 2>&1; then
      echo "Stopping existing ${APP_NAME} server (${pid})."
      kill "${pid}" >/dev/null 2>&1 || true
      sleep 1
      if kill -0 "${pid}" >/dev/null 2>&1; then
        kill -9 "${pid}" >/dev/null 2>&1 || true
      fi
    fi
    rm -f "${PID_FILE}"
  fi
}

remove_existing() {
  stop_running
  rm -rf "${APP_TARGET}"
  if [ -L "${PLUGIN_TARGET}" ]; then
    rm -f "${PLUGIN_TARGET}"
  elif [ -d "${PLUGIN_TARGET}" ] && [ -f "${PLUGIN_TARGET}/plugin.yaml" ]; then
    if grep -q "name: ${APP_NAME}" "${PLUGIN_TARGET}/plugin.yaml"; then
      rm -rf "${PLUGIN_TARGET}"
    fi
  fi
  rm -f "${LAUNCHER}"
  echo "Removed existing ${APP_NAME} installation."
}

install_from_local() {
  if [ "${COPY_MODE}" -eq 1 ]; then
    if [ -e "${APP_TARGET}" ] && [ "${APP_TARGET}" != "${SCRIPT_DIR}" ]; then
      echo "Install target already exists: ${APP_TARGET}" >&2
      echo "Run again with --remove-existing for a clean install." >&2
      exit 1
    fi
    mkdir -p "${APP_TARGET}"
    (cd "${SCRIPT_DIR}" && tar --exclude .git --exclude __pycache__ -cf - .) | (cd "${APP_TARGET}" && tar -xf -)
  elif [ "${APP_TARGET}" != "${SCRIPT_DIR}" ]; then
    if [ -e "${APP_TARGET}" ] || [ -L "${APP_TARGET}" ]; then
      if [ -L "${APP_TARGET}" ]; then
        rm -f "${APP_TARGET}"
      else
        echo "Install target already exists: ${APP_TARGET}" >&2
        echo "Run again with --remove-existing for a clean install." >&2
        exit 1
      fi
    fi
    ln -s "${SCRIPT_DIR}" "${APP_TARGET}"
  fi
}

install_from_git() {
  if ! command -v git >/dev/null 2>&1; then
    echo "git is required to install from ${REPO_URL}." >&2
    exit 1
  fi
  if [ -d "${APP_TARGET}/.git" ]; then
    git -C "${APP_TARGET}" pull --ff-only
  elif [ -e "${APP_TARGET}" ]; then
    echo "Install target already exists: ${APP_TARGET}" >&2
    echo "Run again with --remove-existing for a clean install." >&2
    exit 1
  else
    git clone "${REPO_URL}" "${APP_TARGET}"
  fi
}

install_plugin_link() {
  mkdir -p "${HERMES_HOME}/plugins"
  if [ -e "${PLUGIN_TARGET}" ] || [ -L "${PLUGIN_TARGET}" ]; then
    if [ -L "${PLUGIN_TARGET}" ]; then
      rm -f "${PLUGIN_TARGET}"
    else
      echo "Hermes plugin target already exists: ${PLUGIN_TARGET}" >&2
      echo "Run again with --remove-existing for a clean install." >&2
      exit 1
    fi
  fi
  ln -s "${APP_TARGET}" "${PLUGIN_TARGET}"
  echo "Installed Hermes plugin link at ${PLUGIN_TARGET}"
  if command -v hermes >/dev/null 2>&1 && [ "${ENABLE_PLUGIN}" -eq 1 ]; then
    hermes plugins enable "${APP_NAME}" || true
  fi
}

write_launcher() {
  mkdir -p "${LAUNCHER_DIR}"
  cat > "${LAUNCHER}" <<EOF
#!/usr/bin/env bash
exec "$(python_cmd)" "${APP_TARGET}/standalone/server.py" "\$@"
EOF
  chmod +x "${LAUNCHER}"
}

start_server() {
  stop_running
  local py
  py="$(python_cmd)"
  echo "Starting ${APP_NAME} on ${HOST}:${PORT}."
  nohup "${py}" "${APP_TARGET}/standalone/server.py" --host "${HOST}" --port "${PORT}" --hermes-home "${HERMES_HOME}" > "${LOG_FILE}" 2>&1 &
  local pid=$!
  echo "${pid}" > "${PID_FILE}"
  sleep 1
  if ! kill -0 "${pid}" >/dev/null 2>&1; then
    echo "Server failed to start. Log:" >&2
    sed -n '1,80p' "${LOG_FILE}" >&2 || true
    rm -f "${PID_FILE}"
    exit 1
  fi
}

lan_ip() {
  if command -v hostname >/dev/null 2>&1; then
    hostname -I 2>/dev/null | awk '{print $1}' || true
  fi
}

if [ "${REMOVE_EXISTING}" -eq 1 ]; then
  if [ "${YES}" -ne 1 ] && [ "${UNINSTALL_ONLY}" -eq 0 ]; then
    printf 'Remove existing %s install first? [y/N] ' "${APP_NAME}"
    read -r answer
    case "${answer}" in
      y|Y|yes|YES) ;;
      *) echo "Install cancelled."; exit 1 ;;
    esac
  fi
  remove_existing
  if [ "${RUNNING_FROM_APP_TARGET}" -eq 1 ]; then
    LOCAL_CHECKOUT=0
  fi
fi

if [ "${UNINSTALL_ONLY}" -eq 1 ]; then
  exit 0
fi

if [ "${LOCAL_CHECKOUT}" -eq 1 ]; then
  install_from_local
else
  install_from_git
fi

write_launcher

if [ "${WITH_PLUGIN}" -eq 1 ]; then
  install_plugin_link
fi

echo "Installed ${APP_NAME} at ${APP_TARGET}"
echo "Launcher: ${LAUNCHER}"

if [ "${RUN_DOCTOR}" -eq 1 ] && [ -x "${APP_TARGET}/scripts/doctor.sh" ]; then
  "${APP_TARGET}/scripts/doctor.sh" || true
fi

if [ "${START_SERVER}" -eq 1 ]; then
  start_server
fi

IP="$(lan_ip)"
if [ -z "${IP}" ]; then
  IP="127.0.0.1"
fi

cat <<EOF

Hermes Personal Dashboard is ready.

Open:
  http://${IP}:${PORT}

Log:
  ${LOG_FILE}

Stop:
  kill \$(cat "${PID_FILE}")

Clean reinstall:
  ./install.sh --remove-existing --yes
EOF
