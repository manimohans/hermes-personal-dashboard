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
        self.assertEqual(len(self.ctx.tools), 16)
        self.assertIn("personal_dashboard_quickstart", self.ctx.tools)
        self.assertIn("personal_dashboard_save_setup", self.ctx.tools)
        self.assertIn("personal_dashboard_create_cron_jobs", self.ctx.tools)
        self.assertIn("personal-dashboard", self.ctx.commands)
        self.assertIn("briefing-curator", self.ctx.skills)

    def test_quickstart_creates_starters_and_samples(self) -> None:
        data = self.call_tool(
            "personal_dashboard_quickstart",
            {
                "briefing_time": "08:00",
                "timezone": "America/Los_Angeles",
                "location": "San Francisco",
                "create_cron_jobs": False,
            },
        )
        self.assertEqual(data["starter_topics"]["count"], 6)
        self.assertEqual(data["sample_cards"]["count"], 4)
        self.assertTrue(data["snapshot"]["setup"]["configured"])
        self.assertEqual(data["snapshot"]["preferences"]["location"], "San Francisco")

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

    def test_slash_quickstart_is_helpful(self) -> None:
        message = self.ctx.commands["personal-dashboard"]["handler"]("quickstart")
        self.assertIn("quickstart complete", message)
        self.assertIn("starter topics: 6", message)
        self.assertIn("sample cards: 4", message)


if __name__ == "__main__":
    unittest.main()
