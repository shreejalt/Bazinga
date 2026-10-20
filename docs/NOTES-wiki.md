# Notes from the wiki builder

## Files (owner: wiki)

- `tessera/graph.py`: `Graph` and `build_graph` per INTERFACES.
  - Edges: builds_on 3, series 2.5, mentions 2, cites 1 per shared key (max 3), topic 0.5 per shared topic. A topic
    links each page to at most 6 same-topic pages by date. A key cited by more than 40 pages is ignored.
  - `related` leaves out what builds_on and read_next already show.
  - `rings` follow direct links only (builds_on, mentions, series), at most 3 steps. A page with no direct links falls
    back to the pages it shares citations with, then to its topic peers.
  - Layout: a seeded force layout. Clusters are placed by each page's first topic, repulsion is local through a grid,
    and a separation pass follows. It is deterministic. 400 pages take a few seconds.
  - `series_slug` uses the same rule as `content.slugify`.
- `tessera/wiki.py`: `passages`, `write_site_files`, `write_repo_wiki`, `append_log`, plus the helpers `split_text`,
  `page_markdown`, `llms_txt` and `index_md`.
- `tessera/retrieve.py`: standard library only.
  - It does BM25 with a coordination factor, light stemming and stopwords.
  - Boosts: the current page ×1.6 and its neighbours ×1.25, plus bonuses for words in the title and section heading.
  - It returns an extractive answer of at most 3 sentences, de-duplicated. Another page may add a sentence only if it
    scores close to the best page.
  - The index is cached per passage list. `load()` exists too.
  - About 1 ms per question over 2,000 passages once warm.
- `tessera/llm.py`:
  - The client is OpenAI-compatible and has fallbacks over comma-separated models. If `response_format` fails, it
    retries once without it. The key comes from env or `.env.local`; a localhost endpoint needs no key.
  - Operations: `ingest`, `lint`, `highlights`, `describe`, `equation`, `figure_draft`, all with validation. They write
    `proposals/<op>-<slug>.md`/`.json` and a log entry.
  - `cli(argv, cfg=None)` covers `index | query | ingest | lint [--model] | highlights | describe | equation | figure | log`.
- `tessera/ask_server.py`: `handle(method, body, ip, env, passages_loader, cfg=None, chat=None)`.
  - `passages_loader` may return a list or `{"passages", "graph"}`.
  - Limits are kept in memory per hashed IP. A refund is given when nothing matches or the model fails.
  - It stores and logs nothing.
- `api/ask.py`: a Vercel `handler(BaseHTTPRequestHandler)` (checked against Vercel's current Python runtime docs).
  - It reads `site.yml` for the `llm:`/`ask:` defaults.
  - It loads passages from a local `_site/data` if one is bundled, else from `SITE_URL` or the request host.
  - Env overrides: `LLM_MODEL`, `LLM_BASE_URL`, `ASK_PER_VISITOR`, `ASK_DAILY_CAP`, and the key in `llm.key_env`.
- `tessera/theme/assets/js/explore.js`, `ask.js`, `tessera/theme/assets/css/wiki.css`.
- `AGENTS.md`: the wiki schema.
- `tests/test_wiki_{graph,files,retrieve,llm,ask}.py`, plus the fixture `tests/test_wiki_fixtures.py`.

## Results

- `.venv/bin/python -m unittest discover tests`: 105 tests OK, 47 of them the wiki tests.
- `node --check` passes on both JS files.
- Browser check: Playwright on Chrome, scripts in `scratchpad/wiki/` (`make_site.py`, `serve.py`, `check.mjs`).
  - The test site had 24 pages and 63 passages and was built with core's `build.build`.
  - **/explore/** at 1440 and 390:
    - Hover (or tap) lights the rings nearest first, then fades what they did not reach.
    - A second tap opens the page.
    - Labels never overlap.
    - No horizontal overflow at 1440, 390 or 360.
    - Dark mode looks right.
  - **/ask/** and the floating panel:
    - The quick answer runs in the figures worker (`Tessera.py.call` with `{"$json": url}` args).
    - The first answer takes about 1.8 s while the runtime boots; later ones take about 30 ms.
    - Status reads "Answered from 63 passages of this site."
    - Written answer: GET on, POST answer with numbered sources, limit counter.
    - No machinery words appear in the visible text.
    - No console errors from these files.
  - Screenshots are in `scratchpad/wiki/shots/`: explore, hover, dark, ask, written answer and widget, at 1440 and 390.

## For core (please wire or fix)

1. `cli.py` should delegate `python -m tessera wiki …` to `tessera.llm.cli(argv[1:])` (it loads config itself, or
   pass `cfg=`). `tessera/__main__.py` and `cli.py` do not exist yet, so `python -m tessera build` cannot run.
2. `serve.py`: route `GET/POST /api/ask/` to
   `ask_server.handle(method, body, ip, os.environ, loader, cfg=cfg)`, where `loader` reads
   `_site/data/passages.json` and `graph.json`.
3. **Bug in `markdown.py` sections:** apostrophes are dropped from section plain text ("Adam's estimate" becomes
   "Adam s estimate" in `passages.json`). Probably a smart-quote or stash placeholder is removed when the text is made
   plain.
4. `explore.html` subtitle says "Point at a page … click to open it". That is wrong on phones, where explore.js already
   shows "Tap a page for its links; tap again to open it." inside the map. Suggest: "Every page and how it connects."
5. `<link rel="alternate" type="text/markdown" href="{{ page.url }}index.md">` in `page.html`, and
   `<link rel="describedby" href="/llms.txt">` in `base.html`, if they are not there yet.
6. `vercel.json`:
   - It may add `"functions": {"api/ask.py": {"excludeFiles": "{tests/**,content/**,figures/**,drawings/**,static/**}"}}`.
     `api/ask.py` needs `site.yml` and `tessera/` in the bundle, which is the default.
   - Set `SITE_URL` in the Vercel project if `site.origin` differs from the deployed host.
7. URLs assumed in `llms.txt` (`## Optional`): `/series/<slugify(name)>/` and `/topics/<slug>/`, which match
   build.py now.
8. `site.css`, `math.css` and `site.js` still return 404 in builds; core owns them.

## Known gaps

- Written-answer limits live in memory per function instance, so on serverless they are best-effort. A shared store
  would be needed for strict limits.
- Model operations were tested against a mocked server only, not a live model; no key was used.
- On a page with no direct links, the hover shows only its fallback ring (same sources, or same topic).
- Very large sites (thousands of pages) make `graph.json` rings O(n·reach). That is fine at blog scale.
