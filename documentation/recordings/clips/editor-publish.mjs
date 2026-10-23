// Publish with "Dry run" ticked: every step runs on a copy of the site, and nothing changes.
import { openEditor, newDraft, setBody } from "../lib/editor.mjs";
export const meta = {
  path: "/", bar: "127.0.0.1:8001 · Editor",
  caption: "Publish, as a dry run: every step runs on a copy of the site, and nothing changes.",
  gif: true, gif_start: 0, gif_seconds: 8,
};

export default async function (page, h) {
  await openEditor(page, h);
  await newDraft(page, h, "Ready to publish", { onCamera: false });
  await setBody(page, h, "A short post that is ready to go.\n\n## What it says\n\nVery little, and that is fine.\n");
  h.start();
  await h.pause(600);
  await h.step("Publish");
  await h.click("button.btn.primary:has-text('Publish') >> nth=0", { highlight: true });
  await page.waitForSelector(".publish-modal", { timeout: 15000 });
  await h.pause(700);
  await h.step("Tick Dry run: nothing will change");
  await h.click(".publish-modal label.check.dry", { fx: 0.04 });
  await h.pause(400);
  await h.step("Go through every step");
  await h.click(".publish-modal .modal-foot button.btn.primary");
  await h.until(() => /went through every step|Done/i.test(document.querySelector(".publish-modal")?.innerText || ""), null, 120000);
  await h.pause(2800);
}
