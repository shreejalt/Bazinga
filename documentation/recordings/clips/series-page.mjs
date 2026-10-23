// Series: the list of series, one series with its parts in order, and a part showing where it sits.
export const meta = {
  path: "/series/getting-started/", crf: 27,
  caption: "A series page lists its parts in order with highlights; every part shows where it sits.",
};

export default async function (page, h) {
  await h.goto("/series/");
  h.start();
  await h.pause(700);
  await h.step("Every series on the site");
  await h.click('a[href="/series/getting-started/"] >> visible=true');
  await h.loaded("main, #main", 600);
  await h.step("Its parts, in order, with highlights");
  await h.move(700, 520);
  await h.scroll(520, 1500);
  await h.pause(1200);
  await h.step("Open part 2");
  await h.click('#main a[href="/reads/writing-math/"] >> visible=true');
  await h.loaded("main, #main", 600);
  await h.step("The part shows the whole series");
  await h.highlight(page.locator("text=Series:").first(), 1600);
  await h.unhighlight();
  await h.pause(900);
}
