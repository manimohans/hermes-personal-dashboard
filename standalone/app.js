(function () {
  "use strict";

  var API = "/api/plugins/hermes-personal-dashboard";
  var state = {
    snapshot: null,
    loading: true,
    mutating: false,
    error: "",
    notice: ""
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

  function sectionFor(card) {
    var payload = card.payload || {};
    if (payload.section) return payload.section;
    if (card.pinned || card.priority === "critical" || card.priority === "high") return "now";
    if (["weather", "calendar", "alerts"].indexOf(card.domain) >= 0) return "now";
    if (["news", "daily", "daycare", "family"].indexOf(card.domain) >= 0) return "today";
    if (["planning", "sports", "events"].indexOf(card.domain) >= 0) return "week";
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

  function visibleCards(cards) {
    return (cards || []).filter(function (card) { return !isScannerCard(card); });
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
    for (var i = 0; i < runs.length; i += 1) {
      if (runs[i].status === "running") return runs[i];
    }
    return null;
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
      title = "Hermes refresh running";
      detail = running.summary || running.job_key || "A scheduled dashboard refresh is in progress.";
    } else {
      return null;
    }
    return el("section", { className: cx("hpd-sync", !snapshot && "is-prominent") },
      el("div", { className: "hpd-sync-pulse", "aria-hidden": "true" }),
      el("div", { className: "hpd-sync-copy" },
        el("p", { className: "hpd-eyebrow", text: "Working" }),
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
        if (result.error) {
          state.notice = [
            "Refresh jobs were not created.",
            result.error,
            result.next_step || "Run /personal-dashboard create-jobs inside Hermes."
          ].join("\n");
        } else if (result.skipped) {
          state.notice = "Refresh jobs already exist.";
        } else {
          state.notice = "Refresh jobs created.\nHermes will update cards when the jobs run.";
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
      el("p", { className: "hpd-summary", text: card.summary || "" }),
      card.detail_md ? el("pre", { className: "hpd-detail", text: card.detail_md }) : null,
      el("div", { className: "hpd-meta" },
        freshness(card.updated_at) ? el("span", { text: freshness(card.updated_at) }) : null,
        card.source_label ? el("span", { text: card.source_label }) : null,
        card.why_shown ? el("span", { text: card.why_shown }) : null
      ),
      el("div", { className: "hpd-card-actions" },
        card.source_url ? el("a", { href: card.source_url, target: "_blank", rel: "noreferrer", text: "Source" }) : null,
        button(isPinned ? "Unpin" : "Pin", "ghost", function () {
          mutate(request("/cards/" + encodeURIComponent(card.id) + "/" + (isPinned ? "unpin" : "pin"), { method: "POST" }));
        }, state.mutating),
        button("Dismiss", "ghost", function () {
          mutate(request("/cards/" + encodeURIComponent(card.id) + "/dismiss", { method: "POST" }));
        }, state.mutating)
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

  function curationPanel(snapshot, cards, contextItems) {
    var automation = snapshot.automation || {};
    var curation = snapshot.curation || {};
    var refreshed = automation.refreshed
      ? "Scanned just now"
      : (automation.last_auto_refresh_at ? "Scanned " + freshness(automation.last_auto_refresh_at) : "Auto scan ready");
    return el("section", { className: "hpd-start" },
      el("div", { className: "hpd-start-copy" },
        el("p", { className: "hpd-eyebrow", text: "AI curated" }),
        el("h2", { text: curation.title || "Hermes-curated dashboard" }),
        el("p", { className: "hpd-start-message", text: curation.message || "Useful cards appear here after Hermes curates the inferred signals." }),
        el("div", { className: "hpd-checklist" },
          checkItem("OK", "No configuration", true),
          checkItem(contextItems.length > 0 ? "OK" : "-", contextItems.length + " signals", contextItems.length > 0),
          checkItem(cards.length > 0 ? "OK" : "-", cards.length + " curated cards", cards.length > 0),
          curation.scanner_cards_suppressed ? checkItem("OK", curation.scanner_cards_suppressed + " logs hidden", true) : null,
          checkItem("-", refreshed, false)
        )
      ),
      el("div", { className: "hpd-start-actions" },
        button(state.mutating ? "Scanning" : "Scan signals", null, function () {
          mutate(request("/context/refresh", {
            method: "POST",
            body: JSON.stringify({ include_sessions: true, include_cron: true, create_cards: false })
          }));
        }, state.mutating),
        button("Create refresh jobs", "secondary", createRefreshJobs, state.mutating)
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

  function emptyMain(curation) {
    curation = curation || {};
    return el("section", { className: "hpd-section hpd-main-empty" },
      el("div", { className: "hpd-section-head" },
        el("h2", { text: "Cards" }),
        badge("0")
      ),
      el("div", { className: "hpd-empty" },
        el("strong", { text: curation.title || "No curated cards yet" }),
        el("p", { text: curation.message || "Hermes has not written any dashboard cards yet." })
      )
    );
  }

  function mainSections(grouped, curation) {
    var total = grouped.now.length + grouped.today.length + grouped.week.length + grouped.watching.length;
    if (!total) return emptyMain(curation);
    return el("div", { className: "hpd-sections" },
      grouped.now.length ? cardSection("Now", grouped.now, "") : null,
      grouped.today.length ? cardSection("Today", grouped.today, "") : null,
      grouped.week.length ? cardSection("This Week", grouped.week, "") : null,
      grouped.watching.length ? cardSection("Watching", grouped.watching, "") : null
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
          badge("Standalone", "hpd-badge-pin"),
          button(state.loading ? "Refreshing" : "Refresh", "secondary", load, state.loading || state.mutating)
        )
      ),
      syncStatus(snapshot),
      state.error ? errorPanel(state.error) : null,
      state.notice ? noticePanel(state.notice) : null,
      snapshot ? [
        curationPanel(snapshot, cards, contextItems),
        el("div", { className: "hpd-dashboard-grid" },
          el("div", { className: "hpd-main-column" },
            mainSections(grouped, curation)
          ),
          el("aside", { className: "hpd-side-rail" },
            contextPanel(contextItems),
            activity(snapshot)
          )
        )
      ] : null
    ));
  }

  load();
  window.setInterval(load, 60 * 1000);
})();
