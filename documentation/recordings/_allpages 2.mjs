import { chromium } from "playwright";
import fs from "node:fs";
const base = "http://127.0.0.1:8031";
const sitemap = await (await fetch(base + "/sitemap.xml")).text();
const paths = [...sitemap.matchAll(/<loc>https?:\/\/[^/]+(\/[^<]*)<\/loc>/g)].map(m => m[1]);
const b = await chromium.launch({ channel: "chrome" });
let problems = 0;
for (const scheme of ["light", "dark"]) for (const w of [1440, 390]) {
  for (const path of paths) {
    const ctx = await b.newContext({ viewport: { width: w, height: 900 }, colorScheme: scheme });
    const p = await ctx.newPage();
    const errs = []; p.on("pageerror", e => errs.push(String(e).slice(0, 120)));
    p.on("console", m => { if (m.type() === "error" && !/api.github.com|favicon|404/.test(m.text())) errs.push(m.text().slice(0, 120)); });
    await p.goto(base + path, { waitUntil: "load" }); await p.waitForTimeout(250);
    const r = await p.evaluate(() => {
      const main = document.querySelector("article.md-content__inner");
      const imgs = [...document.querySelectorAll("article img")].filter(i => i.complete && i.naturalWidth === 0 && i.getBoundingClientRect().width > 0).map(i => i.getAttribute("src"));
      const toc = document.querySelectorAll(".md-nav--secondary .md-nav__link, .md-nav__link--active ~ nav .md-nav__link").length;
      return { overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
               text: main ? main.innerText.trim().length : 0, h2: main ? main.querySelectorAll("h2").length : 0,
               brokenImgs: imgs, toc, banners: [...document.querySelectorAll('img[src*="banner-"]')].filter(i => i.getBoundingClientRect().height > 0).length };
    });
    const bad = r.overflow > 0 || r.text < 200 || r.brokenImgs.length || errs.length || (path === "/" && r.banners !== 1);
    if (bad) { problems++; console.log("PROBLEM", scheme, w, path, JSON.stringify(r), errs.join(" | ")); }
    await ctx.close();
  }
  console.log("done", scheme, w, paths.length, "pages");
}
// search
const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
await p.goto(base + "/"); await p.waitForTimeout(800);
await p.keyboard.press("/"); await p.keyboard.type("figure test"); await p.waitForTimeout(1500);
const hits = await p.locator(".md-search-result__item").count();
console.log("search hits for 'figure test':", hits);
// palette toggle
await p.goto(base + "/getting-started/"); await p.waitForTimeout(500);
const before = await p.evaluate(() => document.body.getAttribute("data-md-color-scheme"));
await p.click("label.md-header__button[for^='__palette']:visible").catch(() => {});
await p.waitForTimeout(300);
await p.click("label.md-header__button[for^='__palette']:visible").catch(() => {});
await p.waitForTimeout(300);
const after = await p.evaluate(() => document.body.getAttribute("data-md-color-scheme"));
console.log("palette toggle:", before, "->", after);
await b.close();
console.log("problems", problems);
