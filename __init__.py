"""Hermes Personal Dashboard plugin registration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from . import personal_dashboard_core as core
from . import schemas

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
    number = _day_number(value)
    labels = ["Sundays", "Mondays", "Tuesdays", "Wednesdays", "Thursdays", "Fridays", "Saturdays"]
    return labels[number]


def _job_specs(prefs: Dict[str, Any], overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Dict[str, str]]:
    overrides = overrides or {}
    briefing_time = str(
        overrides.get("daily_time")
        or overrides.get("briefing_time")
        or prefs.get("daily_time")
        or prefs.get("daily_refresh_time")
        or prefs.get("briefing_time")
        or "07:30"
    )
    alert_frequency = str(
        overrides.get("frequent_refresh")
        or overrides.get("alert_frequency")
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


def _jobs_payload(prefs: Dict[str, Any], job_ids: Dict[str, Any], overrides: Optional[Dict[str, Any]] = None) -> list[Dict[str, Any]]:
    specs = _job_specs(prefs, overrides)
    rows = []
    for kind in ("morning", "alerts", "weekend"):
        spec = dict(specs[kind])
        spec["kind"] = kind
        if kind in job_ids:
            spec["id"] = str(job_ids[kind])
        rows.append(spec)
    return rows


def _persist_schedule_overrides(overrides: Dict[str, Any]) -> None:
    values = {
        key: value
        for key, value in overrides.items()
        if key in {"daily_time", "frequent_refresh", "planning_day", "planning_time"}
    }
    if values:
        core.put_preferences(values)


def _create_standard_cron_jobs(force: bool = False, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    overrides = overrides or {}
    _persist_schedule_overrides(overrides)
    prefs = core.get_preferences()
    existing = prefs.get("cron_jobs") or {}
    if existing and not force:
        return {"created": [], "existing": existing, "skipped": True, "jobs": _jobs_payload(prefs, existing, overrides)}

    try:
        from cron import jobs as cron_jobs
    except Exception as exc:
        core.put_preferences({"cron_unavailable": str(exc)})
        return {
            "created": [],
            "existing": existing,
            "skipped": True,
            "error": f"cron integration unavailable: {exc}",
            "next_step": "Run `/personal-dashboard create-jobs` inside Hermes where the cron runtime is available.",
            "jobs": _jobs_payload(prefs, existing, overrides),
        }

    specs = _job_specs(prefs, overrides)
    created = []
    cron_job_ids: Dict[str, str] = {}
    for kind in ("morning", "alerts", "weekend"):
        job = cron_jobs.create_job(
            prompt=_cron_prompt(kind),
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
    return {"created": created, "existing": {}, "skipped": False, "jobs": _jobs_payload(prefs, cron_job_ids, overrides)}


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
        include_scanner=bool(params.get("include_scanner", False)),
        limit=int(params.get("limit") or 200),
    )


def _handle_record_refresh(params: Dict[str, Any]) -> Any:
    return core.record_refresh(params)


def _handle_upsert_context(params: Dict[str, Any]) -> Any:
    return core.upsert_context_item(params)


def _handle_list_context(params: Dict[str, Any]) -> Any:
    return core.list_context_items(
        include_hidden=bool(params.get("include_hidden", False)),
        limit=int(params.get("limit") or 100),
    )


def _handle_hide_context(params: Dict[str, Any]) -> Any:
    return core.hide_context_item(str(params.get("id") or ""))


def _handle_get_preferences(params: Dict[str, Any]) -> Any:
    del params
    return core.get_preferences()


def _handle_get_snapshot(params: Dict[str, Any]) -> Any:
    auto_refresh = params.get("auto_refresh")
    return core.dashboard_snapshot(auto_refresh=True if auto_refresh is None else bool(auto_refresh))


def _schedule_overrides_from_params(params: Dict[str, Any]) -> Dict[str, Any]:
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
    overrides: Dict[str, Any] = {}
    for key, value in (params or {}).items():
        if key in aliases and value is not None and value != "":
            overrides[aliases[key]] = value
    planning = str((params or {}).get("planning") or (params or {}).get("weekly") or "").strip()
    if "@" in planning:
        day, time = planning.split("@", 1)
        overrides["planning_day"] = day
        overrides["planning_time"] = time
    return overrides


def _parse_create_jobs_args(tokens: list[str]) -> Dict[str, Any]:
    params: Dict[str, Any] = {}
    for token in tokens:
        text = token.strip()
        if not text:
            continue
        if text in {"force", "--force"}:
            params["force"] = True
            continue
        if "=" not in text:
            continue
        key, value = text.split("=", 1)
        params[key.strip().lower().replace("-", "_")] = value.strip()
    return params


def _handle_create_cron_jobs(params: Dict[str, Any]) -> Any:
    return _create_standard_cron_jobs(
        force=bool(params.get("force", False)),
        overrides=_schedule_overrides_from_params(params),
    )


def _format_job_lines(jobs: Any) -> str:
    rows = []
    for job in jobs or []:
        name = job.get("name") or job.get("kind") or "Dashboard job"
        cadence = job.get("cadence") or job.get("schedule") or "scheduled"
        purpose = job.get("purpose") or "refresh dashboard cards"
        rows.append(f"  - {name}: {cadence}; {purpose}.")
    return "\n".join(rows)


def _handle_refresh_from_hermes(params: Dict[str, Any]) -> Any:
    return core.refresh_from_hermes_context(
        include_sessions=bool(params.get("include_sessions", True)),
        include_cron=bool(params.get("include_cron", True)),
        create_cards=bool(params.get("create_cards", False)),
    )


_HANDLERS = {
    "personal_dashboard_upsert_card": _handle_upsert_card,
    "personal_dashboard_patch_card": _handle_patch_card,
    "personal_dashboard_expire_card": _handle_expire_card,
    "personal_dashboard_add_evidence": _handle_add_evidence,
    "personal_dashboard_list_cards": _handle_list_cards,
    "personal_dashboard_record_refresh": _handle_record_refresh,
    "personal_dashboard_upsert_context": _handle_upsert_context,
    "personal_dashboard_list_context": _handle_list_context,
    "personal_dashboard_hide_context": _handle_hide_context,
    "personal_dashboard_get_snapshot": _handle_get_snapshot,
    "personal_dashboard_refresh_from_hermes": _handle_refresh_from_hermes,
    "personal_dashboard_get_preferences": _handle_get_preferences,
    "personal_dashboard_create_cron_jobs": _handle_create_cron_jobs,
}


_HELP = """\
/personal-dashboard - Hermes Personal Dashboard

