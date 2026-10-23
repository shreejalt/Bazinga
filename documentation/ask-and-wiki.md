# Ask and the wiki

Your site is also a small wiki. Every build writes a catalog of your pages, a map of how they connect, and one
passage per section of every page. **Ask** answers readers' questions from those passages, right in their browser.

On this page you will:

- see what Ask does with no setup at all;
- run the wiki commands that need no model, and read their real output;
- connect a language model (OpenRouter, OpenAI, or one on your own computer);
- turn on written answers, and learn their limits;
- use the model's suggestions safely: it proposes, you decide.

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
reads like "Answered from the map and 125 passages of this site." (the number grows with your site).

The example questions under the box are made from your own pages. To choose them yourself, list up to four in
`site.yml` under `home:`:

```yaml
home:
  ask_examples:
    - "What should I read before Attention from Scratch?"
    - "What connects softmax and attention?"
```

To turn Ask off everywhere, set `features: {ask: false}` in `site.yml`.

## What the build writes for the wiki

You do not run anything for these. `python -m bazinga build` (and `serve`) writes them every time:

| File | What it is |
|---|---|
| `_site/data/passages.json` | one passage per section of every public page; this is what Ask searches |
| `_site/data/graph.json` | the pages, their links and their places on the map |
| `_site/llms.txt` | a short index of the site for language-model tools ([llmstxt.org](https://llmstxt.org) layout) |
| `_site/llms-full.txt` | every public page as Markdown, in one file |
| `_site/<kind>/<slug>/index.md` | a Markdown copy of each page, next to its HTML |

Drafts and scheduled pages never appear in any of them. To leave out the two `llms` files, set
`features: {llms_txt: false}`.

Two more files live in your repository and are meant to be committed:

- `wiki/index.md` is the catalog: one line per public page with its summary, topics and what it builds on.
- `wiki/log.md` is the log: one dated entry for each publish, lint, index and note.

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

`python -m bazinga wiki --help` prints the same list.

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

What you should see: the short answer, then the sections it came from.

```text
In the next part the softmax runs over words instead of classes, and its temperature is fixed at \sqrt{d}. …

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
instead (`export LLM_API_KEY=…`); the shell wins over the file.

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

A model never edits your pages. Each command writes a **proposal** to the `proposals/` folder. You read it, copy what
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

A series page shows three or four highlights under each part. Without accepted highlights it shows the part's own
section headings. To get suggestions:

```bash
python -m bazinga wiki highlights "Getting started"
```

What you should see:

```text
Proposal: <your site folder>/proposals/highlights-getting-started.md
```

Next to it is `proposals/highlights-getting-started.yml`, ready to use. A trimmed real one:

```yaml
# content/series/getting-started.yml (proposal; copy it there when you accept it)
series: "Getting started"
parts:
  read:writing-math:
    - "Name an equation with {#eq:name} after its closing $$ to number it, then reference it anywhere with [eq:name] which becomes a link showing that number."
  read:making-figures:
    - "figure test draws the figure at start values, every preset, and 20 random settings; each draw must finish under 30 ms with no NaN or infinity values."
  read:welcome:
    []
```

A line is kept only when every number in it appears in the part's own text. A part with `[]` keeps its headings.

To accept it, copy the file to `content/series/getting-started.yml`, edit what you like and build. The steps are in
[Series, step 4](writing/series.md#step-4-or-have-a-model-propose-them).

### Check for contradictions

```bash
python -m bazinga wiki lint --model
```

This runs the fixed rules and then asks the model to compare pages that share a topic. The report gets one more
section, "Possible contradictions". It reads many pages, so it is slow: on a free model it took about five minutes
for the 14 example pages.

### An equation or a figure from words

`wiki equation` prints LaTeX (shown above). `wiki figure` prints a complete figure file drafted from the closest
starter:

```bash
python -m bazinga wiki figure "a bar chart of the softmax of five scores with a temperature slider" > figures/softmax_bars.py
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

When a visitor has used theirs, they see "That is all the written answers for today. The quick answer still works."
If the model fails or finds nothing, the answer is not counted. The counts live in the server's memory only. On a
host that starts many short-lived copies of the function, such as Vercel, the limits are best effort rather than exact.

Questions and answers are never stored or logged, and the visitor's IP address is only hashed in memory to count.

You can override the settings with environment variables on the server, without changing `site.yml`:

| Variable | Overrides |
|---|---|
| `LLM_MODEL` | `llm.model` |
| `LLM_BASE_URL` | `llm.base_url` |
| `LLM_KEY_ENV` | `llm.key_env` |
| `ASK_PER_VISITOR` | `ask.per_visitor` |
| `ASK_DAILY_CAP` | `ask.daily_cap` |
| `ASK_WRITTEN=0` | turns written answers off |

### On the deployed site

Written answers run on **Vercel**: `api/ask.py` is the function. Set the key there (Project → Settings →
Environment Variables, the name from `key_env`), never in a file. If your `site.origin` is not the address Vercel
serves, also set `SITE_URL` to the deployed address. See [Deploying](deploying.md).

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

## When something goes wrong

| What you see | Why | What to do |
|---|---|---|
| `No model configured: set llm.model in site.yml and the key …` | no `llm.model`, or no key found | set `llm.model`; put the key in `.env.local` under the name in `key_env` |
| `No model configured (llm.model and a key); running the fixed rules only.` | `lint --model` without a model | the same; the fixed rules still ran |
| `error: every model failed (…: HTTP 401)` | the key is wrong, expired, or for another service | copy the key again; check `base_url` belongs to the same service |
| `error: every model failed (…: HTTP 429)` | the model is busy or you hit the service's rate limit | wait a minute, or add another model after a comma |
| `error: every model failed (…: HTTP 404)` | the model name does not exist at that service | copy the exact name from the service's model list |
| `error: every model failed (…: empty reply)` | the model returned nothing | try another model |
| `error: every model failed (…: TimeoutError)` or `URLError` | no reply within 60 seconds (25 for written answers) | try a smaller or less busy model |
| `error: the reply was not JSON` | the model wrote text, often its thinking, instead of the structured reply | use a model that answers directly |
| `error: no public page '…'` | the page id is wrong, or the page is a draft | use the id shown in `wiki/index.md`, or the file path |
| `error: no series '…'; known: …` | the series name does not match | copy a name from the list it prints |
| Written answer button never appears | written answers are off | `curl -s http://127.0.0.1:8000/api/ask/` should say `"on": true`; see [What it needs](#what-it-needs) |
| "No written answer right now" | the model failed for this question | it is not counted; try again, or add a fallback model |

More problems and fixes are in [Troubleshooting](troubleshooting.md).

## What's next

- [The map and topics](map-and-topics.md): the other half of the wiki, the map readers explore.
- [Deploying](deploying.md): put the site online, with written answers on Vercel.
- [Configuration reference](reference/configuration.md): every `llm:` and `ask:` setting in one table.
