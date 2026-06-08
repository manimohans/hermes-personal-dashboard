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
LAUNCHER_DIR="${HPD_LAUNCHER_DIR:-"${HOME}/.local/bin"}"
LAUNCHER="${LAUNCHER_DIR}/${APP_NAME}"

HOST="127.0.0.1"
PORT="9119"
OPEN_BROWSER=1
INSECURE=0
SKIP_BUILD=0
RUN_DOCTOR=0
START_SERVER=1
WITH_PLUGIN=0
ENABLE_PLUGIN=1
REMOVE_EXISTING=0
UNINSTALL_ONLY=0
COPY_MODE=0
UPDATE_INSTALL=1
FOREGROUND=0
STRICT_PORT=0
YES=0

usage() {
  cat <<'EOF'
Install, build-check, and run Hermes Personal Dashboard.

Usage:
  ./run.sh [options]

Common:
  --lan                  Raspberry Pi / server shortcut:
                         --host 0.0.0.0 --insecure --no-open
  --host HOST            Bind address. Default: 127.0.0.1
  --port PORT            Preferred port. Default: 9119
  --insecure             Allow non-localhost binding. Use only on trusted LANs.
  --no-open              Do not open a browser.
  --open                 Open a browser after the server starts.

Install:
  --remove-existing      Stop and remove an existing install before installing.
  --uninstall            Stop and remove existing install, then exit.
  --copy                 Copy this checkout instead of symlinking when run locally.
  --with-plugin          Also install optional Hermes plugin/tool bundle.
  --no-enable            With --with-plugin, do not run `hermes plugins enable`.
  --no-update            Do not git pull an existing cloned install.

Run:
  --foreground           Run in the foreground instead of daemonizing.
  --no-start             Install and build-check only.
  --strict-port          Fail if --port is busy instead of choosing the next port.
  --skip-build           Skip JavaScript/Python build checks.
  --doctor               Run scripts/doctor.sh after install/build-check.
  --yes, -y              Do not prompt.
  --help, -h             Show this help.

Examples:
  ./run.sh
  ./run.sh --lan
  ./run.sh --host 0.0.0.0 --port 9119 --insecure --no-open
  curl -fsSL https://raw.githubusercontent.com/manimohans/hermes-personal-dashboard/main/run.sh | bash -s -- --lan
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --lan) HOST="0.0.0.0"; INSECURE=1; OPEN_BROWSER=0 ;;
    --host) HOST="${2:?Missing host}"; shift ;;
    --port) PORT="${2:?Missing port}"; shift ;;
    --insecure) INSECURE=1 ;;
    --no-open) OPEN_BROWSER=0 ;;
    --open) OPEN_BROWSER=1 ;;
    --remove-existing) REMOVE_EXISTING=1 ;;
    --uninstall) REMOVE_EXISTING=1; UNINSTALL_ONLY=1 ;;
    --copy) COPY_MODE=1 ;;
    --with-plugin) WITH_PLUGIN=1 ;;
    --no-enable) ENABLE_PLUGIN=0 ;;
    --no-update) UPDATE_INSTALL=0 ;;
    --foreground) FOREGROUND=1 ;;
    --background) FOREGROUND=0 ;;
    --no-start) START_SERVER=0 ;;
    --strict-port) STRICT_PORT=1 ;;
    --skip-build) SKIP_BUILD=1 ;;
    --doctor) RUN_DOCTOR=1 ;;
    --skip-doctor) RUN_DOCTOR=0 ;;
    --yes|-y) YES=1 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 1 ;;
  esac
  shift
done

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

is_loopback_host() {
  case "$1" in
    127.0.0.1|localhost|::1) return 0 ;;
    *) return 1 ;;
  esac
}

require_safe_bind() {
  if ! is_loopback_host "${HOST}" && [ "${INSECURE}" -ne 1 ]; then
    cat >&2 <<EOF
Refusing to bind Hermes Personal Dashboard to ${HOST} without --insecure.

This dashboard reflects Hermes memory, sessions, cron output, and prior work.
For a Raspberry Pi or trusted LAN, run:

  ./run.sh --host ${HOST} --port ${PORT} --insecure --no-open

Or use the shortcut:

  ./run.sh --lan
EOF
    exit 1
  fi
}

