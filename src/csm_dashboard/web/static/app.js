(function () {
  "use strict";

  var status = { version: "", accounts: [] };
  var currentAccount = null;
  var currentTab = "timeline";
  var homeChatId = "";
  var chatScope = "";
  var chatBookmarked = false;
  var chatMentionHi = 0;
  var chatMentionItems = [];
  var chatMentionToken = null;
  var chatMentionGen = 0;
  var chatBooksList = null;
  var chatPeopleAll = null;
  var chatPeopleByBook = {};
  var chatTicketsByBook = {};
  var pendingComposeSeed = null;
  var accountQ = "";
  var accountProject = "";
  var lastAccountAbbr = "";
  var accountProjects = [];
  var searchTimer = null;
  var slashIndex = 0;
  var personSuggestGen = 0;
  var notesDirty = false;
  var homeTab = "agenda";
  var agendaDay = "";
  var agendaCalView = "day";
  var agendaMeetings = [];
  var agendaInboxFilter = { kinds: [], audience: [], from: "", when: "any", fromDay: "", toDay: "" };
  var agendaInboxItems = [];
  var agendaProjFilter = "";
  var agendaProjOptions = [];
  var agendaProjBound = false;
  var agendaProjProbe = null;
  var peopleAllProjects = false;
  var operatorTz = "UTC";
  var deskClockTimer = 0;
  var deskClockFmts = { tz: "", hour24: null, time: null, date: null, zone: null };
  var themeMql = null;
  var prefSave = Promise.resolve();
  var TL_SIDE_CAP = 40;
  var WEEKDAY_SHORT = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  var homeItems = null;
  var helpReady = false;
  var helpFuse = null;
  var pickedConnector = "";
  var aiTestOk = {};
  var connTestOk = {};
  var AI_PROVIDERS = [
    { id: "grok", label: "xAI / Grok", key: "xai" },
    { id: "openai", label: "OpenAI", key: "openai" },
    { id: "gemini", label: "Gemini", key: "gemini" },
  ];
  var CONN_LABELS = {
    smtp_imap: "IMAP",
    google_mail: "Gmail",
    microsoft365: "Microsoft 365",
    jira: "Jira",
    slack: "Slack",
    teams: "Teams",
    salesforce: "Salesforce",
    google_cal: "Google Calendar",
    m365_cal: "M365 Calendar",
  };
  var FEED_NAMES = ["smtp_imap", "google_mail", "microsoft365", "jira", "slack", "teams", "salesforce", "google_cal", "m365_cal"];
  var TZ_FALLBACK = [
    "UTC",
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Los_Angeles",
    "America/Anchorage",
    "Pacific/Honolulu",
    "America/Toronto",
    "America/Vancouver",
    "America/Mexico_City",
    "America/Sao_Paulo",
    "Europe/London",
    "Europe/Paris",
    "Europe/Berlin",
    "Europe/Amsterdam",
    "Europe/Madrid",
    "Europe/Rome",
    "Europe/Zurich",
    "Africa/Johannesburg",
    "Asia/Dubai",
    "Asia/Kolkata",
    "Asia/Singapore",
    "Asia/Hong_Kong",
    "Asia/Shanghai",
    "Asia/Tokyo",
    "Asia/Seoul",
    "Australia/Sydney",
    "Pacific/Auckland",
  ];
  var SLASH = [
    { cmd: "note", tab: "timeline", note: true, label: "Notes on events", example: "/note call Pat" },
    { cmd: "project", tab: "projects", note: false, label: "Projects", example: "/project all" },
    { cmd: "people", tab: "people", note: false, label: "People", example: "/people bob" },
    { cmd: "email", tab: "email", note: false, label: "Email", example: "/email outage" },
    { cmd: "ticket", tab: "tickets", note: false, label: "Tickets", example: "/ticket ACME-12" },
    { cmd: "chat", tab: "chat", note: false, label: "Slack / Teams", example: "/chat DC3" },
    { cmd: "slack", tab: "chat", note: false, label: "Slack", example: "/slack pin" },
    { cmd: "teams", tab: "chat", note: false, label: "Teams", example: "/teams Bob" },
    { cmd: "calendar", tab: "calendar", note: false, label: "Meetings", example: "/calendar QBR" },
    { cmd: "sf", tab: "salesforce", note: false, label: "Salesforce", example: "/sf renewal" },
  ];
  var PERSON_FUNCS = ["Ops", "Accounting", "DBA"];
  var PROJECT_KINDS = [
    ["implementation", "Implementation"],
    ["qbr", "QBR"],
    ["training", "Training"],
    ["migration", "Migration"],
    ["other", "Other"],
  ];
  var PROJECT_STATUSES = [
    ["planned", "Planned"],
    ["active", "Active"],
    ["blocked", "Blocked"],
    ["done", "Done"],
    ["cancelled", "Cancelled"],
  ];
  var HIDDEN_TABS = { actions: true, reports: true };
  var ACCOUNT_TABS = ["timeline", "tickets", "email", "chat", "salesforce", "calendar", "projects", "people", "orgchart", "accountteam"];
  var TAB_ALIASES = { slack: "chat", teams: "chat" };

  function tabLabel(name) {
    if (name === "orgchart") return "org chart";
    if (name === "accountteam") return "account team";
    if (name === "chat") return "slack / teams";
    return name;
  }

  function canonicalTab(tab) {
    tab = String(tab || "timeline").toLowerCase();
    if (TAB_ALIASES[tab]) tab = TAB_ALIASES[tab];
    if (ACCOUNT_TABS.indexOf(tab) < 0) return "timeline";
    return tab;
  }

  function $(id) {
    if (!id) return null;
    return document.getElementById(id);
  }

  function api(path, opts) {
    opts = opts || {};
    var headers = Object.assign({ "Content-Type": "application/json" }, opts.headers || {});
    return fetch(path, Object.assign({}, opts, { headers: headers })).then(function (res) {
      return res.text().then(function (text) {
        var data = text ? JSON.parse(text) : {};
        if (!res.ok) {
          var err = new Error((data && data.detail) || res.statusText);
          err.status = res.status;
          throw err;
        }
        return data;
      });
    });
  }

  function toast(msg) {
    var box = $("toasts");
    if (!box) return;
    var el = document.createElement("div");
    el.className = "toast";
    el.textContent = msg;
    box.appendChild(el);
    setTimeout(function () {
      el.remove();
    }, 4500);
  }

  function explainMailError(err) {
    var raw = String((err && err.message) || err || "").trim();
    if (raw.indexOf("{") === 0) {
      try {
        var parsed = JSON.parse(raw);
        raw = String(parsed.detail || parsed.message || raw);
      } catch (e) {}
    }
    var map = {
      google_send_reconnect: "Google can read mail but cannot Send. Sign in with Google again and allow sending.",
      google_draft_reconnect: "Sign in with Google again to save this into Gmail Drafts.",
      send_not_configured: "Mail send is not set up. Sign in with Google (allow Send) or add SMTP in Settings.",
      operator_email_required: "Add your email under Settings → You first.",
      "to_addrs required": "Add at least one To address.",
      send_failed: "Send failed. Try again.",
    };
    return map[raw] || raw;
  }

  function accountChip(acct) {
    var el = document.createElement("span");
    el.className = "acct-chip";
    var sw = document.createElement("i");
    sw.className = "acct-swatch";
    sw.style.background = (acct && acct.color) || "#0B3D91";
    var ab = document.createElement("b");
    ab.className = "acct-abbr";
    ab.textContent = (acct && acct.abbr) || "?";
    el.appendChild(sw);
    el.appendChild(ab);
    el.title = (acct && acct.name) || "";
    return el;
  }

  function logoSrc(acct) {
    if (!acct || !acct.account_id || !acct.has_logo) return "";
    return "/api/accounts/" + encodeURIComponent(acct.account_id) + "/logo?t=" + encodeURIComponent(acct.logo_updated_at || "1");
  }

  function accountMark(acct, size) {
    var src = logoSrc(acct);
    if (!src) return accountChip(acct);
    var img = document.createElement("img");
    img.className = "acct-logo" + (size === "tile" ? " acct-logo-tile" : size === "lg" ? " acct-logo-lg" : size === "inbox" ? " acct-logo-inbox" : "");
    img.src = src;
    img.alt = (acct && acct.name) || "";
    img.title = (acct && acct.name) || "";
    img.addEventListener("error", function () {
      var chip = accountChip(acct);
      if (img.parentNode) img.parentNode.replaceChild(chip, img);
    });
    return img;
  }

  function kindIcon(kind, size) {
    var wrap = document.createElement("span");
    wrap.className = "kind-icon is-" + (kind || "email") + (size === "lg" ? " is-lg" : "");
    var img = document.createElement("img");
    var src = "/static/icon-email.svg";
    var label = "Email";
    if (kind === "slack") {
      src = "/static/icon-slack.svg";
      label = "Slack";
    } else if (kind === "teams") {
      src = "/static/icon-teams.svg";
      label = "Teams";
    } else if (kind === "task") {
      src = "/static/icon-task.svg";
      label = "Task";
    }
    img.src = src + (status && status.version ? "?v=" + status.version : "");
    img.alt = "";
    wrap.title = label;
    wrap.setAttribute("aria-label", label);
    wrap.appendChild(img);
    return wrap;
  }

  function healthPill(health) {
    health = health || {};
    var el = document.createElement("span");
    var st = health.status || "watch";
    el.className = "health-pill " + st;
    el.textContent = st.replace("_", " ") + " " + (health.score == null ? "" : health.score);
    return el;
  }

  function empty(node) {
    if (node) node.textContent = "";
  }

  var _searchSelectOpen = null;
  var _searchSelectBound = false;

  function closeSearchSelect(inst) {
    if (!inst) inst = _searchSelectOpen;
    if (!inst || !inst.menu) return;
    inst.menu.hidden = true;
    inst.menu.classList.add("hidden");
    if (_searchSelectOpen === inst) _searchSelectOpen = null;
  }

  function ensureSearchSelectDoc() {
    if (_searchSelectBound) return;
    _searchSelectBound = true;
    document.addEventListener("click", function (ev) {
      if (!_searchSelectOpen) return;
      if (_searchSelectOpen.wrap && _searchSelectOpen.wrap.contains(ev.target)) return;
      if (_searchSelectOpen.menu && _searchSelectOpen.menu.contains(ev.target)) return;
      closeSearchSelect();
    });
    window.addEventListener("resize", function () {
      if (_searchSelectOpen && _searchSelectOpen.place) _searchSelectOpen.place();
    });
    window.addEventListener("scroll", function () {
      if (_searchSelectOpen && _searchSelectOpen.place) _searchSelectOpen.place();
    }, true);
  }

  function mountSearchSelect(opts) {
    opts = opts || {};
    ensureSearchSelectDoc();
    var items = (opts.items || []).slice();
    var multiple = !!opts.multiple;
    var allowCustom = !!opts.allowCustom;
    var trigger = opts.trigger === "input" ? "input" : "button";
    var selected = multiple ? (opts.value ? opts.value.slice() : []) : (opts.value || "");
    var query = "";
    var hi = -1;
    var shown = [];
    var wrap = document.createElement("div");
    wrap.className = "search-select" + (trigger === "input" ? " is-input" : "") + (opts.wrapClass ? " " + opts.wrapClass : "");
    var btn;
    if (trigger === "input") {
      btn = document.createElement("input");
      btn.type = "search";
      btn.className = "search search-select-input" + (opts.btnClass ? " " + opts.btnClass : "");
      btn.placeholder = opts.placeholder || "";
      btn.setAttribute("autocomplete", "off");
    } else {
      btn = document.createElement("button");
      btn.type = "button";
      btn.className = "toolbar-filter search-select-btn" + (opts.btnClass ? " " + opts.btnClass : "");
    }
    if (opts.ariaLabel) btn.setAttribute("aria-label", opts.ariaLabel);
    btn.setAttribute("aria-haspopup", "listbox");
    var menu = document.createElement("div");
    menu.className = "search-select-menu hidden";
    menu.hidden = true;
    var search = null;
    if (trigger !== "input") {
      search = document.createElement("input");
      search.type = "search";
      search.className = "search";
      search.placeholder = opts.searchPlaceholder || opts.placeholder || "Search";
      search.setAttribute("aria-label", opts.searchPlaceholder || "Search");
      search.setAttribute("autocomplete", "off");
      menu.appendChild(search);
    }
    var list = document.createElement("div");
    list.className = "search-select-list";
    list.setAttribute("role", "listbox");
    menu.appendChild(list);
    wrap.appendChild(btn);
    document.body.appendChild(menu);

    function labelFor(value) {
      if (value === "" && opts.emptyLabel) return opts.emptyLabel;
      var hit = items.filter(function (it) { return String(it.value) === String(value); })[0];
      return (hit && (hit.label || hit.value)) || String(value || "");
    }
    function hay(it) {
      return String((it && (it.search || it.label || it.value)) || "").toLowerCase();
    }
    function isOn(value) {
      if (multiple) return selected.indexOf(value) >= 0;
      return String(selected) === String(value);
    }
    function buttonText() {
      if (multiple) {
        if (!selected.length) return opts.placeholder || opts.emptyLabel || "Select";
        if (selected.length === 1) return labelFor(selected[0]);
        return selected.length + " selected";
      }
      if (selected === "" || selected == null) return opts.placeholder || opts.emptyLabel || "Select";
      return labelFor(selected);
    }
    function paintBtn() {
      if (trigger === "input") {
        if (document.activeElement !== btn) {
          btn.value = multiple ? (selected.length ? buttonText() : "") : (selected ? labelFor(selected) : query);
          if (allowCustom && !multiple && selected) btn.value = labelFor(selected);
        }
        return;
      }
      btn.textContent = buttonText();
      btn.title = multiple ? selected.map(labelFor).join(", ") : buttonText();
    }
    function place() {
      if (menu.hidden) return;
      var cap = Math.min(window.innerWidth - 16, 42 * 16);
      var w = Math.min(cap, Math.max(opts.minWidth || 16 * 16, wrap.getBoundingClientRect().width || 16 * 16));
      var r = wrap.getBoundingClientRect();
      var top = r.bottom + 4;
      var left = r.left;
      if (opts.align === "right") left = r.right - w;
      if (left < 8) left = 8;
      if (left + w > window.innerWidth - 8) left = Math.max(8, window.innerWidth - 8 - w);
      var maxH = Math.min(18 * 16, window.innerHeight - top - 12);
      if (maxH < 8 * 16 && r.top > window.innerHeight / 2) {
        maxH = Math.min(18 * 16, r.top - 16);
        top = Math.max(8, r.top - 4 - maxH);
      }
      menu.style.top = top + "px";
      menu.style.left = left + "px";
      menu.style.width = w + "px";
      list.style.maxHeight = Math.max(6 * 16, maxH - (search ? 48 : 12)) + "px";
    }
    function emit() {
      if (opts.onChange) opts.onChange(multiple ? selected.slice() : selected, query);
    }
    function choose(value) {
      if (multiple) {
        var i = selected.indexOf(value);
        if (i >= 0) selected.splice(i, 1);
        else selected.push(value);
        paintBtn();
        paintList();
        emit();
        return;
      }
      selected = value;
      query = "";
      if (trigger === "input") btn.value = labelFor(value);
      paintBtn();
      closeSearchSelect(api);
      emit();
    }
    function paintList() {
      empty(list);
      var q = (trigger === "input" ? String(btn.value || "") : query).toLowerCase().trim();
      shown = [];
      if (!q && opts.emptyLabel && !multiple) {
        shown.push({ value: "", label: opts.emptyLabel, search: opts.emptyLabel });
      }
      var cap = opts.maxShown || 80;
      var pin = opts.pinValues || [];
      items.forEach(function (it) {
        if (q && hay(it).indexOf(q) < 0) return;
        if (!q && it.value === "" && opts.emptyLabel) return;
        if (!q && pin.length && it.value && pin.indexOf(it.value) < 0 && !isOn(it.value)) return;
        shown.push(it);
      });
      if (shown.length > cap) shown = shown.slice(0, cap);
      if (allowCustom && q) {
        var exists = shown.some(function (it) {
          return String(it.label || it.value).toLowerCase() === q;
        });
        if (!exists) shown.unshift({ value: trigger === "input" ? btn.value.trim() : q, label: "Use “" + (trigger === "input" ? btn.value.trim() : q) + "”", search: q, custom: true });
      }
      if (hi >= shown.length) hi = shown.length - 1;
      shown.forEach(function (it, idx) {
        var b = document.createElement("button");
        b.type = "button";
        b.className = "search-select-opt" + (isOn(it.value) ? " is-on" : "") + (idx === hi ? " is-hi" : "");
        b.textContent = it.label || it.value;
        b.title = it.label || it.value;
        b.addEventListener("mousedown", function (ev) { ev.preventDefault(); });
        b.addEventListener("click", function () { choose(it.custom ? it.value : it.value); });
        list.appendChild(b);
      });
      if (!list.firstChild) {
        var p = document.createElement("p");
        p.className = "muted";
        p.textContent = allowCustom ? "Type to add, or pick a match." : "No match.";
        list.appendChild(p);
      }
      place();
    }
    function open() {
      if (_searchSelectOpen && _searchSelectOpen !== api) closeSearchSelect(_searchSelectOpen);
      if (search) search.value = "";
      query = "";
      hi = -1;
      menu.hidden = false;
      menu.classList.remove("hidden");
      _searchSelectOpen = api;
      paintList();
      place();
      var focusEl = search || (trigger === "input" ? btn : search);
      if (focusEl) focusEl.focus();
    }
    function onQuery(ev) {
      query = (search && search.value) || (trigger === "input" ? btn.value : "") || "";
      hi = 0;
      paintList();
      if (opts.onQuery) opts.onQuery(query);
      if (ev && ev.type === "input" && trigger === "input" && allowCustom && !multiple) {
        selected = btn.value;
      }
    }
    function onKey(ev) {
      if (ev.key === "Escape") {
        ev.preventDefault();
        closeSearchSelect(api);
        btn.focus();
        return;
      }
      if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
        ev.preventDefault();
        if (menu.hidden) {
          open();
          return;
        }
        if (!shown.length) return;
        if (ev.key === "ArrowDown") hi = hi < 0 ? 0 : (hi + 1) % shown.length;
        else hi = hi <= 0 ? shown.length - 1 : hi - 1;
        paintList();
        var hit = list.querySelector(".is-hi");
        if (hit && hit.scrollIntoView) hit.scrollIntoView({ block: "nearest" });
        return;
      }
      if (ev.key === "Enter") {
        if (menu.hidden) return;
        ev.preventDefault();
        if (hi >= 0 && shown[hi]) choose(shown[hi].value);
        else if (allowCustom && (trigger === "input" ? btn.value.trim() : query)) {
          choose(trigger === "input" ? btn.value.trim() : query);
        }
      }
    }
    btn.addEventListener("click", function (ev) {
      ev.stopPropagation();
      if (trigger === "button") {
        if (!menu.hidden && _searchSelectOpen === api) {
          closeSearchSelect(api);
          return;
        }
        open();
      }
    });
    btn.addEventListener("focus", function () {
      if (trigger === "input") open();
    });
    btn.addEventListener("input", onQuery);
    btn.addEventListener("keydown", onKey);
    if (search) {
      search.addEventListener("input", onQuery);
      search.addEventListener("keydown", onKey);
    }
    paintBtn();
    var api = {
      wrap: wrap,
      menu: menu,
      el: wrap,
      place: place,
      get: function () {
        return multiple ? selected.slice() : selected;
      },
      set: function (value) {
        selected = multiple ? (value ? value.slice() : []) : (value || "");
        query = "";
        paintBtn();
        if (!menu.hidden) paintList();
      },
      setItems: function (next) {
        items = (next || []).slice();
        if (!menu.hidden) paintList();
        paintBtn();
      },
      destroy: function () {
        closeSearchSelect(api);
        if (menu.parentNode) menu.parentNode.removeChild(menu);
      },
    };
    return api;
  }

  function showView(name) {
    document.querySelectorAll(".view").forEach(function (v) {
      v.classList.toggle("is-on", v.getAttribute("data-view") === name);
    });
    document.querySelectorAll(".nav-item").forEach(function (a) {
      a.classList.toggle("is-on", a.getAttribute("data-nav") === name);
    });
  }

  function hashParts() {
    var raw = (location.hash || "#home").replace(/^#/, "");
    return raw.split("/").filter(Boolean);
  }

  function hashItemId(parts) {
    parts = parts || hashParts();
    for (var i = 0; i < parts.length; i++) {
      if (parts[i].slice(0, 3) === "id=") {
        try {
          return decodeURIComponent(parts[i].slice(3));
        } catch (err) {
          return parts[i].slice(3);
        }
      }
    }
    return "";
  }

  function accountItemHash(abbr, tab, id) {
    var base = "#account/" + (abbr || "") + "/" + (tab || "timeline");
    if (!id) return base;
    return base + "/id=" + String(id).replace(/\//g, "%2F");
  }

  function goAccountItem(abbr, tab, id) {
    var next = accountItemHash(abbr, tab, id);
    var sameBook = currentAccount && (currentAccount.abbr || "").toLowerCase() === String(abbr || "").toLowerCase();
    if (sameBook && currentTab === tab && location.hash === next) {
      openRoutedItem(tab, id);
      return;
    }
    if (sameBook && currentTab === tab) {
      if (history.replaceState) history.replaceState(null, "", next);
      else location.hash = next;
      openRoutedItem(tab, id);
      return;
    }
    location.hash = next;
  }

  function route() {
    closeDetail();
    closeTaskForm();
    var parts = hashParts();
    var head = (parts[0] || "home").toLowerCase();
    if (head === "account" && parts[1]) {
      showView("home");
      var tab = (parts[2] || "timeline").toLowerCase();
      var itemId = hashItemId(parts);
      var openHint = tab;
      if (tab.slice(0, 3) === "id=") tab = "timeline";
      if (HIDDEN_TABS[tab]) tab = "timeline";
      currentTab = canonicalTab(tab);
      setHomeMode(true);
      loadAccount(parts[1], currentTab).then(function () {
        syncChatScope(currentAccount && currentAccount.account_id);
        if (itemId) openRoutedItem(openHint === "slack" || openHint === "teams" ? openHint : currentTab, itemId);
      });
      return;
    }
    if (head === "compose" && parts[1]) {
      showView("home");
      setHomeMode(true);
      var openCompose = function () {
        syncChatScope(currentAccount && currentAccount.account_id);
        var seed = pendingComposeSeed || {};
        pendingComposeSeed = null;
        if (window.CSMCompose) window.CSMCompose.open(currentAccount, seed);
      };
      if (currentAccount && (currentAccount.abbr || "").toLowerCase() === parts[1].toLowerCase()) {
        openCompose();
        return;
      }
      loadAccount(parts[1], "email").then(openCompose);
      return;
    }
    if (HIDDEN_TABS[head]) {
      location.hash = "#home";
      return;
    }
    if (["help", "settings"].indexOf(head) >= 0) {
      showView(head);
      if (head === "help") loadHelp(parts[1] || "");
      if (head === "settings") loadSettings();
      return;
    }
    showView("home");
    currentAccount = null;
    lastAccountAbbr = "";
    setHomeMode(false);
    homeTab = (parts[1] || "agenda").toLowerCase();
    if (homeTab !== "companies") homeTab = "agenda";
    showHomeTab(homeTab);
    syncChatScope("desk");
  }

  function setHomeMode(accountOn) {
    var home = $("view-home");
    if (home) home.classList.toggle("is-account", !!accountOn);
    var board = $("acct-board");
    var homeDesk = $("home-desk");
    var desk = $("view-account");
    var head = $("home-head");
    if (homeDesk) {
      homeDesk.hidden = !!accountOn;
      homeDesk.classList.toggle("hidden", !!accountOn);
    }
    if (board && accountOn) {
      board.hidden = true;
      board.classList.add("hidden");
    }
    if (desk) {
      desk.hidden = !accountOn;
      desk.classList.toggle("hidden", !accountOn);
      if (!accountOn) {
        empty($("account-head"));
        empty($("account-tabs"));
        empty($("account-pane"));
      }
    }
    if (head) {
      head.hidden = !!accountOn;
      head.classList.toggle("hidden", !!accountOn);
    }
    if (!accountOn) renderHomeCrumb(null);
  }

  function refreshStatus() {
    return api("/api/status").then(function (s) {
      status = s;
      var badge = $("app-version");
      if (badge) {
        badge.textContent = "v" + (s.version || "");
        badge.title = "Listening on " + (s.host || "127.0.0.1") + ":" + (s.public_port || s.port || 8788);
      }
      var tag = $("home-tagline");
      if (tag) tag.textContent = s.tagline || "";
      operatorTz = (s.operator && s.operator.timezone) || "UTC";
      tickDeskClock();
      applyTheme();
      fillPreferencesForm();
      return s;
    });
  }

  function browserTimezone() {
    try {
      return (Intl.DateTimeFormat().resolvedOptions().timeZone || "").trim();
    } catch (e) {
      return "";
    }
  }

  var timezoneList = null;
  function timezoneOptions() {
    if (timezoneList && timezoneList.length) return timezoneList;
    var zones = [];
    try {
      if (typeof Intl !== "undefined" && typeof Intl.supportedValuesOf === "function") {
        zones = Intl.supportedValuesOf("timeZone") || [];
      }
    } catch (e) {
      zones = [];
    }
    if (!zones.length) zones = TZ_FALLBACK.slice();
    timezoneList = zones;
    return timezoneList;
  }

  function fillTimezoneSelect(selected) {
    var hidden = $("op-timezone");
    var host = $("op-timezone-picker");
    var wanted = (selected || "").trim() || "UTC";
    if (hidden) hidden.value = wanted;
    if (!host) return;
    var zones = timezoneOptions();
    if (zones.indexOf("UTC") < 0) zones = ["UTC"].concat(zones);
    if (wanted && zones.indexOf(wanted) < 0) zones = [wanted].concat(zones);
    var items = zones.map(function (z) {
      var parts = String(z).split("/");
      var city = (parts[parts.length - 1] || z).replace(/_/g, " ");
      var region = parts.length > 1 ? parts.slice(0, -1).join(" / ").replace(/_/g, " ") : "";
      var label = region ? city + " · " + region : city;
      return { value: z, label: label, search: (label + " " + z + " " + city).toLowerCase() };
    });
    if (host._picker) {
      host._picker.setItems(items);
      host._picker.set(wanted);
      return;
    }
    host._picker = mountSearchSelect({
      placeholder: "Timezone",
      searchPlaceholder: "Search city or timezone",
      ariaLabel: "Timezone",
      items: items,
      value: wanted,
      pinValues: TZ_FALLBACK.concat([wanted]),
      maxShown: 60,
      minWidth: 22 * 16,
      btnClass: "search-select-btn-block",
      onChange: function (v) {
        if (hidden) hidden.value = v;
      },
    });
    host.appendChild(host._picker.el);
  }

  function ymdInZone(d, tz) {
    try {
      return new Intl.DateTimeFormat("en-CA", {
        timeZone: tz || "UTC",
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
      }).format(d || new Date());
    } catch (e) {
      return utcYmd(d);
    }
  }

  function todayYmd() {
    return ymdInZone(new Date(), operatorTz);
  }

  function utcYmd(d) {
    var dt = d || new Date();
    var m = dt.getUTCMonth() + 1;
    var day = dt.getUTCDate();
    return dt.getUTCFullYear() + "-" + (m < 10 ? "0" : "") + m + "-" + (day < 10 ? "0" : "") + day;
  }

  function shiftYmd(ymd, delta) {
    var p = String(ymd || utcYmd()).split("-");
    var dt = new Date(Date.UTC(+p[0], +p[1] - 1, +p[2] + delta));
    return utcYmd(dt);
  }

  function formatDayLabel(ymd) {
    var p = String(ymd || "").split("-");
    if (p.length !== 3) return ymd;
    var dt = new Date(Date.UTC(+p[0], +p[1] - 1, +p[2]));
    return dt.toLocaleDateString(undefined, {
      weekday: "long",
      month: "short",
      day: "numeric",
      year: "numeric",
      timeZone: "UTC",
    });
  }

  function userPrefs() {
    var p = (status && status.preferences) || {};
    var start = +p.week_start;
    if (!(start >= 0 && start <= 6)) start = 0;
    var hidden = [];
    if (Array.isArray(p.hidden_weekdays)) {
      p.hidden_weekdays.forEach(function (d) {
        var n = +d;
        if (n >= 0 && n <= 6 && hidden.indexOf(n) < 0) hidden.push(n);
      });
    }
    var theme = p.theme === "day" || p.theme === "night" || p.theme === "auto" ? p.theme : "auto";
    var layout = p.timeline_layout === "horizontal" ? "horizontal" : "vertical";
    var pastDays = +p.timeline_past_days === 30 ? 30 : 7;
    var nextDays = +p.timeline_next_days === 30 ? 30 : 7;
    return {
      week_start: start,
      hidden_weekdays: hidden,
      theme: theme,
      timeline_layout: layout,
      timeline_past_days: pastDays,
      timeline_next_days: nextDays,
    };
  }

  function timelineLayout() {
    return userPrefs().timeline_layout === "horizontal" ? "horizontal" : "vertical";
  }

  function ymdWeekday(ymd) {
    var parts = String(ymd || "").split("-");
    return new Date(Date.UTC(+parts[0], +parts[1] - 1, +parts[2])).getUTCDay();
  }

  function visibleWeekdays() {
    var hidden = {};
    userPrefs().hidden_weekdays.forEach(function (d) {
      hidden[d] = true;
    });
    var start = userPrefs().week_start;
    var out = [];
    var i;
    for (i = 0; i < 7; i++) {
      var d = (start + i) % 7;
      if (!hidden[d]) out.push(d);
    }
    if (!out.length) {
      for (i = 0; i < 7; i++) out.push((start + i) % 7);
    }
    return out;
  }

  function weekDaysFrom(ymd) {
    var start = weekStartYmd(ymd);
    var vis = visibleWeekdays();
    var days = [];
    var i;
    for (i = 0; i < 7; i++) {
      var d = shiftYmd(start, i);
      if (vis.indexOf(ymdWeekday(d)) >= 0) days.push(d);
    }
    return days.length ? days : [start];
  }

  function weekStartYmd(ymd) {
    var p = String(ymd || "").split("-");
    var dt = new Date(Date.UTC(+p[0], +p[1] - 1, +p[2]));
    var dow = dt.getUTCDay();
    var start = userPrefs().week_start;
    var delta = (dow - start + 7) % 7;
    return shiftYmd(ymd, -delta);
  }

  function resolvedTheme(pref) {
    var t = pref || userPrefs().theme;
    if (t === "night" || t === "day") return t;
    try {
      return window.matchMedia("(prefers-color-scheme: dark)").matches ? "night" : "day";
    } catch (e) {
      return "day";
    }
  }

  function onSystemTheme() {
    if (userPrefs().theme === "auto") applyTheme("auto");
  }

  function bindThemeMql(on) {
    if (themeMql) {
      try { themeMql.removeEventListener("change", onSystemTheme); } catch (e) {}
      themeMql = null;
    }
    if (!on) return;
    try {
      themeMql = window.matchMedia("(prefers-color-scheme: dark)");
      themeMql.addEventListener("change", onSystemTheme);
    } catch (e) {}
  }

  function applyTheme(prefTheme) {
    var t = prefTheme || userPrefs().theme;
    var resolved = resolvedTheme(t);
    document.documentElement.setAttribute("data-theme", resolved);
    try { localStorage.setItem("csm.theme", t); } catch (e) {}
    var btn = $("btn-theme");
    if (btn) {
      btn.setAttribute("data-theme", resolved);
      btn.setAttribute("aria-label", resolved === "night" ? "Switch to day" : "Switch to night");
      btn.title = resolved === "night" ? "Night — click for Day" : "Day — click for Night";
    }
    bindThemeMql(t === "auto");
  }

  function fillPreferencesForm() {
    var p = userPrefs();
    if ($("pref-week-start")) $("pref-week-start").value = String(p.week_start);
    document.querySelectorAll("#pref-days input[type=checkbox]").forEach(function (cb) {
      cb.checked = p.hidden_weekdays.indexOf(+cb.value) < 0;
    });
    document.querySelectorAll("#pref-theme input[type=radio]").forEach(function (r) {
      r.checked = r.value === p.theme;
    });
  }

  function readHiddenDays() {
    var shown = [];
    document.querySelectorAll("#pref-days input[type=checkbox]").forEach(function (cb) {
      if (cb.checked) shown.push(+cb.value);
    });
    if (!shown.length) return null;
    var hidden = [];
    var i;
    for (i = 0; i < 7; i++) if (shown.indexOf(i) < 0) hidden.push(i);
    return hidden;
  }

  function savePreferences(partial, opts) {
    opts = opts || {};
    var cur = userPrefs();
    var next = {
      week_start: cur.week_start,
      hidden_weekdays: cur.hidden_weekdays.slice(),
      theme: cur.theme,
      timeline_layout: cur.timeline_layout,
      timeline_past_days: cur.timeline_past_days,
      timeline_next_days: cur.timeline_next_days,
    };
    if (partial.week_start != null) next.week_start = +partial.week_start;
    if (Object.prototype.hasOwnProperty.call(partial, "hidden_weekdays")) {
      next.hidden_weekdays = partial.hidden_weekdays || [];
    }
    if (partial.theme) next.theme = partial.theme;
    if (partial.timeline_layout) {
      next.timeline_layout = partial.timeline_layout === "horizontal" ? "horizontal" : "vertical";
    }
    if (partial.timeline_past_days) next.timeline_past_days = +partial.timeline_past_days === 30 ? 30 : 7;
    if (partial.timeline_next_days) next.timeline_next_days = +partial.timeline_next_days === 30 ? 30 : 7;
    if (!status) status = {};
    status.preferences = next;
    applyTheme(next.theme);
    fillPreferencesForm();
    var reloadCal = opts.calendar;
    if (reloadCal == null) {
      reloadCal = partial.week_start != null || Object.prototype.hasOwnProperty.call(partial, "hidden_weekdays");
    }
    if (reloadCal && homeTab === "agenda") loadAgenda();
    prefSave = prefSave.catch(function () {}).then(function () {
      return api("/api/settings", {
        method: "PUT",
        body: JSON.stringify({ preferences: next }),
      });
    }).catch(function (err) {
      toast(String(err.message || err));
    });
    return prefSave;
  }

  function monthStartYmd(ymd) {
    var p = String(ymd || "2000-01-01").split("-");
    return p[0] + "-" + p[1] + "-01";
  }

  function lastOfMonthYmd(ymd) {
    var p = String(ymd || "2000-01-01").split("-");
    var dim = new Date(Date.UTC(+p[0], +p[1], 0)).getUTCDate();
    return p[0] + "-" + p[1] + "-" + (dim < 10 ? "0" : "") + dim;
  }

  function shiftMonth(ymd, delta) {
    var p = String(ymd || "").split("-");
    var dt = new Date(Date.UTC(+p[0], +p[1] - 1 + delta, 1));
    var dim = new Date(Date.UTC(dt.getUTCFullYear(), dt.getUTCMonth() + 1, 0)).getUTCDate();
    var day = Math.min(+p[2] || 1, dim);
    return utcYmd(new Date(Date.UTC(dt.getUTCFullYear(), dt.getUTCMonth(), day)));
  }

  function agendaMeetRange() {
    if (agendaCalView === "week") {
      var start = weekStartYmd(agendaDay);
      return { start: start, end: shiftYmd(start, 6) };
    }
    if (agendaCalView === "month") {
      var first = monthStartYmd(agendaDay);
      return { start: weekStartYmd(first), end: shiftYmd(weekStartYmd(lastOfMonthYmd(first)), 6) };
    }
    return { start: agendaDay, end: agendaDay };
  }

  function formatRangeLabel(ymd) {
    if (agendaCalView === "week") {
      var days = weekDaysFrom(ymd);
      var first = days[0];
      var last = days[days.length - 1];
      if (first === last) return formatDayLabel(first);
      return formatDayLabel(first).replace(/,.*/, "") + " – " + formatDayLabel(last);
    }
    if (agendaCalView === "month") {
      var p = String(ymd || "").split("-");
      var dt = new Date(Date.UTC(+p[0], +p[1] - 1, 1));
      return dt.toLocaleDateString(undefined, { month: "long", year: "numeric", timeZone: "UTC" });
    }
    return formatDayLabel(ymd);
  }

  function formatTimeTz(date) {
    try {
      return new Intl.DateTimeFormat("en-US", {
        timeZone: operatorTz || "UTC",
        hour: "numeric",
        minute: "2-digit",
        hour12: !deskClockHour24(),
      }).format(date);
    } catch (e) {
      return formatClock(date);
    }
  }

  function tzClock(date) {
    var out = { hour: 0, minute: 0 };
    try {
      var parts = new Intl.DateTimeFormat("en-US", {
        timeZone: operatorTz || "UTC",
        hour: "numeric",
        minute: "2-digit",
        hourCycle: "h23",
      }).formatToParts(date);
      var i;
      for (i = 0; i < parts.length; i++) {
        if (parts[i].type === "hour") out.hour = +parts[i].value;
        if (parts[i].type === "minute") out.minute = +parts[i].value;
      }
      if (out.hour === 24) out.hour = 0;
    } catch (e) {
      out.hour = date.getHours();
      out.minute = date.getMinutes();
    }
    return out;
  }

  function minutesOfDay(date) {
    var c = tzClock(date);
    return c.hour * 60 + c.minute;
  }

  function deskClockHour24() {
    var clock = (status && status.world_clock) || {};
    return !!clock.hour24;
  }

  function deskClockFormatters(tz, use24) {
    if (deskClockFmts.tz !== tz || deskClockFmts.hour24 !== use24) {
      deskClockFmts.tz = tz;
      deskClockFmts.hour24 = use24;
      deskClockFmts.time = new Intl.DateTimeFormat("en-US", {
        timeZone: tz,
        hour: "numeric",
        minute: "2-digit",
        second: "2-digit",
        hour12: !use24,
      });
      deskClockFmts.date = new Intl.DateTimeFormat("en-US", {
        timeZone: tz,
        weekday: "short",
        month: "short",
        day: "numeric",
      });
      deskClockFmts.zone = new Intl.DateTimeFormat("en-US", {
        timeZone: tz,
        timeZoneName: "short",
      });
    }
    return deskClockFmts;
  }

  function tickDeskClock() {
    if (typeof document !== "undefined" && document.hidden) return;
    var timeEl = $("desk-clock-time");
    var root = $("desk-clock");
    if (!timeEl) return;
    var tz = operatorTz || "UTC";
    var now = new Date();
    var use24 = deskClockHour24();
    try {
      var fmts = deskClockFormatters(tz, use24);
      var timeStr = fmts.time.format(now);
      timeEl.textContent = timeStr;
      timeEl.dateTime = now.toISOString();
      var dateStr = fmts.date.format(now);
      var tzName = "";
      var parts = fmts.zone.formatToParts(now);
      var i;
      for (i = 0; i < parts.length; i++) {
        if (parts[i].type === "timeZoneName") tzName = parts[i].value;
      }
      var tip = tzName ? dateStr + " · " + tzName : dateStr;
      var whenEl = $("desk-clock-when");
      if (whenEl) whenEl.textContent = tip;
      if (root) {
        root.setAttribute("aria-label", timeStr + ". " + tip + ". Click for World Clock");
      }
      paintAgendaNowLine();
    } catch (e) {
      timeEl.textContent = now.toLocaleTimeString();
      var whenFail = $("desk-clock-when");
      if (whenFail) whenFail.textContent = tz;
      if (root) root.setAttribute("aria-label", "Click for World Clock");
    }
  }

  function startDeskClock() {
    tickDeskClock();
    if (deskClockTimer) window.clearInterval(deskClockTimer);
    deskClockTimer = window.setInterval(tickDeskClock, 1000);
  }

  function crumbSep(nav) {
    var sep = document.createElement("span");
    sep.className = "crumb-sep";
    sep.setAttribute("aria-hidden", "true");
    sep.textContent = ">";
    nav.appendChild(sep);
  }

  function crumbPart(nav, label, href, current) {
    if (current || !href) {
      var cur = document.createElement("span");
      cur.className = "crumb-current";
      cur.setAttribute("aria-current", "page");
      cur.textContent = label;
      nav.appendChild(cur);
      return;
    }
    var a = document.createElement("a");
    a.className = "crumb-link";
    a.href = href;
    a.textContent = label;
    nav.appendChild(a);
  }

  function renderHomeCrumb(acct) {
    var nav = $("home-crumb");
    if (!nav) return;
    empty(nav);
    if (acct) {
      crumbPart(nav, "Home", "#home", false);
      crumbSep(nav);
      crumbPart(nav, "Company", "#home/companies", false);
      crumbSep(nav);
      var cur = document.createElement("span");
      cur.className = "crumb-current";
      cur.setAttribute("aria-current", "page");
      cur.appendChild(document.createTextNode(acct.name || acct.abbr || "Company"));
      if (acct.abbr && acct.name && acct.abbr !== acct.name) {
        var ab = document.createElement("span");
        ab.className = "crumb-abbr";
        ab.textContent = acct.abbr;
        cur.appendChild(ab);
      }
      nav.appendChild(cur);
      return;
    }
    crumbPart(nav, "Home", "#home", false);
    crumbSep(nav);
    if (homeTab === "companies") crumbPart(nav, "Companies", "", true);
    else crumbPart(nav, "Agenda", "", true);
  }

  function showHomeTab(tab) {
    homeTab = tab === "companies" ? "companies" : "agenda";
    var tabs = $("home-tabs");
    if (tabs && !tabs.firstChild) {
      [["agenda", "Agenda"], ["companies", "Companies"]].forEach(function (pair) {
        var b = document.createElement("button");
        b.type = "button";
        b.className = "tab" + (homeTab === pair[0] ? " is-on" : "");
        b.textContent = pair[1];
        b.addEventListener("click", function () {
          location.hash = pair[0] === "agenda" ? "#home" : "#home/companies";
        });
        tabs.appendChild(b);
      });
    } else if (tabs) {
      var btns = tabs.querySelectorAll(".tab");
      if (btns[0]) btns[0].classList.toggle("is-on", homeTab === "agenda");
      if (btns[1]) btns[1].classList.toggle("is-on", homeTab === "companies");
    }
    var agenda = $("agenda-panel");
    var board = $("acct-board");
    if (agenda) {
      agenda.hidden = homeTab !== "agenda";
      agenda.classList.toggle("hidden", homeTab !== "agenda");
    }
    if (board) {
      board.hidden = homeTab !== "companies";
      board.classList.toggle("hidden", homeTab !== "companies");
    }
    var tools = $("home-company-tools");
    if (tools) {
      tools.hidden = homeTab !== "companies";
      tools.classList.toggle("hidden", homeTab !== "companies");
    }
    renderHomeCrumb(null);
    if (homeTab === "companies") loadHome();
    else loadAgenda();
  }

  function syncAgendaViewChrome(pane) {
    var split = pane.querySelector(".agenda-split");
    if (split) split.classList.toggle("is-wide", agendaCalView !== "day");
    pane.querySelectorAll("[data-cal-view]").forEach(function (b) {
      b.classList.toggle("is-on", b.getAttribute("data-cal-view") === agendaCalView);
    });
  }

  function fetchAgendaLists(calList, inList) {
    empty(calList);
    empty(inList);
    var loading = document.createElement("p");
    loading.className = "muted";
    loading.textContent = "Loading…";
    calList.appendChild(loading.cloneNode(true));
    inList.appendChild(loading);
    var range = agendaMeetRange();
    var qs = "date=" + encodeURIComponent(agendaDay) + "&start=" + encodeURIComponent(range.start) + "&end=" + encodeURIComponent(range.end);
    return api("/api/home/agenda?" + qs).then(function (data) {
      agendaMeetings = data.meetings || [];
      renderAgendaMeetings(calList, agendaMeetings);
      agendaInboxItems = data.inbox || [];
      agendaProjOptions = data.project_filters || [];
      fillAgendaProjFilter();
      renderAgendaInbox(inList, agendaInboxItems);
    }).catch(function (err) {
      var p = document.createElement("p");
      p.className = "muted";
      p.textContent = String(err.message || err);
      calList.appendChild(p);
    });
  }

  function loadAgenda() {
    if (!agendaDay) agendaDay = todayYmd();
    var pane = $("agenda-panel");
    if (!pane) return Promise.resolve();
    var calBoard = pane.querySelector(".agenda-cal");
    var inList = $("agenda-inbox-list");
    var label = pane.querySelector(".agenda-day-label");
    if (calBoard && inList) {
      if (label) label.textContent = formatRangeLabel(agendaDay);
      syncAgendaViewChrome(pane);
      var inHead = pane.querySelectorAll(".agenda-col-head")[1];
      if (inHead) {
        ensureAgendaProjFilter(inHead, inList);
        ensureAgendaInboxFilter(inHead, inList);
      }
      return fetchAgendaLists(calBoard, inList);
    }
    empty(pane);
    var split = document.createElement("div");
    split.className = "agenda-split" + (agendaCalView === "day" ? "" : " is-wide");
    var cal = document.createElement("section");
    cal.className = "agenda-col";
    var calHead = document.createElement("div");
    calHead.className = "agenda-col-head agenda-cal-head";
    var calTitle = document.createElement("h2");
    calTitle.textContent = "Meetings";
    var views = document.createElement("div");
    views.className = "agenda-views";
    views.setAttribute("role", "tablist");
    [["day", "Day"], ["week", "Week"], ["month", "Month"]].forEach(function (pair) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "tab" + (agendaCalView === pair[0] ? " is-on" : "");
      b.textContent = pair[1];
      b.setAttribute("data-cal-view", pair[0]);
      b.addEventListener("click", function () {
        agendaCalView = pair[0];
        loadAgenda();
      });
      views.appendChild(b);
    });
    var dayNav = document.createElement("div");
    dayNav.className = "agenda-day";
    var prev = document.createElement("button");
    prev.type = "button";
    prev.className = "btn";
    prev.textContent = "←";
    prev.setAttribute("aria-label", "Previous");
    prev.addEventListener("click", function () {
      if (agendaCalView === "week") agendaDay = shiftYmd(agendaDay, -7);
      else if (agendaCalView === "month") agendaDay = shiftMonth(agendaDay, -1);
      else agendaDay = shiftYmd(agendaDay, -1);
      loadAgenda();
    });
    var label = document.createElement("span");
    label.className = "agenda-day-label";
    label.textContent = formatRangeLabel(agendaDay);
    var next = document.createElement("button");
    next.type = "button";
    next.className = "btn";
    next.textContent = "→";
    next.setAttribute("aria-label", "Next");
    next.addEventListener("click", function () {
      if (agendaCalView === "week") agendaDay = shiftYmd(agendaDay, 7);
      else if (agendaCalView === "month") agendaDay = shiftMonth(agendaDay, 1);
      else agendaDay = shiftYmd(agendaDay, 1);
      loadAgenda();
    });
    dayNav.appendChild(prev);
    dayNav.appendChild(label);
    dayNav.appendChild(next);
    calHead.appendChild(calTitle);
    calHead.appendChild(views);
    calHead.appendChild(dayNav);
    var calList = document.createElement("div");
    calList.className = "agenda-cal";
    cal.appendChild(calHead);
    cal.appendChild(calList);
    var inbox = document.createElement("section");
    inbox.className = "agenda-col";
    var inHead = document.createElement("div");
    inHead.className = "agenda-col-head";
    var inTitle = document.createElement("h2");
    inTitle.textContent = "New mail / chat / tasks";
    var addTask = document.createElement("button");
    addTask.type = "button";
    addTask.className = "btn btn-icon";
    addTask.id = "btn-add-task";
    addTask.setAttribute("data-tip", "New task");
    addTask.setAttribute("aria-label", "New task");
    addTask.title = "New task";
    var addSvg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    addSvg.setAttribute("viewBox", "0 0 24 24");
    addSvg.setAttribute("aria-hidden", "true");
    var addPath = document.createElementNS("http://www.w3.org/2000/svg", "path");
    addPath.setAttribute("d", "M12 5v14M5 12h14");
    addSvg.appendChild(addPath);
    addTask.appendChild(addSvg);
    addTask.addEventListener("click", function () {
      openTaskForm(null);
    });
    inHead.appendChild(inTitle);
    ensureAgendaProjFilter(inHead, inList);
    ensureAgendaInboxFilter(inHead, inList);
    inHead.appendChild(addTask);
    var inList = document.createElement("div");
    inList.className = "agenda-list";
    inList.id = "agenda-inbox-list";
    inbox.appendChild(inHead);
    inbox.appendChild(inList);
    split.appendChild(cal);
    split.appendChild(inbox);
    pane.appendChild(split);
    return fetchAgendaLists(calList, inList);
  }

  function agendaInboxList() {
    return $("agenda-inbox-list") || document.querySelector("#agenda-panel .agenda-col:last-child .agenda-list");
  }

  function closeAgendaProjMenu() {
    var menu = $("agenda-proj-menu");
    if (!menu) return;
    menu.hidden = true;
    menu.classList.add("hidden");
  }

  function agendaProjLabel() {
    if (!agendaProjFilter) return "Company : Project";
    var hit = agendaProjOptions.filter(function (o) { return o.key === agendaProjFilter; })[0];
    return (hit && hit.label) || "Company : Project";
  }

  function longestAgendaProjPx() {
    if (!agendaProjProbe) {
      agendaProjProbe = document.createElement("span");
      agendaProjProbe.setAttribute("aria-hidden", "true");
      agendaProjProbe.style.cssText = "position:absolute;left:-9999px;top:0;white-space:nowrap;visibility:hidden;pointer-events:none;font-size:0.84rem;font-weight:600;";
      document.body.appendChild(agendaProjProbe);
    }
    var ref = document.querySelector(".agenda-proj-opt") || $("agenda-proj-btn");
    if (ref) {
      var cs = getComputedStyle(ref);
      agendaProjProbe.style.fontFamily = cs.fontFamily;
      agendaProjProbe.style.letterSpacing = cs.letterSpacing;
    }
    var widest = 0;
    function consider(text) {
      agendaProjProbe.textContent = text || "";
      widest = Math.max(widest, agendaProjProbe.offsetWidth);
    }
    consider("All companies");
    consider("Search company or project");
    (agendaProjOptions || []).forEach(function (opt) { consider(opt.label || ""); });
    return widest;
  }

  function placeAgendaProjMenu() {
    var menu = $("agenda-proj-menu");
    var btn = $("agenda-proj-btn");
    if (!menu || !btn || menu.hidden) return;
    var cap = Math.min(window.innerWidth - 16, 42 * 16);
    var w = Math.min(cap, Math.max(18 * 16, Math.ceil(longestAgendaProjPx() + 50)));
    var r = btn.getBoundingClientRect();
    var top = r.bottom + 4;
    var left = r.right - w;
    if (left < 8) left = 8;
    if (left + w > window.innerWidth - 8) left = Math.max(8, window.innerWidth - 8 - w);
    menu.style.top = top + "px";
    menu.style.left = left + "px";
    menu.style.width = w + "px";
  }

  function fillAgendaProjFilter() {
    var list = $("agenda-proj-list");
    var btn = $("agenda-proj-btn");
    if (btn) {
      btn.textContent = agendaProjLabel();
      btn.title = agendaProjLabel();
    }
    if (!list) return;
    var q = (($("agenda-proj-q") && $("agenda-proj-q").value) || "").toLowerCase().trim();
    empty(list);
    function addOpt(key, label) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "agenda-proj-opt" + (agendaProjFilter === key ? " is-on" : "");
      b.textContent = label;
      b.title = label;
      b.addEventListener("click", function () {
        agendaProjFilter = key;
        closeAgendaProjMenu();
        fillAgendaProjFilter();
        renderAgendaInbox(agendaInboxList(), agendaInboxItems);
      });
      list.appendChild(b);
    }
    if (!q) addOpt("", "All companies");
    agendaProjOptions.forEach(function (opt) {
      var label = opt.label || "";
      if (q && label.toLowerCase().indexOf(q) < 0) return;
      addOpt(opt.key || "", label);
    });
    if (!list.firstChild) {
      var p = document.createElement("p");
      p.className = "muted";
      p.textContent = "No match.";
      list.appendChild(p);
    }
    placeAgendaProjMenu();
  }

  function ensureAgendaProjFilter(inHead, inList) {
    if ($("agenda-proj-filter")) return;
    var wrap = document.createElement("div");
    wrap.className = "agenda-proj-filter";
    wrap.id = "agenda-proj-filter";
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "toolbar-filter agenda-proj-btn";
    btn.id = "agenda-proj-btn";
    btn.textContent = agendaProjLabel();
    btn.setAttribute("aria-haspopup", "listbox");
    btn.setAttribute("aria-label", "Filter by company and project");
    var menu = document.createElement("div");
    menu.className = "agenda-proj-menu hidden";
    menu.id = "agenda-proj-menu";
    menu.hidden = true;
    var search = document.createElement("input");
    search.type = "search";
    search.id = "agenda-proj-q";
    search.className = "search";
    search.placeholder = "Search company or project";
    search.setAttribute("aria-label", "Search company or project");
    search.addEventListener("input", fillAgendaProjFilter);
    search.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape") {
        ev.preventDefault();
        closeAgendaProjMenu();
        btn.focus();
      }
    });
    var list = document.createElement("div");
    list.id = "agenda-proj-list";
    list.className = "agenda-proj-list";
    list.setAttribute("role", "listbox");
    menu.appendChild(search);
    menu.appendChild(list);
    btn.addEventListener("click", function (ev) {
      ev.stopPropagation();
      if (!menu.hidden) {
        closeAgendaProjMenu();
        return;
      }
      menu.hidden = false;
      menu.classList.remove("hidden");
      if (search) search.value = "";
      fillAgendaProjFilter();
      placeAgendaProjMenu();
      search.focus();
    });
    wrap.appendChild(btn);
    document.body.appendChild(menu);
    var typeFilter = $("agenda-inbox-filter");
    if (typeFilter && typeFilter.parentNode === inHead) inHead.insertBefore(wrap, typeFilter);
    else inHead.appendChild(wrap);
    if (!agendaProjBound) {
      agendaProjBound = true;
      document.addEventListener("click", function (ev) {
        if (ev.target && !document.body.contains(ev.target)) return;
        var projRoot = $("agenda-proj-filter");
        var projMenu = $("agenda-proj-menu");
        var inboxRoot = $("agenda-inbox-filter");
        var inboxMenu = $("agenda-inbox-menu");
        if (projRoot && projRoot.contains(ev.target)) return;
        if (projMenu && projMenu.contains(ev.target)) return;
        if (inboxRoot && inboxRoot.contains(ev.target)) return;
        if (inboxMenu && inboxMenu.contains(ev.target)) return;
        closeAgendaProjMenu();
        closeAgendaInboxMenu();
      });
      window.addEventListener("resize", function () {
        placeAgendaProjMenu();
        placeAgendaInboxMenu();
      });
      window.addEventListener("scroll", function () {
        placeAgendaProjMenu();
        placeAgendaInboxMenu();
      }, true);
    }
  }

  var INBOX_KIND_OPTS = [
    { id: "email", label: "Email" },
    { id: "slack", label: "Slack" },
    { id: "teams", label: "Teams" },
    { id: "task", label: "Tasks" },
  ];
  var INBOX_TO_OPTS = [
    { id: "me", label: "Me" },
    { id: "us", label: "Us" },
    { id: "them", label: "Them" },
    { id: "all", label: "All" },
    { id: "unknown", label: "??" },
  ];
  var INBOX_WHEN_OPTS = [
    { id: "any", label: "Any time" },
    { id: "today", label: "Today" },
    { id: "yesterday", label: "Yesterday" },
    { id: "7d", label: "Last 7 days" },
    { id: "custom", label: "Custom" },
  ];

  function emptyInboxFilter() {
    return { kinds: [], audience: [], from: "", when: "any", fromDay: "", toDay: "" };
  }

  function toggleIn(list, id) {
    var next = (list || []).slice();
    var i = next.indexOf(id);
    if (i >= 0) next.splice(i, 1);
    else next.push(id);
    return next;
  }

  function inboxFilterCount() {
    var f = agendaInboxFilter || emptyInboxFilter();
    var n = 0;
    if ((f.kinds || []).length) n += 1;
    if ((f.audience || []).length) n += 1;
    if (String(f.from || "").trim()) n += 1;
    if (f.when && f.when !== "any") n += 1;
    return n;
  }

  function inboxFilterLabel() {
    var n = inboxFilterCount();
    return n ? "Filter · " + n : "Filter";
  }

  function closeAgendaInboxMenu() {
    var menu = $("agenda-inbox-menu");
    if (!menu) return;
    menu.hidden = true;
    menu.classList.add("hidden");
  }

  function placeAgendaInboxMenu() {
    var menu = $("agenda-inbox-menu");
    var btn = $("agenda-inbox-btn");
    if (!menu || !btn || menu.hidden) return;
    var w = Math.min(window.innerWidth - 16, 22 * 16);
    var r = btn.getBoundingClientRect();
    var top = r.bottom + 4;
    var left = r.right - w;
    if (left < 8) left = 8;
    if (left + w > window.innerWidth - 8) left = Math.max(8, window.innerWidth - 8 - w);
    menu.style.top = top + "px";
    menu.style.left = left + "px";
    menu.style.width = w + "px";
  }

  function inboxItemDay(item) {
    if (!item || !item.at) return "";
    var d = new Date(item.at);
    if (isNaN(d.getTime())) return String(item.at).slice(0, 10);
    return ymdInZone(d, operatorTz);
  }

  function inboxItemMatches(item) {
    if (!item) return false;
    var f = agendaInboxFilter || emptyInboxFilter();
    var kinds = f.kinds || [];
    if (kinds.length && kinds.indexOf(item.kind) < 0) return false;
    var aud = f.audience || [];
    if (aud.length) {
      var key = AUDIENCE_STAMP[item.audience] ? item.audience : "unknown";
      if (aud.indexOf(key) < 0) return false;
    }
    var fromQ = String(f.from || "").trim().toLowerCase();
    if (fromQ) {
      var blob = [item.from_name, item.title, item.body].join(" ").toLowerCase();
      if (blob.indexOf(fromQ) < 0) return false;
    }
    if (agendaProjFilter) {
      var aid = (item.account && item.account.account_id) || "";
      var pid = item.project_id || "";
      var parts = String(agendaProjFilter).split("|");
      if (parts.length === 1) {
        if (aid !== parts[0]) return false;
      } else if (!(aid === parts[0] && pid === parts[1])) return false;
    }
    var when = f.when || "any";
    if (when === "any") return true;
    var day = inboxItemDay(item);
    if (!day) return false;
    var today = todayYmd();
    if (when === "today") return day === today;
    if (when === "yesterday") return day === shiftYmd(today, -1);
    if (when === "7d") return day <= today && day >= shiftYmd(today, -6);
    if (when === "custom") {
      var a = f.fromDay || "";
      var b = f.toDay || "";
      if (!a && !b) return true;
      if (a && day < a) return false;
      if (b && day > b) return false;
    }
    return true;
  }

  function uniqueInboxFroms(items) {
    var counts = {};
    (items || []).forEach(function (item) {
      var name = String(item.from_name || "").trim();
      if (!name) return;
      counts[name] = (counts[name] || 0) + 1;
    });
    return Object.keys(counts).sort(function (a, b) {
      return counts[b] - counts[a] || a.localeCompare(b);
    }).slice(0, 12);
  }

  function paintInboxFilterBtn() {
    var btn = $("agenda-inbox-btn");
    if (!btn) return;
    btn.textContent = inboxFilterLabel();
    btn.classList.toggle("is-on", inboxFilterCount() > 0);
  }

  function paintInboxFilterMenu() {
    var menu = $("agenda-inbox-menu");
    if (!menu) return;
    empty(menu);
    var f = agendaInboxFilter || emptyInboxFilter();

    function legend(text) {
      var el = document.createElement("div");
      el.className = "agenda-filter-legend";
      el.textContent = text;
      menu.appendChild(el);
    }
    function chips(opts, selected, multi, onPick) {
      var row = document.createElement("div");
      row.className = "agenda-filter-row";
      opts.forEach(function (opt) {
        var b = document.createElement("button");
        b.type = "button";
        var on = multi ? selected.indexOf(opt.id) >= 0 : selected === opt.id;
        b.className = "agenda-filter-chip" + (on ? " is-on" : "");
        b.textContent = opt.label;
        b.addEventListener("click", function (ev) {
          ev.stopPropagation();
          onPick(opt.id);
        });
        row.appendChild(b);
      });
      menu.appendChild(row);
    }

    legend("To");
    chips(INBOX_TO_OPTS, f.audience || [], true, function (id) {
      agendaInboxFilter.audience = toggleIn(agendaInboxFilter.audience, id);
      paintInboxFilterMenu();
      paintInboxFilterBtn();
      renderAgendaInbox(agendaInboxList(), agendaInboxItems);
    });
    legend("Type");
    chips(INBOX_KIND_OPTS, f.kinds || [], true, function (id) {
      agendaInboxFilter.kinds = toggleIn(agendaInboxFilter.kinds, id);
      paintInboxFilterMenu();
      paintInboxFilterBtn();
      renderAgendaInbox(agendaInboxList(), agendaInboxItems);
    });
    legend("From");
    var fromIn = document.createElement("input");
    fromIn.type = "search";
    fromIn.className = "search";
    fromIn.id = "agenda-inbox-from";
    fromIn.placeholder = "name or email";
    fromIn.setAttribute("aria-label", "Filter by from");
    fromIn.value = f.from || "";
    fromIn.addEventListener("input", function () {
      agendaInboxFilter.from = fromIn.value;
      paintInboxFilterBtn();
      renderAgendaInbox(agendaInboxList(), agendaInboxItems);
      paintFromChips();
    });
    menu.appendChild(fromIn);
    var fromChips = document.createElement("div");
    fromChips.className = "agenda-filter-row";
    fromChips.id = "agenda-inbox-from-chips";
    menu.appendChild(fromChips);
    function paintFromChips() {
      empty(fromChips);
      var q = String(agendaInboxFilter.from || "").trim().toLowerCase();
      uniqueInboxFroms(agendaInboxItems).forEach(function (name) {
        if (q && name.toLowerCase().indexOf(q) < 0) return;
        var b = document.createElement("button");
        b.type = "button";
        b.className = "agenda-filter-chip" + (String(agendaInboxFilter.from || "") === name ? " is-on" : "");
        b.textContent = name;
        b.title = name;
        b.addEventListener("click", function () {
          agendaInboxFilter.from = agendaInboxFilter.from === name ? "" : name;
          fromIn.value = agendaInboxFilter.from;
          paintInboxFilterMenu();
          paintInboxFilterBtn();
          renderAgendaInbox(agendaInboxList(), agendaInboxItems);
        });
        fromChips.appendChild(b);
      });
    }
    paintFromChips();

    legend("When");
    chips(INBOX_WHEN_OPTS, f.when || "any", false, function (id) {
      agendaInboxFilter.when = id;
      paintInboxFilterMenu();
      paintInboxFilterBtn();
      renderAgendaInbox(agendaInboxList(), agendaInboxItems);
    });
    if ((f.when || "any") === "custom") {
      var dates = document.createElement("div");
      dates.className = "agenda-filter-dates";
      var start = document.createElement("input");
      start.type = "date";
      start.setAttribute("aria-label", "From date");
      start.value = f.fromDay || "";
      start.addEventListener("change", function () {
        agendaInboxFilter.fromDay = start.value;
        paintInboxFilterBtn();
        renderAgendaInbox(agendaInboxList(), agendaInboxItems);
      });
      var end = document.createElement("input");
      end.type = "date";
      end.setAttribute("aria-label", "To date");
      end.value = f.toDay || "";
      end.addEventListener("change", function () {
        agendaInboxFilter.toDay = end.value;
        paintInboxFilterBtn();
        renderAgendaInbox(agendaInboxList(), agendaInboxItems);
      });
      dates.appendChild(start);
      dates.appendChild(end);
      menu.appendChild(dates);
    }
    var clear = document.createElement("button");
    clear.type = "button";
    clear.className = "btn";
    clear.textContent = "Clear filters";
    clear.addEventListener("click", function () {
      agendaInboxFilter = emptyInboxFilter();
      paintInboxFilterMenu();
      paintInboxFilterBtn();
      renderAgendaInbox(agendaInboxList(), agendaInboxItems);
    });
    menu.appendChild(clear);
    placeAgendaInboxMenu();
  }

  function ensureAgendaInboxFilter(inHead, inList) {
    if ($("agenda-inbox-filter")) {
      paintInboxFilterBtn();
      return;
    }
    var wrap = document.createElement("div");
    wrap.className = "agenda-inbox-filter";
    wrap.id = "agenda-inbox-filter";
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "toolbar-filter agenda-inbox-btn";
    btn.id = "agenda-inbox-btn";
    btn.textContent = inboxFilterLabel();
    btn.setAttribute("aria-haspopup", "dialog");
    btn.setAttribute("aria-label", "Filter mail, chat, and tasks");
    var menu = document.createElement("div");
    menu.className = "agenda-proj-menu agenda-inbox-menu hidden";
    menu.id = "agenda-inbox-menu";
    menu.hidden = true;
    menu.addEventListener("click", function (ev) { ev.stopPropagation(); });
    btn.addEventListener("click", function (ev) {
      ev.stopPropagation();
      if (!menu.hidden) {
        closeAgendaInboxMenu();
        return;
      }
      closeAgendaProjMenu();
      menu.hidden = false;
      menu.classList.remove("hidden");
      paintInboxFilterMenu();
      var fromIn = $("agenda-inbox-from");
      if (fromIn) fromIn.focus();
    });
    wrap.appendChild(btn);
    document.body.appendChild(menu);
    var addTask = $("btn-add-task");
    if (addTask && addTask.parentNode === inHead) inHead.insertBefore(wrap, addTask);
    else inHead.appendChild(wrap);
  }

  function meetingLengthMins(start, end) {
    var s = new Date(start);
    var e = new Date(end);
    if (isNaN(s.getTime()) || isNaN(e.getTime()) || e <= s) return 0;
    return Math.max(1, Math.round((e.getTime() - s.getTime()) / 60000));
  }

  var CAL_PX = 56;
  var CAL_DAY_SPAN = { startH: 0, endH: 24 };
  var CAL_SCROLL_HOUR = 7;

  function eventsOnDay(items, ymd) {
    return (items || []).filter(function (ev) {
      var s = new Date(ev.start_at);
      if (isNaN(s.getTime())) return false;
      return ymdInZone(s, operatorTz) === ymd;
    });
  }

  function placedEvent(ev) {
    var start = new Date(ev.start_at);
    var end = new Date(ev.end_at || ev.start_at);
    if (isNaN(end.getTime()) || end <= start) end = new Date(start.getTime() + 30 * 60000);
    return {
      raw: ev,
      start: start,
      end: end,
      startMin: minutesOfDay(start),
      endMin: minutesOfDay(end),
      col: 0,
      cols: 1,
    };
  }

  function packDayEvents(items) {
    var evs = items.map(placedEvent).sort(function (a, b) {
      return a.start - b.start || a.end - b.end;
    });
    evs.forEach(function (ev) {
      if (ev.endMin <= ev.startMin) ev.endMin = ev.startMin + 30;
    });
    var active = [];
    evs.forEach(function (ev) {
      active = active.filter(function (a) { return a.endMin > ev.startMin; });
      var used = {};
      active.forEach(function (a) { used[a.col] = true; });
      var col = 0;
      while (used[col]) col += 1;
      ev.col = col;
      active.push(ev);
    });
    evs.forEach(function (ev) {
      var max = ev.col;
      evs.forEach(function (o) {
        if (o.startMin < ev.endMin && o.endMin > ev.startMin) max = Math.max(max, o.col);
      });
      ev.cols = max + 1;
    });
    return evs;
  }

  function hourSpan(evs) {
    var startH = 7;
    var endH = 19;
    evs.forEach(function (ev) {
      startH = Math.min(startH, Math.floor(ev.startMin / 60));
      endH = Math.max(endH, Math.ceil(ev.endMin / 60));
    });
    startH = Math.max(0, startH);
    endH = Math.min(24, Math.max(endH, startH + 1));
    return { startH: startH, endH: endH };
  }

  function hourLabel(h) {
    var d = new Date(Date.UTC(2026, 0, 1, h, 0, 0));
    try {
      return new Intl.DateTimeFormat("en-US", {
        timeZone: "UTC",
        hour: "numeric",
        hour12: !deskClockHour24(),
      }).format(d);
    } catch (e) {
      return h + ":00";
    }
  }

  function calEventCard(placed, compact) {
    var ev = placed.raw;
    var mins = meetingLengthMins(placed.start, placed.end) || Math.max(1, placed.endMin - placed.startMin);
    var card = document.createElement("article");
    card.className = "cal-event" + (compact ? " is-compact" : "") + (placed.end.getTime() < Date.now() ? " is-past" : "");
    if (ev._id) card.setAttribute("data-doc-id", ev._id);
    if (ev.account && ev.account.color) card.style.borderLeftColor = ev.account.color;
    var top = document.createElement("div");
    top.className = "cal-event-top";
    if (ev.account) top.appendChild(accountMark(ev.account, "inbox"));
    var when = document.createElement("time");
    when.className = "cal-event-time";
    when.dateTime = ev.start_at || "";
    when.textContent = formatTimeTz(placed.start) + "–" + formatTimeTz(placed.end);
    top.appendChild(when);
    var title = document.createElement("div");
    title.className = "cal-event-title";
    title.textContent = ev.title || "Meeting";
    var meta = document.createElement("div");
    meta.className = "cal-event-meta";
    var bits = [];
    if (ev.account && ev.account.abbr) bits.push(ev.account.abbr);
    if (ev.location) bits.push(ev.location);
    bits.push(mins + " min");
    if (ev.status === "proposed") bits.push("proposed");
    var who = (ev.attendees || []).map(function (a) { return (a && (a.name || a.email)) || ""; }).filter(Boolean);
    if (who.length && !compact) bits.push(who.slice(0, 3).join(", "));
    meta.textContent = bits.join(" · ");
    card.appendChild(top);
    card.appendChild(title);
    if (!compact || mins >= 25) card.appendChild(meta);
    if (ev.account && ev.account.abbr && ev._id) {
      card.addEventListener("click", function () {
        goAccountItem(ev.account.abbr, "calendar", ev._id);
      });
    }
    return card;
  }

  function paintAgendaNowLine() {
    var now = new Date();
    var today = ymdInZone(now, operatorTz);
    var nowMin = minutesOfDay(now);
    document.querySelectorAll(".cal-now").forEach(function (line) {
      var day = line.getAttribute("data-day") || "";
      var startH = +line.getAttribute("data-hour-start") || 0;
      var endH = +line.getAttribute("data-hour-end") || 24;
      var px = +line.getAttribute("data-px") || CAL_PX;
      if (day !== today) {
        line.hidden = true;
        return;
      }
      if (nowMin < startH * 60 || nowMin > endH * 60) {
        line.hidden = true;
        return;
      }
      line.hidden = false;
      line.style.top = ((nowMin - startH * 60) / 60) * px + "px";
    });
  }

  function renderDayColumn(ymd, items, span) {
    var placed = packDayEvents(eventsOnDay(items, ymd));
    var hours = span || hourSpan(placed);
    var height = (hours.endH - hours.startH) * CAL_PX;
    var col = document.createElement("div");
    col.className = "cal-day";
    var gutter = document.createElement("div");
    gutter.className = "cal-gutter";
    var h;
    for (h = hours.startH; h < hours.endH; h++) {
      var slot = document.createElement("div");
      slot.className = "cal-hour";
      slot.style.height = CAL_PX + "px";
      var lab = document.createElement("span");
      lab.textContent = hourLabel(h);
      slot.appendChild(lab);
      gutter.appendChild(slot);
    }
    var track = document.createElement("div");
    track.className = "cal-track";
    track.style.height = height + "px";
    for (h = hours.startH; h < hours.endH; h++) {
      var grid = document.createElement("div");
      grid.className = "cal-grid-line";
      grid.style.top = (h - hours.startH) * CAL_PX + "px";
      track.appendChild(grid);
    }
    placed.forEach(function (ev) {
      var top = ((ev.startMin - hours.startH * 60) / 60) * CAL_PX;
      var ht = Math.max(18, ((ev.endMin - ev.startMin) / 60) * CAL_PX - 2);
      var width = 100 / ev.cols;
      var card = calEventCard(ev, ht < 40);
      card.style.top = Math.max(0, top) + "px";
      card.style.height = ht + "px";
      card.style.left = "calc(" + (width * ev.col) + "% + 2px)";
      card.style.width = "calc(" + width + "% - 4px)";
      track.appendChild(card);
    });
    var nowLine = document.createElement("div");
    nowLine.className = "cal-now";
    nowLine.setAttribute("data-day", ymd);
    nowLine.setAttribute("data-hour-start", String(hours.startH));
    nowLine.setAttribute("data-hour-end", String(hours.endH));
    nowLine.setAttribute("data-px", String(CAL_PX));
    track.appendChild(nowLine);
    col.appendChild(gutter);
    col.appendChild(track);
    return col;
  }

  function renderAgendaMeetings(root, items) {
    empty(root);
    if (agendaCalView === "month") {
      renderMonthGrid(root, items || []);
      return;
    }
    if (agendaCalView === "week") {
      renderWeekGrid(root, items || []);
      return;
    }
    var wrap = document.createElement("div");
    wrap.className = "cal-board is-day";
    wrap.appendChild(renderDayColumn(agendaDay, items, CAL_DAY_SPAN));
    root.appendChild(wrap);
    paintAgendaNowLine();
    root.scrollTop = CAL_SCROLL_HOUR * CAL_PX;
  }

  function renderWeekGrid(root, items) {
    var days = weekDaysFrom(agendaDay);
    var span = CAL_DAY_SPAN;
    var board = document.createElement("div");
    board.className = "cal-board is-week";
    board.style.setProperty("--cal-days", String(days.length));
    var head = document.createElement("div");
    head.className = "cal-week-head";
    head.appendChild(document.createElement("span"));
    days.forEach(function (d) {
      var cell = document.createElement("button");
      cell.type = "button";
      cell.className = "cal-week-day" + (d === agendaDay ? " is-on" : "") + (d === todayYmd() ? " is-today" : "");
      cell.textContent = formatDayLabel(d).replace(/,.*/, "");
      cell.addEventListener("click", function () {
        agendaDay = d;
        agendaCalView = "day";
        loadAgenda();
      });
      head.appendChild(cell);
    });
    board.appendChild(head);
    var body = document.createElement("div");
    body.className = "cal-week-body";
    var gutter = document.createElement("div");
    gutter.className = "cal-gutter";
    var h;
    for (h = span.startH; h < span.endH; h++) {
      var slot = document.createElement("div");
      slot.className = "cal-hour";
      slot.style.height = CAL_PX + "px";
      var lab = document.createElement("span");
      lab.textContent = hourLabel(h);
      slot.appendChild(lab);
      gutter.appendChild(slot);
    }
    body.appendChild(gutter);
    days.forEach(function (d) {
      var col = renderDayColumn(d, items, span);
      var track = col.querySelector(".cal-track");
      col.querySelector(".cal-gutter").remove();
      col.className = "cal-week-col";
      body.appendChild(col);
      if (track) track.style.minHeight = (span.endH - span.startH) * CAL_PX + "px";
    });
    board.appendChild(body);
    root.appendChild(board);
    paintAgendaNowLine();
    body.scrollTop = CAL_SCROLL_HOUR * CAL_PX;
  }

  function renderMonthGrid(root, items) {
    var first = monthStartYmd(agendaDay);
    var gridStart = weekStartYmd(first);
    var vis = visibleWeekdays();
    var board = document.createElement("div");
    board.className = "cal-board is-month";
    board.style.setProperty("--cal-days", String(vis.length));
    var head = document.createElement("div");
    head.className = "cal-month-head";
    vis.forEach(function (dow) {
      var el = document.createElement("div");
      el.textContent = WEEKDAY_SHORT[dow];
      head.appendChild(el);
    });
    board.appendChild(head);
    var body = document.createElement("div");
    body.className = "cal-month-body";
    var i;
    for (i = 0; i < 42; i++) {
      var ymd = shiftYmd(gridStart, i);
      if (vis.indexOf(ymdWeekday(ymd)) < 0) continue;
      var inMonth = ymd.slice(0, 7) === first.slice(0, 7);
      var cell = document.createElement("button");
      cell.type = "button";
      cell.className = "cal-month-cell" + (inMonth ? "" : " is-out") + (ymd === agendaDay ? " is-on" : "") + (ymd === todayYmd() ? " is-today" : "");
      var num = document.createElement("span");
      num.className = "cal-month-num";
      num.textContent = String(+ymd.slice(8));
      cell.appendChild(num);
      eventsOnDay(items, ymd).slice(0, 4).forEach(function (ev) {
        var chip = document.createElement("span");
        chip.className = "cal-month-chip";
        if (ev.account && ev.account.color) chip.style.borderLeftColor = ev.account.color;
        chip.textContent = ev.title || "Meeting";
        cell.appendChild(chip);
      });
      var extra = eventsOnDay(items, ymd).length - 4;
      if (extra > 0) {
        var more = document.createElement("span");
        more.className = "cal-month-more";
        more.textContent = "+" + extra + " more";
        cell.appendChild(more);
      }
      cell.addEventListener("click", function (picked) {
        return function () {
          agendaDay = picked;
          agendaCalView = "day";
          loadAgenda();
        };
      }(ymd));
      body.appendChild(cell);
    }
    board.appendChild(body);
    root.appendChild(board);
  }

  var AUDIENCE_STAMP = {
    me: { label: "Me", title: "To Me" },
    us: { label: "Us", title: "To Us" },
    them: { label: "Them", title: "To Them" },
    all: { label: "All", title: "To All" },
    unknown: { label: "??", title: "Don't know" },
    na: { label: "n/a", title: "n/a" },
  };

  function audienceStamp(value) {
    var key = AUDIENCE_STAMP[value] ? value : "unknown";
    var spec = AUDIENCE_STAMP[key];
    var el = document.createElement("span");
    el.className = "agenda-who is-" + key;
    el.textContent = spec.label;
    el.title = spec.title;
    el.setAttribute("aria-label", spec.title);
    return el;
  }

  function renderAgendaInbox(root, items) {
    empty(root);
    var shown = (items || []).filter(inboxItemMatches);
    if (!shown.length) {
      var p = document.createElement("p");
      p.className = "muted";
      var emptyMsg = "No new email, chat, or tasks.";
      if (inboxFilterCount() || agendaProjFilter) emptyMsg = "Nothing matches those filters.";
      p.textContent = emptyMsg;
      root.appendChild(p);
      return;
    }
    shown.forEach(function (item) {
      var card = document.createElement("article");
      card.className = "agenda-item";
      var ref = item.ref || {};
      var itemId = item.kind === "email" ? (ref.thread_id || ref.id || "") : (ref.id || "");
      if (itemId) card.setAttribute("data-doc-id", itemId);
      var lead = document.createElement("div");
      lead.className = "agenda-item-lead";
      lead.appendChild(kindIcon(item.kind, "lg"));
      if (item.account) lead.appendChild(accountMark(item.account, "inbox"));
      var bodyWrap = document.createElement("div");
      bodyWrap.className = "agenda-item-body";
      var title = document.createElement("strong");
      title.textContent = item.title || "";
      var body = document.createElement("div");
      body.className = "row-meta";
      body.textContent = item.body || "";
      var when = document.createElement("div");
      when.className = "row-meta";
      when.textContent = (item.from_name ? item.from_name + " · " : "") + formatWhen(item.at);
      bodyWrap.appendChild(title);
      bodyWrap.appendChild(body);
      bodyWrap.appendChild(when);
      if (item.kind === "task" && item.due_at) {
        var due = document.createElement("div");
        due.className = "row-meta agenda-task-due";
        due.textContent = "Due " + formatWhen(item.due_at);
        bodyWrap.appendChild(due);
      }
      card.appendChild(lead);
      card.appendChild(bodyWrap);
      card.appendChild(audienceStamp(item.audience));
      card.addEventListener("click", function () {
        var abbr = item.account && item.account.abbr;
        if (!abbr || !itemId) {
          if (item.kind === "task") openTaskForm(item);
          return;
        }
        var tab = (item.kind === "teams" || item.kind === "slack") ? "chat" : "email";
        goAccountItem(abbr, tab, itemId);
      });
      root.appendChild(card);
    });
  }

  var TASK_KINDS = ["Action item(s)", "Follow up(s)", "Review(s)", "More Detail(s)"];

  function closeTaskForm() {
    var box = $("task-box");
    if (!box) return;
    if (box._mail && box._mail.destroy) box._mail.destroy();
    box._mail = null;
    if (box._namePick && box._namePick.destroy) box._namePick.destroy();
    box._namePick = null;
    box.hidden = true;
    box.classList.add("hidden");
    empty(box);
  }

  function dueInputValue(raw) {
    var s = String(raw || "").trim();
    if (!s) return "";
    if (s.length >= 16 && s.charAt(4) === "-" && s.charAt(10) === "T") return s.slice(0, 16);
    return s;
  }

  function taskSubjectPreview(company, name, kind) {
    return "Tasks: " + (company || "Company") + " : " + (name || "task name") + " {" + (kind || TASK_KINDS[0]) + "}";
  }

  function openTaskForm(item) {
    var box = $("task-box");
    if (!box) return;
    box.hidden = false;
    box.classList.remove("hidden");
    empty(box);
    var emailId = "";
    if (item) {
      if (item.ref && item.ref.id) emailId = item.ref.id;
      else if (item.operator && item.operator.task && item._id) emailId = item._id;
      else if (item._id && (item.kind === "task" || item.task_name)) emailId = item._id;
    }
    var sheet = document.createElement("article");
    sheet.className = "sheet sheet-task";
    var head = document.createElement("header");
    var title = document.createElement("h2");
    title.textContent = emailId ? "Edit task" : "New task";
    var close = document.createElement("button");
    close.type = "button";
    close.className = "btn btn-ghost sheet-close";
    close.textContent = "Close";
    close.addEventListener("click", closeTaskForm);
    head.appendChild(title);
    head.appendChild(close);
    sheet.appendChild(head);
    var preview = document.createElement("p");
    preview.className = "muted task-subject-preview";
    var company = document.createElement("select");
    company.id = "task-account";
    var namePick = mountSearchSelect({
      trigger: "input",
      placeholder: "Task name",
      ariaLabel: "Task name",
      allowCustom: true,
      items: [],
      onChange: function () { refreshPreview(); },
      onQuery: function () { refreshPreview(); },
    });
    namePick.el.id = "task-name";
    var kind = document.createElement("select");
    kind.id = "task-kind";
    TASK_KINDS.forEach(function (k) {
      var opt = document.createElement("option");
      opt.value = k;
      opt.textContent = k;
      kind.appendChild(opt);
    });
    var due = document.createElement("input");
    due.id = "task-due";
    due.type = "datetime-local";
    function companyLabel() {
      var opt = company.options[company.selectedIndex];
      return opt ? opt.getAttribute("data-name") || opt.textContent : "";
    }
    function taskNameValue() {
      return String(namePick.get() || "").trim();
    }
    function refreshPreview() {
      var line = taskSubjectPreview(companyLabel(), taskNameValue(), kind.value);
      preview.textContent = line;
      if (mail) mail.setSubject(line);
    }
    kind.addEventListener("change", refreshPreview);
    var form = document.createElement("div");
    form.className = "settings-form";
    var labCo = document.createElement("label");
    labCo.appendChild(document.createTextNode("Company"));
    labCo.appendChild(company);
    var labName = document.createElement("label");
    labName.appendChild(document.createTextNode("Task name"));
    labName.appendChild(namePick.el);
    var labKind = document.createElement("label");
    labKind.appendChild(document.createTextNode("Type"));
    labKind.appendChild(kind);
    var labDue = document.createElement("label");
    labDue.appendChild(document.createTextNode("Due"));
    labDue.appendChild(due);
    form.appendChild(labCo);
    form.appendChild(labName);
    form.appendChild(labKind);
    form.appendChild(labDue);
    var me = ((status && status.operator) || {}).email || "";
    var mail = null;
    function taskPayload(snap) {
      snap = snap || (mail && mail.snapshot()) || {};
      return {
        account_id: company.value,
        task_name: taskNameValue(),
        task_kind: kind.value,
        due_at: due.value,
        cc_addrs: snap.cc_addrs || [],
        bcc_addrs: snap.bcc_addrs || [],
        body: snap.body || "",
      };
    }
    function saveTask(snap) {
      if (!company.value) return Promise.reject(new Error("Pick a company first"));
      if (!taskNameValue()) return Promise.reject(new Error("Task name required"));
      var req = emailId
        ? api("/api/tasks/" + encodeURIComponent(emailId), { method: "PUT", body: JSON.stringify(taskPayload(snap)) })
        : api("/api/tasks", { method: "POST", body: JSON.stringify(taskPayload(snap)) });
      return req.then(function (doc) {
        if (doc && doc._id) emailId = doc._id;
        return doc;
      });
    }
    sheet.appendChild(preview);
    sheet.appendChild(form);
    mail = mountMailComposer(sheet, {
      accountId: "",
      to: me ? [me] : [],
      lockTo: !!me,
      bodyPlaceholder: "What needs to happen",
      sendConfirm: "Send this task to your mailbox?",
      onSuggest: function (snap) {
        if (!company.value) return Promise.reject(new Error("Pick a company first"));
        return api("/api/tasks/assist", {
          method: "POST",
          body: JSON.stringify({
            account_id: company.value,
            task_kind: kind.value,
            task_name: taskNameValue(),
            due_at: due.value,
            body: snap.body,
            cc_addrs: snap.cc_addrs,
          }),
        }).then(function (doc) {
          if (doc.task_name) namePick.set(doc.task_name);
          if (doc.task_kind) kind.value = doc.task_kind;
          if (doc.due_at) due.value = dueInputValue(doc.due_at);
          mail.set({
            cc_addrs: doc.cc_addrs || snap.cc_addrs,
            body: doc.body || snap.body,
            subject: taskSubjectPreview(companyLabel(), taskNameValue(), kind.value),
          });
          refreshPreview();
          toast(doc.result === "grok" ? "Drafted with Grok" : "Template draft");
          return doc;
        });
      },
      onSave: function (snap) {
        return saveTask(snap).then(function () {
          toast("Draft saved");
          closeTaskForm();
          loadAgenda();
        });
      },
      onSend: function (snap, attachments) {
        return saveTask(snap).then(function (doc) {
          var id = (doc && doc._id) || emailId;
          return api("/api/tasks/" + encodeURIComponent(id) + "/send", {
            method: "POST",
            body: JSON.stringify({
              to_addrs: snap.to_addrs,
              cc_addrs: snap.cc_addrs,
              bcc_addrs: snap.bcc_addrs,
              subject: snap.subject,
              body: snap.body,
              attachments: attachments || [],
            }),
          });
        }).then(function () {
          toast("Sent");
          closeTaskForm();
          loadAgenda();
        });
      },
    });
    function refreshTaskNames() {
      var aid = company.value;
      var seen = {};
      var items = [];
      (agendaInboxItems || []).forEach(function (it) {
        if (it.kind !== "task") return;
        if (aid && it.account && it.account.account_id !== aid) return;
        var n = String(it.task_name || it.title || "").replace(/^Tasks:\s*[^:]+:\s*/i, "").replace(/\s*\{[^}]+\}\s*$/, "").trim();
        if (!n || seen[n.toLowerCase()]) return;
        seen[n.toLowerCase()] = true;
        items.push({ value: n, label: n });
      });
      namePick.setItems(items);
    }
    company.addEventListener("change", function () {
      refreshPreview();
      refreshTaskNames();
      mail.setAccount(company.value);
    });
    box._mail = mail;
    box._namePick = namePick;
    box.appendChild(sheet);
    api("/api/accounts").then(function (data) {
      empty(company);
      var blank = document.createElement("option");
      blank.value = "";
      blank.textContent = "Select a company";
      company.appendChild(blank);
      (data.items || []).forEach(function (a) {
        var opt = document.createElement("option");
        opt.value = a.account_id;
        opt.setAttribute("data-name", a.name || a.abbr || "");
        opt.textContent = (a.abbr || "") + " — " + (a.name || "");
        company.appendChild(opt);
      });
      if (emailId) return api("/api/tasks/" + encodeURIComponent(emailId));
      return null;
    }).then(function (doc) {
      if (doc) {
        company.value = doc.account_id || "";
        namePick.set(doc.task_name || "");
        kind.value = doc.task_kind || TASK_KINDS[0];
        due.value = dueInputValue(doc.due_at);
        mail.set({
          to_addrs: doc.to_addrs && doc.to_addrs.length ? doc.to_addrs : (me ? [me] : []),
          cc_addrs: doc.cc_addrs || [],
          bcc_addrs: doc.bcc_addrs || [],
          body: doc.content || "",
          subject: doc.subject || taskSubjectPreview(companyLabel(), taskNameValue(), kind.value),
        });
      } else if (item && item.account && item.account.account_id) {
        company.value = item.account.account_id;
      }
      refreshPreview();
      refreshTaskNames();
      return mail.setAccount(company.value);
    }).catch(function (err) {
      toast(String(err.message || err));
    });
  }

  function paintHomeBoard() {
    var q = ($("home-q") && $("home-q").value || "").toLowerCase();
    var board = $("acct-board");
    if (!board) return;
    empty(board);
    (homeItems || []).forEach(function (acct) {
      var blob = ((acct.name || "") + " " + (acct.abbr || "")).toLowerCase();
      if (q && blob.indexOf(q) < 0) return;
      board.appendChild(homeCard(acct));
    });
    if (!board.firstChild) {
      var p = document.createElement("p");
      p.className = "muted";
      p.textContent = "No accounts yet. Open Settings and load seed data.";
      board.appendChild(p);
    }
  }

  function loadHome(force) {
    if (!force && homeItems) {
      paintHomeBoard();
      return Promise.resolve();
    }
    return api("/api/home").then(function (data) {
      homeItems = data.items || [];
      paintHomeBoard();
    });
  }

  function homeCard(acct) {
    var card = document.createElement("article");
    card.className = "card acct-card";
    card.setAttribute("data-abbr", acct.abbr || "");
    var top = document.createElement("div");
    top.className = "acct-card-top";
    top.appendChild(accountMark(acct, "tile"));
    var name = document.createElement("strong");
    name.textContent = acct.name || "";
    top.appendChild(name);
    card.appendChild(top);
    var statusRow = document.createElement("div");
    statusRow.className = "acct-status-row";
    statusRow.appendChild(healthPill(acct.health));
    var renew = document.createElement("span");
    renew.className = "row-meta acct-renewal";
    renew.textContent = "Renewal " + ((acct.contract && acct.contract.renewal_on) || "—");
    statusRow.appendChild(renew);
    card.appendChild(statusRow);
    var bar = document.createElement("div");
    bar.className = "health-bar";
    var i = document.createElement("i");
    i.style.width = Math.max(0, Math.min(100, (acct.health && acct.health.score) || 0)) + "%";
    bar.appendChild(i);
    card.appendChild(bar);
    var meet = acct.next_meeting || {};
    var meetBox = document.createElement("div");
    meetBox.className = "acct-meeting";
    var meetLab = document.createElement("div");
    meetLab.className = "acct-meeting-label";
    meetLab.textContent = meet.status === "proposed" ? "Proposed meeting" : "Next meeting";
    meetBox.appendChild(meetLab);
    if (meet.title) {
      var meetTitle = document.createElement("div");
      meetTitle.className = "acct-meeting-title";
      meetTitle.textContent = meet.title;
      meetBox.appendChild(meetTitle);
      var meetWhen = document.createElement("div");
      meetWhen.className = "acct-meeting-when";
      meetWhen.textContent = formatWhen(meet.start_at) + (meet.status === "proposed" ? " · proposed" : "");
      meetBox.appendChild(meetWhen);
    } else {
      var none = document.createElement("div");
      none.className = "acct-meeting-when";
      none.textContent = "Nothing on the calendar";
      meetBox.appendChild(none);
    }
    card.appendChild(meetBox);
    var stats = acct.stats || {};
    var pills = document.createElement("div");
    pills.className = "stat-pills";
    [
      [stats.new_tickets || 0, "new ticket", "new tickets"],
      [stats.new_email || 0, "new email", "new emails"],
      [stats.new_chat || 0, "new Slack/Teams", "new Slack/Teams"],
      [stats.new_calendar || 0, "new invite", "new invites"],
    ].forEach(function (pair) {
      var pill = document.createElement("span");
      pill.className = "stat-pill" + (pair[0] > 0 ? " is-hot" : "");
      pill.textContent = pair[0] + " " + (pair[0] === 1 ? pair[1] : pair[2]);
      pills.appendChild(pill);
    });
    card.appendChild(pills);
    card.addEventListener("click", function () {
      location.hash = "#account/" + (acct.abbr || "");
    });
    return card;
  }

  function hideChatHistory() {
    var box = $("chat-history");
    if (!box) return;
    box.hidden = true;
    box.classList.add("hidden");
    empty(box);
  }

  function setBookmarkUi(on) {
    chatBookmarked = !!on;
    var btn = $("btn-chat-bookmark");
    if (!btn) return;
    btn.classList.toggle("is-on", chatBookmarked);
    btn.setAttribute("aria-pressed", chatBookmarked ? "true" : "false");
    var tip = chatBookmarked ? "Bookmarked" : "Bookmark";
    btn.setAttribute("data-tip", tip);
    btn.setAttribute("title", tip);
    btn.setAttribute("aria-label", tip);
  }

  function updateChatChrome(scope) {
    var title = $("chat-title");
    var sub = $("chat-sub");
    var input = $("home-chat-input");
    var acct = currentAccount;
    var onBook = scope && scope !== "desk";
    if (title) title.textContent = onBook ? ((acct && acct.abbr) || "Account") + " chat" : "Desk chat";
    if (sub) {
      sub.textContent = onBook
        ? "This thread stays on " + ((acct && acct.name) || "this account") + ". /people and /ticket bound a question. @ talks to someone."
        : "Type # for a company. /people and /ticket bound a question. @ talks to someone.";
    }
    if (input) {
      input.placeholder = onBook
        ? "what was /people bob response to /ticket ACME-12?"
        : "Is there any issue with #ACME?";
    }
    renderChatSuggest(scope);
  }

  function renderChatSuggest(scope) {
    var box = $("home-chat-suggest");
    if (!box) return;
    empty(box);
    var samples = scope && scope !== "desk"
      ? [
          "Which tasks need to be done today?",
          "What tasks are due this week?",
          "What was /people bob response to /ticket ACME-12?",
          "Who is on the open projects?",
          "Any open tickets I should see?",
        ]
      : [
          "Which tasks need to be done today?",
          "What tasks are due this week?",
          "Is there any issue with #ACME?",
          "Did /people bob on #ACME reply to my last email?",
        ];
    samples.forEach(function (text) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "btn";
      b.textContent = text;
      b.addEventListener("click", function () {
        var input = $("home-chat-input");
        if (input) input.value = text;
        sendHomeChat();
      });
      box.appendChild(b);
    });
  }

  function chatOnBook() {
    return !!(chatScope && chatScope !== "desk");
  }

  function resetChatMentionCache() {
    chatBooksList = null;
    chatPeopleAll = null;
    chatPeopleByBook = {};
    chatTicketsByBook = {};
    hideChatMentions();
  }

  function hideChatMentions() {
    var menu = $("chat-mention-menu");
    if (menu) {
      menu.hidden = true;
      menu.classList.add("hidden");
      empty(menu);
    }
    chatMentionToken = null;
    chatMentionItems = [];
    chatMentionHi = 0;
  }

  function chatMentionAt(text, caret) {
    var src = String(text || "");
    var pos = caret == null ? src.length : caret;
    var left = src.slice(0, pos);
    var slash = left.match(/(^|[^A-Za-z0-9._])(\/)([A-Za-z]*)(?:(\s+)([A-Za-z0-9._-]{0,32}))?$/);
    if (slash) {
      var cmd = slash[3] || "";
      var space = slash[4] || "";
      var rest = slash[5] || "";
      var start = left.length - 1 - cmd.length - space.length - rest.length;
      return {
        kind: "/",
        cmd: cmd.toLowerCase(),
        query: space ? rest : cmd,
        rest: rest,
        hasSpace: !!space,
        start: start,
        end: pos,
      };
    }
    var m = left.match(/(^|[^A-Za-z0-9._])([#@])([A-Za-z0-9._-]{0,32})$/);
    if (!m) return null;
    var kind = m[2];
    var query = m[3] || "";
    var start = left.length - kind.length - query.length;
    return { kind: kind, query: query, cmd: "", rest: "", hasSpace: false, start: start, end: pos };
  }

  function personHandle(person) {
    var email = String((person && person.email) || "");
    var local = email.split("@")[0] || "";
    var firstLocal = local.split(/[._-]/)[0] || "";
    var name = String((person && person.name) || "").trim();
    var first = (name.split(/\s+/)[0] || "").toLowerCase();
    var handle = (first || firstLocal || local || "person").toLowerCase();
    return handle.replace(/[^a-z0-9._-]/g, "") || "person";
  }

  function loadChatBooks() {
    if (homeItems && homeItems.length) return Promise.resolve(homeItems);
    if (chatBooksList) return Promise.resolve(chatBooksList);
    return api("/api/accounts").then(function (data) {
      chatBooksList = data.items || [];
      return chatBooksList;
    }).catch(function () {
      return [];
    });
  }

  function loadChatTickets() {
    if (!(chatOnBook() && currentAccount && currentAccount.account_id)) {
      return Promise.resolve([]);
    }
    var aid = currentAccount.account_id;
    if (chatTicketsByBook[aid]) return Promise.resolve(chatTicketsByBook[aid]);
    return api("/api/tickets?account_id=" + encodeURIComponent(aid)).then(function (data) {
      chatTicketsByBook[aid] = data.items || [];
      return chatTicketsByBook[aid];
    }).catch(function () {
      return [];
    });
  }

  function loadChatPeople() {
    if (chatOnBook() && currentAccount && currentAccount.account_id) {
      var aid = currentAccount.account_id;
      if (chatPeopleByBook[aid]) return Promise.resolve(chatPeopleByBook[aid]);
      return api("/api/people?account_id=" + encodeURIComponent(aid)).then(function (data) {
        var abbr = currentAccount.abbr || "";
        var rows = (data.items || []).map(function (p) {
          return Object.assign({}, p, { _abbr: abbr, _book: currentAccount.name || abbr });
        });
        chatPeopleByBook[aid] = rows;
        return rows;
      }).catch(function () {
        return [];
      });
    }
    if (chatPeopleAll) return Promise.resolve(chatPeopleAll);
    return Promise.all([loadChatBooks(), api("/api/people")]).then(function (parts) {
      var books = parts[0] || [];
      var byId = {};
      books.forEach(function (a) {
        byId[a.account_id] = a;
      });
      var rows = ((parts[1] && parts[1].items) || []).map(function (p) {
        var a = byId[p.account_id] || {};
        return Object.assign({}, p, { _abbr: a.abbr || "", _book: a.name || a.abbr || "" });
      });
      chatPeopleAll = rows;
      return rows;
    }).catch(function () {
      return [];
    });
  }

  function mapPeopleItems(people, query, insertKind) {
    var q = String(query || "").toLowerCase();
    return (people || []).filter(function (p) {
      if (!q) return true;
      var handle = personHandle(p);
      var blob = (handle + " " + (p.name || "") + " " + (p.email || "") + " " + (p._abbr || "")).toLowerCase();
      return blob.indexOf(q) >= 0;
    }).slice(0, 12).map(function (p) {
      var handle = personHandle(p);
      var hint = chatOnBook()
        ? (p.title || p.email || "")
        : ((p._abbr ? "#" + p._abbr : "") + (p.title ? " · " + p.title : ""));
      var insert = insertKind === "/" ? "/people " + handle : "@" + handle;
      return {
        kind: insertKind,
        insert: insert,
        title: p.name || handle,
        hint: hint,
        value: handle,
        abbr: p._abbr || "",
      };
    });
  }

  function mentionItems(tok) {
    tok = tok || {};
    var kind = tok.kind || "";
    var q = String(tok.query || "").toLowerCase();
    if (kind === "#") {
      if (chatOnBook()) return Promise.resolve([]);
      return loadChatBooks().then(function (books) {
        return (books || []).filter(function (a) {
          if (!q) return true;
          var blob = ((a.abbr || "") + " " + (a.name || "") + " " + (a.slug || "")).toLowerCase();
          return blob.indexOf(q) >= 0;
        }).slice(0, 12).map(function (a) {
          return {
            kind: "#",
            insert: "#" + (a.abbr || a.slug || ""),
            title: a.abbr || a.slug || "Book",
            hint: a.name || "",
            abbr: a.abbr || "",
          };
        });
      });
    }
    if (kind === "/") {
      var cmd = String(tok.cmd || "").toLowerCase();
      var peopleExact = cmd === "people";
      var ticketExact = cmd === "ticket";
      if (!tok.hasSpace && !peopleExact && !ticketExact) {
        return Promise.resolve(SLASH.filter(function (s) {
          if (s.hidden) return false;
          if (!cmd) return true;
          return s.cmd.indexOf(cmd) === 0;
        }).map(function (s) {
          return {
            kind: "/",
            insert: "/" + s.cmd + " ",
            title: s.label,
            hint: s.example,
            value: s.cmd,
            slashCmd: true,
          };
        }));
      }
      if (peopleExact) {
        return loadChatPeople().then(function (people) {
          return mapPeopleItems(people, tok.hasSpace ? tok.rest : "", "/");
        });
      }
      if (ticketExact) {
        return loadChatTickets().then(function (rows) {
          var needle = String(tok.hasSpace ? tok.rest : "").toLowerCase();
          return (rows || []).filter(function (t) {
            if (!needle) return true;
            var blob = ((t.key || "") + " " + (t.summary || "")).toLowerCase();
            return blob.indexOf(needle) >= 0;
          }).slice(0, 12).map(function (t) {
            return {
              kind: "/",
              insert: "/ticket " + (t.key || ""),
              title: t.key || "Ticket",
              hint: t.summary || "",
              value: t.key || "",
            };
          });
        });
      }
      return Promise.resolve([]);
    }
    return loadChatPeople().then(function (people) {
      return mapPeopleItems(people, q, "@");
    });
  }

  function insertChatMention(item) {
    var input = $("home-chat-input");
    var tok = chatMentionToken;
    if (!input || !item) return;
    var text = input.value || "";
    var start = tok ? tok.start : input.selectionStart || 0;
    var end = tok ? tok.end : input.selectionEnd || start;
    var token = item.insert;
    if (token.charAt(token.length - 1) !== " ") token += " ";
    input.value = text.slice(0, start) + token + text.slice(end);
    var caret = start + token.length;
    input.focus();
    if (input.setSelectionRange) input.setSelectionRange(caret, caret);
    hideChatMentions();
    if (item.slashCmd) refreshChatMentions();
  }

  function mentionKicker(tok) {
    tok = tok || {};
    if (tok.kind === "@") return chatOnBook() ? "Talk to someone on this book" : "Talk to someone";
    if (tok.kind === "/") {
      if (tok.cmd === "people") return "Bound: person";
      if (tok.cmd === "ticket") return "Bound: ticket";
      return "Bound this question";
    }
    return "Companies";
  }

  function appendMentionOpts(box, items, hi, onPick) {
    items.forEach(function (it, idx) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "search-opt" + (idx === hi ? " is-on" : "");
      if (it.value && (it.kind === "@" || String(it.insert || "").indexOf("/people") === 0)) {
        b.setAttribute("data-handle", it.value);
      }
      if (it.slashCmd) b.setAttribute("data-cmd", it.value || "");
      var cmd = document.createElement("span");
      cmd.className = "search-opt-cmd";
      cmd.textContent = it.insert;
      var label = document.createElement("span");
      label.className = "search-opt-label";
      label.textContent = it.title;
      b.appendChild(cmd);
      b.appendChild(label);
      if (it.hint) {
        var ex = document.createElement("span");
        ex.className = "search-opt-ex";
        ex.textContent = it.hint;
        b.appendChild(ex);
      }
      b.addEventListener("mousedown", function (ev) {
        ev.preventDefault();
      });
      b.addEventListener("click", function () {
        onPick(it);
      });
      box.appendChild(b);
    });
  }

  function paintChatMentionMenu(items) {
    var menu = $("chat-mention-menu");
    if (!menu) return;
    empty(menu);
    chatMentionItems = items || [];
    if (chatMentionHi >= chatMentionItems.length) chatMentionHi = Math.max(0, chatMentionItems.length - 1);
    var kicker = document.createElement("div");
    kicker.className = "chat-mention-kicker";
    kicker.textContent = mentionKicker(chatMentionToken);
    menu.appendChild(kicker);
    if (!chatMentionItems.length) {
      var p = document.createElement("p");
      p.className = "muted";
      var emptyMsg = "No match.";
      if (chatMentionToken && chatMentionToken.kind === "@") emptyMsg = "No matching person.";
      else if (chatMentionToken && chatMentionToken.kind === "#") emptyMsg = "No matching company.";
      else if (chatMentionToken && chatMentionToken.cmd === "ticket") emptyMsg = chatOnBook() ? "No matching ticket." : "Open a book to bound a ticket.";
      else if (chatMentionToken && chatMentionToken.cmd === "people") emptyMsg = "No matching person.";
      p.textContent = emptyMsg;
      menu.appendChild(p);
    } else {
      appendMentionOpts(menu, chatMentionItems, chatMentionHi, insertChatMention);
    }
    menu.hidden = false;
    menu.classList.remove("hidden");
  }

  function refreshChatMentions() {
    var input = $("home-chat-input");
    if (!input) return;
    var tok = chatMentionAt(input.value, input.selectionStart);
    if (!tok || (tok.kind === "#" && chatOnBook())) {
      hideChatMentions();
      return;
    }
    chatMentionToken = tok;
    chatMentionHi = 0;
    var gen = ++chatMentionGen;
    mentionItems(tok).then(function (items) {
      if (gen !== chatMentionGen) return;
      var nowTok = chatMentionAt(input.value, input.selectionStart);
      if (!nowTok || (nowTok.kind === "#" && chatOnBook())) {
        hideChatMentions();
        return;
      }
      if (!items.length && nowTok.kind === "/" && nowTok.hasSpace && nowTok.cmd !== "people" && nowTok.cmd !== "ticket") {
        hideChatMentions();
        return;
      }
      paintChatMentionMenu(items);
    });
  }

  function chatMentionMenuOpen() {
    var menu = $("chat-mention-menu");
    return !!(menu && !menu.hidden);
  }

  function bindChatMentions() {
    var input = $("home-chat-input");
    if (!input || input._mentionBound) return;
    input._mentionBound = true;
    input.addEventListener("focus", function () {
      loadChatBooks();
      loadChatPeople();
      loadChatTickets();
    });
    input.addEventListener("input", refreshChatMentions);
    input.addEventListener("click", refreshChatMentions);
    input.addEventListener("keydown", function (ev) {
      if (!chatMentionMenuOpen()) return;
      if (ev.key === "Escape") {
        ev.preventDefault();
        hideChatMentions();
        return;
      }
      if (ev.key === "ArrowDown") {
        ev.preventDefault();
        chatMentionHi = Math.min(chatMentionItems.length - 1, chatMentionHi + 1);
        paintChatMentionMenu(chatMentionItems);
        return;
      }
      if (ev.key === "ArrowUp") {
        ev.preventDefault();
        chatMentionHi = Math.max(0, chatMentionHi - 1);
        paintChatMentionMenu(chatMentionItems);
        return;
      }
      if (ev.key === "Enter" || ev.key === "Tab") {
        if (!chatMentionItems.length) return;
        ev.preventDefault();
        insertChatMention(chatMentionItems[chatMentionHi] || chatMentionItems[0]);
      }
    });
    input.addEventListener("blur", function () {
      setTimeout(function () {
        if (document.activeElement === input) return;
        hideChatMentions();
      }, 120);
    });
    document.addEventListener("click", function (ev) {
      var menu = $("chat-mention-menu");
      if (!menu || menu.hidden) return;
      if (menu.contains(ev.target) || ev.target === input) return;
      hideChatMentions();
    });
  }

  function syncChatScope(scope) {
    scope = scope || "desk";
    hideChatMentions();
    updateChatChrome(scope);
    if (scope === chatScope) return;
    chatScope = scope;
    chatPeopleAll = null;
    homeChatId = "";
    setBookmarkUi(false);
    var log = $("home-chat-log");
    if (log) empty(log);
    hideChatHistory();
    loadLatestChat(scope);
  }

  function loadLatestChat(scope) {
    return api("/api/chats?account_id=" + encodeURIComponent(scope || chatScope || "desk")).then(function (data) {
      var items = data.items || [];
      items.sort(function (a, b) {
        return String(b.updated_at || "").localeCompare(String(a.updated_at || ""));
      });
      if (items[0] && items[0]._id) return openChat(items[0]._id);
      return null;
    }).catch(function () {
      return null;
    });
  }

  function openChat(chatId) {
    if (!chatId) return Promise.resolve(null);
    return api("/api/chats/" + encodeURIComponent(chatId)).then(function (doc) {
      homeChatId = doc._id || chatId;
      setBookmarkUi(!!doc.bookmarked);
      var log = $("home-chat-log");
      if (log) empty(log);
      (doc.messages || []).forEach(function (msg) {
        if (msg.role !== "user" && msg.role !== "assistant") return;
        if (msg.tool_calls) return;
        appendChat(msg.role === "user" ? "user" : "assistant", msg.content || "", msg.at);
      });
      return doc;
    });
  }

  function startNewChat() {
    homeChatId = "";
    setBookmarkUi(false);
    hideChatHistory();
    var log = $("home-chat-log");
    if (log) empty(log);
    var input = $("home-chat-input");
    if (input) input.focus();
  }

  function toggleChatHistory() {
    var box = $("chat-history");
    if (!box) return;
    if (!box.hidden) {
      hideChatHistory();
      return;
    }
    box.hidden = false;
    box.classList.remove("hidden");
    empty(box);
    var loading = document.createElement("p");
    loading.className = "muted";
    loading.textContent = "Loading…";
    box.appendChild(loading);
    api("/api/chats?account_id=" + encodeURIComponent(chatScope || "desk")).then(function (data) {
      empty(box);
      var items = data.items || [];
      var head = document.createElement("p");
      head.className = "chat-hist-scope";
      head.textContent = chatScope && chatScope !== "desk"
        ? "Chats for " + ((currentAccount && currentAccount.abbr) || "this book")
        : "All-accounts chats";
      box.appendChild(head);
      if (!items.length) {
        var p = document.createElement("p");
        p.className = "muted";
        p.textContent = "No chats in this scope yet. Ask something, then bookmark to keep it.";
        box.appendChild(p);
        return;
      }
      items.forEach(function (item) {
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "chat-hist-item" + (item._id === homeChatId ? " is-on" : "");
        var left = document.createElement("div");
        var t = document.createElement("div");
        t.className = "chat-hist-title";
        t.textContent = item.title || "Untitled";
        var m = document.createElement("div");
        m.className = "chat-hist-meta";
        var bits = [formatAgo(item.updated_at || item.created_at) || formatWhen(item.updated_at || item.created_at)];
        if (item.account_abbr) bits.push(item.account_abbr);
        if (item.project) bits.push(item.project);
        m.textContent = bits.filter(Boolean).join(" · ");
        left.appendChild(t);
        left.appendChild(m);
        btn.appendChild(left);
        if (item.bookmarked) {
          var star = document.createElement("span");
          star.className = "chat-hist-star";
          star.textContent = "Saved";
          btn.appendChild(star);
        }
        btn.addEventListener("click", function () {
          openChat(item._id).then(hideChatHistory);
        });
        box.appendChild(btn);
      });
    }).catch(function (err) {
      empty(box);
      var p = document.createElement("p");
      p.className = "muted";
      p.textContent = String(err.message || err);
      box.appendChild(p);
    });
  }

  function toggleChatBookmark() {
    if (!homeChatId) {
      toast("Ask something first, then bookmark.");
      return;
    }
    var next = !chatBookmarked;
    api("/api/chats/" + encodeURIComponent(homeChatId), {
      method: "PATCH",
      body: JSON.stringify({ bookmarked: next }),
    }).then(function (doc) {
      setBookmarkUi(!!(doc && doc.bookmarked));
      toast(chatBookmarked ? "Bookmarked" : "Bookmark removed");
      var hist = $("chat-history");
      if (hist && !hist.hidden) {
        hideChatHistory();
        toggleChatHistory();
      }
    }).catch(function (err) {
      toast(String(err.message || err));
    });
  }

  function parseChatDraft(text) {
    var out = { abbr: "", to: [], cc: [], emails: [], tickets: [], titleHint: "", subject: "" };
    var t = String(text || "");
    var book = t.match(/#\{([A-Za-z0-9][A-Za-z0-9._-]{0,31})\}/)
      || t.match(/(?:^|[^A-Za-z0-9])#(?!\{)(?!(?:account|compose|help|home|settings|actions|reports)\b)([A-Za-z][A-Za-z0-9_]{1,31})(?!-\d)(?![A-Za-z0-9_])/i);
    if (book) out.abbr = book[1];
    function lineList(label) {
      var re = new RegExp("(?:^|\\n)\\s*" + label + "\\s*:\\s*(.+)$", "im");
      var hit = t.match(re);
      if (!hit) return [];
      return hit[1].split(/[,;]/).map(function (s) { return s.trim(); }).filter(Boolean);
    }
    out.to = lineList("To");
    out.cc = lineList("Cc");
    var sub = t.match(/(?:^|\n)\s*Subject\s*:\s*(.+)$/im);
    if (sub) out.subject = sub[1].trim();
    out.emails = t.match(/[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}/gi) || [];
    out.tickets = t.match(/\b[A-Z]{2,6}-\d+\b/g) || [];
    var title = t.match(/\b(?:now|promoted to|title[:\s]+)\s*(Director|VP|Vice President|Manager|Chief[^,\n]{0,40}|CEO|CTO|CFO)\b/i);
    if (title) out.titleHint = title[1];
    return out;
  }

  function chatLinkEl(label, kind, val) {
    var a = document.createElement("a");
    a.className = "chat-link";
    a.href = "#";
    a.textContent = label;
    a.setAttribute("data-kind", kind);
    a.setAttribute("data-val", val);
    a.addEventListener("click", onChatLink);
    return a;
  }

  function onChatLink(ev) {
    ev.preventDefault();
    var a = ev.currentTarget;
    var kind = a.getAttribute("data-kind") || "";
    var val = a.getAttribute("data-val") || "";
    var abbr = (currentAccount && currentAccount.abbr) || "";
    if (kind === "hash") {
      location.hash = val.charAt(0) === "#" ? val : "#" + val;
      return;
    }
    if (kind === "book") {
      location.hash = "#account/" + val;
      return;
    }
    if (kind === "compose") {
      location.hash = "#compose/" + val;
      return;
    }
    if (kind === "ticket") {
      if (!abbr && currentAccount) abbr = currentAccount.abbr;
      if (!abbr) return;
      accountQ = "/ticket " + val;
      var qEl = $("account-q");
      if (qEl) qEl.value = accountQ;
      location.hash = "#account/" + abbr + "/tickets";
      return;
    }
    if (kind === "slash") {
      if (!abbr) return;
      var spec = null;
      var cmd = String(val.replace(/^\//, "").split(/\s+/)[0] || "").toLowerCase();
      SLASH.forEach(function (s) {
        if (s.cmd === cmd) spec = s;
      });
      accountQ = val.charAt(0) === "/" ? val : "/" + val;
      var box = $("account-q");
      if (box) box.value = accountQ;
      location.hash = "#account/" + abbr + "/" + ((spec && spec.tab) || "timeline");
      return;
    }
    if (kind === "person") {
      var handle = String(val || "").replace(/^@/, "");
      if (!abbr) return;
      accountQ = "@" + handle;
      var peopleQ = $("account-q");
      if (peopleQ) peopleQ.value = accountQ;
      location.hash = "#account/" + abbr + "/people";
      return;
    }
    if (kind === "mail" && currentAccount) {
      openPersonForm(currentAccount, { email: val, name: "", title: "" });
    }
  }

  function fillChatBody(el, text) {
    empty(el);
    var raw = String(text || "");
    if (!raw) return;
    var re = /#\{[A-Za-z0-9][A-Za-z0-9._-]{0,31}\}|#(?:account|compose|help|home|settings)\/[^\s)\]>]+|#(?!\{)(?!(?:account|compose|help|home|settings|actions|reports)\b)[A-Za-z][A-Za-z0-9_]{1,31}(?!-\d)(?![A-Za-z0-9_])|\/(?:ticket|project|people|email|chat|slack|teams|calendar|sf)\s+[^\s,;]+|\b[A-Z]{2,6}-\d+\b|[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}|(?<![A-Za-z0-9._])@[A-Za-z][A-Za-z0-9._-]*/gi;
    var last = 0;
    var m;
    while ((m = re.exec(raw))) {
      if (m.index > last) el.appendChild(document.createTextNode(raw.slice(last, m.index)));
      var tok = m[0];
      if (tok.charAt(0) === "#" && tok.charAt(1) === "{") {
        el.appendChild(chatLinkEl(tok, "book", tok.slice(2, -1)));
      } else if (tok.charAt(0) === "#" && tok.indexOf("/") < 0) {
        el.appendChild(chatLinkEl(tok, "book", tok.slice(1)));
      } else if (tok.charAt(0) === "#") {
        el.appendChild(chatLinkEl(tok, "hash", tok));
      } else if (tok.charAt(0) === "/") {
        el.appendChild(chatLinkEl(tok, "slash", tok));
      } else if (tok.charAt(0) === "@") {
        el.appendChild(chatLinkEl(tok, "person", tok.replace(/^@/, "")));
      } else if (tok.indexOf("@") >= 0) {
        el.appendChild(chatLinkEl(tok, "mail", tok));
      } else {
        el.appendChild(chatLinkEl(tok, "ticket", tok));
      }
      last = m.index + tok.length;
    }
    if (last < raw.length) el.appendChild(document.createTextNode(raw.slice(last)));
  }

  function chatOpBtn(label, fn) {
    var b = document.createElement("button");
    b.type = "button";
    b.className = "btn btn-ghost";
    b.textContent = label;
    b.addEventListener("click", fn);
    return b;
  }

  function attachChatOps(turn, text) {
    var draft = parseChatDraft(text);
    var abbr = draft.abbr || (currentAccount && currentAccount.abbr) || "";
    var ops = document.createElement("div");
    ops.className = "chat-ops";
    if (abbr) {
      ops.appendChild(chatOpBtn("Open", function () {
        if (draft.tickets[0] && abbr) {
          accountQ = "/ticket " + draft.tickets[0];
          var qEl = $("account-q");
          if (qEl) qEl.value = accountQ;
          location.hash = "#account/" + abbr + "/tickets";
        } else {
          location.hash = "#account/" + abbr;
        }
      }));
    }
    if (abbr || currentAccount) {
      ops.appendChild(chatOpBtn("Compose", function () {
        var seed = { to: draft.to.length ? draft.to : [], cc: draft.cc.slice(), subject: draft.subject || "" };
        if (currentAccount && (currentAccount.abbr || "").toLowerCase() === String(abbr || currentAccount.abbr).toLowerCase()) {
          if (window.CSMCompose) window.CSMCompose.open(currentAccount, seed);
          return;
        }
        pendingComposeSeed = seed;
        location.hash = "#compose/" + (abbr || (currentAccount && currentAccount.abbr) || "");
      }));
    }
    if (homeChatId) {
      ops.appendChild(chatOpBtn("Add note", function () {
        openChatNotes(text);
      }));
    }
    if ((draft.emails[0] || draft.to[0]) && (currentAccount || abbr)) {
      ops.appendChild(chatOpBtn(draft.titleHint ? "Update title" : "Add person", function () {
        var addr = draft.to[0] || draft.emails[0];
        var hint = { email: addr, name: "", title: draft.titleHint || "" };
        if (currentAccount) openPersonForm(currentAccount, hint);
        else location.hash = "#account/" + abbr + "/people";
      }));
    }
    if (!ops.firstChild) return;
    turn.appendChild(ops);
  }

  function prettyChatText(text) {
    var raw = String(text || "").trim();
    if (!raw) return "";
    if (raw.charAt(0) !== "[" && raw.charAt(0) !== "{") return String(text || "");
    try {
      var data = JSON.parse(raw);
    } catch (e) {
      return String(text || "");
    }
    if (Array.isArray(data)) {
      if (!data.length) return "Nothing to show.";
      if (data[0] && data[0].key) {
        var open = data.filter(function (row) {
          return row.status !== "done" && row.status !== "cancelled";
        });
        var lines = [open.length + " open ticket" + (open.length === 1 ? "" : "s") + ":"];
        open.slice(0, 12).forEach(function (row) {
          lines.push("- " + (row.key || "—") + ": " + (row.summary || "—") + " (" + (row.priority || "—") + " · " + String(row.status || "").replace(/_/g, " ") + ")");
        });
        return lines.join("\n");
      }
      return data.slice(0, 12).map(function (row) {
        if (row && typeof row === "object") return "- " + (row.title || row.subject || row.key || JSON.stringify(row));
        return "- " + row;
      }).join("\n");
    }
    if (data && typeof data === "object") {
      if (data.error) return String(data.error);
      if (data.key) return prettyChatText(JSON.stringify([data]));
    }
    return String(text || "");
  }

  function formatAgo(iso) {
    if (!iso) return "";
    var at = new Date(iso);
    if (isNaN(at.getTime())) return "";
    var sec = Math.round((Date.now() - at.getTime()) / 1000);
    var future = sec < 0;
    sec = Math.abs(sec);
    if (sec < 45) return future ? "in a moment" : "just now";
    var mins = Math.round(sec / 60);
    if (mins < 60) {
      var mlabel = mins === 1 ? "minute" : "minutes";
      return future ? "in " + mins + " " + mlabel : mins + " " + mlabel + " ago";
    }
    var hours = Math.round(mins / 60);
    if (hours < 24) {
      var hlabel = hours === 1 ? "hour" : "hours";
      return future ? "in " + hours + " " + hlabel : hours + " " + hlabel + " ago";
    }
    var days = Math.round(hours / 24);
    var dlabel = days === 1 ? "day" : "days";
    return future ? "in " + days + " " + dlabel : days + " " + dlabel + " ago";
  }

  function stampChatWhen(turn, role, at) {
    if (!turn) return;
    var old = turn.querySelector(".chat-when");
    if (old) old.remove();
    var label = formatAgo(at);
    if (!label) return;
    var when = document.createElement("div");
    when.className = "chat-when";
    when.textContent = (role === "user" ? "Asked " : "Replied ") + label;
    var ops = turn.querySelector(".chat-ops");
    if (ops) turn.insertBefore(when, ops);
    else turn.appendChild(when);
  }

  function finishChatMessage(el, text, role) {
    if (!el) return;
    var pretty = prettyChatText(text);
    fillChatBody(el, pretty);
    var turn = el.parentNode;
    if (!turn) return;
    var old = turn.querySelector(".chat-ops");
    if (old) old.remove();
    if (role === "assistant") attachChatOps(turn, pretty);
    stampChatWhen(turn, role, el.getAttribute("data-at"));
  }

  function openChatNotes(seed) {
    if (!homeChatId) {
      toast("Ask something first, then add a note.");
      return;
    }
    var sheet = openSheet("Chat notes");
    if (!sheet) return;
    var aid = chatScope && chatScope !== "desk" ? chatScope : ((currentAccount && currentAccount.account_id) || "desk");
    mountNoteEditor(sheet, { _id: homeChatId, account_id: aid }, "chats");
    var ta = sheet.querySelector("textarea");
    if (ta && seed && !(ta.value || "").trim()) ta.value = String(seed || "").slice(0, 400);
  }

  function appendChat(role, text, at) {
    var log = $("home-chat-log");
    if (!log) return null;
    var turn = document.createElement("div");
    turn.className = "chat-turn is-" + role;
    var el = document.createElement("div");
    el.className = "chat-bubble " + role;
    el.setAttribute("data-at", at || new Date().toISOString());
    turn.appendChild(el);
    log.appendChild(turn);
    if (text) finishChatMessage(el, text, role);
    else stampChatWhen(turn, role, el.getAttribute("data-at"));
    log.scrollTop = log.scrollHeight;
    return el;
  }

  function sendHomeChat() {
    var input = $("home-chat-input");
    if (!input) return;
    var message = (input.value || "").trim();
    if (!message) return;
    input.value = "";
    appendChat("user", message);
    var bubble = appendChat("assistant", "");
    var payload = { message: message };
    if (chatScope && chatScope !== "desk") payload.account_id = chatScope;
    if (homeChatId) payload.chat_id = homeChatId;
    fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).then(function (res) {
      if (!res.ok || !res.body) throw new Error("chat failed");
      var reader = res.body.getReader();
      var decoder = new TextDecoder();
      var buf = "";
      var acc = "";
      function pump() {
        return reader.read().then(function (part) {
          buf += decoder.decode(part.value || new Uint8Array(), { stream: !part.done });
          var chunks = buf.split("\n\n");
          buf = chunks.pop() || "";
          chunks.forEach(function (block) {
            var ev = "";
            var data = "";
            block.split("\n").forEach(function (line) {
              if (line.indexOf("event:") === 0) ev = line.slice(6).trim();
              if (line.indexOf("data:") === 0) data = line.slice(5).trim();
            });
            if (ev === "token" && data) {
              try { acc += JSON.parse(data); } catch (e) { acc += data; }
              if (bubble) bubble.textContent = acc;
            }
            if (ev === "done" && data) {
              try {
                var done = JSON.parse(data);
                if (done.chat_id) homeChatId = done.chat_id;
              } catch (e) {}
              if (bubble) finishChatMessage(bubble, acc, "assistant");
            }
          });
          var log = $("home-chat-log");
          if (log) log.scrollTop = log.scrollHeight;
          if (!part.done) return pump();
        });
      }
      return pump();
    }).catch(function (err) {
      if (bubble) bubble.textContent = String(err.message || err);
    });
  }

  function markAccountTab(tab) {
    var tabs = $("account-tabs");
    if (!tabs) return;
    var want = canonicalTab(tab);
    tabs.querySelectorAll(".tab").forEach(function (b) {
      b.classList.toggle("is-on", b.getAttribute("data-tab") === want);
    });
  }

  function loadAccount(abbr, tab) {
    tab = canonicalTab(tab || "timeline");
    var want = (abbr || "").toLowerCase();
    if (currentAccount && lastAccountAbbr === want && $("account-tabs") && $("account-tabs").firstChild) {
      currentTab = canonicalTab(tab || "timeline");
      markAccountTab(currentTab);
      syncAccountTools(currentTab);
      return Promise.resolve(renderPane(currentAccount, currentTab));
    }
    if (want !== lastAccountAbbr) {
      empty($("account-head"));
      empty($("account-tabs"));
      empty($("account-pane"));
    }
    return api("/api/accounts/by-abbr/" + encodeURIComponent(abbr)).then(function (acct) {
      currentAccount = acct;
      if ((acct.abbr || "").toLowerCase() !== lastAccountAbbr) {
        lastAccountAbbr = (acct.abbr || "").toLowerCase();
        accountQ = "";
        accountProject = "";
        peopleAllProjects = false;
        var qEl = $("account-q");
        if (qEl) qEl.value = "";
      }
      renderAccountHead(acct);
      renderHomeCrumb(acct);
      renderTabs(acct, tab);
      return api("/api/projects?account_id=" + encodeURIComponent(acct.account_id)).then(function (data) {
        accountProjects = data.items || [];
        fillProjectSelect();
        syncAccountTools(tab);
        return renderPane(acct, tab);
      });
    });
  }

  function fillProjectSelect() {
    var sel = $("account-project");
    if (!sel) return;
    var keep = accountProject;
    empty(sel);
    var all = document.createElement("option");
    all.value = "";
    all.textContent = "All projects";
    sel.appendChild(all);
    accountProjects.forEach(function (p) {
      var opt = document.createElement("option");
      opt.value = p._id || "";
      opt.textContent = p.name || p._id;
      sel.appendChild(opt);
    });
    sel.value = keep;
    accountProject = sel.value;
  }

  function syncAccountTools(tab) {
    var sel = $("account-project");
    if (!sel) return;
    var show = ["timeline", "tickets", "people", "orgchart", "accountteam", "projects"].indexOf(tab) >= 0;
    sel.hidden = !show;
  }

  function projectName(id) {
    var found = accountProjects.filter(function (p) { return p._id === id; })[0];
    return found ? found.name : id;
  }

  function renderAccountHead(acct) {
    var head = $("account-head");
    empty(head);
    var left = document.createElement("div");
    var titleRow = document.createElement("div");
    titleRow.className = "account-title-row";
    if (logoSrc(acct)) {
      titleRow.appendChild(accountMark(acct, "lg"));
    } else {
      var sw = document.createElement("i");
      sw.className = "acct-swatch acct-swatch-lg";
      sw.style.background = acct.color || "#0B3D91";
      sw.title = acct.name || acct.abbr || "";
      titleRow.appendChild(sw);
    }
    titleRow.appendChild(healthPill(acct.health));
    left.appendChild(titleRow);
    var renew = document.createElement("p");
    renew.className = "muted";
    renew.textContent = "Renewal " + ((acct.contract && acct.contract.renewal_on) || "—");
    left.appendChild(renew);
    head.appendChild(left);
    var actions = document.createElement("div");
    actions.className = "toolbar-actions";
    var compose = document.createElement("button");
    compose.className = "btn btn-primary";
    compose.type = "button";
    compose.textContent = "Compose";
    compose.addEventListener("click", function () {
      location.hash = "#compose/" + (acct.abbr || "");
    });
    actions.appendChild(compose);
    head.appendChild(actions);
  }

  function teamList(title, rows) {
    var wrap = document.createElement("div");
    var h = document.createElement("h3");
    h.textContent = title;
    wrap.appendChild(h);
    var ul = document.createElement("ul");
    ul.className = "people-list";
    (rows || []).forEach(function (row) {
      var li = document.createElement("li");
      li.textContent = (row.name || row.person_id || "") + " · " + (row.role || "");
      ul.appendChild(li);
    });
    wrap.appendChild(ul);
    return wrap;
  }

  function renderTabs(acct, tab) {
    tab = canonicalTab(tab);
    var counts = acct.input_counts || {};
    var tabs = $("account-tabs");
    empty(tabs);
    ACCOUNT_TABS.forEach(function (name) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "tab" + (name === tab ? " is-on" : "");
      b.setAttribute("data-tab", name);
      var label = document.createElement("span");
      label.textContent = tabLabel(name);
      b.appendChild(label);
      var n = counts[name];
      if (n != null) {
        var badge = document.createElement("span");
        badge.className = "tab-count";
        badge.textContent = String(n);
        b.appendChild(badge);
      }
      b.addEventListener("click", function () {
        location.hash = "#account/" + acct.abbr + "/" + name;
      });
      tabs.appendChild(b);
    });
  }

  function renderPane(acct, tab) {
    var pane = $("account-pane");
    empty(pane);
    var aid = acct.account_id;
    if (tab === "tickets") return fillList(pane, "/api/tickets" + accountQs(aid, true), ticketRow);
    if (tab === "email") return fillList(pane, "/api/threads?account_id=" + encodeURIComponent(aid), threadRow);
    if (tab === "chat") return fillChat(pane, aid);
    if (tab === "salesforce") return fillSalesforce(pane, aid);
    if (tab === "calendar") return fillList(pane, "/api/calendar?account_id=" + encodeURIComponent(aid), calRow);
    if (tab === "projects") return fillProjects(pane, acct);
    if (tab === "people") return fillPeople(pane, acct);
    if (tab === "orgchart") return fillOrgChart(pane, acct);
    if (tab === "accountteam") return fillAccountTeam(pane, acct);
    return fillTimeline(pane, timelineFetchUrl(aid));
  }

  function slashState(raw) {
    var t = String(raw || "");
    if (t.charAt(0) !== "/") {
      return { open: false, cmd: "", rest: t, tab: "", note: false, exact: null, matches: [] };
    }
    var space = t.indexOf(" ");
    var cmd = (space < 0 ? t.slice(1) : t.slice(1, space)).toLowerCase();
    var rest = space < 0 ? "" : t.slice(space + 1);
    var matches = cmd
      ? SLASH.filter(function (s) { return !s.hidden && s.cmd.indexOf(cmd) === 0; })
      : SLASH.filter(function (s) { return !s.hidden; });
    var exact = null;
    SLASH.forEach(function (s) {
      if (s.cmd === cmd) exact = s;
    });
    return {
      open: true,
      cmd: cmd,
      rest: rest,
      tab: exact ? exact.tab : "",
      note: !!(exact && exact.note),
      exact: exact,
      matches: matches,
    };
  }

  function atPersonState(raw) {
    var t = String(raw || "");
    var m = t.match(/^@([A-Za-z0-9._-]*)\s*(.*)$/);
    if (!m) return { open: false, handle: "", rest: t };
    return { open: true, handle: m[1] || "", rest: (m[2] || "").trim() };
  }

  function searchNeedle() {
    var at = atPersonState(accountQ);
    if (at.open) return at.handle || at.rest || "";
    var s = slashState(accountQ);
    if (accountQ.charAt(0) === "/") return s.exact ? s.rest : "";
    return accountQ;
  }

  function hideSlashSuggest() {
    var box = $("account-suggest");
    if (!box) return;
    box.hidden = true;
    box.classList.add("hidden");
    empty(box);
  }

  function pickSlash(cmd) {
    var qEl = $("account-q");
    accountQ = "/" + cmd + " ";
    if (qEl) qEl.value = accountQ;
    hideSlashSuggest();
    applyAccountSearch(true);
    if (cmd === "people") {
      renderPersonSuggest(true, "");
    }
    if (qEl) qEl.focus();
  }

  function pickPerson(handle, asSlash) {
    var qEl = $("account-q");
    var name = String(handle || "").replace(/^@/, "");
    accountQ = asSlash ? "/people " + name : "@" + name;
    if (qEl) qEl.value = accountQ;
    hideSlashSuggest();
    applyAccountSearch(true);
    if (qEl) qEl.focus();
  }

  function renderPersonSuggest(asSlash, handle) {
    var box = $("account-suggest");
    if (!box) return;
    var q = handle || "";
    if (!asSlash) {
      var at = atPersonState(accountQ);
      if (!at.open) {
        hideSlashSuggest();
        return;
      }
      q = at.handle;
    }
    var gen = ++personSuggestGen;
    mentionItems({ kind: asSlash ? "/" : "@", cmd: asSlash ? "people" : "", query: q, rest: q, hasSpace: true }).then(function (items) {
      if (gen !== personSuggestGen) return;
      empty(box);
      slashIndex = 0;
      var kicker = document.createElement("div");
      kicker.className = "chat-mention-kicker";
      kicker.textContent = asSlash ? "People" : "Talk to";
      box.appendChild(kicker);
      if (!items.length) {
        var p = document.createElement("p");
        p.className = "muted";
        p.textContent = "No matching person.";
        box.appendChild(p);
      } else {
        appendMentionOpts(box, items, 0, function (it) {
          pickPerson(it.value, asSlash);
        });
      }
      box.hidden = false;
      box.classList.remove("hidden");
    });
  }

  function renderSlashSuggest() {
    var box = $("account-suggest");
    if (!box) return;
    if (atPersonState(accountQ).open) {
      renderPersonSuggest(false);
      return;
    }
    var s = slashState(accountQ);
    if (s.exact && s.cmd === "people") {
      renderPersonSuggest(true, s.rest);
      return;
    }
    if (!s.open || s.exact && accountQ.indexOf(" ") >= 0) {
      hideSlashSuggest();
      return;
    }
    var rows = s.matches.length ? s.matches : SLASH.filter(function (row) { return !row.hidden; });
    if (!rows.length) {
      hideSlashSuggest();
      return;
    }
    empty(box);
    slashIndex = 0;
    rows.forEach(function (row, i) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "search-opt" + (i === 0 ? " is-on" : "");
      b.setAttribute("data-cmd", row.cmd);
      var cmd = document.createElement("span");
      cmd.className = "search-opt-cmd";
      cmd.textContent = "/" + row.cmd;
      var label = document.createElement("span");
      label.className = "search-opt-label";
      label.textContent = row.label;
      var ex = document.createElement("span");
      ex.className = "search-opt-ex";
      ex.textContent = row.example;
      b.appendChild(cmd);
      b.appendChild(label);
      b.appendChild(ex);
      b.addEventListener("click", function () {
        pickSlash(row.cmd);
      });
      box.appendChild(b);
    });
    box.hidden = false;
    box.classList.remove("hidden");
  }

  function applyAccountSearch(forceTab) {
    if (!currentAccount) return;
    var at = atPersonState(accountQ);
    if (at.open) {
      if ((forceTab || at.handle) && currentTab !== "people") {
        location.hash = "#account/" + currentAccount.abbr + "/people";
        return;
      }
      if (currentTab === "people") {
        renderPane(currentAccount, "people");
        return;
      }
    }
    var s = slashState(accountQ);
    if (s.exact && s.cmd === "project" && String(s.rest || "").trim().toLowerCase() === "all") {
      peopleAllProjects = true;
      if (currentTab === "people") {
        renderPane(currentAccount, "people");
        return;
      }
      location.hash = "#account/" + currentAccount.abbr + "/people";
      return;
    }
    peopleAllProjects = false;
    if (forceTab && s.exact && s.tab && s.tab !== currentTab) {
      location.hash = "#account/" + currentAccount.abbr + "/" + s.tab;
      return;
    }
    if (s.exact && s.tab && s.tab !== currentTab && accountQ.indexOf(" ") >= 0) {
      location.hash = "#account/" + currentAccount.abbr + "/" + s.tab;
      return;
    }
    renderPane(currentAccount, currentTab);
  }

  function accountQs(aid, withAccount) {
    var parts = [];
    if (withAccount) parts.push("account_id=" + encodeURIComponent(aid));
    var needle = searchNeedle();
    if (needle) parts.push("q=" + encodeURIComponent(needle));
    if (accountProject) parts.push("project_id=" + encodeURIComponent(accountProject));
    return parts.length ? "?" + parts.join("&") : "";
  }

  function fillList(pane, url, rowFn, pred) {
    return api(url).then(function (data) {
      var items = data.items || data || [];
      if (pred) items = items.filter(pred);
      var q = (searchNeedle() || "").toLowerCase();
      if (q && url.indexOf("q=") < 0) {
        items = items.filter(function (item) {
          return JSON.stringify(item).toLowerCase().indexOf(q) >= 0;
        });
      }
      if (!items.length) {
        var p = document.createElement("p");
        p.className = "muted";
        p.textContent = "Nothing here yet.";
        pane.appendChild(p);
        return;
      }
      items.forEach(function (item) {
        pane.appendChild(rowFn(item));
      });
    });
  }

  function rowEl(left, mid, right) {
    var row = document.createElement("div");
    row.className = "row";
    var a = document.createElement("div");
    a.className = "row-meta";
    a.textContent = left || "";
    var b = document.createElement("div");
    var t = document.createElement("div");
    t.className = "row-title";
    t.textContent = mid || "";
    b.appendChild(t);
    var c = document.createElement("div");
    c.className = "row-meta";
    c.textContent = right || "";
    row.appendChild(a);
    row.appendChild(b);
    row.appendChild(c);
    return row;
  }

  function kindGroup(kind) {
    kind = String(kind || "");
    if (kind.indexOf("ticket") === 0) return "ticket";
    if (kind === "email_out") return "email-out";
    if (kind.indexOf("email") === 0) return "email-in";
    if (kind === "meeting") return "meeting";
    if (kind === "slack") return "slack";
    if (kind === "teams") return "teams";
    if (kind === "salesforce") return "salesforce";
    return "note";
  }

  function kindLabel(kind) {
    var labels = {
      ticket_created: "Ticket created",
      ticket_updated: "Ticket updated",
      email_in: "Received email",
      email_out: "Sent email",
      meeting: "Meeting",
      slack: "Slack",
      teams: "Teams",
      salesforce: "Salesforce",
      note: "Note",
    };
    return labels[kind] || kind || "Activity";
  }

  function kindEmoji(kind) {
    var map = {
      ticket: "🎫",
      "email-out": "⬆️",
      "email-in": "⬇️",
      meeting: "📅",
      slack: "💬",
      teams: "👥",
      salesforce: "☁️",
      note: "📝",
    };
    return map[kindGroup(kind)] || "📝";
  }

  function pad2(n) {
    return n < 10 ? "0" + n : String(n);
  }

  function formatClock(d) {
    var h = d.getHours();
    var ap = h >= 12 ? "PM" : "AM";
    var h12 = h % 12;
    if (h12 === 0) h12 = 12;
    return h12 + ":" + pad2(d.getMinutes()) + " " + ap;
  }

  function startOfDay(d) {
    return new Date(d.getFullYear(), d.getMonth(), d.getDate());
  }

  function formatWhen(iso, now) {
    if (!iso) return "";
    var at = new Date(iso);
    if (isNaN(at.getTime())) return String(iso);
    now = now || new Date();
    var ms = now.getTime() - at.getTime();
    var mins = Math.round(Math.abs(ms) / 60000);
    var dayDiff = Math.round((startOfDay(now) - startOfDay(at)) / 86400000);
    var clock = formatClock(at);
    if (dayDiff === 0 && ms >= 0 && mins < 1) return "Today @ just now";
    if (dayDiff === 0 && ms >= 0 && mins < 60) {
      return "Today @ " + mins + (mins === 1 ? " minute ago" : " minutes ago");
    }
    if (dayDiff === 0) return "Today @ " + clock;
    if (dayDiff === 1) return "Yesterday at " + clock;
    if (dayDiff === -1) return "Tomorrow at " + clock;
    if (dayDiff >= 2 && dayDiff < 14) return dayDiff + " days ago @ " + clock;
    if (dayDiff <= -2 && dayDiff > -14) return "In " + Math.abs(dayDiff) + " days @ " + clock;
    if (dayDiff >= 14 && dayDiff < 60) {
      var weeks = Math.round(dayDiff / 7);
      return weeks + (weeks === 1 ? " week ago @ " : " weeks ago @ ") + clock;
    }
    var months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    var stamp = months[at.getMonth()] + " " + at.getDate();
    if (at.getFullYear() !== now.getFullYear()) stamp += ", " + at.getFullYear();
    return stamp + " @ " + clock;
  }

  function activityDoc(item) {
    if (item && item.a && typeof item.a === "object") {
      var nested = Object.assign({}, item.a);
      if (item._id) nested._id = item._id;
      return nested;
    }
    return item || {};
  }

  function itemTime(item) {
    var raw = (item && (item.at || item.start_at)) || "";
    var t = new Date(raw).getTime();
    return isNaN(t) ? 0 : t;
  }

  function sortTimelineItems(items) {
    return (items || []).slice().sort(function (a, b) {
      return itemTime(a) - itemTime(b);
    });
  }

  function timelineNowItem() {
    var li = document.createElement("li");
    li.className = "timeline-now-item";
    li.setAttribute("data-now", "1");
    var line = document.createElement("div");
    line.className = "tl-now";
    line.setAttribute("aria-hidden", "true");
    var label = document.createElement("span");
    label.className = "tl-now-label";
    label.textContent = "Now";
    li.appendChild(line);
    li.appendChild(label);
    return li;
  }

  function padTimelineAxis(root, layout) {
    var ul = root.querySelector(".timeline");
    if (!ul) return;
    var want = layout === "horizontal" ? "horizontal" : "vertical";
    var sc = want === "horizontal"
      ? (root.querySelector(".timeline-scroll") || root)
      : (root.closest ? (root.closest(".pane") || root) : root);
    var size = want === "horizontal" ? sc.clientWidth : sc.clientHeight;
    var pad = Math.max(32, Math.floor((size || 0) / 2));
    if (want === "horizontal") {
      ul.style.paddingLeft = pad + "px";
      ul.style.paddingRight = pad + "px";
      ul.style.paddingTop = "";
      ul.style.paddingBottom = "";
    } else {
      ul.style.paddingTop = pad + "px";
      ul.style.paddingBottom = pad + "px";
      ul.style.paddingLeft = "";
      ul.style.paddingRight = "";
    }
  }

  function scrollTimelineToNow(root, layout, opts) {
    var nowEl = root.querySelector("[data-now]");
    if (!nowEl) return;
    var behavior = (opts && opts.behavior) || "auto";
    requestAnimationFrame(function () {
      padTimelineAxis(root, layout || timelineLayout());
      requestAnimationFrame(function () {
        nowEl.scrollIntoView({ block: "center", inline: "center", behavior: behavior });
      });
    });
  }

  function applyTimelineLayout(root, layout) {
    var want = layout === "horizontal" ? "horizontal" : "vertical";
    var ul = root.querySelector(".timeline");
    if (ul) {
      ul.classList.toggle("timeline-vertical", want === "vertical");
      ul.classList.toggle("timeline-horizontal", want === "horizontal");
    }
    var scroll = root.querySelector(".timeline-scroll");
    if (scroll) scroll.classList.toggle("is-horizontal", want === "horizontal");
    var shell = root.querySelector(".timeline-shell");
    if (shell) {
      shell.classList.toggle("is-horizontal", want === "horizontal");
      shell.classList.toggle("is-vertical", want === "vertical");
    }
    root.querySelectorAll("[data-tl-layout]").forEach(function (b) {
      b.classList.toggle("is-on", b.getAttribute("data-tl-layout") === want);
    });
    scrollTimelineToNow(root, want);
  }

  function timelineWindow() {
    var p = userPrefs();
    var now = Date.now();
    return {
      now: now,
      pastDays: p.timeline_past_days,
      nextDays: p.timeline_next_days,
      since: now - p.timeline_past_days * 86400000,
      until: now + p.timeline_next_days * 86400000,
    };
  }

  function timelineFetchUrl(aid) {
    var w = timelineWindow();
    var parts = [];
    var extra = accountQs("", false);
    if (extra.charAt(0) === "?") extra = extra.slice(1);
    if (extra) parts.push(extra);
    parts.push("since=" + encodeURIComponent(new Date(w.since).toISOString()));
    parts.push("until=" + encodeURIComponent(new Date(w.until).toISOString()));
    parts.push("limit=200");
    return "/api/accounts/" + encodeURIComponent(aid) + "/timeline?" + parts.join("&");
  }

  function reloadTimeline() {
    if (!currentAccount || currentTab !== "timeline") return;
    var pane = $("account-pane");
    if (!pane) return;
    empty(pane);
    fillTimeline(pane, timelineFetchUrl(currentAccount.account_id));
  }

  function timelineRangeButtons(side) {
    var box = document.createElement("div");
    box.className = "timeline-range is-" + side;
    var current = side === "past" ? userPrefs().timeline_past_days : userPrefs().timeline_next_days;
    var pairs = side === "past"
      ? [[7, "Past 7 days"], [30, "Past 30 days"]]
      : [[7, "Next 7 days"], [30, "Next 30 days"]];
    pairs.forEach(function (pair) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "btn" + (current === pair[0] ? " is-on" : "");
      b.textContent = pair[1];
      b.setAttribute("data-tl-range", side + "-" + pair[0]);
      b.addEventListener("click", function () {
        var patch = side === "past"
          ? { timeline_past_days: pair[0] }
          : { timeline_next_days: pair[0] };
        savePreferences(patch, { calendar: false });
        reloadTimeline();
      });
      box.appendChild(b);
    });
    return box;
  }

  function timelineOrientBar(pane, layout) {
    var bar = document.createElement("div");
    bar.className = "pane-toolbar pane-toolbar-spread";
    var nowBtn = document.createElement("button");
    nowBtn.type = "button";
    nowBtn.className = "btn timeline-now-btn";
    nowBtn.textContent = "Now";
    nowBtn.title = "Scroll to now";
    nowBtn.addEventListener("click", function () {
      scrollTimelineToNow(pane, layout, { behavior: "smooth" });
    });
    bar.appendChild(nowBtn);
    var views = document.createElement("div");
    views.className = "timeline-orient";
    views.setAttribute("role", "tablist");
    views.setAttribute("aria-label", "Timeline layout");
    [["vertical", "Vertical"], ["horizontal", "Horizontal"]].forEach(function (pair) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "tab" + (layout === pair[0] ? " is-on" : "");
      b.textContent = pair[1];
      b.setAttribute("data-tl-layout", pair[0]);
      b.addEventListener("click", function () {
        savePreferences({ timeline_layout: pair[0] }, { calendar: false });
        reloadTimeline();
      });
      views.appendChild(b);
    });
    bar.appendChild(views);
    return bar;
  }

  function fillTimeline(pane, url) {
    var aid = currentAccount && currentAccount.account_id;
    var notesP = aid ? api("/api/notes?account_id=" + encodeURIComponent(aid)) : Promise.resolve({ items: [] });
    return Promise.all([api(url), notesP]).then(function (pair) {
      var items = (pair[0].items || pair[0] || []).map(activityDoc);
      var notes = pair[1].items || [];
      var byAct = {};
      notes.forEach(function (n) {
        var rid = (n.ref && n.ref.id) || "";
        if (!rid) return;
        if (!byAct[rid]) byAct[rid] = [];
        byAct[rid].push(n);
      });
      var slash = slashState(accountQ);
      if (slash.note) {
        var rest = (slash.rest || "").toLowerCase();
        items = items.filter(function (it) {
          var mine = byAct[it._id] || [];
          if (!mine.length && !(it.note_count > 0)) return false;
          if (!rest) return true;
          if (String(it.title || "").toLowerCase().indexOf(rest) >= 0) return true;
          return mine.some(function (n) {
            return String(n.body || "").toLowerCase().indexOf(rest) >= 0;
          });
        });
      }
      var layout = timelineLayout();
      pane.appendChild(timelineOrientBar(pane, layout));
      var w = timelineWindow();
      items = sortTimelineItems(items).filter(function (it) {
        var t = itemTime(it);
        return t >= w.since && t <= w.until;
      });
      var past = [];
      var future = [];
      items.forEach(function (it) {
        if (itemTime(it) > w.now) future.push(it);
        else past.push(it);
      });
      if (past.length > TL_SIDE_CAP) past = past.slice(-TL_SIDE_CAP);
      if (future.length > TL_SIDE_CAP) future = future.slice(0, TL_SIDE_CAP);
      var shell = document.createElement("div");
      shell.className = "timeline-shell " + (layout === "horizontal" ? "is-horizontal" : "is-vertical");
      var scroll = document.createElement("div");
      scroll.className = "timeline-scroll" + (layout === "horizontal" ? " is-horizontal" : "");
      if (!past.length && !future.length) {
        var p = document.createElement("p");
        p.className = "muted";
        p.textContent = "No events in this window.";
        scroll.appendChild(p);
      } else {
        var ul = document.createElement("ul");
        ul.className = "timeline timeline-snap-icon " + (layout === "horizontal" ? "timeline-horizontal" : "timeline-vertical");
        var visual = layout === "vertical"
          ? future.slice().reverse().concat([null]).concat(past.slice().reverse())
          : past.concat([null]).concat(future);
        function addCard(item, visIndex) {
          var count = (byAct[item._id] || []).length || item.note_count || 0;
          item.note_count = count;
          ul.appendChild(timelineItem(item, visIndex, {
            lead: visIndex > 0,
            trail: visIndex < visual.length - 1,
          }));
        }
        visual.forEach(function (item, visIndex) {
          if (!item) {
            ul.appendChild(timelineNowItem());
            return;
          }
          addCard(item, visIndex);
        });
        scroll.appendChild(ul);
      }
      if (layout === "vertical") {
        shell.appendChild(timelineRangeButtons("next"));
        shell.appendChild(scroll);
        shell.appendChild(timelineRangeButtons("past"));
      } else {
        shell.appendChild(timelineRangeButtons("past"));
        shell.appendChild(scroll);
        shell.appendChild(timelineRangeButtons("next"));
      }
      pane.appendChild(shell);
      scrollTimelineToNow(pane, layout);
    });
  }

  function timelineItem(item, index, opts) {
    opts = opts || {};
    var group = kindGroup(item.kind);
    var li = document.createElement("li");
    li.className = "is-" + group;
    if (itemTime(item) < Date.now()) li.classList.add("is-past");
    if (opts.lead) li.appendChild(document.createElement("hr"));
    var mid = document.createElement("div");
    mid.className = "timeline-middle is-" + group;
    var emoji = document.createElement("span");
    emoji.className = "tl-emoji";
    emoji.setAttribute("aria-hidden", "true");
    emoji.textContent = kindEmoji(item.kind);
    mid.appendChild(emoji);
    li.appendChild(mid);
    var side = document.createElement("div");
    side.className = (index % 2 === 0 ? "timeline-start" : "timeline-end") + " timeline-box";
    side.tabIndex = 0;
    side.setAttribute("role", "button");
    side.setAttribute("aria-label", (item.title || kindLabel(item.kind)) + " details");
    var when = document.createElement("time");
    when.className = "tl-time";
    when.dateTime = item.at || "";
    when.textContent = formatWhen(item.at);
    var title = document.createElement("div");
    title.className = "tl-title";
    title.textContent = item.title || kindLabel(item.kind);
    var body = document.createElement("p");
    body.className = "tl-body";
    var bits = [];
    bits.push(kindLabel(item.kind));
    if (item.actor) bits.push(item.actor);
    if (item.body) bits.push(item.body);
    body.textContent = bits.join(" · ");
    side.appendChild(when);
    side.appendChild(title);
    side.appendChild(body);
    if (item.project_id) {
      var proj = document.createElement("div");
      proj.className = "tl-proj";
      var chip = document.createElement("span");
      chip.className = "proj-pill";
      chip.textContent = projectName(item.project_id);
      proj.appendChild(chip);
      side.appendChild(proj);
    }
    if (item.note_count > 0) {
      var pin = document.createElement("img");
      pin.className = "tl-sticky";
      pin.src = "/static/sticky-note.png";
      pin.alt = "Has note";
      pin.title = item.note_count === 1 ? "1 note" : item.note_count + " notes";
      side.appendChild(pin);
    }
    function open() {
      openActivityLightbox(item);
    }
    side.addEventListener("click", open);
    side.addEventListener("keydown", function (ev) {
      if (ev.key === "Enter" || ev.key === " ") {
        ev.preventDefault();
        open();
      }
    });
    li.appendChild(side);
    if (opts.trail) li.appendChild(document.createElement("hr"));
    return li;
  }

  function relatedUrl(item) {
    var ref = item.ref || {};
    var col = ref.collection || "";
    var id = ref.id || "";
    if (!id) return "";
    if (col === "tickets") return "/api/tickets/" + encodeURIComponent(id);
    if (col === "emails") return "/api/emails/" + encodeURIComponent(id);
    if (col === "slack_messages") return "/api/slack/messages/" + encodeURIComponent(id);
    if (col === "teams_messages") return "/api/teams/messages/" + encodeURIComponent(id);
    if (col === "calendar_events") return "/api/calendar/" + encodeURIComponent(id);
    if (col === "salesforce_opportunities") return "/api/salesforce/opportunities/" + encodeURIComponent(id);
    if (col === "salesforce_cases") return "/api/salesforce/cases/" + encodeURIComponent(id);
    return "";
  }

  function closeDetail() {
    var box = $("detail-box");
    if (!box || box.hidden) return;
    if (box._mail && box._mail.destroy) box._mail.destroy();
    box._mail = null;
    (box._picks || []).forEach(function (p) {
      if (p && p.destroy) p.destroy();
    });
    box._picks = null;
    box.hidden = true;
    box.classList.add("hidden");
    empty(box);
    if (notesDirty && currentAccount && currentTab === "timeline") {
      notesDirty = false;
      renderPane(currentAccount, "timeline");
    }
  }

  function openRoutedItem(tab, itemId) {
    if (!itemId) return Promise.resolve();
    if (tab === "calendar") {
      return api("/api/calendar/" + encodeURIComponent(itemId)).then(openCalendarLightbox).catch(function (err) {
        toast(String(err.message || err));
      });
    }
    if (tab === "chat" || tab === "slack" || tab === "teams") {
      return openChatMessage(itemId, tab);
    }
    return api("/api/tasks/" + encodeURIComponent(itemId)).then(function (doc) {
      openTaskForm(doc);
    }).catch(function () {
      return api("/api/threads/" + encodeURIComponent(itemId)).then(openThreadLightbox);
    }).catch(function (err) {
      toast(String(err.message || err));
    });
  }

  function openSheet(titleText) {
    var box = $("detail-box");
    if (!box) return null;
    box.hidden = false;
    box.classList.remove("hidden");
    empty(box);
    var sheet = document.createElement("article");
    sheet.className = "sheet";
    var head = document.createElement("header");
    var h = document.createElement("h2");
    h.textContent = titleText || "";
    var close = document.createElement("button");
    close.type = "button";
    close.className = "btn btn-ghost sheet-close";
    close.setAttribute("aria-label", "Close");
    close.textContent = "×";
    close.addEventListener("click", closeDetail);
    head.appendChild(h);
    head.appendChild(close);
    sheet.appendChild(head);
    box.appendChild(sheet);
    return sheet;
  }

  function closeConfirm() {
    var box = $("confirm-box");
    if (!box) return;
    box.hidden = true;
    box.classList.add("hidden");
    empty(box);
  }

  function confirmDanger(opts) {
    opts = opts || {};
    var box = $("confirm-box");
    if (!box) return;
    box.hidden = false;
    box.classList.remove("hidden");
    empty(box);
    var sheet = document.createElement("article");
    sheet.className = "sheet sheet-confirm";
    var head = document.createElement("header");
    var h = document.createElement("h2");
    h.textContent = opts.title || "Confirm";
    var close = document.createElement("button");
    close.type = "button";
    close.className = "btn btn-ghost sheet-close";
    close.setAttribute("aria-label", "Close");
    close.textContent = "×";
    close.addEventListener("click", closeConfirm);
    head.appendChild(h);
    head.appendChild(close);
    sheet.appendChild(head);
    var p = document.createElement("p");
    p.textContent = opts.body || "";
    sheet.appendChild(p);
    var lab = document.createElement("label");
    var hint = document.createElement("span");
    hint.textContent = "Type ";
    var token = document.createElement("strong");
    token.className = "confirm-token";
    token.textContent = opts.token || "";
    lab.appendChild(hint);
    lab.appendChild(token);
    lab.appendChild(document.createTextNode(" to confirm"));
    var input = document.createElement("input");
    input.type = "text";
    input.autocomplete = "off";
    input.spellcheck = false;
    input.setAttribute("aria-label", "Type " + (opts.token || "") + " to confirm");
    lab.appendChild(input);
    sheet.appendChild(lab);
    var foot = document.createElement("div");
    foot.className = "sheet-foot";
    var cancel = document.createElement("button");
    cancel.type = "button";
    cancel.className = "btn";
    cancel.textContent = "Cancel";
    cancel.addEventListener("click", closeConfirm);
    var go = document.createElement("button");
    go.type = "button";
    go.className = "btn btn-cancel";
    go.textContent = opts.confirmLabel || "Remove";
    go.disabled = true;
    function matches() {
      return input.value.trim().toLowerCase() === String(opts.token || "").trim().toLowerCase();
    }
    function sync() {
      go.disabled = !matches();
    }
    input.addEventListener("input", sync);
    input.addEventListener("keydown", function (ev) {
      if (ev.key === "Enter") {
        ev.preventDefault();
        if (matches()) go.click();
      }
      if (ev.key === "Escape") closeConfirm();
    });
    go.addEventListener("click", function () {
      if (!matches()) return;
      var typed = input.value.trim();
      closeConfirm();
      if (opts.onConfirm) opts.onConfirm(typed);
    });
    foot.appendChild(cancel);
    foot.appendChild(go);
    sheet.appendChild(foot);
    box.appendChild(sheet);
    box.addEventListener("click", function onBackdrop(ev) {
      if (ev.target === box) {
        box.removeEventListener("click", onBackdrop);
        closeConfirm();
      }
    });
    setTimeout(function () { input.focus(); }, 0);
  }

  function openCalendarLightbox(ev) {
    if (!ev) return;
    var sheet = openSheet(ev.title || "Meeting");
    if (!sheet) return;
    var when = document.createElement("p");
    when.className = "muted";
    var bits = [formatWhen(ev.start_at)];
    if (ev.end_at) bits.push("– " + formatWhen(ev.end_at).replace(/^Today @ /, ""));
    var mins = meetingLengthMins(ev.start_at, ev.end_at);
    if (mins) bits.push(mins + " min");
    if (ev.location) bits.push(ev.location);
    if (ev.status === "proposed") bits.push("proposed");
    when.textContent = bits.join(" · ");
    sheet.appendChild(when);
    var dl = document.createElement("dl");
    dl.className = "sheet-kv";
    kvRow(dl, "Account", (ev.account && (ev.account.name || ev.account.abbr)) || (currentAccount && currentAccount.name) || "");
    kvRow(dl, "Location", ev.location || "");
    var names = (ev.attendees || []).map(function (a) {
      return (a && (a.name || a.email)) || "";
    }).filter(Boolean);
    kvRow(dl, "Attendees", names.join(", "));
    if (dl.firstChild) sheet.appendChild(dl);
  }

  function openChatLightbox(doc, kind) {
    if (!doc) return;
    var sheet = openSheet(doc.user_name || doc.user || (kind === "teams" ? "Teams" : "Slack"));
    if (!sheet) return;
    var when = document.createElement("p");
    when.className = "muted";
    when.textContent = formatWhen(doc.ts || doc.at) + " · " + (kind === "teams" ? "Teams" : "Slack");
    sheet.appendChild(when);
    var body = document.createElement("div");
    body.className = "sheet-body";
    body.textContent = doc.text || doc.body || "";
    sheet.appendChild(body);
  }

  function kvRow(dl, key, value) {
    if (value == null || value === "") return;
    var dt = document.createElement("dt");
    dt.textContent = key;
    var dd = document.createElement("dd");
    dd.textContent = String(value);
    dl.appendChild(dt);
    dl.appendChild(dd);
  }

  function fillRelated(root, item, doc) {
    var dl = document.createElement("dl");
    dl.className = "sheet-kv";
    var col = (item.ref || {}).collection || "";
    if (col === "tickets") {
      kvRow(dl, "Key", doc.key);
      kvRow(dl, "Status", doc.status_raw || doc.status);
      kvRow(dl, "Priority", doc.priority_raw || doc.priority);
      kvRow(dl, "Assignee", doc.assignee_email);
      kvRow(dl, "Reporter", doc.reporter_email);
      kvRow(dl, "Updated", formatWhen(doc.updated_at));
      root.appendChild(dl);
      var sum = document.createElement("p");
      sum.className = "sheet-lead";
      sum.textContent = doc.summary || "";
      root.appendChild(sum);
      (doc.comments || []).forEach(function (c) {
        var p = document.createElement("p");
        p.className = "sheet-comment";
        p.textContent = (c.author || "") + " · " + formatWhen(c.at) + "\n" + (c.text || "");
        root.appendChild(p);
      });
      return;
    }
    if (col === "emails") {
      kvRow(dl, "From", doc.from_addr);
      kvRow(dl, "To", (doc.to_addrs || []).join(", "));
      kvRow(dl, "Subject", doc.subject);
      kvRow(dl, "Direction", doc.direction === "outbound" ? "Sent" : "Received");
      kvRow(dl, "Sent", formatWhen(doc.sent_at));
      root.appendChild(dl);
      var mail = document.createElement("p");
      mail.className = "sheet-lead";
      mail.textContent = doc.body_text || doc.snippet || "";
      root.appendChild(mail);
      return;
    }
    if (col === "slack_messages" || col === "teams_messages") {
      kvRow(dl, "From", doc.user_name || doc.user);
      kvRow(dl, "Channel", doc.channel_id);
      kvRow(dl, "When", formatWhen(item.at));
      root.appendChild(dl);
      var chat = document.createElement("p");
      chat.className = "sheet-lead";
      chat.textContent = doc.text || "";
      root.appendChild(chat);
      if (doc.permalink) {
        var link = document.createElement("a");
        link.href = doc.permalink;
        link.target = "_blank";
        link.rel = "noopener";
        link.textContent = doc.permalink;
        root.appendChild(link);
      }
      return;
    }
    if (col === "salesforce_opportunities") {
      kvRow(dl, "Name", doc.name);
      kvRow(dl, "Stage", doc.stage);
      kvRow(dl, "Type", doc.kind);
      kvRow(dl, "Amount", doc.amount == null ? "" : String(doc.amount));
      kvRow(dl, "Close", doc.close_on);
      kvRow(dl, "Owner", doc.owner_name);
      root.appendChild(dl);
      if (doc.url) {
        var ou = document.createElement("a");
        ou.href = doc.url;
        ou.target = "_blank";
        ou.rel = "noopener";
        ou.textContent = doc.url;
        root.appendChild(ou);
      }
      return;
    }
    if (col === "salesforce_cases") {
      kvRow(dl, "Case", doc.case_number);
      kvRow(dl, "Subject", doc.subject);
      kvRow(dl, "Status", doc.status);
      kvRow(dl, "Priority", doc.priority);
      kvRow(dl, "Owner", doc.owner_name);
      root.appendChild(dl);
      if (doc.url) {
        var cu = document.createElement("a");
        cu.href = doc.url;
        cu.target = "_blank";
        cu.rel = "noopener";
        cu.textContent = doc.url;
        root.appendChild(cu);
      }
      return;
    }
    if (col === "calendar_events") {
      kvRow(dl, "Starts", formatWhen(doc.start_at));
      kvRow(dl, "Ends", formatWhen(doc.end_at));
      kvRow(dl, "Location", doc.location);
      var names = (doc.attendees || []).map(function (a) {
        return (a && (a.name || a.email)) || "";
      }).filter(Boolean);
      kvRow(dl, "Attendees", names.join(", "));
      root.appendChild(dl);
      return;
    }
    kvRow(dl, "Actor", item.actor);
    root.appendChild(dl);
    if (item.body) {
      var note = document.createElement("p");
      note.className = "sheet-lead";
      note.textContent = item.body;
      root.appendChild(note);
    }
  }

  function openActivityLightbox(item) {
    var box = $("detail-box");
    if (!box) return;
    box.hidden = false;
    box.classList.remove("hidden");
    empty(box);
    var sheet = document.createElement("article");
    sheet.className = "sheet";
    var head = document.createElement("header");
    var mark = document.createElement("span");
    mark.className = "tl-emoji";
    mark.setAttribute("aria-hidden", "true");
    mark.textContent = kindEmoji(item.kind);
    var title = document.createElement("h2");
    title.textContent = item.title || kindLabel(item.kind);
    var close = document.createElement("button");
    close.type = "button";
    close.className = "btn btn-ghost sheet-close";
    close.setAttribute("aria-label", "Close");
    close.textContent = "×";
    close.addEventListener("click", closeDetail);
    head.appendChild(mark);
    head.appendChild(title);
    head.appendChild(close);
    sheet.appendChild(head);
    var when = document.createElement("p");
    when.className = "muted";
    when.textContent = formatWhen(item.at) + " · " + kindLabel(item.kind);
    if (item.actor) when.textContent += " · " + item.actor;
    sheet.appendChild(when);
    var status = document.createElement("p");
    status.className = "muted";
    var body = document.createElement("div");
    body.className = "sheet-body";
    sheet.appendChild(status);
    sheet.appendChild(body);
    box.appendChild(sheet);
    var url = relatedUrl(item);
    mountProjectTag(sheet, item);
    mountNoteEditor(sheet, item);
    if (!url) {
      fillRelated(body, item, {});
      return;
    }
    status.textContent = "Loading…";
    api(url).then(function (doc) {
      status.textContent = "";
      fillRelated(body, item, doc || {});
    }).catch(function (err) {
      status.textContent = String(err.message || err);
    });
  }

  function mountProjectTag(sheet, item) {
    var wrap = document.createElement("section");
    wrap.className = "tag-block";
    var h = document.createElement("h3");
    h.textContent = "Project";
    var row = document.createElement("div");
    row.className = "tag-row";
    var sel = document.createElement("select");
    var none = document.createElement("option");
    none.value = "";
    none.textContent = "Unassigned";
    sel.appendChild(none);
    accountProjects.forEach(function (p) {
      var opt = document.createElement("option");
      opt.value = p._id || "";
      opt.textContent = p.name || p._id;
      sel.appendChild(opt);
    });
    sel.value = item.project_id || "";
    var save = document.createElement("button");
    save.type = "button";
    save.className = "btn btn-primary";
    save.textContent = "Save project";
    row.appendChild(sel);
    row.appendChild(save);
    var peopleBox = document.createElement("div");
    peopleBox.className = "people-on-proj";
    wrap.appendChild(h);
    wrap.appendChild(row);
    wrap.appendChild(peopleBox);
    sheet.appendChild(wrap);
    var aid = item.account_id || (currentAccount && currentAccount.account_id) || "";
    function loadPeople() {
      empty(peopleBox);
      var pid = sel.value;
      if (!pid || !aid) {
        var hint = document.createElement("p");
        hint.className = "muted";
        hint.textContent = "Assign a project to see who this input belongs with.";
        peopleBox.appendChild(hint);
        return;
      }
      api("/api/people?account_id=" + encodeURIComponent(aid) + "&project_id=" + encodeURIComponent(pid)).then(function (data) {
        empty(peopleBox);
        var items = data.items || [];
        if (!items.length) {
          var emptyP = document.createElement("p");
          emptyP.className = "muted";
          emptyP.textContent = "No people on " + projectName(pid) + " yet.";
          peopleBox.appendChild(emptyP);
          return;
        }
        items.forEach(function (person) {
          var card = document.createElement("div");
          card.className = "person-mini";
          var line = person.name || person._id || "";
          if (person.email) line += " · " + person.email;
          card.textContent = line;
          var bits = [];
          (person.functions || []).forEach(function (fn) { bits.push(fn); });
          if (person.title) bits.push(person.title);
          if (bits.length) {
            var small = document.createElement("small");
            small.textContent = bits.join(" · ");
            card.appendChild(small);
          }
          peopleBox.appendChild(card);
        });
      });
    }
    save.addEventListener("click", function () {
      if (!item._id) return;
      save.disabled = true;
      api("/api/activities/" + encodeURIComponent(item._id), {
        method: "PATCH",
        body: JSON.stringify({ project_id: sel.value }),
      }).then(function (doc) {
        item.project_id = (doc && doc.project_id) || sel.value;
        notesDirty = true;
        toast(item.project_id ? "Tagged " + projectName(item.project_id) : "Project cleared");
        loadPeople();
      }).catch(function (err) {
        toast(String(err.message || err));
      }).then(function () {
        save.disabled = false;
      });
    });
    loadPeople();
  }

  function mountNoteEditor(sheet, item, collection) {
    var wrap = document.createElement("section");
    wrap.className = "note-block";
    var h = document.createElement("h3");
    h.textContent = "Notes";
    var list = document.createElement("div");
    list.className = "note-list";
    var ta = document.createElement("textarea");
    ta.rows = 3;
    ta.placeholder = "Add a note for later…";
    var foot = document.createElement("div");
    foot.className = "sheet-foot";
    var save = document.createElement("button");
    save.type = "button";
    save.className = "btn btn-primary";
    save.textContent = "Save note";
    foot.appendChild(save);
    wrap.appendChild(h);
    wrap.appendChild(list);
    wrap.appendChild(ta);
    wrap.appendChild(foot);
    sheet.appendChild(wrap);
    var aid = (item.account_id || (currentAccount && currentAccount.account_id) || "");
    function loadNotes() {
      if (!item._id || !aid) return;
      api("/api/notes?account_id=" + encodeURIComponent(aid) + "&ref_id=" + encodeURIComponent(item._id)).then(function (data) {
        empty(list);
        (data.items || []).forEach(function (n) {
          var card = document.createElement("div");
          card.className = "note-item";
          card.textContent = n.body || "";
          var when = document.createElement("small");
          when.textContent = (n.author || "you") + " · " + formatWhen(n.created_at);
          card.appendChild(when);
          list.appendChild(card);
        });
        if (!(data.items || []).length) {
          var emptyN = document.createElement("p");
          emptyN.className = "muted";
          emptyN.textContent = "No notes yet.";
          list.appendChild(emptyN);
        }
      });
    }
    save.addEventListener("click", function () {
      var text = (ta.value || "").trim();
      if (!text || !aid || !item._id) return;
      save.disabled = true;
      api("/api/notes", {
        method: "POST",
        body: JSON.stringify({
          account_id: aid,
          body: text,
          ref: { collection: collection || "activities", id: item._id },
          author: (status.operator && status.operator.name) || "you",
        }),
      }).then(function () {
        ta.value = "";
        item.note_count = (item.note_count || 0) + 1;
        notesDirty = true;
        toast("Note saved");
        loadNotes();
      }).catch(function (err) {
        toast(String(err.message || err));
      }).then(function () {
        save.disabled = false;
      });
    });
    loadNotes();
  }

  function ticketRow(item) {
    return rowEl(item.key || "", item.summary || "", (item.priority || "") + " · " + (item.status || ""));
  }

  function threadRow(item) {
    var row = rowEl((item.message_count || 0) + " msgs", item.subject || "", (item.last_at || "").replace("T", " ").slice(0, 16));
    row.classList.add("is-click", "has-avatar");
    row.insertBefore(avatarEl(item.subject || "Mail"), row.firstChild);
    if (item._id) row.setAttribute("data-doc-id", item._id);
    row.addEventListener("click", function () {
      if (!item._id) return;
      api("/api/threads/" + encodeURIComponent(item._id) + "/operator", {
        method: "PATCH",
        body: JSON.stringify({ unread: false }),
      }).catch(function () {});
      if (currentAccount && currentAccount.abbr) goAccountItem(currentAccount.abbr, "email", item._id);
      else openThreadLightbox(item);
    });
    return row;
  }

  function openThreadLightbox(item) {
    var box = $("detail-box");
    if (!box) return;
    box.hidden = false;
    box.classList.remove("hidden");
    empty(box);
    var sheet = document.createElement("article");
    sheet.className = "sheet";
    var head = document.createElement("header");
    var h = document.createElement("h2");
    h.textContent = item.subject || "Thread";
    var close = document.createElement("button");
    close.type = "button";
    close.className = "btn btn-ghost sheet-close";
    close.setAttribute("aria-label", "Close");
    close.textContent = "×";
    close.addEventListener("click", closeDetail);
    head.appendChild(h);
    head.appendChild(close);
    sheet.appendChild(head);
    var status = document.createElement("p");
    status.className = "muted";
    status.textContent = "Loading…";
    sheet.appendChild(status);
    var stack = document.createElement("div");
    stack.className = "msg-stack";
    sheet.appendChild(stack);
    var suggest = document.createElement("section");
    suggest.className = "suggest-box";
    var sh = document.createElement("h3");
    sh.textContent = "Reply";
    var hint = document.createElement("p");
    hint.className = "muted";
    hint.textContent = "This thread plus a short book brief (tickets, people). Not the whole mailbox.";
    suggest.appendChild(sh);
    suggest.appendChild(hint);
    var savedDraftId = "";
    var openFull = document.createElement("button");
    openFull.type = "button";
    openFull.className = "btn btn-ghost";
    openFull.textContent = "Open full Compose";
    var mail = mountMailComposer(suggest, {
      accountId: currentAccount && currentAccount.account_id,
      to: [],
      subject: item.subject ? "Re: " + String(item.subject).replace(/^Re:\s*/i, "") : "",
      bodyPlaceholder: "Write the reply",
      extraActions: [openFull],
      onSuggest: function (snap) {
        return api("/api/threads/" + encodeURIComponent(item._id) + "/suggest-reply", {
          method: "POST",
          body: "{}",
        }).then(function (doc) {
          savedDraftId = doc.draft_id || "";
          mail.set({
            to_addrs: doc.to_addrs || [],
            cc_addrs: doc.cc_addrs || [],
            subject: doc.subject || snap.subject,
            body: doc.body || "",
          });
          toast(doc.result === "grok" ? "Drafted with Grok" : "Template draft");
          return doc;
        });
      },
      onSave: function (snap) {
        var payload = {
          account_id: (currentAccount && currentAccount.account_id) || "",
          subject: snap.subject,
          body: snap.body,
          to_addrs: snap.to_addrs,
          cc_addrs: snap.cc_addrs,
          bcc_addrs: snap.bcc_addrs,
          attachment_names: snap.attachment_names,
          created_by: "you",
          context_ref: { thread_id: item._id },
        };
        var req = savedDraftId
          ? api("/api/drafts/" + encodeURIComponent(savedDraftId), { method: "PATCH", body: JSON.stringify(payload) })
          : api("/api/drafts", { method: "POST", body: JSON.stringify(payload) });
        return req.then(function (doc) {
          if (doc && doc._id) savedDraftId = doc._id;
          return doc;
        });
      },
      onSend: function (snap, attachments) {
        var payload = {
          account_id: (currentAccount && currentAccount.account_id) || "",
          subject: snap.subject,
          body: snap.body,
          to_addrs: snap.to_addrs,
          cc_addrs: snap.cc_addrs,
          bcc_addrs: snap.bcc_addrs,
          attachment_names: snap.attachment_names,
          created_by: "you",
          context_ref: { thread_id: item._id },
        };
        var req = savedDraftId
          ? api("/api/drafts/" + encodeURIComponent(savedDraftId), { method: "PATCH", body: JSON.stringify(payload) })
          : api("/api/drafts", { method: "POST", body: JSON.stringify(payload) });
        return req.then(function (doc) {
          savedDraftId = (doc && doc._id) || savedDraftId;
          return api("/api/drafts/" + encodeURIComponent(savedDraftId) + "/send", {
            method: "POST",
            body: JSON.stringify({
              to_addrs: snap.to_addrs,
              cc_addrs: snap.cc_addrs,
              bcc_addrs: snap.bcc_addrs,
              subject: snap.subject,
              body: snap.body,
              attachment_names: snap.attachment_names,
              attachments: attachments || [],
            }),
          });
        }).then(function () {
          toast("Sent");
          closeDetail();
        });
      },
    });
    openFull.addEventListener("click", function () {
      if (!currentAccount || !window.CSMCompose) return;
      var snap = mail.snapshot();
      closeDetail();
      window.CSMCompose.open(currentAccount, {
        thread_id: item._id,
        to: (snap.to_addrs || []).join(", "),
        cc: snap.cc_addrs,
        bcc: snap.bcc_addrs,
        subject: snap.subject,
        body: snap.body,
      });
    });
    sheet.appendChild(suggest);
    box.appendChild(sheet);
    box._mail = mail;
    api("/api/threads/" + encodeURIComponent(item._id) + "?include=messages").then(function (doc) {
      status.textContent = (doc.message_count || (doc.messages || []).length || 0) + " messages";
      empty(stack);
      (doc.messages || []).forEach(function (msg) {
        var card = document.createElement("div");
        card.className = "msg-card" + (msg.direction === "outbound" ? " is-out" : "");
        var meta = document.createElement("div");
        meta.className = "row-meta";
        meta.textContent = (msg.from_addr || "") + " · " + formatWhen(msg.sent_at);
        var body = document.createElement("p");
        body.textContent = msg.body_text || msg.snippet || "";
        card.appendChild(meta);
        card.appendChild(body);
        stack.appendChild(card);
      });
      if (!(doc.messages || []).length) {
        var emptyP = document.createElement("p");
        emptyP.className = "muted";
        emptyP.textContent = "No messages in this thread.";
        stack.appendChild(emptyP);
      }
    }).catch(function (err) {
      status.textContent = String(err.message || err);
    });
  }

  function chatKindOf(item, hint) {
    var id = String((item && item._id) || "");
    var type = String((item && item.type) || "");
    if (id.indexOf("tmm:") === 0 || type.indexOf("teams") === 0) return "teams";
    if (id.indexOf("slm:") === 0 || type.indexOf("slack") === 0) return "slack";
    if (hint === "teams" || hint === "slack") return hint;
    return "";
  }

  function chatWhen(item) {
    var raw = (item && (item.ts || item.at)) || "";
    var n = Number(raw);
    if (!isNaN(n) && n > 1e9) return formatWhen(new Date(n < 1e12 ? n * 1000 : n).toISOString());
    return formatWhen(raw) || String(raw || "");
  }

  function openChatMessage(itemId, hint) {
    var kind = chatKindOf({ _id: itemId }, hint);
    var slackPath = "/api/slack/messages/" + encodeURIComponent(itemId);
    var teamsPath = "/api/teams/messages/" + encodeURIComponent(itemId);
    function show(doc, source) {
      openChatLightbox(doc, source);
    }
    function fail(err) {
      toast(String(err.message || err));
    }
    if (kind === "teams") {
      return api(teamsPath).then(function (doc) { show(doc, "teams"); }).catch(function () {
        return api(slackPath).then(function (doc) { show(doc, "slack"); });
      }).catch(fail);
    }
    return api(slackPath).then(function (doc) { show(doc, "slack"); }).catch(function () {
      return api(teamsPath).then(function (doc) { show(doc, "teams"); });
    }).catch(fail);
  }

  function chatRow(item) {
    var kind = chatKindOf(item);
    var row = rowEl(item.user_name || "", item.text || "", chatWhen(item));
    row.classList.add("is-click", "is-chat");
    row.setAttribute("data-chat-kind", kind);
    row.insertBefore(kindIcon(kind), row.firstChild);
    if (item._id) row.setAttribute("data-doc-id", item._id);
    row.addEventListener("click", function () {
      if (currentAccount && currentAccount.abbr && item._id) goAccountItem(currentAccount.abbr, "chat", item._id);
    });
    return row;
  }

  function fillChat(pane, aid) {
    var s = slashState(accountQ);
    var want = s.exact && (s.cmd === "slack" || s.cmd === "teams") ? s.cmd : "";
    var qs = "?account_id=" + encodeURIComponent(aid) + "&limit=100";
    var needle = (searchNeedle() || "").toLowerCase();
    var slackReq = want === "teams" ? Promise.resolve({ items: [] }) : api("/api/slack/messages" + qs);
    var teamsReq = want === "slack" ? Promise.resolve({ items: [] }) : api("/api/teams/messages" + qs);
    return Promise.all([slackReq, teamsReq]).then(function (pair) {
      var slack = (pair[0].items || []).map(function (item) {
        return Object.assign({}, item, { type: item.type || "slack_message" });
      });
      var teams = (pair[1].items || []).map(function (item) {
        return Object.assign({}, item, { type: item.type || "teams_message" });
      });
      var items = slack.concat(teams).sort(function (a, b) {
        return String(b.ts || "").localeCompare(String(a.ts || ""));
      });
      if (needle) {
        items = items.filter(function (item) {
          return JSON.stringify(item).toLowerCase().indexOf(needle) >= 0;
        });
      }
      if (!items.length) {
        var p = document.createElement("p");
        p.className = "muted";
        p.textContent = want === "slack" ? "No Slack." : want === "teams" ? "No Teams." : "No Slack or Teams yet.";
        pane.appendChild(p);
        return;
      }
      items.forEach(function (item) {
        pane.appendChild(chatRow(item));
      });
    });
  }

  function fillSalesforce(pane, aid) {
    var needle = searchNeedle();
    var qs = "?account_id=" + encodeURIComponent(aid);
    if (needle) qs += "&q=" + encodeURIComponent(needle);
    return Promise.all([
      api("/api/salesforce/opportunities" + qs),
      api("/api/salesforce/cases" + qs),
    ]).then(function (pair) {
      var opps = pair[0].items || [];
      var cases = pair[1].items || [];
      if (!opps.length && !cases.length) {
        var p = document.createElement("p");
        p.className = "muted";
        p.textContent = "Nothing here yet.";
        pane.appendChild(p);
        return;
      }
      var h1 = document.createElement("h3");
      h1.className = "org-kind";
      h1.textContent = "Opportunities";
      pane.appendChild(h1);
      if (!opps.length) {
        var e1 = document.createElement("p");
        e1.className = "muted";
        e1.textContent = "No opportunities.";
        pane.appendChild(e1);
      }
      opps.forEach(function (item) {
        var amount = item.amount == null ? "" : String(item.amount);
        pane.appendChild(rowEl(item.stage || "", item.name || "", (item.kind || "") + " · " + amount + " · " + (item.close_on || "")));
      });
      var h2 = document.createElement("h3");
      h2.className = "org-kind";
      h2.textContent = "Cases";
      pane.appendChild(h2);
      if (!cases.length) {
        var e2 = document.createElement("p");
        e2.className = "muted";
        e2.textContent = "No cases.";
        pane.appendChild(e2);
      }
      cases.forEach(function (item) {
        pane.appendChild(rowEl(item.case_number || "", item.subject || "", (item.priority || "") + " · " + (item.status || "")));
      });
    });
  }

  function calRow(item) {
    var row = rowEl((item.start_at || "").slice(0, 16), item.title || "", item.location || "");
    row.classList.add("is-click");
    if (item._id) row.setAttribute("data-doc-id", item._id);
    row.addEventListener("click", function () {
      if (currentAccount && currentAccount.abbr && item._id) goAccountItem(currentAccount.abbr, "calendar", item._id);
    });
    return row;
  }

  function projectKindLabel(kind) {
    var hit = PROJECT_KINDS.filter(function (p) { return p[0] === kind; })[0];
    return hit ? hit[1] : (kind || "Other");
  }

  function projectStatusLabel(status) {
    var hit = PROJECT_STATUSES.filter(function (p) { return p[0] === status; })[0];
    return hit ? hit[1] : (status || "Planned");
  }

  function fillSelectPairs(sel, pairs, current) {
    empty(sel);
    pairs.forEach(function (pair) {
      var opt = document.createElement("option");
      opt.value = pair[0];
      opt.textContent = pair[1];
      if (current === pair[0]) opt.selected = true;
      sel.appendChild(opt);
    });
  }

  function fillProjects(pane, acct) {
    var bar = document.createElement("div");
    bar.className = "pane-toolbar pane-toolbar-spread";
    var left = document.createElement("div");
    left.className = "pane-toolbar-left";
    var projPick = mountSearchSelect({
      trigger: "input",
      placeholder: "Search projects",
      searchPlaceholder: "Search projects",
      ariaLabel: "Search projects",
      allowCustom: true,
      emptyLabel: "All projects",
      items: [],
      wrapClass: "project-q-wrap",
      onChange: function () { paint(accountProjects); },
      onQuery: function () { paint(accountProjects); },
    });
    projPick.el.id = "project-q";
    var kind = document.createElement("select");
    kind.className = "toolbar-filter";
    kind.setAttribute("aria-label", "Type");
    var kindAll = document.createElement("option");
    kindAll.value = "";
    kindAll.textContent = "All types";
    kind.appendChild(kindAll);
    PROJECT_KINDS.forEach(function (pair) {
      var opt = document.createElement("option");
      opt.value = pair[0];
      opt.textContent = pair[1];
      kind.appendChild(opt);
    });
    var status = document.createElement("select");
    status.className = "toolbar-filter";
    status.setAttribute("aria-label", "Status");
    var stAll = document.createElement("option");
    stAll.value = "";
    stAll.textContent = "All statuses";
    status.appendChild(stAll);
    PROJECT_STATUSES.forEach(function (pair) {
      var opt = document.createElement("option");
      opt.value = pair[0];
      opt.textContent = pair[1];
      status.appendChild(opt);
    });
    left.appendChild(projPick.el);
    left.appendChild(kind);
    left.appendChild(status);
    var add = document.createElement("button");
    add.type = "button";
    add.className = "btn btn-primary";
    add.textContent = "Add project";
    add.addEventListener("click", function () {
      openProjectForm(acct, null);
    });
    bar.appendChild(left);
    bar.appendChild(add);
    pane.appendChild(bar);
    var list = document.createElement("div");
    list.id = "project-list";
    pane.appendChild(list);
    var peopleById = {};
    function ownerLabel(id) {
      var p = peopleById[id];
      return p ? (p.name || p.email || id) : "";
    }
    function paint(items) {
      empty(list);
      var picked = projPick.get();
      var q = String(picked || "").trim().toLowerCase();
      var wantKind = kind.value;
      var wantStatus = status.value;
      var shown = (items || []).filter(function (item) {
        if (accountProject && item._id !== accountProject) return false;
        if (wantKind && item.kind !== wantKind) return false;
        if (wantStatus && item.status !== wantStatus) return false;
        if (!q) return true;
        var blob = [
          item.name,
          item.kind,
          item.status,
          item.group_email,
          item.summary,
          item.jira_epic,
          (item.tags || []).join(" "),
          ownerLabel(item.owner_person_id),
        ].join(" ").toLowerCase();
        return blob.indexOf(q) >= 0;
      });
      if (!shown.length) {
        var p = document.createElement("p");
        p.className = "muted";
        p.textContent = items && items.length ? "No projects match." : "No projects yet. Add one.";
        list.appendChild(p);
        return;
      }
      shown.forEach(function (item) {
        list.appendChild(projectRow(item, acct, ownerLabel));
      });
    }
    function reload() {
      return Promise.all([
        api("/api/projects?account_id=" + encodeURIComponent(acct.account_id)),
        api("/api/people?account_id=" + encodeURIComponent(acct.account_id)),
      ]).then(function (pair) {
        accountProjects = pair[0].items || [];
        fillProjectSelect();
        peopleById = {};
        (pair[1].items || []).forEach(function (p) {
          if (p._id) peopleById[p._id] = p;
        });
        projPick.setItems((accountProjects || []).map(function (p) {
          return { value: p.name || p._id, label: p.name || p._id, search: (p.name || "") + " " + (p.summary || "") + " " + ((p.tags || []).join(" ")) };
        }));
        paint(accountProjects);
      });
    }
    kind.addEventListener("change", function () {
      paint(accountProjects);
    });
    status.addEventListener("change", function () {
      paint(accountProjects);
    });
    return reload();
  }

  function projectRow(item, acct, ownerLabel) {
    var row = document.createElement("article");
    row.className = "project-row is-click";
    var status = document.createElement("span");
    status.className = "proj-status is-" + (item.status || "planned");
    status.textContent = projectStatusLabel(item.status);
    var mid = document.createElement("div");
    var title = document.createElement("div");
    title.className = "row-title";
    title.textContent = item.name || "";
    var meta = document.createElement("div");
    meta.className = "row-meta";
    var bits = [projectKindLabel(item.kind)];
    var owner = ownerLabel ? ownerLabel(item.owner_person_id) : "";
    if (owner) bits.push(owner);
    if (item.group_email) bits.push(item.group_email);
    meta.textContent = bits.join(" · ");
    var tags = document.createElement("div");
    tags.className = "tag-row";
    (item.tags || []).forEach(function (tag) {
      var chip = document.createElement("span");
      chip.className = "proj-pill";
      chip.textContent = tag;
      tags.appendChild(chip);
    });
    mid.appendChild(title);
    mid.appendChild(meta);
    if (tags.firstChild) mid.appendChild(tags);
    row.appendChild(status);
    row.appendChild(mid);
    row.addEventListener("click", function () {
      openProjectForm(acct, item);
    });
    return row;
  }

  function openProjectForm(acct, proj) {
    var box = $("detail-box");
    if (!box) return;
    box.hidden = false;
    box.classList.remove("hidden");
    empty(box);
    var sheet = document.createElement("article");
    sheet.className = "sheet sheet-project";
    var head = document.createElement("header");
    var h = document.createElement("h2");
    h.textContent = proj ? "Edit project" : "Add project";
    var close = document.createElement("button");
    close.type = "button";
    close.className = "btn btn-ghost sheet-close";
    close.textContent = "Close";
    close.addEventListener("click", closeDetail);
    head.appendChild(h);
    head.appendChild(close);
    sheet.appendChild(head);
    var form = document.createElement("div");
    form.className = "settings-form";
    var name = document.createElement("input");
    name.required = true;
    name.value = (proj && proj.name) || "";
    var kind = document.createElement("select");
    fillSelectPairs(kind, PROJECT_KINDS, (proj && proj.kind) || "implementation");
    var status = document.createElement("select");
    fillSelectPairs(status, PROJECT_STATUSES, (proj && proj.status) || "planned");
    var owner = document.createElement("select");
    var none = document.createElement("option");
    none.value = "";
    none.textContent = "No owner";
    owner.appendChild(none);
    var group = document.createElement("input");
    group.type = "email";
    group.placeholder = "team@company.com";
    group.value = (proj && proj.group_email) || "";
    var tagWhitelist = [];
    accountProjects.forEach(function (p) {
      (p.tags || []).forEach(function (t) {
        if (tagWhitelist.indexOf(t) < 0) tagWhitelist.push(t);
      });
    });
    var tagsPick = mountTagifyMulti({
      placeholder: "Add tags",
      ariaLabel: "Tags",
      allowCustom: true,
      items: tagWhitelist.map(function (t) { return { value: t, label: t }; }),
      value: (proj && proj.tags) || [],
    });
    tagsPick.el.id = "project-tags";
    var summary = document.createElement("textarea");
    summary.rows = 4;
    summary.value = (proj && proj.summary) || "";
    var labName = document.createElement("label");
    labName.appendChild(document.createTextNode("Name"));
    labName.appendChild(name);
    var labKind = document.createElement("label");
    labKind.appendChild(document.createTextNode("Type"));
    labKind.appendChild(kind);
    var labStatus = document.createElement("label");
    labStatus.appendChild(document.createTextNode("Status"));
    labStatus.appendChild(status);
    var labOwner = document.createElement("label");
    labOwner.appendChild(document.createTextNode("Owner"));
    labOwner.appendChild(owner);
    var labGroup = document.createElement("label");
    labGroup.appendChild(document.createTextNode("Group email"));
    labGroup.appendChild(group);
    var labTags = document.createElement("label");
    labTags.className = "settings-span";
    labTags.appendChild(document.createTextNode("Tags"));
    labTags.appendChild(tagsPick.el);
    var labSum = document.createElement("label");
    labSum.className = "settings-span";
    labSum.appendChild(document.createTextNode("Summary"));
    labSum.appendChild(summary);
    form.appendChild(labName);
    form.appendChild(labKind);
    form.appendChild(labStatus);
    form.appendChild(labOwner);
    form.appendChild(labGroup);
    form.appendChild(labTags);
    form.appendChild(labSum);
    var actions = document.createElement("div");
    actions.className = "settings-actions";
    if (proj && proj._id) {
      var rm = document.createElement("button");
      rm.type = "button";
      rm.className = "btn btn-cancel";
      rm.textContent = "Remove";
      rm.addEventListener("click", function () {
        var token = String(proj.name || "").trim();
        if (!token) return;
        confirmDanger({
          title: "Remove project",
          body: "This archives the project on this book. Type the project name. Quiet is not available here — Cancel if you clicked by mistake.",
          token: token,
          confirmLabel: "Remove project",
          onConfirm: function (typed) {
            api("/api/projects/" + encodeURIComponent(proj._id), {
              method: "DELETE",
              body: JSON.stringify({ confirm: typed }),
            }).then(function () {
              toast("Project removed");
              closeDetail();
              return api("/api/projects?account_id=" + encodeURIComponent(acct.account_id));
            }).then(function (data) {
              accountProjects = (data && data.items) || [];
              fillProjectSelect();
              renderPane(acct, "projects");
            }).catch(function (err) {
              toast(String(err.message || err));
            });
          },
        });
      });
      actions.appendChild(rm);
    }
    var save = document.createElement("button");
    save.type = "button";
    save.className = "btn btn-primary";
    save.textContent = proj ? "Save project" : "Add project";
    save.addEventListener("click", function () {
      var tagVals = tagsPick.get() || [];
      var payload = {
        account_id: acct.account_id,
        name: name.value,
        kind: kind.value,
        status: status.value,
        owner_person_id: owner.value,
        group_email: group.value,
        tags: tagVals,
        summary: summary.value,
      };
      var req = proj && proj._id
        ? api("/api/projects/" + encodeURIComponent(proj._id), { method: "PATCH", body: JSON.stringify(payload) })
        : api("/api/projects", { method: "POST", body: JSON.stringify(payload) });
      req.then(function () {
        toast(proj ? "Project saved" : "Project added");
        closeDetail();
        return api("/api/projects?account_id=" + encodeURIComponent(acct.account_id));
      }).then(function (data) {
        accountProjects = (data && data.items) || [];
        fillProjectSelect();
        renderPane(acct, "projects");
      }).catch(function (err) {
        toast(String(err.message || err));
      });
    });
    actions.appendChild(save);
    sheet.appendChild(form);
    sheet.appendChild(actions);
    box.appendChild(sheet);
    tagsPick.bind();
    box._picks = [tagsPick];
    api("/api/people?account_id=" + encodeURIComponent(acct.account_id)).then(function (data) {
      (data.items || []).forEach(function (p) {
        if (!p._id) return;
        var opt = document.createElement("option");
        opt.value = p._id;
        opt.textContent = (p.name || p.email || p._id) + (p.email && p.name ? " · " + p.email : "");
        if (proj && proj.owner_person_id === p._id) opt.selected = true;
        owner.appendChild(opt);
      });
    });
  }

  function personRow(item, acct) {
    var mid = item.name || "";
    if (item.title) mid += " · " + item.title;
    if (item.group) mid += " · " + item.group;
    var right = item.email || "";
    if (item.phone) right = (right ? right + " · " : "") + item.phone;
    if (item.location) right = (right ? right + " · " : "") + item.location;
    var row = rowEl(item.role || item.kind || "", mid, right);
    row.classList.add("is-click", "has-avatar");
    row.insertBefore(avatarEl(item.name || item.email || "?"), row.firstChild);
    var extra = document.createElement("div");
    extra.className = "row-meta";
    if (item.owns_all_projects) {
      var allChip = document.createElement("span");
      allChip.className = "proj-pill";
      allChip.textContent = "All projects";
      extra.appendChild(allChip);
    }
    (item.project_ids || []).forEach(function (pid) {
      var chip = document.createElement("span");
      chip.className = "proj-pill";
      chip.textContent = projectName(pid);
      extra.appendChild(chip);
    });
    (item.functions || []).forEach(function (fn) {
      var chip = document.createElement("span");
      chip.className = "fn-pill";
      chip.textContent = fn;
      extra.appendChild(chip);
    });
    var titleCol = row.querySelector(".row-title");
    if (extra.firstChild && titleCol && titleCol.parentNode) titleCol.parentNode.appendChild(extra);
    if (acct) {
      row.addEventListener("click", function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        openPersonForm(acct, item);
      });
    }
    return row;
  }

  function peopleUrl(acct) {
    if (peopleAllProjects) {
      return "/api/people?account_id=" + encodeURIComponent(acct.account_id) + "&project_id=all";
    }
    return "/api/people" + accountQs(acct.account_id, true);
  }

  function fillPeople(pane, acct) {
    var bar = document.createElement("div");
    bar.className = "pane-toolbar pane-toolbar-spread";
    var left = document.createElement("div");
    left.className = "pane-toolbar-left";
    var search = document.createElement("input");
    search.type = "search";
    search.className = "search";
    search.id = "people-q";
    search.placeholder = "Search people";
    search.setAttribute("aria-label", "Search people");
    search.value = searchNeedle();
    left.appendChild(search);
    var add = document.createElement("button");
    add.type = "button";
    add.className = "btn btn-primary";
    add.textContent = "Add person";
    add.addEventListener("click", function (ev) {
      ev.preventDefault();
      ev.stopPropagation();
      openPersonForm(acct);
    });
    bar.appendChild(left);
    bar.appendChild(add);
    pane.appendChild(bar);
    if (peopleAllProjects) {
      var note = document.createElement("p");
      note.className = "muted";
      note.textContent = "Directors / VPs who own all projects.";
      pane.appendChild(note);
    }
    var list = document.createElement("div");
    list.id = "people-list";
    pane.appendChild(list);
    return api(peopleUrl(acct)).then(function (data) {
      var items = data.items || [];
      function paint() {
        empty(list);
        var q = (search.value || "").toLowerCase().trim();
        var shown = items.filter(function (item) {
          if (!q) return true;
          var blob = [
            item.name,
            item.email,
            item.title,
            item.phone,
            item.group,
            item.job_description,
            item.role,
            item.kind,
            item.location,
            (item.functions || []).join(" "),
          ].join(" ").toLowerCase();
          return blob.indexOf(q) >= 0;
        });
        if (!shown.length) {
          var p = document.createElement("p");
          p.className = "muted";
          p.textContent = items.length ? "No people match." : "No people yet.";
          list.appendChild(p);
          return;
        }
        shown.forEach(function (item) {
          list.appendChild(personRow(item, acct));
        });
      }
      search.addEventListener("input", paint);
      paint();
    });
  }

  function fillOrgSubs(pane, acct, which) {
    var subs = document.createElement("div");
    subs.className = "tabs org-subs";
    [["orgchart", "Customer"], ["accountteam", "Account team"]].forEach(function (pair) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "tab" + (which === pair[0] ? " is-on" : "");
      b.textContent = pair[1];
      b.addEventListener("click", function () {
        location.hash = "#account/" + acct.abbr + "/" + pair[0];
      });
      subs.appendChild(b);
    });
    pane.appendChild(subs);
  }

  function initials(name) {
    var parts = String(name || "").trim().split(/\s+/).filter(Boolean);
    if (!parts.length) return "?";
    if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
    return (parts[0].charAt(0) + parts[parts.length - 1].charAt(0)).toUpperCase();
  }

  var AVATAR_TONES = [
    ["#ecebfe", "#5c5fd4"],
    ["#ffe8d6", "#c65d12"],
    ["#d8f5ed", "#178066"],
    ["#dceefc", "#1573ab"],
    ["#fde2ea", "#b81d5a"],
    ["#fff1cc", "#9a6b00"],
    ["#e7e4ff", "#6d3ccf"],
  ];

  function avatarTone(seed) {
    var s = String(seed || "");
    var n = 0;
    var i;
    for (i = 0; i < s.length; i++) n += s.charCodeAt(i) * (i + 3);
    return AVATAR_TONES[n % AVATAR_TONES.length];
  }

  function paintAvatar(el, seed) {
    var tone = avatarTone(seed);
    el.style.background = tone[0];
    el.style.color = tone[1];
    return el;
  }

  function avatarEl(name) {
    var el = document.createElement("span");
    el.className = "avatar";
    el.setAttribute("aria-hidden", "true");
    el.textContent = initials(name);
    return paintAvatar(el, name);
  }

  function fillOrgChart(pane, acct) {
    fillOrgSubs(pane, acct, "orgchart");
    return api(peopleUrl(acct)).then(function (data) {
      var people = (data.items || []).filter(function (person) {
        return person.kind === "customer";
      });
      if (!people.length) {
        var p = document.createElement("p");
        p.className = "muted";
        p.textContent = "No customer people yet. Add someone on the People tab.";
        pane.appendChild(p);
        return;
      }
      var byId = {};
      people.forEach(function (person) {
        byId[person._id] = person;
      });
      var kids = {};
      var roots = [];
      people.forEach(function (person) {
        var mgr = person.reports_to || "";
        if (mgr && byId[mgr] && mgr !== person._id) {
          if (!kids[mgr]) kids[mgr] = [];
          kids[mgr].push(person);
        } else {
          roots.push(person);
        }
      });
      var scroll = document.createElement("div");
      scroll.className = "org-scroll";
      var ul = document.createElement("ul");
      ul.className = "org-chart";
      roots.forEach(function (person) {
        ul.appendChild(orgLi(person, kids, 0, acct));
      });
      scroll.appendChild(ul);
      pane.appendChild(scroll);
      requestAnimationFrame(function () {
        var extra = scroll.scrollWidth - scroll.clientWidth;
        if (extra > 0) scroll.scrollLeft = extra / 2;
      });
    });
  }

  function orgLi(person, kids, depth, acct) {
    var li = document.createElement("li");
    li.appendChild(orgCard(person, depth, acct));
    var childs = kids[person._id] || [];
    if (childs.length) {
      var ul = document.createElement("ul");
      childs.forEach(function (child) {
        ul.appendChild(orgLi(child, kids, Math.min(depth + 1, 3), acct));
      });
      li.appendChild(ul);
    }
    return li;
  }

  function orgCard(person, depth, acct) {
    var card = document.createElement("article");
    card.className = "org-card depth-" + (depth || 0);
    var av = document.createElement("span");
    av.className = "org-avatar";
    av.setAttribute("aria-hidden", "true");
    av.textContent = initials(person.name);
    paintAvatar(av, person.name || person._id || "");
    var text = document.createElement("div");
    var name = document.createElement("div");
    name.className = "org-name";
    name.textContent = person.name || "";
    var title = document.createElement("div");
    title.className = "org-title";
    title.textContent = person.title || person.role || "";
    text.appendChild(name);
    text.appendChild(title);
    if (person.location) {
      var loc = document.createElement("div");
      loc.className = "org-loc";
      loc.textContent = person.location;
      text.appendChild(loc);
    }
    var tags = (person.functions || []).concat((person.project_ids || []).map(projectName));
    if (tags.length) {
      var tagLine = document.createElement("div");
      tagLine.className = "org-loc";
      tagLine.textContent = tags.join(" · ");
      text.appendChild(tagLine);
    }
    card.appendChild(av);
    card.appendChild(text);
    if (acct) {
      card.classList.add("is-click");
      card.addEventListener("click", function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        openPersonForm(acct, person);
      });
    }
    return card;
  }

  function fillAccountTeam(pane, acct) {
    fillOrgSubs(pane, acct, "accountteam");
    return api(peopleUrl(acct)).then(function (data) {
      var people = (data.items || []).filter(function (person) {
        return person.kind === "account_team" || person.kind === "ps_team";
      });
      if (!people.length) {
        var p = document.createElement("p");
        p.className = "muted";
        p.textContent = "No account or PS people yet.";
        pane.appendChild(p);
        return;
      }
      var table = document.createElement("table");
      table.className = "data-table";
      var thead = document.createElement("thead");
      var hr = document.createElement("tr");
      ["Name", "Title", "Email", "Location", "Kind", "Projects", "Functions"].forEach(function (label) {
        var th = document.createElement("th");
        th.textContent = label;
        hr.appendChild(th);
      });
      thead.appendChild(hr);
      table.appendChild(thead);
      var tbody = document.createElement("tbody");
      people.sort(function (a, b) {
        if (a.kind === b.kind) return String(a.name || "").localeCompare(String(b.name || ""));
        return a.kind === "account_team" ? -1 : 1;
      });
      people.forEach(function (person) {
        var tr = document.createElement("tr");
        tr.className = "is-click";
        [
          person.name || "",
          person.title || person.role || "",
          person.email || "",
          person.location || "",
          person.kind === "ps_team" ? "PS team" : "Account team",
          (person.project_ids || []).map(projectName).join(", "),
          (person.functions || []).join(", "),
        ].forEach(function (val) {
          var td = document.createElement("td");
          td.textContent = val;
          tr.appendChild(td);
        });
        tr.addEventListener("click", function (ev) {
          ev.preventDefault();
          ev.stopPropagation();
          openPersonForm(acct, person);
        });
        tbody.appendChild(tr);
      });
      table.appendChild(tbody);
      pane.appendChild(table);
    });
  }

  var _tipSeq = 0;

  function fieldTipButton(ariaLabel, text) {
    _tipSeq += 1;
    var id = "field-tip-" + _tipSeq;
    var wrap = document.createElement("span");
    wrap.className = "field-tip-wrap";
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "field-tip";
    btn.setAttribute("aria-label", ariaLabel || "About this field");
    btn.setAttribute("aria-describedby", id);
    var svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("aria-hidden", "true");
    var circ = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circ.setAttribute("cx", "12");
    circ.setAttribute("cy", "12");
    circ.setAttribute("r", "9");
    var path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", "M12 10.5v5M12 7.5h.01");
    svg.appendChild(circ);
    svg.appendChild(path);
    btn.appendChild(svg);
    var pop = document.createElement("span");
    pop.id = id;
    pop.className = "field-tip-pop";
    pop.setAttribute("role", "tooltip");
    pop.textContent = text;
    wrap.appendChild(btn);
    wrap.appendChild(pop);
    return wrap;
  }

  function fieldLabel(text, node, opts) {
    opts = opts || {};
    var lab = document.createElement("label");
    lab.className = "field-block";
    var title = document.createElement("span");
    title.className = "field-label";
    title.appendChild(document.createTextNode(text));
    if (opts.required) {
      var req = document.createElement("abbr");
      req.className = "field-req";
      req.title = "Required";
      req.textContent = "*";
      title.appendChild(req);
    }
    if (opts.tip) title.appendChild(fieldTipButton(opts.tipLabel || ("About " + text), opts.tip));
    lab.appendChild(title);
    lab.appendChild(node);
    return lab;
  }

  function checkedValues(root) {
    var out = [];
    root.querySelectorAll("input[type=checkbox]:checked").forEach(function (cb) {
      out.push(cb.value);
    });
    return out;
  }

  function checkGroup(values, items, labelFn) {
    var box = document.createElement("div");
    box.className = "check-row";
    var have = {};
    (values || []).forEach(function (v) { have[v] = true; });
    (items || []).forEach(function (item) {
      var id = typeof item === "string" ? item : (item._id || "");
      var label = typeof item === "string" ? item : (labelFn ? labelFn(item) : (item.name || id));
      var lab = document.createElement("label");
      var cb = document.createElement("input");
      cb.type = "checkbox";
      cb.value = id;
      cb.checked = !!have[id];
      lab.appendChild(cb);
      lab.appendChild(document.createTextNode(" " + label));
      box.appendChild(lab);
    });
    return box;
  }

  function openPersonForm(acct, person) {
    person = person || null;
    var sheet = openSheet(person ? "Edit person" : "Add person");
    if (!sheet) return;
    sheet.classList.add("sheet-person");
    var form = document.createElement("form");
    form.className = "settings-form";
    function lab(text, node, span) {
      var el = document.createElement("label");
      if (span) el.className = "settings-span";
      el.appendChild(document.createTextNode(text));
      el.appendChild(node);
      return el;
    }
    var name = document.createElement("input");
    name.required = true;
    name.value = (person && person.name) || "";
    var email = document.createElement("input");
    email.type = "email";
    email.value = (person && person.email) || "";
    var location = document.createElement("input");
    location.value = (person && person.location) || "";
    var title = document.createElement("input");
    title.value = (person && person.title) || "";
    var phone = document.createElement("input");
    phone.type = "tel";
    phone.value = (person && person.phone) || "";
    var group = document.createElement("input");
    group.value = (person && person.group) || "";
    var job = document.createElement("textarea");
    job.rows = 3;
    job.value = (person && person.job_description) || "";
    var kindPick = mountSearchSelect({
      items: [
        { value: "customer", label: "Customer" },
        { value: "account_team", label: "Account team" },
        { value: "ps_team", label: "PS team" },
      ],
      value: (person && person.kind) || "customer",
      btnClass: "search-select-btn-block",
    });
    var reportsPick = mountSearchSelect({
      placeholder: "No manager",
      emptyLabel: "No manager",
      searchPlaceholder: "Search people",
      items: [{ value: "", label: "No manager" }],
      value: (person && person.reports_to) || "",
      btnClass: "search-select-btn-block",
    });
    var projPick = mountTagifyMulti({
      placeholder: "Search projects",
      ariaLabel: "Projects",
      enforceWhitelist: true,
      items: (accountProjects || []).map(function (p) {
        return { value: p._id || "", label: p.name || p._id };
      }),
      value: (person && person.project_ids) || [],
    });
    projPick.el.id = "person-projects";
    var fnPick = mountTagifyMulti({
      placeholder: "Search functions",
      ariaLabel: "Functions",
      allowCustom: true,
      items: PERSON_FUNCS.map(function (fn) { return { value: fn, label: fn }; }),
      value: (person && person.functions) || [],
    });
    fnPick.el.id = "person-functions";
    var allProj = document.createElement("input");
    allProj.type = "checkbox";
    allProj.checked = !!(person && person.owns_all_projects);
    var allLab = document.createElement("label");
    allLab.className = "settings-span check-inline";
    allLab.appendChild(allProj);
    allLab.appendChild(document.createTextNode("All projects (director / VP)"));
    function syncAllProj() {
      if (allProj.checked) {
        projPick.set([]);
        projPick.setReadonly(true);
      } else {
        projPick.setReadonly(false);
      }
    }
    allProj.addEventListener("change", syncAllProj);
    form.appendChild(lab("Name", name));
    form.appendChild(lab("Email", email));
    form.appendChild(lab("Title", title));
    form.appendChild(lab("Phone", phone));
    form.appendChild(lab("Group", group));
    form.appendChild(lab("Job description", job, true));
    form.appendChild(lab("Location", location));
    form.appendChild(lab("Kind", kindPick.el));
    form.appendChild(lab("Reports to", reportsPick.el));
    form.appendChild(lab("Projects", projPick.el, true));
    form.appendChild(allLab);
    form.appendChild(lab("Functions", fnPick.el, true));
    var foot = document.createElement("div");
    foot.className = "sheet-foot";
    var save = document.createElement("button");
    save.type = "submit";
    save.className = "btn btn-primary";
    save.textContent = "Save";
    foot.appendChild(save);
    form.appendChild(foot);
    sheet.appendChild(form);
    projPick.bind();
    fnPick.bind();
    if (allProj.checked) projPick.setReadonly(true);
    var box = $("detail-box");
    if (box) box._picks = [kindPick, reportsPick, projPick, fnPick];
    api("/api/people?account_id=" + encodeURIComponent(acct.account_id)).then(function (data) {
      var selfId = (person && person._id) || "";
      var items = [{ value: "", label: "No manager" }];
      (data.items || []).forEach(function (row) {
        if (!row._id || row._id === selfId) return;
        items.push({
          value: row._id,
          label: row.name || row._id,
          search: [row.name, row.email, row.title].join(" "),
        });
      });
      reportsPick.setItems(items);
      if (person && person.reports_to) reportsPick.set(person.reports_to);
    });
    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var payload = {
        account_id: acct.account_id,
        name: name.value,
        email: email.value,
        location: location.value,
        title: title.value,
        phone: phone.value,
        group: group.value,
        job_description: job.value,
        kind: kindPick.get() || "customer",
        reports_to: reportsPick.get() || "",
        project_ids: allProj.checked ? [] : (projPick.get() || []),
        functions: fnPick.get() || [],
        owns_all_projects: !!allProj.checked,
      };
      var req = person && person._id
        ? api("/api/people/" + encodeURIComponent(person._id), { method: "PATCH", body: JSON.stringify(payload) })
        : api("/api/people", { method: "POST", body: JSON.stringify(payload) });
      req.then(function () {
        closeDetail();
        toast("Person saved");
        renderPane(acct, currentTab === "accountteam" ? "accountteam" : currentTab === "orgchart" ? "orgchart" : "people");
      }).catch(function (err) {
        toast(String(err.message || err));
      });
    });
  }

  function reportRow(item) {
    var row = rowEl(item.kind || "", item.title || "", (item.created_at || "").slice(0, 10));
    if (item.body_md) {
      var pre = document.createElement("pre");
      pre.textContent = item.body_md;
      row.children[1].appendChild(pre);
    }
    return row;
  }

  function loadActions() {
    var due = $("actions-due").value;
    var st = $("actions-status").value;
    var qs = "?due=" + encodeURIComponent(due);
    if (st) qs += "&status=" + encodeURIComponent(st);
    var box = $("actions-list");
    empty(box);
    api("/api/actions" + qs).then(function (data) {
      (data.items || []).forEach(function (item) {
        var row = rowEl(item.due_on || "", item.title || "", item.status || "");
        if (item.account_id) {
          var chipWrap = document.createElement("div");
          var abbr = (item.account_id || "").replace("acct:", "").slice(0, 6).toUpperCase();
          chipWrap.appendChild(accountChip({ abbr: abbr, color: "#0f2744", name: item.account_id }));
          row.insertBefore(chipWrap, row.firstChild);
        }
        if (item.status === "open") {
          var btn = document.createElement("button");
          btn.className = "btn";
          btn.type = "button";
          btn.textContent = "Done";
          btn.addEventListener("click", function () {
            api("/api/actions/" + encodeURIComponent(item._id), {
              method: "PATCH",
              body: JSON.stringify({ status: "done" }),
            }).then(loadActions);
          });
          row.appendChild(btn);
        }
        box.appendChild(row);
      });
    });
  }

  function loadReports() {
    refreshStatus().then(function () {
      return api("/api/accounts");
    }).then(function (data) {
      var sel = $("report-account");
      empty(sel);
      (data.items || []).forEach(function (a) {
        var opt = document.createElement("option");
        opt.value = a.account_id;
        opt.textContent = a.abbr + " — " + a.name;
        sel.appendChild(opt);
      });
      var aid = sel.value;
      var url = aid ? "/api/reports?account_id=" + encodeURIComponent(aid) : "/api/reports";
      return api(url);
    }).then(function (data) {
      var box = $("reports-list");
      empty(box);
      (data.items || []).forEach(function (item) {
        box.appendChild(reportRow(item));
      });
    });
  }

  function closeHelpItem(el) {
    if (!el) return;
    el.classList.remove("is-jump", "is-open");
  }

  function openHelpItem(el) {
    if (!el) return;
    el.classList.add("is-jump", "is-open");
  }

  function helpBlob() {
    var parts = [];
    var i;
    for (i = 0; i < arguments.length; i++) parts.push(String(arguments[i] || ""));
    return parts.join(" ").toLowerCase();
  }

  function helpTextOf(item) {
    var bits = [item && item.h, item && item.p];
    ((item && item.blocks) || []).forEach(function (b) {
      if (!b) return;
      if (b.h3) bits.push(b.h3);
      if (b.p) bits.push(b.p);
      if (b.ul) bits.push((b.ul || []).join(" "));
    });
    return bits.join(" ");
  }

  function appendHelpAnswer(ans, item) {
    var blocks = (item && item.blocks) || [];
    if (!blocks.length) {
      if (item && item.p) {
        var only = document.createElement("p");
        only.textContent = item.p;
        ans.appendChild(only);
      }
      return;
    }
    blocks.forEach(function (b) {
      if (!b) return;
      if (b.h3) {
        var sub = document.createElement("h3");
        sub.className = "help-sub";
        sub.textContent = b.h3;
        ans.appendChild(sub);
      }
      if (b.p) {
        var p = document.createElement("p");
        p.textContent = b.p;
        ans.appendChild(p);
      }
      if (b.ul && b.ul.length) {
        var ul = document.createElement("ul");
        ul.className = "help-ul";
        b.ul.forEach(function (line) {
          var li = document.createElement("li");
          li.textContent = line;
          ul.appendChild(li);
        });
        ans.appendChild(ul);
      }
    });
  }

  function helpEscapeRe(s) {
    return String(s || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  function unmarkHelp(root) {
    if (!root) return;
    root.querySelectorAll("mark.help-mark").forEach(function (el) {
      var parent = el.parentNode;
      if (!parent) return;
      while (el.firstChild) parent.insertBefore(el.firstChild, el);
      parent.removeChild(el);
      parent.normalize();
    });
  }

  function helpMarkEl(root, terms) {
    if (!root || !terms || !terms.length) return;
    var unique = [];
    terms.forEach(function (raw) {
      var t = String(raw || "").trim();
      if (t.length < 2 || t.length > 40) return;
      var low = t.toLowerCase();
      if (unique.indexOf(low) < 0) unique.push(low);
    });
    unique.sort(function (a, b) { return b.length - a.length; });
    if (!unique.length) return;
    var re = new RegExp("\\b(" + unique.map(helpEscapeRe).join("|") + ")\\b", "gi");
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
    var nodes = [];
    var node;
    while ((node = walker.nextNode())) {
      if (!node.nodeValue || !node.parentNode) continue;
      if (node.parentNode.closest && node.parentNode.closest("mark.help-mark")) continue;
      re.lastIndex = 0;
      if (re.test(node.nodeValue)) nodes.push(node);
    }
    nodes.forEach(function (textNode) {
      var text = textNode.nodeValue;
      re.lastIndex = 0;
      var parts = text.split(re);
      if (parts.length < 2) return;
      var frag = document.createDocumentFragment();
      parts.forEach(function (part, i) {
        if (!part) return;
        if (i % 2 === 1) {
          var mark = document.createElement("mark");
          mark.className = "help-mark";
          mark.textContent = part;
          frag.appendChild(mark);
        } else {
          frag.appendChild(document.createTextNode(part));
        }
      });
      textNode.parentNode.replaceChild(frag, textNode);
    });
  }

  function helpSliceWord(value, start, end) {
    var s = String(value || "");
    var i = Math.max(0, start);
    var j = Math.min(s.length, end);
    var word = function (ch) { return /[A-Za-z0-9]/.test(ch); };
    while (i > 0 && word(s.charAt(i - 1))) i -= 1;
    while (j < s.length && word(s.charAt(j))) j += 1;
    return s.slice(i, j);
  }

  function helpEditDist(a, b) {
    a = String(a || "");
    b = String(b || "");
    if (a === b) return 0;
    var m = a.length;
    var n = b.length;
    if (!m) return n;
    if (!n) return m;
    var prev = [];
    var i;
    var j;
    for (j = 0; j <= n; j++) prev[j] = j;
    for (i = 1; i <= m; i++) {
      var cur = [i];
      for (j = 1; j <= n; j++) {
        var cost = a.charAt(i - 1) === b.charAt(j - 1) ? 0 : 1;
        cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost);
      }
      prev = cur;
    }
    return prev[n];
  }

  function helpCloseToQuery(word, q) {
    var w = String(word || "").toLowerCase();
    var query = String(q || "").toLowerCase();
    if (w.length < 2 || query.length < 2) return false;
    if (w === query) return true;
    if (query.length >= 3 && w.indexOf(query) === 0 && w.length - query.length <= 3) return true;
    if (query.length < 4) return false;
    if (w.slice(0, 3) !== query.slice(0, 3)) return false;
    if (Math.abs(w.length - query.length) > 2) return false;
    return helpEditDist(w, query) <= (query.length <= 5 ? 1 : 2);
  }

  function helpFuseHits(q) {
    if (!q || !helpFuse || q.length < 2) return null;
    var ids = {};
    var terms = [q];
    helpFuse.search(q).forEach(function (hit) {
      var id = hit && hit.item && hit.item.id;
      if (id) ids[id] = true;
      (hit.matches || []).forEach(function (m) {
        (m.indices || []).forEach(function (pair) {
          var word = helpSliceWord(m.value, pair[0], pair[1] + 1);
          if (helpCloseToQuery(word, q)) terms.push(word);
        });
      });
    });
    return { ids: ids, terms: terms };
  }

  function filterHelp(raw) {
    var box = $("help-body");
    var emptyEl = $("help-empty");
    var chips = $("help-chips");
    if (!box) return;
    var q = String(raw || "").trim();
    var qLow = q.toLowerCase();
    var hits = helpFuseHits(q);
    var ids = hits && hits.ids;
    var any = false;
    unmarkHelp(box);
    box.querySelectorAll(".help-group").forEach(function (sec) {
      var titleHit = !q || (sec.getAttribute("data-title") || "").indexOf(qLow) >= 0;
      var shown = 0;
      sec.querySelectorAll(".help-item").forEach(function (item) {
        var key = (item.id || "").replace(/^help-/, "");
        var hit;
        if (!q) hit = true;
        else if (ids) hit = !!ids[key];
        else hit = titleHit || (item.getAttribute("data-search") || "").indexOf(qLow) >= 0;
        item.hidden = !!q && !hit;
        if (hit) shown += 1;
      });
      var vis = !q || shown > 0;
      sec.hidden = !vis;
      if (vis) any = true;
      var countEl = sec.querySelector(".help-count");
      if (countEl) countEl.textContent = String(shown);
      var chip = chips ? chips.querySelector('[data-help-group="' + (sec.id || "").replace("help-", "") + '"]') : null;
      if (chip) chip.hidden = !vis;
    });
    if (emptyEl) emptyEl.hidden = any;
    if (q && any) {
      var terms = hits ? hits.terms : [q];
      box.querySelectorAll(".help-item:not([hidden])").forEach(function (item) {
        helpMarkEl(item, terms);
      });
    }
  }

  function applyHelpTopic(topic) {
    var box = $("help-body");
    if (!box) return;
    box.querySelectorAll(".help-item.is-jump, .help-item.is-open").forEach(closeHelpItem);
    var jump = topic ? $("help-" + topic) : null;
    if (!jump) return;
    var search = $("help-search");
    if (search && search.value) {
      search.value = "";
      filterHelp("");
    }
    if (jump.classList.contains("help-group")) {
      jump.scrollIntoView({ block: "start", behavior: "smooth" });
      var first = jump.querySelector(".help-item");
      if (first) openHelpItem(first);
      return;
    }
    openHelpItem(jump);
    jump.scrollIntoView({ block: "start", behavior: "smooth" });
  }

  function bindHelpSearch() {
    var search = $("help-search");
    if (!search || search.getAttribute("data-bound") === "1") return;
    search.setAttribute("data-bound", "1");
    search.addEventListener("input", function () {
      filterHelp(search.value);
    });
  }

  function paintHelp(data) {
    var box = $("help-body");
    var chips = $("help-chips");
    if (!box) return;
    empty(box);
    if (chips) empty(chips);
    var fuseRows = [];
    (data.groups || []).forEach(function (g) {
      var gid = g.id || "";
      var items = g.items || [];
      var sec = document.createElement("section");
      sec.className = "help-group";
      sec.id = "help-" + gid;
      var groupSearch = [g.title];
      var h = document.createElement("h2");
      var title = document.createElement("span");
      title.textContent = g.title || "";
      var count = document.createElement("span");
      count.className = "help-count";
      count.textContent = String(items.length);
      h.appendChild(title);
      h.appendChild(count);
      sec.appendChild(h);
      if (chips) {
        var chip = document.createElement("button");
        chip.type = "button";
        chip.className = "tab";
        chip.setAttribute("data-help-group", gid);
        chip.textContent = g.title || "";
        chip.addEventListener("click", function () {
          location.hash = "#help/" + gid;
        });
        chips.appendChild(chip);
      }
      items.forEach(function (item) {
        var wrap = document.createElement("div");
        wrap.className = "help-item";
        wrap.id = "help-" + (item.id || "");
        wrap.setAttribute("data-search", helpBlob(g.title, helpTextOf(item)));
        groupSearch.push(helpTextOf(item));
        fuseRows.push({
          id: item.id || "",
          question: item.h || "",
          answer: helpTextOf(item),
          group: g.title || "",
        });
        var q = document.createElement("h3");
        q.className = "help-q";
        var qText = document.createElement("span");
        qText.className = "help-q-text";
        qText.textContent = item.h || "";
        q.appendChild(qText);
        var ans = document.createElement("div");
        ans.className = "help-a";
        appendHelpAnswer(ans, item);
        wrap.appendChild(q);
        wrap.appendChild(ans);
        sec.appendChild(wrap);
      });
      sec.setAttribute("data-title", helpBlob(g.title));
      sec.setAttribute("data-search", helpBlob.apply(null, groupSearch));
      box.appendChild(sec);
    });
    helpFuse = typeof Fuse === "function"
      ? new Fuse(fuseRows, {
          keys: [
            { name: "question", weight: 0.55 },
            { name: "answer", weight: 0.35 },
            { name: "group", weight: 0.1 },
          ],
          includeMatches: true,
          threshold: 0.38,
          ignoreLocation: true,
          minMatchCharLength: 2,
        })
      : null;
    bindHelpSearch();
    filterHelp(($("help-search") && $("help-search").value) || "");
  }

  function loadHelp(topic) {
    var box = $("help-body");
    if (helpReady && box && box.firstChild) {
      applyHelpTopic(topic);
      return;
    }
    api("/api/help").then(function (data) {
      paintHelp(data);
      helpReady = true;
      applyHelpTopic(topic);
    });
  }

  function humanizeField(name) {
    return String(name || "").replace(/_/g, " ");
  }

  function connectorLabel(name) {
    return CONN_LABELS[name] || String(name || "");
  }

  function syncToast(name, doc) {
    if (!doc) return connectorLabel(name) + " sync";
    if (doc.error) return connectorLabel(name) + " sync " + (doc.status || "error") + " · " + doc.error;
    var routed = Number(doc.routed || 0);
    var unmatched = Number(doc.unassigned || 0);
    var fetched = Number(doc.fetched || 0);
    return (
      connectorLabel(name) +
      " sync " +
      (doc.status || "done") +
      " · " +
      fetched +
      " pulled · " +
      routed +
      " on a book · " +
      unmatched +
      " unmatched"
    );
  }

  function attachLiveGoogle(accountId, feeds) {
    var want = feeds && feeds.length ? feeds : ["google_mail", "google_cal"];
    var live = ((status && status.connectors) || []).filter(function (c) {
      return want.indexOf(c.name) >= 0 && c.mode === "live" && (c.connected || c.ok);
    });
    var jobs = [];
    var chain = Promise.resolve();
    live.forEach(function (c) {
      chain = chain.then(function () {
        return api("/api/connectors/" + encodeURIComponent(c.name) + "/sync", {
          method: "POST",
          body: JSON.stringify({ account_id: accountId }),
        }).then(function (doc) {
          toast(syncToast(c.name, doc));
          jobs.push(doc);
          return doc;
        }).catch(function (err) {
          var failed = { connector: c.name, status: "error", error: String(err.message || err), fetched: 0, routed: 0, unassigned: 0 };
          jobs.push(failed);
          toast(syncToast(c.name, failed));
        });
      });
    });
    return chain.then(function () {
      loadHome(true);
      return jobs;
    });
  }

  function reportFeeds(acct) {
    var feeds = ((acct && acct.coverage) || {}).feeds || [];
    feeds = feeds.filter(Boolean);
    if (feeds.length) return feeds;
    var live = [];
    ((status && status.connectors) || []).forEach(function (c) {
      if (c.mode === "live" && (c.connected || c.ok) && FEED_NAMES.indexOf(c.name) >= 0) live.push(c.name);
    });
    return live;
  }

  function latestJobsForAccount(aid, jobs) {
    if (jobs && jobs.length) return Promise.resolve(jobs);
    return api("/api/sync/jobs").then(function (data) {
      var latest = {};
      (data.items || []).forEach(function (j) {
        if ((j.account_id || "") !== aid) return;
        var name = j.connector;
        if (!name) return;
        if (!latest[name] || String(j.updated_at || "") > String(latest[name].updated_at || "")) latest[name] = j;
      });
      return Object.keys(latest).map(function (k) { return latest[k]; });
    });
  }

  function openProcessingReport(acct, jobs) {
    var box = $("detail-box");
    if (!box || !acct || !acct.account_id) return Promise.resolve();
    var aid = acct.account_id;
    var domains = ((acct.domains || []).slice()).map(function (d) {
      return String(d || "").trim().toLowerCase().replace(/^@/, "");
    }).filter(Boolean);
    box.hidden = false;
    box.classList.remove("hidden");
    empty(box);
    var sheet = document.createElement("article");
    sheet.className = "sheet sheet-company sheet-wizard";
    var head = document.createElement("header");
    var h = document.createElement("h2");
    h.textContent = "Processing report";
    var close = document.createElement("button");
    close.type = "button";
    close.className = "btn btn-ghost sheet-close";
    close.textContent = "×";
    close.addEventListener("click", function () {
      closeDetail();
      loadSettings();
      loadHome(true);
    });
    head.appendChild(h);
    head.appendChild(close);
    var body = document.createElement("div");
    body.className = "form-grid";
    var wait = document.createElement("p");
    wait.className = "muted";
    wait.textContent = "Counting what landed on " + (acct.name || "this book") + "…";
    body.appendChild(wait);
    var err = document.createElement("p");
    err.className = "muted";
    err.style.color = "var(--low)";
    err.hidden = true;
    var foot = document.createElement("div");
    foot.className = "sheet-foot";
    sheet.appendChild(head);
    sheet.appendChild(body);
    sheet.appendChild(err);
    sheet.appendChild(foot);
    box.appendChild(sheet);

    function setError(msg) {
      err.hidden = !msg;
      err.textContent = msg || "";
    }

    function loadCounts() {
      return api("/api/accounts/" + encodeURIComponent(aid)).then(function (account) {
        var counts = account.input_counts || {};
        return Promise.all([
          api("/api/emails?account_id=" + encodeURIComponent(aid) + "&limit=200"),
          api("/api/people?account_id=" + encodeURIComponent(aid)),
          api("/api/accounts/" + encodeURIComponent(aid) + "/people-mine"),
        ]).then(function (rows) {
          return { emails: rows[0], people: rows[1], mined: rows[2], account: account, counts: counts };
        });
      });
    }

    function jobFor(name, list) {
      var found = null;
      (list || []).forEach(function (j) {
        if ((j.connector || j.name) === name) found = j;
      });
      return found;
    }

    function paintReport(pack, jobList) {
      empty(body);
      empty(foot);
      setError("");
      var h3 = document.createElement("h3");
      h3.textContent = (acct.name || "Company") + " · inputs";
      body.appendChild(h3);
      var intro = document.createElement("p");
      intro.className = "muted";
      intro.textContent = "What landed on this book. Tickets and Slack stay 0 until those feeds are live and ticked. If a domain was mistyped, fix it below and reprocess.";
      body.appendChild(intro);
      var table = document.createElement("table");
      table.className = "wizard-report";
      var thead = document.createElement("thead");
      var hr = document.createElement("tr");
      ["Feed", "Status", "Pulled", "On this book", "Unmatched"].forEach(function (label) {
        var th = document.createElement("th");
        th.textContent = label;
        hr.appendChild(th);
      });
      thead.appendChild(hr);
      table.appendChild(thead);
      var tb = document.createElement("tbody");
      var selected = reportFeeds(pack.account || acct);
      if (!selected.length) selected = FEED_NAMES.slice();
      selected.forEach(function (name) {
        var j = jobFor(name, jobList) || {};
        var tr = document.createElement("tr");
        if (j.status === "error" || j.error) tr.className = "is-error";
        function td(text) {
          var cell = document.createElement("td");
          cell.textContent = text;
          tr.appendChild(cell);
        }
        td(connectorLabel(name));
        td(j.status || "not run");
        td(j.fetched != null ? String(j.fetched) : "—");
        td(j.routed != null ? String(j.routed) : "—");
        td(j.unassigned != null ? String(j.unassigned) : "—");
        if (j.error) tr.title = j.error;
        tb.appendChild(tr);
      });
      table.appendChild(tb);
      body.appendChild(table);
      var counts = pack.counts || {};
      var emTotal = pack.emails && pack.emails.total != null ? pack.emails.total : ((pack.emails && pack.emails.items) || []).length;
      var totals = document.createElement("p");
      totals.textContent =
        "On the book now: " +
        emTotal + " emails · " +
        (counts.calendar || 0) + " meetings · " +
        (counts.tickets || 0) + " tickets · " +
        (counts.slack || 0) + " Slack · " +
        (counts.teams || 0) + " Teams · " +
        ((pack.people && pack.people.items) || []).length + " people.";
      body.appendChild(totals);

      var domainHolder = document.createElement("div");
      body.appendChild(fieldLabel("Customer domain(s)", domainHolder, {
        tip: "Mail and meetings attach when From / To / Cc or attendees match. Add acme.co.uk, or fix a typo like accme.com, then Reprocess.",
      }));
      var domainBox = document.createElement("div");
      domainBox.className = "wizard-domain-edit";
      var chips = document.createElement("div");
      chips.className = "wizard-domain-chips";
      function paintChips() {
        empty(chips);
        domains.forEach(function (d, i) {
          var chip = document.createElement("button");
          chip.type = "button";
          chip.className = "wizard-domain-chip";
          chip.textContent = "@" + String(d).replace(/^@/, "") + " ×";
          chip.addEventListener("click", function () {
            domains.splice(i, 1);
            paintChips();
          });
          chips.appendChild(chip);
        });
      }
      paintChips();
      var addRow = document.createElement("div");
      addRow.className = "wizard-domain-add";
      var addIn = document.createElement("input");
      addIn.type = "text";
      addIn.placeholder = "acme.co.uk";
      var addBtn = document.createElement("button");
      addBtn.type = "button";
      addBtn.className = "btn";
      addBtn.textContent = "Add domain";
      function addDomain() {
        var v = String(addIn.value || "").trim().toLowerCase().replace(/^@/, "");
        if (!v || domains.indexOf(v) >= 0) return;
        domains.push(v);
        addIn.value = "";
        paintChips();
      }
      addBtn.addEventListener("click", addDomain);
      addIn.addEventListener("keydown", function (ev) {
        if (ev.key === "Enter") {
          ev.preventDefault();
          addDomain();
        }
      });
      addRow.appendChild(addIn);
      addRow.appendChild(addBtn);
      domainBox.appendChild(chips);
      domainBox.appendChild(addRow);
      domainHolder.appendChild(domainBox);

      var rerun = document.createElement("div");
      rerun.className = "wizard-rerun";
      function runReprocess(names, btn) {
        btn.disabled = true;
        var prev = btn.textContent;
        btn.textContent = "Pulling…";
        api("/api/accounts/" + encodeURIComponent(aid) + "/reprocess", {
          method: "POST",
          body: JSON.stringify({ domains: domains, feeds: names }),
        }).then(function (res) {
          toast(names.length === 1 ? connectorLabel(names[0]) + " reprocessed" : "Reprocessed");
          acct = res.account || acct;
          jobList = res.jobs || jobList;
          return loadCounts().then(function (next) { paintReport(next, jobList); });
        }).catch(function (ex) {
          setError(String(ex.message || ex));
          btn.disabled = false;
          btn.textContent = prev;
        });
      }
      selected.forEach(function (name) {
        var b = document.createElement("button");
        b.type = "button";
        b.className = "btn";
        b.textContent = "Reprocess " + connectorLabel(name);
        b.addEventListener("click", function () { runReprocess([name], b); });
        rerun.appendChild(b);
      });
      body.appendChild(rerun);

      var mineOn = ((pack.account || acct).coverage || {}).mine_people !== false;
      var mined = ((pack.mined && pack.mined.items) || []).slice();
      var byEmail = {};
      mined.forEach(function (row) {
        if (row && row.email) byEmail[String(row.email).toLowerCase()] = row;
      });
      var peopleLead = document.createElement("p");
      peopleLead.className = "muted";
      peopleLead.textContent = mined.length
        ? "Mined from mail, meetings, tickets, Slack, and Teams. De-duped by email. Tick who to add — we do not auto-create."
        : "No customer people in this pull yet. Fix a domain and reprocess, or add people on the book later.";
      body.appendChild(peopleLead);
      var list = document.createElement("div");
      list.className = "wizard-people";
      mined.forEach(function (row) {
        var lab = document.createElement("label");
        lab.className = "wizard-person" + (row.existing_id ? " is-on-book" : "");
        var cb = document.createElement("input");
        cb.type = "checkbox";
        cb.value = row.email;
        cb.checked = mineOn && !row.existing_id;
        if (row.existing_id) cb.disabled = true;
        var copy = document.createElement("span");
        var strong = document.createElement("strong");
        strong.textContent = row.name || nameFromEmail(row.email);
        copy.appendChild(strong);
        var line = document.createElement("span");
        line.className = "muted";
        line.textContent = row.email + (row.existing_id ? " · already on the book" : "");
        copy.appendChild(line);
        var bits = [row.title, row.group, row.phone].filter(Boolean);
        if (bits.length) {
          var extra = document.createElement("span");
          extra.className = "muted";
          extra.textContent = bits.join(" · ");
          copy.appendChild(extra);
        }
        if (row.job_description) {
          var jobLine = document.createElement("span");
          jobLine.className = "muted";
          jobLine.textContent = row.job_description;
          copy.appendChild(jobLine);
        }
        if ((row.sources || []).length) {
          var src = document.createElement("span");
          src.className = "muted";
          src.textContent = "seen in " + row.sources.join(", ") + (row.hits ? " · " + row.hits + " hits" : "");
          copy.appendChild(src);
        }
        lab.appendChild(cb);
        lab.appendChild(copy);
        list.appendChild(lab);
      });
      if (mined.length) body.appendChild(list);

      var closeBtn = document.createElement("button");
      closeBtn.type = "button";
      closeBtn.className = "btn";
      closeBtn.textContent = "Close";
      closeBtn.addEventListener("click", function () {
        closeDetail();
        loadSettings();
        loadHome(true);
      });
      var allBtn = document.createElement("button");
      allBtn.type = "button";
      allBtn.className = "btn";
      allBtn.textContent = "Reprocess all feeds";
      allBtn.addEventListener("click", function () { runReprocess(selected, allBtn); });
      var done = document.createElement("button");
      done.type = "button";
      done.className = "btn btn-primary";
      done.textContent = mined.length ? "Add selected people" : "Done";
      done.addEventListener("click", function () {
        var picked = [];
        list.querySelectorAll("input:checked").forEach(function (cb) {
          if (!cb.disabled) picked.push(cb.value);
        });
        var chain = Promise.resolve();
        picked.forEach(function (email) {
          var row = byEmail[String(email).toLowerCase()] || {};
          chain = chain.then(function () {
            return api("/api/people", {
              method: "POST",
              body: JSON.stringify({
                account_id: aid,
                kind: "customer",
                name: row.name || nameFromEmail(email),
                email: email,
                title: row.title || "",
                phone: row.phone || "",
                group: row.group || "",
                job_description: row.job_description || "",
              }),
            });
          });
        });
        chain.then(function () {
          toast(picked.length ? ("Added " + picked.length + " people") : "Company ready");
          closeDetail();
          loadSettings();
          loadHome(true);
        }).catch(function (ex) {
          setError(String(ex.message || ex));
        });
      });
      foot.appendChild(closeBtn);
      foot.appendChild(allBtn);
      foot.appendChild(done);
    }

    return latestJobsForAccount(aid, jobs).then(function (jobList) {
      return loadCounts().then(function (pack) { paintReport(pack, jobList); });
    }).catch(function (ex) {
      setError(String(ex.message || ex));
    });
  }

  function setStatePill(el, state) {
    if (!el) return;
    el.textContent = state;
    el.className = "pill " + state;
  }

  function tallyText(items) {
    var counts = { active: 0, inactive: 0, error: 0 };
    items.forEach(function (item) {
      counts[item.state] = (counts[item.state] || 0) + 1;
    });
    return counts.active + " active · " + counts.inactive + " inactive · " + counts.error + " error";
  }

  function fillStatusSelect(sel, items, current) {
    if (!sel) return current;
    var keep = current;
    var ids = items.map(function (item) { return item.id; });
    if (!keep || ids.indexOf(keep) < 0) keep = items.length ? items[0].id : "";
    empty(sel);
    items.forEach(function (item) {
      var opt = document.createElement("option");
      opt.value = item.id;
      opt.textContent = item.label + " · " + item.state;
      if (item.id === keep) opt.selected = true;
      sel.appendChild(opt);
    });
    return keep;
  }

  function aiHasKey(s, provider) {
    var keys = (s && s.keys) || {};
    if (provider === "grok") return !!(keys.grok || keys.xai);
    return !!keys[provider];
  }

  function aiStateOf(s, provider) {
    if (aiTestOk[provider] === false) return "error";
    var selected = ((s.ai || {}).provider || "grok");
    var has = aiHasKey(s, provider);
    if (selected === provider && !has) return "error";
    if (selected === provider && has) return "active";
    return "inactive";
  }

  function connectorStateOf(c) {
    var name = c.name || "";
    if (connTestOk[name] === false) return "error";
    var mode = c.mode || "disabled";
    if (c.ok === false) return "error";
    var ready = c.auth === "oauth" ? !!c.connected : !!c.present;
    if (mode === "live" && !ready) return "error";
    if (mode === "live" && ready) return "active";
    return "inactive";
  }

  function aiItems(s) {
    return AI_PROVIDERS.map(function (row) {
      return { id: row.id, label: row.label, state: aiStateOf(s, row.id) };
    });
  }

  function connectorItems(s) {
    return (s.connectors || []).map(function (c) {
      return { id: c.name, label: connectorLabel(c.name), state: connectorStateOf(c), raw: c };
    });
  }

  function paintAiPicker(s, prefer) {
    var selected = prefer || ((s.ai || {}).provider || "grok");
    selected = fillStatusSelect($("ai-provider"), aiItems(s), selected);
    var current = aiItems(s).filter(function (item) { return item.id === selected; })[0];
    setStatePill($("ai-state"), current ? current.state : "inactive");
    if ($("ai-tally")) $("ai-tally").textContent = tallyText(aiItems(s));
    if ($("ai-key")) {
      $("ai-key").value = "";
      $("ai-key").placeholder = aiHasKey(s, selected) ? "leave blank to keep" : "";
    }
  }

  function paintSso(s) {
    var sso = s.sso || {};
    var clients = sso.clients || {};
    if ($("sso-portal")) $("sso-portal").value = sso.org_url || "";
    if ($("sso-redirect")) $("sso-redirect").value = sso.redirect_uri || "";
    [["sso-client-id", sso.client_present], ["sso-google-id", clients.google], ["sso-google-secret", clients.google_secret], ["sso-ms-id", clients.microsoft], ["sso-slack-id", clients.slack]].forEach(function (row) {
      var el = $(row[0]);
      if (!el) return;
      el.value = "";
      el.placeholder = row[1] ? "saved" : "";
    });
    var ident = $("sso-identity");
    if (ident) {
      var bits = [];
      if (sso.signed_in) bits.push("Signed in as " + (sso.name ? sso.name + " · " : "") + (sso.email || "you"));
      else bits.push("Not signed in with SSO.");
      if (sso.google_file) bits.push("Google app client loaded from " + (sso.google_file_label || "credentials.json") + ".");
      ident.textContent = bits.join(" ");
    }
    ["sso-google-id", "sso-google-secret"].forEach(function (id) {
      var el = $(id);
      if (!el || !el.parentElement) return;
      el.parentElement.style.display = sso.google_file ? "none" : "";
    });
  }

  function collectConnectorFields(c, box) {
    var fields = {};
    (c.fields || []).forEach(function (f) {
      var input = box.querySelector('[data-field="' + f.name + '"]');
      if (input && input.value) fields[f.name] = input.value;
    });
    return fields;
  }

  function saveConnectorThen(c, box, modeEl, after) {
    var conn = {};
    conn[c.name] = collectConnectorFields(c, box);
    if (c.oauth_vendor === "google") {
      var g = Object.assign({}, conn.google || {});
      if ($("sso-google-id") && $("sso-google-id").value) g.client_id = $("sso-google-id").value;
      if ($("sso-google-secret") && $("sso-google-secret").value) g.client_secret = $("sso-google-secret").value;
      if (Object.keys(g).length) conn.google = g;
    }
    if (c.oauth_vendor === "microsoft" && $("sso-ms-id") && $("sso-ms-id").value) {
      conn.microsoft = Object.assign({}, conn.microsoft || {}, { client_id: $("sso-ms-id").value });
    }
    if (c.oauth_vendor === "slack" && $("sso-slack-id") && $("sso-slack-id").value) {
      conn.slack = Object.assign({}, conn.slack || {}, { client_id: $("sso-slack-id").value });
    }
    var modes = {};
    modes[c.name] = { mode: modeEl.value };
    return api("/api/settings/keys", { method: "PUT", body: JSON.stringify({ connectors: conn }) }).then(function () {
      return api("/api/settings", { method: "PUT", body: JSON.stringify({ connectors: modes }) });
    }).then(after);
  }

  function renderConnectorDetail(c) {
    var box = $("connector-detail");
    if (!box) return;
    empty(box);
    if (!c) {
      var emptyMsg = document.createElement("p");
      emptyMsg.className = "muted";
      emptyMsg.textContent = "No connectors registered.";
      box.appendChild(emptyMsg);
      return;
    }
    var isOauth = c.auth === "oauth";
    var form = document.createElement("div");
    form.className = "settings-form conn-fields";
    var modeLabel = document.createElement("label");
    modeLabel.textContent = "Mode";
    var mode = document.createElement("select");
    ["live", "disabled"].forEach(function (opt) {
      var option = document.createElement("option");
      option.value = opt;
      option.textContent = opt;
      if ((c.mode || "disabled") === opt) option.selected = true;
      mode.appendChild(option);
    });
    modeLabel.appendChild(mode);
    form.appendChild(modeLabel);
    (c.fields || []).forEach(function (f) {
      var label = document.createElement("label");
      label.textContent = humanizeField(f.name) + (f.present ? " (saved)" : "");
      var input = document.createElement("input");
      input.setAttribute("data-field", f.name);
      input.type = f.secret ? "password" : "text";
      input.autocomplete = "off";
      if (f.name === "tenant_id") input.placeholder = "common";
      else if (f.name === "instance_url") input.placeholder = "https://login.salesforce.com";
      else if (f.name === "base_url") input.placeholder = "https://your-site.atlassian.net";
      else if (f.name === "email") input.placeholder = "you@company.com";
      else if (f.name === "user_token") input.placeholder = f.present ? "leave blank to keep" : "xoxp-...";
      else if (f.name === "api_token") input.placeholder = f.present ? "leave blank to keep" : "Atlassian API token";
      else input.placeholder = f.present ? "leave blank to keep" : "";
      label.appendChild(input);
      form.appendChild(label);
    });
    box.appendChild(form);
    if (isOauth || c.name === "jira" || c.name === "slack") {
      var note = document.createElement("p");
      note.className = "muted conn-oauth-note";
      if (c.name === "slack") {
        note.textContent = c.connected
          ? "Connected. Paste a new xoxp token to replace it, or Reconnect the Slack app."
          : "Paste a Slack user token (xoxp-) from api.slack.com, or Connect a Slack app.";
      } else if (c.name === "teams") {
        note.textContent = c.connected
          ? "Connected to Microsoft. Sync pulls Teams chats you belong to."
          : "Connect Microsoft (Chat.Read). That login also covers Outlook mail and calendar.";
      } else if (c.name === "jira") {
        note.textContent = "Create an Atlassian API token at id.atlassian.com. Site URL looks like https://your-company.atlassian.net.";
      } else if (c.name === "google_mail") {
        note.textContent = c.connected
          ? (c.send
            ? (c.drafts
              ? "Connected. Save draft writes Gmail Drafts. Send goes out through this Google account after you confirm."
              : "Connected. Send works. Sign in with Google again to save Compose drafts into Gmail Drafts.")
            : "Connected for read. Sign in with Google again to allow Send and Gmail Drafts.")
          : "Click Sign in with Google on You. Add the redirect URI in Google Cloud if the browser says redirect_uri_mismatch.";
      } else if (c.name === "google_cal") {
        note.textContent = c.connected
          ? "Connected. Tokens stay in the local store; this form never shows them."
          : "Click Sign in with Google on You (or Connect here). Add the redirect URI below in Google Cloud Console if the browser says redirect_uri_mismatch.";
      } else {
        note.textContent = c.connected
          ? "Connected. Tokens stay in the local store; this form never shows them."
          : "Connect opens the vendor login in a new window. Tokens stay in the local store.";
      }
      box.appendChild(note);
    }
    if (c.redirect_uri) {
      var redirLabel = document.createElement("label");
      redirLabel.className = "settings-span sso-redirect";
      redirLabel.appendChild(document.createTextNode("Redirect URI (add in the vendor console)"));
      var redirRow = document.createElement("div");
      redirRow.className = "redir-row";
      var redirInput = document.createElement("input");
      redirInput.type = "text";
      redirInput.readOnly = true;
      redirInput.value = c.redirect_uri;
      var redirCopy = document.createElement("button");
      redirCopy.type = "button";
      redirCopy.className = "btn";
      redirCopy.textContent = "Copy";
      redirCopy.addEventListener("click", function () {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(c.redirect_uri).then(function () { toast("Redirect URI copied"); });
        } else toast(c.redirect_uri);
      });
      redirRow.appendChild(redirInput);
      redirRow.appendChild(redirCopy);
      redirLabel.appendChild(redirRow);
      box.appendChild(redirLabel);
    }
    var actions = document.createElement("div");
    actions.className = "settings-actions";
    if (isOauth) {
      var connect = document.createElement("button");
      connect.type = "button";
      connect.className = "btn btn-primary";
      connect.textContent = c.connected ? "Reconnect" : "Connect";
      connect.addEventListener("click", function () {
        var clients = (status.sso && status.sso.clients) || {};
        var typedId = c.oauth_vendor === "google" ? ($("sso-google-id") && $("sso-google-id").value)
          : c.oauth_vendor === "microsoft" ? ($("sso-ms-id") && $("sso-ms-id").value)
          : c.oauth_vendor === "slack" ? ($("sso-slack-id") && $("sso-slack-id").value)
          : "";
        if (c.oauth_vendor && !clients[c.oauth_vendor] && !typedId) {
          toast("Paste the " + c.oauth_vendor + " client ID on Sign in, Save, then Connect.");
          return;
        }
        saveConnectorThen(c, box, mode, function () {
          window.open("/api/oauth/" + encodeURIComponent(c.oauth_vendor) + "/start", "csm-oauth", "width=520,height=720");
        }).catch(function (err) {
          toast(String(err.message || err));
        });
      });
      actions.appendChild(connect);
      if (c.connected) {
        var disc = document.createElement("button");
        disc.type = "button";
        disc.className = "btn btn-cancel";
        disc.textContent = "Disconnect";
        disc.addEventListener("click", function () {
          api("/api/oauth/" + encodeURIComponent(c.oauth_vendor) + "/disconnect", { method: "POST", body: "{}" }).then(function () {
            toast(connectorLabel(c.name) + " disconnected");
            loadSettings();
          }).catch(function (err) {
            toast(String(err.message || err));
          });
        });
        actions.appendChild(disc);
      }
    }
    var save = document.createElement("button");
    save.type = "button";
    save.className = isOauth ? "btn" : "btn btn-primary";
    save.textContent = "Save";
    save.addEventListener("click", function () {
      saveConnectorThen(c, box, mode, function () {
        toast(connectorLabel(c.name) + " saved");
        loadSettings();
      }).catch(function (err) {
        toast(String(err.message || err));
      });
    });
    var test = document.createElement("button");
    test.type = "button";
    test.className = "btn";
    test.textContent = "Test";
    test.addEventListener("click", function () {
      api("/api/connectors/" + encodeURIComponent(c.name) + "/test", { method: "POST", body: "{}" }).then(function (doc) {
        connTestOk[c.name] = !!doc.ok;
        toast(connectorLabel(c.name) + ": " + (doc.ok ? "ok" : "error") + " · auth " + (doc.auth || "n/a"));
        loadSettings();
      }).catch(function (err) {
        connTestOk[c.name] = false;
        toast(String(err.message || err));
        loadSettings();
      });
    });
    var sync = document.createElement("button");
    sync.type = "button";
    sync.className = "btn";
    sync.textContent = "Sync";
    sync.addEventListener("click", function () {
      api("/api/connectors/" + encodeURIComponent(c.name) + "/sync", { method: "POST", body: "{}" }).then(function (doc) {
        toast(syncToast(c.name, doc));
        loadHome(true);
      }).catch(function (err) {
        toast(String(err.message || err));
      });
    });
    actions.appendChild(save);
    actions.appendChild(test);
    actions.appendChild(sync);
    box.appendChild(actions);
  }

  function paintConnectorPicker(s) {
    var items = connectorItems(s);
    pickedConnector = fillStatusSelect($("connector-picker"), items, pickedConnector);
    var current = items.filter(function (item) { return item.id === pickedConnector; })[0];
    setStatePill($("connector-state"), current ? current.state : "inactive");
    if ($("connector-tally")) $("connector-tally").textContent = tallyText(items);
    renderConnectorDetail(current ? current.raw : null);
  }

  function personaPreset(id) {
    var rows = (status && status.personas) || [];
    return rows.filter(function (p) { return p.id === id; })[0] || null;
  }

  function paintPersonaHint(id) {
    var hint = $("op-persona-hint");
    if (!hint) return;
    var p = personaPreset(id);
    hint.textContent = (p && p.hint) || "";
  }

  function fillOperatorPersona(op) {
    op = op || {};
    var sel = $("op-persona");
    var ta = $("op-intent");
    if (!sel) return;
    var rows = (status && status.personas) || [];
    if (!sel.options.length && rows.length) {
      empty(sel);
      rows.forEach(function (p) {
        var opt = document.createElement("option");
        opt.value = p.id;
        opt.textContent = p.label || p.id;
        sel.appendChild(opt);
      });
      if (!sel._personaBound) {
        sel._personaBound = true;
        sel.addEventListener("change", function () {
          var p = personaPreset(sel.value);
          paintPersonaHint(sel.value);
          if (ta && p) ta.value = p.intent || "";
        });
      }
    }
    var id = op.persona || "csm";
    if (sel.querySelector('option[value="' + id + '"]')) sel.value = id;
    else if (sel.options.length) sel.value = sel.options[0].value;
    paintPersonaHint(sel.value);
    if (ta) {
      if (op.intent) ta.value = op.intent;
      else {
        var preset = personaPreset(sel.value);
        ta.value = (preset && preset.intent) || "";
      }
    }
  }

  function loadSettings() {
    refreshStatus().then(function (s) {
      var op = s.operator || {};
      if ($("op-name")) $("op-name").value = op.name || "";
      if ($("op-phone")) $("op-phone").value = op.phone || "";
      if ($("op-email")) $("op-email").value = op.email || "";
      fillOperatorPersona(op);
      fillTimezoneSelect(op.timezone);
      var ai = s.ai || {};
      if ($("ai-model")) $("ai-model").value = ai.model || s.default_model || "";
      var preferAi = ($("ai-provider") && $("ai-provider").value) || ai.provider || "grok";
      paintAiPicker(s, preferAi);
      paintConnectorPicker(s);
      paintSso(s);
      return api("/api/accounts?include=all");
    }).then(function (data) {
      renderCompanyList(data && data.items ? data.items : []);
    });
  }

  function renderCompanyList(items) {
    var box = $("company-list");
    if (!box) return;
    empty(box);
    if (!items.length) {
      var p = document.createElement("p");
      p.className = "muted";
      p.textContent = "No companies yet. Add company opens a short onboarding train, or load seed data.";
      box.appendChild(p);
      return;
    }
    items.forEach(function (acct) {
      var row = document.createElement("div");
      row.className = "company-row";
      row.appendChild(accountMark(acct, "lg"));
      var mid = document.createElement("div");
      var title = document.createElement("div");
      title.className = "row-title";
      title.textContent = (acct.name || "") + (acct.removed ? " · removed" : acct.quiet ? " · quiet" : "");
      var meta = document.createElement("div");
      meta.className = "row-meta";
      var domains = (acct.domains || []).map(function (d) { return "@" + String(d).replace(/^@/, ""); }).join(" ");
      var cov = coverageLabel(acct.coverage);
      var look = (acct.coverage && acct.coverage.lookback_days) ? (acct.coverage.lookback_days + "d") : "";
      var every = ((acct.coverage && acct.coverage.refresh_minutes) ? acct.coverage.refresh_minutes : 5) + "m";
      meta.textContent = [cov, look, every, domains || "No customer domains"].filter(Boolean).join(" · ");
      mid.appendChild(title);
      mid.appendChild(meta);
      row.appendChild(mid);
      var actions = document.createElement("div");
      actions.className = "company-actions";
      if (!acct.removed) {
        var edit = document.createElement("button");
        edit.type = "button";
        edit.className = "btn";
        edit.textContent = "Edit";
        edit.addEventListener("click", function () { openCompanyForm(acct); });
        var inputs = document.createElement("button");
        inputs.type = "button";
        inputs.className = "btn";
        inputs.textContent = "Inputs";
        inputs.addEventListener("click", function () { openProcessingReport(acct, null); });
        var quiet = document.createElement("button");
        quiet.type = "button";
        quiet.className = "btn";
        quiet.textContent = acct.quiet ? "Unquiet" : "Quiet";
        quiet.addEventListener("click", function () {
          api("/api/accounts/" + encodeURIComponent(acct.account_id), {
            method: "PATCH",
            body: JSON.stringify({ quiet: !acct.quiet }),
          }).then(function () {
            toast(acct.quiet ? "Company visible on Home" : "Company quieted");
            loadSettings();
            loadHome(true);
          });
        });
        var rm = document.createElement("button");
        rm.type = "button";
        rm.className = "btn btn-cancel";
        rm.textContent = "Remove";
        rm.addEventListener("click", function () {
          var token = String(acct.abbr || acct.name || "").trim();
          if (!token) return;
          confirmDanger({
            title: "Remove company",
            body: "Quiet hides the book from Home. Remove archives it. Type the abbreviation to archive " + (acct.name || token) + ".",
            token: token,
            confirmLabel: "Remove company",
            onConfirm: function (typed) {
              api("/api/accounts/" + encodeURIComponent(acct.account_id), {
                method: "DELETE",
                body: JSON.stringify({ confirm: typed }),
              }).then(function () {
                toast("Company removed");
                loadSettings();
                loadHome(true);
              }).catch(function (err) {
                toast(String(err.message || err));
              });
            },
          });
        });
        actions.appendChild(edit);
        actions.appendChild(inputs);
        actions.appendChild(quiet);
        actions.appendChild(rm);
      }
      row.appendChild(actions);
      box.appendChild(row);
    });
  }

  function csvList(text) {
    return String(text || "").split(/[\n,]/).map(function (s) { return s.trim(); }).filter(Boolean);
  }

  function asAddrList(raw) {
    if (!raw) return [];
    if (Array.isArray(raw)) {
      var out = [];
      raw.forEach(function (item) {
        asAddrList(item).forEach(function (a) { out.push(a); });
      });
      return out;
    }
    if (typeof raw === "object") return asAddrList(raw.email || raw.value || raw.addr || "");
    return csvList(raw);
  }

  function peopleAsTags(items) {
    return (items || []).filter(function (p) { return p && p.email; }).map(function (p) {
      return { value: p.email, name: p.name || p.email, email: p.email };
    });
  }

  function filesToPayload(files) {
    return Promise.all((files || []).map(function (f) {
      return new Promise(function (resolve, reject) {
        if (f.size > 5 * 1024 * 1024) {
          reject(new Error("Attachment too large: " + f.name));
          return;
        }
        var reader = new FileReader();
        reader.onload = function () {
          var raw = String(reader.result || "");
          var b64 = raw.indexOf(",") >= 0 ? raw.split(",")[1] : raw;
          resolve({
            filename: f.name,
            content_type: f.type || "application/octet-stream",
            content_b64: b64,
          });
        };
        reader.onerror = function () {
          reject(new Error("Could not read " + f.name));
        };
        reader.readAsDataURL(f);
      });
    }));
  }

  function bindAddrTagify(input, whitelist, selected) {
    var inst = null;
    function destroy() {
      if (!inst) return;
      try { inst.destroy(); } catch (e) {}
      inst = null;
    }
    function set(addrs) {
      var list = asAddrList(addrs);
      var tags = list.map(function (addr) {
        var want = String(addr || "").toLowerCase();
        var hit = (whitelist || []).filter(function (p) {
          return String(p.email || p.value || "").toLowerCase() === want;
        })[0];
        return hit
          ? { value: hit.email || hit.value, name: hit.name || hit.email || hit.value, email: hit.email || hit.value }
          : { value: addr, name: addr, email: addr };
      });
      if (inst) {
        inst.removeAllTags();
        if (tags.length) inst.addTags(tags);
        return;
      }
      input.value = list.join(", ");
    }
    function tagAddr(t) {
      if (!t) return "";
      if (typeof t === "string") return t.trim();
      var v = t.email || t.value || "";
      if (v && typeof v === "object") v = v.email || v.value || "";
      return String(v || "").trim();
    }
    function values() {
      var fromInst = inst && Array.isArray(inst.value)
        ? inst.value.map(tagAddr).filter(Boolean)
        : [];
      if (fromInst.length) return fromInst;
      var raw = String(input.value || "").trim();
      if (raw.charAt(0) === "[") {
        try {
          var parsed = JSON.parse(raw);
          if (Array.isArray(parsed)) return parsed.map(tagAddr).filter(Boolean);
        } catch (e) {}
      }
      return csvList(raw);
    }
    function bind(list, addrs) {
      whitelist = list || [];
      destroy();
      if (!window.Tagify) {
        set(addrs || []);
        return;
      }
      inst = new window.Tagify(input, {
        whitelist: whitelist,
        tagTextProp: "name",
        enforceWhitelist: false,
        delimiters: ",|\n",
        dropdown: { enabled: 0, maxItems: 20, searchKeys: ["value", "name", "email"], closeOnSelect: false },
      });
      set(addrs || []);
    }
    function setReadonly(on) {
      if (inst && inst.setReadonly) inst.setReadonly(!!on);
      input.readOnly = !!on;
    }
    bind(whitelist || [], selected || []);
    return { values: values, set: set, bind: bind, destroy: destroy, setReadonly: setReadonly };
  }

  function mountMailComposer(parent, opts) {
    opts = opts || {};
    var wrap = document.createElement("div");
    wrap.className = "mail-composer";
    var toInput = document.createElement("input");
    toInput.className = "tag-input";
    toInput.placeholder = "Name or email";
    var ccInput = document.createElement("input");
    ccInput.className = "tag-input";
    ccInput.placeholder = "Name or email";
    var bccInput = document.createElement("input");
    bccInput.className = "tag-input";
    bccInput.placeholder = "Name or email";
    var subject = document.createElement("input");
    subject.className = "mail-subject";
    subject.placeholder = "Subject";
    subject.value = opts.subject || "";
    var body = document.createElement("textarea");
    body.className = "mail-body";
    body.rows = 8;
    body.placeholder = opts.bodyPlaceholder || "Write the message";
    body.value = opts.body || "";
    var whitelist = [];
    var toTags = null;
    var ccTags = null;
    var bccTags = null;
    var files = [];
    var bccOn = !!(opts.bcc && opts.bcc.length);
    function mailRow(key, node, extra) {
      var row = document.createElement("div");
      row.className = "mail-row";
      var lab = document.createElement("span");
      lab.className = "mail-key";
      lab.textContent = key;
      var hold = document.createElement("div");
      hold.className = "mail-val";
      hold.appendChild(node);
      if (extra) hold.appendChild(extra);
      row.appendChild(lab);
      row.appendChild(hold);
      return row;
    }
    var bccBtn = document.createElement("button");
    bccBtn.type = "button";
    bccBtn.className = "btn btn-ghost mail-bcc-toggle";
    bccBtn.textContent = "Bcc";
    var bccRow = mailRow("Bcc", bccInput);
    bccRow.hidden = !bccOn;
    bccBtn.addEventListener("click", function () {
      bccOn = !bccOn;
      bccRow.hidden = !bccOn;
      bccBtn.classList.toggle("is-on", bccOn);
    });
    wrap.appendChild(mailRow("To", toInput));
    wrap.appendChild(mailRow("Cc", ccInput, bccBtn));
    wrap.appendChild(bccRow);
    wrap.appendChild(mailRow("Subject", subject));
    wrap.appendChild(mailRow("Body", body));
    var attachRow = document.createElement("div");
    attachRow.className = "mail-attach";
    var attachBtn = document.createElement("button");
    attachBtn.type = "button";
    attachBtn.className = "btn";
    attachBtn.textContent = "Attach";
    var fileInput = document.createElement("input");
    fileInput.type = "file";
    fileInput.multiple = true;
    fileInput.hidden = true;
    var chipBox = document.createElement("div");
    chipBox.className = "mail-attach-list";
    function paintFiles() {
      empty(chipBox);
      files.forEach(function (f, i) {
        var chip = document.createElement("span");
        chip.className = "mail-chip";
        chip.textContent = f.name;
        var rm = document.createElement("button");
        rm.type = "button";
        rm.className = "mail-chip-x";
        rm.setAttribute("aria-label", "Remove " + f.name);
        rm.textContent = "×";
        rm.addEventListener("click", function () {
          files.splice(i, 1);
          paintFiles();
        });
        chip.appendChild(rm);
        chipBox.appendChild(chip);
      });
    }
    attachBtn.addEventListener("click", function () { fileInput.click(); });
    fileInput.addEventListener("change", function () {
      Array.prototype.forEach.call(fileInput.files || [], function (f) {
        files.push(f);
      });
      fileInput.value = "";
      paintFiles();
    });
    attachRow.appendChild(attachBtn);
    attachRow.appendChild(fileInput);
    attachRow.appendChild(chipBox);
    wrap.appendChild(attachRow);
    var foot = document.createElement("div");
    foot.className = "sheet-foot mail-foot";
    var suggest = document.createElement("button");
    suggest.type = "button";
    suggest.className = "btn btn-primary";
    suggest.textContent = "AI Suggest";
    suggest.title = "Draft with Grok from this book, or a template if no key";
    var save = document.createElement("button");
    save.type = "button";
    save.className = "btn";
    save.textContent = "Save draft";
    var send = document.createElement("button");
    send.type = "button";
    send.className = "btn";
    send.textContent = "Send";
    send.title = "Saves, then sends after you confirm";
    if (opts.lockTo) {
      toInput.readOnly = true;
      toInput.title = "Sends to you";
    }
    var statusEl = document.createElement("p");
    statusEl.className = "mail-status muted";
    statusEl.hidden = true;
    statusEl.setAttribute("aria-live", "polite");
    function setMailStatus(text, kind, reconnect) {
      empty(statusEl);
      statusEl.hidden = !text;
      statusEl.className = "mail-status" + (
        kind === "err" ? " is-err" : kind === "ok" ? " is-ok" : kind === "busy" ? " is-busy" : " muted"
      );
      if (!text) return;
      var span = document.createElement("span");
      span.textContent = text;
      statusEl.appendChild(span);
      if (reconnect && window.CSM && window.CSM.startGoogleSignIn) {
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "btn btn-ghost";
        btn.textContent = "Sign in with Google";
        btn.addEventListener("click", function () {
          window.CSM.startGoogleSignIn();
        });
        statusEl.appendChild(btn);
      }
    }
    function snapshot() {
      return {
        to_addrs: toTags ? toTags.values() : csvList(toInput.value),
        cc_addrs: ccTags ? ccTags.values() : csvList(ccInput.value),
        bcc_addrs: bccTags ? bccTags.values() : csvList(bccInput.value),
        subject: subject.value,
        body: body.value,
        attachment_names: files.map(function (f) { return f.name; }),
      };
    }
    function formatContextNote(doc) {
      var n = doc && Number(doc.context_chars);
      if (!n) return "";
      if (n >= 1000) return " · " + (Math.round(n / 100) / 10) + "k context";
      return " · " + n + " chars context";
    }
    function busy(on, why) {
      suggest.disabled = !!on;
      save.disabled = !!on;
      send.disabled = !!on;
      wrap.classList.toggle("is-busy", !!on);
      if (why === "suggest") {
        suggest.classList.toggle("is-wait", !!on);
        suggest.textContent = on ? "Drafting…" : "AI Suggest";
        if (on) suggest.setAttribute("aria-busy", "true");
        else suggest.removeAttribute("aria-busy");
      }
    }
    function showMailErr(err) {
      var raw = String((err && err.message) || err || "");
      var text = explainMailError(err);
      setMailStatus(text, "err", raw === "google_send_reconnect" || raw === "google_draft_reconnect");
      toast(text);
    }
    function applyDraftSaveStatus(doc) {
      if (!doc) return;
      var gmail = (doc && doc.gmail) || {};
      if (gmail.ok) {
        setMailStatus("Draft saved to Gmail", "ok");
        toast("Draft saved to Gmail");
        return;
      }
      if (gmail.reason === "google_draft_reconnect") {
        setMailStatus("Saved on the desk. Sign in with Google again to keep it in Gmail Drafts.", "err", true);
        toast("Saved on the desk. Sign in with Google to save Gmail Drafts.");
        return;
      }
      setMailStatus("Draft saved", "ok");
      toast("Draft saved");
    }
    suggest.addEventListener("click", function () {
      if (!opts.onSuggest) return;
      busy(true, "suggest");
      setMailStatus("Drafting with Grok… this thread plus a short book brief, not the mailbox.", "busy");
      Promise.resolve(opts.onSuggest(snapshot())).then(function (doc) {
        busy(false, "suggest");
        var result = doc && doc.result;
        if (result === "grok") setMailStatus("Drafted with Grok" + formatContextNote(doc), "ok");
        else if (result) setMailStatus("Template draft" + formatContextNote(doc), "ok");
        else setMailStatus("", "");
      }).catch(function (err) {
        busy(false, "suggest");
        showMailErr(err);
      });
    });
    save.addEventListener("click", function () {
      if (!opts.onSave) return;
      busy(true);
      Promise.resolve(opts.onSave(snapshot())).then(function (doc) {
        busy(false);
        applyDraftSaveStatus(doc);
      }).catch(function (err) {
        busy(false);
        showMailErr(err);
      });
    });
    send.addEventListener("click", function () {
      if (!opts.onSend) return;
      var snap = snapshot();
      if (!(snap.to_addrs || []).length) {
        showMailErr(new Error("to_addrs required"));
        return;
      }
      if (!window.confirm(opts.sendConfirm || "Send this email now?")) return;
      busy(true);
      filesToPayload(files).then(function (attachments) {
        return opts.onSend(snapshot(), attachments);
      }).then(function () {
        busy(false);
        setMailStatus("Sent", "ok");
      }).catch(function (err) {
        busy(false);
        showMailErr(err);
      });
    });
    foot.appendChild(suggest);
    (opts.extraActions || []).forEach(function (el) { foot.appendChild(el); });
    var spacer = document.createElement("span");
    spacer.className = "mail-foot-spacer";
    foot.appendChild(spacer);
    foot.appendChild(save);
    foot.appendChild(send);
    wrap.appendChild(foot);
    wrap.appendChild(statusEl);
    parent.appendChild(wrap);
    function applyPeople(list, keep) {
      whitelist = list || [];
      var cur = keep || snapshot();
      if (!toTags) {
        toTags = bindAddrTagify(toInput, whitelist, cur.to_addrs);
        ccTags = bindAddrTagify(ccInput, whitelist, cur.cc_addrs);
        bccTags = bindAddrTagify(bccInput, whitelist, cur.bcc_addrs);
      } else {
        toTags.bind(whitelist, cur.to_addrs);
        ccTags.bind(whitelist, cur.cc_addrs);
        bccTags.bind(whitelist, cur.bcc_addrs);
      }
      if (opts.lockTo) toTags.setReadonly(true);
    }
    function loadPeople(accountId, keep) {
      if (!accountId) {
        applyPeople([], keep);
        return Promise.resolve();
      }
      return api("/api/people?account_id=" + encodeURIComponent(accountId)).then(function (data) {
        applyPeople(peopleAsTags(data.items || []), keep);
      });
    }
    function bootTagify() {
      applyPeople(whitelist, {
        to_addrs: opts.to || [],
        cc_addrs: opts.cc || [],
        bcc_addrs: opts.bcc || [],
      });
      if (opts.accountId) loadPeople(opts.accountId);
    }
    requestAnimationFrame(function () {
      requestAnimationFrame(bootTagify);
    });
    return {
      el: wrap,
      snapshot: snapshot,
      set: function (doc) {
        doc = doc || {};
        if (!toTags) {
          opts.to = doc.to_addrs || opts.to;
          opts.cc = doc.cc_addrs || opts.cc;
          opts.bcc = doc.bcc_addrs || opts.bcc;
        }
        if (doc.to_addrs && toTags) toTags.set(asAddrList(doc.to_addrs));
        if (doc.cc_addrs && ccTags) ccTags.set(asAddrList(doc.cc_addrs));
        if (doc.bcc_addrs && bccTags) {
          var bccList = asAddrList(doc.bcc_addrs);
          bccTags.set(bccList);
          if (bccList.length) {
            bccOn = true;
            bccRow.hidden = false;
            bccBtn.classList.add("is-on");
          }
        }
        if (doc.subject != null) subject.value = doc.subject;
        if (doc.body != null) body.value = doc.body;
      },
      setAccount: function (accountId) {
        return loadPeople(accountId, snapshot());
      },
      setSubject: function (text) {
        subject.value = text || "";
      },
      subjectEl: subject,
      destroy: function () {
        if (toTags) toTags.destroy();
        if (ccTags) ccTags.destroy();
        if (bccTags) bccTags.destroy();
      },
    };
  }

  function connectorList(conn, name, key) {
    var rows = ((conn || {})[name] || {})[key];
    return rows && rows.length ? rows.slice() : [];
  }

  function connectorField(conn, name, key) {
    return connectorList(conn, name, key).join("\n");
  }

  function mountTagifyMulti(opts) {
    opts = opts || {};
    var items = (opts.items || []).slice();
    var selected = (opts.value || []).slice();
    var readonly = false;
    var inst = null;
    var allowCustom = !!opts.allowCustom;
    var input = document.createElement("input");
    input.className = "tag-input";
    input.placeholder = opts.placeholder || "";
    if (opts.ariaLabel) input.setAttribute("aria-label", opts.ariaLabel);
    var wrap = document.createElement("div");
    wrap.className = "tag-multi" + (opts.wrapClass ? " " + opts.wrapClass : "");
    wrap.appendChild(input);

    function asItem(it) {
      if (it == null) return null;
      if (typeof it === "string") return { value: it, name: it };
      var value = String(it.value == null ? "" : it.value);
      if (!value) return null;
      return { value: value, name: String(it.label || it.name || value) };
    }
    function whitelistFrom(list) {
      return (list || []).map(asItem).filter(Boolean);
    }
    function whitelistForBind() {
      var wl = whitelistFrom(items);
      var seen = {};
      wl.forEach(function (it) { seen[String(it.value)] = true; });
      (selected || []).forEach(function (v) {
        var want = String(v || "");
        if (!want || seen[want]) return;
        wl.push({ value: want, name: want });
        seen[want] = true;
      });
      return wl;
    }
    function tagsFromValues(vals) {
      var byVal = {};
      whitelistForBind().forEach(function (it) { byVal[String(it.value)] = it; });
      return (vals || []).map(function (v) {
        var want = String(v || "");
        return byVal[want] || { value: want, name: want };
      }).filter(function (it) { return it.value; });
    }
    function values() {
      if (inst) {
        return inst.value.map(function (t) { return t && t.value; }).filter(Boolean);
      }
      return csvList(input.value);
    }
    function destroy() {
      if (!inst) return;
      try { inst.destroy(); } catch (e) {}
      inst = null;
    }
    function bind() {
      selected = values().length ? values() : selected;
      destroy();
      if (!window.Tagify) {
        input.value = (selected || []).join(", ");
        input.readOnly = readonly;
        return;
      }
      inst = new window.Tagify(input, {
        whitelist: whitelistForBind(),
        tagTextProp: "name",
        enforceWhitelist: allowCustom ? false : opts.enforceWhitelist !== false,
        skipInvalid: !allowCustom,
        duplicates: false,
        editTags: allowCustom ? 1 : false,
        delimiters: allowCustom ? ",|\n" : ",",
        dropdown: {
          enabled: 0,
          maxItems: opts.maxItems || 20,
          searchKeys: ["value", "name"],
          mapValueTo: "name",
          closeOnSelect: false,
          highlightFirst: true,
          appendTarget: document.body,
        },
      });
      if (selected && selected.length) inst.addTags(tagsFromValues(selected));
      if (inst.setReadonly) inst.setReadonly(readonly);
      input.readOnly = readonly;
    }
    function set(vals) {
      selected = (vals || []).slice();
      if (inst) {
        inst.removeAllTags();
        if (selected.length) inst.addTags(tagsFromValues(selected));
        return;
      }
      input.value = selected.join(", ");
    }
    function setItems(list) {
      items = (list || []).slice();
      selected = inst ? values() : selected;
      if (!inst) return;
      var next = whitelistForBind();
      inst.settings.whitelist.length = 0;
      next.forEach(function (it) { inst.settings.whitelist.push(it); });
    }
    function setReadonly(on) {
      readonly = !!on;
      wrap.classList.toggle("is-readonly", readonly);
      if (inst && inst.setReadonly) inst.setReadonly(readonly);
      input.readOnly = readonly;
    }
    return {
      el: wrap,
      bind: bind,
      get: values,
      set: set,
      setItems: setItems,
      setReadonly: setReadonly,
      destroy: destroy,
    };
  }

  function makeTagInput(placeholder, values) {
    var pick = mountTagifyMulti({
      placeholder: placeholder,
      allowCustom: true,
      items: values || [],
      value: values || [],
    });
    return {
      el: pick.el,
      bind: pick.bind,
      values: pick.get,
    };
  }

  function closeCrop() {
    var box = $("crop-box");
    if (!box) return;
    box.hidden = true;
    box.classList.add("hidden");
    empty(box);
  }

  function openLogoCrop(onDone) {
    var box = $("crop-box");
    if (!box) return;
    box.hidden = false;
    box.classList.remove("hidden");
    empty(box);
    var sheet = document.createElement("article");
    sheet.className = "sheet";
    var head = document.createElement("header");
    var h = document.createElement("h2");
    h.textContent = "Change logo";
    var close = document.createElement("button");
    close.type = "button";
    close.className = "btn btn-ghost sheet-close";
    close.textContent = "×";
    close.addEventListener("click", closeCrop);
    head.appendChild(h);
    head.appendChild(close);
    sheet.appendChild(head);
    var lab = document.createElement("p");
    lab.textContent = "Upload image:";
    var file = document.createElement("input");
    file.type = "file";
    file.accept = "image/png,image/jpeg,image/webp,image/*";
    var name = document.createElement("span");
    name.className = "muted";
    name.textContent = " No file chosen";
    var stage = document.createElement("div");
    stage.className = "crop-stage";
    stage.hidden = true;
    var img = document.createElement("img");
    img.alt = "";
    var crop = document.createElement("div");
    crop.className = "crop-box";
    var handle = document.createElement("div");
    handle.className = "crop-handle";
    crop.appendChild(handle);
    stage.appendChild(img);
    stage.appendChild(crop);
    var foot = document.createElement("div");
    foot.className = "sheet-foot";
    var cancel = document.createElement("button");
    cancel.type = "button";
    cancel.className = "btn";
    cancel.textContent = "Close";
    cancel.addEventListener("click", closeCrop);
    var save = document.createElement("button");
    save.type = "button";
    save.className = "btn btn-primary";
    save.textContent = "Crop & Save";
    save.disabled = true;
    foot.appendChild(cancel);
    foot.appendChild(save);
    sheet.appendChild(lab);
    sheet.appendChild(file);
    sheet.appendChild(name);
    sheet.appendChild(stage);
    sheet.appendChild(foot);
    box.appendChild(sheet);
    var state = { x: 0, y: 0, size: 80, mode: "", sx: 0, sy: 0, ss: 80 };
    function layoutCrop() {
      crop.style.left = state.x + "px";
      crop.style.top = state.y + "px";
      crop.style.width = state.size + "px";
      crop.style.height = state.size + "px";
    }
    function clamp() {
      var w = img.clientWidth;
      var h = img.clientHeight;
      var min = 40;
      if (state.size > w) state.size = w;
      if (state.size > h) state.size = h;
      if (state.size < min) state.size = Math.min(min, w, h);
      if (state.x < 0) state.x = 0;
      if (state.y < 0) state.y = 0;
      if (state.x + state.size > w) state.x = Math.max(0, w - state.size);
      if (state.y + state.size > h) state.y = Math.max(0, h - state.size);
    }
    img.addEventListener("load", function () {
      stage.hidden = false;
      var w = img.clientWidth;
      var h = img.clientHeight;
      state.size = Math.round(Math.min(w, h) * 0.62);
      state.x = Math.round((w - state.size) / 2);
      state.y = Math.round((h - state.size) / 2);
      layoutCrop();
      save.disabled = false;
    });
    file.addEventListener("change", function () {
      var picked = file.files && file.files[0];
      if (!picked) return;
      name.textContent = " " + picked.name;
      var reader = new FileReader();
      reader.onload = function () {
        img.src = String(reader.result || "");
      };
      reader.readAsDataURL(picked);
    });
    function onMove(ev) {
      if (!state.mode) return;
      ev.preventDefault();
      var dx = ev.clientX - state.sx;
      var dy = ev.clientY - state.sy;
      if (state.mode === "move") {
        state.x = state.ox + dx;
        state.y = state.oy + dy;
      } else {
        state.size = Math.max(40, state.ss + dx);
      }
      clamp();
      layoutCrop();
    }
    function onUp() {
      state.mode = "";
      document.removeEventListener("pointermove", onMove);
      document.removeEventListener("pointerup", onUp);
    }
    crop.addEventListener("pointerdown", function (ev) {
      if (ev.target === handle) return;
      ev.preventDefault();
      state.mode = "move";
      state.sx = ev.clientX;
      state.sy = ev.clientY;
      state.ox = state.x;
      state.oy = state.y;
      document.addEventListener("pointermove", onMove);
      document.addEventListener("pointerup", onUp);
    });
    handle.addEventListener("pointerdown", function (ev) {
      ev.preventDefault();
      ev.stopPropagation();
      state.mode = "resize";
      state.sx = ev.clientX;
      state.sy = ev.clientY;
      state.ss = state.size;
      document.addEventListener("pointermove", onMove);
      document.addEventListener("pointerup", onUp);
    });
    save.addEventListener("click", function () {
      if (!img.naturalWidth) return;
      var scale = img.naturalWidth / img.clientWidth;
      var sx = Math.round(state.x * scale);
      var sy = Math.round(state.y * scale);
      var ss = Math.round(state.size * scale);
      var canvas = document.createElement("canvas");
      canvas.width = 256;
      canvas.height = 256;
      var ctx = canvas.getContext("2d");
      ctx.drawImage(img, sx, sy, ss, ss, 0, 0, 256, 256);
      var dataUrl = canvas.toDataURL("image/png");
      closeCrop();
      if (onDone) onDone(dataUrl);
    });
  }

  function slugFromName(name) {
    return String(name || "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "")
      .slice(0, 40);
  }

  function abbrFromName(name) {
    var words = String(name || "").trim().split(/\s+/).filter(Boolean);
    var out;
    if (words.length >= 2) {
      out = words.map(function (w) { return w.charAt(0); }).join("");
    } else {
      out = String(name || "");
    }
    return out.replace(/[^A-Za-z0-9]/g, "").toUpperCase().slice(0, 6);
  }

  function coverageLabel(cov) {
    cov = cov || {};
    var mode = cov.mode || "view";
    if (mode === "new") return "Brand new";
    if (mode === "takeover") return "Takeover";
    if (mode === "covering") return "Covering";
    var kind = cov.viewer_kind === "manager" ? "Manager" : cov.viewer_kind === "rep" ? "Rep" : "CSM";
    return "View only · " + kind;
  }

  function nameFromEmail(email) {
    var local = String(email || "").split("@")[0] || "Person";
    local = local.replace(/[._-]+nd$/i, "").replace(/[._+\-]+/g, " ");
    return local.replace(/\b\w/g, function (ch) { return ch.toUpperCase(); }).trim() || "Person";
  }

  function openCompanyWizard() {
    var box = $("detail-box");
    if (!box) return;
    box.hidden = false;
    box.classList.remove("hidden");
    empty(box);
    var state = {
      step: 0,
      mode: "new",
      viewer_kind: "csm",
      previous_owner_email: "",
      until: "",
      lookback_days: 14,
      lookbackTouched: false,
      name: "",
      slug: "",
      abbr: "",
      color: "#0B3D91",
      pendingLogo: "",
      slugTouched: false,
      abbrTouched: false,
      feeds: {},
      mine_people: true,
      refresh_minutes: 5,
      auto_draft_replies: false,
    };
    ((status && status.connectors) || []).forEach(function (c) {
      if ((c.name === "google_mail" || c.name === "google_cal") && c.mode === "live" && c.connected) {
        state.feeds[c.name] = true;
      }
    });
    var STEPS = ["Role", "Book", "Domains", "Feeds", "Look back", "People", "Attach"];
    var sheet = document.createElement("article");
    sheet.className = "sheet sheet-company sheet-wizard";
    var head = document.createElement("header");
    var h = document.createElement("h2");
    h.textContent = "Add company";
    var close = document.createElement("button");
    close.type = "button";
    close.className = "btn btn-ghost sheet-close";
    close.textContent = "×";
    close.addEventListener("click", closeDetail);
    head.appendChild(h);
    head.appendChild(close);
    sheet.appendChild(head);
    var train = document.createElement("ol");
    train.className = "wizard-train";
    train.setAttribute("aria-label", "Onboarding steps");
    var body = document.createElement("div");
    body.className = "form-grid";
    var domainsInput = null;
    var err = document.createElement("p");
    err.className = "muted";
    err.style.color = "var(--low)";
    err.hidden = true;
    var foot = document.createElement("div");
    foot.className = "sheet-foot";
    sheet.appendChild(train);
    sheet.appendChild(body);
    sheet.appendChild(err);
    sheet.appendChild(foot);
    box.appendChild(sheet);

    function setError(msg) {
      err.hidden = !msg;
      err.textContent = msg || "";
    }

    function defaultLookback() {
      return state.mode === "takeover" || state.mode === "covering" ? 90 : 14;
    }

    function validate() {
      if (state.step === 0) {
        if (state.mode === "view" && !state.viewer_kind) return "Pick whether you are a manager, CSM, or rep.";
        if (state.mode === "takeover" && state.previous_owner_email.indexOf("@") < 0) return "Previous CSM / rep email is required for takeover.";
        if (state.mode === "covering") {
          if (state.previous_owner_email.indexOf("@") < 0) return "The owner’s email is required for covering.";
          if (!state.until) return "Covering needs an until date.";
        }
      }
      if (state.step === 1) {
        if (!String(state.name || "").trim()) return "Company name is required.";
        if (!slugFromName(state.slug || state.name)) return "Slug is required.";
        if (abbrFromName(state.abbr || state.name).length < 2) return "Abbreviation must be 2–6 letters or digits.";
      }
      if (state.step === 2) {
        var doms = domainsInput ? domainsInput.values() : [];
        if (!doms.length) return "Add at least one customer domain. That is how mail and meetings land on this book.";
      }
      if (state.step === 3) {
        var anyFeed = FEED_NAMES.some(function (n) { return state.feeds[n]; });
        if (!anyFeed) return "Pick at least one feed for this book. You can connect it in Settings later, then Sync.";
      }
      return "";
    }

    function paintTrain() {
      empty(train);
      STEPS.forEach(function (label, i) {
        var li = document.createElement("li");
        if (i < state.step) li.className = "is-done";
        if (i === state.step) li.className = "is-current";
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "wizard-stop" + (i === state.step ? " is-current" : i < state.step ? " is-done" : "");
        var dot = document.createElement("span");
        dot.className = "dot";
        dot.textContent = String(i + 1);
        btn.appendChild(dot);
        btn.appendChild(document.createTextNode(label));
        btn.disabled = i > state.step;
        btn.addEventListener("click", function () {
          if (i <= state.step) {
            state.step = i;
            paint();
          }
        });
        li.appendChild(btn);
        train.appendChild(li);
      });
    }

    function choice(title, blurb, on, onClick) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "wizard-choice" + (on ? " is-on" : "");
      var strong = document.createElement("strong");
      strong.textContent = title;
      var span = document.createElement("span");
      span.textContent = blurb;
      btn.appendChild(strong);
      btn.appendChild(span);
      btn.addEventListener("click", onClick);
      return btn;
    }

    function paintRole() {
      var legend = document.createElement("p");
      legend.className = "wizard-legend";
      legend.appendChild(document.createTextNode("Fields marked "));
      var star = document.createElement("abbr");
      star.className = "field-req";
      star.title = "Required";
      star.textContent = "*";
      legend.appendChild(star);
      legend.appendChild(document.createTextNode(" are required."));
      body.appendChild(legend);
      var roleBox = document.createElement("div");
      roleBox.appendChild(choice(
        "Brand new account",
        "You own this book. Nobody is handing it off. No previous CSM email. Default pull is the last 14 days.",
        state.mode === "new",
        function () {
          state.mode = "new";
          if (!state.lookbackTouched) state.lookback_days = defaultLookback();
          paint();
        }
      ));
      roleBox.appendChild(choice(
        "View only",
        "You watch the book. Mail still routes here. You do not take their tasks.",
        state.mode === "view",
        function () {
          state.mode = "view";
          if (!state.lookbackTouched) state.lookback_days = defaultLookback();
          paint();
        }
      ));
      roleBox.appendChild(choice(
        "Takeover",
        "You own the book now. Desk tasks transfer to you. Pull is still your mailbox, filtered by customer domain.",
        state.mode === "takeover",
        function () {
          state.mode = "takeover";
          if (!state.lookbackTouched) state.lookback_days = defaultLookback();
          paint();
        }
      ));
      roleBox.appendChild(choice(
        "Covering (temp)",
        "They still own it. You are added as co-owner until a date. Do not rewrite To:Me. Do not resend calendar as you.",
        state.mode === "covering",
        function () {
          state.mode = "covering";
          if (!state.lookbackTouched) state.lookback_days = defaultLookback();
          paint();
        }
      ));
      body.appendChild(fieldLabel("Your role on this book", roleBox, {
        required: true,
        tip: "Brand new = you own it, no handoff. View = watch. Takeover = you own it after someone else. Covering = temp co-owner while they are out. This is not a second Google login.",
      }));
      if (state.mode === "view") {
        var viewer = document.createElement("select");
        [["csm", "CSM"], ["manager", "Manager"], ["rep", "Rep"]].forEach(function (pair) {
          var opt = document.createElement("option");
          opt.value = pair[0];
          opt.textContent = pair[1];
          if (state.viewer_kind === pair[0]) opt.selected = true;
          viewer.appendChild(opt);
        });
        viewer.addEventListener("change", function () { state.viewer_kind = viewer.value; });
        body.appendChild(fieldLabel("You are a", viewer, {
          required: true,
          tip: "Manager, CSM, or sales rep. This labels how you sit on the book. It does not change the Google pull.",
        }));
      }
      if (state.mode === "takeover" || state.mode === "covering") {
        var prev = document.createElement("input");
        prev.type = "email";
        prev.required = true;
        prev.placeholder = "jane.doe@yourcompany.com";
        prev.value = state.previous_owner_email;
        prev.addEventListener("input", function () { state.previous_owner_email = prev.value.trim(); });
        body.appendChild(fieldLabel(state.mode === "covering" ? "Owner email" : "Previous CSM / rep email", prev, {
          required: true,
          tip: "Stored on the book. Gmail pull is still YOUR mailbox. We cannot open their inbox with Sign in with Google. Use their address so later task handoff knows who owned it.",
        }));
      }
      if (state.mode === "covering") {
        var until = document.createElement("input");
        until.type = "date";
        until.required = true;
        until.value = state.until;
        until.addEventListener("change", function () { state.until = until.value; });
        body.appendChild(fieldLabel("Cover until", until, {
          required: true,
          tip: "When covering ends. They stay the owner. You stay co-owner until this date.",
        }));
      }
    }

    function paintBook() {
      var name = document.createElement("input");
      name.required = true;
      name.placeholder = "Acme Inc";
      name.value = state.name;
      var slug = document.createElement("input");
      slug.required = true;
      slug.placeholder = "acme";
      slug.value = state.slug;
      var abbr = document.createElement("input");
      abbr.required = true;
      abbr.maxLength = 6;
      abbr.placeholder = "ACME";
      abbr.value = state.abbr;
      name.addEventListener("input", function () {
        state.name = name.value;
        if (!state.slugTouched) {
          state.slug = slugFromName(name.value);
          slug.value = state.slug;
        }
        if (!state.abbrTouched) {
          state.abbr = abbrFromName(name.value);
          abbr.value = state.abbr;
        }
      });
      slug.addEventListener("input", function () {
        state.slugTouched = true;
        state.slug = slug.value;
      });
      abbr.addEventListener("input", function () {
        state.abbrTouched = true;
        state.abbr = abbr.value;
      });
      body.appendChild(fieldLabel("Name", name, {
        required: true,
        tip: "The customer’s name as you say it. Shows on Home chips and the book header.",
      }));
      body.appendChild(fieldLabel("Slug", slug, {
        required: true,
        tip: "Permanent id: acct:{slug}. Lowercase letters, digits, hyphens. You cannot rename the slug later. Example: Acme Inc → acme → acct:acme.",
      }));
      body.appendChild(fieldLabel("Abbr", abbr, {
        required: true,
        tip: "2–6 letters or digits on every chip. Example: ACME. You can rename this later.",
      }));
      var color = document.createElement("input");
      color.type = "color";
      color.value = state.color;
      var hex = document.createElement("input");
      hex.type = "text";
      hex.maxLength = 7;
      hex.placeholder = "#0B3D91";
      hex.value = state.color;
      color.addEventListener("input", function () {
        state.color = color.value;
        hex.value = color.value;
      });
      hex.addEventListener("change", function () {
        var v = hex.value.trim();
        if (v.charAt(0) !== "#") v = "#" + v;
        if (/^#[0-9A-Fa-f]{6}$/.test(v)) {
          state.color = v;
          color.value = v;
          hex.value = v;
        }
      });
      var colorRow = document.createElement("div");
      colorRow.className = "color-row";
      colorRow.appendChild(color);
      colorRow.appendChild(hex);
      body.appendChild(fieldLabel("Color", colorRow, {
        required: true,
        tip: "Chip color on Home and the book. Pick any hex. Example: #0B3D91.",
      }));
      var logoWrap = document.createElement("div");
      logoWrap.className = "logo-edit";
      var preview = document.createElement("div");
      preview.className = "logo-preview";
      preview.textContent = state.pendingLogo ? "" : "No logo";
      if (state.pendingLogo) {
        var img = document.createElement("img");
        img.src = state.pendingLogo;
        img.alt = "";
        preview.appendChild(img);
      }
      var change = document.createElement("button");
      change.type = "button";
      change.className = "btn";
      change.textContent = "Change logo";
      change.addEventListener("click", function () {
        openLogoCrop(function (dataUrl) {
          state.pendingLogo = dataUrl;
          paint();
        });
      });
      logoWrap.appendChild(preview);
      logoWrap.appendChild(change);
      body.appendChild(fieldLabel("Logo", logoWrap, {
        tip: "Optional. Square crop, PNG. Shows on Agenda cards and the book header.",
      }));
    }

    function paintDomains() {
      var hold = domainsInput ? domainsInput.values() : [];
      domainsInput = makeTagInput("@acme.com", hold.map(function (d) {
        return "@" + String(d).replace(/^@/, "");
      }));
      body.appendChild(fieldLabel("Customer domain(s)", domainsInput.el, {
        required: true,
        tip: "How mail and meetings attach to this book. From / To / Cc (mail) or attendees (calendar) must match. Not a people census — we will suggest people after the pull. Example: acme.com",
      }));
      domainsInput.bind();
      var note = document.createElement("p");
      note.className = "muted";
      note.textContent = "Your own domain (from Settings → You) is skipped so internal mail does not become this book.";
      body.appendChild(note);
    }

    function paintFeeds() {
      var byName = {};
      ((status && status.connectors) || []).forEach(function (c) { byName[c.name] = c; });
      var grid = document.createElement("div");
      grid.className = "wizard-feeds";
      FEED_NAMES.forEach(function (name) {
        var c = byName[name] || { name: name, mode: "disabled", connected: false };
        var st = connectorStateOf(c);
        var tile = document.createElement("button");
        tile.type = "button";
        tile.className = "wizard-feed" + (state.feeds[name] ? " is-on" : "");
        var strong = document.createElement("strong");
        strong.textContent = connectorLabel(name);
        tile.appendChild(strong);
        var pill = document.createElement("span");
        setStatePill(pill, st);
        tile.appendChild(pill);
        tile.addEventListener("click", function () {
          state.feeds[name] = !state.feeds[name];
          paint();
        });
        grid.appendChild(tile);
      });
      body.appendChild(fieldLabel("Feeds for this book", grid, {
        required: true,
        tip: "Which systems should fill this customer. Tiles match Settings → Connectors. Active means you already connected it. Error / inactive still lets you mark the feed — connect it later, then Sync. Finish only pulls feeds that are live.",
      }));
      var note = document.createElement("p");
      note.className = "muted";
      note.textContent = "Gmail and Google Calendar are pre-ticked when they are connected. IMAP is the SMTP/IMAP card. Microsoft 365 is Outlook mail; M365 Calendar is the calendar side.";
      body.appendChild(note);
    }

    function paintLookback() {
      var lead = document.createElement("p");
      lead.className = "muted";
      lead.textContent = "This is the first-pull window for mail and calendar feeds you ticked. The desk searches YOUR connected mailbox and calendar for rows whose From / To / Cc or attendees match this company’s domain(s). It does not download the whole mailbox, and it cannot open another CSM’s inbox.";
      body.appendChild(lead);
      var box = document.createElement("div");
      box.className = "wizard-lookback";
      var opts = [
        { n: 14, title: "14 days", blurb: "Last two weeks of mail plus meetings in that window and the next two weeks on the calendar. Fast. Best for view-only or a book you already know." },
        { n: 90, title: "90 days", blurb: "Last quarter. Default for takeover and covering so you see recent threads and the next meetings. Still capped at 200 messages this pass." },
        { n: 365, title: "365 days", blurb: "Last year. Slower. Same 200-message cap so a huge mailbox does not freeze the desk. Older mail stays in Gmail until you Sync again." },
      ];
      opts.forEach(function (opt) {
        var lab = document.createElement("label");
        if (state.lookback_days === opt.n) lab.className = "is-on";
        var radio = document.createElement("input");
        radio.type = "radio";
        radio.name = "lookback";
        radio.value = String(opt.n);
        radio.checked = state.lookback_days === opt.n;
        radio.addEventListener("change", function () {
          state.lookbackTouched = true;
          state.lookback_days = opt.n;
          paint();
        });
        var copy = document.createElement("span");
        var strong = document.createElement("strong");
        strong.textContent = opt.title;
        var blurb = document.createElement("span");
        blurb.textContent = opt.blurb;
        copy.appendChild(strong);
        copy.appendChild(blurb);
        lab.appendChild(radio);
        lab.appendChild(copy);
        box.appendChild(lab);
      });
      body.appendChild(fieldLabel("How far back", box, {
        required: true,
        tip: "Applies to Gmail, IMAP, Microsoft 365, Google Calendar, and M365 Calendar. Jira / Slack / Teams / Salesforce use their own incremental since. Home still only shows unread mail and meetings in the Agenda range — not 365 days on one screen.",
      }));
      var mins = document.createElement("input");
      mins.type = "number";
      mins.min = "1";
      mins.max = "1440";
      mins.step = "1";
      mins.value = String(state.refresh_minutes || 5);
      mins.addEventListener("change", function () {
        var n = parseInt(mins.value, 10);
        if (!n || n < 1) n = 5;
        if (n > 1440) n = 1440;
        state.refresh_minutes = n;
        mins.value = String(n);
      });
      body.appendChild(fieldLabel("Auto-refresh every (minutes)", mins, {
        required: true,
        tip: "After the first pull, the desk one-shots Gmail and Calendar for new/changed/cancelled rows. Default 5. Uses a Couchbase Lite checkpoint, not a standing Google connection. Home → Refresh does the same pull now.",
      }));
      var autoDraft = document.createElement("input");
      autoDraft.type = "checkbox";
      autoDraft.checked = !!state.auto_draft_replies;
      autoDraft.addEventListener("change", function () {
        state.auto_draft_replies = !!autoDraft.checked;
      });
      var autoLab = document.createElement("div");
      autoLab.className = "check-inline";
      autoLab.appendChild(autoDraft);
      autoLab.appendChild(document.createTextNode("On — draft a Grok reply to Gmail Drafts"));
      body.appendChild(fieldLabel("AI Suggest Response to Draft", autoLab, {
        tip: "When mail is addressed to you (To:), Grok drafts a reply from this book — tickets, Slack/Teams, people, past mail, and your intent — and saves it to Gmail Drafts. Off by default. Needs Gmail Drafts permission.",
      }));
    }

    function paintAttach() {
      var summary = document.createElement("dl");
      summary.className = "sheet-kv";
      function kv(k, v) {
        var dt = document.createElement("dt");
        dt.textContent = k;
        var dd = document.createElement("dd");
        dd.textContent = v;
        summary.appendChild(dt);
        summary.appendChild(dd);
      }
      kv("Role", coverageLabel(state));
      kv("Book", (state.name || "—") + " · " + (state.abbr || "").toUpperCase());
      kv("Domains", (domainsInput ? domainsInput.values() : []).map(function (d) {
        return "@" + String(d).replace(/^@/, "");
      }).join(" ") || "—");
      kv("Look back", state.lookback_days + " days");
      kv("Auto-refresh", "every " + (state.refresh_minutes || 5) + " min");
      kv("AI Suggest Response to Draft", state.auto_draft_replies ? "On — To: you → Gmail Drafts" : "Off");
      kv("Feeds", FEED_NAMES.filter(function (n) { return state.feeds[n]; }).map(connectorLabel).join(", ") || "—");
      kv("People", state.mine_people ? "Mine after pull (you tick who to add)" : "Skip for now");
      body.appendChild(summary);
      var p = document.createElement("p");
      p.className = "muted";
      p.textContent = "Finish pulls the ticked live feeds, then shows a processing report. People are de-duped by email. We do not auto-create anyone.";
      body.appendChild(p);
    }

    function paintPeople() {
      var lead = document.createElement("p");
      lead.className = "muted";
      lead.textContent = "After the pull, mine customer people from mail, meetings, tickets, Slack, and Teams on this book. De-dupe by email. Last, First headers and first.last@domain become a proper name. Title, group, phone, and job description land when those feeds have them. You tick who to add — we do not auto-create a person for every address.";
      body.appendChild(lead);
      var box = document.createElement("div");
      box.appendChild(choice(
        "Mine people",
        "Scan this book’s inputs, de-dupe, and list them on the processing report. Default. Already-on-book emails stay skipped.",
        state.mine_people,
        function () {
          state.mine_people = true;
          paint();
        }
      ));
      box.appendChild(choice(
        "Skip for now",
        "Do not pre-tick anyone. You can still open Inputs later and mine.",
        !state.mine_people,
        function () {
          state.mine_people = false;
          paint();
        }
      ));
      body.appendChild(fieldLabel("People on this book", box, {
        required: true,
        tip: "Mail often has Last, First or first.last@acme.com. Slack, Teams, and tickets add more hits on the same email so one person is created, not three.",
      }));
    }

    function paint() {
      setError("");
      paintTrain();
      empty(body);
      if (state.step === 0) paintRole();
      else if (state.step === 1) paintBook();
      else if (state.step === 2) paintDomains();
      else if (state.step === 3) paintFeeds();
      else if (state.step === 4) paintLookback();
      else if (state.step === 5) paintPeople();
      else paintAttach();
      empty(foot);
      var back = document.createElement("button");
      back.type = "button";
      back.className = "btn";
      back.textContent = "Back";
      back.disabled = state.step === 0;
      back.addEventListener("click", function () {
        if (state.step > 0) {
          state.step -= 1;
          paint();
        }
      });
      var next = document.createElement("button");
      next.type = "button";
      next.className = "btn btn-primary";
      next.textContent = state.step === STEPS.length - 1 ? "Finish" : "Next";
      next.addEventListener("click", function () {
        var msg = validate();
        if (msg) {
          setError(msg);
          return;
        }
        if (state.step < STEPS.length - 1) {
          state.step += 1;
          paint();
          return;
        }
        finish();
      });
      foot.appendChild(back);
      foot.appendChild(next);
    }

    function finish() {
      var msg = validate();
      if (msg) {
        setError(msg);
        return;
      }
      foot.querySelectorAll("button").forEach(function (b) { b.disabled = true; });
      var payload = {
        name: state.name.trim(),
        slug: slugFromName(state.slug || state.name),
        abbr: abbrFromName(state.abbr || state.name),
        color: state.color,
        domains: domainsInput ? domainsInput.values() : [],
        coverage: {
          mode: state.mode,
          viewer_kind: state.viewer_kind,
          previous_owner_email: state.previous_owner_email,
          until: state.until,
          lookback_days: state.lookback_days,
          feeds: FEED_NAMES.filter(function (n) { return state.feeds[n]; }),
          mine_people: !!state.mine_people,
          refresh_minutes: state.refresh_minutes || 5,
          auto_draft_replies: !!state.auto_draft_replies,
        },
      };
      api("/api/accounts", { method: "POST", body: JSON.stringify(payload) }).then(function (doc) {
        var chain = Promise.resolve(doc);
        if (state.pendingLogo && doc && doc.account_id) {
          chain = api("/api/accounts/" + encodeURIComponent(doc.account_id) + "/logo", {
            method: "POST",
            body: JSON.stringify({ image: state.pendingLogo }),
          }).then(function () { return doc; });
        }
        return chain;
      }).then(function (doc) {
        toast("Company saved");
        if (!doc || !doc.account_id) return doc;
        var feeds = FEED_NAMES.filter(function (n) { return state.feeds[n]; });
        var pullable = ((status && status.connectors) || []).filter(function (c) {
          return feeds.indexOf(c.name) >= 0 && c.mode === "live" && (c.connected || c.ok);
        });
        var jobsP = pullable.length ? attachLiveGoogle(doc.account_id, feeds) : Promise.resolve([]);
        return jobsP.then(function (jobs) {
          return openProcessingReport(doc, jobs || []);
        });
      }).catch(function (ex) {
        setError(String(ex.message || ex));
      });
    }

    paint();
  }

  function openCompanyForm(acct) {
    acct = acct || null;
    if (!acct) {
      openCompanyWizard();
      return;
    }
    var box = $("detail-box");
    if (!box) return;
    box.hidden = false;
    box.classList.remove("hidden");
    empty(box);
    var sheet = document.createElement("article");
    sheet.className = "sheet sheet-company";
    var head = document.createElement("header");
    var h = document.createElement("h2");
    h.textContent = acct ? "Edit company" : "Add company";
    var close = document.createElement("button");
    close.type = "button";
    close.className = "btn btn-ghost sheet-close";
    close.textContent = "×";
    close.addEventListener("click", closeDetail);
    head.appendChild(h);
    head.appendChild(close);
    sheet.appendChild(head);
    var form = document.createElement("form");
    form.className = "form-grid";
    var name = document.createElement("input");
    name.required = true;
    name.placeholder = "Acme Inc";
    name.value = (acct && acct.name) || "";
    var slug = document.createElement("input");
    slug.required = !acct;
    slug.placeholder = "acme";
    slug.value = (acct && acct.slug) || "";
    slug.disabled = !!acct;
    var abbr = document.createElement("input");
    abbr.required = true;
    abbr.maxLength = 6;
    abbr.placeholder = "ACME";
    abbr.value = (acct && acct.abbr) || "";
    var color = document.createElement("input");
    color.type = "color";
    color.value = /^#[0-9A-Fa-f]{6}$/.test((acct && acct.color) || "") ? acct.color : "#0B3D91";
    var hex = document.createElement("input");
    hex.type = "text";
    hex.maxLength = 7;
    hex.value = color.value;
    hex.setAttribute("aria-label", "Hex color");
    color.addEventListener("input", function () { hex.value = color.value; });
    hex.addEventListener("change", function () {
      var v = hex.value.trim();
      if (v.charAt(0) !== "#") v = "#" + v;
      if (/^#[0-9A-Fa-f]{6}$/.test(v)) {
        color.value = v;
        hex.value = v;
      }
    });
    var colorRow = document.createElement("div");
    colorRow.className = "color-row";
    colorRow.appendChild(color);
    colorRow.appendChild(hex);
    var pendingLogo = "";
    var logoWrap = document.createElement("div");
    logoWrap.className = "logo-edit";
    var preview = document.createElement("div");
    preview.className = "logo-preview";
    function showLogoPreview(src) {
      empty(preview);
      if (src) {
        var img = document.createElement("img");
        img.src = src;
        img.alt = "";
        preview.appendChild(img);
      } else {
        preview.textContent = "No logo";
      }
    }
    showLogoPreview(logoSrc(acct));
    var logoBtns = document.createElement("div");
    var change = document.createElement("button");
    change.type = "button";
    change.className = "btn";
    change.textContent = "Change logo";
    change.addEventListener("click", function () {
      openLogoCrop(function (dataUrl) {
        pendingLogo = dataUrl;
        showLogoPreview(dataUrl);
        if (acct && acct.account_id) {
          api("/api/accounts/" + encodeURIComponent(acct.account_id) + "/logo", {
            method: "POST",
            body: JSON.stringify({ image: dataUrl }),
          }).then(function (doc) {
            acct.has_logo = true;
            acct.logo_updated_at = doc.logo_updated_at;
            pendingLogo = "";
            toast("Logo saved");
            loadHome(true);
            loadSettings();
          }).catch(function (err) {
            toast(String(err.message || err));
          });
        }
      });
    });
    var removeLogo = document.createElement("button");
    removeLogo.type = "button";
    removeLogo.className = "btn btn-cancel";
    removeLogo.textContent = "Remove logo";
    removeLogo.addEventListener("click", function () {
      pendingLogo = "";
      showLogoPreview("");
      if (acct && acct.account_id && acct.has_logo) {
        api("/api/accounts/" + encodeURIComponent(acct.account_id) + "/logo", { method: "DELETE" }).then(function () {
          acct.has_logo = false;
          toast("Logo removed");
          loadHome();
          loadSettings();
        });
      }
    });
    logoBtns.appendChild(change);
    logoBtns.appendChild(removeLogo);
    logoWrap.appendChild(preview);
    logoWrap.appendChild(logoBtns);
    var domainVals = ((acct && acct.domains) || []).map(function (d) {
      return "@" + String(d).replace(/^@/, "");
    });
    var conn = (acct && acct.connectors) || {};
    var domains = makeTagInput("@acme.com", domainVals);
    var jira = makeTagInput("PROJ", connectorList(conn, "jira", "project_keys"));
    var slack = makeTagInput("C0XXXX", connectorList(conn, "slack", "channel_ids"));
    var teams = makeTagInput("19:channel", connectorList(conn, "teams", "channel_ids"));
    var sfdc = makeTagInput("001XXXX", connectorList(conn, "salesforce", "account_ids"));
    form.appendChild(fieldLabel("Name", name, {
      required: true,
      tip: "The customer’s name as you say it. Shows on Home chips and the book header.",
    }));
    form.appendChild(fieldLabel("Slug", slug, {
      required: true,
      tip: "Permanent id: acct:{slug}. You cannot rename the slug later.",
    }));
    form.appendChild(fieldLabel("Abbr", abbr, {
      required: true,
      tip: "2–6 letters or digits on every chip. You can rename this later. Example: HEALTH.",
    }));
    form.appendChild(fieldLabel("Color", colorRow, {
      required: true,
      tip: "Chip color on Home and the book. Example: #0B3D91.",
    }));
    form.appendChild(fieldLabel("Logo", logoWrap, {
      tip: "Optional. Square crop. Shows on Agenda cards and the book header.",
    }));
    form.appendChild(fieldLabel("Customer domain(s)", domains.el, {
      required: true,
      tip: "From / To / Cc and calendar attendees must match a domain here or the row stays unassigned. Example: acme.com",
    }));
    var refreshMins = document.createElement("input");
    refreshMins.type = "number";
    refreshMins.min = "1";
    refreshMins.max = "1440";
    refreshMins.step = "1";
    refreshMins.value = String(((acct && acct.coverage) || {}).refresh_minutes || 5);
    form.appendChild(fieldLabel("Auto-refresh every (minutes)", refreshMins, {
      required: true,
      tip: "How often this book is willing to one-shot Gmail and Calendar for new mail and meetings. Default 5. The desk uses the shortest interval among your companies. Home → Refresh runs it now.",
    }));
    var autoDraft = document.createElement("input");
    autoDraft.type = "checkbox";
    autoDraft.checked = !!(((acct && acct.coverage) || {}).auto_draft_replies);
    var autoLab = document.createElement("div");
    autoLab.className = "check-inline";
    autoLab.appendChild(autoDraft);
    autoLab.appendChild(document.createTextNode("On — draft a Grok reply to Gmail Drafts"));
    form.appendChild(fieldLabel("AI Suggest Response to Draft", autoLab, {
      tip: "When mail is addressed to you (To:), Grok drafts a reply from this book — tickets, Slack/Teams, people, past mail, and your intent and style — and saves it to Gmail Drafts. Off by default. Needs Gmail Drafts (Sign in with Google and allow composing).",
    }));
    form.appendChild(fieldLabel("Jira tags / project keys", jira.el, {
      tip: "Project keys on this book, for example PROJ or ACME. Used to route tickets.",
    }));
    form.appendChild(fieldLabel("Slack channels", slack.el, {
      tip: "Channel ids (C…) so Slack history lands on this book.",
    }));
    form.appendChild(fieldLabel("Teams channels", teams.el, {
      tip: "Teams thread or channel ids for this book.",
    }));
    form.appendChild(fieldLabel("Salesforce accounts", sfdc.el, {
      tip: "Salesforce account ids (001…) when that connector is live.",
    }));
    var foot = document.createElement("div");
    foot.className = "sheet-foot";
    var reportBtn = document.createElement("button");
    reportBtn.type = "button";
    reportBtn.className = "btn";
    reportBtn.textContent = "Inputs";
    reportBtn.addEventListener("click", function () {
      openProcessingReport(acct, null);
    });
    var save = document.createElement("button");
    save.type = "submit";
    save.className = "btn btn-primary";
    save.textContent = "Save";
    foot.appendChild(reportBtn);
    foot.appendChild(save);
    form.appendChild(foot);
    sheet.appendChild(form);
    box.appendChild(sheet);
    domains.bind();
    jira.bind();
    slack.bind();
    teams.bind();
    sfdc.bind();
    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var connectors = {
        jira: { project_keys: jira.values() },
        slack: { channel_ids: slack.values() },
        teams: { channel_ids: teams.values() },
        salesforce: { account_ids: sfdc.values() },
      };
      if (acct && acct.connectors) {
        connectors = Object.assign({}, acct.connectors, connectors);
      }
      var mins = parseInt(refreshMins.value, 10);
      if (!mins || mins < 1) mins = 5;
      if (mins > 1440) mins = 1440;
      var payload = {
        name: name.value,
        abbr: abbr.value,
        color: color.value,
        domains: domains.values(),
        connectors: connectors,
        coverage: Object.assign({}, (acct && acct.coverage) || {}, {
          refresh_minutes: mins,
          auto_draft_replies: !!autoDraft.checked,
        }),
      };
      var req = acct
        ? api("/api/accounts/" + encodeURIComponent(acct.account_id), { method: "PATCH", body: JSON.stringify(payload) })
        : api("/api/accounts", { method: "POST", body: JSON.stringify(Object.assign({ slug: slug.value }, payload)) });
      req.then(function (doc) {
        if (pendingLogo && doc && doc.account_id) {
          return api("/api/accounts/" + encodeURIComponent(doc.account_id) + "/logo", {
            method: "POST",
            body: JSON.stringify({ image: pendingLogo }),
          }).then(function () { return doc; });
        }
        return doc;
      }).then(function (doc) {
        toast("Company saved");
        loadSettings();
        loadHome(true);
        if (doc && doc.account_id) {
          var feeds = ((doc.coverage || {}).feeds || []);
          var pull = feeds.length ? attachLiveGoogle(doc.account_id, feeds) : Promise.resolve([]);
          return pull.then(function (jobs) {
            return openProcessingReport(doc, jobs || []);
          });
        }
        closeDetail();
      }).catch(function (err) {
        toast(String(err.message || err));
      });
    });
  }

  function bind() {
    var qEl = $("account-q");
    if (qEl) {
      qEl.addEventListener("input", function () {
        accountQ = qEl.value || "";
        renderSlashSuggest();
        if (searchTimer) clearTimeout(searchTimer);
        searchTimer = setTimeout(function () {
          applyAccountSearch(false);
        }, 160);
      });
      qEl.addEventListener("keydown", function (ev) {
        var box = $("account-suggest");
        var open = box && !box.hidden;
        if (ev.key === "Escape" && open) {
          ev.preventDefault();
          hideSlashSuggest();
          return;
        }
        if (open && (ev.key === "ArrowDown" || ev.key === "ArrowUp")) {
          ev.preventDefault();
          var opts = box.querySelectorAll(".search-opt");
          if (!opts.length) return;
          slashIndex = ev.key === "ArrowDown"
            ? (slashIndex + 1) % opts.length
            : (slashIndex - 1 + opts.length) % opts.length;
          opts.forEach(function (el, i) {
            el.classList.toggle("is-on", i === slashIndex);
          });
          return;
        }
        if (ev.key === "Enter") {
          ev.preventDefault();
          if (open) {
            var on = box.querySelector(".search-opt.is-on") || box.querySelector(".search-opt");
            if (on) {
              var handle = on.getAttribute("data-handle");
              if (handle) pickPerson(handle, (accountQ || "").indexOf("/people") === 0);
              else pickSlash(on.getAttribute("data-cmd"));
              return;
            }
          }
          applyAccountSearch(true);
        }
      });
      qEl.addEventListener("focus", function () {
        loadChatPeople();
        renderSlashSuggest();
      });
    }
    document.addEventListener("click", function (ev) {
      var tools = $("account-tools");
      if (tools && !tools.contains(ev.target)) hideSlashSuggest();
    });
    var projEl = $("account-project");
    if (projEl) {
      projEl.addEventListener("change", function () {
        accountProject = projEl.value || "";
        if (currentAccount) renderPane(currentAccount, currentTab);
      });
    }
    var detail = $("detail-box");
    if (detail) {
      detail.addEventListener("click", function (ev) {
        if (ev.target === detail) closeDetail();
      });
    }
    document.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape") {
        var taskBox = $("task-box");
        if (taskBox && !taskBox.hidden) {
          closeTaskForm();
          return;
        }
        if (window.CSMWorld && window.CSMWorld.isOpen && window.CSMWorld.isOpen()) {
          window.CSMWorld.close();
          return;
        }
        var crop = $("crop-box");
        if (crop && !crop.hidden) {
          closeCrop();
          return;
        }
        var sug = $("account-suggest");
        if (sug && !sug.hidden) {
          hideSlashSuggest();
          return;
        }
        closeDetail();
      }
    });
    var cropBox = $("crop-box");
    if (cropBox) {
      cropBox.addEventListener("click", function (ev) {
        if (ev.target === cropBox) closeCrop();
      });
    }
    if ($("desk-clock")) {
      $("desk-clock").addEventListener("click", function () {
        if (window.CSMWorld) window.CSMWorld.open();
      });
    }
    var worldBox = $("world-box");
    if (worldBox) {
      worldBox.addEventListener("click", function (ev) {
        if (ev.target === worldBox && window.CSMWorld) window.CSMWorld.close();
      });
    }
    var taskBox = $("task-box");
    if (taskBox) {
      taskBox.addEventListener("click", function (ev) {
        if (ev.target === taskBox) closeTaskForm();
      });
    }
    $("sidebar-toggle").addEventListener("click", function () {
      $("app").classList.toggle("is-mini");
      var mini = $("app").classList.contains("is-mini");
      $("sidebar-toggle").setAttribute("aria-label", mini ? "Expand sidebar" : "Collapse sidebar");
    });
    $("home-q").addEventListener("input", function () {
      if (homeItems) paintHomeBoard();
      else loadHome();
    });
    var chatForm = $("home-chat-form");
    if (chatForm) {
      chatForm.addEventListener("submit", function (ev) {
        ev.preventDefault();
        hideChatMentions();
        sendHomeChat();
      });
    }
    bindChatMentions();
    if ($("btn-chat-history")) $("btn-chat-history").addEventListener("click", toggleChatHistory);
    if ($("btn-chat-bookmark")) $("btn-chat-bookmark").addEventListener("click", toggleChatBookmark);
    if ($("btn-chat-new")) $("btn-chat-new").addEventListener("click", startNewChat);
    if ($("btn-home-refresh")) {
      $("btn-home-refresh").addEventListener("click", function () {
        var btn = $("btn-home-refresh");
        btn.disabled = true;
        var prev = btn.textContent;
        btn.textContent = "Refreshing…";
        api("/api/sync/refresh", { method: "POST", body: "{}" }).then(function (data) {
          var jobs = data.jobs || [];
          if (!jobs.length) toast("Connect Gmail or Calendar in Settings, then Refresh");
          jobs.forEach(function (j) { toast(syncToast(j.connector || j.name, j)); });
          var home = loadHome(true);
          var agenda = homeTab !== "companies" ? loadAgenda() : Promise.resolve();
          return Promise.all([home, agenda]);
        }).catch(function (err) {
          toast(String(err.message || err));
        }).then(function () {
          btn.disabled = false;
          btn.textContent = prev || "Refresh";
        });
      });
    }
    $("btn-refresh-health").addEventListener("click", function () {
      api("/api/accounts").then(function (data) {
        var jobs = (data.items || []).map(function (a) {
          return api("/api/accounts/" + encodeURIComponent(a.account_id) + "/rescore", { method: "POST", body: "{}" });
        });
        return Promise.all(jobs);
      }).then(function () {
        toast("Health refreshed");
        loadHome(true);
      });
    });
    if ($("actions-due")) $("actions-due").addEventListener("change", loadActions);
    if ($("actions-status")) $("actions-status").addEventListener("change", loadActions);
    if ($("btn-gen-report")) {
      $("btn-gen-report").addEventListener("click", function () {
        var aid = $("report-account") && $("report-account").value;
        if (!aid) return;
        api("/api/reports/generate", { method: "POST", body: JSON.stringify({ account_id: aid }) }).then(function () {
          toast("Report saved");
          loadReports();
        });
      });
    }
    function startGoogleSignIn() {
      var email = ($("op-email") && $("op-email").value) || "";
      var save = email
        ? api("/api/settings", { method: "PUT", body: JSON.stringify({ operator: { email: email } }) })
        : Promise.resolve();
      save.then(function () {
        window.open("/api/oauth/google/start", "csm-oauth", "width=520,height=720");
      }).catch(function (err) {
        toast(String(err.message || err));
      });
    }
    if (window.CSM) window.CSM.startGoogleSignIn = startGoogleSignIn;
    if ($("btn-google-signin")) {
      $("btn-google-signin").addEventListener("click", startGoogleSignIn);
    }
    if ($("btn-save-operator")) {
      $("btn-save-operator").addEventListener("click", function () {
        api("/api/settings", {
          method: "PUT",
          body: JSON.stringify({
            operator: {
              name: ($("op-name") && $("op-name").value) || "",
              phone: ($("op-phone") && $("op-phone").value) || "",
              email: ($("op-email") && $("op-email").value) || "",
              timezone: ($("op-timezone") && $("op-timezone").value) || "UTC",
              persona: ($("op-persona") && $("op-persona").value) || "csm",
              intent: ($("op-intent") && $("op-intent").value) || "",
            },
          }),
        }).then(function () {
          toast("Profile saved");
          var prev = operatorTz;
          return refreshStatus().then(function () {
            if (operatorTz !== prev) agendaDay = todayYmd();
          });
        });
      });
    }
    if ($("pref-week-start")) {
      $("pref-week-start").addEventListener("change", function () {
        savePreferences({ week_start: +$("pref-week-start").value });
      });
    }
    if ($("pref-days")) {
      $("pref-days").addEventListener("change", function (ev) {
        var hidden = readHiddenDays();
        if (hidden === null) {
          var cb = ev.target;
          if (cb && cb.type === "checkbox") cb.checked = true;
          toast("Keep at least one day visible");
          return;
        }
        savePreferences({ hidden_weekdays: hidden });
      });
    }
    if ($("pref-theme")) {
      $("pref-theme").addEventListener("change", function (ev) {
        var v = ev.target && ev.target.value;
        if (v) savePreferences({ theme: v }, { calendar: false });
      });
    }
    if ($("btn-theme")) {
      $("btn-theme").addEventListener("click", function () {
        savePreferences({ theme: resolvedTheme() === "night" ? "day" : "night" }, { calendar: false });
      });
    }
    if ($("btn-add-company")) {
      $("btn-add-company").addEventListener("click", function () {
        openCompanyForm(null);
      });
    }
    if ($("btn-save-sso")) {
      $("btn-save-sso").addEventListener("click", function () {
        var org = ($("sso-portal") && $("sso-portal").value) || "";
        var conn = { okta: { org_url: org } };
        if ($("sso-client-id") && $("sso-client-id").value) conn.okta.client_id = $("sso-client-id").value;
        if ($("sso-google-id") && $("sso-google-id").value) {
          conn.google = Object.assign({}, conn.google || {}, { client_id: $("sso-google-id").value });
        }
        if ($("sso-google-secret") && $("sso-google-secret").value) {
          conn.google = Object.assign({}, conn.google || {}, { client_secret: $("sso-google-secret").value });
        }
        if ($("sso-ms-id") && $("sso-ms-id").value) conn.microsoft = { client_id: $("sso-ms-id").value };
        if ($("sso-slack-id") && $("sso-slack-id").value) conn.slack = { client_id: $("sso-slack-id").value };
        api("/api/settings", { method: "PUT", body: JSON.stringify({ sso: { org_url: org } }) }).then(function () {
          return api("/api/settings/keys", { method: "PUT", body: JSON.stringify({ connectors: conn }) });
        }).then(function () {
          toast("SSO saved");
          loadSettings();
        }).catch(function (err) {
          toast(String(err.message || err));
        });
      });
    }
    if ($("btn-sso-signin")) {
      $("btn-sso-signin").addEventListener("click", function () {
        var org = ($("sso-portal") && $("sso-portal").value) || "";
        var conn = { okta: { org_url: org } };
        if ($("sso-client-id") && $("sso-client-id").value) conn.okta.client_id = $("sso-client-id").value;
        api("/api/settings", { method: "PUT", body: JSON.stringify({ sso: { org_url: org } }) }).then(function () {
          return api("/api/settings/keys", { method: "PUT", body: JSON.stringify({ connectors: conn }) });
        }).then(function () {
          window.open("/api/oauth/okta/start", "csm-sso", "width=520,height=720");
        }).catch(function (err) {
          toast(String(err.message || err));
        });
      });
    }
    if ($("btn-sso-signout")) {
      $("btn-sso-signout").addEventListener("click", function () {
        api("/api/oauth/okta/disconnect", { method: "POST", body: "{}" }).then(function () {
          toast("Signed out");
          loadSettings();
        }).catch(function (err) {
          toast(String(err.message || err));
        });
      });
    }
    if ($("btn-copy-sso-redirect")) {
      $("btn-copy-sso-redirect").addEventListener("click", function () {
        var uri = ($("sso-redirect") && $("sso-redirect").value) || "";
        if (navigator.clipboard && navigator.clipboard.writeText && uri) {
          navigator.clipboard.writeText(uri).then(function () { toast("Redirect URI copied"); });
        } else toast(uri || "Nothing to copy");
      });
    }
    if ($("ai-provider")) {
      $("ai-provider").addEventListener("change", function () {
        paintAiPicker(status, $("ai-provider").value);
      });
    }
    if ($("connector-picker")) {
      $("connector-picker").addEventListener("change", function () {
        pickedConnector = $("connector-picker").value;
        paintConnectorPicker(status);
      });
    }
    $("btn-save-key").addEventListener("click", function () {
      var provider = ($("ai-provider") && $("ai-provider").value) || "grok";
      var body = { ai: {} };
      if ($("ai-key") && $("ai-key").value) body.ai[provider] = $("ai-key").value;
      var ai = {
        provider: provider,
        model: ($("ai-model") && $("ai-model").value) || "",
      };
      api("/api/settings/keys", { method: "PUT", body: JSON.stringify(body) }).then(function () {
        return api("/api/settings", { method: "PUT", body: JSON.stringify({ ai: ai }) });
      }).then(function () {
        if ($("ai-key")) $("ai-key").value = "";
        toast("AI provider saved");
        loadSettings();
      });
    });
    if ($("btn-test-ai")) {
      $("btn-test-ai").addEventListener("click", function () {
        var provider = ($("ai-provider") && $("ai-provider").value) || "grok";
        api("/api/settings/providers/test", { method: "POST", body: JSON.stringify({ provider: provider }) }).then(function (doc) {
          aiTestOk[provider] = !!doc.ok;
          toast((doc.provider || provider) + ": " + (doc.message || (doc.ok ? "ok" : "error")));
          loadSettings();
        }).catch(function (err) {
          aiTestOk[provider] = false;
          toast(String(err.message || err));
          loadSettings();
        });
      });
    }
    $("btn-seed").addEventListener("click", function () {
      api("/api/settings/seed", { method: "POST", body: "{}" }).then(function () {
        toast("Seed loaded");
        resetChatMentionCache();
        loadHome(true);
      });
    });
    $("btn-reset").addEventListener("click", function () {
      confirmDanger({
        title: "Reset store",
        body: "Wipes books and keeps your profile and world clock. Type RESET.",
        token: "RESET",
        confirmLabel: "Reset store",
        onConfirm: function () {
          api("/api/settings/reset", { method: "POST", body: JSON.stringify({ confirm: "RESET" }) }).then(function () {
            toast("Store reset");
            resetChatMentionCache();
            loadHome(true);
          }).catch(function (err) {
            toast(String(err.message || err));
          });
        },
      });
    });
    window.addEventListener("message", function (ev) {
      if (ev.origin !== window.location.origin) return;
      if (!ev.data || !ev.data.csm_oauth) return;
      loadSettings();
    });
    window.addEventListener("hashchange", route);
    startDeskClock();
  }

  window.CSM = {
    api: api,
    toast: toast,
    accountChip: accountChip,
    mountMailComposer: mountMailComposer,
    mountSearchSelect: mountSearchSelect,
    mountTagifyMulti: mountTagifyMulti,
    refreshStatus: refreshStatus,
    formatWhen: formatWhen,
    kindEmoji: kindEmoji,
    timezoneOptions: timezoneOptions,
    todayYmd: todayYmd,
    shiftYmd: shiftYmd,
    formatDayLabel: formatDayLabel,
    getOperatorTz: function () {
      return operatorTz;
    },
    getOperator: function () {
      return (status && status.operator) || {};
    },
    getWorldClock: function () {
      return (status && status.world_clock) || {};
    },
    getPreferences: function () {
      return userPrefs();
    },
    setWorldClock: function (clock) {
      if (!status) status = {};
      status.world_clock = clock || {};
    },
  };

  bind();
  refreshStatus().then(route);
})();
