// Sections: every "## " heading becomes a numbered entry in the page's contents, as you type it.
import { openEditor, newDraft, setBody } from "../lib/editor.mjs";
export const meta = {
  path: "/", bar: "127.0.0.1:8001 · Editor",
  caption: "Each ## heading becomes a numbered entry in the contents, in the preview as you type.",
};

export default async function (page, h) {
  await openEditor(page, h);
  await newDraft(page, h, "Sections, step by step", { onCamera: false });
  await setBody(page, h, "One line to start.\n\n");
  await h.offCamera(async () => { await page.click(".cm-content"); await page.keyboard.press("Meta+ArrowDown"); await page.waitForTimeout(800); });
  h.start();
  await h.pause(600);
  await h.step("Write a ## heading");
  await h.click(".cm-content", { fy: 0.6 });
  await page.keyboard.press("Meta+ArrowDown");
  await h.type("## Why it matters\n\nA short paragraph.\n\n", 45);
  await h.pause(1200);
  await h.step("Each one joins the contents, numbered");
  await h.type("## How it works\n\nAnother one.\n\n## What to remember\n\nThe last.\n", 45);
  await h.pause(1400);
  await h.highlight(page.frameLocator("iframe").first().locator("body"), 10).catch(() => {});
  await h.unhighlight();
  await h.moveTo("iframe", { fx: 0.4, fy: 0.75 });
  await h.pause(2600);
}
