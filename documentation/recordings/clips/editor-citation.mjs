// Citation…: look a paper up by its arXiv id, add it to references.yml and cite it, in one step.
import { openEditor, newDraft, setBody } from "../lib/editor.mjs";
export const meta = {
  path: "/", bar: "127.0.0.1:8001 · Editor",
  caption: "Citation…: look a paper up by its arXiv id or DOI; it is added to references.yml and cited where the cursor is.",
};

export default async function (page, h) {
  await openEditor(page, h);
  await newDraft(page, h, "Citing a paper", { onCamera: false });
  await setBody(page, h, "Vision transformers cut an image into patches ");
  await h.offCamera(async () => { await page.click(".cm-content"); await page.keyboard.press("Meta+ArrowDown"); await page.keyboard.press("End"); });
  h.start();
  await h.pause(600);
  await h.step("Citation… in the toolbar");
  await h.click('button.tb-btn[aria-label="Citation"]', { highlight: true });
  await page.waitForSelector(".cite-modal input.input.big");
  await h.step("Paste an arXiv id or a DOI");
  await h.click(".cite-modal input.input.big");
  await h.type("2010.11929", 80);
  await h.click('.cite-modal button:has-text("Look it up")');
  await h.until(() => /insert/i.test(document.querySelector(".cite-result")?.innerText || ""), null, 30000);
  await h.pause(1600);
  await h.step("Add it and cite it");
  await h.click(".cite-result button.btn.primary", { highlight: true });
  await h.pause(2600);
}
