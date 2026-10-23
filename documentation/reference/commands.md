# Commands

This page lists every command and every option, with the help text each one prints and a short example that was
run on the example site. Run every command from your site's folder (the one with `site.yml`).

All commands start with `python -m bazinga`. Here `python` is the one in your virtual environment: run
`source .venv/bin/activate` first (see [Getting started](../getting-started.md#2-install)), or type
`.venv/bin/python` instead.

To see a command's options in your terminal, add `--help`, for example `python -m bazinga build --help`. `wiki` has
no `--help`: run `python -m bazinga wiki` on its own to see its list.

A language model is optional; see [Ask and the wiki](../ask-and-wiki.md#connect-a-model).

| Command | What it does | Needs a language model |
|---|---|---|
| [`new`](#new) | start a new draft | no |
| [`build`](#build) | build the site into `_site/` | no |
| [`serve`](#serve) | build, serve, rebuild on save, and start the Editor | no |
| [`check`](#check) | run the checks on pages | no |
| [`cite`](#cite) | add a paper to `content/references.yml` | no (needs the internet) |
| [`math`](#math) | check one formula | no |
| [`figure`](#figure) | new figure, test, preview, list, starters | no |
| [`editor`](#editor) | the Editor, the local writing window | no |
| [`studio`](#editor) | the same as `editor` (the old name) | no |
| [`publish`](#publish) | publish one page from the terminal | no |
| [`wiki`](#wiki) | the wiki files, questions, and model proposals | some sub-commands |

## The whole program

```text
usage: python -m bazinga [-h] [--root ROOT] <command> ...

Build and write a Bazinga site.

positional arguments:
  <command>
    new        start a new draft
    build      build the site into _site/
    serve      build, serve on 127.0.0.1 and rebuild on changes
    check      check pages; exit code 1 on errors
    cite       add a paper to content/references.yml
    math       check one formula (MathML, or what is wrong and what to write
               instead)
    figure     new figure (from a starter or the builder), test, preview or
               list figures
    editor     the Editor, the local writing window
    studio     the same as editor
    publish    publish one page
    wiki       index, query, ingest, lint, highlights, describe, equation,
               figure, log

options:
  -h, --help   show this help message and exit
  --root ROOT  the site folder (default: the current folder)
```

`--root` goes **before** the command and points at another site folder:

```bash
python -m bazinga --root . check --errors-only
```

**What you should see:**

```text
Checked 15 page(s): 0 error(s), 0 warning(s).
```

Python must still be able to import `bazinga`, so run it from a folder that holds the `bazinga/` package (or has it
installed).

## new

```text
usage: python -m bazinga new [-h] [--kind KIND] [--slug SLUG] title

positional arguments:
  title

options:
  -h, --help   show this help message and exit
  --kind KIND  content folder, e.g. posts or projects (default: the first
               kind)
  --slug SLUG  the file name / URL part (default: from the title)
```

Copies the starter post into `content/<kind>/<slug>.md` with `status: draft` and today's date.

```bash
python -m bazinga new "My first post"
```

**What you should see:**

```text
Created content/reads/my-first-post.md (a draft). Preview it with: python -m bazinga serve --drafts
```

```bash
python -m bazinga new "A side project" --kind projects --slug side-project
```

**What you should see:**

```text
Created content/projects/side-project.md (a draft). Preview it with: python -m bazinga serve --drafts
```

The first kind in `site.yml` is the default (`reads` on the example site). An unknown kind or an existing file stops
it:

```bash
python -m bazinga new "My first post" --kind nope
```

**What you should see:**

```text
unknown kind 'nope'; site.yml defines: reads, papers, projects, elsewhere
```

```bash
python -m bazinga new "My first post"
```

**What you should see:**

```text
content/reads/my-first-post.md already exists; pick another title or pass --slug
```

## build

```text
usage: python -m bazinga build [-h] [--drafts] [--quiet] [--origin URL]

options:
  -h, --help    show this help message and exit
  --drafts      include drafts and scheduled pages (private previews only)
  --quiet
  --origin URL  the address the site is deployed at, instead of site.origin
                (also BAZINGA_ORIGIN or SITE_URL in the environment); a path
                such as https://you.github.io/repo puts every link under /repo
```

```bash
python -m bazinga build
```

**What you should see:**

```text
Built 14 pages (36 HTML files) into _site/ in 0.83s
```

```bash
python -m bazinga build --drafts
```

**What you should see:**

```text
Built 17 pages (39 HTML files) into _site/ in 0.77s — drafts included, do not deploy this build
```

`--origin` builds for another address without editing `site.yml`. With a path, every link starts with it:

```bash
python -m bazinga build --origin https://you.github.io/notes
```

**What you should see:**

```text
Built 14 pages (36 HTML files) into _site/ in 1.06s
```

```bash
grep -o '<link rel="canonical"[^>]*>' _site/reads/welcome/index.html
```

**What you should see:**

```text
<link rel="canonical" href="https://you.github.io/notes/reads/welcome/">
```

Only `build` reads `--origin`, `BAZINGA_ORIGIN` and `SITE_URL`; `serve` and the Editor always serve at the root of
`127.0.0.1`. See [A site under a path](configuration.md#a-site-under-a-path).

The `--drafts` count is from after the two `new` commands above; a fresh copy prints 15 pages (37 HTML files).
`--quiet` hides the warnings and notes printed while building; the last line still counts the warnings. If anything is wrong, nothing is written: the build lists each problem with
its file, line and a hint, and the exit code is 1.

## serve

```text
usage: python -m bazinga serve [-h] [--port PORT] [--open] [--drafts]
                               [--no-editor] [--editor-port STUDIO_PORT]

options:
  -h, --help            show this help message and exit
  --port PORT
  --open                open the browser
  --drafts              also show drafts and scheduled pages (local preview)
  --no-editor, --no-studio
                        do not start the Editor (no Write button)
  --editor-port, --studio-port STUDIO_PORT
                        port of the Editor on 127.0.0.1 (default: the serve
                        port + 1, or a free one)
```

```bash
python -m bazinga serve --port 8000
```

**What you should see:**

```text
Building Your Name …
  built 14 pages in 1.94s
  The Editor runs at http://127.0.0.1:8001/ (the Write button opens it)

  Serving at http://127.0.0.1:8000/  (Ctrl+C to stop; pages reload when you save)
```

- The default port is 8000. The Editor starts next to it, on 8001 when that is free, and every page gets a
  **Write** button. You will also see a line saying where the Editor runs.
- It serves on `127.0.0.1` only, so the pages are visible on your computer and nowhere else.
- `/api/ask/` works locally too, for written answers (see [Ask and the wiki](../ask-and-wiki.md)).
- Press ++ctrl+c++ to stop.

## check

```text
usage: python -m bazinga check [-h] [--errors-only] [files ...]

positional arguments:
  files

options:
  -h, --help     show this help message and exit
  --errors-only
```

Runs the same checks as the build and the Editor. With no files it checks every page.

```bash
python -m bazinga check content/reads/welcome.md
```

**What you should see:**

```text
Checked 1 page(s): 0 error(s), 0 warning(s).
```

Each problem is printed as `file:line: level: message` with a hint. The exit code is 1 when there is at least one
error, so it works in scripts. `--errors-only` hides the warnings.

## cite

```text
usage: python -m bazinga cite [-h] [--key KEY] id

positional arguments:
  id          an arXiv id or URL, or a DOI

options:
  -h, --help  show this help message and exit
  --key KEY   the citation key (default: FirstAuthorYY)
```

Looks the paper up online (arXiv, or Crossref for a DOI) and appends it to `content/references.yml`.

```bash
python -m bazinga cite 2010.11929 --key ViT
```

**What you should see:**

```text
ViT: Alexey Dosovitskiy et al. (2020). An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale
Cite it with [@ViT] (or [@ViT, p. 4]).
```

```bash
python -m bazinga cite 10.1038/nature14539
```

**What you should see:**

```text
LeCun15: Yann LeCun et al. (2015). Deep learning
Cite it with [@LeCun15] (or [@LeCun15, p. 4]).
```

If the paper is already in the file (same arXiv id or DOI), nothing is added and the existing key is printed. A
`--key` that is already used is refused.

## math

```text
usage: python -m bazinga math [-h] [--display] [--html FILE] tex

positional arguments:
  tex          the LaTeX, in quotes; "-" reads it from the input

options:
  -h, --help   show this help message and exit
  --display    as a displayed equation ($$ … $$), not inside a sentence
  --html FILE  write a preview page to FILE instead of printing
```

Checks one formula. When it is fine, it prints the MathML; when it is not, it shows where and what to write instead.

```bash
python -m bazinga math "\frac{a}{b"
```

**What you should see:**

```text
line 1, column 9: this { is never closed.
    \frac{a}{b
            ^
Instead: add the matching } where the group ends
```

```bash
python -m bazinga math --display "e^{i\pi} + 1 = 0" --html preview.html
```

**What you should see:**

```text
Wrote preview.html
```

Use single quotes in the shell when the formula holds `$` or `!`. This command needs no site, so it works anywhere.

## figure

```text
usage: python -m bazinga figure [-h] [--from STARTER]
                                {new,test,preview,list,starters} [name]

positional arguments:
  {new,test,preview,list,starters}
  name

options:
  -h, --help            show this help message and exit
  --from STARTER        a starter (slider_plot, scatter_fit, distribution, …)
                        or builder / builder:<type> for the form
```

| Action | What it does |
|---|---|
| `figure starters` | lists the examples you can copy |
| `figure new <name> --from <starter>` | copies an example to `figures/<name>.py` (or a drawing starter to `drawings/<name>.py`) |
| `figure new <name> --from builder:<type>` | the form's example of a kind, as a file |
| `figure test [name]` | tests one figure, or all of them |
| `figure preview <name>` | writes a page with the figure at every preset and prints where |
| `figure list` | every figure, how it was made, and where it is used |

`--from` defaults to `slider_plot`. The form's kinds are `function`, `shapes`, `bars`, `heatmap`,
`distribution`, `data` and `scene3d`.

```bash
python -m bazinga figure new my_plot --from slider_plot
```

**What you should see:**

```text
Created figures/my_plot.py. Use it in a post with ::figure my_plot
```

```bash
python -m bazinga figure test my_plot
```

**What you should see:**

```text
ok   my_plot  (83 ms for all states)
```

```bash
python -m bazinga figure preview my_plot
```

**What you should see:**

```text
/path/to/your-site/.studio/figure-preview/my_plot.html
```

```bash
python -m bazinga figure new x --from builder:nope
```

**What you should see:**

```text
error: no builder type 'nope'. Choose one of: function, shapes, bars, heatmap, distribution, data, scene3d (for example --from builder:function).
```

`figure preview` prints the full path on your computer. `figure test` exits with 1 when a figure fails, so the tests
and the build catch a broken figure. To use a copied drawing starter, place it with `::drawing <name>.<function>`;
for example the `pipeline` starter's function is `steps`, so `::drawing my_pipe.steps`. The command prints that line
for you: `Use it in a post with ::drawing my_pipe.steps`. The full starter list and the form are in
[Interactive figures](../figures.md) and [Diagrams](../diagrams.md).

## editor

`editor` and `studio` are the same command. Options after the command are passed to it:

```text
usage: bazinga editor [-h] [--port PORT] [--no-browser] [--root ROOT]

The Editor, the local writing window (127.0.0.1 only).

options:
  -h, --help    show this help message and exit
  --port PORT   port on 127.0.0.1 (default: a free one)
  --no-browser  do not open the browser
  --root ROOT   the site folder (default: the current folder)
```

```bash
python -m bazinga editor --port 8001 --no-browser
```

**What you should see:**

```text
Bazinga Editor for <your site folder>
  http://127.0.0.1:8001/?token=…
  Local only: this address works on this computer and nowhere else. Press Ctrl+C to stop.
```

The address holds a new key each time, so copy the whole line. You do not need this command while `serve` runs: the
**Write** button opens the same Editor. See [The Editor](../editor.md).

## publish

```text
usage: bazinga publish [-h] [--dry-run] [--unpublish] [--schedule YYYY-MM-DD]
                       [--yes]
                       file

positional arguments:
  file

options:
  -h, --help            show this help message and exit
  --dry-run
  --unpublish
  --schedule YYYY-MM-DD
  --yes                 accept warnings
```

The Editor's publish pipeline, from a terminal: check, set the status and date, test the page's figures, build,
update the wiki files, commit, push, and run `publish.command`.

- `--dry-run` works on a temporary copy of the site and only says what git would do.
- `--unpublish` turns the page back into a draft.
- `--schedule 2026-11-01` publishes it on a later date.
- `--yes` goes on despite warnings (errors always stop it).

```bash
python -m bazinga publish content/reads/my-first-post.md --dry-run --yes
```

**What you should see** (shortened: the lines of the changed header and the build command are left out):

```text
          Dry run: working on a temporary copy of the site; nothing in your folder will change.
[   done] Check the page - No problems
[   done] Set status and date - status: published, date: 2026-10-22
[skipped] Test its figures - This page has no figures
          …
          Built 15 pages (37 HTML files) into _site/ in 1.32s
[   done] Build the site
[   done] Update the wiki files - log: publish | My first post
[skipped] Suggested links and topics - None asked for
          Would stage: content/reads/my-first-post.md, content/references.yml, content/topics.yml, wiki/index.md, wiki/log.md
          Would run: git commit -m 'Publish: My first post' -- content/reads/my-first-post.md content/references.yml content/topics.yml wiki/index.md wiki/log.md
[   done] Commit - Dry run: not committed
          Would run: git push
[   done] Push - Dry run: not pushed
[skipped] Deploy command - No deploy command in site.yml
[   done] Live address - Live after your host finishes deploying

https://example.com/reads/my-first-post/
```

A real publish needs a git repository, and a name and email for the commit (`publish.author` in `site.yml`, or
`git config user.name` and `user.email`); without them it stops at the Commit step and says so. It pushes to the
branch your local branch is linked to. See [Publishing](../writing/publishing.md).

## wiki

```text
usage: python -m bazinga wiki <command>

  index                      rewrite wiki/index.md from the public pages (no model)
  query "<question>"         answer from the site's passages (no model)
  ingest <page>              propose topics, links, summary, description, questions for one page
  lint [--model]             fixed checks; with --model also look for contradictions
  highlights <series>        propose 3-4 highlights per part of a series
  describe <page>            propose a description of at most 155 characters
  equation "<words>"         LaTeX for an equation described in words
  figure "<description>"     draft a figure module from the closest starter
  log <op> "<subject>"       append an entry to wiki/log.md

<page> is an id (read:attention-from-scratch), a slug or a file path. Proposals go to proposals/; nothing in content/ changes.
```

| Sub-command | Needs a model |
|---|---|
| `index`, `query`, `lint` (without `--model`), `log` | no |
| `ingest`, `highlights`, `describe`, `equation`, `figure`, `lint --model` | yes |

```bash
python -m bazinga wiki index
```

**What you should see:**

```text
wiki/index.md: 14 pages, updated
```

```bash
python -m bazinga wiki log note "tried the commands"
tail -1 wiki/log.md
```

**What you should see:**

```text
## [2026-10-22] note | tried the commands
```

```bash
python -m bazinga wiki ingest read:welcome
```

**What you should see:**

```text
No model configured: set llm.model in site.yml and the key in the environment variable named by llm.key_env (or .env.local).
```

Real outputs of every sub-command, and how to set up a model, are in [Ask and the wiki](../ask-and-wiki.md).

## Passing options to editor, publish and wiki

For `editor`, `studio`, `publish` and `wiki`, everything after the command name is handed to it unchanged, so
these two lines are the same:

```bash
python -m bazinga editor --port 8001 --no-browser
python -m bazinga editor -- --port 8001 --no-browser
```

The `--` form, used in older notes, still works. The program's `--root` goes before the command name
(`python -m bazinga --root ../my-site editor`); `editor` also takes its own `--root` after its name.

## What's next

- Every setting in `site.yml`: [Configuration](configuration.md).
- Something went wrong: [Troubleshooting](../troubleshooting.md).
