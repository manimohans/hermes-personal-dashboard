# Hermes Personal Dashboard

Zero-setup standalone personal dashboard for Hermes Agent.

Hermes already knows things from memory, sessions, cron runs, and prior agent
work. This app gives Hermes a dashboard surface without asking
the user to pick interests, enter a location, add tickers, choose teams, or
build a setup profile.

Open the web app. Hermes scans existing context into relevance signals, then
Hermes jobs write and update the useful cards.

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

Cards should show the actual user-facing data, not the fact that a source or
cron job exists. Examples:

- AI news cards should show AI news items.
- Calendar cards should show events or important schedule context.
- Email cards should show important messages or counts worth acting on.
- Weather cards should show current conditions and relevant forecast.
- Sensor cards should show the actual reading.
- Sports cards should show fixtures, scores, standings, or news.

Source health, authentication status, prompt rules, and cron details belong in
card details or the collapsed **Details** rail, not as primary cards.

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

Then it creates inferred context items. Visible cards are written separately by
Hermes jobs through the dashboard tools, so raw prompts, schedules, logs, and
memory-write JSON do not become dashboard content.

## Install And Run

One command does the install, web UI build checks, server start, and URL print.
It installs the standalone web app, installs the Hermes tool/skill bundle, starts
its own web server, and gives the terminal back.

```bash
curl -fsSL https://raw.githubusercontent.com/manimohans/hermes-personal-dashboard/main/run.sh | bash
```

On a Raspberry Pi, home server, or any machine you want to reach from another
device on your LAN:

```bash
curl -fsSL https://raw.githubusercontent.com/manimohans/hermes-personal-dashboard/main/run.sh | bash -s -- --lan
```

`--lan` is shorthand for:

```bash
--host 0.0.0.0 --insecure --no-open
```

When the script finishes, follow the printed steps exactly:

1. Open the exact dashboard URL printed by the script. Do not guess the port.
2. If cards are already shown, you are done.
3. If the page says signals were found but cards are not curated yet, click
   **Install auto updates**.
4. If that button says Hermes cron is unavailable, open Hermes chat and run:

```bash
/personal-dashboard create-jobs
```

5. To force cards immediately, ask Hermes:

```text
Use hermes-personal-dashboard:briefing-curator. Refresh the Personal Dashboard now from existing Hermes memory, sessions, cron output, and prior work. Write useful cards and record the refresh result.
```

On a LAN install, the printed URL will usually look like:

```text
http://<machine-ip>:9120
```

No Hermes Dashboard tab is required.

The launcher follows the useful Hermes dashboard conventions:

| Flag | Purpose |
| --- | --- |
| `--host` | bind address, default `127.0.0.1` |
| `--port` | preferred port, default `9120` |
| `--insecure` | required for non-localhost binding |
| `--no-open` | do not launch a browser |
| `--no-plugin` | skip Hermes tool/skill bundle install |
| `--skip-build` | skip local syntax/build checks |
| `--strict-port` | fail if the requested port is busy |

If the preferred port is busy, `run.sh` leaves that process alone, chooses the
next free port, and prints the actual URL. This keeps a Hermes dashboard already
running on that port from being stopped or overwritten.

Manual install:

```bash
mkdir -p ~/.hermes/products
git clone https://github.com/manimohans/hermes-personal-dashboard.git \
  ~/.hermes/products/hermes-personal-dashboard
~/.hermes/products/hermes-personal-dashboard/run.sh --lan
```

Or symlink this checkout while developing:

```bash
./run.sh
```

Clean reinstall:

```bash
./run.sh --remove-existing --yes
```

Uninstall:

```bash
./run.sh --uninstall --yes
```

Run manually:

```bash
hermes-personal-dashboard --host 0.0.0.0 --port 9120
```

Check the install:

```bash
./scripts/doctor.sh
```

The same repo is installed as a Hermes plugin by default so Hermes jobs can use
the model-visible dashboard tools. To skip that, use:

