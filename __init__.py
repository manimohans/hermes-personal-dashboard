"""Hermes Personal Dashboard plugin registration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict

from . import personal_dashboard_core as core
from . import schemas


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


def _handle_add_starter_topics(params: Dict[str, Any]) -> Any:
    del params
    return core.add_starter_topics()


def _handle_create_sample_cards(params: Dict[str, Any]) -> Any:
    del params
    return core.create_sample_cards()


_HANDLERS = {
    "personal_dashboard_upsert_card": _handle_upsert_card,
    "personal_dashboard_expire_card": _handle_expire_card,
    "personal_dashboard_add_evidence": _handle_add_evidence,
    "personal_dashboard_list_cards": _handle_list_cards,
    "personal_dashboard_record_refresh": _handle_record_refresh,
    "personal_dashboard_suggest_card": _handle_suggest_card,
    "personal_dashboard_upsert_topic": _handle_upsert_topic,
    "personal_dashboard_get_topics": _handle_get_topics,
    "personal_dashboard_get_preferences": _handle_get_preferences,
    "personal_dashboard_get_snapshot": _handle_get_snapshot,
    "personal_dashboard_add_starter_topics": _handle_add_starter_topics,
    "personal_dashboard_create_sample_cards": _handle_create_sample_cards,
}


_HELP = """\
/personal-dashboard - Hermes Personal Dashboard

Subcommands:
  status           Show setup, card, topic, refresh, and suggestion counts
  starter-topics   Add generic starter topics for common dashboard domains
  sample-cards     Create generic sample cards so the dashboard is not blank
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
