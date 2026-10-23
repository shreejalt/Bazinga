// A reader drags a figure's slider and the plot redraws as they move it; then a preset, then Reset.
export const meta = {
  path: "/reads/softmax-and-temperature/",
  caption: "Drag the slider and the figure redraws as you move it. Presets set several controls at once.",
  gif: true, gif_start: 0, gif_seconds: 8,
};

export default async function (page, h) {
  await h.goto(meta.path);
  const fig = page.locator('figure[data-figure="softmax_temperature"]').first();
  await h.offCamera(async () => {
    const top = await fig.evaluate((el) => el.getBoundingClientRect().top);
    await page.evaluate((y) => window.scrollBy(0, y - 70), top);
    // the first move loads the figure's code in the browser; do it before filming
    await fig.locator('input[type=range][name="t"]').evaluate((i) => { i.value = 1.05; i.dispatchEvent(new Event("input", { bubbles: true })); });
    await page.waitForTimeout(5000);
    await fig.locator("button.fig-reset").click();
    await page.waitForTimeout(1200);
  });
  h.start();
  await h.pause(600);
  const slider = fig.locator('input[type=range][name="t"]');
  await h.step("Drag the temperature slider");
  await h.slide(slider, 0.25, 1600);
  await h.pause(700);
  await h.slide(slider, 4.2, 2400);
  await h.pause(900);
  await h.step("Pick a preset");
  await h.click(fig.locator("button.fig-preset", { hasText: "Sharp" }), { highlight: true });
  await h.pause(1400);
  await h.step("Reset puts it back");
  await h.click(fig.locator("button.fig-reset"));
  await h.pause(1300);
}
