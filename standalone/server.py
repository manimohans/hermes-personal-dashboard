#!/usr/bin/env python3
"""Standalone Hermes Personal Dashboard web server."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
from http import HTTPStatus
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, unquote, urlparse


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import personal_dashboard_core as core  # noqa: E402


API_PREFIX = "/api/plugins/hermes-personal-dashboard"
DAY_NUMBERS = {
    "sun": 0,
    "sunday": 0,
    "mon": 1,
    "monday": 1,
    "tue": 2,
    "tuesday": 2,
    "wed": 3,
    "wednesday": 3,
    "thu": 4,
    "thursday": 4,
    "fri": 5,
    "friday": 5,
    "sat": 6,
    "saturday": 6,
}


def cron_prompt(kind: str) -> str:
    base = (
        "Use the hermes-personal-dashboard:briefing-curator skill. "
        "Start with personal_dashboard_refresh_from_hermes so the dashboard reflects "
        "existing Hermes memory, sessions, cron output, and prior agent work as relevance signals without "
        "requiring user setup. Then read personal_dashboard_list_context and use the "
        "available Hermes tools to refresh useful live cards for the inferred context. Do not turn raw "
        "scanner lines, prompts, schedules, or memory-write JSON into cards. Write structured AI-curated "
        "cards with personal_dashboard_upsert_card and record the run "
        "with personal_dashboard_record_refresh. Show provenance and why each card was shown."
    )
    if kind == "morning":
        return f"{base} Produce the autonomous daily dashboard refresh."
    if kind == "alerts":
        return f"{base} Refresh time-sensitive cards inferred from Hermes context."
    if kind == "weekend":
        return f"{base} Produce a periodic planning refresh from whatever Hermes already knows is relevant."
    return base


def parse_hhmm(value: Any) -> str:
    text = str(value or "07:30").strip()
    parts = text.split(":")
    if len(parts) != 2:
        return "30 7 * * *"
    try:
        hour = max(0, min(23, int(parts[0])))
        minute = max(0, min(59, int(parts[1])))
    except ValueError:
        hour, minute = 7, 30
    return f"{minute} {hour} * * *"


def alert_schedule(value: Any) -> str:
    text = str(value or "hourly").strip().lower()
    if text in {"15m", "every-15-min", "every 15m"}:
        return "every 15m"
    if text in {"30m", "every-30-min", "every 30m"}:
        return "every 30m"
    if text in {"daily", "once-daily"}:
        return "0 12 * * *"
    return "every 1h"


def day_number(value: Any) -> int:
    text = str(value or "fri").strip().lower()
    if text.isdigit():
        return max(0, min(6, int(text)))
    return DAY_NUMBERS.get(text, 5)


def day_label(value: Any) -> str:
    labels = ["Sundays", "Mondays", "Tuesdays", "Wednesdays", "Thursdays", "Fridays", "Saturdays"]
    return labels[day_number(value)]


def schedule_overrides_from_body(body: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    body = body or {}
    aliases = {
        "daily": "daily_time",
        "daily_time": "daily_time",
        "time": "daily_time",
        "briefing_time": "daily_time",
        "frequent": "frequent_refresh",
        "signals": "frequent_refresh",
        "alerts": "frequent_refresh",
        "alert_frequency": "frequent_refresh",
        "frequent_refresh": "frequent_refresh",
        "planning_day": "planning_day",
        "weekly_day": "planning_day",
        "planning_time": "planning_time",
        "weekly_time": "planning_time",
    }
    overrides = {
        target: body[key]
        for key, target in aliases.items()
        if key in body and body[key] is not None and body[key] != ""
    }
    planning = str(body.get("planning") or body.get("weekly") or "").strip()
    if "@" in planning:
        day, time = planning.split("@", 1)
        overrides["planning_day"] = day
        overrides["planning_time"] = time
    return overrides


def persist_schedule_overrides(overrides: Dict[str, Any]) -> None:
    values = {
        key: value
        for key, value in overrides.items()
        if key in {"daily_time", "frequent_refresh", "planning_day", "planning_time"}
    }
    if values:
        core.put_preferences(values)


def job_specs(prefs: Dict[str, Any], body: Optional[Dict[str, Any]] = None) -> Dict[str, Dict[str, str]]:
    overrides = schedule_overrides_from_body(body)
    briefing_time = str(
        overrides.get("daily_time")
        or prefs.get("daily_time")
        or prefs.get("daily_refresh_time")
        or prefs.get("briefing_time")
        or "07:30"
    )
    alert_frequency = str(
        overrides.get("frequent_refresh")
        or prefs.get("frequent_refresh")
        or prefs.get("frequent_refresh_interval")
        or prefs.get("alert_frequency")
        or "hourly"
    ).strip().lower()
    planning_day = overrides.get("planning_day") or prefs.get("planning_day") or "fri"
    planning_time = str(overrides.get("planning_time") or prefs.get("planning_time") or "15:00")
    if alert_frequency in {"15m", "every-15-min", "every 15m"}:
        alert_cadence = "every 15 minutes"
    elif alert_frequency in {"30m", "every-30-min", "every 30m"}:
        alert_cadence = "every 30 minutes"
    elif alert_frequency in {"daily", "once-daily"}:
        alert_cadence = "daily at 12:00 local time"
    else:
        alert_cadence = "hourly"
    planning_schedule = parse_hhmm(planning_time)
    planning_minute, planning_hour = planning_schedule.split()[:2]
    return {
        "morning": {
            "name": "Personal Dashboard Daily Briefing",
            "schedule": parse_hhmm(briefing_time),
            "cadence": f"daily at {briefing_time} local time",
            "purpose": "turn daily-relevant Hermes context into briefing cards",
        },
        "alerts": {
            "name": "Personal Dashboard Frequent Signal Refresh",
            "schedule": alert_schedule(alert_frequency),
            "cadence": alert_cadence,
            "purpose": "refresh time-sensitive cards such as weather, stocks, sports, news, calendar, family, projects, and alerts",
        },
        "weekend": {
            "name": "Personal Dashboard Planning Refresh",
            "schedule": f"{planning_minute} {planning_hour} * * {day_number(planning_day)}",
            "cadence": f"{day_label(planning_day)} at {planning_time} local time",
            "purpose": "prepare planning cards from Hermes context",
        },
    }


def jobs_payload(prefs: Dict[str, Any], job_ids: Dict[str, Any], body: Optional[Dict[str, Any]] = None) -> list[Dict[str, Any]]:
    specs = job_specs(prefs, body)
    rows = []
    for kind in ("morning", "alerts", "weekend"):
        spec = dict(specs[kind])
        spec["kind"] = kind
        if kind in job_ids:
            spec["id"] = str(job_ids[kind])
        rows.append(spec)
    return rows


def create_standard_cron_jobs(body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    body = body or {}
    persist_schedule_overrides(schedule_overrides_from_body(body))
    prefs = core.get_preferences()
    existing = prefs.get("cron_jobs") or {}
    if existing and not body.get("force"):
        return {"created": [], "existing": existing, "skipped": True, "jobs": jobs_payload(prefs, existing, body)}
    try:
        from cron import jobs as cron_jobs  # type: ignore
    except Exception as exc:
        core.put_preferences({"cron_unavailable": str(exc)})
        return {
            "created": [],
            "existing": existing,
            "skipped": True,
            "error": f"cron integration unavailable: {exc}",
            "next_step": "Open Hermes and run `/personal-dashboard create-jobs` where the Hermes cron runtime is available.",
            "jobs": jobs_payload(prefs, existing, body),
        }

    specs = job_specs(prefs, body)
    created = []
    cron_job_ids: Dict[str, str] = {}
    for kind in ("morning", "alerts", "weekend"):
        job = cron_jobs.create_job(
            prompt=cron_prompt(kind),
            schedule=specs[kind]["schedule"],
            name=specs[kind]["name"],
            deliver="local",
            skills=[f"{core.PLUGIN_ID}:briefing-curator"],
            origin={"plugin": core.PLUGIN_ID, "kind": kind},
        )
        created.append(job)
        if isinstance(job, dict) and job.get("id"):
            cron_job_ids[kind] = str(job["id"])
    core.put_preferences({"cron_jobs": cron_job_ids})
    return {"created": created, "existing": {}, "skipped": False, "jobs": jobs_payload(prefs, cron_job_ids, body)}


class Handler(BaseHTTPRequestHandler):
    server_version = "HermesPersonalDashboard/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith(API_PREFIX):
            self.handle_api("GET", parsed.path, parse_qs(parsed.query))
            return
        self.serve_static(parsed.path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith(API_PREFIX):
            self.handle_api("POST", parsed.path, parse_qs(parsed.query))
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_PATCH(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith(API_PREFIX):
            self.handle_api("PATCH", parsed.path, parse_qs(parsed.query))
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, OPTIONS")
        self.end_headers()

    def read_json(self) -> Dict[str, Any]:
        raw_len = self.headers.get("Content-Length") or "0"
        try:
            length = max(0, int(raw_len))
        except ValueError:
            length = 0
        if not length:
            return {}
        raw = self.rfile.read(length)
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def send_json(self, payload: Any, status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def send_api_error(self, exc: Exception) -> None:
        status = HTTPStatus.NOT_FOUND if "not found" in str(exc).lower() else HTTPStatus.BAD_REQUEST
        self.send_json({"detail": str(exc)}, int(status))

    def serve_static(self, path: str) -> None:
        if path in {"", "/"}:
            target = ROOT / "standalone" / "index.html"
        else:
            clean = Path(unquote(path.lstrip("/")))
            if clean.is_absolute() or ".." in clean.parts:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            target = ROOT / clean
        if not target.exists() or not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        data = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def handle_api(self, method: str, path: str, query: Dict[str, Any]) -> None:
        rel = path[len(API_PREFIX):].strip("/")
        parts = rel.split("/") if rel else []
        try:
            if method == "GET" and rel == "health":
                self.send_json({"ok": True, "plugin": core.PLUGIN_ID, "db_path": str(core.db_path())})
                return
            if method == "GET" and rel == "snapshot":
                auto_refresh = (query.get("auto_refresh") or ["true"])[0].lower() not in {"0", "false", "no"}
                self.send_json(core.dashboard_snapshot(auto_refresh=auto_refresh))
                return
            if method == "GET" and rel == "cards":
                self.send_json({"cards": core.list_cards(
                    status=(query.get("status") or [None])[0],
                    domain=(query.get("domain") or [None])[0],
                    include_hidden=(query.get("include_hidden") or ["false"])[0].lower() in {"1", "true", "yes"},
                    include_scanner=(query.get("include_scanner") or ["false"])[0].lower() in {"1", "true", "yes"},
                    limit=int((query.get("limit") or ["200"])[0]),
                )})
                return
            if method == "GET" and rel == "context":
                self.send_json({"context_items": core.list_context_items()})
                return
            if method == "GET" and rel == "preferences":
                self.send_json({"preferences": core.get_preferences()})
                return
            if method == "GET" and rel == "refresh-runs":
                self.send_json({"refresh_runs": core.list_refresh_runs()})
                return
            if method == "POST" and rel == "context/refresh":
                body = self.read_json()
                self.send_json(core.refresh_from_hermes_context(
                    include_sessions=bool(body.get("include_sessions", True)),
                    include_cron=bool(body.get("include_cron", True)),
                    create_cards=bool(body.get("create_cards", False)),
                ))
                return
            if method == "POST" and rel in {"automation/ensure-jobs", "automation/create-cron-jobs"}:
                self.send_json(create_standard_cron_jobs(self.read_json()))
                return
            if method == "POST" and rel == "refresh-runs":
                self.send_json({"refresh_run": core.record_refresh(self.read_json())})
                return
            if method == "POST" and rel == "cards":
                self.send_json({"card": core.upsert_card(self.read_json())})
                return
            if method == "PATCH" and len(parts) == 2 and parts[0] == "cards":
                self.send_json({"card": core.patch_card(unquote(parts[1]), self.read_json())})
                return
            if method == "POST" and len(parts) == 3 and parts[0] == "cards":
                card_id = unquote(parts[1])
                action = parts[2]
                if action == "dismiss":
                    self.send_json({"card": core.dismiss_card(card_id)})
                    return
                if action == "pin":
                    self.send_json({"card": core.patch_card(card_id, {"pinned": True, "status": "pinned"})})
                    return
                if action == "unpin":
                    self.send_json({"card": core.patch_card(card_id, {"pinned": False, "status": "active"})})
                    return
            if method == "POST" and len(parts) == 3 and parts[0] == "context" and parts[2] == "hide":
                self.send_json({"context_item": core.hide_context_item(unquote(parts[1]))})
                return
            self.send_error(HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self.send_api_error(exc)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the standalone Hermes Personal Dashboard.")
    parser.add_argument("--host", default=os.environ.get("HPD_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("HPD_PORT", "9120")))
    parser.add_argument("--hermes-home", default=os.environ.get("HERMES_HOME"))
    args = parser.parse_args()
    if args.hermes_home:
        os.environ["HERMES_HOME"] = str(Path(args.hermes_home).expanduser())
    os.environ.setdefault("HERMES_PERSONAL_DASHBOARD_DATA", str(core.hermes_home() / "personal-dashboard"))
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Hermes Personal Dashboard running at http://{args.host}:{args.port}", flush=True)
    print(f"Reading Hermes data from {core.hermes_home()}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Hermes Personal Dashboard.", flush=True)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
