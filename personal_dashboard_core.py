"""Shared storage and validation for Hermes Personal Dashboard.

This module is intentionally dependency-light. The plugin loader and the
dashboard API loader import it through different paths, so all state lives in
SQLite rather than module globals.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


PLUGIN_ID = "hermes-personal-dashboard"
PLUGIN_LABEL = "Hermes Personal Dashboard"

PRIORITIES = {"low", "medium", "high", "critical"}
CARD_STATUSES = {"active", "stale", "dismissed", "expired", "pinned"}
SUGGESTION_STATUSES = {"pending", "accepted", "dismissed"}
REFRESH_STATUSES = {"running", "success", "error"}

_ID_RE = re.compile(r"[^a-zA-Z0-9_.:-]+")


class DashboardError(ValueError):
    """Raised when a dashboard payload is invalid."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_time(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def normalize_time(value: str) -> str:
    parsed = parse_time(value)
    if parsed is None:
        raise DashboardError("timestamp must be ISO-8601")
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def slugify(value: str, fallback: str = "item") -> str:
    text = str(value or "").strip().lower()
    text = _ID_RE.sub("-", text).strip("-._:")
    return text[:120] or fallback


def hermes_home() -> Path:
    raw = os.environ.get("HERMES_HOME")
    return Path(raw).expanduser() if raw else Path.home() / ".hermes"


def plugin_home(home: Optional[Path] = None) -> Path:
    return (home or hermes_home()) / "plugins" / PLUGIN_ID


def db_path(home: Optional[Path] = None) -> Path:
    return plugin_home(home) / "cards.db"


