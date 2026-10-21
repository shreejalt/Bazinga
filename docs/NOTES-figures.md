# Notes from the figures builder

## Files (all owned by figures)

| File | What it does |
|---|---|
| `bazinga/plot.py` | spec → `(svg, readouts_html)`. Standard library only; shipped to `_site/figures/_plot.py` and run in the browser too. Panel kinds `xy`, `bars`, `heatmap`, `scene`; 1–4 panels in a row (880 wide) or a column when narrow (480 wide). Also `coerce(controls, values)`, used by the build and the worker so both see identical values. |
| `bazinga/figures.py` | `discover`, `load` (contract check, cached by mtime), `run`, `figure_html`, `write_assets`, `test_figure`, `defaults`, `cli_new`, `cli_test`, `FigureError`. |
| `bazinga/draw.py` | Diagram kit: `Diagram`, `box`, `arrow` (edge anchoring, `bend`, `start`/`end` sides, `both`), `label`, `note`, `group`, `row`, `column`, `grid`, `chain`, `svg()`. |
| `bazinga/drawings.py` | `drawing_html(ref, caption)`, `render`, `discover`, `DrawingError`. |
| `bazinga/theme/assets/js/figure.js` | Wires the controls, starts the worker on intent or when idle and on screen, coalesces requests, play, presets, Reset, plain status text. Exposes `window.Bazinga.py` and `window.Bazinga.figures`. |
| `bazinga/theme/assets/js/pyworker.js` | Module worker: boots the runtime, `loadPackage(REQUIRES)`, fetches modules into its file system, runs figures and generic calls. |
| `bazinga/theme/assets/css/figure.css` | Figures, controls, readouts and drawings; light and dark; phone layout. |
| `bazinga/starters/figures/` | `slider_plot`, `compare_bars`, `heatmap`, `geometry2d`, `animation` (commented for newcomers). |
| `bazinga/starters/drawings/` | `pipeline` (`steps()`), `blocks` (`stack()`). |
| `figures/` | `softmax_temperature`, `gradient_descent`, `fourier_series` (numpy). |
| `drawings/pipeline.py` | `overview(narrow=0)`: write → check → build → publish, with a stacked phone layout. |
| `tests/test_fig_*.py` | 58 tests: plot kinds, determinism, escaping, narrow layout, errors, contract messages, HTML, assets, CLI hooks, every figure, every starter copied, drawings, `node --check`. |

## Figure authoring (second round, 2026-10-20)

**The figure builder** (`bazinga/figbuilder.py`, standard library only): a form ("spec", JSON) becomes an ordinary,
commented figure file.
- Six types: `function`, `shapes`, `bars`, `heatmap`, `distribution` (normal, uniform, exponential, binomial, Poisson),
  `data` (pasted CSV as lines, dots or bars, optional least-squares line and a toggle for it, optional curves on top).
  Shared sections: controls (slider/toggle/steps), values (named expressions), readouts, presets, note.
- Expressions are parsed with `ast` against a whitelist (numbers, declared names, `+ - * / ^ %`, comparisons, `and`/`or`,
  whitelisted maths functions; aggregates such as `max(y)`, `area(y)`, `at(y, 2)` only on lists). Friendly syntax:
  `^`, implicit multiplication (`2x`, `2pi r`, `(a)(b)`), `π`, `−`, `²`. Never `eval`: the checked tree is unparsed into
  the file (`where(c, a, b)` becomes an if/else, `ln` becomes `log`, an int base of `**` becomes a float so `9^9^9`
  overflows at once). Messages carry `path`, `col`, `end` ("unknown name 'freqq' — did you mean 'freq'?").
- Labels, titles and notes take `{expr}` / `{expr:.2f}`.
- Generated files import only `math` and never `bazinga`. Their last line is `# bazinga-builder: {"v","hash","spec"}`;
  `read_spec()` returns the spec and `edited` (the hash of everything above no longer matches).
- API: `validate`, `generate` (raises `SpecError`), `read_spec`, `default_spec(type)`, `describe()`, `parse_expr`.

**figures.py additions:** `test_report(name)` (the same states as `test_figure`, as plain checks with the slowest time
and the failing line), `made_with(source)` (`builder` / `edited` / `code`), `line_of(text)`, `cli_list`,
`cli_preview` (writes `.studio/figure-preview/<name>.html` with the files it needs; interactive when served),
`cli_new(name, "builder" | "builder:<type>")`. Starters added: `scatter_fit`, `distribution`, `matrix_transform`,
`step_through`. CLI: `figure new|test|preview|list`.

**plot.py additions:** series `sizes` and `labels` for `points` (and the new `stems` style), panel `grid`
(`True`/`"x"`/`"y"`, also in scenes without axes) and `origin` (lines through zero). `text_width` now never estimates
narrower than a monospaced face (0.6 em), because the default theme sets figure text in Courier Prime; labels were
being clipped at the right edge.

