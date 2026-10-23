// A 3-D figure: drag the background to turn the scene, then drag the point P across the surface.
export const meta = {
  path: "/reads/making-figures/",
  caption: "Turn a 3-D figure by dragging it, then drag the point P: the tangent plane follows.",
  gif: true, gif_start: 0, gif_seconds: 8,
};

export default async function (page, h) {
  await h.goto(meta.path, 900);
  const fig = page.locator('figure[data-figure="tangent_plane"]').first();
  const svg = fig.locator("svg.fig-plot:not(.narrow) >> visible=true").first();
  await h.offCamera(async () => {
    const r = await svg.evaluate((el) => { const b = el.getBoundingClientRect(); return [b.top, b.height]; });
    await page.evaluate(([t, hgt]) => window.scrollBy(0, t - (800 - hgt) / 2 + 40), r);
    await page.waitForTimeout(400);
    const b = await svg.boundingBox();
    // a tiny drag loads the figure's code in the browser before filming
    await page.mouse.move(b.x + b.width * 0.9, b.y + b.height * 0.15);
    await page.mouse.down(); await page.mouse.move(b.x + b.width * 0.9 + 3, b.y + b.height * 0.15); await page.mouse.up();
    await page.waitForTimeout(6000);
  });
  h.start();
  await h.pause(500);
  const b = await svg.boundingBox();
  await h.step("Drag the scene to turn it");
  await h.dragFrom(b.x + b.width * 0.85, b.y + b.height * 0.2, 230, 0, 1900);
  await h.pause(500);
  await h.dragFrom(b.x + b.width * 0.9, b.y + b.height * 0.3, -150, 50, 1500);
  await h.pause(800);
  const p = await page.evaluate(() => {
    const f = document.querySelector('figure[data-figure="tangent_plane"]');
    const el = [...f.querySelectorAll("svg text")].find((t) => t.textContent.trim() === "P" && t.getClientRects().length && t.getBoundingClientRect().width);
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return [r.x, r.y + r.height];
  });
  if (p) {
    await h.step("Drag the point P");
    const hdl = await page.evaluate(([x, y]) => {
      // the handle is the circle nearest to the label P
      const f = document.querySelector('figure[data-figure="tangent_plane"]');
      let best = null, d = 1e9;
      for (const c of f.querySelectorAll("svg circle")) { if (!c.getClientRects().length) continue; {
        const r = c.getBoundingClientRect(), cx = r.x + r.width / 2, cy = r.y + r.height / 2;
        const dd = Math.hypot(cx - x, cy - y);
        if (dd < d) { d = dd; best = [cx, cy]; } }
      }
      return best;
    }, p);
    const [x0, y0] = hdl || p;
    await h.dragFrom(x0, y0, 80, 30, 1500);
    await h.pause(300);
    await h.dragFrom(x0 + 80, y0 + 30, -130, 30, 1700);
  }
  await h.pause(1500);
}
