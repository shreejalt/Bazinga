# Troubleshooting and FAQ

Something did not work. This page lists the problems people meet most, with the message you see and the fix. The
messages are copied from real runs, so you can search this page for the words on your screen.

A rule that helps everywhere: Bazinga stops rather than publishing something broken, and it says where and what to
do. Read the line that starts with `hint:` or `Instead:` first.

## Installing

??? question "Which Python do I need?"
    Python 3.11 or newer. Check with `python3 --version`. There is no Node and no bundler to install.

??? question "`pip install -r requirements.txt` fails on numpy"
    numpy is only used by one example figure (`fourier_series`, which lists `REQUIRES = ["numpy"]`). If your Python
    is very new and numpy has no ready-made package for it yet, install a Python version numpy supports, or delete
    `figures/fourier_series.py` and the page that uses it. The rest of Bazinga needs only the standard library plus
    Markdown, PyYAML, Jinja2, latex2mathml and Pygments.

??? question "`No module named bazinga` or `No module named yaml`"
    Run commands from your site folder (the one with `site.yml`), with the Python of your virtual environment:
    `python -m bazinga build`, or activate it first with `source .venv/bin/activate`. You can also point
    at another folder with `python -m bazinga --root path/to/site build`.

## Building and checking

::clip math-check | A formula the build cannot draw: the message points at the place and says what to write instead.

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
| `site.yml is not valid YAML (line N)` | look at line N: usually a missing space after `:`, or a tab |

??? question "A formula looks wrong or will not build"
    Check it on its own. The command shows where the problem is and what to write instead:

    ```text
    $ python -m bazinga math 'x^10'
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

## The Editor and serve

??? question "`OSError: [Errno 48] Address already in use`"
    Another program, or another copy of `serve`, uses the port. Stop it, or pick another port:
    `python -m bazinga serve --port 8001`. The Editor then uses the next port; choose it yourself with
    `--studio-port 8011`. (On Linux the number is 98 instead of 48.)

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
    The Editor loads its text editor from a public CDN (esm.sh) the first time. It needs a network connection.

## Ask and the language model

| What you see | Why | What to do |
|---|---|---|
| `No model configured: set llm.model in site.yml and the key …` | no model name, or no key found | set `llm.model`; put the key in `.env.local` under the name in `llm.key_env` |
| `error: every model failed (…: HTTP 401)` | wrong or expired key, or a key for another service | copy the key again; check `llm.base_url` |
| `error: every model failed (…: HTTP 429)` | the model is busy, or you hit a rate limit | wait a minute, or add a second model after a comma |
| `error: every model failed (…: HTTP 404)` | no model by that name at that service | copy the exact name from the service's list |
| `error: every model failed (…: TimeoutError)` or `URLError` | no reply in time, or no connection | try again, or a smaller model; check the address |
| `error: every model failed (…: empty reply)` | the model sent back nothing | use another model |
| `error: the reply was not JSON` | the model wrote its thinking instead of the reply | use a model that answers directly |
| The Written answer button never shows | written answers are off | the server needs `llm.model` and a non-empty key variable; see [Ask and the wiki](ask-and-wiki.md#what-it-needs) |
| "That is all the written answers for today." | the visitor used their daily written answers | raise `ask.per_visitor`, or wait until tomorrow |
| "No written answer right now." | the model failed for this question | not counted against the limit; try again |

??? question "Can a model on my laptop answer my readers?"
    No. The deployed site cannot reach your computer. A local model (Ollama, LM Studio) works for your own
    suggestions and for trying written answers with `serve`. See [Ask and the wiki](ask-and-wiki.md).

??? question "Is my key safe?"
    Keep it in `.env.local` (git never commits it) or in your host's environment settings. Never put it in
    `site.yml` or a post. Bazinga never prints it.

## Publishing and deploying

??? question "Publish stopped"
    Publish runs the checks, tests the page's figures, builds, commits and pushes, and stops at the first failure.
    A failure before the commit puts your page back as it was. If only the push fails, the commit stays on your
    computer; push it yourself with `git push` once the problem is fixed. Try the whole run safely first:
    `python -m bazinga publish content/reads/my-post.md --dry-run`.

??? question "`Not committed: git does not know your name and email.`"
    The commit needs a name and an email, and git has none. Run these once in your site folder, then publish again:

    ```bash
    git config user.name "Your Name"
    git config user.email you@example.com
    ```

    Or set `publish.author: "Your Name <you@example.com>"` in `site.yml`. Your page was put back as it was.

??? question "`No such page: content/reads/…`"
    The path is wrong. Give the path from your site folder, as `content/<kind>/<file>.md`.

??? question "The deploy fails on the host but builds on my computer"
    Vercel and Netlify run the tests before they build (`python3 -m unittest discover tests`). A failing test stops
    the deploy and the old site stays up. Run the same command on your computer to see the failure.

??? question "GitHub Pages shows nothing"
    In your repository, open Settings → Pages and set Source to **GitHub Actions**. The workflow
    `.github/workflows/pages.yml` runs on every push to `main` and once a day. If your branch has another name,
    change `branches: [main]` in that file.

??? question "A scheduled post did not go live"
    A scheduled post appears on the first build on or after its date. GitHub Pages rebuilds once a day by itself.
    On Vercel or Netlify, start a build on that day (a push, or a scheduled build hook).

See [Deploying](deploying.md) for each host.

## Still stuck?

Run `python -m bazinga check` and read the first error. If you think you found a bug, open an issue on
[GitHub](https://github.com/shreejalt/Bazinga/issues) with the command, the full message, and your Python version.
Never paste a key.

## What's next

- [Commands reference](reference/commands.md): every command and option.
- [Configuration reference](reference/configuration.md): every setting in `site.yml`.
- [Contributing](contributing/index.md): help improve Bazinga and these pages.