Subcommands:
  status           Show card, inferred context, source, and refresh counts
  refresh          Scan Hermes memory, sessions, and cron output now
  context          List the top inferred context items
  create-jobs      Install auto updates by creating Hermes curator cron jobs
  help             Show this help

Open the visual dashboard from `hermes dashboard` at the Personal Dashboard tab.
No setup is required. The dashboard reflects what Hermes already knows from memory,
session history, cron output, and prior agent work.

Schedule overrides are optional:
  /personal-dashboard create-jobs daily=09:00 frequent=30m planning=mon@16:00 force
"""


def _handle_slash(raw_args: str) -> str:
    argv = (raw_args or "").strip().split()
    sub = argv[0].lower() if argv else "help"
    try:
        if sub in {"help", "-h", "--help"}:
            return _HELP
        if sub == "status":
            snapshot = core.dashboard_snapshot()
            automation = snapshot.get("automation") or {}
            source_report = snapshot.get("source_report") or {}
            by_type = source_report.get("by_type") or {}
            source_types = ", ".join(f"{key}={value}" for key, value in sorted(by_type.items())) or "none yet"
            return (
                "Hermes Personal Dashboard\n"
                "  mode: autonomous\n"
                f"  cards: {len(snapshot['cards'])}\n"
                f"  inferred context: {len(snapshot['context_items'])}\n"
                f"  readable sources: {source_report.get('source_count', 0)} ({source_types})\n"
                f"  refresh runs: {len(snapshot['refresh_runs'])}\n"
                f"  last scan refreshed: {automation.get('refreshed')}\n"
                f"  db: {core.db_path()}"
            )
        if sub == "refresh":
            result = core.refresh_from_hermes_context(create_cards=False)
            return (
                "Hermes Personal Dashboard refreshed from Hermes context.\n"
                f"  sources scanned: {result['sources']}\n"
                f"  inferred context: {len(result['context_items'])}\n"
                f"  cards updated: {len(result['cards'])} curated\n"
                f"  scanner cards suppressed: {result.get('scanner_cards_suppressed', 0)}"
            )
        if sub == "context":
            items = core.list_context_items(limit=12)
            if not items:
                snapshot = core.dashboard_snapshot(auto_refresh=False)
                report = snapshot.get("source_report") or {}
                return (
                    "No inferred context items yet.\n"
                    f"  readable sources: {report.get('source_count', 0)}\n"
                    "Open the dashboard or run `/personal-dashboard refresh` after Hermes has memory or sessions."
                )
            lines = ["Top inferred dashboard context:"]
            for item in items:
                lines.append(f"  - {item['domain']}: {item['label']}")
            return "\n".join(lines)
        if sub in {"create-jobs", "jobs"}:
            params = _parse_create_jobs_args(argv[1:])
            schedule_hint = (
                "Schedule hint: these are starter defaults. Change them with "
                "`/personal-dashboard create-jobs daily=09:00 frequent=30m planning=mon@16:00 force`."
            )
            result = _create_standard_cron_jobs(
                force=bool(params.get("force", False)),
                overrides=_schedule_overrides_from_params(params),
            )
            jobs = _format_job_lines(result.get("jobs"))
            if result.get("error"):
                return (
                    "Auto updates were not installed.\n"
                    "Tried to create these scheduled Hermes curator jobs:\n"
                    f"{jobs}\n"
                    f"  {schedule_hint}\n"
                    f"  error: {result['error']}\n"
                    f"  next: {result.get('next_step') or 'Run this command inside Hermes.'}"
                )
            scan = core.refresh_from_hermes_context(create_cards=False)
            scan_lines = (
                "Immediate scan completed.\n"
                f"  sources scanned: {scan['sources']}\n"
                f"  inferred signals: {len(scan['context_items'])}\n"
                f"  curated cards currently stored: {len(scan['cards'])}\n"
                "  note: scheduled jobs are installed, but they run later; job creation does not execute the curator immediately."
            )
            if result.get("skipped"):
                return (
                    "Auto updates were already installed.\n"
                    f"{jobs}\n\n"
                    f"{schedule_hint}\n\n"
                    f"{scan_lines}"
                )
            return (
                f"Auto updates installed: created {len(result.get('created') or [])} scheduled Hermes curator job(s).\n"
                f"{jobs}\n\n"
                f"{schedule_hint}\n\n"
                f"{scan_lines}"
            )
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
