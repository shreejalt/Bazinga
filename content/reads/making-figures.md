---
title: "Making Interactive Figures"
date: 2026-10-20
summary: "How a figure you can move is made: drawn when the site is built, redrawn in the reader's browser when they touch a control. Three ways to make one (a form, an example, or code), what a figure file holds, how it is tested, and the mistakes worth avoiding."
description: "How to make interactive figures in Tessera: the no-code form, the examples, the figure file part by part, testing, speed and common mistakes."
topics: [visualization, tools]
series: {name: "Getting started", part: 3}
builds_on: [read:welcome]
---

A figure in Tessera is a picture with controls under it. Move a slider and the picture follows. This guide shows how
one is made, from the form in the Studio that needs no code at all to the small code file behind every figure, and
how to keep figures quick and correct.

Here is one to start with. Drag the rate and watch the gap open up.

::figure compound_interest

I made this one with the form in the Studio, in about two minutes: two curves, one slider, three readouts and two
presets. Nothing in it is special; every figure on this site works the same way.

## How a figure works

Every figure is one small code file in the `figures/` folder, with one job: given the value of each control, describe
the picture. It does not draw anything itself. It returns a description (these points joined by a blue line, these
bars, this number in a tile) and the site turns the description into the picture.

That code runs in two places:

1. **When the site is built.** The figure is worked out once at its starting values and the picture is written into
   the page. The page shows the figure before any script has run, in a feed reader, with scripts turned off, and to
   search engines.
2. **In the reader's browser, when they touch a control.** The same code runs again with the new values, and the new
   picture replaces the old one. The first time takes a second or so while the browser gets ready; after that each
   change is redrawn in a few hundredths of a second.

Because the same code draws both, the picture a reader sees after moving a slider back to its start is exactly the one
the build made. And because only the description travels, colours come from the site's theme, not from the figure.

In a post, one line places a figure:

```markdown
::figure compound_interest
```

Add `| start:` and the name of a preset to open it at that preset instead of its starting values:

```markdown
::figure compound_interest | start: Stock market
```

::figure compound_interest | start: Stock market

## Three ways to make one

All three end in the same kind of file, so you can start one way and continue another.

### With the form (no code)

In the Studio, choose **Figure…** in the toolbar (or type `/` on an empty line), then **New figure**, then **Fill in
a form**. Pick what to draw:

| Kind | What it draws | You write |
|---|---|---|
| Function plot | one or more curves | `y =` an expression in `x`, such as `a*sin(f*x)*exp(-d*x)` |
| Shapes and curves | points, lines, arrows, circles, polygons, text and curves x(t), y(t) | an expression for each number |
| Bars | bars that move with the sliders | a height for each bar, or one formula repeated |
| Heatmap | a grid of coloured cells | the value of the cell in row `i`, column `j` |
| Distribution | normal, uniform, exponential, binomial or Poisson | nothing: its parameters become sliders |
| Data table | a pasted table as lines, dots or bars, with a fitted line | nothing, or curves to lay over the data |

Each kind starts as a small working example. Change the title, rewrite the expressions, add sliders, and the preview
beside the form redraws as you type, with the figure's test results under it. When something is wrong, the field turns
red and the message says what and where: `unknown name 'freqq' — did you mean 'freq'?`, with the misspelt word marked.

Expressions are written the way you would write them on paper:

| Write | Means |
|---|---|
| `x^2 + 1` | $x^2 + 1$ (`^` is a power) |
| `2pi r` or `2(x + 1)` | multiplication can be left out next to a number or a bracket |
| `exp(-d*x)`, `sqrt(x)`, `log(x)`, `abs(x)` | the usual functions; `log` is the natural logarithm |
| `(x > 0) * x` | a comparison is 1 or 0 |
| `where(x > 0, log(x), 0)` | one value or another |
| `max(wave)`, `mean(bars)`, `area(y)`, `at(y, 2)` | numbers from a whole curve or list, for readouts |

Where an expression has no value, such as the logarithm of a negative number or a division by zero, the curve leaves
a gap and a readout shows a dash; the figure never breaks. In labels, titles and notes, an expression in braces shows
its value: `T = {t:.2f}` shows `t` with two decimals.

Below the drawing part, every kind has the same sections:

- **Controls:** sliders (from, to, step, start, and an optional Play button), toggles (two choices, 0 or 1 in
  expressions) and steps (several choices; when they are all numbers, expressions get the number).
