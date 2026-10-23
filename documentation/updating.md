# Updating Bazinga

Bazinga keeps improving after you make your site from it. This page shows how to bring a newer version into your
site without losing your own pages and settings.

Your writing lives in files Bazinga never changes: `site.yml`, `content/`, `figures/`, `drawings/`, `static/` and
your own `theme/` folder. The engine lives in `bazinga/`, with its tests in `tests/` and the written-answer function
in `api/`. An update is about those engine folders.

## Updating your site to a newer Bazinga

### Step 1: read what changed

Open `CHANGELOG.md` in Bazinga's repository, or [What's new](whats-new.md) in these docs. It lists the changes
newest first. Read every entry newer than your copy, and look for the words "you" and "your": those entries say what
you may need to do, such as a new setting in `site.yml` or a change for theme files you copied.

### Step 2: add Bazinga as a second remote

Do this once, from your site's folder:

```bash
git remote add upstream https://github.com/shreejalt/Bazinga.git
```

Then, each time you update:

```bash
git fetch upstream
```

**What you should see:** `git fetch` lists Bazinga's branches, and `git remote -v` shows both `origin` (your site)
and `upstream` (Bazinga).

### Step 3: bring the update in

How you made your site decides which way works.

=== "You forked or cloned Bazinga"

    Your history starts from Bazinga's, so git can merge the two:

    ```bash
    git merge upstream/main
    ```

    **What you should see:** `Merge made by the 'ort' strategy.` and a merge commit on top of your own.

    If you and Bazinga changed the same lines (often in `site.yml` or an example page), git stops and lists the
    files with conflicts. In each one:

    1. Keep your version of your settings and your pages (`site.yml`, `content/`, `figures/`, `static/`).
    2. Keep Bazinga's version of everything under `bazinga/`, `tests/` and `api/`.
    3. Run `git add <file>`.

    Then finish with `git commit`.

=== "You used \"Use this template\""

    A copy made with GitHub's **Use this template** starts a fresh history, so a plain merge is refused:

    ```text
    fatal: refusing to merge unrelated histories
    ```

    (`git merge --allow-unrelated-histories upstream/main` gets past that message, but then nearly every file
    conflicts: 44 of them in our test. It is not worth it.)

    Take the engine folders from Bazinga instead. Your settings and pages are not touched:

    ```bash
    git checkout upstream/main -- bazinga tests api requirements.txt
    ```

    If you never changed them, take the host files and the notes too, so new deploy settings reach you:

    ```bash
    git checkout upstream/main -- .github/workflows/pages.yml vercel.json netlify.toml AGENTS.md CLAUDE.md CHANGELOG.md
    ```

    **What you should see:** `git status` lists only the files you named. Then commit:

    ```bash
    git commit -m "Update Bazinga"
    ```

    A file Bazinga deleted stays in your copy; `git diff --stat HEAD upstream/main -- bazinga` shows what still
    differs.

### Step 4: check that everything still works

```bash
python -m pip install -r requirements.txt
python -m unittest discover tests
python -m bazinga build
```

**What you should see:** the tests end with `OK`, and the build prints `Built … pages`.

- If the build stops, its message names the file and line and says what to write instead; see
  [Troubleshooting](troubleshooting.md).
- A few tests check the example site. If one fails and names an example file Bazinga added (after the 3-D update it
  was `figures/tangent_plane.py`), take that file too, for example
  `git checkout upstream/main -- figures/tangent_plane.py`, or delete the matching example page yourself.

Then push. Your host deploys the updated site as usual.

These steps were tried on two test copies of a site, one cloned and one made as a fresh history, each with its own
changes to `site.yml`, updating from an older copy (before 3-D figures) to the 2026-10-23 version.

!!! tip "Copied theme files do not update"
    A file you copied into `theme/` keeps your version. If an update changes the same file in `bazinga/theme/`,
    compare the two (`git diff --no-index theme/templates/base.html bazinga/theme/templates/base.html`) and carry
    over what you want. See [Theme and customising](theme.md#your-own-copy-of-a-theme-file).

## What's next

Next: what changed in each version, in [What's new](whats-new.md). Read it before you update.

- Something broke after an update: [Troubleshooting and FAQ](troubleshooting.md).
