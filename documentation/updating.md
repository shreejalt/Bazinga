# Updating Bazinga

Bazinga keeps improving after you make your site from it. This page shows how to bring a newer version into your
site without losing your own pages and settings, and how to let an AI coding agent help you with the site.

Your writing lives in files Bazinga never changes: `site.yml`, `content/`, `figures/`, `drawings/`, `static/` and
your own `theme/` folder. The engine lives in `bazinga/`, with its tests in `tests/` and the written-answer function
in `api/`. An update is about those engine folders.

## Step 1: add Bazinga as a second remote

Do this once, from your site's folder:

```bash
git remote add upstream https://github.com/shreejalt/Bazinga.git
git fetch upstream
```

What you should see: `git fetch` lists the branches of `upstream`, and `git remote -v` now shows both `origin`
(your site) and `upstream` (Bazinga).

## Step 2: bring the update in

How you made your site decides which way works.

=== "You forked or cloned Bazinga"

    Your history starts from Bazinga's, so git can merge the two:

    ```bash
    git fetch upstream
    git merge upstream/main
    ```

    What you should see: `Merge made by the 'ort' strategy.` and a merge commit on top of your own. If you and
    Bazinga changed the same lines (often in `site.yml` or an example page), git stops and marks the conflict in
    those files. Keep your version of your settings and pages, keep Bazinga's version of everything under
    `bazinga/`, then `git add` the files and `git commit`.

=== "You used \"Use this template\""

    A copy made with GitHub's **Use this template** starts a fresh history, so a plain merge is refused:

    ```text
    fatal: refusing to merge unrelated histories
    ```

    Take only the engine folders from Bazinga instead. Your settings and pages are not touched:

    ```bash
    git fetch upstream
    git checkout upstream/main -- bazinga tests api requirements.txt
    git commit -m "Update Bazinga's engine"
    ```

    What you should see: `git status` before the commit lists only files under `bazinga/`, `tests/`, `api/` and
    `requirements.txt`. A file Bazinga deleted stays in your copy; `git diff --stat HEAD upstream/main -- bazinga`
    shows what still differs.

These commands were tried on two test copies of a site, one cloned and one made as a fresh history, each with its own
changes to `site.yml` and a page of its own.

## Step 3: check that everything still works

```bash
python -m pip install -r requirements.txt
python -m unittest discover tests
python -m bazinga build
```

What you should see: the tests end with `OK`, and the build prints `Built … pages`. If the build stops, its message
names the file and line and says what to write instead; see [Troubleshooting](troubleshooting.md).

!!! tip "Copied theme files do not update"
    A file you copied into `theme/` keeps your version. If an update changes the same file in `bazinga/theme/`,
    compare the two (`git diff --no-index theme/templates/base.html bazinga/theme/templates/base.html`) and carry
    over what you want. See [Theme and customising](theme.md#your-own-copy-of-a-theme-file).

## Working with AI coding agents {#working-with-ai-coding-agents}

`AGENTS.md`, at the root of the site, is written for coding agents such as Claude Code, Codex or Cursor, and for
you. It explains how the site works as a wiki, in the sense of Karpathy's "LLM Wiki" idea:

- **Three layers.** `sources/` (optional, git-ignored: the papers and notes you collect), the wiki itself
  (`content/`), and the rules (`AGENTS.md` and `docs/DESIGN.md`).
- **What is generated.** `wiki/index.md`, the catalog an agent reads first, and `wiki/log.md`, the log of what
  happened. Neither is edited by hand.
- **The exact commands** for asking (`wiki query`), connecting a new page (`check`, then `wiki ingest`), keeping the
  wiki healthy (`wiki lint`) and the other proposals. They are described in [Ask and the wiki](ask-and-wiki.md).
- **The rules.** Cite everything; a model only writes proposals to `proposals/`, and nothing reaches `content/`
  unless you accept it.

When you ask an agent to work on your site, point it at `AGENTS.md` first. Edit the file when your own rules
change, for example the topics you allow or how you like pages written.

## What's next

- See every part of Bazinga in one place: [What's in Bazinga](whats-in-bazinga.md).
- Something broke after an update: [Troubleshooting and FAQ](troubleshooting.md).
