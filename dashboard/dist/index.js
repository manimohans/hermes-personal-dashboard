(function () {
  "use strict";

  const SDK = window.__HERMES_PLUGIN_SDK__;
  if (!SDK || !SDK.React || !window.__HERMES_PLUGINS__) {
    return;
  }

  const React = SDK.React;
  const h = React.createElement;
  const API = "/api/plugins/hermes-personal-dashboard";

  function cx() {
    return Array.prototype.slice.call(arguments).filter(Boolean).join(" ");
  }

  async function request(path, options) {
    options = options || {};
    let res;
    try {
      res = await fetch(API + path, Object.assign({
        headers: { "Content-Type": "application/json" },
      }, options));
    } catch (err) {
      throw makeNetworkError(path, options, err);
    }
    const text = await res.text();
    let data = {};
    if (text) {
      try {
        data = JSON.parse(text);
      } catch (_err) {
        data = { detail: text };
      }
    }
    if (!res.ok) {
      throw makeApiError(path, options, res, data);
    }
    return data;
  }

  function requestMethod(options) {
    return String((options && options.method) || "GET").toUpperCase();
  }

  function apiUrl(path) {
    return window.location.origin + API + path;
  }

  function responseDetail(data) {
    if (!data) return "No response body returned.";
    if (data.detail) return String(data.detail);
    if (data.error) return String(data.error);
    try {
      return JSON.stringify(data);
    } catch (_err) {
      return "Response body could not be displayed.";
    }
  }

  function errorHint(status) {
    if (status === 401 || status === 403) {
      return "Hint: this is an authorization failure. If you opened this inside Hermes Dashboard, sign in again or use the standalone dashboard URL. If this standalone app is behind a proxy, make sure the proxy is not protecting /api/plugins/hermes-personal-dashboard/.";
    }
    if (status === 404) {
      return "Hint: the dashboard API route was not found. Make sure you are running the latest standalone server, not an older Hermes Dashboard plugin route.";
    }
    if (status >= 500) {
      return "Hint: the server failed while reading Hermes data. Check ~/.hermes/run/hermes-personal-dashboard.log or the terminal running standalone/server.py.";
    }
    return "Hint: retry the request, then check the standalone server log if it keeps failing.";
  }

  function makeApiError(path, options, res, data) {
    return new Error([
      "Dashboard request failed.",
      requestMethod(options) + " " + apiUrl(path),
      "HTTP " + res.status + (res.statusText ? " " + res.statusText : ""),
      "Response: " + responseDetail(data),
      errorHint(res.status)
    ].join("\n"));
  }

  function makeNetworkError(path, options, err) {
    return new Error([
      "Dashboard API is unreachable.",
      requestMethod(options) + " " + apiUrl(path),
      "Browser error: " + ((err && err.message) || String(err)),
      "Hint: make sure the standalone server is running and that you opened the dashboard on the same host and port printed by run.sh."
    ].join("\n"));
  }

  function freshness(value) {
    if (!value) return "";
    const ts = Date.parse(value);
    if (!Number.isFinite(ts)) return value;
    const seconds = Math.max(0, Math.floor((Date.now() - ts) / 1000));
    if (seconds < 60) return "just now";
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return minutes + "m ago";
    const hours = Math.floor(minutes / 60);
    if (hours < 48) return hours + "h ago";
    return Math.floor(hours / 24) + "d ago";
  }

  function fallbackSunTime(hour, minute) {
    const date = new Date();
    date.setHours(hour, minute, 0, 0);
    return date;
  }

  function parseSunTime(value) {
    if (!value) return null;
    if (Array.isArray(value)) {
      for (let i = 0; i < value.length; i += 1) {
        const parsed = parseSunTime(value[i]);
        if (parsed) return parsed;
      }
      return null;
    }
    if (typeof value === "object") return null;
    if (typeof value === "number" && Number.isFinite(value)) {
      if (value > 1000000000000) return new Date(value);
      if (value > 1000000000) return new Date(value * 1000);
      return null;
    }
    const text = String(value).trim();
    if (/^\d{10,13}$/.test(text)) {
      const numeric = Number(text);
      return numeric > 1000000000000 ? new Date(numeric) : new Date(numeric * 1000);
    }
    const clock = text.match(/^(\d{1,2}):(\d{2})(?::\d{2})?\s*(am|pm)?$/i);
    if (clock) {
      let hour = Number(clock[1]);
      const minute = Number(clock[2]);
      const suffix = (clock[3] || "").toLowerCase();
      if (suffix === "pm" && hour < 12) hour += 12;
      if (suffix === "am" && hour === 12) hour = 0;
      return fallbackSunTime(hour, minute);
    }
    const timestamp = Date.parse(text);
    return Number.isFinite(timestamp) ? new Date(timestamp) : null;
  }

  function collectSunTimes(value, names, found, depth) {
    if (!value || depth > 5) return;
    if (Array.isArray(value)) {
      value.forEach(function (item) { collectSunTimes(item, names, found, depth + 1); });
      return;
    }
    if (typeof value !== "object") return;
    Object.keys(value).forEach(function (key) {
      const normalized = key.toLowerCase().replace(/[_-]+/g, "");
      const isMatch = names.some(function (name) { return normalized.indexOf(name) >= 0; });
      if (isMatch) {
        const parsed = parseSunTime(value[key]);
        if (parsed) found.push(parsed);
      }
      collectSunTimes(value[key], names, found, depth + 1);
    });
  }

  function sunTimeFromSnapshot(snapshot, names) {
    const found = [];
    ((snapshot && snapshot.cards) || []).forEach(function (card) {
      collectSunTimes(card.payload || {}, names, found, 0);
    });
    if (!found.length) return null;
    const today = new Date();
    const sameDay = found.filter(function (date) {
      return date.getFullYear() === today.getFullYear() &&
        date.getMonth() === today.getMonth() &&
        date.getDate() === today.getDate();
    });
    if (sameDay[0]) return sameDay[0];
    const first = found[0];
    if (!first) return null;
    today.setHours(first.getHours(), first.getMinutes(), 0, 0);
    return today;
  }

  function themeClass(snapshot) {
    const params = new URLSearchParams(window.location.search || "");
    const override = String(params.get("theme") || "").toLowerCase();
    if (override === "dark" || override === "night") return "hpd-theme-night";
    if (override === "light" || override === "day") return "hpd-theme-day";
    const now = new Date();
    const sunrise = sunTimeFromSnapshot(snapshot, ["sunrise", "sunup"]) || fallbackSunTime(6, 30);
    const sunset = sunTimeFromSnapshot(snapshot, ["sunset", "sundown"]) || fallbackSunTime(18, 30);
    return now < sunrise || now >= sunset ? "hpd-theme-night" : "hpd-theme-day";
  }

  function priorityClass(priority) {
    if (priority === "critical") return "hpd-priority-critical";
    if (priority === "high") return "hpd-priority-high";
    if (priority === "low") return "hpd-priority-low";
    return "hpd-priority-medium";
  }

  function sectionAlias(value) {
    const key = String(value || "").trim().toLowerCase().replace(/[\s-]+/g, "_");
    const aliases = {
      now: "now",
      urgent: "now",
      alerts: "now",
      alert: "now",
      weather: "now",
      calendar: "now",
      today: "today",
      daily: "today",
      news: "today",
      family: "today",
      daycare: "today",
      this_week: "week",
      week: "week",
      weekly: "week",
      planning: "week",
      sports: "week",
      events: "week",
      event: "week",
      watching: "watching",
      watchlist: "watching",
      radar: "watching",
      on_radar: "watching",
      projects: "watching",
      project: "watching",
      stocks: "watching",
      stock: "watching",
      finance: "watching"
    };
    return aliases[key] || "";
  }

  function sectionFor(card) {
    const payload = card.payload || {};
    const explicit = sectionAlias(payload.section);
    if (explicit) return explicit;
    const domainSection = sectionAlias(card.domain);
    if (domainSection) return domainSection;
    if (card.priority === "critical") return "now";
    if (card.priority === "high") return "today";
    return "watching";
  }

  function isScannerCard(card) {
    const payload = card.payload || {};
    if (payload.ai_curated || payload.user_curated || payload.keep_visible) return false;
    if (payload.scanner_generated || payload.system_card) return true;
    const id = String(card.id || "");
    const summary = String(card.summary || "").toLowerCase();
    if (id === "system-hermes-context-map") return true;
    if (payload.context_item_id && id.indexOf("auto-context-") === 0) return true;
    if (card.source_label === "Hermes context scanner") return true;
    return summary.indexOf("hermes has this in its ") === 0;
  }

  function hasArrayData(value) {
    return Array.isArray(value) && value.length > 0;
  }

  function hasObjectData(value) {
    return value && typeof value === "object" && !Array.isArray(value) && Object.keys(value).length > 0;
  }

  function hasSectionData(sections) {
    return Array.isArray(sections) && sections.some(function (section) {
      return section && typeof section === "object" && (
        hasArrayData(section.items) || hasArrayData(section.rows) || hasArrayData(section.entries)
      );
    });
  }

  function hasListObjectData(lists) {
    return hasObjectData(lists) && Object.keys(lists).some(function (key) {
      return hasArrayData(lists[key]);
    });
  }

  function hasDisplayablePayloadData(card) {
    const payload = card.payload || {};
    return hasArrayData(payload.metrics) ||
      hasObjectData(payload.metrics) ||
      hasArrayData(payload.readings) ||
      hasObjectData(payload.observed) ||
      hasObjectData(payload.current) ||
      hasSectionData(payload.sections) ||
      hasListObjectData(payload.lists) ||
      hasArrayData(payload.items) ||
      hasArrayData(payload.news_items) ||
      hasArrayData(payload.headlines) ||
      hasArrayData(payload.stories) ||
      hasArrayData(payload.calendar_events) ||
      hasArrayData(payload.events) ||
      hasArrayData(payload.email_items) ||
      hasArrayData(payload.emails) ||
      hasArrayData(payload.daycare_items) ||
      hasArrayData(payload.menu_items) ||
      hasArrayData(payload.school_items) ||
      hasArrayData(payload.fixtures) ||
      hasArrayData(payload.games) ||
      hasArrayData(payload.scores) ||
      hasArrayData(payload.tickers) ||
      hasArrayData(payload.positions) ||
      hasArrayData(payload.alerts) ||
      payload.thermal_zone0_c !== undefined ||
      payload.current_temp_c !== undefined ||
      payload.current_temp_f !== undefined ||
      payload.temperature_c !== undefined ||
      payload.temperature_f !== undefined ||
      payload.rain_probability_max_today !== undefined ||
      payload.uv_index_max_today !== undefined;
  }

  function normalizeKey(value) {
    return String(value || "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "");
  }

  function hasTemperatureSignal(card) {
    const payload = card.payload || {};
    const text = [
      card.title || "",
      card.summary || "",
      card.domain || ""
    ].join(" ").toLowerCase();
    return text.indexOf("thermal") >= 0 ||
      text.indexOf("machine temperature") >= 0 ||
      payload.thermal_zone0_c !== undefined ||
      payload.temperature_c !== undefined ||
      payload.current_temp_c !== undefined ||
      hasArrayData(payload.readings);
  }

  function topicClusterKey(card) {
    const payload = card.payload || {};
    const domain = String(card.domain || "").toLowerCase();
    const title = String(card.title || "").toLowerCase();
    if (domain === "weather") {
      const title = String(card.title || "");
      const match = title.match(/^(.+?)\s+(?:weather|now|conditions)\b/i) || title.match(/^(.+?):/);
      const location = normalizeKey(match && match[1]) || normalizeKey(payload.location);
      return "weather:" + (location || "current");
    }
    if ((domain === "alerts" || domain === "sensors" || domain === "sensor") && hasTemperatureSignal(card)) {
      return "sensor:machine-temperature";
    }
    if (domain === "calendar") {
      return "calendar:current";
    }
    if (domain === "stocks" || domain === "stock" || domain === "finance") {
      return "finance:watch";
    }
    if (domain === "news") {
      if (title.indexOf("ai") >= 0 || title.indexOf("siri") >= 0 || title.indexOf("openai") >= 0) return "news:ai";
      if (title.indexOf("data center") >= 0 || title.indexOf("infra") >= 0 || title.indexOf("chip") >= 0) return "news:infra";
      return "news:" + normalizeKey(title).split("-").slice(0, 3).join("-");
    }
    if (domain === "family" || domain === "daycare") {
      if (title.indexOf("daycare") >= 0 || title.indexOf("kanaa") >= 0 || title.indexOf("menu") >= 0) return "family:daycare";
      return "family:" + normalizeKey(title).split("-").slice(0, 3).join("-");
    }
    if (domain === "sports") {
      if (title.indexOf("united") >= 0 || title.indexOf("man utd") >= 0 || title.indexOf("manchester") >= 0) return "sports:man-united";
      if (title.indexOf("ipl") >= 0 || title.indexOf("cricket") >= 0) return "sports:cricket";
      return "sports:" + normalizeKey(title).split("-").slice(0, 3).join("-");
    }
    if (domain === "planning" || domain === "projects" || domain === "project") {
      if (title.indexOf("startup") >= 0 || title.indexOf("roles") >= 0 || title.indexOf("jobs") >= 0) return "projects:startup-jobs";
      return "projects:" + normalizeKey(title).split("-").slice(0, 3).join("-");
    }
    return "";
  }

  function cardUpdatedMs(card) {
    const value = Date.parse(card.updated_at || card.last_seen_at || "");
    return Number.isFinite(value) ? value : 0;
  }

  function cardScore(card) {
    let value = Number(card.relevance_score);
    if (!Number.isFinite(value)) value = Number((card.payload || {}).relevance_score || 0);
    return Number.isFinite(value) ? value : 0;
  }

  function betterCard(candidate, existing) {
    const candidatePinned = Boolean(candidate.pinned) || candidate.status === "pinned";
    const existingPinned = Boolean(existing.pinned) || existing.status === "pinned";
    if (candidatePinned !== existingPinned) return candidatePinned;
    const candidateActive = candidate.status !== "stale" && candidate.status !== "expired" && candidate.status !== "dismissed";
    const existingActive = existing.status !== "stale" && existing.status !== "expired" && existing.status !== "dismissed";
    if (candidateActive !== existingActive) return candidateActive;
    const candidateHasData = hasDisplayablePayloadData(candidate);
    const existingHasData = hasDisplayablePayloadData(existing);
    if (candidateHasData !== existingHasData) return candidateHasData;
    const candidateTime = cardUpdatedMs(candidate);
    const existingTime = cardUpdatedMs(existing);
    if (Math.abs(candidateTime - existingTime) > 2 * 60 * 1000) return candidateTime > existingTime;
    return cardScore(candidate) > cardScore(existing);
  }

  function dedupeTopicCards(cards) {
    const chosen = {};
    cards.forEach(function (card) {
      const key = topicClusterKey(card);
      if (!key) return;
      if (!chosen[key] || betterCard(card, chosen[key])) chosen[key] = card;
    });
    return cards.filter(function (card) {
      const key = topicClusterKey(card);
      return !key || chosen[key] === card;
    });
  }

  function isInternalContextCard(card) {
    const payload = card.payload || {};
    if (payload.keep_visible) return false;
    if (payload.internal_card || payload.operational_metadata) return true;
    const primaryText = [
      card.title || "",
      card.summary || "",
      card.source_label || ""
    ].join(" ").toLowerCase();
    const detailText = String(card.detail_md || "").toLowerCase();
    const internalPatterns = [
      " is authenticated",
      "access is available",
      "formatting rules",
      "formatting preference",
      "preferred delivery style",
      "backend context",
      "project path:",
      "preference/watchlist card",
      "no configured live",
      "no verified live",
      "should stay on the dashboard watchlist",
      "watched alerts quiet",
      "watchdog paused",
      "cron jobs are disabled",
      "quality monitoring",
      "current cron environment"
    ];
    for (let i = 0; i < internalPatterns.length; i += 1) {
      if (primaryText.indexOf(internalPatterns[i]) >= 0) return true;
    }
    const operationalOnlyPatterns = [
      "blocked by invisible unicode",
      "prompt contains invisible unicode",
      "job last errored",
      "failed refresh",
      "refresh failed",
      "hermes cron/jobs",
      "curator job",
      "scheduled job",
      "no new update surfaced",
      "watchdog",
      "briefing blocked",
      "briefing is blocked",
      "cron injection",
      "invisible unicode",
      "u+200c"
    ];
    if (!hasDisplayablePayloadData(card) || payload.error) {
      for (let j = 0; j < operationalOnlyPatterns.length; j += 1) {
        if (primaryText.indexOf(operationalOnlyPatterns[j]) >= 0) return true;
      }
    }
    if (detailText.indexOf("token path:") >= 0 || detailText.indexOf("oauth client path:") >= 0) return true;
    return false;
  }

  function visibleCards(cards) {
    const filtered = (cards || []).filter(function (card) {
      return !isScannerCard(card) && !isInternalContextCard(card);
    });
    return dedupeTopicCards(filtered);
  }

  function cronJobCount(preferences) {
    const jobs = (preferences && preferences.cron_jobs) || {};
    return Object.keys(jobs).filter(function (key) { return jobs[key]; }).length;
  }

  function plural(value, singular, pluralText) {
    return value === 1 ? singular : pluralText;
  }

  function autoUpdateState(snapshot) {
    const preferences = (snapshot && snapshot.preferences) || {};
    const count = cronJobCount(preferences);
    if (count > 0) {
      return {
        tone: "installed",
        badge: "Installed",
        button: "Auto updates installed",
        check: "Auto updates installed",
        disabled: true,
        title: "Auto updates installed",
        detail: count + " scheduled Hermes curator " + plural(count, "job is", "jobs are") + " recorded. They run inside Hermes and update cards when due."
      };
    }
    if (preferences.cron_unavailable) {
      return {
        tone: "blocked",
        badge: "Needs Hermes",
        button: "Retry install check",
        check: "Auto updates need Hermes",
        disabled: false,
        title: "Auto updates need Hermes",
        detail: "The standalone page can scan signals, but scheduled curator jobs must be created where Hermes cron is available."
      };
    }
    return {
      tone: "ready",
      badge: "Not installed",
      button: "Install auto updates",
      check: "Auto updates not installed",
      disabled: false,
      title: "Install auto updates",
      detail: "One-time action: creates daily, frequent-signal, and planning curator jobs in Hermes. To use a different cadence, run /personal-dashboard create-jobs daily=09:00 frequent=30m planning=mon@16:00 force in Hermes."
    };
  }

  function formatJobLines(jobs) {
    if (!jobs || !jobs.length) return "";
    return jobs.map(function (job) {
      const name = job.name || job.kind || "Dashboard job";
      const cadence = job.cadence || job.schedule || "scheduled";
      const purpose = job.purpose || "refresh dashboard cards";
      return "- " + name + ": " + cadence + "; " + purpose + ".";
    }).join("\n");
  }

  function Button(props) {
    return h("button", Object.assign({}, props, {
      className: cx("hpd-button", props.variant && "hpd-button-" + props.variant, props.className),
    }), props.children);
  }

  function Badge(props) {
    return h("span", { className: cx("hpd-badge", props.className) }, props.children);
  }

  function ErrorPanel(props) {
    const lines = String(props.message || "Unknown dashboard error.").split("\n");
    const title = lines.shift() || "Dashboard error";
    return h("div", { className: "hpd-error" },
      h("strong", { className: "hpd-error-title" }, title),
      h("pre", { className: "hpd-error-detail" }, lines.join("\n"))
    );
  }

  function NoticePanel(props) {
    const lines = String(props.message || "Dashboard notice.").split("\n");
    const title = lines.shift() || "Dashboard notice";
    return h("div", { className: "hpd-notice" },
      h("strong", { className: "hpd-notice-title" }, title),
      lines.length ? h("pre", { className: "hpd-notice-detail" }, lines.join("\n")) : null
    );
  }

  function runningRefresh(snapshot) {
    const runs = snapshot ? (snapshot.refresh_runs || []) : [];
    const resolvedJobs = {};
    for (let i = 0; i < runs.length; i += 1) {
      const jobKey = runs[i].job_key || "__unknown__";
      if (runs[i].status === "success" || runs[i].status === "error" || runs[i].status === "failed") {
        resolvedJobs[jobKey] = true;
        continue;
      }
      if (runs[i].status === "running") {
        if (resolvedJobs[jobKey]) continue;
        const started = Date.parse(runs[i].started_at || "");
        if (!Number.isFinite(started) || Date.now() - started < 20 * 60 * 1000) return runs[i];
      }
    }
    return null;
  }

  function SyncStatus(props) {
    const snapshot = props.snapshot;
    const running = runningRefresh(snapshot);
    let title = "";
    let detail = "";
    if (props.mutating) {
      title = "Updating dashboard";
      detail = "Refreshing Hermes signals, curated cards, freshness, and source coverage.";
    } else if (props.loading && !snapshot) {
      title = "Reading Hermes signals";
      detail = "Scanning memory, sessions, cron output, and existing curated cards.";
    } else if (props.loading) {
      title = "Checking for new Hermes context";
      detail = "Refreshing the dashboard snapshot and stale-card status.";
    } else if (running) {
      title = "Updating in background";
      detail = running.summary || running.job_key || "Hermes is refreshing dashboard cards.";
    } else {
      return null;
    }
    return h("section", { className: cx("hpd-sync", snapshot && "is-compact", !snapshot && "is-prominent") },
      h("div", { className: "hpd-sync-pulse", "aria-hidden": "true" }),
      h("div", { className: "hpd-sync-copy" },
        h("p", { className: "hpd-eyebrow" }, "Updating"),
        h("strong", null, title),
        h("span", null, detail)
      ),
      h("div", { className: "hpd-sync-meter", "aria-hidden": "true" },
        h("span", { className: "hpd-sync-line" })
      )
    );
  }

  function displayValue(value, suffix) {
    if (value === null || value === undefined || value === "") return "";
    if (typeof value === "number" && Number.isFinite(value)) {
      return (Math.round(value * 10) / 10) + (suffix || "");
    }
    return String(value) + (suffix || "");
  }

  function humanLabel(value) {
    return String(value || "")
      .replace(/[_-]+/g, " ")
      .replace(/\b\w/g, function (letter) { return letter.toUpperCase(); });
  }

  function DataMetric(props) {
    const shown = displayValue(props.value, props.suffix);
    if (!shown) return null;
    return h("div", { className: "hpd-data-metric" },
      h("span", null, props.label),
      h("strong", null, shown)
    );
  }

  function appendMetric(metrics, metric) {
    if (!metric) return;
    if (Array.isArray(metric)) {
      metrics.push([metric[0], metric[1], metric[2]]);
      return;
    }
    if (typeof metric === "object") {
      metrics.push([metric.label || metric.name || "Metric", metric.value, metric.unit || metric.suffix]);
    }
  }

  function appendMetricObject(metrics, value) {
    if (!value) return;
    if (Array.isArray(value)) {
      value.forEach(function (metric) { appendMetric(metrics, metric); });
      return;
    }
    if (typeof value === "object") {
      Object.keys(value).forEach(function (key) {
        metrics.push([humanLabel(key), value[key]]);
      });
    }
  }

  function listItemKey(item) {
    if (typeof item === "string") return item.toLowerCase();
    if (!item || typeof item !== "object") return "";
    const title = itemTitle(item).toLowerCase();
    const anchor = item.url || item.source_url || item.link || item.start || item.date || item.time || "";
    return (title + "|" + String(anchor).toLowerCase()).trim();
  }

  function listItemTitleKey(item) {
    return itemTitle(item).toLowerCase().trim();
  }

  function addListGroup(groups, label, items) {
    if (!Array.isArray(items) || !items.length) return;
    const keys = items.map(listItemKey).filter(Boolean);
    const titles = items.map(listItemTitleKey).filter(Boolean);
    for (let i = 0; i < groups.length; i += 1) {
      const other = groups[i];
      const overlap = keys.filter(function (key) { return other.keys.indexOf(key) >= 0; }).length;
      const titleOverlap = titles.filter(function (title) { return other.titles.indexOf(title) >= 0; }).length;
      if (!overlap && !titleOverlap) continue;
      if (items.length > other.items.length) {
        groups[i] = { label: label, items: items, keys: keys, titles: titles };
      }
      return;
    }
    groups.push({ label: label, items: items, keys: keys, titles: titles });
  }

  function itemTitle(item) {
    if (typeof item === "string") return item;
    return item.title || item.subject || item.name || item.label || item.summary || "Item";
  }

  function itemSummary(item) {
    if (typeof item === "string") return "";
    return item.summary || item.description || item.snippet || item.detail || item.status || "";
  }

  function itemMeta(item) {
    if (typeof item === "string") return "";
    return [item.source, item.source_label, item.time, item.start, item.date, item.when]
      .filter(Boolean)
      .slice(0, 2)
      .join(" - ");
  }

  function isInternalDataItem(item) {
    const text = [
      itemTitle(item),
      itemSummary(item),
      itemMeta(item)
    ].join(" ").toLowerCase();
    const patterns = [
      "whatsapp plain text only",
      "keep it crisp",
      "bullet-pointed",
      "max 5 bullets",
      "formatting rule",
      "formatting preference",
      "preferred delivery style"
    ];
    return patterns.some(function (pattern) {
      return text.indexOf(pattern) >= 0;
    });
  }

  function DataList(props) {
    const items = (props.items || []).filter(function (item) { return !isInternalDataItem(item); });
    if (!Array.isArray(items) || !items.length) return null;
    return h("div", { className: "hpd-data-list" },
      h("span", { className: "hpd-data-label" }, props.label),
      items.slice(0, 5).map(function (item, index) {
        const title = itemTitle(item);
        const summary = itemSummary(item);
        const meta = itemMeta(item);
        const url = typeof item === "object" && item ? (item.url || item.source_url || item.link) : "";
        return h("div", { key: index + ":" + title, className: "hpd-data-item" },
          url ? h("a", { href: url, target: "_blank", rel: "noreferrer" }, title) : h("strong", null, title),
          summary && summary !== title ? h("p", null, summary) : null,
          meta ? h("small", null, meta) : null
        );
      })
    );
  }

  function StructuredData(props) {
    const payload = props.card.payload || {};
    const observed = payload.observed || payload.current || null;
    const metrics = [];
    appendMetricObject(metrics, payload.metrics);
    const hasExplicitMetrics = metrics.length > 0;
    if (!hasExplicitMetrics) {
      appendMetricObject(metrics, payload.readings);
    }
    const hasGenericMetrics = metrics.length > 0;
    if (!hasGenericMetrics && observed && typeof observed === "object" && !Array.isArray(observed)) {
      metrics.push(["Condition", observed.condition]);
      metrics.push(["Temp", observed.temp_F, "F"]);
      metrics.push(["Feels", observed.feels_like_F, "F"]);
      metrics.push(["Humidity", observed.humidity_pct, "%"]);
      metrics.push(["Wind", observed.wind_mph, " mph"]);
      metrics.push(["AQI", observed.aqi]);
    }
    if (!hasGenericMetrics) {
      metrics.push(["Machine Temp", payload.thermal_zone0_c, "C"]);
      metrics.push(["Current Temp", payload.current_temp_c, "C"]);
      metrics.push(["Current Temp", payload.current_temp_f, "F"]);
      metrics.push(["Temperature", payload.temperature_f, "F"]);
      metrics.push(["Temperature", payload.temperature_c, "C"]);
      metrics.push(["Rain chance", payload.rain_probability_max_today, "%"]);
      metrics.push(["UV index", payload.uv_index_max_today]);
      metrics.push(["Unread", payload.unread_count]);
      metrics.push(["Events", payload.calendar_events_seen]);
    }
    const metricNodes = metrics.map(function (metric) {
      return h(DataMetric, { key: metric[0] + ":" + metric[1], label: metric[0], value: metric[1], suffix: metric[2] });
    }).filter(Boolean);
    const listGroups = [];
    if (Array.isArray(payload.sections)) {
      payload.sections.forEach(function (section) {
        if (!section || typeof section !== "object") return;
        addListGroup(listGroups, section.label || section.title || "Items", section.items || section.rows || section.entries);
      });
    }
    if (payload.lists && typeof payload.lists === "object" && !Array.isArray(payload.lists)) {
      Object.keys(payload.lists).forEach(function (key) {
        addListGroup(listGroups, humanLabel(key), payload.lists[key]);
      });
    }
    if (Array.isArray(payload.items) && payload.items.length) {
      addListGroup(listGroups, "Items", payload.items);
    }
    [
      ["News", payload.news_items || payload.headlines || payload.stories],
      ["Calendar", payload.calendar_events || payload.events],
      ["Email", payload.email_items || payload.emails],
      ["Daycare", payload.daycare_items || payload.menu_items || payload.school_items],
      ["Sports", payload.fixtures || payload.games || payload.scores],
      ["Stocks", payload.tickers || payload.positions || payload.alerts]
    ].forEach(function (group) {
      addListGroup(listGroups, group[0], group[1]);
    });
    const lists = listGroups.map(function (group) {
      return h(DataList, { key: group.label, label: group.label, items: group.items });
    }).filter(Boolean);
    if (!metricNodes.length && !lists.length) return null;
    return h("div", { className: "hpd-data" },
      metricNodes.length ? h("div", { className: "hpd-data-grid" }, metricNodes) : null,
      lists
    );
  }

  function CardItem(props) {
    const card = props.card;
    const isPinned = Boolean(card.pinned) || card.status === "pinned";
    const expanded = Boolean(props.expanded);
    const hasDetail = Boolean(card.detail_md || card.why_shown);
    return h("article", { className: cx("hpd-card", card.status === "stale" && "is-stale") },
      h("div", { className: "hpd-card-top" },
        h("div", { className: "hpd-card-title-block" },
          h("div", { className: "hpd-card-domain" }, card.domain || "general"),
          h("h3", null, card.title)
        ),
        h("div", { className: "hpd-card-badges" },
          isPinned ? h(Badge, { className: "hpd-badge-pin" }, "Pinned") : null,
          h(Badge, { className: priorityClass(card.priority) }, card.priority || "medium"),
          card.status !== "active" ? h(Badge, null, card.status) : null
        )
      ),
      h(StructuredData, { card: card }),
      h("p", { className: "hpd-summary" }, card.summary),
      expanded ? h("div", { className: "hpd-card-expanded" },
        card.why_shown ? h("p", { className: "hpd-why" }, card.why_shown) : null,
        card.detail_md ? h("pre", { className: "hpd-detail" }, card.detail_md) : null
      ) : null,
      h("div", { className: "hpd-meta" },
        h("span", null, freshness(card.updated_at)),
        card.source_label ? h("span", null, card.source_label) : null
      ),
      h("div", { className: "hpd-card-actions" },
        card.source_url ? h("a", { href: card.source_url, target: "_blank", rel: "noreferrer" }, "Source") : null,
        hasDetail ? h(Button, {
          variant: "ghost",
          onClick: function () { props.onToggleDetail(card.id); },
        }, expanded ? "Hide Detail" : "Detail") : null,
        h(Button, {
          variant: "ghost",
          onClick: function () { isPinned ? props.onUnpin(card.id) : props.onPin(card.id); },
        }, isPinned ? "Unpin" : "Pin"),
        h(Button, {
          variant: "ghost",
          onClick: function () { props.onDismiss(card.id); },
        }, "Dismiss")
      )
    );
  }

  function sectionClass(title) {
    return "hpd-section-" + String(title || "cards")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "");
  }

  function CardSection(props) {
    return h("section", { className: cx("hpd-section", sectionClass(props.title)) },
      h("div", { className: "hpd-section-head" },
        h("h2", null, props.title),
        h(Badge, null, String(props.cards.length))
      ),
      props.cards.length
        ? h("div", { className: "hpd-card-grid" },
            props.cards.map(function (card) {
              return h(CardItem, {
                key: card.id,
                card: card,
                expanded: props.expandedCards && props.expandedCards[card.id],
                onDismiss: props.onDismiss,
                onPin: props.onPin,
                onUnpin: props.onUnpin,
                onToggleDetail: props.onToggleDetail,
              });
            })
          )
        : h("div", { className: "hpd-empty" }, props.empty)
    );
  }

  function insightLabel(card) {
    const domain = String(card.domain || "card");
    if (card.priority === "critical") return "Critical";
    if (card.priority === "high") return domain;
    return domain;
  }

  function Overview(props) {
    const cards = props.cards || [];
    if (!cards.length) return null;
    return h("section", { className: "hpd-briefing" },
      h("div", { className: "hpd-briefing-head" },
        h("p", { className: "hpd-eyebrow" }, "Snapshot"),
        h("h2", null, "What matters now")
      ),
      h("div", { className: "hpd-briefing-grid" },
        cards.slice(0, 5).map(function (card) {
          return h("article", { key: card.id, className: "hpd-briefing-card" },
            h("span", null, insightLabel(card)),
            h("strong", null, card.title || "Untitled card"),
            h("p", null, card.summary || ""),
            h("small", null, freshness(card.updated_at) || "current")
          );
        })
      )
    );
  }

  function StatusPanel(props) {
    const automation = props.automation || {};
    const curation = props.curation || {};
    const contextCount = (props.contextItems || []).length;
    const cardCount = (props.cards || []).length;
    const autoUpdate = autoUpdateState(props.snapshot || {});
    const refreshed = automation.refreshed ? "Scanned just now" : (automation.last_auto_refresh_at ? "Scanned " + freshness(automation.last_auto_refresh_at) : "Auto scan ready");
    return h("section", { className: "hpd-section hpd-side-panel hpd-controls-panel" },
      h("div", { className: "hpd-section-head" },
        h("h2", null, "Details"),
        h(Badge, { className: autoUpdate.tone === "installed" ? "hpd-badge-pin" : "" }, autoUpdate.badge)
      ),
      h("div", { className: "hpd-panel" },
        h("div", { className: "hpd-detail-summary" },
          h("strong", null, curation.title || "Hermes-curated dashboard"),
          h("p", null, curation.message || "Useful cards appear after Hermes curates inferred signals.")
        ),
        h("div", { className: "hpd-checklist" },
          h("span", { className: cx("hpd-checkitem", "is-done") }, h("span", { className: "hpd-checkmark" }, "OK"), "No configuration"),
          h("span", { className: cx("hpd-checkitem", contextCount > 0 && "is-done") }, h("span", { className: "hpd-checkmark" }, contextCount > 0 ? "OK" : "-"), contextCount + " signals"),
          h("span", { className: cx("hpd-checkitem", cardCount > 0 && "is-done") }, h("span", { className: "hpd-checkmark" }, cardCount > 0 ? "OK" : "-"), cardCount + " curated cards"),
          curation.scanner_cards_suppressed ? h("span", { className: cx("hpd-checkitem", "is-done") }, h("span", { className: "hpd-checkmark" }, "OK"), curation.scanner_cards_suppressed + " logs hidden") : null,
          h("span", { className: cx("hpd-checkitem", autoUpdate.tone === "installed" && "is-done") }, h("span", { className: "hpd-checkmark" }, autoUpdate.tone === "installed" ? "OK" : "-"), autoUpdate.check),
          h("span", { className: "hpd-checkitem" }, h("span", { className: "hpd-checkmark" }, "-"), refreshed)
        ),
        h("div", { className: "hpd-side-actions" },
          h("div", { className: "hpd-action-group" },
            h("div", { className: "hpd-action-title-row" },
              h("strong", { className: "hpd-action-title" }, "Scan"),
              h(Badge, null, "Manual")
            ),
            h(Button, { onClick: props.onScanNow, disabled: props.loading }, props.loading ? "Scanning" : "Scan signals")
          ),
          h("div", { className: cx("hpd-action-group", "hpd-action-group-" + autoUpdate.tone) },
            h("div", { className: "hpd-action-title-row" },
              h("strong", { className: "hpd-action-title" }, autoUpdate.title)
            ),
            h("p", { className: "hpd-action-desc" }, autoUpdate.detail),
            h(Button, { variant: "secondary", onClick: props.onCreateCron, disabled: props.loading || autoUpdate.disabled }, autoUpdate.button)
          )
        )
      )
    );
  }

  function ContextPanel(props) {
    const items = props.items || [];
    return h("section", { className: "hpd-section hpd-side-panel" },
      h("div", { className: "hpd-section-head" },
        h("h2", null, "Signals"),
        h(Badge, null, String(items.length))
      ),
      h("div", { className: "hpd-panel hpd-signal-list" },
        items.length ? items.slice(0, 10).map(function (item) {
          const sources = (item.source_types || []).join(", ");
          return h("div", { key: item.id, className: "hpd-context" },
            h("div", null,
              h("strong", null, (item.domain || "personal") + ": " + item.label),
              h("p", null, sources ? "Sources: " + sources + "." : (item.summary || "Inferred from Hermes context."))
            ),
            h("div", { className: "hpd-inline-actions" },
              h(Button, { variant: "ghost", onClick: function () { props.onHideContext(item.id); } }, "Hide")
            )
          );
        }) : h("div", { className: "hpd-empty" }, "No Hermes signals found yet.")
      )
    );
  }

  function SourceCoverage(props) {
    const report = props.report || {};
    const checks = report.checks || {};
    const byType = report.by_type || {};
    const memoryFiles = (checks.memory_files || []).filter(function (item) { return item.exists; });
    const rows = [
      { label: "Memory files", value: String(memoryFiles.length), detail: memoryFiles.map(function (item) { return item.label; }).join(", ") || "No readable memory files yet" },
      { label: "Session DB", value: checks.state_db && checks.state_db.exists ? "Found" : "Missing", detail: checks.state_db && checks.state_db.path },
      { label: "Cron jobs", value: checks.cron_jobs && checks.cron_jobs.exists ? "Found" : "Missing", detail: checks.cron_jobs && checks.cron_jobs.path },
      { label: "Cron output", value: String((checks.cron_output && checks.cron_output.file_count) || 0), detail: checks.cron_output && checks.cron_output.path },
    ];
    const typeLabels = Object.keys(byType).sort().map(function (key) { return key + ": " + byType[key]; });
    return h("div", { className: "hpd-panel" },
      h("h3", null, "Source Coverage"),
      h("div", { className: "hpd-source-total" },
        h("strong", null, String(report.source_count || 0)),
        h("span", null, "readable Hermes source" + ((report.source_count || 0) === 1 ? "" : "s"))
      ),
      typeLabels.length ? h("p", { className: "hpd-source-types" }, typeLabels.join(" - ")) : null,
      rows.map(function (row) {
        return h("div", { key: row.label, className: "hpd-context" },
          h("div", null,
            h("strong", null, row.label + ": " + row.value),
            row.detail ? h("p", null, row.detail) : null
          )
        );
      })
    );
  }

  function Activity(props) {
    const runs = props.runs || [];
    return h("section", { className: "hpd-section hpd-activity hpd-side-panel" },
      h("div", { className: "hpd-section-head" }, h("h2", null, "Hermes Activity")),
      h("div", { className: "hpd-activity-grid" },
        h("div", { className: "hpd-panel" },
          h("h3", null, "Refreshes"),
          runs.length ? runs.slice(0, 10).map(function (run) {
            return h("div", { key: run.id, className: "hpd-run" },
              h("span", { className: cx("hpd-dot", run.status === "error" && "is-error", run.status === "running" && "is-running") }),
              h("div", null,
                h("strong", null, run.job_key),
                h("p", null, (run.summary || run.error || run.status) + " - " + freshness(run.started_at))
              )
            );
          }) : h("div", { className: "hpd-empty" }, "No refreshes yet.")
        ),
        h(SourceCoverage, { report: props.sourceReport || {} })
      )
    );
  }

  function EmptyMain(props) {
    const curation = props.curation || {};
    return h("section", { className: "hpd-section hpd-main-empty" },
      h("div", { className: "hpd-section-head" },
        h("h2", null, "Cards"),
        h(Badge, null, "0")
      ),
      h("div", { className: "hpd-empty" },
        h("strong", null, curation.title || "No curated cards yet"),
        h("p", null, curation.message || "Hermes has not written any dashboard cards yet."),
        h(Button, { variant: "secondary", onClick: props.onOpenDetails }, "Open Details")
      )
    );
  }

  function MainSections(props) {
    const grouped = props.grouped;
    const total = grouped.now.length + grouped.today.length + grouped.week.length + grouped.watching.length;
    if (!total) return h(EmptyMain, { curation: props.curation, onOpenDetails: props.onOpenDetails });
    const allCards = props.cards || grouped.now.concat(grouped.today, grouped.week, grouped.watching);
    return h("div", { className: "hpd-sections" },
      h(Overview, { cards: allCards }),
      grouped.now.length ? h(CardSection, Object.assign({
        title: "Now",
        cards: grouped.now,
        empty: "No urgent Hermes-curated cards.",
      }, props.cardActions)) : null,
      grouped.today.length ? h(CardSection, Object.assign({
        title: "Today",
        cards: grouped.today,
        empty: "No daily Hermes-curated cards.",
      }, props.cardActions)) : null,
      grouped.week.length ? h(CardSection, Object.assign({
        title: "This Week",
        cards: grouped.week,
        empty: "No weekly Hermes-curated cards.",
      }, props.cardActions)) : null,
      grouped.watching.length ? h(CardSection, Object.assign({
        title: "On Radar",
        cards: grouped.watching,
        empty: "No long-running Hermes-curated watches.",
      }, props.cardActions)) : null
    );
  }

  function PersonalDashboard() {
    const [snapshot, setSnapshot] = React.useState(null);
    const [loading, setLoading] = React.useState(true);
    const [mutating, setMutating] = React.useState(false);
    const [error, setError] = React.useState("");
    const [notice, setNotice] = React.useState("");
    const [detailsOpen, setDetailsOpen] = React.useState(false);
    const [expandedCards, setExpandedCards] = React.useState({});

    const load = React.useCallback(function () {
      setLoading(true);
      return request("/snapshot")
        .then(function (data) {
          setSnapshot(data);
          setError("");
        })
        .catch(function (err) {
          setError(err.message || String(err));
        })
        .finally(function () {
          setLoading(false);
        });
    }, []);

    React.useEffect(function () {
      load();
    }, [load]);

    React.useEffect(function () {
      const id = window.setInterval(load, 60000);
      return function () { window.clearInterval(id); };
    }, [load]);

    function mutate(promise) {
      setMutating(true);
      setNotice("");
      return promise
        .then(load)
        .catch(function (err) { setError(err.message || String(err)); })
        .finally(function () { setMutating(false); });
    }

    function createRefreshJobs() {
      setMutating(true);
      setNotice("");
      return request("/automation/ensure-jobs", { method: "POST", body: JSON.stringify({}) })
        .then(function (result) {
          setError("");
          const jobLines = formatJobLines(result && result.jobs);
          const scheduleHint = "These are starter defaults. To change cadence, run /personal-dashboard create-jobs daily=09:00 frequent=30m planning=mon@16:00 force in Hermes.";
          if (result && result.error) {
            setNotice([
              "Auto updates were not installed.",
              "Tried to create these scheduled Hermes curator jobs:",
              jobLines,
              scheduleHint,
              result.error,
              result.next_step || "Run /personal-dashboard create-jobs inside Hermes."
            ].join("\n"));
          } else if (result && result.skipped) {
            setNotice([
              "Auto updates are already installed.",
              jobLines,
              scheduleHint,
              "These are scheduled jobs. Installing them does not run the curator immediately; cards update when Hermes runs them."
            ].join("\n"));
          } else {
            const createdCount = (result.created || []).length;
            setNotice([
              "Auto updates installed.",
              "Created " + createdCount + " scheduled Hermes curator " + (createdCount === 1 ? "job" : "jobs") + ".",
              jobLines,
              scheduleHint,
              "Installing jobs does not run the curator immediately. Cards update after Hermes runs them."
            ].join("\n"));
          }
          return load();
        })
        .catch(function (err) { setError(err.message || String(err)); })
        .finally(function () { setMutating(false); });
    }

    const cards = snapshot ? visibleCards(snapshot.cards || []) : [];
    const contextItems = snapshot ? (snapshot.context_items || []) : [];
    const curation = snapshot ? (snapshot.curation || {}) : {};
    const grouped = { now: [], today: [], week: [], watching: [] };
    cards.forEach(function (card) {
      const key = sectionFor(card);
      if (grouped[key]) grouped[key].push(card);
      else grouped.watching.push(card);
    });

    const cardActions = {
      onDismiss: function (id) { mutate(request("/cards/" + encodeURIComponent(id) + "/dismiss", { method: "POST" })); },
      onPin: function (id) { mutate(request("/cards/" + encodeURIComponent(id) + "/pin", { method: "POST" })); },
      onUnpin: function (id) { mutate(request("/cards/" + encodeURIComponent(id) + "/unpin", { method: "POST" })); },
      onToggleDetail: function (id) {
        setExpandedCards(function (previous) {
          return Object.assign({}, previous, { [id]: !previous[id] });
        });
      },
      expandedCards: expandedCards,
    };

    return h("main", { className: cx("hpd-root", themeClass(snapshot)) },
      h("header", { className: "hpd-header" },
        h("div", null,
          h("p", { className: "hpd-eyebrow" }, "Hermes Agent"),
          h("h1", null, "Personal Dashboard")
        ),
        h("div", { className: "hpd-header-actions" },
          h(Button, { variant: "secondary", onClick: load, disabled: loading || mutating }, loading ? "Refreshing" : "Refresh"),
          h(Button, { variant: "secondary", onClick: function () { setDetailsOpen(!detailsOpen); } }, detailsOpen ? "Hide Details" : "Details")
        )
      ),
      h(SyncStatus, { snapshot: snapshot, loading: loading, mutating: mutating }),
      error ? h(ErrorPanel, { message: error }) : null,
      notice ? h(NoticePanel, { message: notice }) : null,
      snapshot ? h(React.Fragment, null,
        h("div", { className: cx("hpd-dashboard-grid", detailsOpen && "is-details-open") },
          h("div", { className: "hpd-main-column" },
            h(MainSections, {
              grouped: grouped,
              cards: cards,
              curation: curation,
              cardActions: cardActions,
              onOpenDetails: function () { setDetailsOpen(true); },
            })
          ),
          detailsOpen ? h("aside", { className: "hpd-side-rail" },
            h(StatusPanel, {
              snapshot: snapshot,
              automation: snapshot.automation || {},
              curation: curation,
              contextItems: contextItems,
              cards: cards,
              loading: mutating,
              onScanNow: function () {
                mutate(request("/context/refresh", {
                  method: "POST",
                  body: JSON.stringify({ include_sessions: true, include_cron: true, create_cards: false }),
                }));
              },
              onCreateCron: createRefreshJobs,
            }),
            h(ContextPanel, {
              items: contextItems,
              onHideContext: function (id) { mutate(request("/context/" + encodeURIComponent(id) + "/hide", { method: "POST" })); },
            }),
            h(Activity, {
              runs: snapshot.refresh_runs || [],
              sourceReport: snapshot.source_report || {},
            })
          ) : null
        )
      ) : null
    );
  }

  window.__HERMES_PLUGINS__.register("hermes-personal-dashboard", PersonalDashboard);
})();
