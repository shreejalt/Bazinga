// Checks: the page's problems as you write, each with its line; clicking one jumps there.
import { h, clear, icon } from "../lib.js";

export function render(container, ed, { close }) {
  const list = h("div.issue-list");
  const head = h("p.small.muted");
  container.append(
    h("div.drawer-head", h("h2", "Checks"), h("button.icon-btn", { title: "Close", "aria-label": "Close", onclick: close }, icon("x"))),
    h("div.drawer-body", head, list));

  function refresh() {
    clear(list);
    if (!ed.checksAvailable) { head.textContent = "Checks are not available yet."; return; }
    const errs = ed.issues.filter((i) => i.level === "error");
    const warns = ed.issues.filter((i) => i.level !== "error");
    head.textContent = errs.length ? "Errors stop publishing. Warnings are worth a look." : warns.length ? "Nothing stops publishing. Worth a look:" : "";
    if (!ed.issues.length) {
      list.append(h("div.all-clear", icon("check", 26), h("h3", "All clear"), h("p", "Equations, links, citations, figures and the details are all in order.")));
      return;
    }
    for (const i of [...errs, ...warns]) {
      const line = ed.editorLine(i.line);
      const where = line ? `Line ${line}` : i.field ? fieldName(i.field) : i.line ? "Details" : "";
      list.append(h("button.issue", { class: `issue-${i.level}`, onclick: () => {
          if (line) ed.goToLine(line);
          else if (i.field) ed.focusField(i.field);
          else if (i.line && i.line < ed.bodyLine) ed.openDrawer("details");
        } },
        h("span.issue-icon", icon(i.level === "error" ? "alert" : "info", 16)),
        h("span.issue-text", h("span.issue-msg", i.message), i.hint ? h("span.issue-hint", i.hint) : null),
        where ? h("span.issue-where", where) : null));
    }
  }
  refresh();
  ed.runChecks();
  return { refresh, destroy() {} };
}

function fieldName(f) {
  return { title: "Title", summary: "Summary", description: "Description", topics: "Topics", date: "Date", updated: "Updated", series: "Series", builds_on: "Builds on", cover: "Share image", status: "Status" }[f] || f;
}
