// Shared steps for the Editor clips: open it the way an author does (the Write button), and start a draft.

/** Open the Editor straight away (off camera): click the site's Write button and wait for the library. */
export async function openEditor(page, h, from = "/") {
  await h.offCamera(async () => {
    await page.goto(h.url(from), { waitUntil: "load" });
    await page.click("a.cta.write");
    await page.waitForSelector("button:has-text('New post')", { timeout: 30000 });
    await page.evaluate(() => document.fonts && document.fonts.ready);
    await page.waitForTimeout(600);
  });
}

/** New post -> title -> Create draft; waits (off camera) until the writing pane and the preview are ready. */
export async function newDraft(page, h, title, { onCamera = true } = {}) {
  if (!onCamera) {
    await h.offCamera(async () => {
      await page.click("button:has-text('New post')");
      await page.fill("input.input.big", title);
      await page.click("button:has-text('Create draft')");
      await page.waitForSelector(".cm-content", { timeout: 30000 });
      await page.waitForTimeout(2200);
    });
    return;
  }
  await h.click("button:has-text('New post')");
  await page.waitForSelector("input.input.big");
  await h.click("input.input.big");
  await h.type(title, 60);
  await h.pause(300);
  await h.click("button:has-text('Create draft')");
  await h.loaded(".cm-content", 2000);
}

/** Replace the body of the page with `text`, off camera (the clip then starts from a tidy page). */
export async function setBody(page, h, text) {
  await h.offCamera(async () => {
    await page.click(".cm-content");
    await page.keyboard.press("Meta+A");
    await page.keyboard.press("Backspace");
    if (text) await page.keyboard.insertText(text);
    await page.waitForTimeout(2500);
  });
}
