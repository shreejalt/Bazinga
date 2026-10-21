# AGENTS.md — how this site works as a wiki

This file is for coding agents (Claude Code, Codex, Cursor, …) and for the author. It is the *schema* layer of an
LLM wiki in the sense of Karpathy's "LLM Wiki" idea file
(https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f): the pages are the wiki, `wiki/index.md` is the
catalog, `wiki/log.md` is the log, and this file says how to work on them. Keep it short and change it with the author.

## The three layers

| Layer | Where | Who writes it |
|---|---|---|
| **Sources** (optional) | `sources/` — papers, notes, PDFs, transcripts the author collects. Git-ignored by default. Never edited. | The author |
| **The wiki** | `content/<kind>/<slug>.md` — one Markdown page per concept, paper, project. Front matter + body. | The author (models only propose) |
| **The schema** | this file, plus `docs/DESIGN.md` for the full syntax | The author, with agents |

Generated, committed, never edited by hand:

- `wiki/index.md` — the catalog. One line per public page, grouped by kind and topic: title and link, id, summary,
  topics, what it builds on, series. **Read it first** when you need to find anything.
- `wiki/log.md` — append-only. Every entry starts `## [YYYY-MM-DD] op | subject` (ops: `publish`, `ingest`,
  `lint`, `highlights`, `describe`, `index`, …). `grep '^## \[' wiki/log.md | tail -10` shows what happened lately.

Generated into the built site (`_site/`): `llms.txt`, `llms-full.txt`, a Markdown copy of every page at
`<page url>index.md`, `data/passages.json` (one passage per section) and `data/graph.json` (the map).

## Pages and links

- Id: `<singular kind>:<slug>`, e.g. `read:attention`, `project:robot`. URL: `/<kind>/<slug>/`.
- Front matter: `title`, `date`, `status` (draft | published), `summary`, optional `description` (≤ 155 characters),
  `topics` (1–4, only slugs from `content/topics.yml`), `series: {name, part}`, `builds_on: [ids]`, `cites: [keys]`.
- Links between pages: `[[read:attention]]` or `[[read:attention|this post]]` in the body. Citations: `[@KEY]`, with
  `KEY` in `content/references.yml`. Figures: `::figure name`; diagrams: `::drawing module.fn | caption`.
- The graph has five kinds of edges: builds_on, mentions (`[[…]]`), shared citations, shared topics (weak), series.
  The build refuses unknown ids, topics and citation keys.

## Workflows (exact commands)

Run everything from the site root with the project's Python (`.venv/bin/python` if you use a venv).

**Query** — answer a question from the wiki, with citations:
1. Read `wiki/index.md`; open the pages it points to.
2. Or search the sections: `python -m bazinga wiki query "why divide by the square root of d"` (no model needed;
   prints the best sentences and the sections they come from).
3. Answer only from the pages; cite page URLs with `#section` anchors. Answers are not filed back as pages unless the
   author asks for a new page.

**Ingest** — connect a new or changed page:
1. `python -m bazinga check content/reads/<slug>.md` — fix every error first.
2. `python -m bazinga wiki ingest read:<slug>` — the model proposes topics, builds_on, `[[links]]` to add (each with
   the exact sentence it belongs in), a summary, a description, three questions the page answers, and a series.
   Everything is checked against the real ids, topics and the page's own text; what fails is listed as dropped.
3. Read `proposals/ingest-<slug>.md` with the author. Apply only what they accept, by hand, in the page's front
   matter or body.
4. Build (`python -m bazinga build`): `wiki/index.md` is rewritten when it changed.

**Lint** — keep the wiki healthy:
- `python -m bazinga wiki lint` — fixed rules: orphans (no links, shared sources or series), one-way links between
  pages on the same topic, thin topics (fewer than two pages), pages without figures or drawings, odd `updated`
  dates, broken `[[ids]]`.
- `python -m bazinga wiki lint --model` — also asks the model for contradictions between pages that share a topic;
  a claim is kept only if it is quoted from the pages.
- Result: `proposals/lint-site.md`.

**Other proposals** (all need `llm.model` in `site.yml` and the key in the env var named by `llm.key_env`, or in
`.env.local`, which is git-ignored):
- `python -m bazinga wiki highlights "<series name>"` — 3–4 highlights per part; a line with a number that is not in
  its page is dropped. Accepted lines go to `content/series/<slug>.yml`.
- `python -m bazinga wiki describe read:<slug>` — a description of at most 155 characters in the page's own words.
- `python -m bazinga wiki equation "<words>"` — LaTeX for an equation described in words.
- `python -m bazinga wiki figure "<description>"` — a draft figure module from the closest starter; test it with
  `python -m bazinga figure test <name>` after copying it to `figures/`.
- `python -m bazinga wiki index` rewrites the catalog without a full build; `python -m bazinga wiki log <op> "<subject>"`
  adds a log entry by hand.

## Rules

1. **Cite everything.** Every claim, number and figure in a page comes from a source in `content/references.yml`
   (`[@KEY]`) or from the author's own work. Never invent numbers, results or quotes.
2. **Models propose; the author publishes.** Model output goes to `proposals/` only. No tool here writes to
   `content/`. An agent may edit a page only when the author asks for that edit.
3. **Never rewrite a published page on your own.** Suggest the change (a proposal, a diff, a comment) and wait.
   Typos and broken links are still the author's call.
4. **Keep the wiki connected.** A new page builds on, links to, or shares sources with at least one other page, and
   carries 1–4 existing topics. Add a topic to `content/topics.yml` only with the author.
5. **Do not edit generated files** (`wiki/index.md`, `_site/`, `data/*.json`). Change the pages; the build does the rest.
   `wiki/log.md` is append-only: add entries, never change old ones.
6. **Secrets stay out of the repo.** Keys live in environment variables or `.env.local` (git-ignored); never print
   them, never commit them.
7. **Plain words on the site.** Visible text names what the reader gets ("Answered from 214 passages of this site"),
   not the machinery behind it.
