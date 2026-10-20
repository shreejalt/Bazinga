// Small enhancements for every page. Everything works without this file; it only adds:
//  - the light/dark switch (the choice is remembered in localStorage when the browser allows it),
//  - "Copy" buttons on code blocks,
//  - copying a heading's link when its "#" is clicked,
//  - highlighting the current section in the table of contents.
(function () {
  "use strict";

  var root = document.documentElement;
  var KEY = "tessera-theme";

  // ------------------------------------------------------------------------------ light / dark
  function systemDark() {
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  }
  function currentTheme() {
    var t = root.getAttribute("data-theme");
    if (t === "light" || t === "dark") return t;
    return systemDark() ? "dark" : "light";
  }
  function saveTheme(t) {
    try { localStorage.setItem(KEY, t); } catch (e) { /* private mode or blocked: the choice lasts this page only */ }
  }
  function initThemeToggle() {
    var buttons = document.querySelectorAll(".theme-toggle");
    function label() {
      var next = currentTheme() === "dark" ? "light" : "dark";
      buttons.forEach(function (b) {
        b.setAttribute("aria-label", "Switch to " + next + " mode");
        b.setAttribute("title", "Switch to " + next + " mode");
      });
    }
    buttons.forEach(function (b) {
      b.addEventListener("click", function () {
        var next = currentTheme() === "dark" ? "light" : "dark";
        root.setAttribute("data-theme", next);
        saveTheme(next);
        label();
        document.dispatchEvent(new CustomEvent("tessera:theme", { detail: { theme: next } }));
      });
    });
    label();
  }

  // ------------------------------------------------------------------------------ copying
  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text);
    }
    return new Promise(function (resolve, reject) {
      var area = document.createElement("textarea");
      area.value = text;
      area.setAttribute("readonly", "");
      area.style.position = "fixed";
      area.style.opacity = "0";
      document.body.appendChild(area);
      area.select();
      try { document.execCommand("copy") ? resolve() : reject(new Error("copy failed")); }
      catch (e) { reject(e); }
      finally { document.body.removeChild(area); }
    });
  }

  function initCopyButtons() {
    document.querySelectorAll(".code-block").forEach(function (block) {
      if (block.querySelector(".copy-code")) return;
      var code = block.querySelector("code");
      if (!code) return;
      var button = document.createElement("button");
      button.type = "button";
      button.className = "copy-code";
      button.textContent = "Copy";
      button.setAttribute("aria-label", "Copy this code");
      button.addEventListener("click", function () {
        copyText(code.innerText.replace(/\n$/, "")).then(function () {
          button.textContent = "Copied";
          button.classList.add("done");
        }, function () {
          button.textContent = "Select and copy";
        });
        setTimeout(function () { button.textContent = "Copy"; button.classList.remove("done"); }, 1800);
      });
      block.appendChild(button);
    });
  }

  function initHeadingLinks() {
    document.querySelectorAll(".heading-anchor").forEach(function (a) {
      a.addEventListener("click", function (ev) {
        var url = location.href.split("#")[0] + a.getAttribute("href");
        ev.preventDefault();
        history.replaceState(null, "", a.getAttribute("href"));
        var target = document.getElementById(decodeURIComponent(a.getAttribute("href").slice(1)));
        if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
        copyText(url).then(function () {
          a.classList.add("copied");
          setTimeout(function () { a.classList.remove("copied"); }, 1500);
        }, function () { /* the address bar already shows the link */ });
      });
    });
  }

  // ------------------------------------------------------------------------------ contents
  function initToc() {
    var links = Array.prototype.slice.call(document.querySelectorAll(".toc a[href^='#']"));
    if (!links.length || !("IntersectionObserver" in window)) return;
    var byId = {};
    var headings = links.map(function (a) {
      var id = decodeURIComponent(a.getAttribute("href").slice(1));
      byId[id] = a;
      return document.getElementById(id);
    }).filter(Boolean);
    var visible = new Set();
    function update() {
      var current = null;
      for (var i = 0; i < headings.length; i++) {
        if (visible.has(headings[i].id)) { current = headings[i].id; break; }
      }
      if (!current) {
        // Between headings: the last heading above the top of the screen is the current section.
        headings.forEach(function (h) { if (h.getBoundingClientRect().top < 120) current = h.id; });
      }
      links.forEach(function (a) { a.classList.remove("is-active"); a.removeAttribute("aria-current"); });
      if (current && byId[current]) {
        byId[current].classList.add("is-active");
        byId[current].setAttribute("aria-current", "location");
      }
    }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) visible.add(e.target.id); else visible.delete(e.target.id);
      });
      update();
    }, { rootMargin: "-64px 0px -60% 0px" });
    headings.forEach(function (h) { io.observe(h); });

    // On narrow screens the contents box starts folded, and closes after a jump.
    var box = document.querySelector(".toc-box");
    var wide = window.matchMedia("(min-width: 1240px)");
    function fit() { if (box) box.open = wide.matches; }
    fit();
    if (wide.addEventListener) wide.addEventListener("change", fit);
    links.forEach(function (a) {
      a.addEventListener("click", function () { if (box && !wide.matches) box.open = false; });
    });
  }

  function start() {
    initThemeToggle();
    initCopyButtons();
    initHeadingLinks();
    initToc();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
