// The diagram panel: write boxes and arrows as text, and the drawing appears beside it.
import { openEditor, newDraft } from "../lib/editor.mjs";
export const meta = {
  path: "/", bar: "127.0.0.1:8001 · Editor",
  caption: "Diagram…: write boxes and arrows as text; the drawing appears beside it, for wide screens and phones.",
};

export default async function (page, h) {
  await openEditor(page, h);
  await newDraft(page, h, "A diagram", { onCamera: false });
  h.start();
  await h.pause(500);
  await h.step("Diagram… in the toolbar");
  await h.click('button.tb-btn[aria-label="Diagram"]', { highlight: true });
  await page.waitForSelector(".dgp-modal .cm-content", { timeout: 15000 });
  await h.offCamera(async () => {
    await page.click(".dgp-modal .cm-content");
    await page.keyboard.press("Meta+A");
    await page.keyboard.press("Backspace");
    await page.waitForTimeout(500);
  });
  await h.step("Write the boxes and arrows");
  await h.click(".dgp-modal .cm-content", { fy: 0.1 });
  await h.type("Write -> Check -> Build -> Publish [emphasis]\nCheck -> Write: \"fix\"\nBuild [accent]", 62);
  await h.pause(1500);
  await h.step("See it at phone width");
  await h.click('.dgp-modal button.seg-btn:has-text("Phone")');
  await h.pause(1600);
  await h.click('.dgp-modal button.seg-btn:has-text("Wide")');
  await h.step("Insert it");
  await h.click('.dgp-modal button:has-text("Insert diagram")');
  await h.pause(2400);
}
