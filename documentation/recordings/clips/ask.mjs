// Ask: a reader types a question and gets an answer from the site's own pages, with links to the sections.
export const meta = {
  path: "/ask/",
  caption: "Ask a question: the answer is put together from the site's own pages, with links to the sections it used.",
  gif: true, gif_start: 1.5, gif_seconds: 8,
};

export default async function (page, h) {
  await h.goto(meta.path, 800);
  await h.offCamera(async () => {
    // the first answer prepares the answering code in the browser; do it before filming
    await page.fill("#ask-q", "softmax");
    await page.click("#ask-go");
    await h.until(() => /passages of this site/i.test(document.body.innerText), null, 60000);
    await page.fill("#ask-q", "");
    await page.evaluate(() => { const r = document.querySelector("#ask-out, .ask-out, .answer"); if (r) r.innerHTML = ""; window.scrollTo(0, 0); });
    await page.waitForTimeout(400);
  });
  h.start();
  await h.pause(500);
  await h.step("Type a question");
  await h.click("#ask-q");
  await h.type("What does the temperature do to a softmax?", 50);
  await h.pause(300);
  await h.step("Ask");
  await h.click("#ask-go");
  await h.pause(2400);
  await h.step("The answer links to the sections it used");
  await h.scroll(300, 1100);
  await h.pause(2600);
}
