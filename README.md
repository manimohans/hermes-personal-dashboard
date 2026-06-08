# Hermes Personal Dashboard

> Generic daily briefing dashboard for Hermes Agent.

Hermes Personal Dashboard gives Hermes a single place to show what it has
figured out that matters right now: briefings, alerts, plans, watched topics,
source-backed cards, and refresh health.

It is not a transcript viewer and it is not built around one person's usage.
Each user configures their own topics, location, tickers, teams, sources,
calendar preference, and briefing schedule. Hermes jobs fetch the live data;
this plugin stores and renders the structured dashboard cards.

## Start Here

Install the plugin into Hermes:

```bash
git clone https://github.com/manimohans/hermes-personal-dashboard.git \
  ~/.hermes/plugins/hermes-personal-dashboard

hermes plugins enable hermes-personal-dashboard
hermes dashboard
```

Open the Hermes dashboard and select **Personal Dashboard**.

From there:

1. Add your location, timezone, and briefing time.
2. Add topics such as AI news, local weather, stock tickers, sports teams,
   calendar items, projects, or RSS/news sources.
3. Save setup.
4. Click **Create jobs** to create the standard Hermes cron refresh jobs.
5. Let Hermes refresh the dashboard through the bundled curator skill.

For local development from a checkout:

```bash
cd hermes-personal-dashboard
./scripts/install-local.sh
hermes plugins enable hermes-personal-dashboard
hermes dashboard
```

## What It Does

Hermes Personal Dashboard turns recurring Hermes work into a durable dashboard.

| Surface | What it shows |
| --- | --- |
| **Now** | Urgent cards, weather alerts, high-priority updates, schedule-sensitive items. |
| **Today** | Daily briefing cards, calendar-style items, menus, reminders, top news. |
| **This Week** | Weekend plans, upcoming games, events, deadlines, longer-range context. |
| **Watching** | Topics, teams, stocks, sources, projects, and ongoing monitors. |
| **Hermes Activity** | Recent refreshes, failed jobs, stale sources, and pending suggestions. |
| **Setup** | Topics, preferences, discovery suggestions, and job creation. |

Cards include freshness and provenance when Hermes has it:

- when the card was updated
- where it came from
- why it is shown
- when it becomes stale
- optional source evidence

## How It Works

The plugin has three parts:

```text
Hermes cron jobs / chat sessions
        |
        v
personal_dashboard tools
        |
        v
SQLite card store
        |
        v
Hermes dashboard tab
```

Hermes fetches data with its existing tools and skills. This plugin is the
structured storage and display layer.

The bundled skill, `hermes-personal-dashboard:briefing-curator`, tells Hermes
how to:

- read configured topics and preferences
- fetch only user-configured domains
- write cards with stable IDs
- attach evidence
- record refresh runs
- create suggestions instead of silently exposing inferred topics

Memory and session discovery are suggestion-only. They never create visible
cards without user confirmation.

## Install

### Normal Install

```bash
git clone https://github.com/manimohans/hermes-personal-dashboard.git \
  ~/.hermes/plugins/hermes-personal-dashboard

hermes plugins enable hermes-personal-dashboard
hermes dashboard
```

### Local Checkout Install

Use this when you are editing the plugin locally:

```bash
./scripts/install-local.sh
hermes plugins enable hermes-personal-dashboard
hermes dashboard
```

The install script symlinks the current checkout into:

```text
~/.hermes/plugins/hermes-personal-dashboard
```

Normal users do not need Node, npm, or a build step. The dashboard JavaScript
and CSS are checked in under `dashboard/dist/`.

## First Setup

In the dashboard Setup panel, configure:

- briefing time
- timezone
- location
- alert frequency
- calendar preference
- weekend planner preference
- topics to watch

Topic examples:

| Domain | Example label | Example query |
| --- | --- | --- |
| `news` | AI news | latest major AI product, model, policy, and startup updates |
| `weather` | Home weather | forecast and severe weather for my configured location |
| `stocks` | Watchlist | AAPL, MSFT, NVDA |
| `sports` | Favorite team | next match, result, injuries, transfer news |
| `calendar` | Today | upcoming calendar events and important reminders |
| `planning` | Weekend plans | weather-aware weekend options |
| `project` | GitHub issues | important issues, PRs, and project blockers |

After saving setup, click **Create jobs**. The plugin creates standard Hermes
cron jobs:

