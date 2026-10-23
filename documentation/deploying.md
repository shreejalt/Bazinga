# Deploying

In this guide you put your site online. Bazinga builds a folder of plain files, `_site/`, and any static host (a
service that serves files as they are) can serve it. Pick one host below and follow its steps. A portfolio and a
blog deploy the same way. Vercel, Netlify and GitHub Pages each have a step for your own domain.

| Host | What you set | Ask's written answers | Scheduled posts go live |
|---|---|---|---|
| [Vercel](#vercel) | the address in `site.yml`; a key, only if you want written answers | yes | with your next push, or a deploy hook you schedule |
| [Netlify](#netlify) | the address in `site.yml` | no (quick answers work) | with your next push, or a build hook you schedule |
| [GitHub Pages](#github-pages) | one setting in the repository | no (quick answers work) | by themselves, once a day (see [Scheduled posts](#scheduled-posts)) |
| [Anywhere else](#anywhere-else) | the address in `site.yml` | no (quick answers work) | when you build and upload again |

Quick answers on the Ask page run in the reader's browser, so they work on every host. Only the optional written
answers need a server, and only Vercel has one in this template. See [Ask and the wiki](ask-and-wiki.md).

## Before you deploy, on any host {#before-you-deploy}

### Step 1: set the site's address

Open `site.yml` and set `origin` to the address your site will have, with no `/` at the end:

```yaml
site:
  origin: "https://your-domain.example"
```

The build writes this address into the canonical link of every page (the address search engines should use), the
sitemap, the feed and the share cards. A wrong address does not stop the build, but search engines and link
previews will point to the wrong place.

!!! tip "Not sure of the address yet?"
    Deploy once with the host's free address (such as `https://my-site.vercel.app`), then set `origin` to it, or to
    your own domain later. On GitHub Pages you can skip this step: the workflow fills in the address by itself.

### Step 2: check everything

```bash
python -m bazinga check
python -m unittest discover tests
```

**What you should see:** `Checked 15 page(s): 0 error(s), 0 warning(s).` (your count will differ), and `OK` on the
last line of the tests. Every host runs the same tests before it builds. A failing test stops the deploy, and the
old site stays up.

!!! warning "The tests check the example pages"
    Some of the tests in `tests/` build the example site and look for its pages. Once you delete or rewrite the
    example pages, those tests fail (on a portfolio-only site, 16 of 453), and because every host runs the tests
    before it builds, the deploy stops. Until Bazinga's tests are fixed, take the tests out of the host's build: in
    `vercel.json` change `buildCommand` to `python3 -m bazinga build`; in `netlify.toml` remove
    `python3 -m unittest discover tests && ` from `command`; in `.github/workflows/pages.yml` delete the line
    `- run: python -m unittest discover tests`. The build itself still checks every page and stops on an error.

### Step 3: put your site on GitHub

Vercel and Netlify also work with GitLab and Bitbucket; GitHub Pages needs GitHub.

=== "You followed Getting started"

    Your folder is already a clone of your own copy on GitHub. Commit your changes and push them:

    ```bash
    git add -A
    git commit -m "My site"
    git push
    ```

    **What you should see:** git ends with a line such as `main -> main`.

=== "Your folder is not in git yet"

    Create an empty repository on GitHub, then from your site folder:

    ```bash
    git init -b main
    git add -A
    git commit -m "My site"
    git remote add origin https://github.com/<you>/<your-site>.git
    git push -u origin main
    ```

    **What you should see:** git uploads your files and ends with
    `branch 'main' set up to track 'origin/main'.`

### Step 4: not using GitHub Pages? Delete its workflow {#no-github-pages}

Your copy holds `.github/workflows/pages.yml`, which runs on every push and once a day. Without Pages turned on, it
fails at the `configure-pages` step and GitHub emails you each time. If you deploy on Vercel, Netlify or anywhere
else, delete it:

```bash
git rm .github/workflows/pages.yml
git commit -m "Deploy without GitHub Pages"
git push
```

**What you should see:** no new run under the **Actions** tab when you push.

## Vercel

### Step 1: import the repository

1. Sign in at vercel.com.
2. Choose **Add New → Project**.
3. Pick your repository and press **Import**.
4. Leave **Framework Preset** as **Other**. Change nothing else.
5. Press **Deploy**.

You set nothing else because `vercel.json` in your repository already says how to build (shortened):

```json
{
  "installCommand": "python3 -m pip install -r requirements.txt",
  "buildCommand": "python3 -m unittest discover tests && python3 -m bazinga build",
  "outputDirectory": "_site",
  "trailingSlash": true
}
```

It also declares `api/ask.py`, the small function behind written answers.

**What you should see:** a green build log, then your site at an address such as `https://my-site.vercel.app`.

From then on every push to `main` deploys by itself, and every other branch gets its own preview address. If a test
fails, that deploy stops and the last good site stays up; the build log shows which test failed.

### Step 2 (optional): turn on written answers {#written-answers-on-vercel}

Written answers need a model and its key. Set them in Vercel, never in a file you commit.

1. In `site.yml`, name a model under `llm:` (or skip this and set `LLM_MODEL` below):

    ```yaml
    llm:
      base_url: "https://openrouter.ai/api/v1"
      model: "openai/gpt-4o-mini"
    ```

2. In Vercel, open your project, then **Settings → Environment Variables**.
3. Add the key. Its name is whatever `llm.key_env` says in `site.yml`; the default is `LLM_API_KEY`. Tick
   **Production** (and **Preview** if you want written answers on preview links too).
4. Add any of these only if you need them:

    | Name | What it does |
    |---|---|
    | `LLM_MODEL` (or `ASK_MODEL`) | the model, instead of `llm.model` |
    | `LLM_BASE_URL` | the API address, instead of `llm.base_url` |
    | `ASK_PER_VISITOR` | written answers per visitor per day (default 5, from `ask.per_visitor`) |
    | `ASK_DAILY_CAP` | written answers per day for the whole site (default 300, from `ask.daily_cap`) |
    | `ASK_WRITTEN` | `off` turns written answers off without removing the key |
    | `SITE_URL` | your site's public address; only needed when the function cannot find the passages. The build also uses it in place of `site.origin`, so set it to the address you want search engines to show (your own domain, not `vercel.app`) |

5. Go to **Deployments**, open the latest one and choose **Redeploy**, so the new variables take effect.

**What you should see:** on your site's Ask page, a **Written answer** button next to the quick answer. Opening
`https://<your-site>/api/ask/` shows `{"on": true, ...}`. Without a key it shows `{"on": false}` and the button
stays hidden.

Every name above is read by `bazinga/ask_server.py` (and `SITE_URL` by `api/ask.py`); the full list is in the
[configuration reference](reference/configuration.md#environment-variables).

### Step 3 (optional): your own domain {#vercel-domain}

1. In the project, open **Settings → Domains** and add your domain. Vercel shows the DNS records (entries at your
   domain registrar that point the domain at the host) to create at your registrar.
2. Set `site.origin` in `site.yml` to the new address and push.

**What you should see:** the site at your domain, and its pages' canonical links using it.


## Netlify

### Step 1: import the repository

1. Sign in at netlify.com.
2. Choose **Add new site → Import an existing project**.
3. Pick your Git provider and your repository.
4. Leave the build settings as they are and press **Deploy**.

`netlify.toml` in your repository sets the build, and Python 3.12:

```toml
[build]
  command = "python3 -m pip install -r requirements.txt && python3 -m unittest discover tests && python3 -m bazinga build"
  publish = "_site"

[build.environment]
  PYTHON_VERSION = "3.12"
```

**What you should see:** a green deploy, then your site at an address such as `https://my-site.netlify.app`. Every
push to `main` deploys again.

### Written answers on Netlify

They are not available. This template's Netlify setup serves files only and has no function for `/api/ask/`, so
the **Written answer** button never appears. Quick answers work as usual. If you want written answers, use Vercel.

### Step 2 (optional): your own domain {#netlify-domain}

1. In the site, open **Domain management** and add your domain, then follow Netlify's DNS steps.
2. Set `site.origin` in `site.yml` to the new address and push.

**What you should see:** the site at your domain, and its pages' canonical links using it.


## GitHub Pages

### Step 1: turn Pages on

1. Open your repository on GitHub.
2. Go to **Settings → Pages**.
3. Under **Build and deployment**, set **Source** to **GitHub Actions**.

**What you should see:** the page says your site is built by a GitHub Actions workflow. In a fork, also open the
**Actions** tab once and turn workflows on: GitHub does not run a fork's workflows until you do.

### Step 2: push

Push to `main` (or, in the **Actions** tab, open **Deploy to GitHub Pages** and press **Run workflow**).

The workflow `.github/workflows/pages.yml` installs the requirements, runs the tests, builds, and publishes `_site/`.

**What you should see:** under **Actions**, a run called "Deploy to GitHub Pages" with two green jobs, `build` and
`deploy`. The `deploy` job shows the site's address.

The workflow runs:

- on every push to `main`;
- once a day at 06:15 UTC, so scheduled posts go live on their date;
- by hand, from the **Actions** tab.

If your main branch has another name, change `branches: [main]` in the workflow.

### The address is filled in for you

A repository named `<you>.github.io` is served at `https://<you>.github.io/`. Any other repository is a *project
site*, served under a folder: `https://<you>.github.io/<repository>/`. Both work.

Before building, the workflow asks GitHub for the site's real address (with `actions/configure-pages`) and hands it
to the build as `BAZINGA_ORIGIN`. That address replaces `site.origin` for this build only. When it has a folder,
every link, style, data file and figure is written under that folder. You do not need to edit `site.yml` for
GitHub Pages; the setting only matters for the build on your own computer.

**What you should see** in the built pages of a project site called `notes`: links such as `/notes/reads/welcome/`
and a canonical address such as `https://<you>.github.io/notes/reads/welcome/`.

### Your own domain {#github-pages-domain}

In **Settings → Pages**, enter it under **Custom domain** and follow GitHub's DNS steps. The next run of the workflow
builds for the new address by itself.

**What you should see:** after the next run, the site at your domain, and a green tick next to the domain in
**Settings → Pages**.

!!! note "Private repositories"
    On a free GitHub account, Pages works for public repositories only. Publishing from a private repository needs a
    paid plan.

!!! info "In the Bazinga repository itself"
    The jobs in `pages.yml` carry `if: github.repository != 'shreejalt/Bazinga'`. In the Bazinga repository they
    are skipped, because its Pages site is this documentation (built by `.github/workflows/docs.yml`). In your own
    copy or fork the condition is true, so `pages.yml` publishes your site.

## Anywhere else

1. Build:

    ```bash
    python -m bazinga build
    ```

    **What you should see:** `Built 14 pages (36 HTML files) into _site/ in 0.83s` (your numbers will differ).

2. Upload everything inside `_site/` to your host's web root.

    **What you should see:** your home page at the host's address.

3. If the host asks for a not-found page, point it at `404.html`.

Pages are folders with an `index.html` (`/reads/welcome/index.html`), so the host must serve `index.html` for a
folder address. Almost every static host does.

If the site will live in a folder of the host (`https://host.example/notes/`), build for that address:

```bash
python -m bazinga build --origin https://host.example/notes
```

Never deploy a `--drafts` build. It holds your drafts and tells search engines to stay away.

## Scheduled posts

A post with `status: published` and a date in the future is scheduled. Every build leaves it out until its date, and
the first build on or after that date includes it. Bazinga has no timer of its own:

- **GitHub Pages:** the workflow's daily run (06:15 UTC) takes care of it. GitHub pauses that daily run when the
  repository has had no commits for 60 days. If a scheduled post did not appear, open **Actions → Deploy to GitHub
  Pages** and press **Enable workflow**.
- **Vercel and Netlify:** a build happens when you push, so the post appears with your next push on or after its
  date. To publish it on the day without pushing, create a deploy hook (Vercel) or build hook (Netlify), a secret address that starts a build when called, in the
  host's settings and call it from any scheduler you like; the template does not set one up.

## How Publish fits in {#publishing-from-the-editor}

The Editor's **Publish** (and `python -m bazinga publish`) checks the page, builds, commits and pushes. The push is
what starts the deploy on Vercel, Netlify or GitHub Pages; Bazinga never talks to the host itself. Where it pushes,
whose name the commit carries and what to do when a push fails are in [Publishing](writing/publishing.md).

## When something goes wrong

| What you see | Why | What to do |
|---|---|---|
| The site has no styles, or links lead to 404 pages | the build used the wrong address or folder | set `site.origin` to the real address; for a folder by hand, build with `--origin` ([details](reference/configuration.md#a-site-under-a-path)) |
| Search results or link previews point to `example.com` | `site.origin` was never changed | set it and push |
| No **Written answer** button | no key in the host's settings, or the host is not Vercel | add the key under Environment Variables and redeploy |
| The deploy fails on the host | a test failed (the old site stays up) | read the host's build log, run `python -m unittest discover tests` on your computer, fix, push |
| The Deploy to GitHub Pages run fails at the `configure-pages` step, or the site shows nothing | Pages is not set to GitHub Actions | Settings → Pages → Source: **GitHub Actions** |
| A failed Deploy to GitHub Pages run on every push, though you use Vercel or Netlify | `pages.yml` still runs | delete it ([Before you deploy, step 4](#no-github-pages)) |
| A scheduled post is not live | the host has not built since its date | GitHub Pages builds daily by itself (unless the daily run was paused: **Enable workflow** in Actions); on Vercel or Netlify push again, or call a deploy hook on a schedule (the template does not set one up for you) |

More answers are in [Troubleshooting](troubleshooting.md#publishing-and-deploying).

## What's next

- Make the site easy to find: [SEO and feeds](seo-and-feeds.md).
- Set up written answers: [Ask and the wiki](ask-and-wiki.md).
- Keep your site up to date with Bazinga: [Updating Bazinga](updating.md).
