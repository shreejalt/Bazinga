// The no-code figure form: pick "Function plot", change the formula, and the preview redraws as you type.
import { openEditor, newDraft } from "../lib/editor.mjs";
export const meta = {
  path: "/", bar: "127.0.0.1:8001 · Editor",
  caption: "Figure… → New figure → Fill in a form: change the formula and the preview redraws as you type.",
  gif: true, gif_start: 3, gif_seconds: 8,
};

export default async function (page, h) {
  await openEditor(page, h);
  await newDraft(page, h, "A figure", { onCamera: false });
  h.start();
  await h.pause(500);
  await h.step("Figure… in the toolbar");
  await h.click('button.tb-btn[aria-label="Figure"]', { highlight: true });
  await h.step("New figure, with a form");
  await h.click("button.fg-new");
  await h.click('button.fg-way:has-text("Fill in a form")');
  await h.step("Pick what to draw");
  await h.click('button.fg-type:has-text("Function plot")');
  await page.waitForSelector("input.fb-expr", { timeout: 15000 });
  await h.pause(900);
  await h.moveTo(':text("Works, and passes its test")', { fy: 6 });
  await h.scroll(330, 900);
  await h.pause(400);
  await h.step("Change the formula: the preview follows");
  const expr = page.locator("input.fb-expr").first();
  await h.click(expr, { fx: 0.97 });
  await page.keyboard.press("End");
  await h.type(" + 0.4*sin(5*x)", 90);
  await h.pause(2200);
  await h.step("Save it and place it in the text");
  await h.click('button:has-text("Save and place in the text")', { highlight: true });
  await h.pause(2600);
}
