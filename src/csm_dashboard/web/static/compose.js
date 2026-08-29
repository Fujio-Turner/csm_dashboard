(function () {
  "use strict";

  function $(id) {
    return document.getElementById(id);
  }

  function csvList(text) {
    return String(text || "").split(/[\n,]/).map(function (s) { return s.trim(); }).filter(Boolean);
  }

  function openCompose(acct, seed) {
    seed = seed || {};
    var box = $("compose-box");
    if (!box || !window.CSM || !window.CSM.mountMailComposer) return;
    box.hidden = false;
    box.classList.remove("hidden");
    while (box.firstChild) box.removeChild(box.firstChild);
    var sheet = document.createElement("div");
    sheet.className = "sheet sheet-mail";
    var head = document.createElement("header");
    var title = document.createElement("h2");
    title.textContent = "Compose";
    head.appendChild(title);
    head.appendChild(window.CSM.accountChip(acct));
    var close = document.createElement("button");
    close.className = "btn btn-ghost sheet-close";
    close.type = "button";
    close.setAttribute("aria-label", "Close");
    close.textContent = "×";
    close.addEventListener("click", closeCompose);
    head.appendChild(close);
    sheet.appendChild(head);

    var threadPick = window.CSM.mountSearchSelect({
      placeholder: "No thread",
      emptyLabel: "No thread",
      searchPlaceholder: "Search threads",
      ariaLabel: "Thread",
      items: [{ value: "", label: "No thread" }],
      value: seed.thread_id || "",
      btnClass: "search-select-btn-block",
    });
    threadPick.el.id = "compose-thread";
    var ticketPick = window.CSM.mountTagifyMulti({
      placeholder: "Search tickets",
      ariaLabel: "Tickets",
      enforceWhitelist: true,
      items: [],
      value: [],
    });
    ticketPick.el.id = "compose-tickets";
    function ctxLabel(text, node) {
      var lab = document.createElement("label");
      lab.className = "mail-ctx";
      var span = document.createElement("span");
      span.textContent = text;
      lab.appendChild(span);
      lab.appendChild(node);
      return lab;
    }
    sheet.appendChild(ctxLabel("Thread", threadPick.el));
    sheet.appendChild(ctxLabel("Tickets", ticketPick.el));

    var draftId = seed.draft_id || "";
    var mail = window.CSM.mountMailComposer(sheet, {
      accountId: acct.account_id,
      to: Array.isArray(seed.to) ? seed.to : csvList(seed.to),
      cc: Array.isArray(seed.cc) ? seed.cc : csvList(seed.cc),
      bcc: Array.isArray(seed.bcc) ? seed.bcc : csvList(seed.bcc),
      subject: seed.subject || "",
      body: seed.body || "",
      onSuggest: function (snap) {
        return window.CSM.api("/api/drafts/compose", {
          method: "POST",
          body: JSON.stringify({
            account_id: acct.account_id,
            thread_id: threadPick.get() || null,
            ticket_ids: ticketPick.get() || [],
          }),
        }).then(function (doc) {
          draftId = doc._id || draftId;
          mail.set({
            to_addrs: doc.to_addrs || [],
            cc_addrs: doc.cc_addrs || [],
            bcc_addrs: doc.bcc_addrs || [],
            subject: doc.subject || snap.subject,
            body: doc.body || "",
          });
          window.CSM.toast(doc.result === "grok" ? "Drafted with Grok" : "Template draft");
        });
      },
      onSave: function (snap) {
        var payload = {
          account_id: acct.account_id,
          subject: snap.subject,
          body: snap.body,
          to_addrs: snap.to_addrs,
          cc_addrs: snap.cc_addrs,
          bcc_addrs: snap.bcc_addrs,
          attachment_names: snap.attachment_names,
          created_by: "you",
          context_ref: { thread_id: threadPick.get() || "" },
        };
        var req = draftId
          ? window.CSM.api("/api/drafts/" + encodeURIComponent(draftId), { method: "PATCH", body: JSON.stringify(payload) })
          : window.CSM.api("/api/drafts", { method: "POST", body: JSON.stringify(payload) });
        return req.then(function (doc) {
          if (doc && doc._id) draftId = doc._id;
          window.CSM.toast("Draft saved");
        });
      },
      onSend: function (snap, attachments) {
        var payload = {
          account_id: acct.account_id,
          subject: snap.subject,
          body: snap.body,
          to_addrs: snap.to_addrs,
          cc_addrs: snap.cc_addrs,
          bcc_addrs: snap.bcc_addrs,
          attachment_names: snap.attachment_names,
          created_by: "you",
          context_ref: { thread_id: threadPick.get() || "" },
        };
        var req = draftId
          ? window.CSM.api("/api/drafts/" + encodeURIComponent(draftId), { method: "PATCH", body: JSON.stringify(payload) })
          : window.CSM.api("/api/drafts", { method: "POST", body: JSON.stringify(payload) });
        return req.then(function (doc) {
          draftId = (doc && doc._id) || draftId;
          return window.CSM.api("/api/drafts/" + encodeURIComponent(draftId) + "/send", {
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
          window.CSM.toast("Sent");
          closeCompose();
        });
      },
    });
    box._mail = mail;
    box._threadPick = threadPick;
    box._ticketPick = ticketPick;
    box.appendChild(sheet);
    ticketPick.bind();

    var aid = encodeURIComponent(acct.account_id);
    window.CSM.api("/api/threads?account_id=" + aid).then(function (data) {
      var items = [{ value: "", label: "No thread" }];
      (data.items || []).forEach(function (th) {
        items.push({ value: th._id || "", label: th.subject || th._id, search: (th.subject || "") + " " + (th._id || "") });
      });
      threadPick.setItems(items);
      if (seed.thread_id) threadPick.set(seed.thread_id);
    });
    window.CSM.api("/api/tickets?account_id=" + aid).then(function (data) {
      ticketPick.setItems((data.items || []).map(function (t) {
        var label = ((t.key || "") + " " + (t.summary || "")).trim();
        return { value: t._id || "", label: label, search: label + " " + (t.status || "") + " " + (t.priority || "") };
      }));
    });
  }

  function closeCompose() {
    var box = $("compose-box");
    if (!box) return;
    if (box._mail && box._mail.destroy) box._mail.destroy();
    box._mail = null;
    if (box._threadPick && box._threadPick.destroy) box._threadPick.destroy();
    box._threadPick = null;
    if (box._ticketPick && box._ticketPick.destroy) box._ticketPick.destroy();
    box._ticketPick = null;
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
