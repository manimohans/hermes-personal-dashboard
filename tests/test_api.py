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

    def test_topics_setup_and_suggestions_routes(self) -> None:
        setup = self.client.post(
            "/setup/save",
            json={
                "briefing_time": "07:45",
                "timezone": "America/Los_Angeles",
                "topics": [{"domain": "news", "label": "Technology", "query": "technology news"}],
            },
        )
        self.assertEqual(setup.status_code, 200)
        self.assertTrue(setup.json()["configured"])

        topics = self.client.get("/topics")
        self.assertEqual(topics.status_code, 200)
        self.assertEqual(len(topics.json()["topics"]), 1)

        starters = self.client.post("/setup/starter-topics")
        self.assertEqual(starters.status_code, 200)
        self.assertEqual(starters.json()["count"], 6)

        samples = self.client.post("/setup/sample-cards")
        self.assertEqual(samples.status_code, 200)
        self.assertEqual(samples.json()["count"], 4)

        suggestion = self.client.post(
            "/suggestions",
            json={
                "title": "Suggested topic",
                "payload": {"topic": {"domain": "sports", "label": "Example team"}},
            },
        )
        self.assertEqual(suggestion.status_code, 200)
        suggestion_id = suggestion.json()["suggestion"]["id"]

        accepted = self.client.post(f"/suggestions/{suggestion_id}/accept")
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(accepted.json()["suggestion"]["status"], "accepted")

    def test_refresh_routes_and_snapshot(self) -> None:
        refresh = self.client.post(
            "/refresh-runs",
            json={"job_key": "morning", "status": "success", "summary": "Updated."},
        )
        self.assertEqual(refresh.status_code, 200)
        self.assertEqual(refresh.json()["refresh_run"]["job_key"], "morning")

        snapshot = self.client.get("/snapshot")
        self.assertEqual(snapshot.status_code, 200)
        self.assertEqual(len(snapshot.json()["refresh_runs"]), 1)


if __name__ == "__main__":
    unittest.main()
