from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_plugin():
    parent = "hermes_plugins"
    if parent not in sys.modules:
        ns = types.ModuleType(parent)
        ns.__path__ = []
        ns.__package__ = parent
        sys.modules[parent] = ns
    module_name = "hermes_plugins.hermes_personal_dashboard_test"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, ROOT / "__init__.py", submodule_search_locations=[str(ROOT)])
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    module.__package__ = module_name
    module.__path__ = [str(ROOT)]
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class FakeContext:
    def __init__(self) -> None:
        self.tools = {}
        self.commands = {}
        self.skills = {}

    def register_tool(self, **kwargs):
        self.tools[kwargs["name"]] = kwargs

    def register_command(self, name, handler, description=""):
        self.commands[name] = {"handler": handler, "description": description}

    def register_skill(self, name, path):
        self.skills[name] = str(path)


class PluginRegistrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_home = os.environ.get("HERMES_HOME")
        os.environ["HERMES_HOME"] = self.tmp.name
        self.plugin = load_plugin()
        self.ctx = FakeContext()
        self.plugin.register(self.ctx)

    def tearDown(self) -> None:
        if self.old_home is None:
            os.environ.pop("HERMES_HOME", None)
        else:
            os.environ["HERMES_HOME"] = self.old_home
        self.tmp.cleanup()

    def call_tool(self, name: str, params: dict):
        result = self.ctx.tools[name]["handler"](params)
        payload = json.loads(result)
        self.assertTrue(payload["success"], payload.get("error"))
        return payload["data"]

    def test_registers_full_user_friendly_surface(self) -> None:
        self.assertEqual(len(self.ctx.tools), 13)
        self.assertIn("personal_dashboard_refresh_from_hermes", self.ctx.tools)
        self.assertIn("personal_dashboard_list_context", self.ctx.tools)
        self.assertIn("personal_dashboard_hide_context", self.ctx.tools)
        self.assertIn("personal_dashboard_create_cron_jobs", self.ctx.tools)
        self.assertIn("personal-dashboard", self.ctx.commands)
        self.assertIn("briefing-curator", self.ctx.skills)

    def test_refresh_from_memory_creates_context_not_scanner_cards(self) -> None:
        memory_dir = Path(self.tmp.name) / "memories"
        memory_dir.mkdir(parents=True)
        (memory_dir / "MEMORY.md").write_text(
            "- User wants a morning AI news briefing and stock alerts.\n",
            encoding="utf-8",
        )
        data = self.call_tool(
            "personal_dashboard_refresh_from_hermes",
            {"include_sessions": False, "include_cron": False, "create_cards": True},
        )
        self.assertGreaterEqual(len(data["context_items"]), 1)
        self.assertEqual(len(data["cards"]), 0)
        domains = {item["domain"] for item in data["context_items"]}
        self.assertIn("news", domains)
        self.assertIn("stocks", domains)

    def test_patch_card_tool_updates_existing_card(self) -> None:
        self.call_tool(
            "personal_dashboard_upsert_card",
            {"id": "status-card", "domain": "news", "title": "Status", "summary": "Initial."},
        )
        patched = self.call_tool(
            "personal_dashboard_patch_card",
            {"id": "status-card", "summary": "Pinned.", "pinned": True, "status": "pinned"},
        )
        self.assertEqual(patched["summary"], "Pinned.")
        self.assertTrue(patched["pinned"])
        self.assertEqual(patched["status"], "pinned")

    def test_slash_refresh_is_zero_setup(self) -> None:
        memory_dir = Path(self.tmp.name) / "memories"
        memory_dir.mkdir(parents=True)
        (memory_dir / "MEMORY.md").write_text(
            "- User tracks weekend planning and local weather.\n",
            encoding="utf-8",
        )
        message = self.ctx.commands["personal-dashboard"]["handler"]("refresh")
        self.assertIn("refreshed from Hermes context", message)
        self.assertIn("sources scanned:", message)
        self.assertIn("cards updated:", message)
        self.assertIn("scanner cards suppressed:", message)

    def test_slash_status_shows_source_coverage(self) -> None:
        memory_dir = Path(self.tmp.name) / "memories"
        memory_dir.mkdir(parents=True)
        (memory_dir / "MEMORY.md").write_text(
            "- User tracks AI news.\n",
            encoding="utf-8",
        )
        message = self.ctx.commands["personal-dashboard"]["handler"]("status")
        self.assertIn("readable sources:", message)
        self.assertIn("memory=1", message)

    def test_slash_create_jobs_reports_missing_cron_runtime(self) -> None:
        message = self.ctx.commands["personal-dashboard"]["handler"]("create-jobs")
        self.assertIn("Cron jobs were not created:", message)


if __name__ == "__main__":
    unittest.main()
