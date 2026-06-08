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
        "Start with personal_dashboard_refresh_from_hermes so the dashboard reflects "
        "existing Hermes memory, sessions, cron output, and prior agent work without "
        "requiring user setup. Then read personal_dashboard_list_context and use the "
        "available Hermes tools to refresh useful live cards for the inferred context. "
        "Write structured cards with personal_dashboard_upsert_card and record the run "
        "with personal_dashboard_record_refresh. Show provenance and why each card was shown."
    )
    if kind == "morning":
        return f"{base} Produce the autonomous morning dashboard refresh."
    if kind == "alerts":
        return f"{base} Refresh time-sensitive cards such as weather, stocks, sports, news, calendar, family, project, and alert items inferred from Hermes context."
    if kind == "weekend":
        return f"{base} Produce a weekend/planning refresh from whatever Hermes already knows is relevant."
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

    try:
        from cron import jobs as cron_jobs
    except Exception as exc:
        core.put_preferences({"cron_unavailable": str(exc)})
        return {"created": [], "existing": existing, "skipped": True, "error": f"cron integration unavailable: {exc}"}

    schedules = {
        "morning": _parse_hhmm(prefs.get("briefing_time") or "07:30"),
        "alerts": _alert_schedule(prefs.get("alert_frequency") or "hourly"),
    }
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


def _handle_create_cron_jobs(params: Dict[str, Any]) -> Any:
    return _create_standard_cron_jobs(force=bool(params.get("force", False)))


def _handle_refresh_from_hermes(params: Dict[str, Any]) -> Any:
    return core.refresh_from_hermes_context(
        include_sessions=bool(params.get("include_sessions", True)),
        include_cron=bool(params.get("include_cron", True)),
        create_cards=bool(params.get("create_cards", True)),
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
  create-jobs      Create autonomous Hermes cron refresh jobs
  help             Show this help

Open the visual dashboard from `hermes dashboard` at the Personal Dashboard tab.
No setup is required. The dashboard reflects what Hermes already knows from memory,
session history, cron output, and prior agent work.
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
            return (
                "Hermes Personal Dashboard\n"
                "  mode: autonomous\n"
                f"  cards: {len(snapshot['cards'])}\n"
                f"  inferred context: {len(snapshot['context_items'])}\n"
                f"  refresh runs: {len(snapshot['refresh_runs'])}\n"
                f"  last scan refreshed: {automation.get('refreshed')}\n"
                f"  db: {core.db_path()}"
            )
        if sub == "refresh":
            result = core.refresh_from_hermes_context()
            return (
                "Hermes Personal Dashboard refreshed from Hermes context.\n"
                f"  sources scanned: {result['sources']}\n"
                f"  inferred context: {len(result['context_items'])}\n"
                f"  cards updated: {len(result['cards'])}"
            )
        if sub == "context":
            items = core.list_context_items(limit=12)
            if not items:
                return "No inferred context items yet. Open the dashboard or run `/personal-dashboard refresh` after Hermes has memory or sessions."
            lines = ["Top inferred dashboard context:"]
            for item in items:
                lines.append(f"  - {item['domain']}: {item['label']}")
            return "\n".join(lines)
        if sub in {"create-jobs", "jobs"}:
            result = _create_standard_cron_jobs(force=False)
            if result.get("skipped"):
                return f"Cron jobs already exist: {result['existing']}"
            return f"Created {len(result.get('created') or [])} cron job(s)."
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