| Job | Default schedule | Purpose |
| --- | --- | --- |
| Morning briefing | 7:30 AM local time | Refresh daily dashboard cards. |
| Alerts refresh | Hourly | Refresh time-sensitive cards. |
| Weekend planner | Friday 3:00 PM | Refresh weekend planning cards. |

The jobs use the bundled curator skill and write cards through this plugin's
tools.

## Tool Surface

The plugin registers the `personal_dashboard` toolset:

| Tool | Purpose |
| --- | --- |
| `personal_dashboard_upsert_card` | Create or update a dashboard card. |
| `personal_dashboard_expire_card` | Mark a card expired. |
| `personal_dashboard_add_evidence` | Attach source evidence to a card. |
| `personal_dashboard_list_cards` | List cards for inspection or refresh logic. |
| `personal_dashboard_record_refresh` | Record refresh success, failure, or running state. |
| `personal_dashboard_suggest_card` | Create a pending suggestion for user approval. |
| `personal_dashboard_get_topics` | Read configured topics. |
| `personal_dashboard_get_preferences` | Read dashboard setup preferences. |

Minimum card payload:

```json
{
  "id": "weather-today",
  "domain": "weather",
  "title": "Weather today",
  "summary": "Mild morning, warmer afternoon.",
  "priority": "medium"
}
```

Recommended fields:

```json
{
  "valid_until": "2026-06-08T15:00:00Z",
  "source_label": "Weather provider",
  "source_url": "https://example.com",
  "why_shown": "Configured location",
  "payload": {
    "section": "now"
  }
}
```

Valid `payload.section` values:

- `now`
- `today`
- `week`
- `watching`

Use stable card IDs so recurring jobs update existing cards instead of creating
duplicates.

## Dashboard API

Routes are mounted under:

```text
/api/plugins/hermes-personal-dashboard/
```

Useful routes:

| Route | Purpose |
| --- | --- |
| `GET /snapshot` | Full dashboard snapshot. |
| `GET /cards` | List cards. |
| `POST /cards` | Create or update a card. |
| `PATCH /cards/{id}` | Update card fields. |
| `POST /cards/{id}/dismiss` | Dismiss a card. |
| `GET /topics` | List configured topics. |
| `POST /topics` | Add or update a topic. |
| `GET /preferences` | Read setup preferences. |
| `PUT /preferences` | Update setup preferences. |
| `GET /refresh-runs` | Show refresh history. |
| `GET /suggestions` | List pending suggestions. |
| `POST /suggestions/{id}/accept` | Accept a suggestion. |
| `POST /setup/create-cron-jobs` | Create standard refresh jobs. |

## Repository Layout

```text
.
├── __init__.py
├── plugin.yaml
├── personal_dashboard_core.py
├── schemas.py
├── dashboard/
│   ├── manifest.json
│   ├── plugin_api.py
│   └── dist/
├── skills/
│   └── briefing-curator/
├── scripts/
│   └── install-local.sh
└── tests/
```

Important files:

- `__init__.py` registers tools, slash command, and the bundled skill.
- `personal_dashboard_core.py` owns SQLite storage and validation.
- `dashboard/plugin_api.py` exposes FastAPI routes for the dashboard.
- `dashboard/dist/index.js` is the prebuilt dashboard UI.
- `skills/briefing-curator/SKILL.md` is the job/agent operating guide.

## Development

Run checks from the repository root:

```bash
python3 -m py_compile __init__.py dashboard/plugin_api.py personal_dashboard_core.py schemas.py
python3 -m unittest discover -s tests -v
node --check dashboard/dist/index.js
```

If your local Python does not have FastAPI installed, the API route tests are
skipped. They should run inside a Hermes dashboard development environment
where FastAPI is available.

The dashboard UI is intentionally a plain IIFE using Hermes' dashboard plugin
SDK. Do not bundle React. Hermes provides React through
`window.__HERMES_PLUGIN_SDK__`.

## Privacy Defaults

Hermes Personal Dashboard stores local dashboard state only:

- cards
- topics
- evidence
- refresh runs
- preferences
- pending suggestions

The SQLite database lives at:

```text
$HERMES_HOME/plugins/hermes-personal-dashboard/cards.db
```

The plugin does not replace Hermes memory. It can read Hermes memory files to
create suggestions, but those suggestions stay pending until the user accepts
them.

## Notes For Future Work

- Add richer domain packs for common sources such as weather, RSS/news, stocks,
  sports, GitHub, and calendars.
- Add dashboard export/import for topic presets.
- Add a stronger stale-source health view.
- Add optional notification hooks for critical cards.
- Keep the product generic; never ship personal default topics.
