// The equation helper: type LaTeX, see it drawn as you type, number it, and insert it into the page.
import { openEditor, newDraft, setBody } from "../lib/editor.mjs";
export const meta = {
  path: "/", bar: "127.0.0.1:8001 · Editor",
  caption: "The equation helper draws the formula as you type; Insert puts it where the cursor was.",
};

export default async function (page, h) {
  await openEditor(page, h);
  await newDraft(page, h, "Softmax, briefly", { onCamera: false });
  await setBody(page, h, "The softmax with a temperature:\n\n");
  await h.offCamera(async () => { await page.click(".cm-content"); await page.keyboard.press("Meta+ArrowDown"); });
  h.start();
  await h.pause(600);
  await h.step("Open the equation helper");
  await h.click('button.tb-btn[aria-label="Equation"]', { highlight: true });
  await page.waitForSelector(".eq-modal .cm-content", { timeout: 15000 });
  await h.pause(500);
  await h.step("Type LaTeX: it is drawn as you type");
  await h.click(".eq-modal .cm-content");
  await h.type("p_i = \\frac{e^{z_i / T}}{\\sum_j e^{z_j / T}}", 60);
  await h.pause(1500);
  await h.step("Number it");
  await h.click('.eq-modal :text("Number this equation")');
  await h.pause(500);
  await h.step("Give it a short name");
  await h.click('.eq-modal input[placeholder^="eq:"], .eq-modal input[placeholder*="softmax"]');
  await h.type("softmax", 70);
  await h.pause(900);
  await h.step("Insert it into the page");
  await h.click('.eq-modal .modal-foot button.btn.primary, .eq-modal button.btn.primary >> nth=-1');
  await h.pause(2600);
}