```bash
./run.sh --no-plugin
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

On first load, the standalone app asks the backend for `/snapshot`. The backend can
auto-scan Hermes memory, session history, cron jobs, and cron output, then store
inferred relevance signals.

If Hermes has no curated cards yet, the dashboard shows the signal state and
source coverage in the side rail instead of pretending logs are useful cards.
It fills in when Hermes cron jobs or chats call `personal_dashboard_upsert_card`.

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

Install auto updates, when running with Hermes plugin support:

```bash
/personal-dashboard create-jobs
```

That command installs three scheduled Hermes curator jobs using starter defaults.
Those defaults are not personal assumptions and are not required. Any user can
set a different cadence in the same command, without a setup wizard:

```bash
/personal-dashboard create-jobs daily=09:00 frequent=30m planning=mon@16:00 force
```

It does not execute those jobs at install time.

| Job | When it runs | What it does |
| --- | --- | --- |
| Personal Dashboard Daily Briefing | default: daily at `07:30` local time; override with `daily=HH:MM` | turns daily-relevant Hermes context into briefing cards |
| Personal Dashboard Frequent Signal Refresh | default: hourly; override with `frequent=15m`, `frequent=30m`, `frequent=hourly`, or `frequent=daily` | refreshes time-sensitive cards such as weather, stocks, sports, news, calendar, family, projects, and alerts |
| Personal Dashboard Planning Refresh | default: Friday at `15:00` local time; override with `planning=day@HH:MM` | prepares planning cards from Hermes context |

After installing jobs, the command also performs an immediate deterministic
scan of Hermes sources so the dashboard can show inferred signals right away.
Cards still appear when a Hermes curator job or chat writes them with
`personal_dashboard_upsert_card`.

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
Hermes curator jobs
        |
        v
dashboard cards ranked by priority, freshness, and time relevance
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
- mark visible cards with `payload.ai_curated: true`
- attach evidence
- record refresh results

## User Controls

The standalone dashboard includes correction controls, not setup controls:

- **Refresh**: reload the snapshot
- **Scan Hermes signals**: read Hermes memory, sessions, and cron output once; this finds relevance signals but does not itself create final cards
- **Install auto updates**: ask Hermes to create scheduled curator jobs for daily briefing, frequent signal refresh, and planning; if the standalone server cannot reach Hermes cron, the dashboard shows the exact failure and the next command to run inside Hermes
- **Pin / Unpin**: keep a card visible
- **Dismiss**: hide a card
- **Hide** on inferred context: stop showing that inferred item
- **Source Coverage**: see which Hermes memory/session/cron sources were read

During first load, manual scans, snapshot refreshes, and running cron jobs, the
top of the dashboard shows a **Working** strip with an animated scan meter. That
strip is the visual signal that Hermes context is being read or curated cards
are being updated.

## Plugin Tools

Hermes jobs can use these model-visible tools:

| Tool | Purpose |
| --- | --- |
| `personal_dashboard_refresh_from_hermes` | scan Hermes memory/session/cron state into relevance signals |
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
| `personal_dashboard_create_cron_jobs` | install auto updates by creating Hermes curator cron jobs |

## Standalone API

The standalone app serves the same API shape under:

```text
/api/plugins/hermes-personal-dashboard/
```

Important routes:

| Route | Purpose |
| --- | --- |
| `GET /snapshot` | autonomous dashboard snapshot, auto-refreshes by default |
| `POST /context/refresh` | force a Hermes memory/session/cron signal scan |
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
| `POST /automation/ensure-jobs` | install auto updates by creating autonomous Hermes curator jobs |

The standalone server can only install auto updates when it is running in an
environment where Hermes exposes its cron module. If the dashboard says
`cron integration unavailable`, do not wait for jobs that were not created.
Open Hermes and run:

```text
/personal-dashboard create-jobs
```

Cards appear after a Hermes curator job actually runs and writes them through
the dashboard tools.

## Storage

The standalone web app and Hermes plugin share one dashboard database by
default:

```text
$HERMES_HOME/plugins/hermes-personal-dashboard/cards.db
```

This is important: cards written by Hermes jobs and cards read by the standalone
web UI must come from the same file.

Older standalone-only installs may have used:

```text
$HERMES_HOME/personal-dashboard/cards.db
```

On startup, the standalone server migrates that old database into the shared
plugin location only when the shared database does not already exist. It will
not overwrite cards Hermes has already written.

To force a custom data location, set:

```text
HERMES_PERSONAL_DASHBOARD_DATA=/path/to/dashboard-data
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
|-- run.sh
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
