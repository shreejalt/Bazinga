# 9. Publishing

On this page you turn your draft into a live page. One command (or one button in the Editor) checks the post, builds
the site, records it in the wiki log, commits the post with git and pushes it. Your host then puts it online. It works
the same for any page: a post, a paper or a project page (`content/projects/`).

Publishing works only on your own computer. Nothing in the built site can publish or change anything.

!!! note "Before you start"
    Your site's folder must be a git repository with a remote your host deploys from (GitHub, for example). If you
    have not set that up yet, see [Deploying](../deploying.md) first. To publish without git, see
    [Without git](#without-git) below.

    Git also needs your name and email for the commit. Check with `git config user.email`. If it prints nothing,
    run these once in your site's folder (or set `publish.author`, below):

    ```bash
    git config user.name "Your Name"
    git config user.email you@example.com
    ```

## Step 1: try it without changing anything

Do a dry run first. It runs every step in a temporary copy of your site and only reports the git commands:

```bash
python -m bazinga publish content/reads/my-first-post.md --dry-run
```

**What you should see:**

```text
          Dry run: working on a temporary copy of the site; nothing in your folder will change.
[   done] Check the page - No problems
          @@ -4 +4 @@
          -status: draft
          +status: published
[   done] Set status and date - status: published, date: 2026-10-22
[skipped] Test its figures - This page has no figures
          $ <your site folder>/.venv/bin/python -m bazinga build
          Built 15 pages (37 HTML files) into _site/ in 0.89s
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

Your file, your git history and your remote are exactly as they were.

::clip publish-dry-run | A dry run of publish in the terminal: every step runs on a copy, and git is only reported.

## Step 2: publish

Run the same command without `--dry-run`:

```bash
python -m bazinga publish content/reads/my-first-post.md
```

**What you should see:** the same steps, this time for real:

```text
[   done] Check the page - No problems
          @@ -4 +4 @@
          -status: draft
          +status: published
[   done] Set status and date - status: published, date: 2026-10-23
[skipped] Test its figures - This page has no figures
          $ <your site folder>/.venv/bin/python -m bazinga build
          Built 15 pages (37 HTML files) into _site/ in 0.97s
[   done] Build the site
[   done] Update the wiki files - log: publish | My first post
[skipped] Suggested links and topics - None asked for
          staged content/reads/my-first-post.md
          staged wiki/index.md
          staged wiki/log.md
          $ git commit -m 'Publish: My first post' -- content/reads/my-first-post.md content/references.yml content/topics.yml wiki/index.md wiki/log.md
          [main 4b61e62] Publish: My first post
           3 files changed, 37 insertions(+), 1 deletion(-)
           create mode 100644 content/reads/my-first-post.md
           create mode 100644 wiki/log.md
[   done] Commit - 4b61e62 Publish: My first post
          $ git push origin HEAD:main
          To <your remote>
             c2d3af4..4b61e62  HEAD -> main
[   done] Push
[skipped] Deploy command - No deploy command in site.yml
[   done] Live address - Live after your host finishes deploying

https://example.com/reads/my-first-post/
```

What happened, step by step:

1. **Check the page.** Errors stop here. Warnings stop here too, unless you add `--yes` to accept them.
2. **Set status and date.** `status: published`, and `date` becomes today. Publishing a page that was already
   published keeps its date and sets `updated:` instead.
3. **Test its figures.** Every figure the page uses is tested at all its settings. A failing figure stops here.
4. **Build the site,** exactly like `python -m bazinga build`.
5. **Update the wiki files.** `wiki/index.md` is rewritten and `wiki/log.md` gets the line
   `## [2026-10-23] publish | My first post`.
6. **Suggested links and topics.** Only in the Editor, when you asked a model for suggestions and accepted some.
7. **Commit.** Only the page and the files that belong to it are committed: its figures, drawings and uploaded
   images, `content/references.yml`, `content/topics.yml` and the two wiki files. Other changes in your folder are
   left alone.
8. **Push** the commit to GitHub, to the branch your local branch is linked to (usually `main`;
   `git push origin HEAD:main` above), then run the optional deploy command from
   `site.yml`. If your branch tracks none yet, it runs `git push -u origin HEAD`.
9. **Live address.** Your host builds the site from the push. The page is live when it finishes.

If a step fails before the commit, nothing is left behind: your page, `wiki/index.md` and `wiki/log.md` are put back
as they were, and any file Publish staged in git is unstaged again. If only the push fails, the commit stays and the
message says so; push again when you can.

Publish checks who commits before it stages anything. If git does not know your name and email, it stops at the
commit:

```text
[ failed] Commit - Not committed: git does not know your name and email.
          Set publish.author in site.yml ("Your Name <you@example.com>") or run `git config user.name "Your Name"` and `git config user.email you@example.com`.
          Restored content/reads/my-first-post.md and the wiki files to how they were before publishing.
```

Do what it says, then publish again. The commits are always yours: Bazinga never makes up a name.

## Step 3: or press Publish in the Editor

In the Editor, **Publish** opens a dialog that runs the same steps with a live list and log. It has a dry run, shows
warnings with a **Publish anyway** box to tick, and offers **Schedule** and **Unpublish**. See
[The Editor](../editor.md#publish), which also has a clip of it.

The **Write** button that opens the Editor is never part of the published site: readers of the live site do not see
it. [Only you see the Write button](../editor.md#only-you-see-the-write-button) explains why.

## Schedule a post for later

Give a future date with `--schedule`:

```bash
python -m bazinga publish content/reads/my-first-post.md --schedule 2026-11-01
```

The page gets `status: published` and that date, and the commit says `Schedule: My first post (2026-11-01)`. A page
with a future date is left out of every build until that day; the first build on or after it puts it online. So your
host must build at least once a day. The GitHub Pages workflow that comes with the template builds every morning; see
[Deploying](../deploying.md) for other hosts.

**What you should see** at the end:

```text
[   done] Live address - Goes live on 2026-11-01, on the first build that day
```

A date that is not in the future stops with: `A scheduled day must be in the future; use Publish to publish today.`

## Take a post down

`--unpublish` turns a page back into a draft, builds, commits `Unpublish: <title>` and pushes:

```bash
python -m bazinga publish content/reads/my-first-post.md --unpublish
```

**What you should see** at the end:

```text
[   done] Live address - The page is a draft again; it leaves the site on the next deploy
```

If other published pages link to the page or build on it, the build fails and nothing is committed, because those
pages would then point at a draft. Remove those links first.

## When the push fails

Your commit stays on your computer, so nothing is lost. Private repositories work like public ones: the push uses the
git sign-in you already have. The usual causes of a failed push:

- **No remote:** Publish says `Committed, but there is no remote to push to.` Your post is already committed, so do
  not publish again (that would add an `updated:` date and a second commit), even though the message says so. Add the
  remote and push the commit:

    ```bash
    git remote add origin <url>
    git push -u origin HEAD
    ```
- **Not signed in:** sign in to GitHub on this computer (for example with `gh auth login`), then run `git push`.
- **A protected branch** that only accepts pull requests: push to another branch and open a pull request.

## Choose what publish does

The `publish:` section of `site.yml` controls the last steps:

```yaml
publish:
  commit: true                          # git add the page and its files, then commit
  push: true                            # git push (Vercel, Netlify or GitHub Pages deploy from the repository)
  command: ""                           # optional extra step, e.g. "vercel deploy --prod --yes"
  author: ""                            # optional "Name <email>" for commits (default: your git config)
```

Every key, with its default, is in [Configuration](../reference/configuration.md#publish).

### Without git

Set `commit: false` and `push: false`. Publish then checks the page, sets its status and date, tests its figures,
builds `_site/` and updates the wiki files. Upload `_site/` to your host yourself, or put your upload command in
`command:`. See [Deploying](../deploying.md).

## What's next

That is the whole path, from a new file to a live page. Next, write in a window with a live preview:
[The Editor](../editor.md). From there:

- Make your own figures: [Interactive figures](../figures.md).
- Make it your portfolio: [home page, CV and projects](../home-and-cv.md).
- Put the site online, if you have not yet: [Deploying](../deploying.md).
