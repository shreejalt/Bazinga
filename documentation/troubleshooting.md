# Troubleshooting and FAQ

Something did not work. This page lists the problems people meet most, with the message you see and the fix. The
messages are copied from real runs, so you can search this page for the words on your screen.

A rule that helps everywhere: Bazinga stops rather than publishing something broken, and it says where and what to
do. Read the line that starts with `hint:` or `Instead:` first.

## Installing

??? question "Which Python do I need?"
    Python 3.11 or newer. Check with `python3 --version` (on Windows: `py --version`). You don't need to install
    anything else (no Node.js).

??? question "`pip install -r requirements.txt` fails on numpy"
    numpy is only used by one example figure (`fourier_series`, which lists `REQUIRES = ["numpy"]`).
    `requirements.txt` picks a numpy that suits your Python (2.4.6 on Python 3.11, 2.5.4 on 3.12 and newer). If your
    Python is so new that numpy has no ready-made package for it yet, delete the numpy lines from
    `requirements.txt` and install again. The site still builds without numpy: a figure that needs it shows a short
    note in its place, and the build prints a warning such as
    `figure 'fourier_series': figure 'fourier_series' needs numpy, which is not installed here, …`. Readers' browsers
    load numpy by themselves, so the figure still works on the live site. The rest of Bazinga needs only Markdown,
    PyYAML, Jinja2, latex2mathml and Pygments.

??? question "`No module named bazinga` or `No module named yaml`"
    Run commands from your site folder (the one with `site.yml`), with the Python of your virtual environment:
    `python -m bazinga build`, or activate it first with `source .venv/bin/activate`. If your site is in another
    folder, stay in the folder that holds `bazinga/` and add `--root path/to/site` before the command.

## Building and checking

When the build finds a problem it writes nothing, so the last good `_site/` stays as it was. It prints every
problem at once:

```text
5 problem(s) stop the build:
content/reads/broken.md:5: error: unknown topic 'atention'
    hint: did you mean attention?
content/reads/broken.md:8: error: [@Nobody99] is not in content/references.yml
    hint: add it with: python -m bazinga cite <arxiv id or DOI>
content/reads/broken.md:8: error: [[read:nope]] is not a page of this site
    hint: did you mean read:broken?
content/reads/broken.md:8:6: error: maths: \frac needs two parts in braces.
    hint: write \frac{top}{bottom}
content/reads/broken.md:10: error: figure 'no_such_fig': there is no figure 'no_such_fig' (…). Known figures: …
    hint: fix the figure file, or run: python -m bazinga figure test no_such_fig

Nothing was written. Fix the problems above (each has a hint) and build again.
```

Each line starts with the file and line number. `python -m bazinga check content/reads/broken.md` shows the same
list for one page without building.

| Message | Fix |
|---|---|
| `unknown topic '…'` | use a topic from `content/topics.yml`, or add it there first |
| `[@Key] is not in content/references.yml` | add the paper: `python -m bazinga cite 1706.03762` (an arXiv id or a DOI) |
| `[[read:…]] is not a page of this site` | check the id: the kind's singular name, a colon, and the file name without `.md` |
| `maths: …` | follow the hint; test one formula with `python -m bazinga math "<latex>"` |
| `figure '…': there is no figure …` | the name after `::figure` must match a file `figures/<name>.py` |
| `site.yml: theme.accent must be a hex colour such as '#3b5bdb' (got 'blue')` | write colours as hex, in quotes: `"#0F52BA"` |
| `site.yml:N: not valid YAML: …` | look at line N: usually a missing space after `:`, or a tab |
| `…:N: 2026-02-30 is not a real date` | that day does not exist; write a real date as `YYYY-MM-DD`. It can be in a page, `site.yml`, `content/references.yml` or `content/cv.yml` |
| `date: '2026/01/05' is not a date (so this page would not be published)` | write dates as `YYYY-MM-DD` |
| `status 'publshed' is not draft or published (so this page would not be published)` | write `status: published` (or leave the line out), or `status: draft` |

??? question "A formula looks wrong or will not build"
    Check it on its own. The command shows where the problem is and what to write instead:

    ```bash
    python -m bazinga math 'x^10'
    ```

    **What you should see:**

    ```text
    line 1, column 2: ^10 raises only the 1; the rest stays on the line.
        x^10
         ^^^
    Instead: write ^{10}
    ```

    Writing equations is covered step by step in [Writing](writing/index.md).

??? question "My new post does not appear"
    A new post starts as a draft (`status: draft`). Drafts are never built into the site. Preview drafts with
    `python -m bazinga serve --drafts`. A post with a date in the future is scheduled: it appears on the first build
    on or after that date. `python -m bazinga build --drafts` includes drafts too; never deploy that build.

## Figures

