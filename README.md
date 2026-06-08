# Hermes Personal Dashboard

Zero-setup personal dashboard for Hermes Agent.

Hermes already knows things from memory, sessions, cron runs, and prior agent
work. This plugin turns that existing context into a dashboard without asking
the user to pick interests, enter a location, add tickers, choose teams, or
build a setup profile.

Open the tab. It reflects what Hermes has already figured out.

## What It Shows

The dashboard groups useful Hermes-derived cards into:

| Section | What appears there |
| --- | --- |
| **Now** | urgent alerts, weather warnings, schedule conflicts, threshold breaches |
| **Today** | daily briefings, family/school/menu items, news summaries, reminders |
| **This Week** | weekend plans, upcoming games, events, deadlines, travel |
| **Watching** | stocks, teams, projects, GitHub issues, recurring beats |
| **Inferred Context** | what Hermes appears to know is relevant and why |
| **Hermes Activity** | refresh runs, failures, scan counts, stale sources |

Every card should show freshness and provenance when Hermes has it.

## The Important Difference

This is not a configuration flow.

The plugin does not start by asking:

- what news beats you want
- where you live
- which teams you follow
- which stocks to watch
- which calendar to use
- which schedule to run

Instead it scans existing Hermes state:

- `$HERMES_HOME/memories/MEMORY.md`
- `$HERMES_HOME/memories/USER.md`
- `$HERMES_HOME/state.db`
- `$HERMES_HOME/cron/jobs.json`
- recent `$HERMES_HOME/cron/output/**`
- cards written by Hermes jobs through this plugin

Then it creates inferred context items and dashboard cards.

## Install

One-command install:

```bash
curl -fsSL https://raw.githubusercontent.com/manimohans/hermes-personal-dashboard/main/install.sh | bash
```

Then open Hermes:

```bash
hermes dashboard
```

Open the **Personal Dashboard** tab. No configuration is required.

Manual install:

```bash
mkdir -p ~/.hermes/plugins
git clone https://github.com/manimohans/hermes-personal-dashboard.git \
  ~/.hermes/plugins/hermes-personal-dashboard
hermes plugins enable hermes-personal-dashboard
hermes dashboard
```

Or symlink this checkout while developing:

```bash
./install.sh
```

Check the install:

```bash
./scripts/doctor.sh
```

## Try It Before Installing Hermes

From the repo root:

```bash
python3 -m http.server 8765
```

Open:

```text
http://127.0.0.1:8765/docs/preview.html
```

The preview loads the real dashboard bundle with mocked Hermes memory/session
data so you can click through the zero-setup experience.

## First Run

On first load, the dashboard asks the backend for `/snapshot`. The backend can
auto-scan Hermes memory, session history, cron jobs, and cron output, then write
cards into the local SQLite store.

If Hermes has no memory or saved sessions yet, the dashboard still shows a
ready card and source coverage. It explains what it checked and then fills in
automatically as Hermes builds memory or runs jobs. It does not ask the user to
fill out a form.

Useful command:

```bash
/personal-dashboard status
```

Manual refresh, if you want to force a scan:

```bash
/personal-dashboard refresh
```

List what Hermes inferred:

```bash
/personal-dashboard context
```

Create recurring autonomous refresh jobs:

```bash
/personal-dashboard create-jobs
```

## How It Works

```text
Hermes memory + sessions + cron output
        |
        v
context scanner
        |
        v
inferred context items
        |
        v
dashboard cards
        |
        v
Hermes cron jobs keep live cards fresh
```

The scanner is deterministic and dependency-light. It uses Python stdlib and
SQLite so normal users do not need Node or npm.

Cron jobs use the plugin-provided `briefing-curator` skill. The skill tells
Hermes to:

- refresh from existing Hermes context first
- read inferred context items
- fetch live data only when the inferred context points to it
- write structured cards
- attach evidence
- record refresh results

## User Controls

The dashboard includes correction controls, not setup controls:

- **Refresh**: reload the snapshot
- **Scan Hermes now**: force a memory/session/cron scan
- **Create refresh jobs**: install autonomous recurring jobs
- **Pin / Unpin**: keep a card visible
- **Dismiss**: hide a card
- **Hide** on inferred context: stop showing that inferred item
- **Source Coverage**: see which Hermes memory/session/cron sources were read

## Plugin Tools

Hermes jobs can use these model-visible tools:

| Tool | Purpose |
| --- | --- |
| `personal_dashboard_refresh_from_hermes` | scan Hermes memory/session/cron state and update inferred cards |
| `personal_dashboard_list_context` | read inferred context items |
| `personal_dashboard_upsert_context` | add or improve inferred context from agent reasoning |
| `personal_dashboard_hide_context` | hide an inferred context item |
| `personal_dashboard_upsert_card` | create or update a visible card |
| `personal_dashboard_patch_card` | update selected card fields |
| `personal_dashboard_expire_card` | expire a card |
| `personal_dashboard_add_evidence` | attach provenance to a card |
| `personal_dashboard_list_cards` | list cards |
| `personal_dashboard_record_refresh` | record refresh status |
| `personal_dashboard_get_snapshot` | read cards, context, refreshes, and status |
| `personal_dashboard_get_preferences` | read internal timestamps and cron ids |
| `personal_dashboard_create_cron_jobs` | create autonomous refresh jobs |

## Dashboard API

Routes are mounted under:

```text
/api/plugins/hermes-personal-dashboard/
```

Important routes:

| Route | Purpose |
| --- | --- |
| `GET /snapshot` | autonomous dashboard snapshot, auto-refreshes by default |
| `POST /context/refresh` | force a Hermes memory/session/cron scan |
| `GET /context` | list inferred context |
| `POST /context` | add or update inferred context |
| `POST /context/{id}/hide` | hide inferred context |
| `GET /cards` | list cards |
| `POST /cards` | upsert a card |
| `PATCH /cards/{id}` | patch a card |
| `POST /cards/{id}/pin` | pin a card |
| `POST /cards/{id}/unpin` | unpin a card |
| `POST /cards/{id}/dismiss` | dismiss a card |
| `GET /refresh-runs` | list refresh history |
| `POST /refresh-runs` | record refresh history |
| `POST /automation/ensure-jobs` | create autonomous refresh jobs |

## Storage

State lives in:

```text
$HERMES_HOME/plugins/hermes-personal-dashboard/cards.db
```

Main tables:

- `cards`
- `context_items`
- `evidence`
- `refresh_runs`
- `preferences`

## Validate

```bash
./scripts/doctor.sh
python3 -m unittest discover -s tests -v
node --check dashboard/dist/index.js
```

FastAPI route tests run when the Hermes dashboard/FastAPI test client is
available. In a minimal Python environment they are skipped.

## Project Layout

```text
.
|-- __init__.py
|-- personal_dashboard_core.py
|-- schemas.py
|-- plugin.yaml
|-- install.sh
|-- dashboard/
|   |-- manifest.json
|   |-- plugin_api.py
|   `-- dist/
|-- docs/
|   `-- preview.html
|-- skills/
|   `-- briefing-curator/
|-- scripts/
|   |-- doctor.sh
|   `-- install-local.sh
`-- tests/
```

## Design Principles

- No required setup.
- No personal hardcoded defaults.
- Use Hermes memory/session/cron state as the starting point.
- Show why each card exists.
- Let users correct the dashboard by hiding or dismissing items.
- Keep the plugin lightweight and easy to install.
- Do not replace Hermes memory; reflect it.
