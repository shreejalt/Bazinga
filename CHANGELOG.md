# Changelog

What changed in Bazinga, newest first. If your site was made from an older copy, this is the list to read before you
pull the new version in.

## 2026-10-23

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
