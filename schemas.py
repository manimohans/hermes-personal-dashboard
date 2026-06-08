"""Tool schemas exposed by Hermes Personal Dashboard."""

CARD_PROPERTIES = {
    "id": {
        "type": "string",
        "description": "Stable card id. Reuse the same id to update the same card on future runs.",
    },
    "topic_id": {"type": "string", "description": "Optional topic id this card belongs to."},
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
    "payload": {"type": "object", "description": "Optional structured metadata."},
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

PERSONAL_DASHBOARD_SUGGEST_CARD = {
    "name": "personal_dashboard_suggest_card",
    "description": "Create a pending suggestion. Suggestions are not visible cards until the user accepts them.",
    "parameters": {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "kind": {"type": "string", "description": "Suggestion kind, typically card or topic."},
            "title": {"type": "string"},
            "summary": {"type": "string"},
            "payload": {"type": "object", "description": "Suggested card/topic payload."},
        },
        "required": ["title"],
    },
}

PERSONAL_DASHBOARD_GET_TOPICS = {
    "name": "personal_dashboard_get_topics",
    "description": "Return configured dashboard topics and interests.",
    "parameters": {"type": "object", "properties": {"include_disabled": {"type": "boolean"}}},
}

PERSONAL_DASHBOARD_GET_PREFERENCES = {
    "name": "personal_dashboard_get_preferences",
    "description": "Return dashboard setup preferences such as location, briefing time, and source settings.",
    "parameters": {"type": "object", "properties": {}},
}

ALL_SCHEMAS = [
    PERSONAL_DASHBOARD_UPSERT_CARD,
    PERSONAL_DASHBOARD_EXPIRE_CARD,
    PERSONAL_DASHBOARD_ADD_EVIDENCE,
    PERSONAL_DASHBOARD_LIST_CARDS,
    PERSONAL_DASHBOARD_RECORD_REFRESH,
    PERSONAL_DASHBOARD_SUGGEST_CARD,
    PERSONAL_DASHBOARD_GET_TOPICS,
    PERSONAL_DASHBOARD_GET_PREFERENCES,
]
