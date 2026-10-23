// A portfolio-only site (no blog): the home page, a role opening in Experience, Contact, the CV and a project.
// It is filmed on recordings/sites/portfolio: the example site with the posts removed and a made-up person's details.
export const meta = {
  site: "portfolio", path: "/", bar: "127.0.0.1:8000", crf: 30, speed: 1.15,
  caption: "A portfolio with no blog: the home page, a role in Experience, Contact, the CV and a project.",
  gif: true, gif_start: 0, gif_seconds: 8,
};

export default async function (page, h) {
  await h.goto("/");
  h.start();
  await h.pause(800);
  await h.step("Your home page");
  await h.move(700, 420);
  await h.pause(600);
  await h.step("Experience: each role opens");
  await h.scrollTo("#experience");
  await h.click("details.role summary >> nth=0");
  await h.pause(1600);
  await h.step("Contact");
  await h.click('nav a[href="#contact"], a[href="#contact"] >> visible=true');
  await h.pause(1800);
  await h.step("The CV");
  await h.click('a[href="/cv/"] >> visible=true');
  await h.loaded("main, #main", 600);
  await h.move(700, 500);
  await h.scroll(500, 1400);
  await h.pause(900);
  await h.step("A project");
  await h.click('a[href="/projects/"] >> visible=true');
  await h.loaded("main, #main", 500);
  await h.click('a[href="/projects/weather-app/"] >> nth=-1');
  await h.offCamera(async () => { await page.waitForURL(/weather-app/, { timeout: 15000 }); });
  await h.loaded("main, #main", 600);
  await h.move(700, 480);
  await h.scroll(400, 1200);
  await h.pause(1600);
}
