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
    if (["news", "daily", "daycare"].indexOf(card.domain) >= 0) return "today";
    if (["planning", "sports", "events"].indexOf(card.domain) >= 0) return "week";
    return "watching";
  }

  function Field(props) {
    return h("label", { className: "hpd-field" },
      h("span", null, props.label),
      props.children
    );
  }

  function TextInput(props) {
    return h("input", Object.assign({
      className: "hpd-input",
    }, props));
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

  function Activity(props) {
    const runs = props.runs || [];
    const suggestions = props.suggestions || [];
    return h("section", { className: "hpd-section hpd-activity" },
      h("div", { className: "hpd-section-head" }, h("h2", null, "Hermes Activity")),
      h("div", { className: "hpd-activity-grid" },
        h("div", { className: "hpd-panel" },
          h("h3", null, "Refreshes"),
          runs.length ? runs.slice(0, 8).map(function (run) {
            return h("div", { key: run.id, className: "hpd-run" },
              h("span", { className: cx("hpd-dot", run.status === "error" && "is-error") }),
              h("div", null,
                h("strong", null, run.job_key),
                h("p", null, (run.summary || run.error || run.status) + " - " + freshness(run.started_at))
              )
            );
          }) : h("div", { className: "hpd-empty" }, "No refreshes yet.")
        ),
        h("div", { className: "hpd-panel" },
          h("h3", null, "Suggestions"),
          suggestions.length ? suggestions.slice(0, 8).map(function (item) {
            return h("div", { key: item.id, className: "hpd-suggestion" },
              h("div", null,
                h("strong", null, item.title),
                item.summary ? h("p", null, item.summary) : null
              ),
              h("div", { className: "hpd-inline-actions" },
                h(Button, { variant: "ghost", onClick: function () { props.onAcceptSuggestion(item.id); } }, "Accept"),
                h(Button, { variant: "ghost", onClick: function () { props.onDismissSuggestion(item.id); } }, "Dismiss")
              )
            );
          }) : h("div", { className: "hpd-empty" }, "No pending suggestions.")
        )
      )
    );
  }

  function TopicRow(props) {
    const topic = props.topic;
    return h("div", { className: "hpd-topic" },
      h("div", null,
        h("strong", null, topic.label),
        h("p", null, [topic.domain, topic.cadence || "manual", topic.enabled ? "enabled" : "disabled"].join(" - "))
      ),
      h(Button, { variant: "ghost", onClick: function () { props.onDelete(topic.id); } }, "Remove")
    );
  }

  function FirstRunPanel(props) {
    const setup = props.setup || {};
    const hasTopics = (props.topics || []).length > 0;
    const hasCards = (props.cards || []).length > 0;
    const cronJobs = ((props.preferences || {}).cron_jobs) || {};
    const hasJobs = Object.keys(cronJobs).length > 0;
    const items = [
      { label: "Save setup", done: Boolean(setup.configured) },
      { label: "Add topics", done: hasTopics },
      { label: "Create jobs", done: hasJobs },
      { label: "Receive cards", done: hasCards },
    ];
    if (setup.configured && hasTopics && hasJobs && hasCards) return null;
    return h("section", { className: "hpd-start" },
      h("div", { className: "hpd-start-copy" },
        h("p", { className: "hpd-eyebrow" }, "Start here"),
        h("h2", null, "Set up your briefing board"),
        h("div", { className: "hpd-checklist" },
          items.map(function (item) {
            return h("span", { key: item.label, className: cx("hpd-checkitem", item.done && "is-done") },
              h("span", { className: "hpd-checkmark" }, item.done ? "OK" : "-"),
              item.label
            );
          })
        )
      ),
      h("div", { className: "hpd-start-actions" },
        h(Button, { onClick: props.onAddStarterTopics }, "Add starter topics"),
        h(Button, { variant: "secondary", onClick: props.onCreateSampleCards }, "Show sample cards"),
        h(Button, { variant: "secondary", onClick: props.onCreateCron }, "Create jobs")
      )
    );
  }

  function SetupPanel(props) {
    const setup = props.setup || {};
    const prefs = setup.preferences || props.preferences || {};
    const [draft, setDraft] = React.useState({
      briefing_time: prefs.briefing_time || "07:30",
      timezone: prefs.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone || "",
      location: prefs.location || "",
      alert_frequency: prefs.alert_frequency || "hourly",
      calendar_enabled: Boolean(prefs.calendar_enabled),
      weekend_planner: prefs.weekend_planner !== false,
    });
    const [topic, setTopic] = React.useState({ domain: "news", label: "", query: "", cadence: "daily" });

    React.useEffect(function () {
      setDraft({
        briefing_time: prefs.briefing_time || "07:30",
        timezone: prefs.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone || "",
        location: prefs.location || "",
        alert_frequency: prefs.alert_frequency || "hourly",
        calendar_enabled: Boolean(prefs.calendar_enabled),
        weekend_planner: prefs.weekend_planner !== false,
      });
    }, [prefs.briefing_time, prefs.timezone, prefs.location, prefs.alert_frequency, prefs.calendar_enabled, prefs.weekend_planner]);

    function update(key, value) {
      setDraft(Object.assign({}, draft, { [key]: value }));
    }

    function updateTopic(key, value) {
      setTopic(Object.assign({}, topic, { [key]: value }));
    }

    return h("section", { className: "hpd-section hpd-setup" },
      h("div", { className: "hpd-section-head" },
        h("h2", null, "Setup"),
        setup.configured ? h(Badge, { className: "hpd-badge-pin" }, "Configured") : h(Badge, null, "New")
      ),
      h("div", { className: "hpd-setup-grid" },
        h("div", { className: "hpd-panel" },
          h("h3", null, "Briefing"),
          h("div", { className: "hpd-form-grid" },
            h(Field, { label: "Briefing time" }, h(TextInput, {
              value: draft.briefing_time,
              onChange: function (e) { update("briefing_time", e.target.value); },
            })),
            h(Field, { label: "Timezone" }, h(TextInput, {
              value: draft.timezone,
              onChange: function (e) { update("timezone", e.target.value); },
            })),
            h(Field, { label: "Location" }, h(TextInput, {
              value: draft.location,
              onChange: function (e) { update("location", e.target.value); },
            })),
            h(Field, { label: "Alert frequency" },
              h("select", {
                className: "hpd-input",
                value: draft.alert_frequency,
                onChange: function (e) { update("alert_frequency", e.target.value); },
              },
                h("option", { value: "hourly" }, "Hourly"),
                h("option", { value: "30m" }, "Every 30 minutes"),
                h("option", { value: "15m" }, "Every 15 minutes"),
                h("option", { value: "daily" }, "Daily")
              )
            )
          ),
          h("div", { className: "hpd-checks" },
            h("label", null, h("input", {
              type: "checkbox",
              checked: draft.calendar_enabled,
              onChange: function (e) { update("calendar_enabled", e.target.checked); },
            }), " Calendar"),
            h("label", null, h("input", {
              type: "checkbox",
              checked: draft.weekend_planner,
              onChange: function (e) { update("weekend_planner", e.target.checked); },
            }), " Weekend planner")
          ),
          h("div", { className: "hpd-inline-actions" },
            h(Button, { onClick: function () { props.onSaveSetup(draft); } }, "Save setup"),
            h(Button, { variant: "secondary", onClick: props.onCreateCron }, "Create jobs")
          )
        ),
        h("div", { className: "hpd-panel" },
          h("h3", null, "Topics"),
          h("div", { className: "hpd-form-grid" },
            h(Field, { label: "Domain" }, h(TextInput, {
              value: topic.domain,
              onChange: function (e) { updateTopic("domain", e.target.value); },
            })),
            h(Field, { label: "Label" }, h(TextInput, {
              value: topic.label,
              onChange: function (e) { updateTopic("label", e.target.value); },
            })),
            h(Field, { label: "Query" }, h(TextInput, {
              value: topic.query,
              onChange: function (e) { updateTopic("query", e.target.value); },
            })),
            h(Field, { label: "Cadence" }, h(TextInput, {
              value: topic.cadence,
              onChange: function (e) { updateTopic("cadence", e.target.value); },
            }))
          ),
          h("div", { className: "hpd-inline-actions" },
            h(Button, { onClick: function () { props.onAddTopic(topic); setTopic({ domain: "news", label: "", query: "", cadence: "daily" }); } }, "Add topic"),
            h(Button, { variant: "secondary", onClick: props.onAddStarterTopics }, "Starter topics"),
            h(Button, { variant: "secondary", onClick: props.onDiscover }, "Discover"),
            h(Button, { variant: "secondary", onClick: props.onCreateSampleCards }, "Sample cards")
          ),
          h("div", { className: "hpd-topic-list" },
            (props.topics || []).length
              ? props.topics.map(function (item) {
                  return h(TopicRow, { key: item.id, topic: item, onDelete: props.onDeleteTopic });
                })
              : h("div", { className: "hpd-empty" }, "No topics configured.")
          )
        )
      )
    );
  }

  function PersonalDashboard() {
    const [snapshot, setSnapshot] = React.useState(null);
    const [loading, setLoading] = React.useState(true);
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
      return promise.then(load).catch(function (err) { setError(err.message || String(err)); });
    }

    const cards = snapshot ? (snapshot.cards || []) : [];
    const grouped = { now: [], today: [], week: [], watching: [] };
    cards.forEach(function (card) {
      const key = sectionFor(card);
      if (grouped[key]) grouped[key].push(card);
      else grouped.watching.push(card);
    });

    return h("main", { className: "hpd-root" },
      h("header", { className: "hpd-header" },
        h("div", null,
          h("p", { className: "hpd-eyebrow" }, "Hermes"),
          h("h1", null, "Personal Dashboard")
        ),
        h("div", { className: "hpd-header-actions" },
          snapshot && snapshot.setup && snapshot.setup.configured ? h(Badge, { className: "hpd-badge-pin" }, "Configured") : h(Badge, null, "Setup needed"),
          h(Button, { variant: "secondary", onClick: load, disabled: loading }, loading ? "Refreshing" : "Refresh")
        )
      ),
      error ? h("div", { className: "hpd-error" }, error) : null,
      loading && !snapshot ? h("div", { className: "hpd-empty hpd-loading" }, "Loading dashboard.") : null,
      snapshot ? h(React.Fragment, null,
        h(FirstRunPanel, {
          setup: snapshot.setup,
          topics: snapshot.topics || [],
          cards: cards,
          preferences: snapshot.preferences || {},
          onAddStarterTopics: function () { mutate(request("/setup/starter-topics", { method: "POST" })); },
          onCreateSampleCards: function () { mutate(request("/setup/sample-cards", { method: "POST" })); },
          onCreateCron: function () { mutate(request("/setup/create-cron-jobs", { method: "POST", body: JSON.stringify({}) })); },
        }),
        h("div", { className: "hpd-sections" },
          h(CardSection, {
            title: "Now",
            cards: grouped.now,
            empty: "No urgent cards.",
            onDismiss: function (id) { mutate(request("/cards/" + encodeURIComponent(id) + "/dismiss", { method: "POST" })); },
            onPin: function (id) { mutate(request("/cards/" + encodeURIComponent(id) + "/pin", { method: "POST" })); },
            onUnpin: function (id) { mutate(request("/cards/" + encodeURIComponent(id) + "/unpin", { method: "POST" })); },
          }),
          h(CardSection, {
            title: "Today",
            cards: grouped.today,
            empty: "No cards for today.",
            onDismiss: function (id) { mutate(request("/cards/" + encodeURIComponent(id) + "/dismiss", { method: "POST" })); },
            onPin: function (id) { mutate(request("/cards/" + encodeURIComponent(id) + "/pin", { method: "POST" })); },
            onUnpin: function (id) { mutate(request("/cards/" + encodeURIComponent(id) + "/unpin", { method: "POST" })); },
          }),
          h(CardSection, {
            title: "This Week",
            cards: grouped.week,
            empty: "No weekly cards.",
            onDismiss: function (id) { mutate(request("/cards/" + encodeURIComponent(id) + "/dismiss", { method: "POST" })); },
            onPin: function (id) { mutate(request("/cards/" + encodeURIComponent(id) + "/pin", { method: "POST" })); },
            onUnpin: function (id) { mutate(request("/cards/" + encodeURIComponent(id) + "/unpin", { method: "POST" })); },
          }),
          h(CardSection, {
            title: "Watching",
            cards: grouped.watching,
            empty: "No watched-topic cards.",
            onDismiss: function (id) { mutate(request("/cards/" + encodeURIComponent(id) + "/dismiss", { method: "POST" })); },
            onPin: function (id) { mutate(request("/cards/" + encodeURIComponent(id) + "/pin", { method: "POST" })); },
            onUnpin: function (id) { mutate(request("/cards/" + encodeURIComponent(id) + "/unpin", { method: "POST" })); },
          })
        ),
        h(Activity, {
          runs: snapshot.refresh_runs || [],
          suggestions: snapshot.suggestions || [],
          onAcceptSuggestion: function (id) { mutate(request("/suggestions/" + encodeURIComponent(id) + "/accept", { method: "POST" })); },
          onDismissSuggestion: function (id) { mutate(request("/suggestions/" + encodeURIComponent(id) + "/dismiss", { method: "POST" })); },
        }),
        h(SetupPanel, {
          setup: snapshot.setup,
          preferences: snapshot.preferences || {},
          topics: snapshot.topics || [],
          onSaveSetup: function (draft) { mutate(request("/setup/save", { method: "POST", body: JSON.stringify(draft) })); },
          onCreateCron: function () { mutate(request("/setup/create-cron-jobs", { method: "POST", body: JSON.stringify({}) })); },
          onAddStarterTopics: function () { mutate(request("/setup/starter-topics", { method: "POST" })); },
          onCreateSampleCards: function () { mutate(request("/setup/sample-cards", { method: "POST" })); },
          onDiscover: function () { mutate(request("/suggestions/discover", { method: "POST" })); },
          onAddTopic: function (topic) {
            if (!topic.label.trim()) {
              setError("Topic label is required.");
              return;
            }
            mutate(request("/topics", { method: "POST", body: JSON.stringify(topic) }));
          },
          onDeleteTopic: function (id) { mutate(request("/topics/" + encodeURIComponent(id), { method: "DELETE" })); },
        })
      ) : null
    );
  }

  window.__HERMES_PLUGINS__.register("hermes-personal-dashboard", PersonalDashboard);
})();
