# Changelog

What changed in Bazinga, newest first. If your site was made from an older copy, this is the list to read before you
pull the new version in.

## 2026-10-23

- **Small fixes from the documentation review:** `figure new <name> --from <drawing starter>` now tells you to use
  `::drawing <name>.<function>`; `wiki query` lists each section once and no longer runs a callout's title into its
  text ("at onceHow"); `wiki --help` lists every command, and its examples use a real page id
  (`read:attention-from-scratch`); a broken `site.yml` is reported as `site.yml:<line>: not valid YAML`, once;
  publishing without a remote says to run `git push -u origin HEAD` (the commit is already made); `site.avatar` may
  start with `/`; the example home title is "Machine Learning Notes" (the site name is added to it); and
  `wiki/index.md` lists all 14 example pages.
- **No links to parts you switched off.** With `features: {ask: false}` (or `explore`, `series`) the rail leaves out
  those items even if `nav:` still lists them, and pages no longer show "Ask the map", "Explore" or "On the map".
- **Page numbers after a `::pagebreak`** are right: the footer of the second page said "[Page 1]".
- **Removing the example pages no longer stops your deploys.** Sixteen tests built the template's own example pages,
  so on a portfolio-only site (or any site that deleted the examples) they failed, and every host runs the tests
  before deploying. They now build their own copy of the example site in `tests/fixtures/example-site/`. There is no
  need to take the test step out of `vercel.json`, `netlify.toml` or the Pages workflow.
