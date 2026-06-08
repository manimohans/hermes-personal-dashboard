(function () {
  "use strict";

  var API = "/api/plugins/hermes-personal-dashboard";
	var state = {
	  snapshot: null,
	  loading: true,
	  mutating: false,
	  error: "",
	  notice: "",
	  detailsOpen: false,
	  expandedCards: {}
	};

  function cx() {
    return Array.prototype.slice.call(arguments).filter(Boolean).join(" ");
  }

  function el(tag, attrs) {
    var node = document.createElement(tag);
    attrs = attrs || {};
    Object.keys(attrs).forEach(function (key) {
      var value = attrs[key];
      if (value === false || value === null || value === undefined) return;
      if (key === "className") node.className = value;
      else if (key === "text") node.textContent = value;
      else if (key === "disabled") node.disabled = Boolean(value);
      else if (key === "onclick") node.addEventListener("click", value);
      else node.setAttribute(key, value);
    });
    for (var i = 2; i < arguments.length; i += 1) {
      append(node, arguments[i]);
    }
    return node;
  }

  function append(parent, child) {
    if (child === null || child === undefined || child === false) return;
    if (Array.isArray(child)) {
      child.forEach(function (item) { append(parent, item); });
      return;
    }
    if (typeof child === "string" || typeof child === "number") {
      parent.appendChild(document.createTextNode(String(child)));
      return;
    }
    parent.appendChild(child);
  }

  function freshness(value) {
    if (!value) return "";
    var ts = Date.parse(value);
    if (!Number.isFinite(ts)) return value;
    var seconds = Math.max(0, Math.floor((Date.now() - ts) / 1000));
    if (seconds < 60) return "just now";
    var minutes = Math.floor(seconds / 60);
    if (minutes < 60) return minutes + "m ago";
    var hours = Math.floor(minutes / 60);
    if (hours < 48) return hours + "h ago";
    return Math.floor(hours / 24) + "d ago";
  }

  function request(path, options) {
    options = options || {};
    return fetch(API + path, Object.assign({
      headers: { "Content-Type": "application/json" }
    }, options)).catch(function (err) {
      throw makeNetworkError(path, options, err);
    }).then(function (res) {
      return res.text().then(function (text) {
        var data = {};
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
      });
    });
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
    var message = [
      "Dashboard request failed.",
      requestMethod(options) + " " + apiUrl(path),
      "HTTP " + res.status + (res.statusText ? " " + res.statusText : ""),
      "Response: " + responseDetail(data),
      errorHint(res.status)
    ].join("\n");
    return new Error(message);
  }

  function makeNetworkError(path, options, err) {
    return new Error([
      "Dashboard API is unreachable.",
      requestMethod(options) + " " + apiUrl(path),
      "Browser error: " + ((err && err.message) || String(err)),
      "Hint: make sure the standalone server is running and that you opened the dashboard on the same host and port printed by run.sh."
    ].join("\n"));
  }

  function priorityClass(priority) {
    if (priority === "critical") return "hpd-priority-critical";
    if (priority === "high") return "hpd-priority-high";
    if (priority === "low") return "hpd-priority-low";
    return "hpd-priority-medium";
  }

  function sectionAlias(value) {
    var key = String(value || "").trim().toLowerCase().replace(/[\s-]+/g, "_");
    var aliases = {
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
    var payload = card.payload || {};
    var explicit = sectionAlias(payload.section);
    if (explicit) return explicit;
    var domainSection = sectionAlias(card.domain);
    if (domainSection) return domainSection;
    if (card.priority === "critical") return "now";
    if (card.priority === "high") return "today";
    return "watching";
  }

  function isScannerCard(card) {
    var payload = card.payload || {};
    if (payload.ai_curated || payload.user_curated || payload.keep_visible) return false;
    if (payload.scanner_generated || payload.system_card) return true;
    var id = String(card.id || "");
    var summary = String(card.summary || "").toLowerCase();
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
    var payload = card.payload || {};
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
    var payload = card.payload || {};
    var text = [
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
    var payload = card.payload || {};
    var domain = String(card.domain || "").toLowerCase();
    if (domain === "weather") {
      var title = String(card.title || "");
      var match = title.match(/^(.+?)\s+(?:weather|now|conditions)\b/i) || title.match(/^(.+?):/);
      var location = normalizeKey(match && match[1]) || normalizeKey(payload.location);
      return "weather:" + (location || "current");
    }
    if ((domain === "alerts" || domain === "sensors" || domain === "sensor") && hasTemperatureSignal(card)) {
      return "sensor:machine-temperature";
    }
    if (domain === "calendar") {
      return "calendar:current";
    }
    return "";
  }

  function cardUpdatedMs(card) {
    var value = Date.parse(card.updated_at || card.last_seen_at || "");
    return Number.isFinite(value) ? value : 0;
  }

  function cardScore(card) {
    var value = Number(card.relevance_score);
    if (!Number.isFinite(value)) value = Number((card.payload || {}).relevance_score || 0);
    return Number.isFinite(value) ? value : 0;
  }

  function betterCard(candidate, existing) {
    var candidatePinned = Boolean(candidate.pinned) || candidate.status === "pinned";
    var existingPinned = Boolean(existing.pinned) || existing.status === "pinned";
    if (candidatePinned !== existingPinned) return candidatePinned;
    var candidateHasData = hasDisplayablePayloadData(candidate);
    var existingHasData = hasDisplayablePayloadData(existing);
    if (candidateHasData !== existingHasData) return candidateHasData;
    var candidateTime = cardUpdatedMs(candidate);
    var existingTime = cardUpdatedMs(existing);
    if (Math.abs(candidateTime - existingTime) > 2 * 60 * 1000) return candidateTime > existingTime;
    return cardScore(candidate) > cardScore(existing);
  }

  function dedupeTopicCards(cards) {
    var chosen = {};
    cards.forEach(function (card) {
      var key = topicClusterKey(card);
      if (!key) return;
      if (!chosen[key] || betterCard(card, chosen[key])) chosen[key] = card;
    });
    return cards.filter(function (card) {
      var key = topicClusterKey(card);
      return !key || chosen[key] === card;
    });
  }

  function isInternalContextCard(card) {
    var payload = card.payload || {};
    if (payload.keep_visible) return false;
    if (payload.internal_card || payload.operational_metadata) return true;
    var primaryText = [
      card.title || "",
      card.summary || "",
      card.source_label || ""
    ].join(" ").toLowerCase();
    var detailText = String(card.detail_md || "").toLowerCase();
    var internalPatterns = [
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
      "should stay on the dashboard watchlist"
    ];
    for (var i = 0; i < internalPatterns.length; i += 1) {
      if (primaryText.indexOf(internalPatterns[i]) >= 0) return true;
    }
    var operationalOnlyPatterns = [
      "blocked by invisible unicode",
      "prompt contains invisible unicode",
      "job last errored",
      "failed refresh",
      "refresh failed",
      "hermes cron/jobs",
      "curator job",
      "scheduled job",
      "no new update surfaced"
    ];
    if (!hasDisplayablePayloadData(card) || payload.error) {
      for (var j = 0; j < operationalOnlyPatterns.length; j += 1) {
        if (primaryText.indexOf(operationalOnlyPatterns[j]) >= 0) return true;
      }
    }
    if (detailText.indexOf("token path:") >= 0 || detailText.indexOf("oauth client path:") >= 0) return true;
    return false;
  }

  function visibleCards(cards) {
    var filtered = (cards || []).filter(function (card) {
      return !isScannerCard(card) && !isInternalContextCard(card);
    });
    return dedupeTopicCards(filtered);
  }

  function cronJobCount(preferences) {
    var jobs = (preferences && preferences.cron_jobs) || {};
    return Object.keys(jobs).filter(function (key) { return jobs[key]; }).length;
  }

  function plural(value, singular, pluralText) {
    return value === 1 ? singular : pluralText;
  }

  function autoUpdateState(snapshot) {
    var preferences = (snapshot && snapshot.preferences) || {};
    var count = cronJobCount(preferences);
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
      var name = job.name || job.kind || "Dashboard job";
      var cadence = job.cadence || job.schedule || "scheduled";
      var purpose = job.purpose || "refresh dashboard cards";
      return "- " + name + ": " + cadence + "; " + purpose + ".";
    }).join("\n");
  }

  function button(label, variant, handler, disabled) {
    return el("button", {
      className: cx("hpd-button", variant && "hpd-button-" + variant),
      disabled: disabled,
      onclick: handler,
      text: label
    });
  }

  function badge(label, className) {
    return el("span", { className: cx("hpd-badge", className), text: label });
  }

  function runningRefresh(snapshot) {
    var runs = snapshot ? (snapshot.refresh_runs || []) : [];
    var resolvedJobs = {};
    for (var i = 0; i < runs.length; i += 1) {
      var jobKey = runs[i].job_key || "__unknown__";
      if (runs[i].status === "success" || runs[i].status === "error" || runs[i].status === "failed") {
        resolvedJobs[jobKey] = true;
        continue;
      }
      if (runs[i].status === "running") {
        if (resolvedJobs[jobKey]) continue;
        var started = Date.parse(runs[i].started_at || "");
        if (!Number.isFinite(started) || Date.now() - started < 20 * 60 * 1000) return runs[i];
      }
    }
    return null;
  }

  function humanLabel(value) {
    return String(value || "")
      .replace(/[_-]+/g, " ")
      .replace(/\b\w/g, function (letter) { return letter.toUpperCase(); });
  }

  function displayValue(value, suffix) {
    if (value === null || value === undefined || value === "") return "";
    if (typeof value === "number" && Number.isFinite(value)) {
      return (Math.round(value * 10) / 10) + (suffix || "");
    }
    return String(value) + (suffix || "");
  }

  function dataMetric(label, value, suffix) {
    var shown = displayValue(value, suffix);
    if (!shown) return null;
    return el("div", { className: "hpd-data-metric" },
      el("span", { text: label }),
      el("strong", { text: shown })
    );
  }

  function appendMetric(metrics, metric) {
    if (!metric) return;
    if (Array.isArray(metric)) {
      metrics.push(dataMetric(metric[0], metric[1], metric[2]));
      return;
    }
    if (typeof metric === "object") {
      metrics.push(dataMetric(metric.label || metric.name || "Metric", metric.value, metric.unit || metric.suffix));
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
        metrics.push(dataMetric(humanLabel(key), value[key]));
      });
    }
  }

  function listItemKey(item) {
    if (typeof item === "string") return item.toLowerCase();
    if (!item || typeof item !== "object") return "";
    var title = itemTitle(item).toLowerCase();
    var anchor = item.url || item.source_url || item.link || item.start || item.date || item.time || "";
    return (title + "|" + String(anchor).toLowerCase()).trim();
  }

  function listItemTitleKey(item) {
    return itemTitle(item).toLowerCase().trim();
  }

  function addListGroup(groups, label, items) {
    if (!Array.isArray(items) || !items.length) return;
    var keys = items.map(listItemKey).filter(Boolean);
    var titles = items.map(listItemTitleKey).filter(Boolean);
    for (var i = 0; i < groups.length; i += 1) {
      var other = groups[i];
      var overlap = keys.filter(function (key) { return other.keys.indexOf(key) >= 0; }).length;
      var titleOverlap = titles.filter(function (title) { return other.titles.indexOf(title) >= 0; }).length;
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
    var text = [
      itemTitle(item),
      itemSummary(item),
      itemMeta(item)
    ].join(" ").toLowerCase();
    var patterns = [
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

  function dataList(label, items) {
    if (!Array.isArray(items) || !items.length) return null;
    var visibleItems = items.filter(function (item) { return !isInternalDataItem(item); });
    if (!visibleItems.length) return null;
    return el("div", { className: "hpd-data-list" },
      el("span", { className: "hpd-data-label", text: label }),
      visibleItems.slice(0, 5).map(function (item) {
        var title = itemTitle(item);
        var summary = itemSummary(item);
        var meta = itemMeta(item);
        var url = typeof item === "object" && item ? (item.url || item.source_url || item.link) : "";
        return el("div", { className: "hpd-data-item" },
          url ? el("a", { href: url, target: "_blank", rel: "noreferrer", text: title }) : el("strong", { text: title }),
          summary && summary !== title ? el("p", { text: summary }) : null,
          meta ? el("small", { text: meta }) : null
        );
      })
    );
  }

  function structuredData(card) {
    var payload = card.payload || {};
    var nodes = [];
    var metrics = [];
    appendMetricObject(metrics, payload.metrics);
    var hasExplicitMetrics = metrics.filter(Boolean).length > 0;
    if (!hasExplicitMetrics) {
      appendMetricObject(metrics, payload.readings);
    }
    var hasGenericMetrics = metrics.filter(Boolean).length > 0;
    var observed = payload.observed || payload.current || null;
    if (!hasGenericMetrics && observed && typeof observed === "object" && !Array.isArray(observed)) {
      metrics.push(dataMetric("Condition", observed.condition));
      metrics.push(dataMetric("Temp", observed.temp_F, "F"));
      metrics.push(dataMetric("Feels", observed.feels_like_F, "F"));
      metrics.push(dataMetric("Humidity", observed.humidity_pct, "%"));
      metrics.push(dataMetric("Wind", observed.wind_mph, " mph"));
      metrics.push(dataMetric("AQI", observed.aqi));
    }
    if (!hasGenericMetrics) {
      metrics.push(dataMetric("Machine Temp", payload.thermal_zone0_c, "C"));
      metrics.push(dataMetric("Current Temp", payload.current_temp_c, "C"));
      metrics.push(dataMetric("Current Temp", payload.current_temp_f, "F"));
      metrics.push(dataMetric("Temperature", payload.temperature_f, "F"));
      metrics.push(dataMetric("Temperature", payload.temperature_c, "C"));
      metrics.push(dataMetric("Rain chance", payload.rain_probability_max_today, "%"));
      metrics.push(dataMetric("UV index", payload.uv_index_max_today));
      metrics.push(dataMetric("Unread", payload.unread_count));
      metrics.push(dataMetric("Events", payload.calendar_events_seen));
    }
    metrics = metrics.filter(Boolean);
    if (metrics.length) {
      nodes.push(el("div", { className: "hpd-data-grid" }, metrics));
    }

    var listGroups = [];
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
    listGroups.forEach(function (group) {
      var list = dataList(group.label, group.items);
      if (list) nodes.push(list);
    });

    if (!nodes.length) return null;
    return el("div", { className: "hpd-data" }, nodes);
  }

  function syncStatus(snapshot) {
    var running = runningRefresh(snapshot);
    var title = "";
    var detail = "";
    if (state.mutating) {
      title = "Updating dashboard";
      detail = "Refreshing Hermes signals, curated cards, freshness, and source coverage.";
    } else if (state.loading && !snapshot) {
      title = "Reading Hermes signals";
      detail = "Scanning memory, sessions, cron output, and existing curated cards.";
    } else if (state.loading) {
      title = "Checking for new Hermes context";
      detail = "Refreshing the dashboard snapshot and stale-card status.";
    } else if (running) {
      title = "Updating in background";
      detail = running.summary || running.job_key || "Hermes is refreshing dashboard cards.";
    } else {
      return null;
    }
    return el("section", { className: cx("hpd-sync", snapshot && "is-compact", !snapshot && "is-prominent") },
      el("div", { className: "hpd-sync-pulse", "aria-hidden": "true" }),
      el("div", { className: "hpd-sync-copy" },
        el("p", { className: "hpd-eyebrow", text: "Updating" }),
        el("strong", { text: title }),
        el("span", { text: detail })
      ),
      el("div", { className: "hpd-sync-meter", "aria-hidden": "true" },
        el("span", { className: "hpd-sync-line" })
      )
    );
  }

  function errorPanel(message) {
    var lines = String(message || "Unknown dashboard error.").split("\n");
    return el("div", { className: "hpd-error" },
      el("strong", { className: "hpd-error-title", text: lines.shift() || "Dashboard error" }),
      el("pre", { className: "hpd-error-detail", text: lines.join("\n") })
    );
  }

  function noticePanel(message) {
    var lines = String(message || "").split("\n");
    return el("div", { className: "hpd-notice" },
      el("strong", { className: "hpd-notice-title", text: lines.shift() || "Dashboard notice" }),
      lines.length ? el("pre", { className: "hpd-notice-detail", text: lines.join("\n") }) : null
    );
  }

  function mutate(promise) {
    state.mutating = true;
    state.notice = "";
    render();
    return promise.then(load).catch(function (err) {
      state.error = err.message || String(err);
      state.mutating = false;
      render();
    });
  }

  function createRefreshJobs() {
    state.mutating = true;
    state.notice = "";
    render();
    return request("/automation/ensure-jobs", { method: "POST", body: JSON.stringify({}) })
      .then(function (result) {
        state.error = "";
        var jobLines = formatJobLines(result.jobs);
        var scheduleHint = "These are starter defaults. To change cadence, run /personal-dashboard create-jobs daily=09:00 frequent=30m planning=mon@16:00 force in Hermes.";
        if (result.error) {
          state.notice = [
            "Auto updates were not installed.",
            "Tried to create these scheduled Hermes curator jobs:",
            jobLines,
            scheduleHint,
            result.error,
            result.next_step || "Run /personal-dashboard create-jobs inside Hermes."
          ].join("\n");
        } else if (result.skipped) {
          state.notice = [
            "Auto updates are already installed.",
            jobLines,
            scheduleHint,
            "These are scheduled jobs. Installing them does not run the curator immediately; cards update when Hermes runs them."
          ].join("\n");
        } else {
          var createdCount = (result.created || []).length;
          state.notice = [
            "Auto updates installed.",
            "Created " + createdCount + " scheduled Hermes curator " + (createdCount === 1 ? "job" : "jobs") + ".",
            jobLines,
            scheduleHint,
            "Installing jobs does not run the curator immediately. Cards update after Hermes runs them."
          ].join("\n");
        }
        return load();
      })
      .catch(function (err) {
        state.error = err.message || String(err);
        state.mutating = false;
        render();
      });
  }

  function load() {
    state.loading = true;
    render();
    return request("/snapshot").then(function (data) {
      state.snapshot = data;
      state.error = "";
    }).catch(function (err) {
      state.error = err.message || String(err);
    }).finally(function () {
      state.loading = false;
      state.mutating = false;
      render();
    });
  }

  function cardItem(card) {
    var isPinned = Boolean(card.pinned) || card.status === "pinned";
    var expanded = Boolean(state.expandedCards[card.id]);
    var hasDetail = Boolean(card.detail_md || card.why_shown);
    var dataView = structuredData(card);
    return el("article", { className: cx("hpd-card", card.status === "stale" && "is-stale") },
      el("div", { className: "hpd-card-top" },
        el("div", { className: "hpd-card-title-block" },
          el("div", { className: "hpd-card-domain", text: card.domain || "general" }),
          el("h3", { text: card.title || "Untitled card" })
        ),
        el("div", { className: "hpd-card-badges" },
          isPinned ? badge("Pinned", "hpd-badge-pin") : null,
          badge(card.priority || "medium", priorityClass(card.priority)),
          card.status !== "active" ? badge(card.status || "active") : null
        )
      ),
      dataView,
      el("p", { className: "hpd-summary", text: card.summary || "" }),
      expanded ? el("div", { className: "hpd-card-expanded" },
        card.why_shown ? el("p", { className: "hpd-why", text: card.why_shown }) : null,
        card.detail_md ? el("pre", { className: "hpd-detail", text: card.detail_md }) : null
      ) : null,
      el("div", { className: "hpd-meta" },
        freshness(card.updated_at) ? el("span", { text: freshness(card.updated_at) }) : null,
        card.source_label ? el("span", { text: card.source_label }) : null
      ),
      el("div", { className: "hpd-card-actions" },
        card.source_url ? el("a", { href: card.source_url, target: "_blank", rel: "noreferrer", text: "Source" }) : null,
        hasDetail ? button(expanded ? "Hide Detail" : "Detail", "ghost", function () {
          state.expandedCards[card.id] = !expanded;
          render();
        }, false) : null,
        button(isPinned ? "Unpin" : "Pin", "ghost", function () {
          mutate(request("/cards/" + encodeURIComponent(card.id) + "/" + (isPinned ? "unpin" : "pin"), { method: "POST" }));
        }, state.mutating),
        button("Dismiss", "ghost", function () {
          mutate(request("/cards/" + encodeURIComponent(card.id) + "/dismiss", { method: "POST" }));
        }, state.mutating)
      )
    );
  }

  function insightLabel(card) {
    var domain = String(card.domain || "card");
    if (card.priority === "critical") return "Critical";
    if (card.priority === "high") return domain;
    return domain;
  }

  function overview(cards) {
    if (!cards.length) return null;
    var top = cards.slice(0, 5);
    return el("section", { className: "hpd-briefing" },
      el("div", { className: "hpd-briefing-head" },
        el("p", { className: "hpd-eyebrow", text: "Snapshot" }),
        el("h2", { text: "What matters now" })
      ),
      el("div", { className: "hpd-briefing-grid" },
        top.map(function (card) {
          return el("article", { className: "hpd-briefing-card" },
            el("span", { text: insightLabel(card) }),
            el("strong", { text: card.title || "Untitled card" }),
            el("p", { text: card.summary || "" }),
            el("small", { text: freshness(card.updated_at) || "current" })
          );
        })
      )
    );
  }

  function cardSection(title, cards, emptyText) {
    return el("section", { className: "hpd-section" },
      el("div", { className: "hpd-section-head" },
        el("h2", { text: title }),
        badge(String(cards.length))
      ),
      cards.length
        ? el("div", { className: "hpd-card-grid" }, cards.map(cardItem))
        : el("div", { className: "hpd-empty", text: emptyText })
    );
  }

	function statusPanel(snapshot, cards, contextItems) {
	  var automation = snapshot.automation || {};
	  var curation = snapshot.curation || {};
	  var autoUpdate = autoUpdateState(snapshot);
	  var refreshed = automation.refreshed
	    ? "Scanned just now"
	    : (automation.last_auto_refresh_at ? "Scanned " + freshness(automation.last_auto_refresh_at) : "Auto scan ready");
	  return el("section", { className: "hpd-section hpd-side-panel hpd-controls-panel" },
	    el("div", { className: "hpd-section-head" },
	      el("h2", { text: "Details" }),
	      badge(autoUpdate.badge, autoUpdate.tone === "installed" ? "hpd-badge-pin" : "")
	    ),
	    el("div", { className: "hpd-panel" },
	      el("div", { className: "hpd-detail-summary" },
	        el("strong", { text: curation.title || "Hermes-curated dashboard" }),
	        el("p", { text: curation.message || "Useful cards appear after Hermes curates inferred signals." })
	      ),
	      el("div", { className: "hpd-checklist" },
	        checkItem("OK", "No configuration", true),
	        checkItem(contextItems.length > 0 ? "OK" : "-", contextItems.length + " signals", contextItems.length > 0),
          checkItem(cards.length > 0 ? "OK" : "-", cards.length + " curated cards", cards.length > 0),
          curation.scanner_cards_suppressed ? checkItem("OK", curation.scanner_cards_suppressed + " logs hidden", true) : null,
          checkItem(autoUpdate.tone === "installed" ? "OK" : "-", autoUpdate.check, autoUpdate.tone === "installed"),
          checkItem("-", refreshed, false)
	      ),
	      el("div", { className: "hpd-side-actions" },
	        el("div", { className: "hpd-action-group" },
	          el("div", { className: "hpd-action-title-row" },
	            el("strong", { className: "hpd-action-title", text: "Scan" }),
	            badge("Manual")
	          ),
	          button(state.mutating ? "Scanning" : "Scan signals", null, function () {
	            mutate(request("/context/refresh", {
	              method: "POST",
	              body: JSON.stringify({ include_sessions: true, include_cron: true, create_cards: false })
	            }));
	          }, state.mutating)
	        ),
	        el("div", { className: cx("hpd-action-group", "hpd-action-group-" + autoUpdate.tone) },
	          el("div", { className: "hpd-action-title-row" },
	            el("strong", { className: "hpd-action-title", text: autoUpdate.title })
	          ),
	          el("p", { className: "hpd-action-desc", text: autoUpdate.detail }),
	          button(autoUpdate.button, "secondary", createRefreshJobs, state.mutating || autoUpdate.disabled)
	        )
	      )
	    )
	  );
  }

  function checkItem(mark, text, done) {
    return el("span", { className: cx("hpd-checkitem", done && "is-done") },
      el("span", { className: "hpd-checkmark", text: mark }),
      text
    );
  }

  function contextPanel(items) {
    return el("section", { className: "hpd-section hpd-side-panel" },
      el("div", { className: "hpd-section-head" },
        el("h2", { text: "Signals" }),
        badge(String(items.length))
      ),
      el("div", { className: "hpd-panel hpd-signal-list" },
        items.length ? items.slice(0, 10).map(function (item) {
          var sources = (item.source_types || []).join(", ");
          return el("div", { className: "hpd-context" },
            el("div", null,
              el("strong", { text: (item.domain || "personal") + ": " + item.label }),
              el("p", { text: sources ? "Sources: " + sources + "." : (item.summary || "Inferred from Hermes context.") })
            ),
            el("div", { className: "hpd-inline-actions" },
              button("Hide", "ghost", function () {
                mutate(request("/context/" + encodeURIComponent(item.id) + "/hide", { method: "POST" }));
              }, state.mutating)
            )
          );
        }) : el("div", { className: "hpd-empty", text: "No Hermes signals found yet." })
      )
    );
  }

  function sourceCoverage(report) {
    report = report || {};
    var checks = report.checks || {};
    var byType = report.by_type || {};
    var memoryFiles = (checks.memory_files || []).filter(function (item) { return item.exists; });
    var rows = [
      { label: "Memory files", value: String(memoryFiles.length), detail: memoryFiles.map(function (item) { return item.label; }).join(", ") || "No readable memory files yet" },
      { label: "Session DB", value: checks.state_db && checks.state_db.exists ? "Found" : "Missing", detail: checks.state_db && checks.state_db.path },
      { label: "Cron jobs", value: checks.cron_jobs && checks.cron_jobs.exists ? "Found" : "Missing", detail: checks.cron_jobs && checks.cron_jobs.path },
      { label: "Cron output", value: String((checks.cron_output && checks.cron_output.file_count) || 0), detail: checks.cron_output && checks.cron_output.path }
    ];
    var typeLabels = Object.keys(byType).sort().map(function (key) { return key + ": " + byType[key]; });
    return el("div", { className: "hpd-panel" },
      el("h3", { text: "Source Coverage" }),
      el("div", { className: "hpd-source-total" },
        el("strong", { text: String(report.source_count || 0) }),
        el("span", { text: "readable Hermes source" + ((report.source_count || 0) === 1 ? "" : "s") })
      ),
      typeLabels.length ? el("p", { className: "hpd-source-types", text: typeLabels.join(" - ") }) : null,
      rows.map(function (row) {
        return el("div", { className: "hpd-context" },
          el("div", null,
            el("strong", { text: row.label + ": " + row.value }),
            row.detail ? el("p", { text: row.detail }) : null
          )
        );
      })
    );
  }

  function activity(snapshot) {
    var runs = snapshot.refresh_runs || [];
    return el("section", { className: "hpd-section hpd-activity hpd-side-panel" },
      el("div", { className: "hpd-section-head" }, el("h2", { text: "Hermes Activity" })),
      el("div", { className: "hpd-activity-grid" },
        el("div", { className: "hpd-panel" },
          el("h3", { text: "Refreshes" }),
          runs.length ? runs.slice(0, 10).map(function (run) {
            return el("div", { className: "hpd-run" },
              el("span", { className: cx("hpd-dot", run.status === "error" && "is-error", run.status === "running" && "is-running") }),
              el("div", null,
                el("strong", { text: run.job_key }),
                el("p", { text: (run.summary || run.error || run.status) + " - " + freshness(run.started_at) })
              )
            );
          }) : el("div", { className: "hpd-empty", text: "No refreshes yet." })
        ),
        sourceCoverage(snapshot.source_report || {})
      )
    );
  }

	function emptyMain(curation, onOpenDetails) {
	  curation = curation || {};
	  return el("section", { className: "hpd-section hpd-main-empty" },
	    el("div", { className: "hpd-section-head" },
	      el("h2", { text: "Cards" }),
	      badge("0")
	    ),
	    el("div", { className: "hpd-empty" },
	      el("strong", { text: curation.title || "No curated cards yet" }),
	      el("p", { text: curation.message || "Hermes has not written any dashboard cards yet." }),
	      button("Open Details", "secondary", onOpenDetails, false)
	    )
	  );
	}

	function mainSections(grouped, curation, onOpenDetails, rankedCards) {
	  var total = grouped.now.length + grouped.today.length + grouped.week.length + grouped.watching.length;
	  if (!total) return emptyMain(curation, onOpenDetails);
	  return el("div", { className: "hpd-sections" },
      overview(rankedCards || grouped.now.concat(grouped.today, grouped.week, grouped.watching)),
      grouped.now.length ? cardSection("Now", grouped.now, "") : null,
      grouped.today.length ? cardSection("Today", grouped.today, "") : null,
      grouped.week.length ? cardSection("This Week", grouped.week, "") : null,
      grouped.watching.length ? cardSection("On Radar", grouped.watching, "") : null
    );
  }

	function render() {
    var root = document.getElementById("app-root");
    if (!root) return;
    root.innerHTML = "";
    var snapshot = state.snapshot;
    var cards = snapshot ? visibleCards(snapshot.cards || []) : [];
    var contextItems = snapshot ? (snapshot.context_items || []) : [];
    var curation = snapshot ? (snapshot.curation || {}) : {};
	    var grouped = { now: [], today: [], week: [], watching: [] };
	    var openDetails = function () {
	      state.detailsOpen = true;
	      render();
	    };
	    var toggleDetails = function () {
	      state.detailsOpen = !state.detailsOpen;
	      render();
	    };
	    cards.forEach(function (card) {
      var key = sectionFor(card);
      if (grouped[key]) grouped[key].push(card);
      else grouped.watching.push(card);
    });

    root.appendChild(el("main", { className: "hpd-root" },
      el("header", { className: "hpd-header" },
        el("div", null,
          el("p", { className: "hpd-eyebrow", text: "Hermes Agent" }),
          el("h1", { text: "Personal Dashboard" })
	        ),
	        el("div", { className: "hpd-header-actions" },
	          button(state.loading ? "Refreshing" : "Refresh", "secondary", load, state.loading || state.mutating),
	          button(state.detailsOpen ? "Hide Details" : "Details", "secondary", toggleDetails, false)
	        )
	      ),
      syncStatus(snapshot),
      state.error ? errorPanel(state.error) : null,
	      state.notice ? noticePanel(state.notice) : null,
	      snapshot ? [
	        el("div", { className: cx("hpd-dashboard-grid", state.detailsOpen && "is-details-open") },
	          el("div", { className: "hpd-main-column" },
	            mainSections(grouped, curation, openDetails, cards)
	          ),
	          state.detailsOpen ? el("aside", { className: "hpd-side-rail" },
	            statusPanel(snapshot, cards, contextItems),
	            contextPanel(contextItems),
	            activity(snapshot)
	          ) : null
	        )
	      ] : null
    ));
  }

  load();
  window.setInterval(load, 60 * 1000);
})();
