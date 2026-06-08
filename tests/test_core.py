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

    def test_preferences_preserve_cron_metadata(self) -> None:
        core.put_preferences(
            {
                "cron_jobs": {"morning": "abc123"},
                "last_auto_refresh_at": "2026-06-08T00:00:00Z",
            },
            self.conn,
        )
        prefs = core.get_preferences(self.conn)
        self.assertEqual(prefs["cron_jobs"], {"morning": "abc123"})
        self.assertEqual(prefs["last_auto_refresh_at"], "2026-06-08T00:00:00Z")

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

    def test_refresh_from_hermes_context_creates_signals_not_visible_cards(self) -> None:
        memory_dir = Path(self.tmp.name) / "memories"
        memory_dir.mkdir(parents=True)
        (memory_dir / "MEMORY.md").write_text(
            "- User wants AI news in the morning.\n"
            "- User tracks stock alerts and weekend planning.\n",
            encoding="utf-8",
        )
        result = core.refresh_from_hermes_context(
            include_sessions=False,
            include_cron=False,
            create_cards=True,
            conn=self.conn,
        )
        self.assertEqual(result["sources"], 1)
        self.assertGreaterEqual(len(result["context_items"]), 3)
        cards = core.list_cards(conn=self.conn)
        self.assertEqual(cards, [])
        self.assertEqual(result["cards"], [])
        self.assertEqual(result["source_report"]["source_count"], 1)
        self.assertIn("memory", result["source_report"]["by_type"])

    def test_refresh_with_no_sources_creates_no_visible_cards(self) -> None:
        result = core.refresh_from_hermes_context(
            include_sessions=False,
            include_cron=False,
            create_cards=True,
            conn=self.conn,
        )
        self.assertEqual(result["sources"], 0)
        self.assertEqual(len(result["context_items"]), 0)
        cards = core.list_cards(conn=self.conn)
        self.assertEqual(cards, [])
        self.assertEqual(result["source_report"]["source_count"], 0)

    def test_legacy_scanner_cards_are_hidden_from_visible_cards(self) -> None:
        item = core.upsert_context_item(
            {
                "id": "context-news-ai",
                "domain": "news",
                "label": "AI news briefing",
                "summary": "From memory.",
                "source_types": ["memory"],
                "score": 1.0,
            },
            self.conn,
        )
        core.upsert_card(
            {
                "id": "auto-context-news-ai",
                "context_id": item["id"],
                "domain": "news",
                "title": "AI news briefing",
                "summary": "Hermes has this in its memory history: User wants AI news.",
                "payload": {"auto_discovered": True, "context_item_id": item["id"]},
            },
            self.conn,
        )
        self.assertEqual(len(core.list_cards(conn=self.conn)), 0)
        self.assertEqual(len(core.list_cards(include_scanner=True, conn=self.conn)), 1)
        self.assertEqual(core.suppress_scanner_cards(self.conn), 1)
        hidden = core.hide_context_item(item["id"], self.conn)
        self.assertEqual(hidden["status"], "hidden")
        self.assertEqual(len(core.list_cards(conn=self.conn)), 0)

    def test_dashboard_snapshot_auto_refreshes_without_setup(self) -> None:
        memory_dir = Path(self.tmp.name) / "memories"
        memory_dir.mkdir(parents=True)
        (memory_dir / "USER.md").write_text("- User follows soccer fixtures.\n", encoding="utf-8")
        snapshot = core.dashboard_snapshot(auto_refresh=True)
        self.assertFalse(snapshot["status"]["requires_configuration"])
        self.assertEqual(snapshot["status"]["mode"], "autonomous")
        self.assertIn("source_report", snapshot)
        self.assertGreaterEqual(len(snapshot["context_items"]), 1)
        self.assertEqual(len(snapshot["cards"]), 0)
        self.assertEqual(snapshot["curation"]["state"], "needs_ai_curation")

    def test_curated_cards_rank_above_low_fresh_cards(self) -> None:
        core.upsert_card(
            {
                "id": "routine",
                "domain": "news",
                "title": "Routine",
                "summary": "A routine item.",
                "priority": "low",
                "payload": {"ai_curated": True, "section": "today"},
            },
            self.conn,
        )
        core.upsert_card(
            {
                "id": "important",
                "domain": "alerts",
                "title": "Important",
                "summary": "A high priority item.",
                "priority": "high",
                "payload": {"ai_curated": True, "section": "now", "relevance_score": 50},
            },
            self.conn,
        )
        cards = core.list_cards(conn=self.conn)
        self.assertEqual(cards[0]["id"], "important")
        self.assertIn("relevance_score", cards[0])


if __name__ == "__main__":
    unittest.main()
