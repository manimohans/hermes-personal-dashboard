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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


PLUGIN_ID = "hermes-personal-dashboard"
PLUGIN_LABEL = "Hermes Personal Dashboard"

PRIORITIES = {"low", "medium", "high", "critical"}
CARD_STATUSES = {"active", "stale", "dismissed", "expired", "pinned"}
REFRESH_STATUSES = {"running", "success", "error"}
CONTEXT_STATUSES = {"active", "hidden"}

_ID_RE = re.compile(r"[^a-zA-Z0-9_.:-]+")

DOMAIN_PATTERNS: Dict[str, Tuple[str, ...]] = {
    "alerts": (
        "alert",
        "urgent",
        "threshold",
        "notify",
        "watch",
        "monitor",
        "warning",
        "deadline",
    ),
    "calendar": (
        "calendar",
        "meeting",
        "appointment",
        "schedule",
        "event",
        "reminder",
        "today",
        "tomorrow",
    ),
    "family": (
        "daycare",
        "school",
        "lunch menu",
        "menu",
        "daughter",
        "son",
        "kid",
        "child",
        "family",
    ),
    "news": (
        "news",
        "politics",
        "ai update",
        "morning update",
        "briefing",
        "headlines",
        "current events",
    ),
    "planning": (
        "weekend",
        "plan",
        "plans",
        "itinerary",
        "trip",
        "local events",
        "things to do",
    ),
    "projects": (
        "github",
        "issue",
        "pull request",
        "repo",
        "repository",
        "project",
        "worktree",
        "deploy",
        "build",
    ),
    "sports": (
        "sports",
        "soccer",
        "football",
        "match",
        "fixture",
        "game",
        "league",
        "team",
        "club",
    ),
    "stocks": (
        "stock",
        "stocks",
        "ticker",
        "portfolio",
        "market",
        "equity",
        "earnings",
        "price alert",
    ),
    "weather": (
        "weather",
        "forecast",
        "rain",
        "snow",
        "temperature",
        "storm",
        "air quality",
        "commute",
    ),
}

DOMAIN_SECTIONS = {
    "alerts": "now",
    "calendar": "now",
    "family": "today",
    "news": "today",
    "planning": "week",
    "projects": "watching",
    "sports": "week",
    "stocks": "watching",
    "weather": "now",
}

SOURCE_WEIGHTS = {
    "memory": 1.0,
    "user_profile": 1.0,
    "session": 0.65,
    "cron": 0.8,
    "cron_job": 0.7,
}

