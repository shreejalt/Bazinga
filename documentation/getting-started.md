# Getting started

In ten minutes you will have Bazinga's example site running on your own computer. You will install it, build it
once, serve it with live reload, and take a short tour of the folders. You need Python, git and a GitHub account.

## What you'll have

Bazinga is a personal website in one folder:

- **A portfolio:** a home page with your photo, who you are, your experience, education and a contact section; a CV
  page; and a page for each project.
- **A blog, if you want one:** posts with equations, diagrams, figures readers can move, series and a map of how
  everything connects, plus Ask, which answers questions from your own pages.

Use either part on its own, or both. The example site shows everything; you remove what you don't need later
([a portfolio without the blog](home-and-cv.md#a-portfolio-without-the-blog)).

## What you need

- **Python 3.11 or newer.** Check with `python3 --version` (on Windows: `py --version`).
- **git**, to get the code and, later, to publish.
- **A GitHub account**, to make your own copy of Bazinga.
- A terminal and a text editor. Bazinga also has its own writing window, [the Editor](editor.md).

There is no Node, no bundler and no database.

## 1. Get the code

On GitHub, open [shreejalt/Bazinga](https://github.com/shreejalt/Bazinga) and press **Fork** to make your own copy
(or **Use this template**, if you see that button). Then clone your copy:

```bash
git clone https://github.com/<you>/<your-site>.git
cd <your-site>
```

Replace `<you>` and `<your-site>` with your GitHub name and the name you gave the copy.

**What you should see:** a folder with `site.yml`, `content/`, `figures/`, `bazinga/` and a `README.md` in it.

## 2. Install

Make a virtual environment (a private set of Python packages for this one folder) inside the folder and install the few packages Bazinga needs:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

On Windows the second line is `.venv\Scripts\pip install -r requirements.txt`.

**What you should see:** pip installs Markdown, PyYAML, Jinja2, latex2mathml, Pygments and numpy, and ends with
`Successfully installed …`. The `.venv` folder is git-ignored, so it never ends up in your repository.

Now switch this terminal to that environment, so that `python` means the Python inside `.venv`:

```bash
source .venv/bin/activate
```

On Windows: `.venv\Scripts\activate`. Do this once in every new terminal. (Without it, type
`.venv/bin/python` wherever these pages say `python`.)

**What you should see:** `(.venv)` at the start of your prompt.

::clip install | Make the virtual environment, install the requirements, and serve the site for the first time.

!!! tip "Why numpy?"
    Only one example figure (`fourier_series`) uses numpy. A figure that does not ask for it never loads it.

## 3. Build the site once

```bash
python -m bazinga build
```

**What you should see:**

```text
Built 14 pages (36 HTML files) into _site/ in 0.78s
```

The whole site is now plain files in `_site/`: HTML, the figures' first pictures, the map, the search passages,
the feed and the sitemap. You could upload that folder anywhere. The numbers change as you add pages.

If something is wrong, nothing is written. The build prints each problem with its file, its line and a hint, and
ends with `Nothing was written. Fix the problems above (each has a hint) and build again.`

To check every page without building, run:

```bash
python -m bazinga check
```

```text
Checked 15 page(s): 0 error(s), 0 warning(s).
```

It counts 15 pages and the build 14 because the example site has one draft. Drafts are checked but never
published.

::clip build | One build and one check of the example site.

## 4. Serve it while you write

```bash
python -m bazinga serve
```

**What you should see:**

```text
Building Your Name …
  built 14 pages in 0.77s
  The Editor runs at http://127.0.0.1:8001/ (the Write button opens it)

  Serving at http://127.0.0.1:8000/  (Ctrl+C to stop; pages reload when you save)
```

Open <http://127.0.0.1:8000> in your browser. You see the example site. When you save a file in `content/`,
`figures/`, `drawings/`, `static/`, `theme/` or `site.yml`, the site rebuilds and the open page reloads by itself. The terminal shows
`changed: <file>` and the new build time.

Every page served this way has a **Write** button, and every post has **Edit this page**. They open the Editor,
which only runs on your computer. The live site never has them.

Useful options (all of them are in the [commands reference](reference/commands.md)):

| Option | What it does |
|---|---|
| `--port 8080` | serve on another port (the default is 8000) |
| `--open` | open the browser for you |
| `--drafts` | also show drafts and scheduled pages |
| `--no-editor` | do not start the Editor, so there is no Write button |
| `--editor-port 9001` | the Editor's port (the default is the serve port + 1, or a free one) |

Press **Ctrl+C** in the terminal to stop.

::clip site-tour | The example site: the home page, a list, and a post with its contents and figures.

## 5. A tour of the folders

```text
site.yml      settings and home page        content/   your posts, cv.yml, topics.yml, references.yml
figures/      interactive figures           drawings/  diagrams made with code (optional)
static/       images and files              wiki/      generated wiki files
bazinga/      the engine, theme and Editor  tests/     run before every deploy
```

What lives where:

| Path | What it holds | You edit it? |
|---|---|---|
| `site.yml` | your name, links, the menu, the home page, colours and fonts, the model for Ask | yes |
| `content/reads/`, `content/papers/`, `content/projects/` | one Markdown file per page | yes |
| `content/elsewhere/` | entries for articles that live on other sites | yes |
| `content/cv.yml` | the CV page | yes |
| `content/topics.yml` | the only topics pages may use | yes |
| `content/references.yml` | the papers you cite | yes, or with `python -m bazinga cite` |
| `figures/` | interactive figures, one small Python file each | yes |
| `drawings/` | diagrams drawn by code (most diagrams are written as text in the post instead) | sometimes |
| `static/` | images and other files, copied as they are | yes |
| `wiki/` | `index.md` (rewritten by every build) and `log.md` (added to when you publish or run a `wiki` command) | no |
| `bazinga/` | the engine, the default theme and the Editor | no; see [Theme](theme.md) to change the look |
| `tests/` | the tests your host runs before each deploy | no |
| `_site/` | the built site | no, it is rebuilt every time |
| `content/series/` | optional highlights for each series ([Series](writing/series.md)) | yes |
| `content/LICENSE.md` | the licence of your writing | yes, replace it |
| `static/uploads/` | pictures uploaded in the Editor | the Editor does |
| `api/ask.py` | the written-answer function for Vercel ([Ask and the wiki](ask-and-wiki.md)) | no |
| `theme/` (you create it) | your own copies of theme files ([Theme](theme.md#your-own-copy-of-a-theme-file)) | yes |
| `proposals/` | suggestions from a model, waiting for you; git-ignored | you read them |
| `sources/` (you create it) | papers and notes you collect for your writing; git-ignored, never published | yes |
| `.env.local` (you create it) | your model key; git-ignored, never committed | yes |
| `.studio/` | the Editor's saved versions; git-ignored | no |
| `vercel.json`, `netlify.toml`, `.github/workflows/pages.yml` | build settings for each host ([Deploying](deploying.md)) | rarely |
| `AGENTS.md` | how the site works, for AI coding agents ([Ask and the wiki](ask-and-wiki.md#working-with-ai-coding-agents)) | when you change the rules |
| `docs/` | notes for people working on Bazinga itself | no |
| `LICENSE`, `THIRD_PARTY.md` | the code's licence and the parts it uses ([What's in Bazinga](whats-in-bazinga.md#licences)) | no |
| `README.md`, `CHANGELOG.md` | what Bazinga is, and what changed in each version ([What's new](whats-new.md)) | no |
| `requirements.txt` | the Python packages Bazinga needs | no |
| `CLAUDE.md` | points coding agents to `AGENTS.md` | no |
| `documentation/`, `mkdocs.yml` | this user guide; not part of your site, so delete them if you like | no |

The example site also holds its own guides in `content/reads/`, a five-part series called *Getting started*:
*Welcome to Bazinga*, *Writing Equations in Bazinga*, *Making Interactive Figures*, *Drawing Diagrams*, and
*Templates for Figures and Diagrams* (a gallery of every figure template). Keep them until you no
longer need them; they are the best way to see each feature next to the text that makes it.

## 6. Run the tests (optional)

Your host runs these before every deploy, so it is worth knowing they pass on your machine too:

```bash
python -m unittest discover tests
```

**What you should see:** rows of dots, then `Ran 497 tests in …` and `OK (skipped=3)` (under a minute). The three
skipped tests time things and run only when you ask for them. A few warning lines among the dots are normal; only
`FAILED` means something is wrong.

## What's next

Next, see every part of Bazinga in one place: [What's in Bazinga](whats-in-bazinga.md). Or jump in:

- Make it your portfolio: [home page, CV and projects](home-and-cv.md).
- Write your first post: [Writing, step 1](writing/first-post.md).