- **Editor: previews can no longer write.** A script in a page (or a figure's code) used to run in the preview with
  the Editor's rights, so a page could save files through it. Previews now open from a second local port, and every
  write needs a key that only the Editor's own page has. Nothing changes in how you use it.
- **Editor: a figure drafted from a description is not run until you say so.** It opens as code with a note; press
  "I have read it: run it" (or save it) to test it. The note also lists anything in it a figure does not need, such
  as imports other than `math`, `random`, `statistics`, the figure kits and (when declared) `numpy`.
- **Ask's written answer reads only your own site.** On Vercel it used to take the site's address from the visitor's
  request, so a crafted request could feed it someone else's passages and links. It now uses `SITE_URL` or
  `site.origin` (and says so plainly when neither is set), and links that do not point into your site are dropped,
  on the server and in the page.
- **A failed publish leaves nothing behind.** When the commit failed (a git hook said no, or git did not know your
  name), the published version of the page and a "publish" line in `wiki/log.md` stayed staged, so your next commit
  would have published it. Publish now checks who commits before it stages anything, and on any failure unstages its
  files and puts the page and the wiki files back.
- **Renaming a page that was never committed** no longer stops its first publish.
- **Typos in `status` or `date` no longer hide a page.** A page that is not `status: draft` but says
  `status: publshed` or `date: 2026/01/05` used to be left out of the site without a word; the build now stops and
  names the file and line. Impossible dates such as `2026-02-30` (in a page, `site.yml`, `references.yml` or
  `cv.yml`) are reported as `<file>:<line>: … not a real date` instead of a Python traceback.
- **Python 3.11 works again.** `requirements.txt` pinned numpy 2.5.4, which needs Python 3.12, so the whole install
  failed on 3.11. It now picks numpy 2.4.6 on 3.11. A build without numpy no longer stops: a figure that needs it
  is replaced by a short note and a warning.
- **Phones and tablets:** text fields and menus are 16 px on touch screens, so iPhones no longer zoom in when you
  tap them; the Ask panel's close button is a proper target and its header stays in view above the keyboard;
  figure sliders and buttons are at least 36 px tall on touch screens; the references list wastes less width on
  phones; and a post's section list in the rail fades at its edge to show it scrolls.
- **Editor on tablets and phones:** the preview no longer comes up blank at 980 px and narrower (it fills the screen
  when you show it), the top bar's buttons scroll inside the bar instead of overlapping, the Library's tabs scroll
  instead of pushing the page sideways, and the Editor uses the visible screen height on phones.
- **Figure text is readable on phones.** The smallest labels were 6-8 px on a 360-px phone; the phone layout now
  sets them larger (about 11 px there), insets of 3-D figures included, and pages give figures a little more width
  on phones.
- **The map works by tap on iPhone and iPad.** The first tap on a page now shows its connections and the second
  opens it, as on Android; before, Safari opened the page at once.
- **Safer links and data blocks.** A reference whose `url` is not an `http(s)` address or a path on your site (for
  example `javascript:`) is no longer turned into a link; the arXiv or DOI link is used instead, if there is one.
  Titles containing `</script>` or `<!--` can no longer break out of the page's structured data. The local server's
  Ask endpoint refuses a body length that is not a plain number.
- **Scheduled posts on Vercel and Netlify:** the README now says how to give them a daily build (a build hook and a
  small GitHub Actions cron), and the Editor's schedule note says a page appears on the first build on or after its
  date. Before, the docs claimed the README explained it, and it did not.
- **The Editor's name everywhere.** `serve --editor-port` (the old `--studio-port` still works), "The Editor
  stopped." when you press Ctrl+C, and citation lookups no longer send a made-up email address.
- **`bazinga new` writes valid front matter** for any title (backslashes and quotes included), and refuses a `--slug`
  with `/`, `..` or capitals instead of writing outside `content/`.
- **The figure form cannot hang on a huge power.** An expression such as `(9*9)**999999999` used to be worked out
  exactly and never finish; it is now computed as a decimal number, which overflows at once and leaves that point out.
- **3-D figures work from the keyboard.** Tab to the picture, then the left and right arrow keys turn it and up and
  down tilt it (Shift for small steps); the new angle is read out to screen readers. The hint under the figure says so.
- **Keyboard focus shows on the rail.** The rail kept a pale focus ring from when it was dark; it now uses the same
  blue ring as the rest of the page. Unused dark-rail colours were removed from `site.css`.
- **Deploys no longer fail on a slow build machine.** The tests that time things (figures under 30 ms and the like)
  now run only with `BAZINGA_PERF_TESTS=1`; the deploy runs every correctness check as before.
- **`check` counts pages it cannot read.** Broken front matter is now an error (exit code 1), and
  `check <file>` reports only the files you name.
- **Sites under a sub-path work.** If `site.origin` has a path (for example `https://you.github.io/notes`), every
  link, asset, data file and figure module is placed under `/notes`. The GitHub Pages workflow fills in the address
  by itself, so a project site works with no edits. `python -m bazinga build --origin …`, `BAZINGA_ORIGIN` or
  `SITE_URL` set the address for one build. If you changed templates under `theme/`, write your own links with
  `link()` or `{{ base }}`.
- **Publish pushes where you expect.** It pushes to the branch your current one tracks, even when the names differ.
  It no longer commits under a made-up email: set `publish.author` in `site.yml` or your git name and email first.
- **`CLAUDE.md`** points coding agents to `AGENTS.md`, so its rules (you write and publish; models only propose)
  apply to every agent.
- **New look for the project:** the Bazinga logo (a Vulcan-salute hand with a pencil beside it), the tagline
  "Live long and connect the dots.", and an animated README banner. Their files are in `documentation/assets/brand/`.

## 2026-10-22

- **3-D figures.** Surfaces, curves, planes, vectors, boxes, axes and cameras that readers turn by dragging, with
  points they can move. Four new starters (`scene_basic`, `surface_plot`, `vectors_planes`, `camera_rig`) and a
  "3-D scene" type in the figure form. `figure test` now also drags every handle.
- **"Made with Bazinga"** link in the rail and the logo as the default tab icon. Turn the link off with
  `features: {credit: false}`.

## 2026-10-21

- The writing window is called the **Editor** (`python -m bazinga editor`). The old name `studio` still works.

## 2026-10-20

- **First version**, then named Bazinga: Markdown posts with real equations, interactive figures (a form, starters,
  or code), text diagrams, the map, Ask, the wiki files, series and topic pages, a CV page, and the local Editor that
  publishes. Four new templates (your own data as lines, two linked panels, data piling up, a field of arrows) and a
  page with every template working.
