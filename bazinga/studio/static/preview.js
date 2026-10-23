// The live preview: an iframe of the real rendered page (/preview/<id>), served from the preview port (another
// origin, see bridge.js). Updates are sent to the frame, which patches the page in place so the scroll position, and
// the state of interactive figures that did not change, survive typing.
import { h, previewURL, frameLink } from "./lib.js";

export function createPreview(container, id, { onReady } = {}) {
  const src = (extra = "") => previewURL(`/preview/${encodeURIComponent(id)}${extra}`);
  const frame = h("iframe.preview-frame", { title: "Preview of the page", src: src() });
  const note = h("div.preview-note", { hidden: true });
  container.append(frame, note);
  let ready = false, pending = null, reloadScroll = null, scrollY = 0;

  const send = frameLink(frame, (m) => {
    if (m.bz === "scroll") scrollY = +m.y || 0;
    else if (m.bz === "reload") reload();
  });

  function matchTheme() {
    send({ bz: "theme", theme: document.documentElement.dataset.theme || "" });
  }
  window.addEventListener("studio-theme", matchTheme);

  frame.addEventListener("load", () => {
    ready = true;
    matchTheme();
    if (reloadScroll !== null) send({ bz: "scrollTo", y: reloadScroll });
    reloadScroll = null;
    if (pending) { const p = pending; pending = null; update(p); }
    if (onReady) onReady();
  });

  function reload() {
    reloadScroll = scrollY;
    ready = false;
    frame.src = src(`?t=${Date.now()}`);
  }

  function update(html) {
    if (!ready) { pending = html; return; }
    send({ bz: "update", html });
  }

  function setNote(text, kind = "info") {
    note.hidden = !text;
    note.className = `preview-note ${kind}`;
    note.textContent = text || "";
  }

  // editorAnchors: [{y, kind}] in editor pixels; the frame maps them onto its headings, figures and equations.
  function syncTo(editorY, editorAnchors, editorHeight, bodyTop = 0) {
    if (!ready) return;
    send({ bz: "sync", editorY, anchors: editorAnchors, editorHeight, bodyTop });
  }

  function scrollToId(anchor) { send({ bz: "scrollToId", id: anchor }); }

  return { frame, update, reload, setNote, syncTo, scrollToId };
}
