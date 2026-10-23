// The Editor: Write opens it, New post starts a draft, and the preview follows the typing.
import { newDraft, setBody } from "../lib/editor.mjs";
export const meta = {
  path: "/", bar: "127.0.0.1:8001 · Editor",
  caption: "Write opens the Editor. Start a draft, type, and the preview on the right follows as you write.",
};

export default async function (page, h) {
  await h.goto("/reads/welcome/");
  h.start();
  await h.pause(600);
  await h.step("Click Write on any page");
  await h.click("a.cta.write", { highlight: true });
  await h.loaded("button:has-text('New post')", 700);
  await h.step("Start a new post");
  await newDraft(page, h, "My first post");
  await setBody(page, h, "");
  await h.step("Type, and the preview follows");
  await h.click(".cm-content", { fy: 0.1 });
  await h.type("Softmax turns scores into probabilities.\n\n## The formula\n\n$$\np_i = \\frac{e^{z_i}}{\\sum_j e^{z_j}}\n$$\n", 42);
  await h.pause(1800);
  await h.moveTo(".preview iframe, iframe", { fx: 0.5, fy: 0.6 });
  await h.scroll(380, 1200);
  await h.pause(2200);
}
