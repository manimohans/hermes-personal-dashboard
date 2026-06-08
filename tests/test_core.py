from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

import personal_dashboard_core as core


class CoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_home = os.environ.get("HERMES_HOME")
        os.environ["HERMES_HOME"] = self.tmp.name
        self.conn = core.connect()

    def tearDown(self) -> None:
        self.conn.close()
        if self.old_home is None:
            os.environ.pop("HERMES_HOME", None)
        else:
            os.environ["HERMES_HOME"] = self.old_home
        self.tmp.cleanup()

    def test_upsert_card_updates_existing(self) -> None:
        first = core.upsert_card(
            {
                "id": "weather-today",
                "domain": "weather",
                "title": "Weather today",
                "summary": "Mild morning.",
                "priority": "medium",
            },
            self.conn,
        )
        second = core.upsert_card(
            {
                "id": "weather-today",
                "domain": "weather",
                "title": "Weather today",
                "summary": "Warmer afternoon.",
                "priority": "high",
            },
            self.conn,
        )
        cards = core.list_cards(conn=self.conn)
        self.assertEqual(len(cards), 1)
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(second["summary"], "Warmer afternoon.")
        self.assertEqual(second["priority"], "high")

    def test_missing_required_card_fields_fail(self) -> None:
        with self.assertRaises(core.DashboardError):
            core.upsert_card({"id": "bad", "domain": "news"}, self.conn)

    def test_valid_until_marks_active_card_stale(self) -> None:
        card = core.upsert_card(
            {
                "id": "old-alert",
                "domain": "alerts",
                "title": "Old alert",
                "summary": "Expired.",
                "valid_until": "2000-01-01T00:00:00Z",
            },
            self.conn,
        )
        self.assertEqual(card["status"], "active")
        cards = core.list_cards(conn=self.conn)
        self.assertEqual(cards[0]["status"], "stale")

    def test_valid_until_offset_is_compared_as_instant(self) -> None:
        future = core.upsert_card(
            {
                "id": "future-offset",
                "domain": "alerts",
                "title": "Future offset",
                "summary": "Should stay active.",
                "valid_until": "2999-01-01T00:00:00-07:00",
            },
            self.conn,
        )
        self.assertEqual(future["valid_until"], "2999-01-01T07:00:00Z")
        cards = core.list_cards(conn=self.conn)
        self.assertEqual(cards[0]["status"], "active")

    def test_topic_crud(self) -> None:
        topic = core.upsert_topic(
            {
                "domain": "sports",
                "label": "Example team",
                "query": "example team fixtures",
                "cadence": "daily",
            },
            self.conn,
        )
        self.assertTrue(topic["enabled"])
        patched = core.patch_topic(topic["id"], {"enabled": False}, self.conn)
        self.assertFalse(patched["enabled"])
        self.assertEqual(core.delete_topic(topic["id"], self.conn)["deleted"], 1)

    def test_starter_topics_are_generic_and_idempotent(self) -> None:
        first = core.add_starter_topics(self.conn)
        second = core.add_starter_topics(self.conn)
        topics = core.list_topics(conn=self.conn)
        self.assertEqual(first["count"], 6)
        self.assertEqual(second["count"], 6)
        self.assertEqual(len(topics), 6)
        self.assertEqual({topic["domain"] for topic in topics}, {"calendar", "news", "planning", "sports", "stocks", "weather"})

    def test_preferences_save_and_setup_status(self) -> None:
        result = core.save_setup(
            {
                "briefing_time": "08:15",
                "timezone": "America/Los_Angeles",
                "location": "San Francisco",
                "topics": [{"domain": "news", "label": "Technology", "query": "technology news"}],
            },
            self.conn,
        )
        self.assertTrue(result["configured"])
        prefs = core.get_preferences(self.conn)
        self.assertEqual(prefs["briefing_time"], "08:15")
        self.assertEqual(len(core.list_topics(conn=self.conn)), 1)

    def test_setup_save_preserves_existing_cron_jobs_when_omitted(self) -> None:
        core.put_preferences(
            {
                "cron_jobs": {"morning": "abc123"},
                "source_preferences": {"news": ["rss"]},
            },
            self.conn,
        )
        core.save_setup({"briefing_time": "09:00"}, self.conn)
        prefs = core.get_preferences(self.conn)
        self.assertEqual(prefs["cron_jobs"], {"morning": "abc123"})
        self.assertEqual(prefs["source_preferences"], {"news": ["rss"]})

    def test_evidence_and_refresh_runs(self) -> None:
        core.upsert_card(
            {"id": "market-note", "domain": "stocks", "title": "Market note", "summary": "Flat open."},
            self.conn,
        )
        evidence = core.add_evidence(
            {"card_id": "market-note", "source_label": "Example", "excerpt": "Flat open."},
            self.conn,
        )
        self.assertEqual(evidence["card_id"], "market-note")
        run = core.record_refresh(
            {"job_key": "stocks", "status": "success", "summary": "Updated stocks."},
            self.conn,
        )
        self.assertEqual(run["status"], "success")
        self.assertEqual(len(core.list_refresh_runs(conn=self.conn)), 1)

    def test_sample_cards_are_visible_and_idempotent(self) -> None:
        first = core.create_sample_cards(self.conn)
        second = core.create_sample_cards(self.conn)
        cards = core.list_cards(conn=self.conn)
        self.assertEqual(first["count"], 4)
        self.assertEqual(second["count"], 4)
        self.assertEqual(len(cards), 4)
        self.assertTrue(all((card.get("payload") or {}).get("sample") for card in cards))

    def test_suggestions_accept_card_and_topic(self) -> None:
        suggestion = core.suggest(
            {
                "kind": "card",
                "title": "Suggested card",
                "payload": {
                    "card": {
                        "id": "suggested-card",
                        "domain": "news",
                        "title": "Suggested",
                        "summary": "Accepted.",
                    },
                    "topic": {"domain": "news", "label": "Suggested topic"},
                },
            },
            self.conn,
        )
        accepted = core.accept_suggestion(suggestion["id"], self.conn)
        self.assertEqual(accepted["suggestion"]["status"], "accepted")
        self.assertIsNotNone(core.get_card("suggested-card", self.conn))
        self.assertEqual(len(core.list_topics(conn=self.conn)), 1)

    def test_discover_suggestions_from_memory_is_pending_only(self) -> None:
        memory_dir = Path(self.tmp.name) / "memories"
        memory_dir.mkdir(parents=True)
        (memory_dir / "MEMORY.md").write_text("- User follows an example soccer team.\n", encoding="utf-8")
        result = core.discover_suggestions_from_memory(self.conn)
        self.assertEqual(result["count"], 1)
        self.assertEqual(len(core.list_suggestions(conn=self.conn)), 1)
        self.assertEqual(len(core.list_cards(conn=self.conn)), 0)


if __name__ == "__main__":
    unittest.main()
