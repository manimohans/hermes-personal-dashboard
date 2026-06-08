"""Hermes Personal Dashboard plugin registration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict

from . import personal_dashboard_core as core
from . import schemas


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


def _create_standard_cron_jobs(force: bool = False) -> Dict[str, Any]:
    prefs = core.get_preferences()
    existing = prefs.get("cron_jobs") or {}
    if existing and not force:
        return {"created": [], "existing": existing, "skipped": True}

    from cron import jobs as cron_jobs

    schedules = {
        "morning": _parse_hhmm(prefs.get("briefing_time")),
        "alerts": _alert_schedule(prefs.get("alert_frequency")),
    }
    if prefs.get("weekend_planner", True):
        schedules["weekend"] = "0 15 * * 5"

    created = []
    cron_job_ids: Dict[str, str] = {}
    for kind, schedule in schedules.items():
        job = cron_jobs.create_job(
            prompt=_cron_prompt(kind),
            schedule=schedule,
            name=_cron_name(kind),
            deliver="local",
            skills=[f"{core.PLUGIN_ID}:briefing-curator"],
            origin={"plugin": core.PLUGIN_ID, "kind": kind},
        )
        created.append(job)
        if isinstance(job, dict) and job.get("id"):
            cron_job_ids[kind] = str(job["id"])

    core.put_preferences({"cron_jobs": cron_job_ids})
    return {"created": created, "existing": {}, "skipped": False}


def _ok(payload: Any) -> str:
    return json.dumps({"success": True, "data": payload}, ensure_ascii=True)


def _err(exc: Exception) -> str:
    return json.dumps({"success": False, "error": str(exc)}, ensure_ascii=True)


def _tool(handler: Callable[[Dict[str, Any]], Any]) -> Callable[[Dict[str, Any]], str]:
    def wrapped(params: Dict[str, Any], **_: Any) -> str:
        try:
            return _ok(handler(params or {}))
        except Exception as exc:
            return _err(exc)

    return wrapped


def _handle_upsert_card(params: Dict[str, Any]) -> Any:
    return core.upsert_card(params)


def _handle_patch_card(params: Dict[str, Any]) -> Any:
    card_id = str(params.get("id") or "")
    payload = dict(params)
    payload.pop("id", None)
    return core.patch_card(card_id, payload)


def _handle_expire_card(params: Dict[str, Any]) -> Any:
    return core.expire_card(str(params.get("id") or ""))


def _handle_add_evidence(params: Dict[str, Any]) -> Any:
    return core.add_evidence(params)


def _handle_list_cards(params: Dict[str, Any]) -> Any:
    return core.list_cards(
        status=params.get("status"),
        domain=params.get("domain"),
        include_hidden=bool(params.get("include_hidden", False)),
        limit=int(params.get("limit") or 200),
    )


def _handle_record_refresh(params: Dict[str, Any]) -> Any:
    return core.record_refresh(params)


def _handle_suggest_card(params: Dict[str, Any]) -> Any:
    return core.suggest(params)


def _handle_upsert_topic(params: Dict[str, Any]) -> Any:
    return core.upsert_topic(params)


def _handle_get_topics(params: Dict[str, Any]) -> Any:
    return core.list_topics(include_disabled=bool(params.get("include_disabled", True)))


def _handle_get_preferences(params: Dict[str, Any]) -> Any:
    del params
    return core.get_preferences()


def _handle_get_snapshot(params: Dict[str, Any]) -> Any:
    del params
    return core.dashboard_snapshot()


def _handle_save_setup(params: Dict[str, Any]) -> Any:
    return core.save_setup(params)


def _handle_add_starter_topics(params: Dict[str, Any]) -> Any:
    del params
    return core.add_starter_topics()


def _handle_create_sample_cards(params: Dict[str, Any]) -> Any:
    del params
    return core.create_sample_cards()


def _handle_create_cron_jobs(params: Dict[str, Any]) -> Any:
    return _create_standard_cron_jobs(force=bool(params.get("force", False)))


def _handle_quickstart(params: Dict[str, Any]) -> Any:
    setup_keys = {
        "briefing_time",
        "timezone",
        "location",
        "alert_frequency",
        "calendar_enabled",
        "weekend_planner",
        "source_preferences",
        "topics",
    }
    setup_payload = {key: params[key] for key in setup_keys if key in params}
    result: Dict[str, Any] = {}
    if setup_payload:
        result["setup"] = core.save_setup(setup_payload)
    result["starter_topics"] = core.add_starter_topics()
    if bool(params.get("create_sample_cards", True)):
        result["sample_cards"] = core.create_sample_cards()
    if bool(params.get("create_cron_jobs", False)):
        result["cron_jobs"] = _create_standard_cron_jobs(force=False)
    result["snapshot"] = core.dashboard_snapshot()
    return result


_HANDLERS = {
    "personal_dashboard_upsert_card": _handle_upsert_card,
    "personal_dashboard_patch_card": _handle_patch_card,
    "personal_dashboard_expire_card": _handle_expire_card,
    "personal_dashboard_add_evidence": _handle_add_evidence,
    "personal_dashboard_list_cards": _handle_list_cards,
    "personal_dashboard_record_refresh": _handle_record_refresh,
    "personal_dashboard_suggest_card": _handle_suggest_card,
    "personal_dashboard_upsert_topic": _handle_upsert_topic,
    "personal_dashboard_get_topics": _handle_get_topics,
    "personal_dashboard_get_preferences": _handle_get_preferences,
    "personal_dashboard_get_snapshot": _handle_get_snapshot,
    "personal_dashboard_save_setup": _handle_save_setup,
    "personal_dashboard_add_starter_topics": _handle_add_starter_topics,
    "personal_dashboard_create_sample_cards": _handle_create_sample_cards,
    "personal_dashboard_create_cron_jobs": _handle_create_cron_jobs,
    "personal_dashboard_quickstart": _handle_quickstart,
}


_HELP = """\
/personal-dashboard - Hermes Personal Dashboard

