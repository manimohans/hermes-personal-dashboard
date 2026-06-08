from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

import personal_dashboard_core as core


ROOT = Path(__file__).resolve().parents[1]


def load_server_module():
    module_name = "test_hpd_standalone_server"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, ROOT / "standalone" / "server.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class StandaloneServerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_home = os.environ.get("HERMES_HOME")
        self.old_data = os.environ.get("HERMES_PERSONAL_DASHBOARD_DATA")
        os.environ["HERMES_HOME"] = self.tmp.name
        os.environ.pop("HERMES_PERSONAL_DASHBOARD_DATA", None)
        self.server = load_server_module()

    def tearDown(self) -> None:
        if self.old_home is None:
            os.environ.pop("HERMES_HOME", None)
        else:
            os.environ["HERMES_HOME"] = self.old_home
        if self.old_data is None:
            os.environ.pop("HERMES_PERSONAL_DASHBOARD_DATA", None)
        else:
            os.environ["HERMES_PERSONAL_DASHBOARD_DATA"] = self.old_data
        self.tmp.cleanup()

    def write_card(self, db_path: Path, payload: dict) -> None:
        conn = core.connect(db_path)
        try:
            core.upsert_card(payload, conn)
        finally:
            conn.close()

    def list_card_ids(self) -> list[str]:
        conn = core.connect()
        try:
            return [card["id"] for card in core.list_cards(conn=conn)]
        finally:
            conn.close()

    def test_migrates_legacy_standalone_db_when_shared_db_is_missing(self) -> None:
        legacy_db = Path(self.tmp.name) / "personal-dashboard" / "cards.db"
        self.write_card(
            legacy_db,
            {
                "id": "legacy-card",
                "domain": "news",
                "title": "Legacy card",
                "summary": "Created before standalone and plugin shared one database.",
                "payload": {"ai_curated": True},
            },
        )

        self.assertFalse(core.db_path().exists())
        note = self.server.migrate_legacy_standalone_db()
        self.assertIn("Migrated legacy standalone database", note or "")
        self.assertTrue(core.db_path().exists())
        self.assertEqual(self.list_card_ids(), ["legacy-card"])

    def test_does_not_overwrite_existing_shared_db(self) -> None:
        legacy_db = Path(self.tmp.name) / "personal-dashboard" / "cards.db"
        self.write_card(legacy_db, {"id": "legacy-card", "domain": "news", "title": "Legacy", "summary": "Old."})
        self.write_card(core.db_path(), {"id": "shared-card", "domain": "alerts", "title": "Shared", "summary": "Current."})

        note = self.server.migrate_legacy_standalone_db()
        self.assertIn("left untouched", note or "")
        self.assertEqual(self.list_card_ids(), ["shared-card"])

    def test_bad_legacy_db_does_not_block_startup(self) -> None:
        legacy_db = Path(self.tmp.name) / "personal-dashboard" / "cards.db"
        legacy_db.parent.mkdir(parents=True)
        legacy_db.write_text("not a sqlite database", encoding="utf-8")

        note = self.server.migrate_legacy_standalone_db()
        self.assertIn("migration skipped", note or "")
        self.assertFalse(core.db_path().exists())

    def test_custom_data_env_disables_legacy_migration(self) -> None:
        custom_dir = Path(self.tmp.name) / "custom-dashboard-data"
        os.environ["HERMES_PERSONAL_DASHBOARD_DATA"] = str(custom_dir)
        legacy_db = Path(self.tmp.name) / "personal-dashboard" / "cards.db"
        self.write_card(legacy_db, {"id": "legacy-card", "domain": "news", "title": "Legacy", "summary": "Old."})

        note = self.server.migrate_legacy_standalone_db()
        self.assertIsNone(note)
        self.assertFalse((custom_dir / "cards.db").exists())


if __name__ == "__main__":
    unittest.main()