**Editor figure panel** (`static/panels/figure.js`, `figbuilder.js`, `figure.css`; server side in
`bazinga/studio/figpanel.py`, installed onto `Editor`, and `figworker.py`, whose ops are added to the worker): gallery with
live thumbnails, a page per figure (preview, open at a preset, place in the text), New figure → form / example /
describe, the builder (form beside a live preview with the test in plain words; problems marked in the field), and a
code view (CodeMirror, live check on a 0.9 s pause, failing line marked, Go to line). Unsaved work is tested in
`.studio/drafts/` and shown by `/frame/draft/<name>`, whose figure loads `/_draft/figures/<name>.py`.
Routes: GET `/api/figures/gallery`, `/api/figures/open`, `/api/builder/info`; POST `/api/builder/preview`,
`/api/builder/save`, `/api/figures/check`, `/api/figures/save-code`.

**Shared files touched (surgically):** `server.py` (route table update, the draft frame and draft files),
`api.py` (two lines at the end install the panel), `worker.py` (two lines add the panel's ops), `cm.js`
(`codeEditor` takes `extensions`), `editor.js` (Figure… opens `panels/figure.js`; drawings still use `panels/figures.js`),
`cli.py` (figure actions), `tests/test_core_theme.py` (the reads list counts the built reads instead of a fixed 6: the
two new guides made it 8).

**For core:** `content/reads/welcome.md` says "A figure is a small Python file" and "Diagrams are Python too" in visible
text, which the owner's rule forbids; suggest "a small code file". The guide `content/reads/making-figures.md` shows
terminal commands as `figure test …` after saying "the command you build the site with", to avoid the word.

**Tests:** `test_fig_builder.py` (25), `test_fig_authoring.py` (17), `test_fig_studio.py` (9).

## For core (please act on these)

1. **requirements.txt: add `numpy`.** The example `figures/fourier_series.py` declares `REQUIRES = ["numpy"]`, and the build imports it. I installed numpy 2.5.4 into `.venv`. Without numpy, `test_fig_figures` fails on that figure with a clear message.
2. **Pyodide URL.** `figure.js` reads, in this order:
   - `window.BazingaConfig.pyodide`;
   - `<meta name="bazinga-pyodide" content="…/full/">`, which base.html already writes from `vendor.pyodide_index`;
   - the fallback constant `https://cdn.jsdelivr.net/pyodide/v314.0.7/full/` in `figure.js` and `pyworker.js`.

   `tests/test_fig_js.py` checks that both constants are exactly this pinned URL. If you bump the version in `vendor.py`, bump them too.
3. **Site root.** Module URLs in `data-bazinga` are relative to the site root, for example `figures/softmax_temperature.py?v=<hash>`. figure.js resolves them against:
   - `window.BazingaConfig.root`;
   - else `<meta name="bazinga-root">`;
   - else `../../` from its own script URL, because it lives at `/assets/js/figure.js`.

   That default works for sub-path deployments such as GitHub Pages project sites.
4. **Breakout.** `site.css` already widens `.fig` and `.drawing` to `--wide`, so `figure.css` no longer does. `.fig .fig-head` overrides the prose `figcaption` centring and hyphenation.
5. **Tokens used.** `figure.css` uses `--bg`, `--surface`, `--text`, `--text-muted`, `--text-faint`, `--border`, `--accent`, `--fig-accent-dark` and `--font-ui`, and has fallbacks for all of them. Dark mode follows `prefers-color-scheme` plus `:root[data-theme="dark"|"light"]`.
6. **Signatures.**
   - `figure_html(name, start=None, cfg=None)` and `drawing_html(ref, caption="", cfg=None)`: the optional `cfg` lets tests and the Editor point at other folders; otherwise they use `bazinga.config.ROOT`.
   - `cli_new(name, starter, cfg=None)` copies a drawing starter (`pipeline`, `blocks`) into `drawings/` and a figure starter into `figures/`, then runs `test_figure` on new figures.
   - `cli_test(name=None, cfg=None)` returns the exit code.
7. **Live preview.** `Bazinga.figures.init(root)` initialises figures inserted after load; the Editor's `preview.js` already calls it. The `?v=` in module URLs changes with the file's content, and the worker re-imports a module when the URL changes, so edited figures refresh without a reload.

## For wiki (Ask)

```js
await Bazinga.py.call("/figures/_retrieve.py", "answer",
                      {question: q, passages: {"$json": "/data/passages.json"}, page: id})
```

- The result is the function's return value, round-tripped as JSON.
- Keyword arguments come from the object; an array is passed as positional arguments.
- Any `{"$json": url}` value is fetched once by the worker and kept there, so the passages cross the boundary only once.
- Errors reject with the exception's last line, for example `"TypeError: answer() got an unexpected keyword argument 'x'"`.
- Verified in Chrome and WebKit.
- `Bazinga.py.start()` warms the worker; `Bazinga.py.stats` holds `{bootMs, lastMs, requests}`.

## How to make a figure

1. `python -m bazinga figure new my_plot --from slider_plot`. The other starters are `compare_bars`, `heatmap`, `geometry2d` and `animation`.
2. Edit `figures/my_plot.py`. The comments explain every field. `compute()` returns a dict of panels; styles are names, never colours.
3. `python -m bazinga figure test my_plot` checks:
   - the defaults, every preset and 20 random states, wide and narrow;
   - under 30 ms each;
   - no NaN or infinity (use `None` for a gap);
   - well-formed SVG.
4. Put `::figure my_plot` (or `::figure my_plot | start: Preset label`) in a post.

**Spec additions beyond DESIGN.md:**
- **Top level:**
  - `legend` = `[{name, style, kind: "line"|"box"}]`
  - `widths` (relative panel widths in a row)
  - `height`
  - `description` (the SVG `<desc>`)
- **Panel:**
  - `axes`
  - `equal`
  - `x_ticks` / `y_ticks` (values or `[value, "label"]`)
  - `horizontal` (bars)
  - `range` (bars)
  - heatmap fields: `highlight` (cells), `diverging`, `decimals`, `legend`, `square`
- **Series:** `base` (area lower bound).
- **Shapes:**
  - `circle` takes `rx`/`ry`;
  - `line` and `arrow` take `points` (a polyline);
  - `point` takes `r`;
  - `text` takes `anchor`.
- **Styles:** `main`, `second`, `third`, `fourth`, `muted`, `faint`, `highlight`, `good`, `bad`, `ink`, `contour`, `dashed`, `dotted`, `thick`, `thin`, `area`, `points`, `outline`, `solid`, `small`. Combine them with spaces.

**Drawings:** a function returning `Diagram(...).svg()`. If it takes a `narrow` parameter, it is also drawn at about 400 wide for phones. Without one, it keeps a readable size on phones and scrolls inside its frame.

## Test results (2026-10-20)

- `python -m unittest discover tests`: 105 tests OK, 58 of them `test_fig_*`.
- `python -m bazinga figure test`: all three example figures pass.
- Build-side `run()` (compute + render), median of 20:

  | Figure | ms |
  |---|---|
  | softmax_temperature | 1.2 |
  | gradient_descent | 0.9 |
  | fourier_series (numpy) | 6.1 |

**Browser checks.** I ran Playwright in Chrome (system channel) and WebKit at 1440 and 390 px. The pages were a harness with the 3 example figures, the 5 starters and 3 drawings, and core's real build of `posts/welcome`, served from a copy.
- On every figure, a keyboard slider move or a choice click replaced the SVG through the worker.
- Presets, Reset, Play and "Loading…" all worked.
- There were no console errors and no horizontal overflow at 360, 390 or 1440 px.
- With an unreachable runtime URL, the touched figure says "The interactive version could not start here; this is the figure at its default settings." It keeps the static SVG and disables its controls. Untouched figures stay quiet.
- No visible text names the machinery (`tests/test_fig_js.py` checks this).

**Timings in the browser:**

| | Chrome | WebKit |
|---|---|---|
| Runtime boot (warm HTTP cache, fast connection) | 1.2–1.45 s | 1.4–1.5 s |
| First recompute including boot, plain figure | ~1.0 s | ~1.5 s |
| First recompute including boot plus numpy | 1.0–1.3 s | 2.1–2.3 s |
| Later recomputes, end to end | 12–28 ms | 12–28 ms |
| Worker compute + render, plain figure | 1–6 ms | 1–6 ms |
| Worker compute + render, numpy Fourier figure | ~18 ms | ~18 ms |

**Screenshots** are in the session scratchpad, under `scratchpad/figs/`:
- `shots/` holds `<browser>-<width>[-dark]-{static,live}-<n>.png` and `draw-*.png`;
- `real/` holds the built welcome post.

## Known gaps

- **Text width is estimated** from character classes; there is no font metrics. Labels can sit a few pixels off with unusual fonts.
- **Label placement is a greedy candidate search.** It avoids other labels, points, lines and the plot edge, but very crowded plots can still touch.
- **No hover tooltips beyond SVG `<title>`.** That is the native tooltip on lines, bars and cells. There is no crosshair.
- **No helpers for contours, 3-D or images.** Contours are drawn as shapes, for example the ellipses in `gradient_descent`.
- **One module per figure.** A figure cannot import a sibling helper module from `figures/`; only the module itself and `_plot.py` are shipped.
- **One shared worker.** Figures on a page compute one at a time, latest values first. Play advances only when the previous frame has arrived, so slow devices play slower rather than skipping.
- **The runtime comes from the pinned CDN.** Offline, figures stay static at their defaults.