Subcommands:
  status           Show setup, card, topic, refresh, and suggestion counts
  starter-topics   Add generic starter topics for common dashboard domains
  sample-cards     Create generic sample cards so the dashboard is not blank
  quickstart       Add starter topics and sample cards in one step
  create-jobs      Create the standard Hermes cron refresh jobs
  discover         Scan Hermes memory for pending topic suggestions
  help             Show this help

Open the visual dashboard from `hermes dashboard` at the Personal Dashboard tab.
The dashboard setup wizard configures generic topics, schedules, and source preferences.
"""


def _handle_slash(raw_args: str) -> str:
    argv = (raw_args or "").strip().split()
    sub = argv[0].lower() if argv else "help"
    try:
        if sub in {"help", "-h", "--help"}:
            return _HELP
        if sub == "status":
            snapshot = core.dashboard_snapshot()
            return (
                "Hermes Personal Dashboard\n"
                f"  configured: {snapshot['setup']['configured']}\n"
                f"  cards: {len(snapshot['cards'])}\n"
                f"  topics: {len(snapshot['topics'])}\n"
                f"  refresh runs: {len(snapshot['refresh_runs'])}\n"
                f"  pending suggestions: {len(snapshot['suggestions'])}\n"
                f"  db: {core.db_path()}"
            )
        if sub in {"starter-topics", "starters"}:
            result = core.add_starter_topics()
            return f"Added or updated {result['count']} starter topic(s). Open the dashboard Setup panel to customize them."
        if sub in {"sample-cards", "demo"}:
            result = core.create_sample_cards()
            return f"Created or updated {result['count']} sample card(s). Dismiss them when you are ready for live cards."
        if sub in {"quickstart", "setup"}:
            topics = core.add_starter_topics()
            cards = core.create_sample_cards()
            return (
                "Hermes Personal Dashboard quickstart complete.\n"
                f"  starter topics: {topics['count']}\n"
                f"  sample cards: {cards['count']}\n"
                "Next: open the Personal Dashboard tab, add your location/time, save setup, then create jobs."
            )
        if sub in {"create-jobs", "jobs"}:
            result = _create_standard_cron_jobs(force=False)
            if result.get("skipped"):
                return f"Cron jobs already exist: {result['existing']}"
            return f"Created {len(result.get('created') or [])} cron job(s)."
        if sub == "discover":
            result = core.discover_suggestions_from_memory()
            return f"Created {result['count']} pending suggestion(s). Review them in the dashboard Setup tab."
        return f"Unknown subcommand: {sub}\n\n{_HELP}"
    except Exception as exc:
        return f"personal-dashboard failed: {exc}"


def _register_skills(ctx) -> None:
    skills_dir = Path(__file__).parent / "skills"
    if not skills_dir.exists():
        return
    for child in sorted(skills_dir.iterdir()):
        skill_md = child / "SKILL.md"
        if child.is_dir() and skill_md.exists():
            ctx.register_skill(child.name, skill_md)


def register(ctx) -> None:
    """Register dashboard tools, slash command, and plugin-provided skills."""
    for schema in schemas.ALL_SCHEMAS:
        name = schema["name"]
        ctx.register_tool(
            name=name,
            toolset="personal_dashboard",
            schema=schema,
            handler=_tool(_HANDLERS[name]),
            description=schema.get("description", ""),
        )

    ctx.register_command(
        "personal-dashboard",
        handler=_handle_slash,
        description="Manage the Hermes Personal Dashboard.",
    )

    _register_skills(ctx)
