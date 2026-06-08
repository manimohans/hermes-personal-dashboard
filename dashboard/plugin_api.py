"""Dashboard API routes for Hermes Personal Dashboard.

Mounted by Hermes under /api/plugins/hermes-personal-dashboard/.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query


_PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

core = importlib.import_module("personal_dashboard_core")

router = APIRouter()

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


def _raise(exc: Exception) -> None:
    status = 404 if "not found" in str(exc).lower() else 400
    raise HTTPException(status_code=status, detail=str(exc))


def _cron_prompt(kind: str) -> str:
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
        return f"{base} Refresh time-sensitive cards such as weather, stocks, sports, news, calendar, family, project, and alert items inferred from Hermes context."
    if kind == "weekend":
        return f"{base} Produce a periodic planning refresh from whatever Hermes already knows is relevant."
    return base


def _cron_name(kind: str) -> str:
    return {
        "morning": "Personal Dashboard Daily Briefing",
        "alerts": "Personal Dashboard Frequent Signal Refresh",
        "weekend": "Personal Dashboard Planning Refresh",
    }.get(kind, f"Personal Dashboard {kind.title()}")


def _parse_hhmm(value: Any) -> str:
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


def _alert_schedule(value: Any) -> str:
    text = str(value or "hourly").strip().lower()
    if text in {"15m", "every-15-min", "every 15m"}:
        return "every 15m"
    if text in {"30m", "every-30-min", "every 30m"}:
        return "every 30m"
    if text in {"daily", "once-daily"}:
        return "0 12 * * *"
    return "every 1h"


def _day_number(value: Any) -> int:
    text = str(value or "fri").strip().lower()
    if text.isdigit():
        return max(0, min(6, int(text)))
    return DAY_NUMBERS.get(text, 5)


def _day_label(value: Any) -> str:
    labels = ["Sundays", "Mondays", "Tuesdays", "Wednesdays", "Thursdays", "Fridays", "Saturdays"]
    return labels[_day_number(value)]


def _schedule_overrides_from_body(body: Optional[Dict[str, Any]]) -> Dict[str, Any]:
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
    overrides = {target: body[key] for key, target in aliases.items() if key in body and body[key] is not None and body[key] != ""}
    planning = str(body.get("planning") or body.get("weekly") or "").strip()
    if "@" in planning:
        day, time = planning.split("@", 1)
        overrides["planning_day"] = day
        overrides["planning_time"] = time
    return overrides


def _persist_schedule_overrides(overrides: Dict[str, Any]) -> None:
    values = {
        key: value
        for key, value in overrides.items()
        if key in {"daily_time", "frequent_refresh", "planning_day", "planning_time"}
    }
    if values:
        core.put_preferences(values)


def _job_specs(prefs: Dict[str, Any], body: Optional[Dict[str, Any]] = None) -> Dict[str, Dict[str, str]]:
    overrides = _schedule_overrides_from_body(body)
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
    planning_schedule = _parse_hhmm(planning_time)
    planning_minute, planning_hour = planning_schedule.split()[:2]
    return {
        "morning": {
            "name": _cron_name("morning"),
            "schedule": _parse_hhmm(briefing_time),
            "cadence": f"daily at {briefing_time} local time",
            "purpose": "turn daily-relevant Hermes context into briefing cards",
        },
        "alerts": {
            "name": _cron_name("alerts"),
            "schedule": _alert_schedule(alert_frequency),
            "cadence": alert_cadence,
            "purpose": "refresh time-sensitive cards such as weather, stocks, sports, news, calendar, family, projects, and alerts",
        },
        "weekend": {
            "name": _cron_name("weekend"),
            "schedule": f"{planning_minute} {planning_hour} * * {_day_number(planning_day)}",
            "cadence": f"{_day_label(planning_day)} at {planning_time} local time",
            "purpose": "prepare planning cards from Hermes context",
        },
    }


def _jobs_payload(prefs: Dict[str, Any], job_ids: Dict[str, Any], body: Optional[Dict[str, Any]] = None) -> list[Dict[str, Any]]:
    specs = _job_specs(prefs, body)
    rows = []
    for kind in ("morning", "alerts", "weekend"):
        spec = dict(specs[kind])
        spec["kind"] = kind
        if kind in job_ids:
            spec["id"] = str(job_ids[kind])
        rows.append(spec)
    return rows


def _create_cron_job(kind: str, schedule: str) -> Dict[str, Any]:
    from cron import jobs as cron_jobs

    return cron_jobs.create_job(
        prompt=_cron_prompt(kind),
        schedule=schedule,
        name=_cron_name(kind),
        deliver="local",
        skills=[f"{core.PLUGIN_ID}:briefing-curator"],
        origin={"plugin": core.PLUGIN_ID, "kind": kind},
    )


@router.get("/health")
async def health() -> Dict[str, Any]:
    return {"ok": True, "plugin": core.PLUGIN_ID, "db_path": str(core.db_path())}


@router.get("/snapshot")
async def snapshot(auto_refresh: bool = True) -> Dict[str, Any]:
    return core.dashboard_snapshot(auto_refresh=auto_refresh)


@router.get("/cards")
async def get_cards(
    status: Optional[str] = Query(None),
    domain: Optional[str] = Query(None),
    include_hidden: bool = False,
    include_scanner: bool = False,
    limit: int = 200,
) -> Dict[str, Any]:
    try:
        return {"cards": core.list_cards(status=status, domain=domain, include_hidden=include_hidden, include_scanner=include_scanner, limit=limit)}
    except Exception as exc:
        _raise(exc)


@router.post("/cards")
async def post_card(body: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return {"card": core.upsert_card(body)}
    except Exception as exc:
        _raise(exc)


@router.patch("/cards/{card_id}")
async def patch_card(card_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return {"card": core.patch_card(card_id, body)}
    except Exception as exc:
        _raise(exc)


@router.post("/cards/{card_id}/dismiss")
async def dismiss_card(card_id: str) -> Dict[str, Any]:
    try:
        return {"card": core.dismiss_card(card_id)}
    except Exception as exc:
        _raise(exc)


@router.post("/cards/{card_id}/pin")
async def pin_card(card_id: str) -> Dict[str, Any]:
    try:
        return {"card": core.patch_card(card_id, {"pinned": True, "status": "pinned"})}
    except Exception as exc:
        _raise(exc)


@router.post("/cards/{card_id}/unpin")
async def unpin_card(card_id: str) -> Dict[str, Any]:
    try:
        return {"card": core.patch_card(card_id, {"pinned": False, "status": "active"})}
    except Exception as exc:
        _raise(exc)


@router.get("/cards/{card_id}/evidence")
async def get_evidence(card_id: str) -> Dict[str, Any]:
    try:
        return {"evidence": core.list_evidence(card_id)}
    except Exception as exc:
        _raise(exc)


@router.post("/cards/{card_id}/evidence")
async def post_evidence(card_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    try:
        payload = dict(body or {})
        payload["card_id"] = card_id
        return {"evidence": core.add_evidence(payload)}
    except Exception as exc:
        _raise(exc)


@router.get("/preferences")
async def get_preferences() -> Dict[str, Any]:
    return {"preferences": core.get_preferences()}


@router.put("/preferences")
async def put_preferences(body: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return {"preferences": core.put_preferences(body)}
    except Exception as exc:
        _raise(exc)


@router.get("/refresh-runs")
async def get_refresh_runs(limit: int = 50) -> Dict[str, Any]:
    try:
        return {"refresh_runs": core.list_refresh_runs(limit)}
    except Exception as exc:
        _raise(exc)


@router.post("/refresh-runs")
async def post_refresh_run(body: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return {"refresh_run": core.record_refresh(body)}
    except Exception as exc:
        _raise(exc)


@router.get("/context")
async def get_context(include_hidden: bool = False, limit: int = 100) -> Dict[str, Any]:
    try:
        return {"context_items": core.list_context_items(include_hidden=include_hidden, limit=limit)}
    except Exception as exc:
        _raise(exc)


@router.post("/context")
async def post_context(body: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return {"context_item": core.upsert_context_item(body)}
    except Exception as exc:
        _raise(exc)


@router.post("/context/refresh")
async def refresh_context(body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    try:
        body = body or {}
        return core.refresh_from_hermes_context(
            include_sessions=bool(body.get("include_sessions", True)),
            include_cron=bool(body.get("include_cron", True)),
            create_cards=bool(body.get("create_cards", False)),
        )
    except Exception as exc:
        _raise(exc)


@router.post("/context/{context_id}/hide")
async def hide_context(context_id: str) -> Dict[str, Any]:
    try:
        return {"context_item": core.hide_context_item(context_id)}
    except Exception as exc:
        _raise(exc)


@router.post("/automation/create-cron-jobs")
@router.post("/automation/ensure-jobs")
async def create_cron_jobs(body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    try:
        body = body or {}
        overrides = _schedule_overrides_from_body(body)
        _persist_schedule_overrides(overrides)
        prefs = core.get_preferences()
        existing = prefs.get("cron_jobs") or {}
        force = bool(body.get("force"))
        if existing and not force:
            return {"created": [], "existing": existing, "skipped": True, "jobs": _jobs_payload(prefs, existing, body)}

        try:
            import cron  # noqa: F401
        except Exception as exc:
            core.put_preferences({"cron_unavailable": str(exc)})
            return {
                "created": [],
                "existing": existing,
                "skipped": True,
                "error": f"cron integration unavailable: {exc}",
                "next_step": "Open Hermes and run `/personal-dashboard create-jobs` where the Hermes cron runtime is available.",
                "jobs": _jobs_payload(prefs, existing, body),
            }

        specs = _job_specs(prefs, body)
        created = []
        cron_jobs: Dict[str, str] = {}
        for kind in ("morning", "alerts", "weekend"):
            job = _create_cron_job(kind, specs[kind]["schedule"])
            created.append(job)
            if isinstance(job, dict) and job.get("id"):
                cron_jobs[kind] = str(job["id"])

        prefs["cron_jobs"] = cron_jobs
        core.put_preferences({"cron_jobs": cron_jobs})
        return {"created": created, "existing": {}, "skipped": False, "jobs": _jobs_payload(prefs, cron_jobs, body)}
    except Exception as exc:
        _raise(exc)
