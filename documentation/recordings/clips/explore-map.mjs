// The map: hovering a page lights what is nearest, ring by ring, then walks the reading order through it.
export const meta = {
  path: "/explore/",
  caption: "Hover a page on the map: its nearest pages light up ring by ring, then the reading order walks through it.",
  gif: true, gif_start: 0, gif_seconds: 8,
};

export default async function (page, h) {
  await h.goto(meta.path, 1200);
  await h.offCamera(async () => { await page.evaluate(() => window.scrollTo(0, 380)); await page.waitForTimeout(500); });
  h.start();
  await h.pause(500);
  await h.step("Point at a page");
  await h.moveTo('a.n[data-id="read:softmax-and-temperature"]');
  await h.pause(3600);
  await h.step("Point at another");
  await h.moveTo('a.n[data-id="read:making-figures"]');
  await h.pause(3600);
  await h.move(1120, 720);
  await h.pause(700);
}
