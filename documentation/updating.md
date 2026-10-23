# Updating Bazinga

Bazinga keeps improving after you make your site from it. This page shows how to bring a newer version into your
site without losing your own pages and settings.

Your own files are `site.yml`, `content/`, `figures/`, `drawings/`, `static/` and `theme/`. An update is mostly about
the engine: `bazinga/`, its tests in `tests/` and the written-answer function in `api/`. Sometimes it also adds a
setting to `site.yml` or a section to an example page, and the changelog says when.

## Updating your site to a newer Bazinga

### Step 1: read what changed

Open `CHANGELOG.md` in Bazinga's repository, or [What's new](whats-new.md) in these docs. It lists the changes
newest first. Read every entry newer than your copy, and look for the words "you" and "your": those entries say what
you may need to do, such as a new setting in `site.yml` or a change for theme files you copied.

To see how old your copy is, look at the newest heading in your own `CHANGELOG.md`. If you have none, your copy is
from before 2026-10-23: compare with the date of your first commit:

```bash
git log --reverse --format=%as | head -1
```

### Step 2: add Bazinga as a second remote

Do this once, from your site's folder:

```bash
git remote add upstream https://github.com/shreejalt/Bazinga.git
```

Then, each time you update:

```bash
git fetch upstream
```

**What you should see:** the first time, `* [new branch] main -> upstream/main`; later, only the branches that
changed (or nothing). `git remote -v` shows both `origin` (your site) and `upstream` (Bazinga).

If you cloned Bazinga itself (as on the [Home](index.md#try-it) page), `origin` already is Bazinga: skip this step,
run `git fetch origin`, and in Step 3 use `git merge origin/main`.

### Step 3: bring the update in

How you made your site decides which way works.

=== "You forked Bazinga"

    Your history starts from Bazinga's, so git can merge the two:

    ```bash
    git merge upstream/main
    ```

    **What you should see:** `Merge made by the 'ort' strategy.` and a merge commit on top of your own.

    If you and Bazinga changed the same lines (often in `site.yml` or an example page), git stops and lists the
    files with conflicts. In each one:

    1. For your settings and pages, keep yours. Name the files git listed, for example:

        ```bash
        git checkout --ours -- site.yml content/reads/welcome.md
        ```

    2. For the engine, keep Bazinga's:

        ```bash
        git checkout --theirs -- bazinga/ tests/ api/
        ```

    3. Run `git add` with the same files, for example `git add site.yml content/ bazinga/ tests/ api/`.

    Then finish with `git commit`.

=== "You used “Use this template”"

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
- After the 3-D update (2026-10-22), `test_scene_figures` fails with
  `AssertionError: 4 not greater than or equal to 5`, because your copy lacks the new example figure. Take it from
  Bazinga, then run the tests again:

    ```bash
    git checkout upstream/main -- figures/tangent_plane.py
    ```

Then push. Your host deploys the updated site as usual.

!!! tip "Copied theme files do not update"
    A file you copied into `theme/` keeps your version. If an update changes the same file in `bazinga/theme/`,
    compare the two (`git diff --no-index theme/templates/base.html bazinga/theme/templates/base.html`) and carry
    over what you want. See [Theme and customising](theme.md#your-own-copy-of-a-theme-file).

## What's next

Next: what changed in each version, in [What's new](whats-new.md). Read it before you update.

- Something broke after an update: [Troubleshooting and FAQ](troubleshooting.md).
