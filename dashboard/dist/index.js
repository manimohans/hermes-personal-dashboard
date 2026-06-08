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
      "Hint: make sure the standalone server is running and that you opened the dashboard on the same host and port printed by install.sh."
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

  function priorityClass(priority) {
    if (priority === "critical") return "hpd-priority-critical";
    if (priority === "high") return "hpd-priority-high";
    if (priority === "low") return "hpd-priority-low";
    return "hpd-priority-medium";
  }

  function sectionFor(card) {
    const payload = card.payload || {};
    if (payload.section) return payload.section;
    if (card.pinned || card.priority === "critical" || card.priority === "high") return "now";
    if (["weather", "calendar", "alerts"].indexOf(card.domain) >= 0) return "now";
    if (["news", "daily", "daycare", "family"].indexOf(card.domain) >= 0) return "today";
    if (["planning", "sports", "events"].indexOf(card.domain) >= 0) return "week";
    return "watching";
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

  function runningRefresh(snapshot) {
    const runs = snapshot ? (snapshot.refresh_runs || []) : [];
    for (let i = 0; i < runs.length; i += 1) {
      if (runs[i].status === "running") return runs[i];
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
      detail = "Refreshing Hermes context, cards, freshness, and source coverage.";
    } else if (props.loading && !snapshot) {
      title = "Reading Hermes context";
      detail = "Scanning memory, sessions, cron output, and existing dashboard cards.";
    } else if (props.loading) {
      title = "Checking for new Hermes context";
      detail = "Refreshing the dashboard snapshot and stale-card status.";
    } else if (running) {
      title = "Hermes refresh running";
      detail = running.summary || running.job_key || "A scheduled dashboard refresh is in progress.";
    } else {
      return null;
    }
    return h("section", { className: cx("hpd-sync", !snapshot && "is-prominent") },
      h("div", { className: "hpd-sync-pulse", "aria-hidden": "true" }),
      h("div", { className: "hpd-sync-copy" },
        h("p", { className: "hpd-eyebrow" }, "Working"),
        h("strong", null, title),
        h("span", null, detail)
      ),
      h("div", { className: "hpd-sync-meter", "aria-hidden": "true" },
        h("span", { className: "hpd-sync-line" })
      )
    );
  }

  function CardItem(props) {
    const card = props.card;
    const isPinned = Boolean(card.pinned) || card.status === "pinned";
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
      h("p", { className: "hpd-summary" }, card.summary),
      card.detail_md ? h("pre", { className: "hpd-detail" }, card.detail_md) : null,
      h("div", { className: "hpd-meta" },
        h("span", null, freshness(card.updated_at)),
        card.source_label ? h("span", null, card.source_label) : null,
        card.why_shown ? h("span", null, card.why_shown) : null
      ),
      h("div", { className: "hpd-card-actions" },
        card.source_url ? h("a", { href: card.source_url, target: "_blank", rel: "noreferrer" }, "Source") : null,
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

  function CardSection(props) {
    return h("section", { className: "hpd-section" },
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
                onDismiss: props.onDismiss,
                onPin: props.onPin,
                onUnpin: props.onUnpin,
              });
            })
          )
        : h("div", { className: "hpd-empty" }, props.empty)
    );
  }

  function ReflectionPanel(props) {
    const automation = props.automation || {};
    const contextCount = (props.contextItems || []).length;
    const cardCount = (props.cards || []).length;
    const refreshed = automation.refreshed ? "Scanned just now" : (automation.last_auto_refresh_at ? "Scanned " + freshness(automation.last_auto_refresh_at) : "Auto scan ready");
    return h("section", { className: "hpd-start" },
      h("div", { className: "hpd-start-copy" },
        h("p", { className: "hpd-eyebrow" }, "Zero setup"),
        h("h2", null, "Reflecting Hermes context"),
        h("div", { className: "hpd-checklist" },
          h("span", { className: cx("hpd-checkitem", "is-done") }, h("span", { className: "hpd-checkmark" }, "OK"), "No configuration"),
          h("span", { className: cx("hpd-checkitem", contextCount > 0 && "is-done") }, h("span", { className: "hpd-checkmark" }, contextCount > 0 ? "OK" : "-"), contextCount + " inferred"),
          h("span", { className: cx("hpd-checkitem", cardCount > 0 && "is-done") }, h("span", { className: "hpd-checkmark" }, cardCount > 0 ? "OK" : "-"), cardCount + " cards"),
          h("span", { className: "hpd-checkitem" }, h("span", { className: "hpd-checkmark" }, "-"), refreshed)
        )
      ),
      h("div", { className: "hpd-start-actions" },
        h(Button, { onClick: props.onScanNow, disabled: props.loading }, props.loading ? "Scanning" : "Scan Hermes now"),
        h(Button, { variant: "secondary", onClick: props.onCreateCron }, "Create refresh jobs")
      )
    );
  }

  function ContextPanel(props) {
    const items = props.items || [];
    return h("section", { className: "hpd-section hpd-activity" },
      h("div", { className: "hpd-section-head" },
        h("h2", null, "Inferred Context"),
        h(Badge, null, String(items.length))
      ),
      h("div", { className: "hpd-activity-grid" },
        h("div", { className: "hpd-panel" },
          h("h3", null, "What Hermes appears to care about"),
          items.length ? items.slice(0, 12).map(function (item) {
            const sources = (item.source_types || []).join(", ");
            return h("div", { key: item.id, className: "hpd-context" },
              h("div", null,
                h("strong", null, (item.domain || "personal") + ": " + item.label),
                h("p", null, (item.summary || "Inferred from Hermes context.") + (sources ? " Sources: " + sources + "." : ""))
              ),
              h("div", { className: "hpd-inline-actions" },
                h(Button, { variant: "ghost", onClick: function () { props.onHideContext(item.id); } }, "Hide")
              )
            );
          }) : h("div", { className: "hpd-empty" }, "No Hermes memory, session, or cron context found yet. This fills in automatically as Hermes works.")
        )
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
    return h("section", { className: "hpd-section hpd-activity" },
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

  function PersonalDashboard() {
    const [snapshot, setSnapshot] = React.useState(null);
    const [loading, setLoading] = React.useState(true);
    const [mutating, setMutating] = React.useState(false);
    const [error, setError] = React.useState("");

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
      return promise
        .then(load)
        .catch(function (err) { setError(err.message || String(err)); })
        .finally(function () { setMutating(false); });
    }

    const cards = snapshot ? (snapshot.cards || []) : [];
    const contextItems = snapshot ? (snapshot.context_items || []) : [];
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
    };

    return h("main", { className: "hpd-root" },
      h("header", { className: "hpd-header" },
        h("div", null,
          h("p", { className: "hpd-eyebrow" }, "Hermes Agent"),
          h("h1", null, "Personal Dashboard")
        ),
        h("div", { className: "hpd-header-actions" },
          h(Badge, { className: "hpd-badge-pin" }, "Autonomous"),
          h(Button, { variant: "secondary", onClick: load, disabled: loading || mutating }, loading ? "Refreshing" : "Refresh")
        )
      ),
      h(SyncStatus, { snapshot: snapshot, loading: loading, mutating: mutating }),
      error ? h(ErrorPanel, { message: error }) : null,
      snapshot ? h(React.Fragment, null,
        h(ReflectionPanel, {
          automation: snapshot.automation || {},
          contextItems: contextItems,
          cards: cards,
          loading: mutating,
          onScanNow: function () {
            mutate(request("/context/refresh", {
              method: "POST",
              body: JSON.stringify({ include_sessions: true, include_cron: true, create_cards: true }),
            }));
          },
          onCreateCron: function () { mutate(request("/automation/ensure-jobs", { method: "POST", body: JSON.stringify({}) })); },
        }),
        h("div", { className: "hpd-sections" },
          h(CardSection, Object.assign({
            title: "Now",
            cards: grouped.now,
            empty: "No urgent Hermes-derived cards.",
          }, cardActions)),
          h(CardSection, Object.assign({
            title: "Today",
            cards: grouped.today,
            empty: "No daily Hermes-derived cards.",
          }, cardActions)),
          h(CardSection, Object.assign({
            title: "This Week",
            cards: grouped.week,
            empty: "No weekly Hermes-derived cards.",
          }, cardActions)),
          h(CardSection, Object.assign({
            title: "Watching",
            cards: grouped.watching,
            empty: "No long-running Hermes-derived watches.",
          }, cardActions))
        ),
        h(ContextPanel, {
          items: contextItems,
          onHideContext: function (id) { mutate(request("/context/" + encodeURIComponent(id) + "/hide", { method: "POST" })); },
        }),
        h(Activity, {
          runs: snapshot.refresh_runs || [],
          sourceReport: snapshot.source_report || {},
        })
      ) : null
    );
  }

  window.__HERMES_PLUGINS__.register("hermes-personal-dashboard", PersonalDashboard);
})();
