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


def _raise(exc: Exception) -> None:
    status = 404 if "not found" in str(exc).lower() else 400
    raise HTTPException(status_code=status, detail=str(exc))


def _cron_prompt(kind: str) -> str:
    base = (
        "Use the hermes-personal-dashboard:briefing-curator skill. "
        "Read personal_dashboard_get_preferences and personal_dashboard_get_topics. "
        "Fetch only the user-configured generic topics with available Hermes tools. "
        "Write structured cards with personal_dashboard_upsert_card and record the run "
        "with personal_dashboard_record_refresh. Do not infer or expose private topics "
        "that the user has not configured or accepted."
    )
    if kind == "morning":
        return f"{base} Produce the morning daily briefing dashboard refresh."
    if kind == "alerts":
        return f"{base} Refresh time-sensitive alert cards such as weather, stocks, sports, news, and calendar items."
    if kind == "weekend":
        return f"{base} Produce a weekend planning refresh using configured location, calendar preference, weather, events, and interests."
    return base


def _cron_name(kind: str) -> str:
    return {
        "morning": "Personal Dashboard Morning Briefing",
        "alerts": "Personal Dashboard Alerts Refresh",
        "weekend": "Personal Dashboard Weekend Planner",
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
async def snapshot() -> Dict[str, Any]:
    return core.dashboard_snapshot()


@router.get("/cards")
async def get_cards(
    status: Optional[str] = Query(None),
    domain: Optional[str] = Query(None),
    include_hidden: bool = False,
    limit: int = 200,
) -> Dict[str, Any]:
    try:
        return {"cards": core.list_cards(status=status, domain=domain, include_hidden=include_hidden, limit=limit)}
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


@router.get("/topics")
async def get_topics(include_disabled: bool = True) -> Dict[str, Any]:
    try:
        return {"topics": core.list_topics(include_disabled=include_disabled)}
    except Exception as exc:
        _raise(exc)


@router.post("/topics")
async def post_topic(body: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return {"topic": core.upsert_topic(body)}
    except Exception as exc:
        _raise(exc)


@router.patch("/topics/{topic_id}")
async def patch_topic(topic_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return {"topic": core.patch_topic(topic_id, body)}
    except Exception as exc:
        _raise(exc)


@router.delete("/topics/{topic_id}")
async def delete_topic(topic_id: str) -> Dict[str, Any]:
    try:
        return core.delete_topic(topic_id)
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


@router.get("/suggestions")
async def get_suggestions(status: Optional[str] = "pending") -> Dict[str, Any]:
    try:
        return {"suggestions": core.list_suggestions(status)}
    except Exception as exc:
        _raise(exc)


@router.post("/suggestions")
async def post_suggestion(body: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return {"suggestion": core.suggest(body)}
    except Exception as exc:
        _raise(exc)


@router.post("/suggestions/discover")
async def discover_suggestions() -> Dict[str, Any]:
    try:
        return core.discover_suggestions_from_memory()
    except Exception as exc:
        _raise(exc)


@router.post("/suggestions/{suggestion_id}/accept")
async def accept_suggestion(suggestion_id: str) -> Dict[str, Any]:
    try:
        return core.accept_suggestion(suggestion_id)
    except Exception as exc:
        _raise(exc)


@router.post("/suggestions/{suggestion_id}/dismiss")
async def dismiss_suggestion(suggestion_id: str) -> Dict[str, Any]:
    try:
        return {"suggestion": core.dismiss_suggestion(suggestion_id)}
    except Exception as exc:
        _raise(exc)


@router.get("/setup/status")
async def get_setup_status() -> Dict[str, Any]:
    return core.setup_status()


@router.post("/setup/save")
async def save_setup(body: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return core.save_setup(body)
    except Exception as exc:
        _raise(exc)


@router.post("/setup/create-cron-jobs")
async def create_cron_jobs(body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    try:
        body = body or {}
        prefs = core.get_preferences()
        existing = prefs.get("cron_jobs") or {}
        force = bool(body.get("force"))
        if existing and not force:
            return {"created": [], "existing": existing, "skipped": True}

        schedules = {
            "morning": _parse_hhmm(prefs.get("briefing_time") or body.get("briefing_time")),
            "alerts": _alert_schedule(prefs.get("alert_frequency") or body.get("alert_frequency")),
        }
        if prefs.get("weekend_planner", True):
            schedules["weekend"] = "0 15 * * 5"

        created = []
        cron_jobs: Dict[str, str] = {}
        for kind, schedule in schedules.items():
            job = _create_cron_job(kind, schedule)
            created.append(job)
            if isinstance(job, dict) and job.get("id"):
                cron_jobs[kind] = str(job["id"])

        prefs["cron_jobs"] = cron_jobs
        core.put_preferences({"cron_jobs": cron_jobs})
        return {"created": created, "existing": {}, "skipped": False}
    except Exception as exc:
        _raise(exc)
