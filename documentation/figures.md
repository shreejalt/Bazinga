# Interactive figures

A figure is a picture with controls under it. The reader moves a slider and the picture follows. On this page you
will make one three ways: with a form (no code), from a ready-made example, and by hand. Then you will test it and
place it in a post.

::clip figure-slider | A reader drags a slider and presses a preset; the plot redraws each time.

## How a figure works

Every figure is one small Python file in `figures/`. It lists its controls and has one function, `compute()`,
that says what to draw for the current values. It returns a description (these points as a blue line, these bars,
this number in a tile), and the site turns the description into the picture.

The same file runs in two places:

1. **When the site is built.** The figure is drawn once at its starting values and written into the page. It shows
   with scripts off, in feed readers and to search engines.
2. **In the reader's browser,** when they touch a control. The first time takes a second or so while the browser
   gets ready; after that each change redraws in a few hundredths of a second.

Colours come from the theme, not the figure, so figures always match the site.

## Make one with the form (no code)

1. In the Editor, press **Figure…** in the toolbar (or type `/` on an empty line and choose **Figure…**).
2. Press **New figure**, then **Fill in a form**.
3. Pick what to draw:

    | Kind | What it draws | You write |
    |---|---|---|
    | Function plot | one or more curves y = f(x) | `y =` an expression in `x`, such as `a*sin(f*x)*exp(-d*x)` |
    | Shapes and curves | points, lines, arrows, circles and parametric curves | an expression for each number |
    | Bars | bars whose heights move with the sliders | a height for each bar |
    | Heatmap | a grid of coloured cells | the value of the cell in row `i`, column `j` |
    | Distribution | normal, uniform, exponential, binomial or Poisson | nothing: its parameters become sliders |
    | Data table | a pasted table (CSV) as lines, dots or bars, with a fitted line | nothing, or curves to lay over it |
    | 3-D scene | points, segments, boxes and a surface z = f(x, y), turned by dragging | an expression for each number |

4. Each kind opens as a small working example. Change the **Name**, **Title** and **Caption**, rewrite the
   expressions, and add **Controls** (sliders, toggles, steps), **Values**, **Readouts** and **Presets**.
5. Watch the preview on the right. Above it the test reads **Works, and passes its test**, with the slowest
   setting's time.
6. Press **Save and place in the text**.

**What you should see:** `figures/<name>.py` exists, and `::figure <name>` is in your post at the cursor.

::clip editor-figure-form | Making a figure with the form: pick Function plot, change the expression, save and place it.

Expressions are written the way you would write them on paper:

| Write | Means |
|---|---|
| `x^2 + 1` | `^` is a power |
| `2pi r`, `2(x + 1)` | multiplication can be left out next to a number or a bracket |
| `exp(-d*x)`, `sqrt(x)`, `log(x)`, `abs(x)` | the usual functions; `log` is the natural logarithm |
| `(x > 0) * x` | a comparison is 1 or 0 |
| `where(x > 0, log(x), 0)` | one value or another |
| `max(wave)`, `mean(bars)`, `area(y)`, `at(y, 2)` | numbers from a whole curve or list, for readouts |

Where an expression has no value (the log of a negative number, a division by zero) the curve leaves a gap and a
readout shows a dash. In titles and labels, `{t:.2f}` shows the value of `t` with two decimals. A mistake turns the
field red and says what is wrong, for example `unknown name 'freqq' — did you mean 'freq'?`.

The form writes an ordinary, commented Python file. Its last line keeps the form's settings, so the Editor reopens
the figure in the form. If you change the code by hand, the Editor opens it as code from then on. **Open as code**
switches at any time.

## Start from an example

Each example is a working figure with a comment on every part. List them:

```bash
python -m bazinga figure starters
```

```text
Figures (figures/)
  slider_plot       A damped wave
  compare_bars      Three ways to do the same job
  heatmap           Attention weights
  geometry2d        Rotate and stretch
  animation         A thrown ball
  scatter_fit       Fitting a line to noisy points
  distribution      The normal distribution
  matrix_transform  What a matrix does to the plane
  step_through      Bubble sort, one comparison at a time
  data_lines        Readers per month
  linked_panels     A curve and its slope
  sampling          Rolling a die again and again
  vector_field      A pendulum's arrows
  scene_basic       A cube you can turn
  surface_plot      A wave on a sheet
  vectors_planes    The cross product
  camera_rig        A point becomes a pixel
  copy one:  python -m bazinga figure new my_name --from <starter>   then write  ::figure my_name

Drawings from code (drawings/)
  pipeline          Pipeline
  blocks            Blocks
  architecture      Model architecture
  flowchart         Flowchart
  timeline          Timeline
  tree              Tree
  copy one:  python -m bazinga figure new my_name --from <starter>   then write  ::drawing my_name.<function>

See them all, live: the "Templates for Figures and Diagrams" page of the example site.
```