def connect(path: Optional[Path] = None) -> sqlite3.Connection:
    target = path or db_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    init_db(conn)
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS cards (
            id TEXT PRIMARY KEY,
            topic_id TEXT,
            domain TEXT NOT NULL,
            title TEXT NOT NULL,
            summary TEXT NOT NULL,
            detail_md TEXT,
            priority TEXT NOT NULL DEFAULT 'medium',
            status TEXT NOT NULL DEFAULT 'active',
            pinned INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            valid_until TEXT,
            source_label TEXT,
            source_url TEXT,
            why_shown TEXT,
            confidence REAL,
            payload_json TEXT,
            last_seen_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_cards_status ON cards(status);
        CREATE INDEX IF NOT EXISTS idx_cards_domain ON cards(domain);
        CREATE INDEX IF NOT EXISTS idx_cards_updated_at ON cards(updated_at);
        CREATE INDEX IF NOT EXISTS idx_cards_valid_until ON cards(valid_until);

        CREATE TABLE IF NOT EXISTS topics (
            id TEXT PRIMARY KEY,
            domain TEXT NOT NULL,
            label TEXT NOT NULL,
            query TEXT,
            enabled INTEGER NOT NULL DEFAULT 1,
            priority TEXT NOT NULL DEFAULT 'medium',
            cadence TEXT,
            config_json TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_topics_domain ON topics(domain);
        CREATE INDEX IF NOT EXISTS idx_topics_enabled ON topics(enabled);

        CREATE TABLE IF NOT EXISTS evidence (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_id TEXT NOT NULL,
            source_label TEXT,
            source_url TEXT,
            title TEXT,
            excerpt TEXT,
            captured_at TEXT NOT NULL,
            payload_json TEXT,
            FOREIGN KEY(card_id) REFERENCES cards(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_evidence_card_id ON evidence(card_id);

        CREATE TABLE IF NOT EXISTS refresh_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_key TEXT NOT NULL,
            status TEXT NOT NULL,
            summary TEXT,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            error TEXT,
            payload_json TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_refresh_runs_job_key ON refresh_runs(job_key);
        CREATE INDEX IF NOT EXISTS idx_refresh_runs_started_at ON refresh_runs(started_at);

        CREATE TABLE IF NOT EXISTS preferences (
            key TEXT PRIMARY KEY,
            value_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS suggestions (
            id TEXT PRIMARY KEY,
            kind TEXT NOT NULL,
            title TEXT NOT NULL,
            summary TEXT,
            payload_json TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_suggestions_status ON suggestions(status);
        """
    )
    conn.commit()


def _json_dumps(value: Any) -> Optional[str]:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


def _json_loads(value: Any, fallback: Any = None) -> Any:
    if value in (None, ""):
        return fallback
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return fallback


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    item = dict(row)
    for key in ("payload_json", "config_json", "value_json"):
        if key in item:
            decoded = _json_loads(item.pop(key), None)
            target = key.replace("_json", "")
            item[target] = decoded
    if "pinned" in item:
        item["pinned"] = bool(item["pinned"])
    if "enabled" in item:
        item["enabled"] = bool(item["enabled"])
    return item


def normalize_priority(value: Any) -> str:
    text = str(value or "medium").strip().lower()
    if text not in PRIORITIES:
        raise DashboardError(f"priority must be one of {sorted(PRIORITIES)}")
    return text


def normalize_status(value: Any, allowed: Iterable[str], default: str) -> str:
    text = str(value or default).strip().lower()
    allowed_set = set(allowed)
    if text not in allowed_set:
        raise DashboardError(f"status must be one of {sorted(allowed_set)}")
    return text


def validate_card_payload(data: Dict[str, Any], partial: bool = False) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise DashboardError("payload must be an object")

    required = [] if partial else ["id", "domain", "title", "summary"]
    for key in required:
        if not str(data.get(key) or "").strip():
            raise DashboardError(f"{key} is required")

    out: Dict[str, Any] = {}
    string_fields = [
        "id",
        "topic_id",
        "domain",
        "title",
        "summary",
        "detail_md",
        "updated_at",
        "valid_until",
        "source_label",
        "source_url",
        "why_shown",
    ]
    for key in string_fields:
        if key in data and data.get(key) is not None:
            out[key] = str(data[key]).strip()

    if "id" in out:
        out["id"] = slugify(out["id"], "card")
    if "domain" in out:
        out["domain"] = slugify(out["domain"], "general")

    if "priority" in data:
        out["priority"] = normalize_priority(data.get("priority"))
    elif not partial:
        out["priority"] = "medium"

    if "status" in data:
        out["status"] = normalize_status(data.get("status"), CARD_STATUSES, "active")
    elif not partial:
        out["status"] = "active"

    if "pinned" in data:
        out["pinned"] = 1 if bool(data.get("pinned")) else 0
    elif out.get("status") == "pinned":
        out["pinned"] = 1
    elif not partial:
        out["pinned"] = 0

    if "confidence" in data and data.get("confidence") is not None:
        try:
            confidence = float(data["confidence"])
        except (TypeError, ValueError) as exc:
            raise DashboardError("confidence must be numeric") from exc
        out["confidence"] = max(0.0, min(1.0, confidence))

    if "payload" in data:
        out["payload_json"] = _json_dumps(data.get("payload"))
    elif "payload_json" in data:
        out["payload_json"] = _json_dumps(_json_loads(data.get("payload_json"), data.get("payload_json")))

    now = utc_now()
    if not partial and not out.get("updated_at"):
        out["updated_at"] = now
    if out.get("updated_at"):
        try:
            out["updated_at"] = normalize_time(out["updated_at"])
        except DashboardError as exc:
            raise DashboardError("updated_at must be ISO-8601") from exc
    if out.get("valid_until"):
        try:
            out["valid_until"] = normalize_time(out["valid_until"])
        except DashboardError as exc:
            raise DashboardError("valid_until must be ISO-8601") from exc

    return out


def mark_stale_cards(conn: sqlite3.Connection) -> int:
    now = utc_now()
    now_dt = parse_time(now)
    rows = conn.execute(
        """
        SELECT id, valid_until
          FROM cards
         WHERE status = 'active'
           AND valid_until IS NOT NULL
           AND valid_until != ''
        """
    ).fetchall()
    stale_ids = []
    for row in rows:
        valid_until = parse_time(row["valid_until"])
        if valid_until is not None and now_dt is not None and valid_until < now_dt:
            stale_ids.append(row["id"])
    if not stale_ids:
        return 0
    placeholders = ", ".join("?" for _ in stale_ids)
    cur = conn.execute(
        f"UPDATE cards SET status = 'stale', updated_at = ? WHERE id IN ({placeholders})",
        [now] + stale_ids,
    )
    conn.commit()
    return int(cur.rowcount or 0)


def upsert_card(data: Dict[str, Any], conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    own = conn is None
    cx = conn or connect()
    try:
        payload = validate_card_payload(data)
        now = utc_now()
        payload.setdefault("created_at", now)
        payload["last_seen_at"] = now

        existing = cx.execute("SELECT created_at FROM cards WHERE id = ?", (payload["id"],)).fetchone()
        created_at = existing["created_at"] if existing else now
        payload["created_at"] = created_at

        fields = [
            "id",
            "topic_id",
            "domain",
            "title",
            "summary",
            "detail_md",
            "priority",
            "status",
            "pinned",
            "updated_at",
            "created_at",
            "valid_until",
            "source_label",
            "source_url",
            "why_shown",
            "confidence",
            "payload_json",
            "last_seen_at",
        ]
        values = [payload.get(f) for f in fields]
        updates = ", ".join(f"{f}=excluded.{f}" for f in fields if f not in {"id", "created_at"})
        cx.execute(
            f"""
            INSERT INTO cards ({", ".join(fields)})
            VALUES ({", ".join("?" for _ in fields)})
            ON CONFLICT(id) DO UPDATE SET {updates}
            """,
            values,
        )
        cx.commit()
        return get_card(payload["id"], cx) or {}
    finally:
        if own:
            cx.close()


def patch_card(card_id: str, data: Dict[str, Any], conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    own = conn is None
    cx = conn or connect()
    try:
        card_id = slugify(card_id, "card")
        existing = get_card(card_id, cx)
        if not existing:
            raise DashboardError("card not found")
        payload = validate_card_payload(data, partial=True)
        if not payload:
            return existing
        payload["updated_at"] = payload.get("updated_at") or utc_now()
        if payload.get("status") == "pinned":
            payload["pinned"] = 1
        allowed_fields = {
            "topic_id",
            "domain",
            "title",
            "summary",
            "detail_md",
            "priority",
            "status",
            "pinned",
            "updated_at",
            "valid_until",
            "source_label",
            "source_url",
            "why_shown",
            "confidence",
            "payload_json",
        }
        fields = [k for k in payload if k in allowed_fields]
        if not fields:
            return existing
        cx.execute(
            f"UPDATE cards SET {', '.join(f'{k} = ?' for k in fields)} WHERE id = ?",
            [payload[k] for k in fields] + [card_id],
        )
        cx.commit()
        return get_card(card_id, cx) or {}
    finally:
        if own:
            cx.close()


def get_card(card_id: str, conn: Optional[sqlite3.Connection] = None) -> Optional[Dict[str, Any]]:
    own = conn is None
    cx = conn or connect()
    try:
        row = cx.execute("SELECT * FROM cards WHERE id = ?", (slugify(card_id, "card"),)).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        if own:
            cx.close()


def list_cards(
    status: Optional[str] = None,
    domain: Optional[str] = None,
    include_hidden: bool = False,
    limit: int = 200,
    conn: Optional[sqlite3.Connection] = None,
) -> List[Dict[str, Any]]:
    own = conn is None
    cx = conn or connect()
    try:
        mark_stale_cards(cx)
        clauses: List[str] = []
        params: List[Any] = []
        if status:
            clauses.append("status = ?")
            params.append(normalize_status(status, CARD_STATUSES, "active"))
        elif not include_hidden:
            clauses.append("status NOT IN ('dismissed', 'expired')")
        if domain:
            clauses.append("domain = ?")
            params.append(slugify(domain, "general"))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = cx.execute(
            f"""
            SELECT * FROM cards
            {where}
            ORDER BY pinned DESC,
                     CASE priority
                       WHEN 'critical' THEN 4
                       WHEN 'high' THEN 3
                       WHEN 'medium' THEN 2
                       ELSE 1
                     END DESC,
                     updated_at DESC
            LIMIT ?
            """,
            params + [max(1, min(int(limit), 500))],
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        if own:
            cx.close()


def expire_card(card_id: str, conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    return patch_card(card_id, {"status": "expired", "valid_until": utc_now()}, conn)


def dismiss_card(card_id: str, conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    return patch_card(card_id, {"status": "dismissed"}, conn)


def validate_topic_payload(data: Dict[str, Any], partial: bool = False) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise DashboardError("payload must be an object")
    required = [] if partial else ["domain", "label"]
    for key in required:
        if not str(data.get(key) or "").strip():
            raise DashboardError(f"{key} is required")
    out: Dict[str, Any] = {}
    for key in ("id", "domain", "label", "query", "cadence"):
        if key in data and data.get(key) is not None:
            out[key] = str(data[key]).strip()
    if "domain" in out:
        out["domain"] = slugify(out["domain"], "general")
    if "id" in out:
        out["id"] = slugify(out["id"], "topic")
    elif not partial:
        out["id"] = slugify(f"{out.get('domain', 'general')}:{out.get('label', 'topic')}", "topic")
    if "priority" in data:
        out["priority"] = normalize_priority(data.get("priority"))
    elif not partial:
        out["priority"] = "medium"
    if "enabled" in data:
        out["enabled"] = 1 if bool(data.get("enabled")) else 0
    elif not partial:
        out["enabled"] = 1
    if "config" in data:
        out["config_json"] = _json_dumps(data.get("config"))
    return out


def upsert_topic(data: Dict[str, Any], conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    own = conn is None
    cx = conn or connect()
    try:
        payload = validate_topic_payload(data)
        now = utc_now()
        existing = cx.execute("SELECT created_at FROM topics WHERE id = ?", (payload["id"],)).fetchone()
        created_at = existing["created_at"] if existing else now
        fields = ["id", "domain", "label", "query", "enabled", "priority", "cadence", "config_json", "created_at", "updated_at"]
        values = [
            payload.get("id"),
            payload.get("domain"),
            payload.get("label"),
            payload.get("query"),
            payload.get("enabled"),
            payload.get("priority"),
            payload.get("cadence"),
            payload.get("config_json"),
            created_at,
            now,
        ]
        updates = ", ".join(f"{f}=excluded.{f}" for f in fields if f not in {"id", "created_at"})
        cx.execute(
            f"""
            INSERT INTO topics ({", ".join(fields)})
            VALUES ({", ".join("?" for _ in fields)})
            ON CONFLICT(id) DO UPDATE SET {updates}
            """,
            values,
        )
        cx.commit()
        return get_topic(payload["id"], cx) or {}
    finally:
        if own:
            cx.close()


def get_topic(topic_id: str, conn: Optional[sqlite3.Connection] = None) -> Optional[Dict[str, Any]]:
    own = conn is None
    cx = conn or connect()
    try:
        row = cx.execute("SELECT * FROM topics WHERE id = ?", (slugify(topic_id, "topic"),)).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        if own:
            cx.close()


def list_topics(include_disabled: bool = True, conn: Optional[sqlite3.Connection] = None) -> List[Dict[str, Any]]:
    own = conn is None
    cx = conn or connect()
    try:
        where = "" if include_disabled else "WHERE enabled = 1"
        rows = cx.execute(
            f"SELECT * FROM topics {where} ORDER BY domain ASC, label ASC"
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        if own:
            cx.close()


def patch_topic(topic_id: str, data: Dict[str, Any], conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    own = conn is None
    cx = conn or connect()
    try:
        topic_id = slugify(topic_id, "topic")
        if not get_topic(topic_id, cx):
            raise DashboardError("topic not found")
        payload = validate_topic_payload(data, partial=True)
        payload["updated_at"] = utc_now()
        allowed = {"domain", "label", "query", "enabled", "priority", "cadence", "config_json", "updated_at"}
        fields = [k for k in payload if k in allowed]
        if fields:
            cx.execute(
                f"UPDATE topics SET {', '.join(f'{k} = ?' for k in fields)} WHERE id = ?",
                [payload[k] for k in fields] + [topic_id],
            )
            cx.commit()
        return get_topic(topic_id, cx) or {}
    finally:
        if own:
            cx.close()


def delete_topic(topic_id: str, conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    own = conn is None
    cx = conn or connect()
    try:
        topic_id = slugify(topic_id, "topic")
        cur = cx.execute("DELETE FROM topics WHERE id = ?", (topic_id,))
        cx.commit()
        return {"deleted": int(cur.rowcount or 0), "id": topic_id}
    finally:
        if own:
            cx.close()


def add_evidence(data: Dict[str, Any], conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise DashboardError("payload must be an object")
    card_id = slugify(str(data.get("card_id") or ""), "card")
    if not card_id:
        raise DashboardError("card_id is required")
    own = conn is None
    cx = conn or connect()
    try:
        if not get_card(card_id, cx):
            raise DashboardError("card not found")
        captured_at = str(data.get("captured_at") or utc_now())
        fields = ["card_id", "source_label", "source_url", "title", "excerpt", "captured_at", "payload_json"]
        values = [
            card_id,
            data.get("source_label"),
            data.get("source_url"),
            data.get("title"),
            data.get("excerpt"),
            captured_at,
            _json_dumps(data.get("payload")) if "payload" in data else None,
        ]
        cur = cx.execute(
            f"INSERT INTO evidence ({', '.join(fields)}) VALUES ({', '.join('?' for _ in fields)})",
            values,
        )
        cx.commit()
        row = cx.execute("SELECT * FROM evidence WHERE id = ?", (cur.lastrowid,)).fetchone()
        return _row_to_dict(row)
    finally:
        if own:
            cx.close()


def list_evidence(card_id: str, conn: Optional[sqlite3.Connection] = None) -> List[Dict[str, Any]]:
    own = conn is None
    cx = conn or connect()
    try:
        rows = cx.execute(
            "SELECT * FROM evidence WHERE card_id = ? ORDER BY captured_at DESC",
            (slugify(card_id, "card"),),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        if own:
            cx.close()


def record_refresh(data: Dict[str, Any], conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise DashboardError("payload must be an object")
    job_key = str(data.get("job_key") or "").strip()
    if not job_key:
        raise DashboardError("job_key is required")
    status = normalize_status(data.get("status"), REFRESH_STATUSES, "success")
    own = conn is None
    cx = conn or connect()
    try:
        started_at = str(data.get("started_at") or utc_now())
        ended_at = data.get("ended_at")
        if status in {"success", "error"} and not ended_at:
            ended_at = utc_now()
        cur = cx.execute(
            """
            INSERT INTO refresh_runs (job_key, status, summary, started_at, ended_at, error, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_key,
                status,
                data.get("summary"),
                started_at,
                ended_at,
                data.get("error"),
                _json_dumps(data.get("payload")) if "payload" in data else None,
            ),
        )
        cx.commit()
        row = cx.execute("SELECT * FROM refresh_runs WHERE id = ?", (cur.lastrowid,)).fetchone()
        return _row_to_dict(row)
    finally:
        if own:
            cx.close()


def list_refresh_runs(limit: int = 50, conn: Optional[sqlite3.Connection] = None) -> List[Dict[str, Any]]:
    own = conn is None
    cx = conn or connect()
    try:
        rows = cx.execute(
            "SELECT * FROM refresh_runs ORDER BY started_at DESC, id DESC LIMIT ?",
            (max(1, min(int(limit), 200)),),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        if own:
            cx.close()


def get_preferences(conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    own = conn is None
    cx = conn or connect()
    try:
        rows = cx.execute("SELECT key, value_json FROM preferences").fetchall()
        return {r["key"]: _json_loads(r["value_json"], None) for r in rows}
    finally:
        if own:
            cx.close()


def put_preferences(values: Dict[str, Any], conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    if not isinstance(values, dict):
        raise DashboardError("preferences payload must be an object")
    own = conn is None
    cx = conn or connect()
    try:
        now = utc_now()
        for key, value in values.items():
            safe_key = slugify(str(key), "preference")
            cx.execute(
                """
                INSERT INTO preferences (key, value_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json, updated_at = excluded.updated_at
                """,
                (safe_key, _json_dumps(value), now),
            )
        cx.commit()
        return get_preferences(cx)
    finally:
        if own:
            cx.close()


def setup_status(conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    own = conn is None
    cx = conn or connect()
    try:
        prefs = get_preferences(cx)
        topics = list_topics(True, cx)
        card_count = cx.execute("SELECT COUNT(*) AS count FROM cards").fetchone()["count"]
        return {
            "configured": bool(prefs.get("setup_completed")),
            "topic_count": len(topics),
            "card_count": int(card_count),
            "preferences": prefs,
            "db_path": str(db_path()),
        }
    finally:
        if own:
            cx.close()


def save_setup(data: Dict[str, Any], conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise DashboardError("setup payload must be an object")
    own = conn is None
    cx = conn or connect()
    try:
        existing = get_preferences(cx)
        prefs = {
            "setup_completed": True,
            "briefing_time": data.get("briefing_time") or "07:30",
            "timezone": data.get("timezone") or "",
            "location": data.get("location") or "",
            "alert_frequency": data.get("alert_frequency") or "hourly",
            "weekend_planner": bool(data.get("weekend_planner", True)),
            "calendar_enabled": bool(data.get("calendar_enabled", False)),
            "source_preferences": data["source_preferences"] if "source_preferences" in data else existing.get("source_preferences", {}),
            "cron_jobs": data["cron_jobs"] if "cron_jobs" in data else existing.get("cron_jobs", {}),
        }
        put_preferences(prefs, cx)

        for item in data.get("topics") or []:
            if isinstance(item, dict):
                upsert_topic(item, cx)

        return setup_status(cx)
    finally:
        if own:
            cx.close()


def suggest(data: Dict[str, Any], conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise DashboardError("payload must be an object")
    kind = slugify(str(data.get("kind") or "card"), "card")
    title = str(data.get("title") or "").strip()
    if not title:
        raise DashboardError("title is required")
    payload = data.get("payload") or {}
    sugg_id = slugify(str(data.get("id") or f"{kind}:{title}:{time.time_ns()}"), "suggestion")
    own = conn is None
    cx = conn or connect()
    try:
        now = utc_now()
        cx.execute(
            """
            INSERT INTO suggestions (id, kind, title, summary, payload_json, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                kind = excluded.kind,
                title = excluded.title,
                summary = excluded.summary,
                payload_json = excluded.payload_json,
                status = 'pending',
                updated_at = excluded.updated_at
            """,
            (sugg_id, kind, title, data.get("summary"), _json_dumps(payload), now, now),
        )
        cx.commit()
        return get_suggestion(sugg_id, cx) or {}
    finally:
        if own:
            cx.close()


def get_suggestion(suggestion_id: str, conn: Optional[sqlite3.Connection] = None) -> Optional[Dict[str, Any]]:
    own = conn is None
    cx = conn or connect()
    try:
        row = cx.execute("SELECT * FROM suggestions WHERE id = ?", (slugify(suggestion_id, "suggestion"),)).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        if own:
            cx.close()


def list_suggestions(status: Optional[str] = "pending", conn: Optional[sqlite3.Connection] = None) -> List[Dict[str, Any]]:
    own = conn is None
    cx = conn or connect()
    try:
        if status:
            normalized = normalize_status(status, SUGGESTION_STATUSES, "pending")
            rows = cx.execute(
                "SELECT * FROM suggestions WHERE status = ? ORDER BY updated_at DESC",
                (normalized,),
            ).fetchall()
        else:
            rows = cx.execute("SELECT * FROM suggestions ORDER BY updated_at DESC").fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        if own:
            cx.close()


def accept_suggestion(suggestion_id: str, conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    own = conn is None
    cx = conn or connect()
    try:
        suggestion = get_suggestion(suggestion_id, cx)
        if not suggestion:
            raise DashboardError("suggestion not found")
        payload = suggestion.get("payload") or {}
        result: Dict[str, Any] = {"suggestion": suggestion}
        if isinstance(payload, dict):
            if isinstance(payload.get("card"), dict):
                result["card"] = upsert_card(payload["card"], cx)
            if isinstance(payload.get("topic"), dict):
                result["topic"] = upsert_topic(payload["topic"], cx)
        cx.execute(
            "UPDATE suggestions SET status = 'accepted', updated_at = ? WHERE id = ?",
            (utc_now(), slugify(suggestion_id, "suggestion")),
        )
        cx.commit()
        result["suggestion"] = get_suggestion(suggestion_id, cx)
        return result
    finally:
        if own:
            cx.close()


def dismiss_suggestion(suggestion_id: str, conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    own = conn is None
    cx = conn or connect()
    try:
        suggestion_id = slugify(suggestion_id, "suggestion")
        cur = cx.execute(
            "UPDATE suggestions SET status = 'dismissed', updated_at = ? WHERE id = ?",
            (utc_now(), suggestion_id),
        )
        cx.commit()
        if not cur.rowcount:
            raise DashboardError("suggestion not found")
        return get_suggestion(suggestion_id, cx) or {}
    finally:
        if own:
            cx.close()


def discover_suggestions_from_memory(conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    """Create pending suggestions from generic Hermes memory/session hints.

    This intentionally never creates visible cards. It only proposes topics
    that a user may accept from the setup UI.
    """
    own = conn is None
    cx = conn or connect()
    try:
        created: List[Dict[str, Any]] = []
        memory_dir = hermes_home() / "memories"
        for filename in ("MEMORY.md", "USER.md"):
            path = memory_dir / filename
            if not path.exists():
                continue
            for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                text = line.strip(" -\t")
                if len(text) < 18:
                    continue
                lowered = text.lower()
                domain = None
                if any(word in lowered for word in ("stock", "ticker", "portfolio", "market")):
                    domain = "stocks"
                elif any(word in lowered for word in ("team", "soccer", "football", "match", "club")):
                    domain = "sports"
                elif any(word in lowered for word in ("weather", "location", "city", "commute")):
                    domain = "weather"
                elif any(word in lowered for word in ("news", "politics", "ai", "briefing")):
                    domain = "news"
                if not domain:
                    continue
                created.append(
                    suggest(
                        {
                            "id": f"memory-topic:{domain}:{slugify(text[:60])}",
                            "kind": "topic",
                            "title": f"Track {domain}: {text[:80]}",
                            "summary": f"Suggested from {filename}. Review before enabling.",
                            "payload": {
                                "topic": {
                                    "domain": domain,
                                    "label": text[:80],
                                    "query": text,
                                    "priority": "medium",
                                    "cadence": "daily",
                                    "config": {"source": filename},
                                }
                            },
                        },
                        cx,
                    )
                )
        return {"created": created, "count": len(created)}
    finally:
        if own:
            cx.close()


def dashboard_snapshot() -> Dict[str, Any]:
    cx = connect()
    try:
        cards = list_cards(conn=cx)
        return {
            "cards": cards,
            "topics": list_topics(True, cx),
            "preferences": get_preferences(cx),
            "refresh_runs": list_refresh_runs(25, cx),
            "suggestions": list_suggestions("pending", cx),
            "setup": setup_status(cx),
        }
    finally:
        cx.close()
