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
- Reuse one stable card `id` per user-facing topic. A repeated refresh should
  update `weather-home-now`, `machine-temperature-now`, `calendar-today`,
  `news-ai-briefing`, or an equivalent stable ID instead of creating a new
  card with a timestamp, run name, or alternate wording.
- Never turn raw scanner lines, prompts, cron schedules, persona text, or
  memory-write JSON into visible cards.
- Do not create visible cards merely saying a source is authenticated, a token
  exists, a formatting rule is known, a path/cadence is configured, or a topic is
  on a watchlist without fresh data. Keep those facts as context, evidence, or
  `why_shown`, not as dashboard cards.
- A visible card must answer at least one user-facing question: what matters
  now, what is happening today, what is coming up, what changed, or what needs
  action.
- Adapt the wording, density, tone, and formatting to the user's Hermes memory,
  profile, and prior correction history. Do not create a card about those style
  preferences; apply them silently.
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

Avoid low-signal internal cards:

- "Gmail is authenticated" is not a card. "Two important unread emails need
  attention" can be a card.
- "Digest formatting rules are known" is not a card. Use that rule to format
  the card.
- "A sports team is on the watchlist" is not a card. A fixture, score, injury,
  standings move, or lack of verified live data can be mentioned only when it is
  part of a useful current card.
- "Project path/cadence/context exists" is not a card. A project deadline,
  failing build, active issue, shipped update, or strategic decision can be a
  card.

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

Prefer structured user-facing data in `payload` so the dashboard can render the
actual content without knowing the user's domain in advance:

- `payload.metrics`: object or list of `{label, value, unit}` readings.
- `payload.items`: list of `{title, summary, url, source, time}` items.
- `payload.sections`: list of `{label, items}` groups for multi-part cards.
- Feed cards are not complete unless they include the feed entries. For news,
  sports, school/daycare, jobs, projects, email, calendar, or finance feeds,
  store the visible entries in `payload.items`, `payload.sections`, or the
  matching domain alias. A summary-only card is acceptable only when the source
  truly has no item-level records.

Domain-specific aliases are also supported when useful, such as
`news_items`, `calendar_events`, `email_items`, `daycare_items`, `menu_items`,
`fixtures`, `scores`, `tickers`, `observed`, and `readings`.

The card title and summary should describe the data result, not the source job.
For example:

- Good: "Five AI stories worth reading this morning" with `payload.news_items`.
- Bad: "AI news feed is fresh."
- Good: "San Jose: 67F, low rain risk" with weather metrics.
- Bad: "Weather job ran successfully."
- Good: "Daycare: pasta lunch, nap note, art activity" with menu/daycare items.
- Bad: "Daycare poll is active."

When two old cards already describe the same live topic, update the newest or
most useful one and dismiss, expire, or stop refreshing the duplicate. Do not
keep separate cards for "San Jose weather now" and "San Jose weather today" if
they are both answering the same current-weather question.

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
    "relevance_score": 40,
    "items": [
      {
        "title": "Example story",
        "summary": "Why it matters to this user.",
        "url": "https://example.com/story",
        "source": "Example Source",
        "time": "2026-06-08T14:00:00Z"
      }
    ]
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
