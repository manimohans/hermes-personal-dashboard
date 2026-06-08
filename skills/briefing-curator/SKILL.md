---
name: briefing-curator
description: Update Hermes Personal Dashboard cards from user-configured topics, preferences, and available Hermes tools.
version: 0.1.0
author: Hermes Personal Dashboard contributors
license: MIT
metadata:
  hermes:
    tags: [Dashboard, Daily Briefing, Personal Agent, Cron, Memory]
---

# Hermes Personal Dashboard Briefing Curator

Use this skill when a cron job or user request asks Hermes to refresh the
Personal Dashboard. The dashboard is generic: only use topics and preferences
the user configured or explicitly accepted.

## Operating Rules

- Read preferences with `personal_dashboard_get_preferences`.
- Read configured topics with `personal_dashboard_get_topics`.
- Fetch data with the best available Hermes tools and skills for each enabled
  topic. Do not invent provider access that is not configured.
- Write results with `personal_dashboard_upsert_card`.
- Attach important source evidence with `personal_dashboard_add_evidence`.
- Record the refresh outcome with `personal_dashboard_record_refresh`.
- Create suggestions with `personal_dashboard_suggest_card` when a possible
  topic or card is inferred but not confirmed by the user.
- Do not create visible cards from memory or session inference alone.

## Card Writing Pattern

Use stable ids so repeated runs update cards instead of duplicating them:

```json
{
  "id": "news-ai-top-items",
  "domain": "news",
  "title": "AI news update",
  "summary": "Three notable updates since the last refresh.",
  "priority": "medium",
  "status": "active",
  "valid_until": "2026-06-08T15:00:00Z",
  "source_label": "Configured news sources",
  "why_shown": "Configured topic: AI news",
  "payload": {
    "section": "today"
  }
}
```

Recommended dashboard sections in `payload.section`:

- `now`: urgent alerts, weather warnings, high-priority schedule items.
- `today`: daily briefing, calendar, menus, top news.
- `week`: weekend plans, upcoming games, events, deadlines.
- `watching`: tracked topics, teams, stocks, projects, long-running watches.

## Refresh Pattern

At the start of a job:

```json
{
  "job_key": "morning-briefing",
  "status": "running",
  "summary": "Refreshing configured dashboard topics."
}
```

At the end of a successful job:

```json
{
  "job_key": "morning-briefing",
  "status": "success",
  "summary": "Updated weather, news, calendar, and watched topics."
}
```

On failure, record the failed source instead of silently skipping it:

```json
{
  "job_key": "stock-alerts",
  "status": "error",
  "summary": "Stock alert refresh failed.",
  "error": "Market data provider unavailable."
}
```

## Domain Guidance

- **News:** Summarize only configured topics and sources. Prefer the most recent
  original publication times. Include source labels and URLs when possible.
- **Weather:** Use the configured location. Mark alerts as high or critical.
- **Stocks:** Use configured tickers. Prioritize threshold alerts and unusual
  movement over routine prices.
- **Sports:** Use configured teams, leagues, and competitions. Surface next
  fixtures, recent results, injuries, and high-signal news.
- **Calendar/Planning:** Use configured calendar access only. Avoid exposing
  sensitive details unless the user has opted into calendar cards.
- **Projects:** Use configured repositories, issue filters, or task systems.

## Suggested Job Prompts

Morning briefing:

```text
Use hermes-personal-dashboard:briefing-curator. Refresh the Personal Dashboard
for the user's configured morning briefing topics. Update cards and record the
refresh result.
```

Alerts:

```text
Use hermes-personal-dashboard:briefing-curator. Refresh time-sensitive dashboard
alerts for configured topics only. Update existing cards where possible and
record the refresh result.
```

Weekend planner:

```text
Use hermes-personal-dashboard:briefing-curator. Refresh weekend planning cards
from configured calendar, weather, events, sports, and interest topics. Record
the refresh result.
```
