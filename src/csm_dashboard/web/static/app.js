(function () {
  "use strict";

  var status = { version: "", accounts: [] };
  var currentAccount = null;
  var currentTab = "timeline";
  var homeChatId = "";
  var chatScope = "";
  var chatBookmarked = false;
  var accountQ = "";
  var accountProject = "";
  var lastAccountAbbr = "";
  var accountProjects = [];
  var searchTimer = null;
  var slashIndex = 0;
  var notesDirty = false;
  var homeTab = "agenda";
  var agendaDay = "";
  var agendaInboxFilter = "all";
  var agendaInboxItems = [];
  var agendaProjFilter = "";
  var agendaProjOptions = [];
  var agendaProjBound = false;
  var agendaProjProbe = null;
  var peopleAllProjects = false;
  var operatorTz = "UTC";
  var deskClockTimer = 0;
  var deskClockFmts = { tz: "", hour24: null, time: null, date: null, zone: null };
  var homeItems = null;
  var helpReady = false;
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
    { cmd: "slack", tab: "slack", note: false, label: "Slack", example: "/slack pin" },
    { cmd: "teams", tab: "teams", note: false, label: "Teams", example: "/teams Bob" },
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

  function $(id) {
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
    var el = document.createElement("div");
    el.className = "toast";
    el.textContent = msg;
    box.appendChild(el);
    setTimeout(function () {
      el.remove();
    }, 2800);
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

  function kindIcon(kind) {
    var wrap = document.createElement("span");
    wrap.className = "kind-icon is-" + (kind || "email");
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

  function route() {
    closeDetail();
    var parts = hashParts();
    var head = (parts[0] || "home").toLowerCase();
    if (head === "account" && parts[1]) {
      showView("home");
      currentTab = (parts[2] || "timeline").toLowerCase();
      if (HIDDEN_TABS[currentTab]) currentTab = "timeline";
      setHomeMode(true);
      loadAccount(parts[1], currentTab).then(function () {
        syncChatScope(currentAccount && currentAccount.account_id);
      });
      return;
    }
    if (head === "compose" && parts[1]) {
      showView("home");
      setHomeMode(true);
      var openCompose = function () {
        syncChatScope(currentAccount && currentAccount.account_id);
        if (window.CSMCompose) window.CSMCompose.open(currentAccount);
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
        badge.title = "Listening on " + (s.host || "127.0.0.1") + ":" + (s.port || 8788);
      }
      var tag = $("home-tagline");
      if (tag) tag.textContent = s.tagline || "";
      var xai = $("key-xai");
      if (xai) {
        xai.textContent = s.keys && s.keys.xai ? "present" : "absent";
        xai.className = "pill " + (s.keys && s.keys.xai ? "on" : "off");
      }
      [["key-openai", "openai"], ["key-gemini", "gemini"]].forEach(function (pair) {
        var el = $(pair[0]);
        if (!el) return;
        var on = s.keys && s.keys[pair[1]];
        el.textContent = on ? "present" : "absent";
        el.className = "pill " + (on ? "on" : "off");
      });
      operatorTz = (s.operator && s.operator.timezone) || "UTC";
      tickDeskClock();
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
    var sel = $("op-timezone");
    if (!sel) return;
    var wanted = (selected || "").trim() || "UTC";
    if (sel.options.length > 20) {
      sel.value = wanted;
      if (sel.value !== wanted) {
        var extra = document.createElement("option");
        extra.value = wanted;
        extra.textContent = String(wanted).replace(/_/g, " ");
        sel.insertBefore(extra, sel.firstChild);
        sel.value = wanted;
      }
      return;
    }
    var zones = timezoneOptions();
    if (zones.indexOf("UTC") < 0) zones = ["UTC"].concat(zones);
    if (wanted && zones.indexOf(wanted) < 0) zones = [wanted].concat(zones);
    empty(sel);
    zones.forEach(function (z) {
      var opt = document.createElement("option");
      opt.value = z;
      opt.textContent = String(z).replace(/_/g, " ");
      sel.appendChild(opt);
    });
    sel.value = wanted;
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

  function fetchAgendaLists(calList, inList) {
    empty(calList);
    empty(inList);
    var loading = document.createElement("p");
    loading.className = "muted";
    loading.textContent = "Loading…";
    calList.appendChild(loading.cloneNode(true));
    inList.appendChild(loading);
    return api("/api/home/agenda?date=" + encodeURIComponent(agendaDay)).then(function (data) {
      renderAgendaMeetings(calList, data.meetings || []);
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
    var lists = pane.querySelectorAll(".agenda-list");
    var label = pane.querySelector(".agenda-day-label");
    if (lists.length >= 2) {
      if (label) label.textContent = formatDayLabel(agendaDay);
      var inHead = pane.querySelectorAll(".agenda-col-head")[1];
      if (inHead) ensureAgendaProjFilter(inHead, lists[1]);
      return fetchAgendaLists(lists[0], lists[1]);
    }
    empty(pane);
    var split = document.createElement("div");
    split.className = "agenda-split";
    var cal = document.createElement("section");
    cal.className = "agenda-col";
    var calHead = document.createElement("div");
    calHead.className = "agenda-col-head";
    var calTitle = document.createElement("h2");
    calTitle.textContent = "Meetings";
    var dayNav = document.createElement("div");
    dayNav.className = "agenda-day";
    var prev = document.createElement("button");
    prev.type = "button";
    prev.className = "btn";
    prev.textContent = "←";
    prev.setAttribute("aria-label", "Previous day");
    prev.addEventListener("click", function () {
      agendaDay = shiftYmd(agendaDay, -1);
      loadAgenda();
    });
    var label = document.createElement("span");
    label.className = "agenda-day-label";
    label.textContent = formatDayLabel(agendaDay);
    var next = document.createElement("button");
    next.type = "button";
    next.className = "btn";
    next.textContent = "→";
    next.setAttribute("aria-label", "Next day");
    next.addEventListener("click", function () {
      agendaDay = shiftYmd(agendaDay, 1);
      loadAgenda();
    });
    dayNav.appendChild(prev);
    dayNav.appendChild(label);
    dayNav.appendChild(next);
    calHead.appendChild(calTitle);
    calHead.appendChild(dayNav);
    var calList = document.createElement("div");
    calList.className = "agenda-list";
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
    var filter = document.createElement("select");
    filter.id = "agenda-inbox-filter";
    filter.className = "toolbar-filter agenda-inbox-filter";
    filter.setAttribute("aria-label", "Filter");
    [
      ["all", "All"],
      ["email", "Email"],
      ["slack", "Slack"],
      ["task", "Tasks"],
      ["teams", "Teams"],
    ].forEach(function (pair) {
      var opt = document.createElement("option");
      opt.value = pair[0];
      opt.textContent = pair[1];
      filter.appendChild(opt);
    });
    filter.value = agendaInboxFilter;
    filter.addEventListener("change", function () {
      agendaInboxFilter = filter.value || "all";
      renderAgendaInbox(inList, agendaInboxItems);
    });
    inHead.appendChild(inTitle);
    ensureAgendaProjFilter(inHead, inList);
    inHead.appendChild(filter);
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
        var root = $("agenda-proj-filter");
        var openMenu = $("agenda-proj-menu");
        if (root && root.contains(ev.target)) return;
        if (openMenu && openMenu.contains(ev.target)) return;
        closeAgendaProjMenu();
      });
      window.addEventListener("resize", placeAgendaProjMenu);
      window.addEventListener("scroll", placeAgendaProjMenu, true);
    }
  }

  function renderAgendaMeetings(root, items) {
    empty(root);
    if (!items.length) {
      var p = document.createElement("p");
      p.className = "muted";
      p.textContent = "No meetings this day.";
      root.appendChild(p);
      return;
    }
    items.forEach(function (ev) {
      var card = document.createElement("article");
      card.className = "agenda-meet";
      var when = document.createElement("div");
      when.className = "agenda-meet-time";
      when.textContent = formatWhen(ev.start_at) + (ev.status === "proposed" ? " · proposed" : "");
      var title = document.createElement("div");
      title.className = "acct-meeting-title";
      title.textContent = ev.title || "Meeting";
      var meta = document.createElement("div");
      meta.className = "row-meta";
      var bits = [];
      if (ev.account && ev.account.abbr) bits.push(ev.account.abbr);
      if (ev.location) bits.push(ev.location);
      meta.textContent = bits.join(" · ");
      card.appendChild(when);
      card.appendChild(title);
      card.appendChild(meta);
      if (ev.account && ev.account.abbr) {
        card.addEventListener("click", function () {
          location.hash = "#account/" + ev.account.abbr + "/calendar";
        });
      }
      root.appendChild(card);
    });
  }

  function renderAgendaInbox(root, items) {
    empty(root);
    var want = agendaInboxFilter || "all";
    var shown = (items || []).filter(function (item) {
      if (want !== "all" && item.kind !== want) return false;
      if (!agendaProjFilter) return true;
      var aid = (item.account && item.account.account_id) || "";
      var pid = item.project_id || "";
      var parts = String(agendaProjFilter).split("|");
      if (parts.length === 1) return aid === parts[0];
      return aid === parts[0] && pid === parts[1];
    });
    if (!shown.length) {
      var p = document.createElement("p");
      p.className = "muted";
      var emptyMsg = "No new email, chat, or tasks.";
      if (want === "email") emptyMsg = "No new email.";
      else if (want === "slack") emptyMsg = "No new Slack.";
      else if (want === "teams") emptyMsg = "No new Teams.";
      else if (want === "task") emptyMsg = "No tasks.";
      if (agendaProjFilter) emptyMsg = "Nothing for that company or project.";
      p.textContent = emptyMsg;
      root.appendChild(p);
      return;
    }
    shown.forEach(function (item) {
      var card = document.createElement("article");
      card.className = "agenda-item";
      var top = document.createElement("div");
      top.className = "agenda-item-top";
      top.appendChild(kindIcon(item.kind));
      if (item.account) top.appendChild(accountMark(item.account, "inbox"));
      var title = document.createElement("strong");
      title.textContent = item.title || "";
      top.appendChild(title);
      var body = document.createElement("div");
      body.className = "row-meta";
      body.textContent = item.body || "";
      var when = document.createElement("div");
      when.className = "row-meta";
      when.textContent = formatWhen(item.at);
      card.appendChild(top);
      card.appendChild(body);
      card.appendChild(when);
      if (item.kind === "task" && item.due_at) {
        var due = document.createElement("div");
        due.className = "row-meta agenda-task-due";
        due.textContent = "Due " + formatWhen(item.due_at);
        card.appendChild(due);
      }
      card.addEventListener("click", function () {
        if (item.kind === "task") {
          openTaskForm(item);
          return;
        }
        var abbr = item.account && item.account.abbr;
        if (!abbr) return;
        var tab = item.kind === "email" ? "email" : item.kind === "teams" ? "teams" : "slack";
        location.hash = "#account/" + abbr + "/" + tab;
      });
      root.appendChild(card);
    });
  }

  var TASK_KINDS = ["Action item(s)", "Follow up(s)", "Review(s)", "More Detail(s)"];

  function closeTaskForm() {
    var box = $("task-box");
    if (!box) return;
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
    var emailId = item && item.ref && item.ref.id ? item.ref.id : "";
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
    var name = document.createElement("input");
    name.id = "task-name";
    name.placeholder = "Task name";
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
    var cc = document.createElement("input");
    cc.id = "task-cc";
    cc.className = "tag-input";
    cc.placeholder = "Name or email";
    var body = document.createElement("textarea");
    body.id = "task-body";
    body.rows = 7;
    body.placeholder = "What needs to happen";
    var peopleTagify = null;
    var companyPeople = [];
    function companyLabel() {
      var opt = company.options[company.selectedIndex];
      return opt ? opt.getAttribute("data-name") || opt.textContent : "";
    }
    function refreshPreview() {
      preview.textContent = taskSubjectPreview(companyLabel(), name.value, kind.value);
    }
    function peopleWhitelist(items) {
      return (items || []).filter(function (p) { return p.email; }).map(function (p) {
        return { value: p.email, name: p.name || p.email, email: p.email };
      });
    }
    function ccEmails() {
      if (peopleTagify) {
        return peopleTagify.value.map(function (t) { return t.value || t.email; }).filter(Boolean);
      }
      return csvList(cc.value);
    }
    function setCcEmails(addrs) {
      if (peopleTagify) {
        peopleTagify.removeAllTags();
        var tags = (addrs || []).map(function (addr) {
          var want = String(addr || "").toLowerCase();
          var hit = companyPeople.filter(function (p) {
            return String(p.email || "").toLowerCase() === want;
          })[0];
          return hit
            ? { value: hit.email, name: hit.name || hit.email, email: hit.email }
            : { value: addr, name: addr };
        });
        if (tags.length) peopleTagify.addTags(tags);
        return;
      }
      cc.value = (addrs || []).join(", ");
    }
    function bindPeopleTagify(selected) {
      if (peopleTagify) {
        try { peopleTagify.destroy(); } catch (e) {}
        peopleTagify = null;
      }
      if (!window.Tagify) {
        cc.value = (selected || []).join(", ");
        return;
      }
      peopleTagify = new window.Tagify(cc, {
        whitelist: peopleWhitelist(companyPeople),
        tagTextProp: "name",
        enforceWhitelist: false,
        dropdown: { enabled: 0, maxItems: 20, searchKeys: ["value", "name", "email"], closeOnSelect: false },
        delimiters: ",|\n",
      });
      setCcEmails(selected || []);
    }
    function loadCompanyPeople(aid, selected) {
      if (!aid) {
        companyPeople = [];
        bindPeopleTagify(selected || []);
        return Promise.resolve();
      }
      return api("/api/people?account_id=" + encodeURIComponent(aid)).then(function (data) {
        companyPeople = data.items || [];
        bindPeopleTagify(selected || []);
      });
    }
    company.addEventListener("change", function () {
      refreshPreview();
      loadCompanyPeople(company.value, ccEmails());
      assist.disabled = !company.value;
    });
    name.addEventListener("input", refreshPreview);
    kind.addEventListener("change", refreshPreview);
    var form = document.createElement("div");
    form.className = "settings-form";
    var labCo = document.createElement("label");
    labCo.appendChild(document.createTextNode("Company"));
    labCo.appendChild(company);
    var labName = document.createElement("label");
    labName.appendChild(document.createTextNode("Task name"));
    labName.appendChild(name);
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
    var assist = document.createElement("button");
    assist.type = "button";
    assist.className = "btn";
    assist.id = "btn-task-assist";
    assist.textContent = "AI Assist";
    assist.disabled = true;
    assist.title = "Draft this task from the company, type, and desk context";
    var labCc = document.createElement("label");
    labCc.className = "task-cc-field";
    labCc.appendChild(document.createTextNode("CC"));
    labCc.appendChild(cc);
    var ccRow = document.createElement("div");
    ccRow.className = "task-cc-row settings-span";
    ccRow.appendChild(assist);
    ccRow.appendChild(labCc);
    var labBody = document.createElement("label");
    labBody.className = "settings-span";
    labBody.appendChild(document.createTextNode("Body"));
    labBody.appendChild(body);
    var actions = document.createElement("div");
    actions.className = "settings-actions";
    var save = document.createElement("button");
    save.type = "button";
    save.className = "btn btn-primary";
    save.textContent = emailId ? "Save task" : "Create task";
    assist.addEventListener("click", function () {
      if (!company.value) {
        toast("Pick a company first");
        return;
      }
      assist.disabled = true;
      assist.textContent = "Working…";
      api("/api/tasks/assist", {
        method: "POST",
        body: JSON.stringify({
          account_id: company.value,
          task_kind: kind.value,
          task_name: name.value,
          due_at: due.value,
          body: body.value,
          cc_addrs: ccEmails(),
        }),
      }).then(function (doc) {
        if (doc.task_name) name.value = doc.task_name;
        if (doc.task_kind) kind.value = doc.task_kind;
        if (doc.due_at) due.value = dueInputValue(doc.due_at);
        if (doc.body) body.value = doc.body;
        if (doc.cc_addrs) setCcEmails(doc.cc_addrs);
        refreshPreview();
        toast(doc.result === "grok" ? "Task drafted with Grok" : "Task draft filled");
      }).catch(function (err) {
        toast(String(err.message || err));
      }).then(function () {
        assist.disabled = !company.value;
        assist.textContent = "AI Assist";
      });
    });
    save.addEventListener("click", function () {
      var ccs = ccEmails();
      var payload = {
        account_id: company.value,
        task_name: name.value,
        task_kind: kind.value,
        due_at: due.value,
        cc_addrs: ccs,
        body: body.value,
      };
      var req = emailId
        ? api("/api/tasks/" + encodeURIComponent(emailId), { method: "PUT", body: JSON.stringify(payload) })
        : api("/api/tasks", { method: "POST", body: JSON.stringify(payload) });
      req.then(function () {
        toast(emailId ? "Task saved" : "Task created");
        closeTaskForm();
        loadAgenda();
      }).catch(function (err) {
        toast(String(err.message || err));
      });
    });
    actions.appendChild(save);
    sheet.appendChild(preview);
    sheet.appendChild(form);
    sheet.appendChild(ccRow);
    sheet.appendChild(labBody);
    sheet.appendChild(actions);
    save.disabled = true;
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
        name.value = doc.task_name || "";
        kind.value = doc.task_kind || TASK_KINDS[0];
        due.value = dueInputValue(doc.due_at);
        body.value = doc.content || "";
      } else if (item && item.account && item.account.account_id) {
        company.value = item.account.account_id;
      }
      refreshPreview();
      assist.disabled = !company.value;
      var selectedCc = doc ? (doc.cc_addrs || []) : csvList(cc.value);
      return loadCompanyPeople(company.value, selectedCc).then(function () {
        save.disabled = false;
      });
    }).catch(function (err) {
      save.disabled = false;
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
        ? "This thread stays on " + ((acct && acct.name) || "this account") + "."
        : "Tag a book with #{ACME} or a person with @bob";
    }
    if (input) {
      input.placeholder = onBook
        ? "Ask about " + ((acct && acct.name) || "this account") + "…"
        : "Is there any issue with #{ACME}?";
    }
    renderChatSuggest(scope);
  }

  function renderChatSuggest(scope) {
    var box = $("home-chat-suggest");
    if (!box) return;
    empty(box);
    var samples = scope && scope !== "desk"
      ? [
          "What is at risk?",
          "Who is on the open projects?",
          "Any open tickets I should see?",
        ]
      : [
          "Is there any issue with #{ACME}?",
          "Did @bob from #{ACME} reply to my last email?",
          "What is on fire at #{NWIN}?",
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

  function syncChatScope(scope) {
    scope = scope || "desk";
    updateChatChrome(scope);
    if (scope === chatScope) return;
    chatScope = scope;
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
        appendChat(msg.role === "user" ? "user" : "assistant", msg.content || "");
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
      if (!items.length) {
        var p = document.createElement("p");
        p.className = "muted";
        p.textContent = "No chats yet.";
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
        m.textContent = formatWhen(item.updated_at || item.created_at);
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
    }).catch(function (err) {
      toast(String(err.message || err));
    });
  }

  function appendChat(role, text) {
    var log = $("home-chat-log");
    if (!log) return null;
    var el = document.createElement("div");
    el.className = "chat-bubble " + role;
    el.textContent = text || "";
    log.appendChild(el);
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
    var want = tab || "timeline";
    tabs.querySelectorAll(".tab").forEach(function (b, i) {
      var names = ["timeline", "tickets", "email", "slack", "teams", "salesforce", "calendar", "projects", "people", "orgchart", "accountteam"];
      b.classList.toggle("is-on", names[i] === want);
    });
  }

  function loadAccount(abbr, tab) {
    var want = (abbr || "").toLowerCase();
    if (currentAccount && lastAccountAbbr === want && $("account-tabs") && $("account-tabs").firstChild) {
      currentTab = tab || "timeline";
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
    var names = ["timeline", "tickets", "email", "slack", "teams", "salesforce", "calendar", "projects", "people", "orgchart", "accountteam"];
    var counts = acct.input_counts || {};
    var tabs = $("account-tabs");
    empty(tabs);
    names.forEach(function (name) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "tab" + (name === tab ? " is-on" : "");
      var label = document.createElement("span");
      label.textContent = name === "orgchart" ? "org chart" : name === "accountteam" ? "account team" : name;
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
    if (tab === "slack") return fillList(pane, "/api/slack/messages?account_id=" + encodeURIComponent(aid), slackRow);
    if (tab === "teams") return fillList(pane, "/api/teams/messages?account_id=" + encodeURIComponent(aid), teamsRow);
    if (tab === "salesforce") return fillSalesforce(pane, aid);
    if (tab === "calendar") return fillList(pane, "/api/calendar?account_id=" + encodeURIComponent(aid), calRow);
    if (tab === "projects") return fillProjects(pane, acct);
    if (tab === "people") return fillPeople(pane, acct);
    if (tab === "orgchart") return fillOrgChart(pane, acct);
    if (tab === "accountteam") return fillAccountTeam(pane, acct);
    return fillTimeline(pane, "/api/accounts/" + encodeURIComponent(aid) + "/timeline" + accountQs("", false));
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
      ? SLASH.filter(function (s) { return s.cmd.indexOf(cmd) === 0; })
      : SLASH.slice();
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

  function searchNeedle() {
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
    if (qEl) qEl.focus();
  }

  function renderSlashSuggest() {
    var box = $("account-suggest");
    if (!box) return;
    var s = slashState(accountQ);
    if (!s.open || s.exact && accountQ.indexOf(" ") >= 0) {
      hideSlashSuggest();
      return;
    }
    var rows = s.matches.length ? s.matches : SLASH;
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
      if (!items.length) {
        var p = document.createElement("p");
        p.className = "muted";
        p.textContent = "Nothing here yet.";
        pane.appendChild(p);
        return;
      }
      var ul = document.createElement("ul");
      ul.className = "timeline timeline-vertical timeline-snap-icon";
      items.forEach(function (item, i) {
        var count = (byAct[item._id] || []).length || item.note_count || 0;
        item.note_count = count;
        ul.appendChild(timelineItem(item, i, items.length));
      });
      pane.appendChild(ul);
    });
  }

  function timelineItem(item, index, total) {
    var group = kindGroup(item.kind);
    var li = document.createElement("li");
    li.className = "is-" + group;
    if (index > 0) li.appendChild(document.createElement("hr"));
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
    if (index < total - 1) li.appendChild(document.createElement("hr"));
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
    box.hidden = true;
    box.classList.add("hidden");
    empty(box);
    if (notesDirty && currentAccount && currentTab === "timeline") {
      notesDirty = false;
      renderPane(currentAccount, "timeline");
    }
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

  function mountNoteEditor(sheet, item) {
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
          ref: { collection: "activities", id: item._id },
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
    row.classList.add("is-click");
    row.addEventListener("click", function () {
      if (!item._id) return;
      api("/api/threads/" + encodeURIComponent(item._id) + "/operator", {
        method: "PATCH",
        body: JSON.stringify({ unread: false }),
      }).catch(function () {});
      openThreadLightbox(item);
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
    sh.textContent = "Reply suggestion";
    var hint = document.createElement("p");
    hint.className = "muted";
    hint.textContent = "Uses this thread plus the account (tickets, people, projects).";
    var go = document.createElement("button");
    go.type = "button";
    go.className = "btn btn-primary";
    go.textContent = "Suggest reply";
    var draftTo = document.createElement("input");
    draftTo.placeholder = "To";
    var draftSub = document.createElement("input");
    draftSub.placeholder = "Subject";
    var draftBody = document.createElement("textarea");
    draftBody.placeholder = "Suggested reply appears here";
    var use = document.createElement("button");
    use.type = "button";
    use.className = "btn";
    use.textContent = "Open in Compose";
    suggest.appendChild(sh);
    suggest.appendChild(hint);
    suggest.appendChild(go);
    suggest.appendChild(draftTo);
    suggest.appendChild(draftSub);
    suggest.appendChild(draftBody);
    suggest.appendChild(use);
    sheet.appendChild(suggest);
    box.appendChild(sheet);
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
    go.addEventListener("click", function () {
      go.disabled = true;
      api("/api/threads/" + encodeURIComponent(item._id) + "/suggest-reply", {
        method: "POST",
        body: "{}",
      }).then(function (doc) {
        draftTo.value = (doc.to_addrs || []).join(", ");
        draftSub.value = doc.subject || "";
        draftBody.value = doc.body || "";
        toast(doc.result === "grok" ? "Suggested with Grok" : "Template suggestion");
      }).catch(function (err) {
        toast(String(err.message || err));
      }).then(function () {
        go.disabled = false;
      });
    });
    use.addEventListener("click", function () {
      if (!currentAccount || !window.CSMCompose) return;
      closeDetail();
      window.CSMCompose.open(currentAccount, {
        thread_id: item._id,
        to: draftTo.value,
        subject: draftSub.value,
        body: draftBody.value,
      });
    });
  }

  function slackRow(item) {
    return rowEl(item.user_name || "", item.text || "", item.ts || "");
  }

  function teamsRow(item) {
    return rowEl(item.user_name || "", item.text || "", "Teams · " + (item.ts || ""));
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
    return rowEl((item.start_at || "").slice(0, 16), item.title || "", item.location || "");
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
    var search = document.createElement("input");
    search.className = "search";
    search.type = "search";
    search.id = "project-q";
    search.placeholder = "Search projects";
    search.setAttribute("aria-label", "Search projects");
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
    left.appendChild(search);
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
      var q = (search.value || "").trim().toLowerCase();
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
        paint(accountProjects);
      });
    }
    search.addEventListener("input", function () {
      paint(accountProjects);
    });
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
    var tags = document.createElement("input");
    tags.id = "project-tags";
    tags.placeholder = "Add tags";
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
    labTags.appendChild(tags);
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
        if (!window.confirm("Remove project " + (proj.name || "") + "?")) return;
        api("/api/projects/" + encodeURIComponent(proj._id), { method: "DELETE" }).then(function () {
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
      });
      actions.appendChild(rm);
    }
    var save = document.createElement("button");
    save.type = "button";
    save.className = "btn btn-primary";
    save.textContent = proj ? "Save project" : "Add project";
    var tagify = null;
    save.addEventListener("click", function () {
      var tagVals = [];
      if (tagify) {
        tagify.value.forEach(function (t) {
          if (t && t.value) tagVals.push(t.value);
        });
      } else {
        tagVals = csvList(tags.value);
      }
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
    var whitelist = [];
    accountProjects.forEach(function (p) {
      (p.tags || []).forEach(function (t) {
        if (whitelist.indexOf(t) < 0) whitelist.push(t);
      });
    });
    if (window.Tagify) {
      tagify = new window.Tagify(tags, {
        whitelist: whitelist,
        dropdown: { enabled: 0, maxItems: 20 },
      });
      if (proj && proj.tags && proj.tags.length) tagify.addTags(proj.tags);
    } else if (proj && proj.tags) {
      tags.value = proj.tags.join(", ");
    }
  }

  function personRow(item, acct) {
    var mid = item.name || "";
    if (item.title) mid += " · " + item.title;
    var right = item.email || "";
    if (item.location) right = (right ? right + " · " : "") + item.location;
    var row = rowEl(item.role || item.kind || "", mid, right);
    row.classList.add("is-click");
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
    if (extra.firstChild && row.children[1]) row.children[1].appendChild(extra);
    if (acct) {
      row.addEventListener("click", function () {
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
    bar.className = "pane-toolbar";
    var add = document.createElement("button");
    add.type = "button";
    add.className = "btn btn-primary";
    add.textContent = "Add person";
    add.addEventListener("click", function () {
      openPersonForm(acct);
    });
    bar.appendChild(add);
    pane.appendChild(bar);
    if (peopleAllProjects) {
      var note = document.createElement("p");
      note.className = "muted";
      note.textContent = "Directors / VPs who own all projects.";
      pane.appendChild(note);
    }
    return fillList(pane, peopleUrl(acct), function (item) {
      return personRow(item, acct);
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
      card.addEventListener("click", function () {
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
        tr.addEventListener("click", function () {
          openPersonForm(acct, person);
        });
        tbody.appendChild(tr);
      });
      table.appendChild(tbody);
      pane.appendChild(table);
    });
  }

  function fieldLabel(text, node) {
    var lab = document.createElement("label");
    lab.textContent = text;
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
    items.forEach(function (item) {
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
    var box = $("detail-box");
    if (!box) return;
    box.hidden = false;
    box.classList.remove("hidden");
    empty(box);
    var sheet = document.createElement("article");
    sheet.className = "sheet";
    var head = document.createElement("header");
    var h = document.createElement("h2");
    h.textContent = person ? "Edit person" : "Add person";
    var close = document.createElement("button");
    close.type = "button";
    close.className = "btn btn-ghost sheet-close";
    close.setAttribute("aria-label", "Close");
    close.textContent = "×";
    close.addEventListener("click", closeDetail);
    head.appendChild(h);
    head.appendChild(close);
    sheet.appendChild(head);
    var form = document.createElement("form");
    form.className = "form-grid";
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
    var kind = document.createElement("select");
    [["customer", "Customer"], ["account_team", "Account team"], ["ps_team", "PS team"]].forEach(function (pair) {
      var opt = document.createElement("option");
      opt.value = pair[0];
      opt.textContent = pair[1];
      if (person && person.kind === pair[0]) opt.selected = true;
      kind.appendChild(opt);
    });
    var reports = document.createElement("select");
    var none = document.createElement("option");
    none.value = "";
    none.textContent = "No manager";
    reports.appendChild(none);
    form.appendChild(fieldLabel("Name", name));
    form.appendChild(fieldLabel("Email", email));
    form.appendChild(fieldLabel("Location", location));
    form.appendChild(fieldLabel("Title", title));
    form.appendChild(fieldLabel("Kind", kind));
    form.appendChild(fieldLabel("Reports to", reports));
    var projChecks = checkGroup(person && person.project_ids, accountProjects, function (p) {
      return p.name || p._id;
    });
    form.appendChild(fieldLabel("Projects", projChecks));
    var allProj = document.createElement("input");
    allProj.type = "checkbox";
    allProj.checked = !!(person && person.owns_all_projects);
    var allLab = document.createElement("label");
    allLab.appendChild(allProj);
    allLab.appendChild(document.createTextNode(" All projects (director / VP)"));
    form.appendChild(allLab);
    var fnChecks = checkGroup(person && person.functions, PERSON_FUNCS);
    form.appendChild(fieldLabel("Functions", fnChecks));
    var foot = document.createElement("div");
    foot.className = "sheet-foot";
    var save = document.createElement("button");
    save.type = "submit";
    save.className = "btn btn-primary";
    save.textContent = "Save";
    foot.appendChild(save);
    form.appendChild(foot);
    sheet.appendChild(form);
    box.appendChild(sheet);
    api("/api/people?account_id=" + encodeURIComponent(acct.account_id)).then(function (data) {
      var selfId = (person && person._id) || "";
      (data.items || []).forEach(function (row) {
        if (!row._id || row._id === selfId) return;
        var opt = document.createElement("option");
        opt.value = row._id;
        opt.textContent = row.name || row._id;
        if (person && person.reports_to === row._id) opt.selected = true;
        reports.appendChild(opt);
      });
    });
    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var payload = {
        account_id: acct.account_id,
        name: name.value,
        email: email.value,
        location: location.value,
        title: title.value,
        kind: kind.value,
        reports_to: reports.value,
        project_ids: checkedValues(projChecks),
        functions: checkedValues(fnChecks),
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
    el.classList.remove("is-open");
    var b = el.querySelector(".help-q");
    var a = el.querySelector(".help-a");
    var ic = el.querySelector(".help-q-icon");
    if (b) b.setAttribute("aria-expanded", "false");
    if (a) a.hidden = true;
    if (ic) ic.textContent = "+";
  }

  function openHelpItem(el) {
    if (!el) return;
    el.classList.add("is-open");
    var b = el.querySelector(".help-q");
    var a = el.querySelector(".help-a");
    var ic = el.querySelector(".help-q-icon");
    if (b) b.setAttribute("aria-expanded", "true");
    if (a) a.hidden = false;
    if (ic) ic.textContent = "−";
  }

  function applyHelpTopic(topic) {
    var box = $("help-body");
    if (!box) return;
    box.querySelectorAll(".help-item.is-open").forEach(closeHelpItem);
    var jump = topic ? $("help-" + topic) : null;
    if (jump) {
      openHelpItem(jump);
      jump.scrollIntoView({ block: "start", behavior: "smooth" });
    }
  }

  function loadHelp(topic) {
    var box = $("help-body");
    if (helpReady && box && box.firstChild) {
      applyHelpTopic(topic);
      return;
    }
    api("/api/help").then(function (data) {
      if (!box) box = $("help-body");
      if (!box) return;
      empty(box);
      (data.groups || []).forEach(function (g) {
        var gid = g.id || "";
        var sec = document.createElement("section");
        sec.className = "help-group";
        sec.id = "help-" + gid;
        var h = document.createElement("h2");
        h.textContent = g.title || "";
        sec.appendChild(h);
        (g.items || []).forEach(function (item) {
          var wrap = document.createElement("div");
          wrap.className = "help-item";
          wrap.id = "help-" + (item.id || "");
          var btn = document.createElement("button");
          btn.type = "button";
          btn.className = "help-q";
          btn.setAttribute("aria-expanded", "false");
          var q = document.createElement("span");
          q.className = "help-q-text";
          q.textContent = item.h || "";
          var icon = document.createElement("span");
          icon.className = "help-q-icon";
          icon.setAttribute("aria-hidden", "true");
          icon.textContent = "+";
          btn.appendChild(q);
          btn.appendChild(icon);
          var ans = document.createElement("div");
          ans.className = "help-a";
          ans.hidden = true;
          var p = document.createElement("p");
          p.textContent = item.p || "";
          ans.appendChild(p);
          btn.addEventListener("click", function () {
            var wasOpen = wrap.classList.contains("is-open");
            box.querySelectorAll(".help-item.is-open").forEach(closeHelpItem);
            if (!wasOpen) openHelpItem(wrap);
          });
          wrap.appendChild(btn);
          wrap.appendChild(ans);
          if (topic && (topic === item.id || topic === gid)) openHelpItem(wrap);
          sec.appendChild(wrap);
        });
        box.appendChild(sec);
      });
      helpReady = true;
      applyHelpTopic(topic);
    });
  }

  function loadSettings() {
    refreshStatus().then(function (s) {
      var op = s.operator || {};
      if ($("op-name")) $("op-name").value = op.name || "";
      if ($("op-phone")) $("op-phone").value = op.phone || "";
      if ($("op-email")) $("op-email").value = op.email || "";
      fillTimezoneSelect(op.timezone);
      var ai = s.ai || {};
      if ($("ai-provider")) $("ai-provider").value = ai.provider || "grok";
      if ($("ai-model")) $("ai-model").value = ai.model || s.default_model || "";
      var box = $("connector-list");
      empty(box);
      (s.connectors || []).forEach(function (c) {
        var row = document.createElement("div");
        row.className = "conn-row";
        var name = document.createElement("span");
        name.textContent = c.name || "";
        var mode = document.createElement("span");
        mode.className = "pill";
        mode.textContent = (c.mode || "stub") + (c.ok ? " · ok" : " · down");
        var test = document.createElement("button");
        test.type = "button";
        test.className = "btn";
        test.textContent = "Test";
        test.addEventListener("click", function () {
          api("/api/connectors/" + encodeURIComponent(c.name) + "/test", { method: "POST", body: "{}" }).then(function (doc) {
            toast((c.name || "connector") + ": " + (doc.ok ? "ok" : "down") + " · auth " + (doc.auth || "n/a"));
          }).catch(function (err) {
            toast(String(err.message || err));
          });
        });
        row.appendChild(name);
        row.appendChild(mode);
        row.appendChild(test);
        box.appendChild(row);
      });
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
      p.textContent = "No companies yet. Add one or load seed data.";
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
      meta.textContent = domains || "No customer domains";
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
          if (!window.confirm("Remove " + (acct.name || acct.abbr) + " from the desk?")) return;
          api("/api/accounts/" + encodeURIComponent(acct.account_id), { method: "DELETE" }).then(function () {
            toast("Company removed");
            loadSettings();
            loadHome(true);
          });
        });
        actions.appendChild(edit);
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

  function connectorList(conn, name, key) {
    var rows = ((conn || {})[name] || {})[key];
    return rows && rows.length ? rows.slice() : [];
  }

  function connectorField(conn, name, key) {
    return connectorList(conn, name, key).join("\n");
  }

  function makeTagInput(placeholder, values) {
    var input = document.createElement("input");
    input.className = "tag-input";
    input.placeholder = placeholder || "";
    var inst = null;
    return {
      el: input,
      bind: function () {
        if (inst) return;
        if (window.Tagify) {
          inst = new window.Tagify(input, {
            delimiters: ",|\n",
            dropdown: { enabled: 0, maxItems: 20 },
          });
          if (values && values.length) inst.addTags(values);
        } else if (values && values.length) {
          input.value = values.join(", ");
        }
      },
      values: function () {
        if (inst) {
          return inst.value.map(function (t) { return t && t.value; }).filter(Boolean);
        }
        return csvList(input.value);
      },
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

  function openCompanyForm(acct) {
    acct = acct || null;
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
    name.value = (acct && acct.name) || "";
    var slug = document.createElement("input");
    slug.required = !acct;
    slug.value = (acct && acct.slug) || "";
    slug.disabled = !!acct;
    var abbr = document.createElement("input");
    abbr.required = true;
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
    var domains = makeTagInput("@def.com", domainVals);
    var jira = makeTagInput("DEFUK", connectorList(conn, "jira", "project_keys"));
    var slack = makeTagInput("C0XXXX", connectorList(conn, "slack", "channel_ids"));
    var teams = makeTagInput("19:channel", connectorList(conn, "teams", "channel_ids"));
    var sfdc = makeTagInput("001XXXX", connectorList(conn, "salesforce", "account_ids"));
    form.appendChild(fieldLabel("Name", name));
    form.appendChild(fieldLabel("Slug", slug));
    form.appendChild(fieldLabel("Abbr", abbr));
    form.appendChild(fieldLabel("Color", colorRow));
    form.appendChild(fieldLabel("Logo", logoWrap));
    form.appendChild(fieldLabel("Customer domains", domains.el));
    form.appendChild(fieldLabel("Jira tags / project keys", jira.el));
    form.appendChild(fieldLabel("Slack channels", slack.el));
    form.appendChild(fieldLabel("Teams channels", teams.el));
    form.appendChild(fieldLabel("Salesforce accounts", sfdc.el));
    var foot = document.createElement("div");
    foot.className = "sheet-foot";
    var save = document.createElement("button");
    save.type = "submit";
    save.className = "btn btn-primary";
    save.textContent = "Save";
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
      var payload = {
        name: name.value,
        abbr: abbr.value,
        color: color.value,
        domains: domains.values(),
        connectors: connectors,
      };
      var req = acct
        ? api("/api/accounts/" + encodeURIComponent(acct.account_id), { method: "PATCH", body: JSON.stringify(payload) })
        : api("/api/accounts", { method: "POST", body: JSON.stringify(Object.assign({ slug: slug.value }, payload)) });
      req.then(function (doc) {
        if (pendingLogo && doc && doc.account_id) {
          return api("/api/accounts/" + encodeURIComponent(doc.account_id) + "/logo", {
            method: "POST",
            body: JSON.stringify({ image: pendingLogo }),
          });
        }
        return doc;
      }).then(function () {
        closeDetail();
        toast("Company saved");
        loadSettings();
        loadHome(true);
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
              pickSlash(on.getAttribute("data-cmd"));
              return;
            }
          }
          applyAccountSearch(true);
        }
      });
      qEl.addEventListener("focus", function () {
        if ((qEl.value || "").charAt(0) === "/") renderSlashSuggest();
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
        sendHomeChat();
      });
    }
    if ($("btn-chat-history")) $("btn-chat-history").addEventListener("click", toggleChatHistory);
    if ($("btn-chat-bookmark")) $("btn-chat-bookmark").addEventListener("click", toggleChatBookmark);
    if ($("btn-chat-new")) $("btn-chat-new").addEventListener("click", startNewChat);
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
    if ($("btn-add-company")) {
      $("btn-add-company").addEventListener("click", function () {
        openCompanyForm(null);
      });
    }
    $("btn-save-key").addEventListener("click", function () {
      var body = {
        xai_api_key: $("xai-key") && $("xai-key").value,
        openai_api_key: $("openai-key") && $("openai-key").value,
        gemini_api_key: $("gemini-key") && $("gemini-key").value,
      };
      var ai = {
        provider: ($("ai-provider") && $("ai-provider").value) || "grok",
        model: ($("ai-model") && $("ai-model").value) || "",
      };
      api("/api/settings/keys", { method: "PUT", body: JSON.stringify(body) }).then(function () {
        return api("/api/settings", { method: "PUT", body: JSON.stringify({ ai: ai }) });
      }).then(function () {
        if ($("xai-key")) $("xai-key").value = "";
        if ($("openai-key")) $("openai-key").value = "";
        if ($("gemini-key")) $("gemini-key").value = "";
        toast("Keys saved");
        refreshStatus();
      });
    });
    if ($("btn-test-ai")) {
      $("btn-test-ai").addEventListener("click", function () {
        var provider = ($("ai-provider") && $("ai-provider").value) || "grok";
        api("/api/settings/providers/test", { method: "POST", body: JSON.stringify({ provider: provider }) }).then(function (doc) {
          toast((doc.provider || provider) + ": " + (doc.message || (doc.ok ? "ok" : "failed")));
        }).catch(function (err) {
          toast(String(err.message || err));
        });
      });
    }
    $("btn-seed").addEventListener("click", function () {
      api("/api/settings/seed", { method: "POST", body: "{}" }).then(function () {
        toast("Seed loaded");
        loadHome(true);
      });
    });
    $("btn-reset").addEventListener("click", function () {
      if (!window.confirm("Reset the store? Type was confirmed in UI.")) return;
      api("/api/settings/reset", { method: "POST", body: JSON.stringify({ confirm: "RESET" }) }).then(function () {
        toast("Store reset");
        loadHome(true);
      });
    });
    window.addEventListener("hashchange", route);
    startDeskClock();
  }

  window.CSM = {
    api: api,
    toast: toast,
    accountChip: accountChip,
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
    setWorldClock: function (clock) {
      if (!status) status = {};
      status.world_clock = clock || {};
    },
  };

  bind();
  refreshStatus().then(route);
})();
