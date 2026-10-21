// Publish, Schedule, Unpublish: checks first, optional suggestions to accept or reject, then the steps with a live log.
import { api, stream, store, h, clear, modal, icon, toast, today, niceDate, fill } from "../lib.js";

export async function open(ed) {
  if (!(await ed.save(true, false, true))) { toast("Save the page first (see the message at the top).", "error"); return; }
  const isLive = ed.state === "published";
  const isScheduled = ed.state === "scheduled";
  let mode = "publish";
  let prep = null, accepted = [], acceptWarnings = false, dryRun = false;
  const scheduleDate = h("input.input", { type: "date", min: tomorrow(), value: isScheduled && ed.meta.date ? ed.meta.date : tomorrow(), "aria-label": "Day it goes live" });

  const tabs = h("div.seg.publish-modes", { role: "tablist" });
  const modes = [["publish", isLive ? "Publish changes" : "Publish now"], ["schedule", isScheduled ? "Reschedule" : "Schedule"]];
  if (isLive || isScheduled) modes.push(["unpublish", "Unpublish"]);
  for (const [k, label] of modes) tabs.append(h("button.seg-btn", { role: "tab", "aria-pressed": String(k === mode), onclick: () => setMode(k) }, label));

  const body = h("div.publish");
  let goAction = () => run();
  const goBtn = h("button.btn.primary", { onclick: () => goAction() }, "Publish");
  const cancelBtn = h("button.btn.ghost", { onclick: () => m.close() }, "Cancel");
  const m = modal({ title: "Publish", subtitle: ed.meta.title || "Untitled", body: h("div", tabs, body), footer: [h("span.grow"), cancelBtn, goBtn], className: "publish-modal" });

  function setMode(k) {
    mode = k;
    for (const b of tabs.children) b.setAttribute("aria-pressed", String(b.textContent === modes.find((x) => x[0] === k)[1]));
    prepare();
  }

  async function prepare() {
    goAction = () => run();
    tabs.hidden = false;
    cancelBtn.textContent = "Cancel";
    fill(body, h("div.loading", h("span.spinner"), "Checking the page…"));
    goBtn.disabled = true;
    try {
      prep = await api("/api/publish/prepare", { id: ed.id, mode, date: mode === "schedule" ? scheduleDate.value : null });
    } catch (e) { fill(body, h("div.msg-err", e.message)); return; }
    paint();
  }

  function paint() {
    clear(body);
    const blocks = [];
    if (mode === "schedule") {
      blocks.push(h("div.field", h("span.label", "Goes live on"), scheduleDate,
        h("span.hint", "The page appears on the first build that day. The README explains a daily build on your host.")));
    }
    if (prep.checks_note) blocks.push(h("p.note", icon("info", 16), prep.checks_note));
    if (prep.errors.length) {
      blocks.push(h("div.check-block.err",
        h("h4", icon("alert", 16), prep.errors.length === 1 ? "1 error to fix first" : `${prep.errors.length} errors to fix first`),
        h("ul", prep.errors.map((i) => h("li", issueLine(i)))),
        h("button.btn.small", { onclick: () => { m.close(); ed.openDrawer("checks"); } }, "Show them in the editor")));
    }
    if (prep.warnings.length) {
      const box = h("input", { type: "checkbox", checked: acceptWarnings, onchange: () => { acceptWarnings = box.checked; paintButton(); } });
      blocks.push(h("div.check-block.warn",
        h("h4", icon("alert", 16), prep.warnings.length === 1 ? "1 warning" : `${prep.warnings.length} warnings`),
        h("ul", prep.warnings.map((i) => h("li", issueLine(i)))),
        h("label.check", box, "Publish anyway")));
    }
    if (!prep.errors.length && !prep.warnings.length && !prep.checks_note && mode !== "unpublish") {
      blocks.push(h("p.all-good", icon("check", 16), "The page passes every check."));
    }
    if (prep.plan_error) blocks.push(h("div.msg-err", prep.plan_error));

    // suggestions
    if (store.state.llm && mode !== "unpublish") {
      const sbox = h("div.suggest");
      const askBtn = h("button.btn.small", { onclick: async () => {
          askBtn.disabled = true; askBtn.textContent = "Asking…";
          try {
            const res = await api("/api/llm/ingest", { id: ed.id, meta: ed.meta, body: ed.view.state.doc.toString() });
            renderSuggestions(sbox, res.proposals);
          } catch (e) { fill(sbox, h("p.msg-err", e.message)); }
        } }, icon("wand", 14), "Ask for links and topics");
      sbox.append(h("div.row", h("div", h("h4", "Suggestions"), h("p.hint", "Optional. Nothing changes unless you accept it.")), h("span.grow"), askBtn));
      blocks.push(sbox);
    }

    // what will happen
    const steps = prep.steps.map((s) => {
      let note = "";
      if (s.key === "commit") note = prep.commit ? "only this page's files" : "off in site.yml";
      if (s.key === "push") note = prep.push && prep.commit ? "" : "off in site.yml";
      if (s.key === "command") note = prep.command ? prep.command : "none set";
      if (s.key === "figures") note = prep.figures.length ? prep.figures.join(", ") : "none on this page";
      return h("li", h("span", s.label), note ? h("span.muted.small", note) : null);
    });
    blocks.push(h("details.plan", h("summary", "What happens"), h("ol", steps),
      h("p.small.muted", mode === "unpublish" ? `The page goes back to a draft and leaves ${prep.url.replace(/\/[^/]+\/$/, "/")} on the next deploy.`
        : `It will be at ${prep.url}`)));
    const dry = h("input", { type: "checkbox", checked: dryRun, onchange: () => { dryRun = dry.checked; paintButton(); } });
    blocks.push(h("label.check.dry", dry, h("span", h("strong", "Dry run"), " — go through every step on a copy of the site, and change nothing.")));
    body.append(...blocks);
    paintButton();
  }

  function paintButton() {
    const label = { publish: isLive ? "Publish changes" : "Publish", schedule: "Schedule", unpublish: "Unpublish" }[mode];
    goBtn.textContent = dryRun ? `${label} (dry run)` : label;
    goBtn.disabled = !prep || prep.errors.length > 0 || !!prep.plan_error || (prep.warnings.length > 0 && !acceptWarnings);
    goBtn.classList.toggle("danger", mode === "unpublish" && !dryRun);
  }
  scheduleDate.addEventListener("change", () => prepare());

  function issueLine(i) {
    const line = ed.editorLine(i.line);
    return [line ? h("span.mono.small", `line ${line} `) : null, i.message, i.hint ? h("span.muted", ` — ${i.hint}`) : null];
  }

  // --- suggestions as cards --------------------------------------------------------------------------------------------
  function renderSuggestions(box, p) {
    fill(box, h("h4", "Suggestions"));
    const cards = [];
    const titleOf = (id) => ((store.state.pages || []).find((x) => x.id === id) || {}).title || id;
    const cur = ed.meta;
    if (p.topics && p.topics.length && JSON.stringify(p.topics) !== JSON.stringify(cur.topics || [])) {
      cards.push(card("Topics", h("p", (cur.topics || []).join(", ") || "none", " → ", h("strong", p.topics.join(", "))),
        () => { ed.setMeta({ topics: p.topics }); return `topics: ${p.topics.join(", ")}`; }));
    }
    for (const b of p.builds_on || []) {
      if ((cur.builds_on || []).includes(b)) continue;
      cards.push(card("Builds on", h("p", "Read first: ", h("strong", titleOf(b))),
        () => { ed.setMeta({ builds_on: [...(ed.meta.builds_on || []), b] }); return `builds_on: ${b}`; }));
    }
    for (const ln of p.links || []) {
      cards.push(card(`Link to “${titleOf(ln.target)}”`, h("p.quote", ...highlight(ln.sentence, ln.anchor_text)),
        () => applyLink(ln) ? `link: ${ln.target}` : null));
    }
    if (p.summary && p.summary !== cur.summary) cards.push(card("Summary", h("p", p.summary), () => { ed.setMeta({ summary: p.summary }); return "summary"; }));
    if (p.description && p.description !== cur.description) cards.push(card("Description", h("p", p.description), () => { ed.setMeta({ description: p.description }); return "description"; }));
    if (p.series && (!cur.series || cur.series.name !== p.series.name)) cards.push(card("Series", h("p", `${p.series.name}, part ${p.series.part}`), () => { ed.setMeta({ series: p.series }); return `series: ${p.series.name}`; }));
    if (!cards.length) box.append(h("p.muted.small", "Nothing to suggest: the page is already well connected."));
    box.append(...cards);
    if (p.questions && p.questions.length) box.append(h("div.questions", h("span.label", "Questions this page answers"), h("ul", p.questions.map((q) => h("li", q)))));
  }

  function card(title, content, accept) {
    const c = h("div.s-card", h("div.s-head", h("strong", title)), content);
    const actions = h("div.s-actions",
      h("button.btn.small.ghost", { onclick: () => { c.classList.add("rejected"); fill(actions, h("span.muted.small", "Rejected")); } }, "Reject"),
      h("button.btn.small", { onclick: async () => {
          const note = accept();
          if (!note) { toast("That sentence changed since the suggestion; link it by hand.", "error"); return; }
          accepted.push(note);
          c.classList.add("accepted");
          fill(actions, h("span.ok.small", icon("check", 14), " Accepted"));
          await ed.save(true);
        } }, "Accept"));
    c.append(actions);
    return c;
  }

  function applyLink(ln) {
    const text = ed.view.state.doc.toString();
    const pattern = ln.sentence.split(/\s+/).map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("\\s+");
    const mm = new RegExp(pattern).exec(text);
    if (!mm) return false;
    const inner = mm[0].indexOf(ln.anchor_text);
    if (inner < 0) return false;
    const from = mm.index + inner;
    ed.view.dispatch({ changes: { from, to: from + ln.anchor_text.length, insert: `[[${ln.target}|${ln.anchor_text}]]` } });
    return true;
  }

  function highlight(sentence, anchor) {
    const i = sentence.indexOf(anchor);
    if (i < 0) return [sentence];
    return [sentence.slice(0, i), h("mark", anchor), sentence.slice(i + anchor.length)];
  }

  // --- the run ---------------------------------------------------------------------------------------------------------
  async function run() {
    goBtn.disabled = true;
    tabs.hidden = true;
    const stepEls = {};
    const list = h("ol.steps");
    for (const s of prep.steps) {
      const li = h("li.step", { "data-state": "pending" }, h("span.step-icon"), h("span.step-label", s.label), h("span.step-note"));
      stepEls[s.key] = li;
      list.append(li);
    }
    const log = h("pre.log");
    const logBox = h("details.log-box", h("summary", "Details"), log);
    const result = h("div.run-result");
    fill(body, dryRun ? h("p.note", icon("info", 16), "Dry run: nothing in your folder changes.") : null, list, result, logBox);
    cancelBtn.textContent = "Close";
    let final = null;
    try {
      await stream("/api/publish/run", { id: ed.id, mode, date: mode === "schedule" ? scheduleDate.value : null, dry_run: dryRun, accept_warnings: acceptWarnings, accepted }, (ev, data) => {
        if (ev === "step") {
          const li = stepEls[data.key];
          if (!li) return;
          li.dataset.state = data.state;
          li.querySelector(".step-note").textContent = data.note || "";
          if (data.state === "running") li.scrollIntoView({ block: "nearest" });
        } else if (ev === "log") {
          log.append(document.createTextNode(data.text + "\n"));
          if (data.error) log.append(h("span"));
          log.scrollTop = log.scrollHeight;
        } else if (ev === "done") {
          final = data;
        } else if (ev === "error") {
          final = { ok: false, error: data.message };
        }
      });
    } catch (e) { final = { ok: false, error: e.message }; }
    if (!final) final = { ok: false, error: "The connection closed before the end." };
    if (final.ok) {
      result.append(h("div.run-ok", icon("check", 22),
        h("div", h("strong", final.dry_run ? "The dry run went through every step." : mode === "unpublish" ? "Unpublished." : mode === "schedule" ? "Scheduled." : "Published."),
          final.dry_run ? h("p", final.url ? `Published for real, it would be at ${final.url}` : "") : final.note ? h("p", final.note) : null,
          final.url && !final.dry_run ? h("p", h("a", { href: final.url, target: "_blank", rel: "noopener noreferrer" }, final.url, " ", icon("external", 14))) : null,
          final.commit ? h("p.muted.small", `Commit ${final.commit}`) : null)));
      if (!final.dry_run) {
        await ed.reloadPage();
        await ed.refreshState();
      }
      goBtn.hidden = true;
      cancelBtn.textContent = "Done";
      cancelBtn.className = "btn primary";
    } else {
      logBox.open = true;
      result.append(h("div.run-err", icon("alert", 20), h("div", h("strong", "Stopped: " + (final.error || "something went wrong")),
        h("p.small", final.step === "push" || /Committed/.test(final.error || "") ? "Your commit is safe locally; fix the problem and publish again." : "Nothing was committed. The page is as it was."))));
      goBtn.hidden = false;
      goBtn.disabled = false;
      goBtn.textContent = "Try again";
      goAction = () => prepare();
    }
  }

  prepare();
}

function tomorrow() {
  const d = new Date(Date.now() + 86400000);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export { today, niceDate };
