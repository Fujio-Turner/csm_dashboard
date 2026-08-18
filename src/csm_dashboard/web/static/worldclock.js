(function () {
  "use strict";

  var zones = [];
  var homeTz = "UTC";
  var day = "";
  var hour24 = false;
  var hoverCol = -1;
  var selA = -1;
  var selB = -1;
  var tick = 0;
  var suggestOn = 0;
  var sorting = false;

  function $(id) {
    return document.getElementById(id);
  }

  function empty(node) {
    while (node && node.firstChild) node.removeChild(node.firstChild);
  }

  function csm() {
    return window.CSM || {};
  }

  function zoneLabel(tz) {
    var bits = String(tz || "").split("/");
    return (bits[bits.length - 1] || tz || "UTC").replace(/_/g, " ");
  }

  var POPULAR = [
    "UTC",
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Los_Angeles",
    "America/Phoenix",
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
    "Asia/Dubai",
    "Asia/Kolkata",
    "Asia/Singapore",
    "Asia/Hong_Kong",
    "Asia/Tokyo",
    "Asia/Seoul",
    "Australia/Sydney",
    "Pacific/Auckland",
  ];

  var ALIASES = {
    "America/Los_Angeles": [
      "la",
      "lax",
      "los angeles",
      "las angeles",
      "las angoles",
      "l.a.",
      "california",
      "pacific",
      "pt",
      "pst",
      "pdt",
      "sf",
      "san francisco",
      "seattle",
      "portland",
    ],
    "America/New_York": ["nyc", "ny", "new york", "boston", "miami", "washington", "eastern", "et", "est", "edt"],
    "America/Chicago": ["chicago", "dallas", "houston", "austin", "central", "ct", "cst", "cdt"],
    "America/Denver": ["denver", "mountain", "mt", "mst", "mdt", "salt lake", "boulder"],
    "America/Phoenix": ["phoenix", "arizona"],
    "Europe/London": ["london", "uk", "britain", "bst", "gmt"],
    "Europe/Paris": ["paris", "france", "cet", "cest"],
    "Asia/Tokyo": ["tokyo", "japan", "jst"],
    "Asia/Kolkata": ["india", "mumbai", "delhi", "bangalore", "ist"],
    "Australia/Sydney": ["sydney", "melbourne", "aest"],
  };

  function normText(s) {
    return String(s || "")
      .toLowerCase()
      .replace(/[_/,.-]+/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  function editDist(a, b) {
    a = String(a || "");
    b = String(b || "");
    if (Math.abs(a.length - b.length) > 4) return 99;
    var prev = [];
    var i;
    var j;
    for (j = 0; j <= b.length; j++) prev[j] = j;
    for (i = 1; i <= a.length; i++) {
      var cur = [i];
      for (j = 1; j <= b.length; j++) {
        var cost = a.charAt(i - 1) === b.charAt(j - 1) ? 0 : 1;
        cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost);
      }
      prev = cur;
    }
    return prev[b.length];
  }

  function popularBonus(tz) {
    var idx = POPULAR.indexOf(tz);
    return idx < 0 ? 0 : 40 - idx;
  }

  function scoreZone(tz, q) {
    var nq = normText(q);
    var city = normText(zoneLabel(tz));
    var full = normText(tz);
    var aliases = ALIASES[tz] || [];
    var bonus = popularBonus(tz);
    if (!nq) return 50 + bonus;
    if (city === nq || full === nq) return 200 + bonus;
    if (aliases.indexOf(nq) >= 0) return 195 + bonus;
    if (city.indexOf(nq) === 0) return 175 + bonus;
    if (full.indexOf(nq) === 0) return 90 + bonus;
    if (city.indexOf(nq) >= 0) return 150 + bonus;
    var a;
    for (a = 0; a < aliases.length; a++) {
      if (aliases[a].indexOf(nq) >= 0 || nq.indexOf(aliases[a]) >= 0) return 160 + bonus;
    }
    if (full.indexOf(nq) >= 0) return 70 + bonus;
    var dCity = editDist(nq, city);
    if (nq.length >= 4 && dCity <= 2) return 170 - dCity * 8 + bonus;
    var qt = nq.split(" ");
    var ct = city.split(" ");
    if (qt.length > 1 && qt.length === ct.length) {
      var close = true;
      var t;
      for (t = 0; t < qt.length; t++) {
        if (editDist(qt[t], ct[t]) > 2) close = false;
      }
      if (close) return 168 + bonus;
    }
    return 0;
  }

  function deviceTz() {
    try {
      return (Intl.DateTimeFormat().resolvedOptions().timeZone || "").trim();
    } catch (e) {
      return "";
    }
  }

  function localParts(date, tz) {
    var out = {
      year: 0,
      month: 0,
      day: 0,
      hour: 0,
      minute: 0,
      weekday: "",
      monthName: "",
      tzName: "",
    };
    try {
      var parts = new Intl.DateTimeFormat("en-US", {
        timeZone: tz,
        weekday: "short",
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        hourCycle: "h23",
        timeZoneName: "short",
      }).formatToParts(date);
      parts.forEach(function (p) {
        if (p.type === "year") out.year = +p.value;
        if (p.type === "month") out.month = +p.value;
        if (p.type === "day") out.day = +p.value;
        if (p.type === "hour") out.hour = +p.value;
        if (p.type === "minute") out.minute = +p.value;
        if (p.type === "weekday") out.weekday = p.value;
        if (p.type === "timeZoneName") out.tzName = p.value;
      });
      out.monthName = new Intl.DateTimeFormat("en-US", { timeZone: tz, month: "short" }).format(date);
    } catch (e) {}
    return out;
  }

  function instantAtLocal(ymd, hour, tz) {
    var p = String(ymd).split("-");
    var y = +p[0];
    var mo = +p[1];
    var d = +p[2];
    var utc = Date.UTC(y, mo - 1, d, hour, 0, 0);
    var i;
    for (i = 0; i < 4; i++) {
      var loc = localParts(new Date(utc), tz);
      var desired = Date.UTC(y, mo - 1, d, hour, 0, 0);
      var actual = Date.UTC(loc.year, loc.month - 1, loc.day, loc.hour, loc.minute, 0);
      utc += desired - actual;
    }
    return new Date(utc);
  }

  function offsetMinutes(date, tz) {
    var loc = localParts(date, tz);
    var asUtc = Date.UTC(loc.year, loc.month - 1, loc.day, loc.hour, loc.minute, 0);
    return Math.round((asUtc - date.getTime()) / 60000);
  }

  function formatOffset(mins) {
    var sign = mins >= 0 ? "+" : "−";
    var abs = Math.abs(mins);
    var h = Math.floor(abs / 60);
    var m = abs % 60;
    if (m) return sign + h + ":" + (m < 10 ? "0" : "") + m;
    return sign + h;
  }

  function hourNum(hour) {
    if (hour24) return (hour < 10 ? "0" : "") + hour;
    var h = hour % 12;
    if (!h) h = 12;
    return String(h);
  }

  function hourPeriod(hour) {
    return hour < 12 ? "am" : "pm";
  }

  function bandClass(hour) {
    if (hour <= 5 || hour >= 22) return "is-night";
    if (hour <= 7 || hour >= 19) return "is-dusk";
    return "is-day";
  }

  function formatClock(loc) {
    var h = loc.hour;
    var min = (loc.minute < 10 ? "0" : "") + loc.minute;
    if (hour24) return (h < 10 ? "0" : "") + h + ":" + min;
    var ap = hourPeriod(h);
    var n = h % 12;
    if (!n) n = 12;
    return n + ":" + min + ap;
  }

  function formatRangeEnd(date, tz) {
    return formatClock(localParts(date, tz));
  }

  function columns() {
    var list = [];
    var i;
    for (i = 0; i < 24; i++) list.push(instantAtLocal(day, i, homeTz));
    return list;
  }

  function loadZones() {
    var op = (csm().getOperator && csm().getOperator()) || {};
    var clock = (csm().getWorldClock && csm().getWorldClock()) || {};
    var savedTz = op.timezone || (csm().getOperatorTz && csm().getOperatorTz()) || "";
    var dev = deviceTz();
    if (savedTz && savedTz !== "UTC") homeTz = savedTz;
    else homeTz = dev || savedTz || "UTC";
    var saved = clock.timezones || op.timezones;
    if (saved && saved.length) zones = saved.slice();
    else zones = [homeTz];
    hour24 = !!clock.hour24;
  }

  function readZoneOrder(body) {
    return Array.prototype.map
      .call((body && body.querySelectorAll(".wtb-row")) || [], function (r) {
        return r.getAttribute("data-tz");
      })
      .filter(Boolean);
  }

  function sameOrder(a, b) {
    if (!a || !b || a.length !== b.length) return false;
    var i;
    for (i = 0; i < a.length; i++) {
      if (a[i] !== b[i]) return false;
    }
    return true;
  }

  function applyOrder(next) {
    if (!next || !next.length || sameOrder(zones, next)) return;
    zones = next.slice();
    persistZones();
  }

  function nudgeZone(tz, dir) {
    var i = zones.indexOf(tz);
    var j = i + dir;
    if (i < 0 || j < 0 || j >= zones.length) return;
    var item = zones.splice(i, 1)[0];
    zones.splice(j, 0, item);
    persistZones();
    renderWorld();
    document.querySelectorAll(".wtb-row").forEach(function (r) {
      if (r.getAttribute("data-tz") === tz) {
        var g = r.querySelector(".wtb-grip");
        if (g) g.focus();
      }
    });
  }

  function bindRowSort(row, tz, body) {
    var grip = row.querySelector(".wtb-grip");
    if (!grip || !body) return;
    grip.addEventListener("keydown", function (ev) {
      if (ev.key === "ArrowUp") {
        ev.preventDefault();
        nudgeZone(tz, -1);
      } else if (ev.key === "ArrowDown") {
        ev.preventDefault();
        nudgeZone(tz, 1);
      }
    });
    grip.addEventListener("pointerdown", function (ev) {
      if (ev.button !== 0) return;
      ev.preventDefault();
      sorting = true;
      body.classList.add("is-sorting");
      row.classList.add("is-dragging");
      try {
        grip.setPointerCapture(ev.pointerId);
      } catch (e) {}
      function onMove(mv) {
        var el = document.elementFromPoint(mv.clientX, mv.clientY);
        while (el && !el.closest) el = el.parentNode;
        var over = el && el.closest ? el.closest(".wtb-row") : null;
        if (!over || over === row || over.parentNode !== body) return;
        var box = over.getBoundingClientRect();
        if (mv.clientY > box.top + box.height / 2) {
          if (over.nextSibling !== row) body.insertBefore(row, over.nextSibling);
        } else if (over !== row) {
          body.insertBefore(row, over);
        }
      }
      function onUp() {
        window.removeEventListener("pointermove", onMove, true);
        window.removeEventListener("pointerup", onUp, true);
        window.removeEventListener("pointercancel", onUp, true);
        row.classList.remove("is-dragging");
        body.classList.remove("is-sorting");
        sorting = false;
        applyOrder(readZoneOrder(body));
      }
      window.addEventListener("pointermove", onMove, true);
      window.addEventListener("pointerup", onUp, true);
      window.addEventListener("pointercancel", onUp, true);
    });
  }

  function persistZones() {
    if (!csm().api) return Promise.resolve();
    return csm()
      .api("/api/settings", {
        method: "PUT",
        body: JSON.stringify({
          world_clock: { timezones: zones.slice(), hour24: hour24 },
          operator: { timezones: zones.slice() },
        }),
      })
      .then(function () {
        if (csm().refreshStatus) return csm().refreshStatus();
      })
      .catch(function (err) {
        if (csm().toast) csm().toast("Could not save timezones");
        throw err;
      });
  }

  function filterZones(q) {
    var all = (csm().timezoneOptions && csm().timezoneOptions()) || POPULAR.slice();
    var i;
    if (!normText(q)) return POPULAR.slice();
    var ranked = [];
    for (i = 0; i < all.length; i++) {
      var z = all[i];
      var score = scoreZone(z, q);
      if (score > 0) ranked.push({ tz: z, score: score });
    }
    Object.keys(ALIASES).forEach(function (tz) {
      if (all.indexOf(tz) < 0 && scoreZone(tz, q) > 0) ranked.push({ tz: tz, score: scoreZone(tz, q) });
    });
    ranked.sort(function (a, b) {
      if (b.score !== a.score) return b.score - a.score;
      return zoneLabel(a.tz).localeCompare(zoneLabel(b.tz));
    });
    var out = [];
    var seen = {};
    for (i = 0; i < ranked.length && out.length < 12; i++) {
      if (seen[ranked[i].tz]) continue;
      seen[ranked[i].tz] = true;
      out.push(ranked[i].tz);
    }
    return out;
  }

  function closeSuggest() {
    var box = $("wtb-suggest");
    if (box) {
      box.hidden = true;
      box.classList.add("hidden");
      empty(box);
    }
  }

  function showSuggest(q) {
    var box = $("wtb-suggest");
    if (!box) return;
    empty(box);
    var hits = filterZones(q);
    if (!hits.length) {
      closeSuggest();
      return;
    }
    hits.forEach(function (z, idx) {
      var b = document.createElement("button");
      b.type = "button";
      b.setAttribute("data-tz", z);
      if (idx === suggestOn) b.className = "is-on";
      var name = document.createElement("strong");
      name.textContent = zoneLabel(z);
      var path = document.createElement("small");
      path.textContent = z.replace(/_/g, " ");
      b.appendChild(name);
      b.appendChild(path);
      b.addEventListener("mousedown", function (ev) {
        ev.preventDefault();
        addZone(z);
      });
      box.appendChild(b);
    });
    box.hidden = false;
    box.classList.remove("hidden");
  }

  function addZone(tz) {
    if (!tz) return;
    if (zones.indexOf(tz) >= 0) {
      if (csm().toast) csm().toast("Already added");
      closeSuggest();
      return;
    }
    zones.push(tz);
    closeSuggest();
    var inp = $("wtb-add");
    if (inp) inp.value = "";
    persistZones();
    renderWorld();
    if (csm().toast) csm().toast("Timezone added");
  }

  function removeZone(tz) {
    zones = zones.filter(function (z) {
      return z !== tz;
    });
    if (!zones.length) zones = [homeTz];
    persistZones();
    renderWorld();
  }

  function selRange() {
    if (selA < 0) return null;
    var a = Math.min(selA, selB < 0 ? selA : selB);
    var b = Math.max(selA, selB < 0 ? selA : selB);
    return { a: a, b: b };
  }

  function paintHoverSel() {
    var range = selRange();
    document.querySelectorAll("#world-box .wtb-hour").forEach(function (el) {
      var col = Number(el.getAttribute("data-col"));
      el.classList.toggle("is-hover", hoverCol >= 0 && col === hoverCol);
      el.classList.toggle("is-sel", !!(range && col >= range.a && col <= range.b));
    });
    var line = $("wtb-sel");
    if (!line) return;
    if (!range) {
      line.hidden = true;
      line.classList.add("hidden");
      empty(line);
      return;
    }
    empty(line);
    var cols = columns();
    var start = cols[range.a];
    var end = new Date(cols[range.b].getTime() + 60 * 60 * 1000);
    var bits = zones.map(function (tz) {
      return zoneLabel(tz) + " " + formatRangeEnd(start, tz) + "–" + formatRangeEnd(end, tz);
    });
    line.textContent = bits.join("  ·  ");
    line.hidden = false;
    line.classList.remove("hidden");
  }

  function onHourClick(col) {
    if (selA < 0) {
      selA = col;
      selB = col;
    } else if (selA === selB && selA === col) {
      selA = -1;
      selB = -1;
    } else if (selA === selB) {
      selB = col;
    } else {
      selA = col;
      selB = col;
    }
    paintHoverSel();
  }

  function renderRow(root, tz, cols, now) {
    var isYou = tz === homeTz;
    var row = document.createElement("div");
    row.className = "wtb-row" + (isYou ? " is-you" : "");
    row.setAttribute("data-tz", tz);
    var meta = document.createElement("div");
    meta.className = "wtb-meta";
    var top = document.createElement("div");
    top.className = "wtb-meta-top";
    var grip = document.createElement("span");
    grip.className = "wtb-grip";
    grip.setAttribute("role", "button");
    grip.setAttribute("tabindex", "0");
    grip.setAttribute("aria-label", "Drag to reorder " + zoneLabel(tz));
    grip.title = "Drag to reorder";
    var gripSvg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    gripSvg.setAttribute("viewBox", "0 0 16 16");
    gripSvg.setAttribute("aria-hidden", "true");
    [
      [5, 4],
      [11, 4],
      [5, 8],
      [11, 8],
      [5, 12],
      [11, 12],
    ].forEach(function (pt) {
      var c = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      c.setAttribute("cx", String(pt[0]));
      c.setAttribute("cy", String(pt[1]));
      c.setAttribute("r", "1.35");
      gripSvg.appendChild(c);
    });
    grip.appendChild(gripSvg);
    var rm = document.createElement("button");
    rm.type = "button";
    rm.className = "wtb-remove";
    rm.setAttribute("aria-label", "Remove " + zoneLabel(tz));
    rm.textContent = "×";
    rm.addEventListener("click", function () {
      removeZone(tz);
    });
    var off = document.createElement("span");
    off.className = "wtb-off";
    var delta = offsetMinutes(now, tz) - offsetMinutes(now, homeTz);
    off.textContent = formatOffset(delta);
    var city = document.createElement("span");
    city.className = "wtb-city";
    city.textContent = zoneLabel(tz);
    var abbr = document.createElement("span");
    abbr.className = "wtb-abbr";
    var locNow = localParts(now, tz);
    abbr.textContent = locNow.tzName || "";
    top.appendChild(grip);
    top.appendChild(rm);
    top.appendChild(off);
    top.appendChild(city);
    if (isYou) {
      var you = document.createElement("span");
      you.className = "wtb-you";
      you.textContent = "You";
      top.appendChild(you);
    }
    top.appendChild(abbr);
    var clock = document.createElement("div");
    clock.className = "wtb-now";
    var clockMain = document.createElement("span");
    clockMain.textContent = formatClock(locNow);
    var clockDay = document.createElement("small");
    clockDay.textContent = locNow.weekday + ", " + locNow.monthName + " " + locNow.day;
    clock.appendChild(clockMain);
    clock.appendChild(clockDay);
    meta.appendChild(top);
    meta.appendChild(clock);

    var wrap = document.createElement("div");
    wrap.className = "wtb-hours-wrap";
    var hours = document.createElement("div");
    hours.className = "wtb-hours";
    cols.forEach(function (inst, col) {
      var loc = localParts(inst, tz);
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "wtb-hour " + bandClass(loc.hour);
      btn.setAttribute("data-col", String(col));
      var next = new Date(inst.getTime() + 60 * 60 * 1000);
      if (now >= inst && now < next) btn.classList.add("is-now");
      if (loc.weekday === "Sat" || loc.weekday === "Sun") btn.classList.add("is-weekend");
      var num = document.createElement("b");
      var sub = document.createElement("span");
      if (now >= inst && now < next) {
        num.textContent = formatClock(loc);
        sub.textContent = "now";
      } else if (loc.hour === 0 && loc.minute === 0) {
        btn.classList.add("is-date");
        num.textContent = loc.weekday;
        sub.textContent = loc.monthName + " " + loc.day;
      } else {
        num.textContent = hourNum(loc.hour);
        sub.textContent = hour24 ? loc.tzName : hourPeriod(loc.hour);
      }
      btn.appendChild(num);
      btn.appendChild(sub);
      btn.title = zoneLabel(tz) + " " + formatClock(loc) + " " + loc.tzName;
      btn.addEventListener("mouseenter", function () {
        hoverCol = col;
        paintHoverSel();
      });
      btn.addEventListener("click", function () {
        onHourClick(col);
      });
      hours.appendChild(btn);
    });
    wrap.appendChild(hours);
    row.appendChild(meta);
    row.appendChild(wrap);
    root.appendChild(row);
    bindRowSort(row, tz, root);
  }

  function renderWorld() {
    var box = $("world-box");
    if (!box) return;
    empty(box);
    if (!day) day = (csm().todayYmd && csm().todayYmd()) || "";
    var now = new Date();
    var cols = columns();
    var sheet = document.createElement("div");
    sheet.className = "sheet sheet-world";
    var head = document.createElement("header");
    var title = document.createElement("h2");
    title.textContent = "World clock";
    var close = document.createElement("button");
    close.className = "btn btn-ghost sheet-close";
    close.type = "button";
    close.textContent = "Close";
    close.addEventListener("click", closeWorld);
    head.appendChild(title);
    head.appendChild(close);

    var bar = document.createElement("div");
    bar.className = "wtb-toolbar";
    var prev = document.createElement("button");
    prev.type = "button";
    prev.className = "btn";
    prev.textContent = "◀";
    prev.setAttribute("aria-label", "Previous day");
    prev.addEventListener("click", function () {
      day = csm().shiftYmd ? csm().shiftYmd(day, -1) : day;
      renderWorld();
    });
    var label = document.createElement("span");
    label.className = "wtb-date";
    label.textContent = csm().formatDayLabel ? csm().formatDayLabel(day) : day;
    var next = document.createElement("button");
    next.type = "button";
    next.className = "btn";
    next.textContent = "▶";
    next.setAttribute("aria-label", "Next day");
    next.addEventListener("click", function () {
      day = csm().shiftYmd ? csm().shiftYmd(day, 1) : day;
      renderWorld();
    });
    var fmt = document.createElement("button");
    fmt.type = "button";
    fmt.className = "btn";
    fmt.textContent = hour24 ? "12h" : "24h";
    fmt.addEventListener("click", function () {
      hour24 = !hour24;
      persistZones();
      renderWorld();
    });
    var addWrap = document.createElement("div");
    addWrap.className = "wtb-add";
    var add = document.createElement("input");
    add.id = "wtb-add";
    add.type = "search";
    add.placeholder = "Search city — Los Angeles, London, Tokyo";
    add.setAttribute("autocomplete", "off");
    add.addEventListener("input", function () {
      suggestOn = 0;
      showSuggest(add.value);
    });
    add.addEventListener("focus", function () {
      showSuggest(add.value);
    });
    add.addEventListener("keydown", function (ev) {
      var boxSug = $("wtb-suggest");
      var buttons = boxSug ? boxSug.querySelectorAll("button") : [];
      if (ev.key === "ArrowDown" && buttons.length) {
        ev.preventDefault();
        suggestOn = Math.min(suggestOn + 1, buttons.length - 1);
        showSuggest(add.value);
      } else if (ev.key === "ArrowUp" && buttons.length) {
        ev.preventDefault();
        suggestOn = Math.max(suggestOn - 1, 0);
        showSuggest(add.value);
      } else if (ev.key === "Enter") {
        ev.preventDefault();
        var pick = buttons[suggestOn];
        if (pick) addZone(pick.getAttribute("data-tz"));
        else if (add.value) {
          var hits = filterZones(add.value);
          if (hits.length) addZone(hits[0]);
        }
      } else if (ev.key === "Escape") {
        closeSuggest();
      }
    });
    add.addEventListener("blur", function () {
      setTimeout(closeSuggest, 120);
    });
    var sug = document.createElement("div");
    sug.id = "wtb-suggest";
    sug.className = "wtb-suggest hidden";
    sug.hidden = true;
    addWrap.appendChild(add);
    addWrap.appendChild(sug);
    bar.appendChild(prev);
    bar.appendChild(label);
    bar.appendChild(next);
    bar.appendChild(fmt);
    bar.appendChild(addWrap);

    var body = document.createElement("div");
    body.className = "wtb-body";
    body.addEventListener("mouseleave", function () {
      hoverCol = -1;
      paintHoverSel();
    });
    if (!zones.length) {
      var emptyP = document.createElement("p");
      emptyP.className = "wtb-empty";
      emptyP.textContent = "Add a timezone to compare hours.";
      body.appendChild(emptyP);
    } else {
      zones.forEach(function (tz) {
        renderRow(body, tz, cols, now);
      });
    }
    var sel = document.createElement("div");
    sel.id = "wtb-sel";
    sel.className = "wtb-sel hidden";
    sel.hidden = true;

    sheet.appendChild(head);
    sheet.appendChild(bar);
    sheet.appendChild(body);
    sheet.appendChild(sel);
    box.appendChild(sheet);
    paintHoverSel();
  }

  function openWorld() {
    var box = $("world-box");
    if (!box) return;
    var ready = csm().refreshStatus ? csm().refreshStatus() : Promise.resolve();
    Promise.resolve(ready).then(function () {
      loadZones();
      day = (csm().todayYmd && csm().todayYmd()) || day;
      selA = -1;
      selB = -1;
      hoverCol = -1;
      box.hidden = false;
      box.classList.remove("hidden");
      renderWorld();
      if (tick) clearInterval(tick);
      tick = setInterval(function () {
        if (box.hidden) return;
        var add = $("wtb-add");
        if (add && document.activeElement === add) return;
        if (sorting) return;
        renderWorld();
      }, 30000);
    });
  }

  function closeWorld() {
    var box = $("world-box");
    if (!box) return;
    box.hidden = true;
    box.classList.add("hidden");
    empty(box);
    if (tick) {
      clearInterval(tick);
      tick = 0;
    }
  }

  function isOpen() {
    var box = $("world-box");
    return !!(box && !box.hidden);
  }

  window.CSMWorld = { open: openWorld, close: closeWorld, isOpen: isOpen };
})();
