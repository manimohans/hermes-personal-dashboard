#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PLUGIN_NAME="hermes-personal-dashboard"
HERMES_HOME="${HERMES_HOME:-"${HOME}/.hermes"}"
TARGET="${HERMES_HOME}/plugins/${PLUGIN_NAME}"

ok() {
  printf 'OK   %s\n' "$1"
}

warn() {
  printf 'WARN %s\n' "$1"
}

fail() {
  printf 'FAIL %s\n' "$1"
  exit 1
}

cd "${ROOT}"

echo "Hermes Personal Dashboard doctor"
echo

[ -f plugin.yaml ] || fail "plugin.yaml not found"
[ -f __init__.py ] || fail "__init__.py not found"
[ -f dashboard/manifest.json ] || fail "dashboard/manifest.json not found"
[ -f dashboard/plugin_api.py ] || fail "dashboard/plugin_api.py not found"
[ -f dashboard/dist/index.js ] || fail "dashboard/dist/index.js not found"
[ -f dashboard/dist/style.css ] || fail "dashboard/dist/style.css not found"
[ -f skills/briefing-curator/SKILL.md ] || fail "briefing-curator skill not found"
ok "plugin file layout"

python3 -m py_compile __init__.py dashboard/plugin_api.py personal_dashboard_core.py schemas.py
ok "Python files compile"

if command -v node >/dev/null 2>&1; then
  node --check dashboard/dist/index.js
  ok "dashboard JavaScript parses"
else
  warn "node not found; skipped dashboard JavaScript syntax check"
fi

python3 - <<'PY'
import importlib.util
import sys
import tempfile
import types
from pathlib import Path

root = Path.cwd()
parent = "hermes_plugins"
if parent not in sys.modules:
    ns = types.ModuleType(parent)
    ns.__path__ = []
    ns.__package__ = parent
    sys.modules[parent] = ns

name = "hermes_plugins.hermes_personal_dashboard_doctor"
spec = importlib.util.spec_from_file_location(name, root / "__init__.py", submodule_search_locations=[str(root)])
if spec is None or spec.loader is None:
    raise SystemExit("could not load plugin module spec")
mod = importlib.util.module_from_spec(spec)
mod.__package__ = name
mod.__path__ = [str(root)]
sys.modules[name] = mod
spec.loader.exec_module(mod)

class Ctx:
    def __init__(self):
        self.tools = {}
        self.commands = {}
        self.skills = {}

    def register_tool(self, **kwargs):
        self.tools[kwargs["name"]] = kwargs

    def register_command(self, name, handler, description=""):
        self.commands[name] = handler

    def register_skill(self, name, path):
        self.skills[name] = str(path)

ctx = Ctx()
mod.register(ctx)
expected = 13
if len(ctx.tools) != expected:
    raise SystemExit(f"expected {expected} tools, found {len(ctx.tools)}")
if "personal-dashboard" not in ctx.commands:
    raise SystemExit("slash command was not registered")
if "briefing-curator" not in ctx.skills:
    raise SystemExit("briefing-curator skill was not registered")
print("OK   plugin registers tools, slash command, and skill")
PY

python3 - <<'PY'
import personal_dashboard_core as core

sources = core.collect_hermes_sources(include_sessions=True, include_cron=True)
report = core.build_source_report(sources)
by_type = report.get("by_type") or {}
checks = report.get("checks") or {}

print(f"OK   source scan ready ({report.get('source_count', 0)} readable source(s))")
if by_type:
    print("     source types: " + ", ".join(f"{key}={value}" for key, value in sorted(by_type.items())))
else:
    print("     source types: none yet")

memory_files = [item for item in checks.get("memory_files", []) if item.get("exists")]
state_db = checks.get("state_db") or {}
cron_jobs = checks.get("cron_jobs") or {}
cron_output = checks.get("cron_output") or {}
print(f"     memory files: {len(memory_files)}")
print(f"     state.db: {'found' if state_db.get('exists') else 'not found'}")
print(f"     cron jobs: {'found' if cron_jobs.get('exists') else 'not found'}")
print(f"     cron output files: {cron_output.get('file_count', 0)}")
PY

if command -v hermes >/dev/null 2>&1; then
  ok "hermes command found"
else
  warn "hermes command not found on PATH"
fi

if [ -e "${TARGET}" ]; then
  if [ -L "${TARGET}" ]; then
    ok "installed symlink exists at ${TARGET}"
  else
    ok "installed plugin directory exists at ${TARGET}"
  fi
else
  warn "plugin is not installed at ${TARGET}"
  echo "     Run: ./install.sh"
fi

echo
echo "Next useful commands:"
echo "  ./install.sh"
echo "  hermes plugins enable ${PLUGIN_NAME}"
echo "  hermes dashboard"
echo "  /personal-dashboard status"