validate_port() {
  case "${PORT}" in
    ''|*[!0-9]*)
      echo "Invalid port: ${PORT}" >&2
      exit 1
      ;;
  esac
  if [ "${PORT}" -lt 1 ] || [ "${PORT}" -gt 65535 ]; then
    echo "Port must be between 1 and 65535: ${PORT}" >&2
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
    if [ "${UPDATE_INSTALL}" -eq 1 ]; then
      git -C "${APP_TARGET}" pull --ff-only
    fi
  elif [ -e "${APP_TARGET}" ]; then
    echo "Install target already exists: ${APP_TARGET}" >&2
    echo "Run again with --remove-existing for a clean install." >&2
    exit 1
  else
    git clone "${REPO_URL}" "${APP_TARGET}"
  fi
}

ensure_install() {
  mkdir -p "${INSTALL_ROOT}" "${RUN_DIR}"
  if [ "${LOCAL_CHECKOUT}" -eq 1 ]; then
    install_from_local
  else
    install_from_git
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
  echo "Installed optional Hermes plugin link at ${PLUGIN_TARGET}"
  if command -v hermes >/dev/null 2>&1 && [ "${ENABLE_PLUGIN}" -eq 1 ]; then
    hermes plugins enable "${APP_NAME}" || true
  fi
}

write_launcher() {
  mkdir -p "${LAUNCHER_DIR}"
  cat > "${LAUNCHER}" <<EOF
#!/usr/bin/env bash
export HERMES_HOME="${HERMES_HOME}"
exec "$(python_cmd)" "${APP_TARGET}/standalone/server.py" "\$@"
EOF
  chmod +x "${LAUNCHER}"
}

build_web_ui() {
  if [ "${SKIP_BUILD}" -eq 1 ]; then
    echo "Skipping build checks."
    return
  fi
  echo "Preparing web UI assets."
  [ -f "${APP_TARGET}/standalone/index.html" ] || { echo "Missing standalone/index.html" >&2; exit 1; }
  [ -f "${APP_TARGET}/standalone/app.js" ] || { echo "Missing standalone/app.js" >&2; exit 1; }
  [ -f "${APP_TARGET}/dashboard/dist/index.js" ] || { echo "Missing dashboard/dist/index.js" >&2; exit 1; }
  [ -f "${APP_TARGET}/dashboard/dist/style.css" ] || { echo "Missing dashboard/dist/style.css" >&2; exit 1; }

  local py
  py="$(python_cmd)"
  "${py}" -m py_compile \
    "${APP_TARGET}/__init__.py" \
    "${APP_TARGET}/dashboard/plugin_api.py" \
    "${APP_TARGET}/personal_dashboard_core.py" \
    "${APP_TARGET}/schemas.py" \
    "${APP_TARGET}/standalone/server.py"

  if command -v node >/dev/null 2>&1; then
    node --check "${APP_TARGET}/dashboard/dist/index.js"
    node --check "${APP_TARGET}/standalone/app.js"
    echo "Web UI build checks passed."
  else
    echo "Node not found; using shipped prebuilt web UI assets."
  fi
}

port_available() {
  local host="$1"
  local port="$2"
  local py
  py="$(python_cmd)"
  "${py}" - "${host}" "${port}" <<'PY'
import socket
import sys

host = sys.argv[1]
port = int(sys.argv[2])
family = socket.AF_INET6 if ":" in host and host != "0.0.0.0" else socket.AF_INET
sock = socket.socket(family, socket.SOCK_STREAM)
try:
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
except OSError:
    sys.exit(1)
finally:
    sock.close()
PY
}

choose_port() {
  local candidate="${PORT}"
  local limit=$((PORT + 20))
  if [ "${limit}" -gt 65535 ]; then
    limit=65535
  fi
  while ! port_available "${HOST}" "${candidate}"; do
    if [ "${STRICT_PORT}" -eq 1 ]; then
      echo "Port ${candidate} is already in use. Stop that server or choose --port." >&2
      exit 1
    fi
    candidate=$((candidate + 1))
    if [ "${candidate}" -gt "${limit}" ]; then
      echo "Could not find a free port near ${PORT}." >&2
      exit 1
    fi
  done
  if [ "${candidate}" != "${PORT}" ]; then
    echo "Port ${PORT} is busy; using ${candidate}."
  fi
  PORT="${candidate}"
}

lan_ip() {
  local py
  py="$(python_cmd)"
  "${py}" - <<'PY'
import socket

fallback = "127.0.0.1"
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
try:
    sock.connect(("8.8.8.8", 80))
    ip = sock.getsockname()[0]
except OSError:
    ip = fallback
finally:
    sock.close()
print(ip or fallback)
PY
}

health_host() {
  if [ "${HOST}" = "0.0.0.0" ] || [ "${HOST}" = "::" ]; then
    echo "127.0.0.1"
  elif [ "${HOST}" = "localhost" ]; then
    echo "127.0.0.1"
  else
    echo "${HOST}"
  fi
}

