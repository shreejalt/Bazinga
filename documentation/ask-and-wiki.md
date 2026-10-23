# Ask and the wiki

Your site is also a small wiki. Every build writes a catalog of your pages, a map of how they connect, and one
passage per section of every page. **Ask** answers readers' questions from those passages, right in their browser.

On this page you will:

- see what Ask does with no setup at all;
- run the wiki commands that need no model, and read their real output;
- connect a language model (OpenRouter, OpenAI, or one on your own computer);
- turn on written answers, and learn their limits;
- use the model's suggestions safely: it proposes, you decide;
- point an AI coding agent at your site's rules (`AGENTS.md`).

A model is optional. Everything on this page up to [Connect a model](#connect-a-model) works without one.

## What Ask does with no setup

Every page has an **Ask** button, and the site has an Ask page at `/ask/`. A reader types a question. The browser
finds the sections of your pages that match best and shows:

- a short answer, made of sentences taken from your pages;
- the pages and sections it came from, as links;
- for questions such as "What connects A and B?" or "What should I read before A?", the chain of pages from the map.

Nothing is sent to a server, and nothing is made up: every sentence is one you wrote. The floating Ask button on a
page takes that page as context, so its answers lean towards the page and its neighbours.

::clip ask | Asking a question on the Ask page. The answer is built from the site's own sections.

**Try it.** Start the site with `python -m bazinga serve`, open <http://127.0.0.1:8000/ask/>, and ask
"What does the temperature do to the softmax?"

**What you should see:** under the box, a heading "From the pages" with two or three sentences, then "Pages that
match best" with links into *Softmax, Temperature and Entropy* and *Welcome to Bazinga*. The line under the answer
reads like "Answered from the map and 134 passages of this site." (the number grows with your site).

The example questions under the box are made from your own pages. To choose them yourself, list up to four in
`site.yml` under `home:`:

```yaml
home:
  ask_examples:
    - "What should I read before Attention from Scratch?"
    - "What connects softmax and attention?"
```

To turn Ask off, set `features: {ask: false}` in `site.yml` and delete the `- {label: Ask, href: /ask/}` line under
`nav:`. The build then leaves out the Ask page and the Ask button. (For now, the "Ask the map" line at the end of
each page still links to `/ask/`.)

## What the build writes for the wiki

You do not run anything for these. `python -m bazinga build` (and `serve`) writes them every time:

| File | What it is |
|---|---|
| `_site/data/passages.json` | one passage per section of every public page; this is what Ask searches |
| `_site/data/graph.json` | the pages, their links and their places on the map |
| `_site/llms.txt`, `_site/llms-full.txt`, `_site/<kind>/<slug>/index.md` | your site for language-model tools, and a Markdown copy of each page ([SEO and feeds](seo-and-feeds.md#llmstxt-and-the-markdown-copies)) |

Drafts and scheduled pages never appear in any of them.

Two more files live in your repository and are meant to be committed:

- `wiki/index.md` is the catalog: one line per public page with its summary, topics and what it builds on.
  `python -m bazinga build` rewrites it when a page changes (`serve` does not), and `wiki index` rewrites it without
  a full build.
- `wiki/log.md` is the log. The first wiki command creates it, and every wiki command, proposal and publish adds a
  dated entry.

`AGENTS.md` in the repository root explains this layout to coding agents, so an agent reads the catalog first.

## The wiki commands

All of them start with `python -m bazinga wiki`. Run them from your site folder.

| Command | What it does | Needs a model |
|---|---|---|
| `wiki index` | rewrites `wiki/index.md` from the public pages | no |
| `wiki query "<question>"` | answers in the terminal, the same way Ask does in the browser | no |
| `wiki lint` | checks the whole site with fixed rules and writes a report to `proposals/` | no |
| `wiki lint --model` | the same, and also asks the model to look for contradictions between pages | yes |
| `wiki log <op> "<subject>"` | adds an entry to `wiki/log.md` | no |
| `wiki ingest <page>` | suggests topics, links, a summary, a description and questions for one page | yes |
| `wiki highlights <series>` | suggests 3–4 highlights for each part of a series | yes |
| `wiki describe <page>` | suggests a search description of at most 155 characters | yes |
| `wiki equation "<words>"` | turns an equation in words into LaTeX | yes |
| `wiki figure "<description>"` | drafts a figure file from the closest starter | yes |

`<page>` is a page id such as `read:softmax-and-temperature`, a file name without `.md`, or a file path. `<series>`
is the series name as written in the pages' `series:` field, in quotes when it has spaces.

`python -m bazinga wiki` on its own prints the same list (its example `post:attention` is an old id; use `read:…`,
`paper:…` or `project:…`).

### Without a model

These outputs come from the example site that ships with Bazinga.

**Rewrite the catalog.**

```bash
python -m bazinga wiki index
```

What you should see:

```text
wiki/index.md: 14 pages, updated
```

Run it again and it says `unchanged`. Each line of `wiki/index.md` looks like this:

```markdown
- [Softmax, Temperature and Entropy](/reads/softmax-and-temperature/) `read:softmax-and-temperature` — A model's
  last layer gives raw scores; the softmax turns them into probabilities. … · topics: probability,
  information-theory, neural-networks · builds on: Gradient Descent, One Step at a Time · series: Learning, Visually 2
```

**Ask from the terminal.**

```bash
python -m bazinga wiki query "what does the temperature do to the softmax"
```

What you should see: the short answer, then the sections it came from. (A long section is split into pieces, so
the same section can be listed twice. The run of words "at onceHow" is a known glitch where two blocks are joined.)

```text
In the next part the softmax runs over words instead of classes, and its temperature is fixed at \sqrt{d}. Temperature controls two things at onceHow confident the probabilities look, measured by the entropy, and how much gradient can flow back through the softmax.

- Softmax, Temperature and Entropy — How the softmax learns: /reads/softmax-and-temperature/#how-the-softmax-learns
- Softmax, Temperature and Entropy — How the softmax learns: /reads/softmax-and-temperature/#how-the-softmax-learns
- Softmax, Temperature and Entropy — introduction: /reads/softmax-and-temperature/
- Softmax, Temperature and Entropy — Temperature: /reads/softmax-and-temperature/#temperature
- Welcome to Bazinga — Callouts: /reads/welcome/#callouts
- Welcome to Bazinga — Figures you can move: /reads/welcome/#figures-you-can-move
```

::clip wiki-query | Asking the site a question from the terminal.

**Check the whole site.**

```bash
python -m bazinga wiki lint
```

What you should see:

```text
Lint: 23 findings. Proposal: <your site folder>/proposals/lint-site.md
```

The report lists, in plain sections: pages with no links at all, one-way links between pages on the same topic,
topics with fewer than two pages, pages without figures or diagrams, dates to check, and broken `[[links]]`. A
finding is a suggestion, not an error. "Thin topics" on a new site is normal.

::clip wiki-lint | The fixed checks: the findings go to proposals/lint-site.md for you to read.

!!! note
    The example site's report lists `read:name` and `...` as broken links from `project:bazinga`. Those are in a
    code example on that page, not real links. Lint reads code examples too, so read its findings with that in mind.

**Write in the log.**

```bash
python -m bazinga wiki log note "Reorganised the attention pages"
```

It prints nothing. The end of `wiki/log.md` now reads:

```markdown
## [2026-10-23] note | Reorganised the attention pages
```

## Connect a model

A model is used for two things: suggestions for you (the `wiki` commands above marked "yes", and the Suggest buttons
in the [Editor](editor.md)), and written answers for your readers. Bazinga talks to any service that offers the
OpenAI-style `/chat/completions` address. You set three things.

### 1. Name the service and the model in `site.yml`

```yaml
llm:
  base_url: "https://openrouter.ai/api/v1"   # where the service lives
  model: "google/gemma-4-26b-a4b-it:free"    # the model's name at that service
  key_env: "LLM_API_KEY"                     # the name of the variable that holds your key
```

Some common `base_url` values:

| Service | `base_url` | Model names look like | Tested for this page |
|---|---|---|---|
| OpenRouter | `https://openrouter.ai/api/v1` | `google/gemma-4-26b-a4b-it:free`, `openai/gpt-4o-mini` | yes |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` | no |
| Ollama, on your computer | `http://localhost:11434/v1` | `llama3.1` (whatever you pulled) | no |
| LM Studio, on your computer | `http://localhost:1234/v1` | the model id LM Studio shows | no |

You can list several models, separated by commas. Bazinga tries them in order and moves on when one fails or is busy:

```yaml
llm:
  model: "google/gemma-4-26b-a4b-it:free, nvidia/nemotron-3-ultra-550b-a55b:free"
```

### 2. Put the key in `.env.local`

Create a file called `.env.local` in your site folder, next to `site.yml`:

```bash
LLM_API_KEY=paste-your-key-here
```

The variable name must match `key_env`. `.env.local` is listed in `.gitignore`, so git never commits it. Do not put
the key in `site.yml`, in a post, or anywhere else in the repository. You can also set the variable in your shell
instead (`export LLM_API_KEY=…`). For the `wiki` commands the shell wins over the file; for written answers in
`python -m bazinga serve`, the file wins.

A model on your own computer (an address that starts with `http://localhost` or `http://127.0.0.1`) needs no key for
the `wiki` commands.

### 3. Check it

```bash
python -m bazinga wiki equation "the softmax of z divided by a temperature T"
```

What you should see, after a few seconds (this is a real reply from a free OpenRouter model):

```text
\operatorname{softmax}(\mathbf{z}/T)_i = \frac{\exp(z_i/T)}{\sum_j \exp(z_j/T)}
```

If it says `No model configured`, the model name or the key is missing. See [When something goes wrong](#when-something-goes-wrong).

## Suggestions: the model proposes, you decide

A model never edits your pages. Each command (except `equation`, which only prints) writes a **proposal** to the
`proposals/` folder: a `.md` file to read, and a `.json` copy for tools. You read it, copy what
you like into your page, and ignore the rest. `proposals/` is in `.gitignore`, so proposals stay on your computer.

The workflow is always the same:

1. Run the command.
2. Open the file it names in `proposals/`.
3. Copy the lines you accept into your page (or into `content/series/<slug>.yml` for highlights).
4. Check and build: `python -m bazinga check`, then `python -m bazinga build`.

### Suggestions for one page

```bash
python -m bazinga wiki ingest read:softmax-and-temperature
```

What you should see:

```text
Proposal: <your site folder>/proposals/ingest-softmax-and-temperature.md (0 links, 3 dropped)
```

The proposal is plain Markdown. Here is a real one, trimmed:

````markdown
# Ingest proposal: Softmax, Temperature and Entropy

Page `read:softmax-and-temperature` (…). Nothing was changed; copy what you accept.

## Front matter

```yaml
topics: [probability, information-theory, neural-networks, training]
builds_on: [read:gradient-descent]
summary: "The softmax turns arbitrary scores into probabilities by exponentiating and normalizing, …"
description: "Softmax, temperature, entropy, and the gradient that trains classifiers — plus why attention scales by sqrt(d)."
series: {name: "Learning", part: 2}
```

## Questions the page answers

- How does temperature change the shape of a softmax distribution?
- What does entropy tell us about a probability distribution?
- Why does a sharp softmax produce tiny gradients?

## Dropped (did not check out)

- link to 'read:gradient-descent': already linked
- link to 'read:attention-from-scratch': the sentence is not in the page
````

Bazinga checks every suggestion before it writes the proposal. Topics must exist in `content/topics.yml`, page ids
must exist, and a suggested link must point to a sentence that is really in your page. What fails a check goes under
"Dropped", with the reason. Read the rest with care too: in this example the model suggested `series: {name:
"Learning", part: 2}`, but the page is already part 2 of "Learning, Visually". You would not copy that line.

### A description for search engines

```bash
python -m bazinga wiki describe read:softmax-and-temperature
```

It prints the suggestion and saves it to `proposals/describe-softmax-and-temperature.md`:

```text
A model's last layer gives raw scores; the softmax turns them into probabilities.
```

The description must use the page's own words. When the model's line does not, Bazinga falls back to the page's
summary and says so in the proposal ("Taken from the summary").

### Highlights for a series

`python -m bazinga wiki highlights "<series>"` proposes 3 or 4 highlights per part from the part's own text; a line
whose numbers are not in the page is dropped. The command, a real proposal and how to accept it are in
[Series, step 4](writing/series.md#step-4-or-have-a-model-propose-them).

### Check for contradictions

```bash
python -m bazinga wiki lint --model
```

This runs the fixed rules and then asks the model to compare pages that share a topic. The report gets one more
section, "Possible contradictions". It reads many pages, so it is slow: on a free model it took about five minutes
for the 14 example pages.

**What you should see:** the same `Lint:` line, and a "Possible contradictions" section in `proposals/lint-site.md`.

### An equation or a figure from words

`wiki equation` prints LaTeX (shown above). `wiki figure` prints a complete figure file drafted from the closest
starter, and also saves it in `proposals/`:

```bash
python -m bazinga wiki figure "a bar chart of the softmax of five scores with a temperature slider"
```

Copy the draft into `figures/` under the name you want, then test it:

```bash
cp proposals/figure-a-bar-chart-of-the-softmax-of-five-score.py figures/softmax_bars.py
python -m bazinga figure test softmax_bars
```

What you should see: `ok   softmax_bars  (13 ms for all states)`. Always test a drafted figure, and read it before
you use it: in one of our runs the draft set a preset to 5 while its slider stopped at 3. The [Editor](editor.md)
runs the test for you before it saves a draft.

## Written answers for your readers

With a model connected, the Ask box can also show a **Written answer** button. It sends the question to your site's
`/api/ask/` address. The server picks the matching passages, the same way the quick answer does, and asks the model
to answer from those passages only, citing them by number. The reader sees a few sentences and the sources.

### What it needs

Written answers are on when all three are true:

- `ask: {written_answers: true}` in `site.yml` (the default);
- a model name (`llm.model`, or the `LLM_MODEL` environment variable on the server);
- a **non-empty** value in the key variable (`LLM_API_KEY`, or whatever `key_env` names) on the server.

If any is missing, the button stays hidden and the quick answer works as before.

!!! note "A local model still needs a key variable for written answers"
    The third rule applies even to a model on your own computer. The code that decides whether written answers are
    on checks only that the key variable is not empty; it makes no exception for a local address. So with Ollama or
    LM Studio, set the key variable to any placeholder text, such as `LLM_API_KEY=local`. We confirmed this by
    reading the code, not by running Ollama.

### Try it on your computer

`python -m bazinga serve` answers `/api/ask/` itself, reading the key from your shell or `.env.local`.

```bash
python -m bazinga serve
```

Open <http://127.0.0.1:8000/ask/>, ask a question, then press **Written answer**. You can also check the endpoint
from a second terminal:

```bash
curl -s http://127.0.0.1:8000/api/ask/
```

What you should see when it is on:

```json
{"on": true, "limit": 5, "left": 5}
```

and when it is off (no key, or no model):

```json
{"on": false}
```

A question sent while it is off gets the answer `Written answers are off on this site.`

### Limits

Each written answer costs a model call, so there are two daily limits. Set them in `site.yml`:

```yaml
ask:
  written_answers: true
  per_visitor: 5      # written answers per visitor (by IP address) per day
  daily_cap: 300      # written answers per day for the whole site
```

When a visitor has used theirs, the **Written answer** button turns grey; a request that still gets through is
answered "That is all the written answers for today. The quick answer still works."
If the model fails or finds nothing, the answer is not counted. The counts live in the server's memory only. On a
host that starts many short-lived copies of the function, such as Vercel, the limits are best effort rather than exact.

Questions and answers are never stored or logged, and the visitor's IP address is only hashed in memory to count.

You can override these settings with environment variables on the server, without changing `site.yml`. The full
list is in [Configuration: environment variables](reference/configuration.md#environment-variables).

### On the deployed site

Written answers run on **Vercel**: `api/ask.py` is the function. Set the key there (Project → Settings →
Environment Variables, the name from `key_env`), never in a file. The function reads the passages from the
deployment. If it cannot find them, it fetches them from `SITE_URL`, or else from the address the request came to.
See [Deploying](deploying.md).

On **Netlify**, **GitHub Pages** and other static hosts there is no server, so the button stays hidden. The quick
answer still works everywhere, because it runs in the reader's browser.

!!! warning "A laptop model cannot answer your visitors"
    The deployed site cannot reach `localhost` on your computer. A local model is good for your own suggestions and
    for trying written answers with `serve`. For readers of the deployed site you need a service the server can
    reach, such as OpenRouter or OpenAI.

### Picking a model

We tried the free OpenRouter models on the example site. What we found:

- Free models are often busy. A busy model returns HTTP 429, and the reader sees "No written answer right now".
  List two or three models so one can stand in for another.
- Some reasoning models put their thinking into the reply. With `nvidia/nemotron-3-ultra-550b-a55b:free`, written
  answers began with "The user asks: …" and `wiki ingest` failed with `the reply was not JSON`, because the thinking
  used up the reply before the answer came. Other commands (`equation`, `figure`, `describe`, `highlights`) worked
  with it. If you see this, put a model that answers directly first, for example `google/gemma-4-26b-a4b-it:free`.
- Expect 5 to 30 seconds per suggestion on free models, and minutes for `lint --model`.

## Working with AI coding agents {#working-with-ai-coding-agents}

`AGENTS.md`, at the root of the site, is written for coding agents such as Claude Code, Codex or Cursor, and for
you. It explains how the site works as a wiki, in the sense of Karpathy's "LLM Wiki" idea:

- **Three layers.** `sources/` (optional, git-ignored: the papers and notes you collect), the wiki itself
  (`content/`), and the rules (`AGENTS.md` and `docs/DESIGN.md`).
- **What is generated.** `wiki/index.md`, the catalog an agent reads first, and `wiki/log.md`, the log of what
  happened. Neither is edited by hand.
- **The exact commands** for asking (`wiki query`), connecting a new page (`check`, then `wiki ingest`), keeping the
  wiki healthy (`wiki lint`) and the other proposals, as described [above](#the-wiki-commands).
- **The rules.** Cite everything; a model only writes proposals to `proposals/`, and nothing reaches `content/`
  unless you accept it.

When you ask an agent to work on your site, point it at `AGENTS.md` first. `CLAUDE.md` does that for Claude Code: it
only says to read `AGENTS.md`, so the same rules apply. Edit the file when your own rules
change, for example the topics you allow or how you like pages written.

## When something goes wrong

The most common ones:

| What you see | What to do |
|---|---|
| `No model configured` | set `llm.model`; put the key in `.env.local` under the name in `key_env` |
| `HTTP 401` | the key is wrong or for another service: copy it again, and check that `base_url` belongs to the same service |
| `HTTP 429` | the model is busy: wait a minute, or add another model after a comma |
| Written answer button never appears | `curl -s http://127.0.0.1:8000/api/ask/` should say `"on": true`; see [What it needs](#what-it-needs) |

Every model and Ask message, with its fix, is in
[Troubleshooting: Ask and the language model](troubleshooting.md#ask-and-the-language-model).

## What's next

Next, change how the site looks: [Theme and customising](theme.md).

- [Deploying](deploying.md): put the site online, with written answers on Vercel.
- [Configuration reference](reference/configuration.md): every `llm:` and `ask:` setting in one table.