- **Values:** a name for a number worked out from the controls, such as `half_life = log(2)/d`, usable anywhere after.
- **Readouts:** the tiles under the figure. Each has a label, an expression, decimals and a unit.
- **Presets:** buttons that set several controls at once. Reset is added for you.

Here is a figure of shapes made the same way, with a Play button on its slider. Each coordinate is an expression in
the angle, such as `cos(a)` and `sin(a)`.

::figure unit_circle

And a distribution, where the form asked only for the family and how to shade it:

::figure coin_flips

When you save, the form writes `figures/<name>.py`, a plain, commented code file that you could have written by hand.
Its last line keeps the form's settings, so the Studio reopens the figure in the form next time. If you change the code
by hand, the Studio notices and opens it as code from then on, keeping your changes.

### From an example

**New figure → Start from an example** copies a working figure file into `figures/` and opens it beside its preview.
Every part of it carries a comment, so it is a fair way to learn the figure's code by changing it:

| Example | What it shows |
|---|---|
| Function plot with sliders | a damped wave and its envelope |
| Comparing bars | values side by side, one highlighted |
| Heatmap | a grid of values with labels |
| 2-D geometry | a matrix acting on a square and a circle |
| Animation | a thrown ball, with Play |
| Noisy data and its line | random points (with a fixed seed) and a least-squares line |
| A distribution | a bell curve with a shaded band |
| A matrix moving the plane | four sliders, a transformed grid, the determinant |
| Stepping through an algorithm | bubble sort, one comparison per step |

This one is the noisy data example, copied as it is:

::figure noisy_line

### By writing the code

Any editor works. Create `figures/<name>.py` by hand, or from a terminal: run the command you build the site with,
with `figure …` in place of `build`:

```bash
figure new my_plot --from scatter_fit        # copy an example
figure new my_plot --from builder:bars       # the form's example of a kind, as a file
figure test my_plot                          # the checks described below
figure preview my_plot                       # a page with the figure at every preset
figure list                                  # every figure, how it was made, and where it is used
```

In the Studio, the code opens in an editor beside the preview. The preview follows as you type, the test runs each
time, and when something fails the line is marked and **Go to line** jumps to it.

## The figure's code, part by part

A figure file sets a few names and defines one function. This is a complete one:

```python
import math

TITLE = "A wave"
CAPTION = "Change the frequency."
REQUIRES = []

CONTROLS = [
    {"name": "f", "kind": "slider", "label": "Frequency", "min": 0.5, "max": 6, "step": 0.1, "value": 2},
]
PRESETS = [{"label": "Slow", "values": {"f": 0.5}}]


def compute(f=2, _narrow=0):
    xs = [i / 20 for i in range(201)]
    return {
        "panels": [{"kind": "xy", "x": xs, "y_min": -1, "y_max": 1,
                    "series": [{"name": "wave", "y": [math.sin(f * x) for x in xs]}]}],
        "readouts": [{"label": "Period", "value": "%.2f" % (2 * math.pi / f)}],
    }
```

- `TITLE` and `CAPTION` are shown above the figure. Say in the caption what the controls do.
- `REQUIRES` lists extra packages. Leave it empty when you can: the standard library loads at once, while a package
  such as `numpy` adds a few seconds before the first redraw.
- `CONTROLS` are shown in order. A slider has `min`, `max`, `step`, `value` and optionally `"play": True`; it gives a
  whole number when `min`, `max` and `step` are whole, otherwise a decimal. A `toggle` has two `options` and gives 0 or
  1; `steps` has several `options` and gives the position of the chosen one. `value` is where it starts.
- `PRESETS` are buttons. Each sets some controls and leaves the rest alone.
- `compute()` takes one argument per control, with the same names, plus `_narrow`, which is 1 when the figure is drawn
  for a phone (you may show less there). It must return the same description for the same values every time.

## What compute() returns

A dictionary with up to four `panels` side by side (stacked on phones), and optional `readouts` and a `note`.

### Panels

| `kind` | Draws | Main fields |
|---|---|---|
| `xy` | curves, dots and areas on axes | `series`, `x`, `x_min`, `x_max`, `y_min`, `y_max`, `x_log`, `y_log`, `x_label`, `y_label` |
| `bars` | bars, upright or lying (`"horizontal": True`) | `bars`: each `{"label", "value", "style", "note"}` |
| `heatmap` | a grid of cells | `matrix` (rows of numbers), `row_labels`, `col_labels`, `range`, `show_values` |
| `scene` | shapes in plain units, same scale both ways | `shapes`, `x_min` … `y_max`, `axes`, `grid`, `origin` |

