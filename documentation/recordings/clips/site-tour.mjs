// A first look at the example site: the home page, the list of reads, and one read with its contents.
export const meta = {
  path: "/", bar: "127.0.0.1:8000", crf: 30,
  caption: "The example site: the home page, a list of posts, and a post with its contents.",
};

export default async function (page, h) {
  await h.goto("/");
  h.start();
  await h.pause(700);
  await h.step("The home page");
  await h.move(700, 500);
  await h.scroll(640, 1500);
  await h.pause(700);
  await h.step("Reads lists the posts");
  await h.click('a[href="/reads/"] >> visible=true');
  await h.loaded("main, #main", 600);
  await h.pause(900);
  await h.step("Open one");
  await h.click('a[href="/reads/softmax-and-temperature/"] >> visible=true');
  await h.loaded("main, #main", 600);
  await h.pause(900);
  await h.step("Its contents, numbered");
  await h.move(640, 520);
  await h.scroll(560, 1400);
  await h.pause(2000);
}