wait_for_health() {
  local py
  local host
  py="$(python_cmd)"
  host="$(health_host)"
  "${py}" - "${host}" "${PORT}" <<'PY'
import json
import sys
import time
from urllib.request import urlopen

host = sys.argv[1]
port = sys.argv[2]
url = f"http://{host}:{port}/api/plugins/hermes-personal-dashboard/health"
deadline = time.time() + 12
last_error = None
while time.time() < deadline:
    try:
        with urlopen(url, timeout=1.5) as response:
            data = json.loads(response.read().decode("utf-8"))
        if data.get("ok"):
            sys.exit(0)
    except Exception as exc:
        last_error = exc
        time.sleep(0.5)
print(f"Health check failed for {url}: {last_error}", file=sys.stderr)
sys.exit(1)
PY
}

primary_url() {
  if [ "${HOST}" = "0.0.0.0" ] || [ "${HOST}" = "::" ]; then
    printf 'http://%s:%s\n' "$(lan_ip)" "${PORT}"
  else
    printf 'http://%s:%s\n' "${HOST}" "${PORT}"
  fi
}

local_url() {
  printf 'http://127.0.0.1:%s\n' "${PORT}"
}

open_browser() {
  if [ "${OPEN_BROWSER}" -ne 1 ]; then
    return
  fi
  local url
  if [ "${HOST}" = "0.0.0.0" ] || [ "${HOST}" = "::" ]; then
    url="$(local_url)"
  else
    url="$(primary_url)"
  fi
  if command -v open >/dev/null 2>&1; then
    open "${url}" >/dev/null 2>&1 || true
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "${url}" >/dev/null 2>&1 || true
  else
    "$(python_cmd)" -m webbrowser "${url}" >/dev/null 2>&1 || true
  fi
}

print_ready() {
  local url
  local loopback_url
  url="$(primary_url)"
  loopback_url="$(local_url)"
  cat <<EOF

Hermes Personal Dashboard is ready.

Open:
  ${url}
EOF
  if [ "${url}" != "${loopback_url}" ]; then
    cat <<EOF
  ${loopback_url}
EOF
  fi

  cat <<EOF

Install:
  ${APP_TARGET}

Log:
  ${LOG_FILE}

Stop:
EOF
  if [ "${FOREGROUND}" -eq 1 ]; then
    cat <<'EOF'
  Press Ctrl-C
EOF
  else
    cat <<EOF
  kill \$(cat "${PID_FILE}")
EOF
  fi

  cat <<'EOF'

Clean reinstall:
  ./run.sh --remove-existing --yes
EOF
  if ! is_loopback_host "${HOST}"; then
    cat <<'EOF'

Security:
  This is running in LAN/insecure mode. Do not expose this port to the public internet.
EOF
  fi
}

start_background() {
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
    sed -n '1,120p' "${LOG_FILE}" >&2 || true
    rm -f "${PID_FILE}"
    exit 1
  fi
  if ! wait_for_health; then
    echo "Server started but did not pass health check. Log:" >&2
    sed -n '1,120p' "${LOG_FILE}" >&2 || true
    exit 1
  fi
}

start_foreground() {
  local py
  py="$(python_cmd)"
  print_ready
  exec "${py}" "${APP_TARGET}/standalone/server.py" --host "${HOST}" --port "${PORT}" --hermes-home "${HERMES_HOME}"
}

validate_port
require_safe_bind

if [ "${REMOVE_EXISTING}" -eq 1 ]; then
  if [ "${YES}" -ne 1 ] && [ "${UNINSTALL_ONLY}" -eq 0 ]; then
    printf 'Remove existing %s install first? [y/N] ' "${APP_NAME}"
    read -r answer
    case "${answer}" in
      y|Y|yes|YES) ;;
      *) echo "Run cancelled."; exit 1 ;;
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

ensure_install
write_launcher
build_web_ui

if [ "${WITH_PLUGIN}" -eq 1 ]; then
  install_plugin_link
fi

if [ "${RUN_DOCTOR}" -eq 1 ] && [ -x "${APP_TARGET}/scripts/doctor.sh" ]; then
  "${APP_TARGET}/scripts/doctor.sh" || true
fi

if [ "${START_SERVER}" -ne 1 ]; then
  echo "Installed and build-checked ${APP_NAME} at ${APP_TARGET}"
  echo "Run: ${LAUNCHER} --host ${HOST} --port ${PORT}"
  exit 0
fi

choose_port

if [ "${FOREGROUND}" -eq 1 ]; then
  start_foreground
else
  start_background
  open_browser
  print_ready
fi