Copy one and test it:

```bash
python -m bazinga figure new my_plot --from slider_plot
python -m bazinga figure test my_plot
```

```text
Created figures/my_plot.py. Use it in a post with ::figure my_plot
ok   my_plot  (79 ms for all states)
```

`--from builder:<kind>` writes the form's example of a kind instead, which the Editor then opens in the form. The
kinds are `function`, `shapes`, `bars`, `heatmap`, `distribution`, `data` and `scene3d`:

```bash
python -m bazinga figure new my_bars --from builder:bars
```

In the Editor the same list is under **Figure… → New figure → Start from an example**. The example site's page
*Templates for Figures and Diagrams* (`/reads/templates/`) shows every one working.

::clip figure-cli | Listing the examples, copying one, and testing it.

The four 3-D examples (`scene_basic`, `surface_plot`, `vectors_planes`, `camera_rig`) are explained in
[3-D figures](figures-3d.md).

## Write one by hand

A figure file sets a few names and defines `compute()`. This one is complete:

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

Save it as `figures/wave.py` and put `::figure wave` in a post.

| Name | What it is |
|---|---|
| `TITLE`, `CAPTION` | shown above the figure; say in the caption what the controls do |
| `REQUIRES` | extra packages, such as `["numpy"]`. Leave it empty when you can: a package adds a few seconds before the first redraw |
| `CONTROLS` | shown in order. A `slider` has `min`, `max`, `step`, `value` and optionally `"play": True`. A `toggle` has two `options` and gives 0 or 1. `steps` has several `options` and gives the position of the chosen one. Any control may also have a `group`: controls with the same group fold together under that heading |
| `PRESETS` | buttons that set some controls. **Reset** is added for you |
| `compute()` | one argument per control, with the same names, plus `_narrow`, which is 1 when drawing for a phone. Same values in, same picture out |

`compute()` returns up to four `panels` side by side (stacked on phones), plus optional `readouts` (the tiles under
the figure) and a `note` (one line under them). A panel's `kind` is one of:

| `kind` | Draws | Main fields |
|---|---|---|
| `xy` | curves, dots and areas on axes | `series`, `x`, `x_min`, `x_max`, `y_min`, `y_max`, `x_log`, `y_log`, `x_label`, `y_label` |
| `bars` | bars, upright or lying (`"horizontal": True`) | `bars`: each `{"label", "value", "style", "note"}` |
| `heatmap` | a grid of cells | `matrix`, `row_labels`, `col_labels`, `range`, `show_values` |
| `scene` | shapes in plain units, same scale both ways | `shapes`, `x_min` … `y_max`, `axes`, `grid`, `origin` |

Styles are names, never colours: `main`, `second`, `third`, `fourth`, `muted`, `faint`, `highlight`, `good`, `bad`
and `ink` pick the colour; `dashed`, `dotted`, `thick` and `thin` change the line; `area`, `points` and `stems`
change what a series is. Combine them with spaces, as in `"muted dashed"`.

The full reference for every field is the example site's guide *Making Interactive Figures*
(`content/reads/making-figures.md`).

### Every other field {#spec-fields}

These all go in the dictionary `compute()` returns. Each one was drawn in a test figure that passed
`figure test`.

**On the whole figure**

| Field | What it does |
|---|---|
| `readouts` | tiles under the figure: `{"label": "Period", "value": "3.14", "note": "seconds"}`. The value is text, so format numbers yourself |
| `note` | one plain line under the readouts |
| `legend` | a row of keys above the panels: `[{"name": "wave", "style": "main", "kind": "line"}]`; `kind` is `line` or `box` |
| `height` | the panel height in drawing units (the default depends on how many panels there are) |
| `widths` | relative widths of side-by-side panels, one number per panel, such as `[2, 1]` |

**On a panel**

| Field | What it does |
|---|---|
| `title` | a small title over the panel |
| `grid`, `origin` | `True` adds grid lines both ways, or the two lines through zero |
| `x_ticks`, `y_ticks` | your own ticks: numbers, or `[value, "label"]` pairs, as in `[0, [2.5, "half"], 5]` |
| `marks` | reference lines: `{"x": 2.5, "label": "gap"}` up and down, `{"y": 0.5}` across |
| `annotations` | a short note by a point: `{"x": 1, "y": 1.5, "text": "a note"}` |
| `shapes` | in `xy` and `scene` panels, in the panel's own units (below) |

