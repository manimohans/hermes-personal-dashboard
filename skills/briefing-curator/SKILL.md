---
name: briefing-curator
description: Refresh Hermes Personal Dashboard cards from existing Hermes memory, sessions, cron output, and prior agent work with no user setup.
version: 0.2.0
author: Hermes Personal Dashboard contributors
license: MIT
metadata:
  hermes:
    tags: [Dashboard, Daily Briefing, Personal Agent, Cron, Memory, Sessions]
---

# Hermes Personal Dashboard Briefing Curator

Use this skill when a cron job or user request asks Hermes to refresh the
Personal Dashboard. The dashboard is zero-setup: do not ask the user to choose
interests, sources, tickers, teams, locations, or schedules before producing
cards.

## Operating Rules

- Start with `personal_dashboard_refresh_from_hermes` using `create_cards:
  false`. This scans existing Hermes memory, session history, cron jobs/output,
  and prior agent work into relevance signals.
- Read inferred context with `personal_dashboard_list_context`.
- Treat inferred context as the user's already-provided intent. Use it to decide
  which live data is worth fetching with available Hermes tools.
- Write useful visible cards with `personal_dashboard_upsert_card`.
- Never turn raw scanner lines, prompts, cron schedules, persona text, or
  memory-write JSON into visible cards.
- Use `personal_dashboard_upsert_context` when you discover a durable relevance
  signal from Hermes context that the deterministic scanner missed.
- Adjust existing cards with `personal_dashboard_patch_card` when only status,
  priority, pinning, freshness, or summary changed.
- Attach important provenance with `personal_dashboard_add_evidence`.
- Record the refresh result with `personal_dashboard_record_refresh`.
- Never require setup. User controls are for correction only: hide, dismiss,
  pin, unpin, or ask Hermes to ignore a domain.

## What Belongs On The Dashboard

Prefer high-signal cards that explain what matters now:

- `now`: urgent alerts, weather warnings, threshold breaches, schedule conflicts,
  time-sensitive reminders, breaking updates.
- `today`: daily briefings, family/school/menu updates, news summaries, calendar
  items, and other same-day context.
- `week`: plans, upcoming games, events, travel, deadlines, and other future
  context.
- `watching`: stocks, teams, projects, GitHub issues, recurring beats, interests
  Hermes has learned are relevant.

Every visible card should include:

- a stable `id` so future runs update the same card
- a concise `title`
- a one-to-three sentence `summary`
- `source_label` or evidence when available
- `why_shown` that points to the inferred Hermes context
- freshness through `updated_at` and optional `valid_until`
- `payload.ai_curated: true`
- optional `payload.relevance_score` from `0` to `150` when the card should
  rank higher or lower than priority/freshness alone

## Card Writing Pattern

```json
{
  "id": "news-ai-briefing",
  "domain": "news",
  "title": "AI news briefing",
  "summary": "Three high-signal AI updates are worth showing today.",
  "priority": "medium",
  "status": "active",
  "valid_until": "2026-06-08T15:00:00Z",
  "source_label": "Hermes memory + web search",
  "why_shown": "Auto-discovered from Hermes memory/session history.",
  "payload": {
    "section": "today",
    "ai_curated": true,
    "relevance_score": 40
  }
}
```

## Refresh Pattern

At the start:

```json
{
  "job_key": "autonomous-daily-briefing",
  "status": "running",
  "summary": "Refreshing dashboard from Hermes context."
}
```

At the end:

```json
{
  "job_key": "autonomous-daily-briefing",
  "status": "success",
  "summary": "Updated dashboard cards from inferred Hermes context."
}
```

On failure, record the failed source instead of silently skipping it:

```json
{
  "job_key": "autonomous-alert-refresh",
  "status": "error",
  "summary": "Dashboard alert refresh failed.",
  "error": "Market data provider unavailable."
}
```

## Domain Guidance

- **News:** Infer beats from Hermes memory/session history. Use recent original
  publication times. Do not produce generic world-news filler.
- **Weather:** Use the location Hermes already knows, if present in memory,
  sessions, user profile, or recent jobs. Otherwise only show weather context
  if Hermes has a usable location.
- **Stocks:** Use tickers, portfolio interests, or threshold preferences Hermes
  already knows. Prioritize unusual movement and configured alerts over routine
  prices.
- **Sports:** Use teams, leagues, and competitions inferred from Hermes context.
  Surface next fixtures, recent results, injuries, and high-signal news.
- **Family/School:** Surface menus, schedules, daycare/school summaries, and
  reminders only when Hermes already has that context.
- **Calendar/Planning:** Use available calendar tools only when the user's Hermes
  installation already grants access. Avoid unnecessary sensitive detail.
- **Projects:** Use repositories, issues, tasks, and recurring project work
  inferred from sessions or memory.

## Suggested Job Prompts

Daily briefing:

```text
Use hermes-personal-dashboard:briefing-curator. Refresh the Personal Dashboard
from existing Hermes memory, sessions, cron output, and prior agent work. Do not
ask the user to configure interests. Update cards and record the refresh result.
Do not show raw scanner output as cards.
```

Frequent signal refresh:

```text
Use hermes-personal-dashboard:briefing-curator. Refresh time-sensitive dashboard
alerts from inferred Hermes context. Update existing cards where possible and
record the refresh result.
```

Planning refresh:

```text
Use hermes-personal-dashboard:briefing-curator. Refresh planning cards from
whatever Hermes already knows is relevant. Record the refresh result.
```
