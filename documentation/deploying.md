# Deploying

In this guide you will put your site online. Bazinga builds a plain folder of files, `_site/`, so any static host
can serve it. The repository already carries the settings for three hosts:

| Host | File in the repository | Ask's written answers |
|---|---|---|
| Vercel | `vercel.json` and `api/ask.py` | yes, with a key set in the project |
| Netlify | `netlify.toml` | no (quick answers still work) |
| GitHub Pages | `.github/workflows/pages.yml` | no (quick answers still work) |
| Anywhere else | none: upload `_site/` | no |

Every host runs the tests before it builds. A failing test stops the deploy, so the old site stays up.

Quick answers on the Ask page run in the reader's browser, so they work on every host. Only the optional written
answers need a server; see [Ask and the wiki](ask-and-wiki.md).

## Before you deploy

1. Set your address in `site.yml`, with no `/` at the end:

    ```yaml
    site:
      origin: "https://your-domain.example"
    ```

    Canonical links, the sitemap and the feed are built from it.

2. Check everything:

    ```bash
    python -m bazinga check
    python -m unittest discover tests
    ```

    **What you should see:** `Checked 15 page(s): 0 error(s), 0 warning(s).` and, from the tests, `OK` on the last line.

3. Push your repository to GitHub (or GitLab, or Bitbucket, for Vercel and Netlify).

## Vercel

1. In Vercel, choose **Add New → Project** and import your repository.
2. Leave the framework as **Other**. `vercel.json` already sets everything:

    ```json
    {
      "installCommand": "python3 -m pip install -r requirements.txt",
      "buildCommand": "python3 -m unittest discover tests && python3 -m bazinga build",
      "outputDirectory": "_site",
      "trailingSlash": true
    }
    ```

3. Deploy. **What you should see:** a green build and your site at the address Vercel gives you.

From then on, every push to your main branch deploys, and other branches get preview links.

### Written answers on Vercel

`api/ask.py` is a small function that answers at `/api/ask/`. It turns on when a model and a key are set:

1. In `site.yml`, name a model under `llm:` (or set `LLM_MODEL` in the project instead).
2. In the Vercel project, under **Settings → Environment Variables**, add the key under the name in
   `llm.key_env`. The default name is `LLM_API_KEY`.
3. Deploy again.

The key lives only in Vercel's settings. Never put it in `site.yml` or in a committed file. If the function cannot
fetch the site's passages from the request's own address, set `SITE_URL` to your site's address as well. The limits
(`ask.per_visitor`, `ask.daily_cap`) can be changed with `ASK_PER_VISITOR` and `ASK_DAILY_CAP`. The
[configuration reference](reference/configuration.md#environment-variables) lists every variable.

## Netlify

1. In Netlify, choose **Add new site → Import an existing project** and pick your repository.
2. `netlify.toml` sets the build:

    ```toml
    [build]
      command = "python3 -m pip install -r requirements.txt && python3 -m unittest discover tests && python3 -m bazinga build"
      publish = "_site"

    [build.environment]
      PYTHON_VERSION = "3.12"
    ```

3. Deploy. **What you should see:** your site at the Netlify address.

This setup is static only, so the written-answer button does not appear.

## GitHub Pages

1. Push your copy of the template to GitHub.
2. In the repository, open **Settings → Pages** and set **Source** to **GitHub Actions**.
3. Push to `main`. The workflow `.github/workflows/pages.yml` installs the requirements, runs the tests, builds,
   and publishes `_site/`.

**What you should see:** under the **Actions** tab, a run called "Deploy to GitHub Pages" with two green jobs,
`build` and `deploy`. The deploy job shows the site's address.

The workflow runs:

- on every push to `main`;
- once a day at 06:15 UTC, so scheduled posts go live on their date;
- by hand, from the Actions tab (**Run workflow**).

If your default branch is not `main`, change `branches: [main]` in the workflow.

!!! warning "Use a user site or your own domain"
    Every link Bazinga writes starts at the root of the address (`/reads/...`, `/assets/...`). A project site on
    GitHub Pages lives under a folder, `https://<you>.github.io/<repository>/`, and those links would miss it.
    Use a repository named `<you>.github.io`, or set a custom domain under **Settings → Pages**.

!!! info "In the Bazinga repository itself"
    The jobs in `pages.yml` carry `if: github.repository != 'shreejalt/Bazinga'`. In the Bazinga repository they
    are skipped, because its GitHub Pages site is this documentation (built by `.github/workflows/docs.yml`). In
    your own copy or fork the condition is true, so `pages.yml` publishes your site.

## Anywhere else

Build, then upload the folder:

```bash
python -m bazinga build
```

**What you should see:** `Built 14 pages (36 HTML files) into _site/ in 0.83s` (your numbers will differ).

Upload everything inside `_site/` to your host's web root. Pages are folders with an `index.html`
(`/reads/welcome/index.html`), so the host must serve `index.html` for a folder address. Almost every static host
does.

Never deploy a `--drafts` build. It holds your drafts and tells search engines to stay away.

## Scheduled posts

A post with `status: published` and a date in the future is scheduled. It is left out of every build until its date
has come, and appears on the first build after that. Bazinga has no timer of its own:

- on GitHub Pages, the daily run of `pages.yml` takes care of it;
- on Vercel and Netlify, a build happens when you push, so a scheduled post appears with your next push on or after
  its date, unless you trigger a daily build yourself (both hosts offer deploy hooks you can call on a schedule).

## Publishing from the Editor

The Editor's **Publish** (and `python -m bazinga publish`) checks the page, builds, commits and pushes. The push is
what starts the deploy on Vercel, Netlify or GitHub Pages.

::clip editor-publish | Publish in the Editor, as a dry run: the same steps, on a copy of the site.

The `publish:` keys in `site.yml` choose whether it commits and pushes, and can add one more command after the push,
such as `"vercel deploy --prod --yes"`. That command runs without a shell, so it cannot chain commands with `;` or
`&&`. The whole pipeline is in [Publishing](writing/publishing.md), and the keys in
[Configuration](reference/configuration.md#publish).

## What's next

- Make the site easy to find: [SEO and feeds](seo-and-feeds.md).
- Set up written answers: [Ask and the wiki](ask-and-wiki.md).
- Something failed? [Troubleshooting](troubleshooting.md).