Any panel may have a `title`. `grid: True` adds grid lines both ways, and `origin: True` draws the lines through zero.

### Series and styles

A series is `{"name": "wave", "y": [...], "x": [...], "style": "main"}`. The name labels the end of its line
(`"label_at": "none"` hides it). A `None` in `y` leaves a gap.

Styles are names, never colours, so figures follow the theme: `main`, `second`, `third`, `fourth`, `muted`, `faint`,
`highlight`, `good`, `bad` and `ink` choose the colour; `dashed`, `dotted`, `thick` and `thin` change the line. Combine
them with spaces, as in `"muted dashed"`. Three more change what a series is:

- `area` shades under the line, down to zero, or down to another curve when the series has a `base` list (that is how
  the gap between the two curves at the top of this page is shaded);
- `points` draws dots instead of a line, with `sizes` (one radius per dot) and `labels` (one text per dot) if you want;
- `stems` draws a dot on a stalk from zero, as for the chances in the coin tosses above.

### Shapes, reference lines and notes on the plot

`shapes` (in `scene` and `xy` panels) are `point`, `line`, `arrow`, `polygon`, `circle`, `rect` and `text`, in the
panel's own units: `{"type": "arrow", "x1": 0, "y1": 0, "x2": 1, "y2": 2, "style": "main", "label": "v"}`. A `line`
or `arrow` may take `points` instead, for a path. `marks` are reference lines, `{"x": 2, "label": "half-life"}` up and
down or `{"y": 0.5}` across, and `annotations` put a short note by a point. Labels find a place where they do not
overlap the lines, the dots or each other.

### Readouts and the note

`readouts` are the tiles under the figure: `{"label": "Period", "value": "3.14", "note": "seconds"}`. The value is
text, so format numbers yourself (`"%.2f" % period`). `note` is one plain line under them.

## Testing a figure

The Studio tests a figure every time you save it, and `figure test` does the same from a terminal. The test
draws the figure:

- at its starting values, wide and phone-sized;
- at every preset;
- at 20 random settings of its controls, including the ends of every slider.

Each drawing must finish in under 30 milliseconds, contain no number that is not a number (`nan` or an infinity:
use `None` for a gap), and produce a well-formed picture. In the Studio the results read as a short list, such as
"Fast enough: the slowest setting took 1.5 ms", and a failure says which setting broke it and on which line. The
build refuses a page whose figure fails to load, so a broken figure never reaches the site.

## Keeping it fast

The 30 milliseconds are for the reader: a slider that answers within a frame or two feels attached to the picture.

- A curve needs about 200 points. A thousand look the same and cost five times as much.
- Work out what does not depend on the controls once, outside `compute()`. The bubble sort example runs the whole
  sort when the figure loads and `compute()` only picks a step, so Play is smooth.
- Prefer the standard library to packages, and a few hundred shapes to thousands.
- `figure test` prints the time for every figure, and the Studio shows the slowest setting.

## Common mistakes

- **The axes jump as the slider moves.** Set `y_min` and `y_max` (and `x_min`, `x_max`) to cover every setting, so
  only the curve moves.
- **Random points change on every redraw.** Use `random.Random(seed)` with a seed from a control or a constant.
  `compute()` must give the same picture for the same values, at build time and in the browser.
- **`nan` in a curve.** Turn undefined values into `None`; the line then leaves a gap.
- **Colours in the code.** Write a style name such as `"second"`; the theme picks the colour, and dark pages work.
- **The arguments of `compute()` do not match `CONTROLS`.** Each control needs an argument with exactly its name;
  the error says which one is missing.
- **Reading files or the network in `compute()`.** The code runs in the reader's browser, where neither exists. Put
  data in the file itself (the form's data table does exactly that).
- **Crowded phone layouts.** Check the figure at phone width (the Studio preview and `figure preview` show
  it); use `_narrow` to drop a panel or shorten labels there.
- **In the form:** `sin x` needs brackets, `sin(x)`; a power is `^`; names are lowercase letters, digits and `_`;
  and `x` exists only inside a curve's expression, while readouts use whole curves, as in `max(wave)`.

The [[read:welcome|tour of the template]] shows figures next to everything else a post can hold, and
[[read:writing-math]] covers the equations.
