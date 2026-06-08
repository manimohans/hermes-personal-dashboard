"""Tool schemas exposed by Hermes Personal Dashboard."""

CARD_PROPERTIES = {
    "id": {
        "type": "string",
        "description": "Stable card id. Reuse the same id to update the same card on future runs.",
    },
    "context_id": {"type": "string", "description": "Optional inferred context id this card belongs to."},
    "domain": {
        "type": "string",
        "description": "Card domain such as news, weather, stocks, sports, calendar, planning, project, or alerts.",
    },
    "title": {"type": "string", "description": "Short card title."},
    "summary": {"type": "string", "description": "One-to-three sentence summary for the dashboard."},
    "detail_md": {"type": "string", "description": "Optional Markdown detail shown when a card is expanded."},
    "priority": {
        "type": "string",
        "enum": ["low", "medium", "high", "critical"],
        "description": "How important or urgent the card is.",
    },
    "status": {
        "type": "string",
        "enum": ["active", "stale", "dismissed", "expired", "pinned"],
        "description": "Current card state.",
    },
    "pinned": {"type": "boolean", "description": "Keep the card near the top of the dashboard."},
    "updated_at": {"type": "string", "description": "ISO-8601 timestamp. Defaults to now if omitted."},
    "valid_until": {"type": "string", "description": "ISO-8601 timestamp after which active cards become stale."},
    "source_label": {"type": "string", "description": "Human-readable source label."},
    "source_url": {"type": "string", "description": "Optional source URL."},
    "why_shown": {"type": "string", "description": "Why this card is relevant to the user."},
    "confidence": {"type": "number", "description": "Optional confidence from 0 to 1."},
    "payload": {"type": "object", "description": "Optional structured metadata. Use ai_curated=true for Hermes-written visible cards; section and relevance_score can guide placement/ranking."},
}

PERSONAL_DASHBOARD_UPSERT_CARD = {
    "name": "personal_dashboard_upsert_card",
    "description": "Create or update one visible dashboard card with provenance and freshness metadata.",
    "parameters": {
        "type": "object",
        "properties": CARD_PROPERTIES,
        "required": ["id", "domain", "title", "summary"],
    },
}

PERSONAL_DASHBOARD_PATCH_CARD = {
    "name": "personal_dashboard_patch_card",
    "description": "Update selected fields on an existing dashboard card, such as priority, status, pinned, summary, or valid_until.",
    "parameters": {
        "type": "object",
        "properties": CARD_PROPERTIES,
        "required": ["id"],
    },
}

PERSONAL_DASHBOARD_EXPIRE_CARD = {
    "name": "personal_dashboard_expire_card",
    "description": "Mark a dashboard card as expired so it no longer appears in active views.",
    "parameters": {
        "type": "object",
        "properties": {"id": {"type": "string", "description": "Card id to expire."}},
        "required": ["id"],
    },
}

PERSONAL_DASHBOARD_ADD_EVIDENCE = {
    "name": "personal_dashboard_add_evidence",
    "description": "Attach source evidence to a dashboard card.",
    "parameters": {
        "type": "object",
        "properties": {
            "card_id": {"type": "string", "description": "Existing card id."},
            "source_label": {"type": "string"},
            "source_url": {"type": "string"},
            "title": {"type": "string"},
            "excerpt": {"type": "string"},
            "captured_at": {"type": "string", "description": "ISO-8601 timestamp. Defaults to now."},
            "payload": {"type": "object"},
        },
        "required": ["card_id"],
    },
}

PERSONAL_DASHBOARD_LIST_CARDS = {
    "name": "personal_dashboard_list_cards",
    "description": "List dashboard cards, optionally filtered by status or domain.",
    "parameters": {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["active", "stale", "dismissed", "expired", "pinned"]},
            "domain": {"type": "string"},
            "include_hidden": {"type": "boolean", "description": "Include dismissed and expired cards."},
            "include_scanner": {"type": "boolean", "description": "Debug only: include legacy scanner-generated cards that are hidden from normal views."},
            "limit": {"type": "integer", "minimum": 1, "maximum": 500},
        },
    },
}

PERSONAL_DASHBOARD_RECORD_REFRESH = {
    "name": "personal_dashboard_record_refresh",
    "description": "Record the result of a dashboard refresh job.",
    "parameters": {
        "type": "object",
        "properties": {
            "job_key": {"type": "string", "description": "Stable refresh job identifier."},
            "status": {"type": "string", "enum": ["running", "success", "error"]},
            "summary": {"type": "string"},
            "started_at": {"type": "string"},
            "ended_at": {"type": "string"},
            "error": {"type": "string"},
            "payload": {"type": "object"},
        },
        "required": ["job_key", "status"],
    },
}