**On a series** (in an `xy` panel): `{"name", "y", "x", "style"}`, plus

| Field | What it does |
|---|---|
| `None` in `y` | leaves a gap in the line instead of breaking the figure |
| `"label_at": "none"` | hides the name at the end of the line |
| `base` | with the `area` style, shades down to this list instead of to zero |
| `sizes`, `labels` | with the `points` style, one radius and one text per dot |

**Shapes** (`"type"` and its numbers; every shape also takes `style` and `label`)

| Type | Numbers |
|---|---|
| `point` | `x`, `y`, optional `r` |
| `line`, `arrow` | `x1`, `y1`, `x2`, `y2`, or `points` for a path |
| `polygon` | `points` |
| `circle` | `x`, `y`, `r` (or `rx` and `ry`) |
| `rect` | `x`, `y`, `w`, `h` |
| `text` | `x`, `y`, `text`, optional `anchor` |

**On a heatmap**: `matrix`, `row_labels`, `col_labels`, `range: [lo, hi]`, `show_values: True`, `diverging`
(colours around zero; on by default when the range crosses zero) and `highlight: [[row, column], …]` to outline cells.
**On bars**: `"horizontal": True` lays them down, and each bar may have a `note`.

The kind `scene3d` is the 3-D panel; it is made with the 3-D kit, see [3-D figures](figures-3d.md).

## Place it in a post, and open it at a preset

Put `::figure my_plot` on a line of its own in a post. To open it at one of its presets, write
`::figure my_plot | start: <preset label>`. [Writing, step 5](writing/figures-in-posts.md) shows both, with what
you should see.

## Test it

The Editor tests a figure each time you save it. From a terminal:

```bash
python -m bazinga figure test my_plot   # one figure
python -m bazinga figure test           # all of them
```

The test draws the figure at its starting values (wide and phone-sized), at every preset, and at 20 random settings
including the ends of every slider. Each drawing must finish in under 30 milliseconds, contain no `nan` or infinity,
and be a well-formed picture. 3-D figures also have every handle dragged a little.

A failure names the setting and the line. Two real examples:

```text
FAIL my_plot
     figure 'my_plot': compute() does not accept freq. Its parameters must match CONTROLS plus _narrow, e.g. def compute(freq=2, damping=0.3, _narrow=0).
```

```text
FAIL my_plot
     my_plot {"damping": 0.0, "freq": 2.0}: figure 'my_plot': compute(freq=2.0, damping=0.0) raised ZeroDivisionError: division by zero (line 46)
```

The build refuses a page whose figure fails to load, so a broken figure never reaches the site.

Two more commands help:

```bash
python -m bazinga figure preview my_plot   # a page with the figure at every preset, in .studio/figure-preview/
python -m bazinga figure list              # every figure, how it was made, and where it is used
```

`figure list` on the example site:

```text
attention_weights    Attention weights for five tokens     code             3 controls, 2 presets; papers/attention-is-all-you-need.md, reads/attention-from-scratch.md
coin_flips           Heads in n tosses                     form, then code  3 controls, 0 presets; reads/making-figures.md
compound_interest    Interest on interest                  form, then code  1 control, 2 presets; reads/making-figures.md
...
9 figures. Test them with: python -m bazinga figure test
```

## Keep it fast

The 30 milliseconds are for the reader: a slider that answers within a frame or two feels attached to the picture.

- A curve needs about 200 points. A thousand look the same and cost five times as much.
- Work out what does not depend on the controls once, outside `compute()`.
- Prefer the standard library to packages, and a few hundred shapes to thousands.

## Common mistakes

| Problem | Fix |
|---|---|
| The axes jump as the slider moves | set `y_min` and `y_max` (and `x_min`, `x_max`) to cover every setting |
| Random points change on every redraw | use `random.Random(seed)` with a fixed seed |
| `nan` in a curve | use `None` for a gap |
| Colours in the code | use a style name such as `"second"` |
| The arguments of `compute()` do not match `CONTROLS` | give every control an argument with exactly its name |
| Reading files or the network in `compute()` | the code runs in the reader's browser, where neither exists; put the data in the file |
| A crowded phone layout | use `_narrow` to drop a panel or shorten labels; check with **Phone width** or `figure preview` |
| In the form: `sin x` | write `sin(x)`; a power is `^` |

## What's next

- Turn figures in 3-D: [3-D figures](figures-3d.md).
- Diagrams that do not move: [Diagrams from code](diagrams.md).
- Put them in a post: [Writing, step 5](writing/figures-in-posts.md).
