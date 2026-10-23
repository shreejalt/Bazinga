# Contributing

Thank you for helping. This page shows how to set up a copy of Bazinga for work on the engine or on these docs, how
to run the tests, and how to preview and build the documentation. Everything here runs on your own computer.

## Set up

You need Python 3.11 or newer and git. Node.js is only needed to record the clips in these docs, and for the tests
that check the site's scripts (they are skipped without Node). The install is the same as in
[Getting started](../getting-started.md#2-install), from a clone of Bazinga itself:

```bash
git clone https://github.com/shreejalt/Bazinga.git
cd Bazinga
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

**What you should see:** pip prints `Successfully installed …` (a notice about a newer pip after it is fine).

## Run the tests

```bash
.venv/bin/python -m unittest discover tests
```

**What you should see:** dots, then `OK` on the last line. The same tests run before every deploy, on Vercel, Netlify
and GitHub Pages, so a failing test never reaches a live site.

Run one group while you work, for example the Editor's:

```bash
.venv/bin/python -m unittest discover tests -p "test_studio_*.py"
```

Some tests run `node --check` on the site's scripts when Node is installed; without Node they are skipped.

## Try your change on the example site

```bash
.venv/bin/python -m bazinga serve
```

**What you should see:** `Serving at http://127.0.0.1:8000/` among the lines it prints.

Open `http://127.0.0.1:8000`. The example site is the best test bed: it uses every feature, and the guides in
`content/reads/` show each one next to the text that makes it.

Before you send a change:

1. `.venv/bin/python -m unittest discover tests` passes.
2. `.venv/bin/python -m bazinga check` shows no errors.
3. You looked at the pages you touched, at a wide and at a phone width.

## Send your change

1. Fork [shreejalt/Bazinga](https://github.com/shreejalt/Bazinga) on GitHub and clone your fork.
2. Make a branch for the change:

    ```bash
    git switch -c my-change
    ```

3. Commit, push the branch to your fork, and open a pull request against `main`.
4. If users will notice the change, add a line to `CHANGELOG.md` under today's date, and a row to
   [Coverage](coverage.md) that points to the page documenting it.

Found a bug without a fix? Open an issue at <https://github.com/shreejalt/Bazinga/issues> with the command, the
message and your Python version.

## Where things live

| Folder | What it holds |
|---|---|
| `bazinga/` | the engine: build, Markdown, maths, figures, the map, Ask, the Editor (`bazinga/studio/`) |
| `bazinga/theme/` | the default templates, stylesheets and scripts |
| `content/`, `figures/`, `drawings/`, `static/` | the example site |
| `tests/` | the tests |
| `docs/` | notes for developers: the design (`DESIGN.md`) and build notes per part |
| `documentation/` | this user guide (MkDocs Material) |
| `mkdocs.yml` | the guide's settings and menu |

## Work on these docs

The guide is a separate MkDocs site. Its pages are Markdown files under `documentation/`, and the menu is the `nav:`
list in `mkdocs.yml`. Give it its own virtual environment so it never mixes with the site's:

```bash
python3 -m venv .venv-docs
.venv-docs/bin/pip install -r documentation/requirements.txt
```

Preview it while you write. The page reloads on save:

```bash
.venv-docs/bin/mkdocs serve -a 127.0.0.1:8030
```

**What you should see:** `Serving on http://127.0.0.1:8030/`. Open that address.

Build it the way the published site is built:

```bash
.venv-docs/bin/mkdocs build --strict
```

**What you should see:** `Documentation built in …` and no `WARNING` lines. `--strict` turns every warning into a
failure, such as a broken link or a clip that has not been recorded yet.

A few habits keep the pages consistent:

- Start each page with what the reader will do, and end with **What's next**.
- Give every step a command or snippet that can be copied as it is, then say what the reader should see.
- Show real output. Run the command on the example site and paste what it printed.
- Never document a flag or a setting you have not run.

### Clips

Short looping videos show the how-tos. A page places one with a line of its own:

```text
::clip build | Building and checking the example site from a terminal.
```

The clips are recorded by scripts in `documentation/recordings/`, so anyone can re-record them after the interface
changes. [Recording clips](recording-clips.md) explains the pipeline, and [The demo GIF](demo-gif.md) covers the
terminal demo.

### How the docs are published

`.github/workflows/docs.yml` builds the guide with `mkdocs build --strict` and publishes it on GitHub Pages. It runs
on a push to `main` that changes `mkdocs.yml`, `documentation/` or the workflow itself, and only in the
`shreejalt/Bazinga` repository. In your fork it does nothing; there, `pages.yml` publishes your own site instead
(see [Deploying](../deploying.md#github-pages)).

The guide's address is `bazinga.shreejal.ai`, set by the file `documentation/CNAME`, which MkDocs copies into the
built site. The **Edit this page** links point at `documentation/` on `main`, so they work once the guide is merged
there.

## What's next

- [Recording clips](recording-clips.md)
- [The demo GIF](demo-gif.md)
- [Commands reference](../reference/commands.md)
