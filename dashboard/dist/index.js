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
    const res = await fetch(API + path, Object.assign({
      headers: { "Content-Type": "application/json" },
    }, options || {}));
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
      const detail = data.detail || data.error || "Request failed";
      throw new Error(detail);
    }
    return data;
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

  function Activity(props) {
    const runs = props.runs || [];
    return h("section", { className: "hpd-section hpd-activity" },
      h("div", { className: "hpd-section-head" }, h("h2", null, "Hermes Activity")),
      h("div", { className: "hpd-activity-grid" },
        h("div", { className: "hpd-panel" },
          h("h3", null, "Refreshes"),
          runs.length ? runs.slice(0, 10).map(function (run) {
            return h("div", { key: run.id, className: "hpd-run" },
              h("span", { className: cx("hpd-dot", run.status === "error" && "is-error") }),
              h("div", null,
                h("strong", null, run.job_key),
                h("p", null, (run.summary || run.error || run.status) + " - " + freshness(run.started_at))
              )
            );
          }) : h("div", { className: "hpd-empty" }, "No refreshes yet.")
        )
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
          h("p", { className: "hpd-eyebrow" }, "Hermes"),
          h("h1", null, "Personal Dashboard")
        ),
        h("div", { className: "hpd-header-actions" },
          h(Badge, { className: "hpd-badge-pin" }, "Autonomous"),
          h(Button, { variant: "secondary", onClick: load, disabled: loading || mutating }, loading ? "Refreshing" : "Refresh")
        )
      ),
      error ? h("div", { className: "hpd-error" }, error) : null,
      loading && !snapshot ? h("div", { className: "hpd-empty hpd-loading" }, "Reading Hermes memory and session context.") : null,
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
        })
      ) : null
    );
  }

  window.__HERMES_PLUGINS__.register("hermes-personal-dashboard", PersonalDashboard);
})();
