from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover - depends on Hermes dashboard env
    FastAPI = None
    TestClient = None


ROOT = Path(__file__).resolve().parents[1]


def load_plugin_api():
    module_name = "test_hpd_plugin_api"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, ROOT / "dashboard" / "plugin_api.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


@unittest.skipIf(FastAPI is None or TestClient is None, "FastAPI test client is not installed")
class ApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_home = os.environ.get("HERMES_HOME")
        os.environ["HERMES_HOME"] = self.tmp.name
        api = load_plugin_api()
        app = FastAPI()
        app.include_router(api.router)
        self.client = TestClient(app)

    def tearDown(self) -> None:
        if self.old_home is None:
            os.environ.pop("HERMES_HOME", None)
        else:
            os.environ["HERMES_HOME"] = self.old_home
        self.tmp.cleanup()

    def test_cards_routes(self) -> None:
        created = self.client.post(
            "/cards",
            json={
                "id": "weather-today",
                "domain": "weather",
                "title": "Weather today",
                "summary": "Mild morning.",
            },
        )
        self.assertEqual(created.status_code, 200)
        self.assertEqual(created.json()["card"]["id"], "weather-today")

        patched = self.client.patch("/cards/weather-today", json={"priority": "high"})
        self.assertEqual(patched.status_code, 200)
        self.assertEqual(patched.json()["card"]["priority"], "high")

        listed = self.client.get("/cards")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.json()["cards"]), 1)

        dismissed = self.client.post("/cards/weather-today/dismiss")
        self.assertEqual(dismissed.status_code, 200)
        self.assertEqual(dismissed.json()["card"]["status"], "dismissed")

        sample = self.client.post("/cards", json={"id": "pin-me", "domain": "news", "title": "Pin me", "summary": "Pin test."})
        self.assertEqual(sample.status_code, 200)
        pinned = self.client.post("/cards/pin-me/pin")
        self.assertEqual(pinned.status_code, 200)
        self.assertTrue(pinned.json()["card"]["pinned"])
        unpinned = self.client.post("/cards/pin-me/unpin")
        self.assertEqual(unpinned.status_code, 200)
        self.assertFalse(unpinned.json()["card"]["pinned"])

    def test_context_refresh_and_hide_routes(self) -> None:
        memory_dir = Path(self.tmp.name) / "memories"
        memory_dir.mkdir(parents=True)
        (memory_dir / "MEMORY.md").write_text(
            "- User wants morning AI news and stock alerts.\n",
            encoding="utf-8",
        )

        refresh = self.client.post(
            "/context/refresh",
            json={"include_sessions": False, "include_cron": False, "create_cards": True},
        )
        self.assertEqual(refresh.status_code, 200)
        self.assertGreaterEqual(len(refresh.json()["context_items"]), 1)
        self.assertEqual(len(refresh.json()["cards"]), 0)

        context = self.client.get("/context")
        self.assertEqual(context.status_code, 200)
        context_id = context.json()["context_items"][0]["id"]

        hidden = self.client.post(f"/context/{context_id}/hide")
        self.assertEqual(hidden.status_code, 200)
        self.assertEqual(hidden.json()["context_item"]["status"], "hidden")

    def test_refresh_routes_and_snapshot(self) -> None:
        refresh = self.client.post(
            "/refresh-runs",
            json={"job_key": "morning", "status": "success", "summary": "Updated."},
        )
        self.assertEqual(refresh.status_code, 200)
        self.assertEqual(refresh.json()["refresh_run"]["job_key"], "morning")

        snapshot = self.client.get("/snapshot?auto_refresh=false")
        self.assertEqual(snapshot.status_code, 200)
        self.assertEqual(len(snapshot.json()["refresh_runs"]), 1)
        self.assertFalse(snapshot.json()["status"]["requires_configuration"])


if __name__ == "__main__":
    unittest.main()
