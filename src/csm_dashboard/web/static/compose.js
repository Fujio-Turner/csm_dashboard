(function () {
  "use strict";

  function $(id) {
    return document.getElementById(id);
  }

  function openCompose(acct, seed) {
    seed = seed || {};
    var box = $("compose-box");
    if (!box || !window.CSM) return;
    box.hidden = false;
    box.classList.remove("hidden");
    while (box.firstChild) box.removeChild(box.firstChild);
    var sheet = document.createElement("div");
    sheet.className = "sheet";
    var head = document.createElement("header");
    var title = document.createElement("h2");
    title.textContent = "Compose";
    head.appendChild(title);
    head.appendChild(window.CSM.accountChip(acct));
    var close = document.createElement("button");
    close.className = "btn btn-ghost";
    close.type = "button";
    close.textContent = "Close";
    close.addEventListener("click", closeCompose);
    head.appendChild(close);
    sheet.appendChild(head);

    var threadSel = document.createElement("select");
    threadSel.id = "compose-thread";
    var ticketBox = document.createElement("div");
    ticketBox.id = "compose-tickets";
    var subject = document.createElement("input");
    subject.id = "compose-subject";
    subject.placeholder = "Subject";
    subject.style.width = "100%";
    subject.value = seed.subject || "";
    var to = document.createElement("input");
    to.id = "compose-to";
    to.placeholder = "To";
    to.style.width = "100%";
    to.value = seed.to || "";
    var body = document.createElement("textarea");
    body.id = "compose-body";
    body.value = seed.body || "";
    sheet.appendChild(labelWrap("Thread", threadSel));
    sheet.appendChild(labelWrap("Tickets", ticketBox));
    sheet.appendChild(labelWrap("To", to));
    sheet.appendChild(labelWrap("Subject", subject));
    sheet.appendChild(labelWrap("Body", body));

    var foot = document.createElement("div");
    foot.className = "sheet-foot";
    var draftBtn = document.createElement("button");
    draftBtn.className = "btn btn-primary";
    draftBtn.type = "button";
    draftBtn.textContent = "Draft with Grok";
    draftBtn.addEventListener("click", function () {
      var ticketIds = [];
      ticketBox.querySelectorAll("input[type=checkbox]:checked").forEach(function (cb) {
        ticketIds.push(cb.value);
      });
      window.CSM.api("/api/drafts/compose", {
        method: "POST",
        body: JSON.stringify({
          account_id: acct.account_id,
          thread_id: threadSel.value || null,
          ticket_ids: ticketIds,
        }),
      }).then(function (doc) {
        subject.value = doc.subject || "";
        body.value = doc.body || "";
        to.value = (doc.to_addrs || []).join(", ");
        window.CSM.toast(doc.result === "grok" ? "Drafted with Grok" : "Template draft");
      }).catch(function (err) {
        window.CSM.toast(String(err.message || err));
      });
    });
    var saveBtn = document.createElement("button");
    saveBtn.className = "btn";
    saveBtn.type = "button";
    saveBtn.textContent = "Save draft";
    saveBtn.addEventListener("click", function () {
      window.CSM.api("/api/drafts", {
        method: "POST",
        body: JSON.stringify({
          account_id: acct.account_id,
          subject: subject.value,
          body: body.value,
          to_addrs: to.value.split(",").map(function (s) { return s.trim(); }).filter(Boolean),
          created_by: "you",
        }),
      }).then(function () {
        window.CSM.toast("Draft saved");
      });
    });
    var send = document.createElement("button");
    send.className = "btn";
    send.type = "button";
    send.title = "Saves this draft, then sends after you confirm";
    send.textContent = "Send";
    send.addEventListener("click", function () {
      if (!window.confirm("Send this email now?")) return;
      send.disabled = true;
      window.CSM.api("/api/drafts", {
        method: "POST",
        body: JSON.stringify({
          account_id: acct.account_id,
          subject: subject.value,
          body: body.value,
          to_addrs: to.value.split(",").map(function (s) { return s.trim(); }).filter(Boolean),
          created_by: "you",
        }),
      }).then(function (doc) {
        return window.CSM.api("/api/drafts/" + encodeURIComponent(doc._id) + "/send", { method: "POST", body: "{}" });
      }).then(function () {
        window.CSM.toast("Sent");
        closeCompose();
      }).catch(function (err) {
        window.CSM.toast(String(err.message || err));
      }).then(function () {
        send.disabled = false;
      });
    });
    foot.appendChild(draftBtn);
    foot.appendChild(saveBtn);
    foot.appendChild(send);
    sheet.appendChild(foot);
    box.appendChild(sheet);

    var aid = encodeURIComponent(acct.account_id);
    window.CSM.api("/api/threads?account_id=" + aid).then(function (data) {
      var opt0 = document.createElement("option");
      opt0.value = "";
      opt0.textContent = "No thread";
      threadSel.appendChild(opt0);
      (data.items || []).forEach(function (th) {
        var opt = document.createElement("option");
        opt.value = th._id || "";
        opt.textContent = th.subject || th._id;
        threadSel.appendChild(opt);
      });
      if (seed.thread_id) threadSel.value = seed.thread_id;
    });
    window.CSM.api("/api/tickets?account_id=" + aid).then(function (data) {
      (data.items || []).slice(0, 12).forEach(function (t) {
        var lab = document.createElement("label");
        var cb = document.createElement("input");
        cb.type = "checkbox";
        cb.value = t._id || "";
        lab.appendChild(cb);
        lab.appendChild(document.createTextNode(" " + (t.key || "") + " " + (t.summary || "")));
        ticketBox.appendChild(lab);
        ticketBox.appendChild(document.createElement("br"));
      });
    });
  }

  function labelWrap(text, node) {
    var lab = document.createElement("label");
    lab.textContent = text;
    lab.appendChild(document.createElement("br"));
    lab.appendChild(node);
    return lab;
  }

  function closeCompose() {
    var box = $("compose-box");
    if (!box) return;
    box.hidden = true;
    box.classList.add("hidden");
    while (box.firstChild) box.removeChild(box.firstChild);
    var hash = location.hash || "";
    if (hash.indexOf("#compose/") === 0) {
      var abbr = hash.split("/")[1] || "";
      location.hash = "#account/" + abbr;
    }
  }

  window.CSMCompose = { open: openCompose, close: closeCompose };
})();