SESSION_TABLE_HINTS = ("session", "message", "conversation", "chat", "turn", "cron", "output")
TEXT_COLUMN_HINTS = ("content", "message", "text", "body", "prompt", "response", "title", "summary", "name", "output")
TIME_COLUMN_HINTS = ("updated", "created", "started", "ended", "timestamp", "time", "last")


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
    custom = os.environ.get("HERMES_PERSONAL_DASHBOARD_DATA")
    if custom:
        return Path(custom).expanduser()
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
            context_id TEXT,
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

        CREATE TABLE IF NOT EXISTS context_items (
            id TEXT PRIMARY KEY,
            domain TEXT NOT NULL,
            label TEXT NOT NULL,
            summary TEXT,
            evidence_json TEXT,
            source_types_json TEXT,
            confidence REAL,
            score REAL,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            payload_json TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_context_items_domain ON context_items(domain);
        CREATE INDEX IF NOT EXISTS idx_context_items_status ON context_items(status);
        CREATE INDEX IF NOT EXISTS idx_context_items_score ON context_items(score);
        """
    )
    _migrate_db(conn)
    conn.commit()


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    try:
        return {str(row["name"]) for row in conn.execute(f"PRAGMA table_info({_quote_identifier(table)})").fetchall()}
    except sqlite3.Error:
        return set()


def _migrate_db(conn: sqlite3.Connection) -> None:
    card_columns = _table_columns(conn, "cards")
    if card_columns and "context_id" not in card_columns:
        conn.execute("ALTER TABLE cards ADD COLUMN context_id TEXT")
        card_columns.add("context_id")
    if "context_id" in card_columns and "topic_id" in card_columns:
        conn.execute(
            "UPDATE cards SET context_id = topic_id WHERE context_id IS NULL AND topic_id IS NOT NULL"
        )


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
    for key in ("payload_json", "config_json", "value_json", "evidence_json", "source_types_json"):
        if key in item:
            decoded = _json_loads(item.pop(key), None)
            target = key.replace("_json", "")
            item[target] = decoded
    if "pinned" in item:
        item["pinned"] = bool(item["pinned"])
    if "enabled" in item:
        item["enabled"] = bool(item["enabled"])
    return item


def _card_payload(card: Dict[str, Any]) -> Dict[str, Any]:
    payload = card.get("payload") or {}
    return payload if isinstance(payload, dict) else {}


def is_scanner_generated_card(card: Dict[str, Any]) -> bool:
    """Return true for deterministic scanner artifacts that should not be main cards."""
    payload = _card_payload(card)
    if payload.get("ai_curated") or payload.get("user_curated") or payload.get("keep_visible"):
        return False
    if payload.get("scanner_generated") or payload.get("system_card"):
        return True
    card_id = str(card.get("id") or "")
    summary = str(card.get("summary") or "")
    source_label = str(card.get("source_label") or "")
    if card_id == "system-hermes-context-map":
        return True
    if payload.get("context_item_id") and card_id.startswith("auto-context-"):
        return True
    if source_label == "Hermes context scanner":
        return True
    if summary.lower().startswith("hermes has this in its "):
        return True
    return False


def card_relevance_score(card: Dict[str, Any], now: Optional[datetime] = None) -> float:
    """Rank visible cards by usefulness at this moment."""
    now = now or datetime.now(timezone.utc)
    payload = _card_payload(card)
    priority_weight = {"critical": 420, "high": 320, "medium": 210, "low": 100}
    score = float(priority_weight.get(str(card.get("priority") or "medium"), 210))
    if card.get("pinned") or card.get("status") == "pinned":
        score += 1000
    if card.get("status") == "stale":
        score -= 140
    if payload.get("ai_curated"):
        score += 80
    if card.get("source_label"):
        score += 12
    if card.get("why_shown"):
        score += 12
    try:
        score += max(-100.0, min(150.0, float(payload.get("relevance_score") or 0)))
    except (TypeError, ValueError):
        pass

    updated_at = parse_time(card.get("updated_at"))
    if updated_at:
        age_seconds = max(0.0, (now - updated_at).total_seconds())
        if age_seconds < 30 * 60:
            score += 70
        elif age_seconds < 3 * 60 * 60:
            score += 50
        elif age_seconds < 12 * 60 * 60:
            score += 30
        elif age_seconds > 7 * 24 * 60 * 60:
            score -= 30

    valid_until = parse_time(card.get("valid_until"))
    if valid_until:
        seconds_until = (valid_until - now).total_seconds()
        if 0 <= seconds_until <= 3 * 60 * 60:
            score += 150
        elif 0 <= seconds_until <= 24 * 60 * 60:
            score += 80
        elif seconds_until < 0:
            score -= 120

    domain = str(card.get("domain") or "")
    local_hour = datetime.now().hour
    local_weekday = datetime.now().weekday()
    if 5 <= local_hour <= 10 and domain in {"news", "weather", "calendar", "family"}:
        score += 35
    if 9 <= local_hour <= 17 and domain in {"projects", "stocks", "calendar", "alerts"}:
        score += 28
    if 17 <= local_hour <= 22 and domain in {"planning", "family", "sports"}:
        score += 28
    if (local_weekday == 4 and local_hour >= 12) or local_weekday >= 5:
        if domain in {"planning", "sports", "events"}:
            score += 35
    if domain in {"alerts", "weather", "calendar"} and str(payload.get("section") or "") == "now":
        score += 22
    return score


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
        "context_id",
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
            "context_id",
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
            "context_id",
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
    include_scanner: bool = False,
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
        requested_limit = max(1, min(int(limit), 500))
        query_limit = 500 if not include_scanner else requested_limit
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
            params + [query_limit],
        ).fetchall()
        cards = [_row_to_dict(r) for r in rows]
        if not include_scanner:
            cards = [card for card in cards if not is_scanner_generated_card(card)]
        now = datetime.now(timezone.utc)
        for card in cards:
            card["relevance_score"] = round(card_relevance_score(card, now), 3)
        cards.sort(key=lambda card: (float(card.get("relevance_score") or 0), str(card.get("updated_at") or "")), reverse=True)
        return cards[:requested_limit]
    finally:
        if own:
            cx.close()


def expire_card(card_id: str, conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    return patch_card(card_id, {"status": "expired", "valid_until": utc_now()}, conn)


def dismiss_card(card_id: str, conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    return patch_card(card_id, {"status": "dismissed"}, conn)


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


def dashboard_status(conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    own = conn is None
    cx = conn or connect()
    try:
        prefs = get_preferences(cx)
        context_count = cx.execute("SELECT COUNT(*) AS count FROM context_items WHERE status != 'hidden'").fetchone()["count"]
        card_count = len(list_cards(conn=cx))
        return {
            "mode": "autonomous",
            "requires_configuration": False,
            "context_count": int(context_count),
            "card_count": int(card_count),
            "preferences": prefs,
            "db_path": str(db_path()),
        }
    finally:
        if own:
            cx.close()


def _quote_identifier(name: str) -> str:
    if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
        return name
    return '"' + name.replace('"', '""') + '"'


def _clean_text(value: Any, limit: int = 500) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip(" -\t\r\n")
    return text[:limit]


def _clip_words(value: str, limit: int = 160) -> str:
    text = _clean_text(value, limit + 40)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _memory_file_paths() -> List[Path]:
    home = hermes_home()
    candidates: List[Path] = []
    for name in ("MEMORY.md", "USER.md"):
        candidates.append(home / "memories" / name)
        candidates.append(home / name)
    memory_dir = home / "memories"
    if memory_dir.exists():
        for path in sorted(memory_dir.glob("*.md"))[:30]:
            if path not in candidates:
                candidates.append(path)
    return candidates


def _source_type_for_path(path: Path) -> str:
    name = path.name.lower()
    if name == "user.md":
        return "user_profile"
    if "cron" in str(path).lower():
        return "cron"
    return "memory"


def _read_file_sources(max_chars_per_file: int = 16000) -> List[Dict[str, Any]]:
    sources: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for path in _memory_file_paths():
        key = str(path)
        if key in seen or not path.exists() or not path.is_file():
            continue
        seen.add(key)
        text = path.read_text(encoding="utf-8", errors="ignore")[:max_chars_per_file]
        if _clean_text(text, 80):
            sources.append(
                {
                    "source_type": _source_type_for_path(path),
                    "source_label": path.name,
                    "path": str(path),
                    "text": text,
                    "updated_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat().replace("+00:00", "Z"),
                }
            )
    return sources


def _read_cron_sources(max_files: int = 40, max_chars_per_file: int = 12000) -> List[Dict[str, Any]]:
    sources: List[Dict[str, Any]] = []
    home = hermes_home()
    jobs_path = home / "cron" / "jobs.json"
    if jobs_path.exists() and jobs_path.is_file():
        text = jobs_path.read_text(encoding="utf-8", errors="ignore")[:max_chars_per_file]
        if _clean_text(text, 80):
            sources.append(
                {
                    "source_type": "cron_job",
                    "source_label": "cron/jobs.json",
                    "path": str(jobs_path),
                    "text": text,
                    "updated_at": datetime.fromtimestamp(jobs_path.stat().st_mtime, timezone.utc).isoformat().replace("+00:00", "Z"),
                }
            )

    output_dir = home / "cron" / "output"
    if not output_dir.exists():
        return sources
    paths = [
        path
        for path in output_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in {".md", ".txt", ".json", ".log"}
    ]
    paths.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    for path in paths[:max_files]:
        text = path.read_text(encoding="utf-8", errors="ignore")[:max_chars_per_file]
        if not _clean_text(text, 80):
            continue
        try:
            label = str(path.relative_to(home))
        except ValueError:
            label = path.name
        sources.append(
            {
                "source_type": "cron",
                "source_label": label,
                "path": str(path),
                "text": text,
                "updated_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat().replace("+00:00", "Z"),
            }
        )
    return sources


def _candidate_session_tables(conn: sqlite3.Connection) -> List[Tuple[str, List[str], Optional[str]]]:
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'view') ORDER BY name").fetchall()
    candidates: List[Tuple[str, List[str], Optional[str]]] = []
    for table_row in tables:
        table = str(table_row["name"])
        lowered_table = table.lower()
        if lowered_table.startswith("sqlite_") or any(
            lowered_table.endswith(suffix) for suffix in ("_data", "_idx", "_docsize", "_config")
        ):
            continue
        if not any(hint in lowered_table for hint in SESSION_TABLE_HINTS):
            continue
        try:
            columns = conn.execute(f"PRAGMA table_info({_quote_identifier(table)})").fetchall()
        except sqlite3.Error:
            continue
        text_columns = [
            str(column["name"])
            for column in columns
            if any(hint in str(column["name"]).lower() for hint in TEXT_COLUMN_HINTS)
        ][:4]
        if not text_columns:
            continue
        time_columns = [
            str(column["name"])
            for column in columns
            if any(hint in str(column["name"]).lower() for hint in TIME_COLUMN_HINTS)
        ]
        candidates.append((table, text_columns, time_columns[0] if time_columns else None))
    return candidates


def _read_session_sources(max_rows: int = 220) -> List[Dict[str, Any]]:
    path = hermes_home() / "state.db"
    if not path.exists() or not path.is_file():
        return []
    sources: List[Dict[str, Any]] = []
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
    except sqlite3.Error:
        return []
    try:
        per_table = max(10, max_rows // 6)
        for table, text_columns, time_column in _candidate_session_tables(conn):
            table_sql = _quote_identifier(table)
            select_parts = [f"CAST({_quote_identifier(column)} AS TEXT)" for column in text_columns]
            text_expr = " || ' ' || ".join(f"COALESCE({part}, '')" for part in select_parts)
            where_expr = " OR ".join(f"LENGTH(COALESCE(CAST({_quote_identifier(column)} AS TEXT), '')) > 20" for column in text_columns)
            order_sql = f" ORDER BY {_quote_identifier(time_column)} DESC" if time_column else ""
            query = f"SELECT {text_expr} AS text FROM {table_sql} WHERE {where_expr}{order_sql} LIMIT ?"
            try:
                rows = conn.execute(query, (per_table,)).fetchall()
            except sqlite3.Error:
                continue
            for row in rows:
                text = _clean_text(row["text"], 3000)
                if len(text) < 24:
                    continue
                sources.append(
                    {
                        "source_type": "session",
                        "source_label": f"state.db:{table}",
                        "path": str(path),
                        "text": text,
                    }
                )
                if len(sources) >= max_rows:
                    return sources
    finally:
        conn.close()
    return sources


def collect_hermes_sources(include_sessions: bool = True, include_cron: bool = True) -> List[Dict[str, Any]]:
    sources = _read_file_sources()
    if include_cron:
        sources.extend(_read_cron_sources())
    if include_sessions:
        sources.extend(_read_session_sources())
    return sources


def _limited_file_count(path: Path, suffixes: set[str], limit: int = 1000) -> int:
    if not path.exists():
        return 0
    count = 0
    for item in path.rglob("*"):
        if item.is_file() and item.suffix.lower() in suffixes:
            count += 1
            if count >= limit:
                return count
    return count


def build_source_report(
    sources: Sequence[Dict[str, Any]],
    include_sessions: bool = True,
    include_cron: bool = True,
) -> Dict[str, Any]:
    by_type: Dict[str, int] = {}
    labels_by_type: Dict[str, List[str]] = {}
    for source in sources:
        source_type = str(source.get("source_type") or "unknown")
        by_type[source_type] = by_type.get(source_type, 0) + 1
        label = str(source.get("source_label") or source.get("path") or source_type)
        labels = labels_by_type.setdefault(source_type, [])
        if label not in labels and len(labels) < 8:
            labels.append(label)

    home = hermes_home()
    memory_paths = []
    seen: set[str] = set()
    for path in _memory_file_paths():
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        memory_paths.append(
            {
                "label": path.name,
                "path": str(path),
                "exists": path.exists(),
                "bytes": path.stat().st_size if path.exists() and path.is_file() else 0,
            }
        )

    state_db = home / "state.db"
    cron_jobs = home / "cron" / "jobs.json"
    cron_output = home / "cron" / "output"
    return {
        "source_count": len(sources),
        "by_type": by_type,
        "labels_by_type": labels_by_type,
        "checks": {
            "memory_files": memory_paths,
            "state_db": {
                "path": str(state_db),
                "exists": state_db.exists(),
                "bytes": state_db.stat().st_size if state_db.exists() and state_db.is_file() else 0,
                "scanned": include_sessions,
            },
            "cron_jobs": {
                "path": str(cron_jobs),
                "exists": cron_jobs.exists(),
                "bytes": cron_jobs.stat().st_size if cron_jobs.exists() and cron_jobs.is_file() else 0,
                "scanned": include_cron,
            },
            "cron_output": {
                "path": str(cron_output),
                "exists": cron_output.exists(),
                "file_count": _limited_file_count(cron_output, {".md", ".txt", ".json", ".log"}) if include_cron else 0,
                "scanned": include_cron,
            },
        },
    }


def _candidate_snippets(source: Dict[str, Any], per_source_limit: int = 80) -> List[str]:
    text = str(source.get("text") or "")
    lines = []
    for raw in text.splitlines():
        line = _clean_text(raw, 700)
        if len(line) >= 18:
            lines.append(line)
        if len(lines) >= per_source_limit:
            break
    if lines:
        return lines
    parts = re.split(r"(?<=[.!?])\s+", _clean_text(text, 5000))
    return [part for part in parts[:per_source_limit] if len(part) >= 18]


def _domains_for_text(text: str) -> List[str]:
    lowered = text.lower()
    domains = [
        domain
        for domain, patterns in DOMAIN_PATTERNS.items()
        if any(pattern in lowered for pattern in patterns)
    ]
    if domains:
        return domains
    if any(word in lowered for word in ("user", "prefers", "wants", "likes", "asks", "daily", "recurring")):
        return ["personal"]
    return []


def _label_for_context(domain: str, text: str) -> str:
    cleaned = _clean_text(text, 140)
    cleaned = re.sub(r"^(the )?user (wants|likes|prefers|follows|tracks|uses|asks for|asked for)\s+", "", cleaned, flags=re.I)
    cleaned = re.sub(r"^(remember|note|preference):\s*", "", cleaned, flags=re.I)
    if not cleaned:
        cleaned = domain.replace("_", " ").title()
    return _clip_words(cleaned, 90)


def _context_summary(domain: str, label: str, evidence: Sequence[Dict[str, Any]]) -> str:
    if evidence:
        snippet = _clip_words(str(evidence[0].get("text") or ""), 150)
        return f"Hermes has this in its {evidence[0].get('source_type', 'context')} history: {snippet}"
    return f"Hermes inferred this {domain} item from its existing context: {label}"


def infer_context_items(sources: Sequence[Dict[str, Any]], max_items: int = 40) -> List[Dict[str, Any]]:
    grouped: Dict[str, Dict[str, Any]] = {}
    for source in sources:
        source_type = str(source.get("source_type") or "memory")
        weight = SOURCE_WEIGHTS.get(source_type, 0.5)
        for snippet in _candidate_snippets(source):
            domains = _domains_for_text(snippet)
            for domain in domains:
                label = _label_for_context(domain, snippet)
                key = f"{domain}:{slugify(label, 'context')}"
                item = grouped.setdefault(
                    key,
                    {
                        "id": f"context-{slugify(key, 'item')}",
                        "domain": domain,
                        "label": label,
                        "evidence": [],
                        "source_types": set(),
                        "score": 0.0,
                    },
                )
                item["score"] += weight
                item["source_types"].add(source_type)
                if len(item["evidence"]) < 5:
                    item["evidence"].append(
                        {
                            "source_type": source_type,
                            "source_label": source.get("source_label"),
                            "path": source.get("path"),
                            "text": _clip_words(snippet, 220),
                        }
                    )
    inferred: List[Dict[str, Any]] = []
    for item in grouped.values():
        evidence = item["evidence"]
        score = float(item["score"])
        source_types = sorted(item["source_types"])
        confidence = min(0.95, 0.35 + min(score, 4.0) * 0.15 + min(len(source_types), 3) * 0.05)
        inferred.append(
            {
                "id": item["id"],
                "domain": item["domain"],
                "label": item["label"],
                "summary": _context_summary(item["domain"], item["label"], evidence),
                "evidence": evidence,
                "source_types": source_types,
                "confidence": round(confidence, 3),
                "score": round(score, 3),
                "payload": {"auto_discovered": True},
            }
        )
    inferred.sort(key=lambda item: (float(item.get("score") or 0), float(item.get("confidence") or 0)), reverse=True)
    return inferred[:max_items]


def upsert_context_item(data: Dict[str, Any], conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise DashboardError("context payload must be an object")
    domain = slugify(str(data.get("domain") or "personal"), "personal")
    label = _clean_text(data.get("label"), 160)
    if not label:
        raise DashboardError("label is required")
    context_id = slugify(str(data.get("id") or f"context:{domain}:{label}"), "context")
    status = normalize_status(data.get("status"), CONTEXT_STATUSES, "active")
    own = conn is None
    cx = conn or connect()
    try:
        now = utc_now()
        existing = cx.execute("SELECT created_at, status FROM context_items WHERE id = ?", (context_id,)).fetchone()
        created_at = existing["created_at"] if existing else now
        if existing and existing["status"] == "hidden" and "status" not in data:
            status = "hidden"
        fields = [
            "id",
            "domain",
            "label",
            "summary",
            "evidence_json",
            "source_types_json",
            "confidence",
            "score",
            "status",
            "created_at",
            "updated_at",
            "last_seen_at",
            "payload_json",
        ]
        values = [
            context_id,
            domain,
            label,
            data.get("summary"),
            _json_dumps(data.get("evidence") or []),
            _json_dumps(data.get("source_types") or []),
            data.get("confidence"),
            data.get("score"),
            status,
            created_at,
            now,
            now,
            _json_dumps(data.get("payload") or {}),
        ]
        updates = ", ".join(f"{field}=excluded.{field}" for field in fields if field not in {"id", "created_at"})
        cx.execute(
            f"""
            INSERT INTO context_items ({", ".join(fields)})
            VALUES ({", ".join("?" for _ in fields)})
            ON CONFLICT(id) DO UPDATE SET {updates}
            """,
            values,
        )
        cx.commit()
        return get_context_item(context_id, cx) or {}
    finally:
        if own:
            cx.close()


def get_context_item(context_id: str, conn: Optional[sqlite3.Connection] = None) -> Optional[Dict[str, Any]]:
    own = conn is None
    cx = conn or connect()
    try:
        row = cx.execute("SELECT * FROM context_items WHERE id = ?", (slugify(context_id, "context"),)).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        if own:
            cx.close()


def list_context_items(
    include_hidden: bool = False,
    limit: int = 100,
    conn: Optional[sqlite3.Connection] = None,
) -> List[Dict[str, Any]]:
    own = conn is None
    cx = conn or connect()
    try:
        where = "" if include_hidden else "WHERE status != 'hidden'"
        rows = cx.execute(
            f"""
            SELECT * FROM context_items
            {where}
            ORDER BY score DESC, confidence DESC, updated_at DESC
            LIMIT ?
            """,
            (max(1, min(int(limit), 500)),),
        ).fetchall()
        return [_row_to_dict(row) for row in rows]
    finally:
        if own:
            cx.close()


def hide_context_item(context_id: str, conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    own = conn is None
    cx = conn or connect()
    try:
        context_id = slugify(context_id, "context")
        cur = cx.execute(
            "UPDATE context_items SET status = 'hidden', updated_at = ? WHERE id = ?",
            (utc_now(), context_id),
        )
        if not cur.rowcount:
            raise DashboardError("context item not found")
        cx.execute(
            "UPDATE cards SET status = 'dismissed', updated_at = ? WHERE id = ?",
            (utc_now(), f"auto-{context_id}"),
        )
        cx.commit()
        return get_context_item(context_id, cx) or {}
    finally:
        if own:
            cx.close()


def _priority_for_context(item: Dict[str, Any]) -> str:
    text = f"{item.get('label', '')} {item.get('summary', '')}".lower()
    if any(word in text for word in ("urgent", "critical", "severe", "deadline", "warning")):
        return "high"
    if item.get("domain") in {"alerts", "weather", "calendar"}:
        return "medium"
    if float(item.get("score") or 0) >= 2.5:
        return "medium"
    return "low"


def _card_title_for_context(item: Dict[str, Any]) -> str:
    label = str(item.get("label") or "").strip()
    if label:
        return _clip_words(label, 80)
    return str(item.get("domain") or "Personal").replace("_", " ").title()


def _source_label_for_context(item: Dict[str, Any]) -> str:
    source_types = item.get("source_types") or []
    labels = {
        "memory": "Hermes memory",
        "user_profile": "Hermes user profile",
        "session": "Hermes sessions",
        "cron": "Hermes cron output",
        "cron_job": "Hermes cron jobs",
    }
    readable = [labels.get(str(source_type), str(source_type)) for source_type in source_types]
    return ", ".join(readable[:3]) or "Hermes context"


def _detail_for_context(item: Dict[str, Any]) -> str:
    evidence = item.get("evidence") or []
    lines = []
    for entry in evidence[:4]:
        source = entry.get("source_label") or entry.get("source_type") or "Hermes"
        text = _clip_words(str(entry.get("text") or ""), 220)
        if text:
            lines.append(f"- {source}: {text}")
    return "\n".join(lines)


def _source_report_detail(report: Dict[str, Any]) -> str:
    lines = []
    by_type = report.get("by_type") or {}
    if by_type:
        lines.append("Readable Hermes sources:")
        for source_type, count in sorted(by_type.items()):
            labels = ", ".join((report.get("labels_by_type") or {}).get(source_type, [])[:4])
            suffix = f" ({labels})" if labels else ""
            lines.append(f"- {source_type}: {count}{suffix}")
    else:
        lines.append("No readable Hermes memory, session, or cron sources were found yet.")

    checks = report.get("checks") or {}
    state_db = checks.get("state_db") or {}
    cron_jobs = checks.get("cron_jobs") or {}
    cron_output = checks.get("cron_output") or {}
    lines.append("")
    lines.append("Source checks:")
    memory_files = checks.get("memory_files") or []
    existing_memory = [item for item in memory_files if item.get("exists")]
    lines.append(f"- memory files: {len(existing_memory)} found")
    lines.append(f"- state.db: {'found' if state_db.get('exists') else 'not found'}")
    lines.append(f"- cron jobs: {'found' if cron_jobs.get('exists') else 'not found'}")
    lines.append(f"- cron output files: {cron_output.get('file_count', 0)}")
    return "\n".join(lines)


def upsert_reflection_card(
    source_report: Dict[str, Any],
    context_count: int,
    generated_count: int,
    conn: Optional[sqlite3.Connection] = None,
) -> Optional[Dict[str, Any]]:
    del source_report, context_count, generated_count, conn
    return None


def sync_cards_from_context(items: Sequence[Dict[str, Any]], conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    del conn
    return {"cards": [], "count": 0, "skipped_context_items": len([item for item in items if item.get("status") != "hidden"])}


def suppress_scanner_cards(conn: sqlite3.Connection) -> int:
    rows = conn.execute(
        """
        SELECT * FROM cards
         WHERE status NOT IN ('dismissed', 'expired')
        """
    ).fetchall()
    scanner_ids = []
    for row in rows:
        card = _row_to_dict(row)
        if is_scanner_generated_card(card):
            scanner_ids.append(card["id"])
    if not scanner_ids:
        return 0
    placeholders = ", ".join("?" for _ in scanner_ids)
    cur = conn.execute(
        f"UPDATE cards SET status = 'dismissed', updated_at = ? WHERE id IN ({placeholders})",
        [utc_now()] + scanner_ids,
    )
    conn.commit()
    return int(cur.rowcount or 0)


def refresh_from_hermes_context(
    include_sessions: bool = True,
    include_cron: bool = True,
    create_cards: bool = False,
    conn: Optional[sqlite3.Connection] = None,
) -> Dict[str, Any]:
    own = conn is None
    cx = conn or connect()
    started_at = utc_now()
    try:
        sources = collect_hermes_sources(include_sessions=include_sessions, include_cron=include_cron)
        source_report = build_source_report(sources, include_sessions=include_sessions, include_cron=include_cron)
        items = infer_context_items(sources)
        saved_items = [upsert_context_item(item, cx) for item in items]
        suppressed = suppress_scanner_cards(cx)
        card_result = sync_cards_from_context(saved_items, cx) if create_cards else {"cards": [], "count": 0, "skipped_context_items": len(saved_items)}
        reflection_card = None
        cards = list(card_result["cards"])
        if reflection_card:
            cards.append(reflection_card)
        put_preferences({"last_auto_refresh_at": utc_now(), "autonomous_mode": True, "last_source_report": source_report}, cx)
        run = record_refresh(
            {
                "job_key": "hermes-context-reflection",
                "status": "success",
                "summary": f"Scanned {len(sources)} Hermes source(s), inferred {len(saved_items)} context signal(s), and suppressed {suppressed} raw scanner card(s).",
                "started_at": started_at,
                "payload": {
                    "source_count": len(sources),
                    "context_count": len(saved_items),
                    "card_count": len(cards),
                    "scanner_cards_suppressed": suppressed,
                    "cards_require_ai_curation": True,
                    "source_report": source_report,
                },
            },
            cx,
        )
        return {
            "sources": len(sources),
            "source_report": source_report,
            "context_items": saved_items,
            "cards": cards,
            "scanner_cards_suppressed": suppressed,
            "refresh_run": run,
            "mode": "autonomous",
        }
    except Exception as exc:
        record_refresh(
            {
                "job_key": "hermes-context-reflection",
                "status": "error",
                "summary": "Hermes context scan failed.",
                "started_at": started_at,
                "error": str(exc),
            },
            cx,
        )
        raise
    finally:
        if own:
            cx.close()


def auto_refresh_if_needed(conn: sqlite3.Connection, max_age_seconds: int = 600) -> Dict[str, Any]:
    prefs = get_preferences(conn)
    last = parse_time(prefs.get("last_auto_refresh_at"))
    now = parse_time(utc_now())
    if last and now and (now - last).total_seconds() < max_age_seconds:
        return {
            "refreshed": False,
            "reason": "recent",
            "last_auto_refresh_at": prefs.get("last_auto_refresh_at"),
            "source_report": prefs.get("last_source_report"),
            "mode": "autonomous",
        }
    result = refresh_from_hermes_context(conn=conn, create_cards=False)
    return {
        "refreshed": True,
        "sources": result["sources"],
        "source_report": result.get("source_report"),
        "context_count": len(result["context_items"]),
        "card_count": len(result["cards"]),
        "scanner_cards_suppressed": result.get("scanner_cards_suppressed", 0),
        "mode": "autonomous",
    }


def dashboard_curation_status(
    cards: Sequence[Dict[str, Any]],
    context_items: Sequence[Dict[str, Any]],
    source_report: Dict[str, Any],
    automation: Dict[str, Any],
) -> Dict[str, Any]:
    curated_cards = [card for card in cards if not is_scanner_generated_card(card)]
    context_count = len([item for item in context_items if item.get("status") != "hidden"])
    source_count = int(source_report.get("source_count") or 0)
    if curated_cards:
        state = "active"
        title = "Hermes-curated cards"
        message = f"{len(curated_cards)} useful card(s) are ranked by priority, freshness, and time relevance."
    elif context_count:
        state = "needs_ai_curation"
        title = "Signals found, cards not curated yet"
        message = (
            f"Hermes found {context_count} relevance signal(s). A Hermes refresh job should turn the best "
            "signals into concise cards with current data and provenance."
        )
    elif source_count:
        state = "watching"
        title = "Hermes context scanned"
        message = "Readable Hermes sources exist, but no durable dashboard signals were found yet."
    else:
        state = "empty"
        title = "Waiting for Hermes context"
        message = "No readable Hermes memory, session history, or cron output was found yet."
    return {
        "state": state,
        "title": title,
        "message": message,
        "curated_card_count": len(curated_cards),
        "context_count": context_count,
        "source_count": source_count,
        "last_auto_refresh_at": automation.get("last_auto_refresh_at"),
        "scanner_cards_suppressed": automation.get("scanner_cards_suppressed", 0),
    }


def dashboard_snapshot(auto_refresh: bool = True) -> Dict[str, Any]:
    cx = connect()
    try:
        automation = auto_refresh_if_needed(cx) if auto_refresh else {"refreshed": False, "mode": "autonomous"}
        suppressed = suppress_scanner_cards(cx)
        if suppressed:
            automation["scanner_cards_suppressed"] = int(automation.get("scanner_cards_suppressed") or 0) + suppressed
        source_report = automation.get("source_report")
        if not source_report:
            source_report = get_preferences(cx).get("last_source_report") or build_source_report(collect_hermes_sources())
        cards = list_cards(conn=cx)
        context_items = list_context_items(conn=cx)
        return {
            "cards": cards,
            "context_items": context_items,
            "preferences": get_preferences(cx),
            "refresh_runs": list_refresh_runs(25, cx),
            "status": dashboard_status(cx),
            "automation": automation,
            "source_report": source_report,
            "curation": dashboard_curation_status(cards, context_items, source_report, automation),
        }
    finally:
        cx.close()