CONTEXT_PROPERTIES = {
    "id": {"type": "string", "description": "Stable inferred context id."},
    "domain": {
        "type": "string",
        "description": "Inferred domain such as news, weather, stocks, sports, calendar, family, planning, projects, or alerts.",
    },
    "label": {"type": "string", "description": "Short human-readable description of what Hermes appears to know or watch."},
    "summary": {"type": "string", "description": "Why this context appears relevant."},
    "evidence": {"type": "array", "items": {"type": "object"}, "description": "Source snippets from Hermes memory, sessions, or cron output."},
    "source_types": {"type": "array", "items": {"type": "string"}, "description": "Source types such as memory, session, cron, or user_profile."},
    "confidence": {"type": "number", "description": "Confidence from 0 to 1."},
    "score": {"type": "number", "description": "Internal relevance score."},
    "status": {"type": "string", "enum": ["active", "hidden"]},
    "payload": {"type": "object"},
}

PERSONAL_DASHBOARD_UPSERT_CONTEXT = {
    "name": "personal_dashboard_upsert_context",
    "description": "Create or update an inferred dashboard context item from Hermes memory/session knowledge. This is not user setup.",
    "parameters": {
        "type": "object",
        "properties": CONTEXT_PROPERTIES,
        "required": ["domain", "label"],
    },
}

PERSONAL_DASHBOARD_LIST_CONTEXT = {
    "name": "personal_dashboard_list_context",
    "description": "List context items automatically inferred from Hermes memory, sessions, and cron output.",
    "parameters": {
        "type": "object",
        "properties": {
            "include_hidden": {"type": "boolean", "description": "Include hidden context items."},
            "limit": {"type": "integer", "minimum": 1, "maximum": 500},
        },
    },
}

PERSONAL_DASHBOARD_HIDE_CONTEXT = {
    "name": "personal_dashboard_hide_context",
    "description": "Hide an inferred context item and suppress any legacy scanner-generated dashboard card for it.",
    "parameters": {
        "type": "object",
        "properties": {"id": {"type": "string", "description": "Context item id."}},
        "required": ["id"],
    },
}

PERSONAL_DASHBOARD_GET_SNAPSHOT = {
    "name": "personal_dashboard_get_snapshot",
    "description": "Return the autonomous dashboard snapshot. By default this reflects current Hermes memory/session context.",
    "parameters": {
        "type": "object",
        "properties": {
            "auto_refresh": {"type": "boolean", "description": "Refresh from Hermes context before returning. Defaults to true."}
        },
    },
}

PERSONAL_DASHBOARD_REFRESH_FROM_HERMES = {
    "name": "personal_dashboard_refresh_from_hermes",
    "description": "Scan existing Hermes memory, session history, and cron output, infer relevant context signals, and suppress raw scanner cards. Requires no user setup. Useful visible cards should be written separately with personal_dashboard_upsert_card.",
    "parameters": {
        "type": "object",
        "properties": {
            "include_sessions": {"type": "boolean", "description": "Scan ~/.hermes/state.db when available. Defaults to true."},
            "include_cron": {"type": "boolean", "description": "Scan cron jobs and recent cron output when available. Defaults to true."},
            "create_cards": {"type": "boolean", "description": "Legacy flag. Context scans do not create visible cards; Hermes should curate cards with personal_dashboard_upsert_card. Defaults to false."},
        },
    },
}

PERSONAL_DASHBOARD_GET_PREFERENCES = {
    "name": "personal_dashboard_get_preferences",
    "description": "Return internal dashboard preferences such as autonomous refresh timestamps and cron job ids.",
    "parameters": {"type": "object", "properties": {}},
}

PERSONAL_DASHBOARD_CREATE_CRON_JOBS = {
    "name": "personal_dashboard_create_cron_jobs",
    "description": "Install scheduled Personal Dashboard Hermes curator jobs. This schedules morning, alert, and weekend jobs; it does not run the curator immediately.",
    "parameters": {
        "type": "object",
        "properties": {
            "force": {"type": "boolean", "description": "Create replacement jobs even if job ids are already stored."},
        },
    },
}

ALL_SCHEMAS = [
    PERSONAL_DASHBOARD_UPSERT_CARD,
    PERSONAL_DASHBOARD_PATCH_CARD,
    PERSONAL_DASHBOARD_EXPIRE_CARD,
    PERSONAL_DASHBOARD_ADD_EVIDENCE,
    PERSONAL_DASHBOARD_LIST_CARDS,
    PERSONAL_DASHBOARD_RECORD_REFRESH,
    PERSONAL_DASHBOARD_UPSERT_CONTEXT,
    PERSONAL_DASHBOARD_LIST_CONTEXT,
    PERSONAL_DASHBOARD_HIDE_CONTEXT,
    PERSONAL_DASHBOARD_GET_SNAPSHOT,
    PERSONAL_DASHBOARD_REFRESH_FROM_HERMES,
    PERSONAL_DASHBOARD_GET_PREFERENCES,
    PERSONAL_DASHBOARD_CREATE_CRON_JOBS,
]