??? question "`figure test` says FAIL"
    The test draws the figure at its start values, at every preset, and at 20 random settings, wide and phone-sized.
    Each line names the setting that broke it:

    ```text
    FAIL bad_plot
         bad_plot {"damping": 0.3, "freq": 2.0}: NaN or infinity at spec.panels[0].series[0].y[1] (use None for a gap in a line)
    ```

    Common causes: `nan` or an infinity in a curve (use `None` for a gap); `compute()` arguments that do not match
    the names in `CONTROLS`; a drawing that takes longer than 30 ms. [Interactive figures](figures.md) has the full
    list.

??? question "`figure '…' imports '…', which is not installed here`"
    The figure uses a package. Install it in your environment and list it in the figure's `REQUIRES`, for example
    `REQUIRES = ["numpy"]`, so the reader's browser loads it too.

??? question "The figure shows, but moving a slider does nothing for a second"
    The first move loads the code that redraws figures in the reader's browser; after that each change is quick.
    Without a network connection the figure keeps its first picture and does not redraw.

## Your portfolio

??? question "How do I change the photo?"
    Put a square picture (about 600 × 600 pixels) in `static/images/` and point `home.photo` at it in `site.yml`:
    `photo: /static/images/me.jpg`. The build does not check that the file exists, so a wrong name shows a broken
    picture: check the spelling and the folder. `photo: ""` removes the photo, and the role lines under it go too.
    The browser-tab icon is a separate setting, `site.avatar`:
    `avatar: static/images/me.jpg` (a leading `/` works too). See [Your portfolio](home-and-cv.md#the-top).

??? question "How do I hide the blog and keep only my portfolio?"
    Delete the example posts, keep only `projects:` under `kinds:`, trim `nav:` to Home, Projects and CV, and turn
    off `ask`, `explore`, `series` and `feed` under `features:`. In `content/cv.yml`, keep only the `tags:` that
    your projects use (or delete them), because a tag no page uses has no topic page. The steps are in
    [A portfolio without the blog](home-and-cv.md#a-portfolio-without-the-blog).

??? question "How do I offer my CV as a PDF?"
    Put the file under `static/`, for example `static/cv.pdf`, and set `cv: {pdf: /static/cv.pdf}` in `site.yml`.
    The CV button in the home page's rail then says **Download CV** and opens the file. The `/cv/` page itself has no
    download button; link the PDF from your About text if you want one there. See
    [A PDF copy](home-and-cv.md#a-pdf-copy).

??? question "The CV link opens Page not found"
    The `/cv/` page is built only when `content/cv.yml` exists. Add that file, or take CV out of `nav:` (or set
    `cv: {pdf: …}` so the home page's button opens your PDF). See [Configuration: cv](reference/configuration.md#cv).

??? question "How do I start from an empty site?"
    Follow [A portfolio without the blog](home-and-cv.md#a-portfolio-without-the-blog): it says which folders to
    delete (`content/reads`, `content/papers`, `content/elsewhere` and the example project) and what to change in
    `site.yml` and `content/cv.yml`. Add the `reads` kind back when you want to write posts. The tests still pass
    after you delete the example pages, so you can deploy as usual.

??? question "How do I add analytics?"
    Copy the page frame into your own theme and add your analytics script to it:

    ```bash
    mkdir -p theme/templates
    cp bazinga/theme/templates/base.html theme/templates/base.html
    ```

    Put the script tag your analytics service gives you inside `<head>` in `theme/templates/base.html`, then build.
    See [Your own copy of a theme file](theme.md#your-own-copy-of-a-theme-file).

??? question "How do I remove the \"Pick one\" buttons (Tea, Coffee, Water)?"
    Delete `starters_label` and `starters` under `home:` in `site.yml`. Nothing else needs to change.

??? question "How do I remove the \"Made with Bazinga\" link?"
    Add `credit: false` to `features:` in `site.yml`, for example
    `features: {ask: true, explore: true, series: true, feed: true, llms_txt: true, credit: false}`.

## The Editor and serve

??? question "`Port 8000 is in use`"
    Another program, or another copy of `serve`, uses the port. Stop it, or pick another port, as the message
    suggests: `python -m bazinga serve --port 8010`. The Editor then uses the next port; choose it yourself with
    `--editor-port 8021`.

    For the Editor on its own the message is `Cannot listen on 127.0.0.1:8000: [Errno 48] Address already in use`;
    use `python -m bazinga editor --port 9000`.

??? question "The Editor says \"Open the Editor with the link printed in the terminal.\""
    The Editor only opens with the private link it prints when it starts, such as
    `http://127.0.0.1:9000/?token=…`. A new link is made every time it starts. With `serve`, use the **Write** button
    on any page instead. An address other than `127.0.0.1` or `localhost`, such as your computer's network name, is
    refused on purpose: the Editor can change files and works only on your own computer.

??? question "There is no Write button"
    The Write button appears only on pages served by `python -m bazinga serve`, and not with `--no-editor`. A built
    site never has it.

??? question "The writing pane of the Editor stays empty"
    The Editor downloads its text editor from the internet (esm.sh) the first time you open it, so it needs a
    connection.

## Ask and the language model

| Message | What to do |
|---|---|
| `No model configured` | no model name, or no key found: set `llm.model`; put the key in `.env.local` under the name in `llm.key_env` |
| `running the fixed rules only` | `wiki lint --model` without a model; set one up as above (the fixed rules still ran) |
| `HTTP 401` | a wrong or expired key, or a key for another service: copy the key again; check `llm.base_url` |
| `HTTP 429` | the model is busy, or you hit a rate limit: wait a minute, or add a second model after a comma |
| `HTTP 404` | no model by that name at that service: copy the exact name from the service's list |
| `TimeoutError`, `URLError` | no reply within 60 seconds (25 for written answers), or no connection: try again, or a smaller model; check the address |
| `empty reply` | the model sent back nothing: use another model |
| `the reply was not JSON` | the model wrote its thinking instead of the reply: use a model that answers directly |
| `no public page` | the page id is wrong, or the page is a draft: use the id shown in `wiki/index.md`, or the file path |
| `no series` | the series name does not match: copy a name from the list it prints |
| No Written answer button | written answers are off: the server needs `llm.model` and a non-empty key variable; see [Ask and the wiki](ask-and-wiki.md#what-it-needs) |
| "That is all the written answers for today." | the visitor used their daily written answers: raise `ask.per_visitor`, or wait until tomorrow |
| "No written answer right now." | the model failed for this question: it is not counted against the limit; try again |

The model errors start with `error: every model failed (…: ` and the reason, such as `HTTP 429`.

??? question "Can a model on my laptop answer my readers?"
    No. The deployed site cannot reach your computer. A local model (Ollama, LM Studio) works for your own
    suggestions and for trying written answers with `serve`. See [Ask and the wiki](ask-and-wiki.md).

??? question "Is my key safe?"
    Keep it in `.env.local` (git never commits it) or in your host's environment settings. Never put it in
    `site.yml` or a post. Bazinga never prints it.

## Publishing and deploying

??? question "Publish stopped"
    Publish runs the checks, tests the page's figures, builds, commits and pushes, and stops at the first failure.
    A failure before the commit puts your page and the wiki files back as they were and leaves nothing staged in
    git. If only the push fails, the commit stays on your computer; push it yourself with `git push` once the problem
    is fixed. Try the whole run safely first: `python -m bazinga publish content/reads/my-post.md --dry-run`.

??? question "`Not committed: git does not know your name and email.`"
    The commit needs a name and an email, and git has none. Run these once in your site folder, then publish again:

    ```bash
    git config user.name "Your Name"
    git config user.email you@example.com
    ```

    Or set `publish.author: "Your Name <you@example.com>"` in `site.yml`. Your page and the wiki files were put back
    as they were, and nothing was staged.

??? question "`No such page: content/reads/…`"
    The path is wrong. Give the path from your site folder, as `content/<kind>/<file>.md`.

??? question "The deploy fails on the host but builds on my computer"
    Vercel, Netlify and the GitHub Pages workflow run the tests before they build
    (`python3 -m unittest discover tests`). A failing test stops the deploy and the old site stays up. Run the same
    command on your computer to see the failure. The tests do not use your pages (they build their own copy of the
    example site), so deleting the example pages does not make them fail.

??? question "GitHub Pages shows nothing, or a scheduled post did not go live"
    See [Deploying: when something goes wrong](deploying.md#when-something-goes-wrong).

??? question "The site has no styles, or its links lead to 404 pages"
    The build wrote links for another address. Check `site.origin` in `site.yml`: it must be the address the site
    really lives at. For a GitHub Pages project site that includes the folder, such as
    `https://you.github.io/notes`; the Pages workflow fills this in by itself. If you upload `_site/` under a folder
    by hand, build with `python -m bazinga build --origin https://your-host.example/folder`. See
    [A site under a path](reference/configuration.md#a-site-under-a-path).

??? question "Publish says `Committed, but there is no remote to push to.`"
    Your site folder is not connected to a repository yet. Your post is already committed, so do not publish again
    (that would add an `updated:` date). Add your repository and push the commit:

    ```bash
    git remote add origin https://github.com/<you>/<your-site>.git
    git push -u origin HEAD
    ```

    If the push itself fails, the message from git follows. The usual causes: you are not signed in to GitHub on
    this computer, or the branch is protected and only accepts pull requests. Your commit is safe; push it with
    `git push` once that is fixed.

See [Deploying](deploying.md) for each host.

## Still stuck?

Run `python -m bazinga check` and read the first error. If you think you found a bug, open an issue on
[GitHub](https://github.com/shreejalt/Bazinga/issues) with the command, the full message, and your Python version.
Never paste a key.

## What's next

Next, help improve Bazinga and these pages: [Contributing](contributing/index.md).

- [Commands reference](reference/commands.md): every command and option.
- [Configuration reference](reference/configuration.md): every setting in `site.yml`.
