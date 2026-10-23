# Diagrams

A diagram in Bazinga is drawn when the site is built, in the page's own colours, with no script in the reader's
browser. Most diagrams are written as a few lines of text inside the page (a post or a project page). A few are
better drawn by a small Python function. On this page you will do both.

## Diagrams written as text

Write the boxes and arrows in a code block whose language is `diagram`:

````markdown
```diagram
Image -> Patches -> Encoder [accent] -> Class [emphasis]
Encoder -.-> Attention map: "optional"
caption: "How the model reads an image."
```
````

**What you should see:** four boxes in a row joined by arrows, *Encoder* outlined in the accent colour, *Class*
filled, a dashed arrow to *Attention map* with its label, and the caption under the figure. A diagram wider than
a phone is drawn a second time, top to bottom, for small screens.

The syntax at a glance:

| Write | For |
|---|---|
| `A -> B`, `A <- B`, `A <-> B` | an arrow, a reversed arrow, heads at both ends |
| `A -.-> B`, `A ==> B`, `A -- B` | a dashed arrow, a thick arrow, a plain line |
| `A -> B & C` | one arrow to B and one to C |
| `A -> B: "label"`, `A ->|label| B` | a label on the arrow (the second form works in the middle of a chain) |
| `(Start)`, `{Valid?}`, `((Join))`, `[/Data/]` | rounded ends, a diamond, a circle, a cylinder |
| `[accent]`, `[emphasis]`, `[muted]`, `[data]` | the box the text is about, the result, a side detail, data |
| `Name [diamond]`, `Name [style=accent, shape=round]` | a shape word, or several settings at once (`style`, `shape`, `label`, `sub`, `note`) |
| `Name: "second line"`, `Name [label="Other text"]` | a quieter second line, or other text than the name |
| `"Step 1: load" -> B` | quotes around a name that holds `:` `;` `#` `&` `[` or an arrow |
| `A; B -> C`, `# a comment` | several statements on one line; a comment |
| `note Name: "…"`, `note: "…"`, `caption: "…"` | a note by a box, a note under the diagram, a caption |
| `group Name { A -> B }` | a frame around some boxes |
| `direction: down` | top to bottom instead of left to right |
| `title: "…"` | the name a screen reader announces |
| `kind: timeline`, `kind: tree` | a timeline (one `date: event` per line) or a tree (from indentation) |

A mistake never draws a wrong picture. The checks name the line and what to write instead, for example
`'acent' is not a style or a shape (did you mean accent?)`.

In the Editor, type `/` on an empty line and choose **Diagram…**. You get examples (Pipeline, Model architecture,
Flowchart, Timeline, Tree), a live drawing in **Wide** and **Phone** layouts, and **Insert diagram**.

::clip editor-diagram | Writing a diagram as text in the Editor: the drawing appears beside it, also at phone width.

The example site's guide *Drawing Diagrams* (`content/reads/drawing-diagrams.md`, `/reads/drawing-diagrams/`)
shows every part of the syntax with the drawing under it: shapes, labels, groups, flowcharts, timelines and trees.

## Diagrams from code

Text is the right tool for almost every diagram. A function is better when the boxes come from data or a loop, or
when a layout needs exact positions.

A drawing is a function in a file under `drawings/`. It takes `narrow` (1 for the phone version) and returns SVG
text (the picture as a string, `<svg …>…</svg>`). You place it in a post with the module name, the function name and an optional caption:

```markdown
::drawing pipeline.overview | From a Markdown file to the live site.
```

### Start from a starter

Six starters are listed by `figure starters` under **Drawings from code**: `pipeline`, `blocks`, `architecture`,
`flowchart`, `timeline` and `tree`. The same `figure new` command copies them; it sees that the starter is a drawing
and puts the copy in `drawings/`:

```bash
python -m bazinga figure new my_steps --from pipeline
```

```text
Created drawings/my_steps.py. Use it in a post with ::figure my_steps
```

!!! warning "Use `::drawing`, not `::figure`"
    The message above says `::figure`, but a drawing is placed with `::drawing <file>.<function>`. The pipeline
    starter's function is `steps`, so the line is:

    ```markdown
    ::drawing my_steps.steps | Three steps from files to a saved model.
    ```

    Each starter names its function in its first lines.

If the function name is wrong, the check says which functions the file has:

```text
content/reads/my-post.md:33: error: drawing 'my_steps.nope': drawings/my_steps.py has no function nope(). It has: steps
    hint: fix the function in drawings/
```

In the Editor, **Drawing from code…** lists your drawings, shows each one, lets you edit its code, and has
**New drawing** for the starters.

### Lay it out for you: flow, timeline, tree

`bazinga.draw` has three functions that use the same layout as the text diagrams, so you only say what connects to
what:

```python
from bazinga import draw

STAGES = [("Load", "read the files"), ("Clean", "drop bad rows"), ("Train", "fit the model")]


def steps(narrow=0):
    d = draw.flow(
        nodes=STAGES + [{"name": "Model", "shape": "cylinder", "sub": "saved to disk"}],
        edges=[("Load", "Clean", "rows"), ("Clean", "Train", "clean rows"), ("Train", "Model")],
        title="Data flows from input to a saved model in three steps",
        narrow=narrow)
    d.note("Each step only reads what the one before it wrote.")
    return d.svg()
```

Save it as `drawings/my_steps.py` and write `::drawing my_steps.steps | A caption` in a page.

**What you should see:** four boxes left to right (top to bottom on a phone) and the note under them.

| Function | Takes |
|---|---|
| `draw.flow(…)` | `nodes, edges, direction="right", groups=None, notes=None, title=None, narrow=0`: nodes as names, `(name, second line)` pairs, or dicts with `label`, `sub`, `style` (accent, muted, data, emphasis), `shape` (box, round, diamond, circle, cylinder) and `note`; edges as `(a, b)` or `(a, b, label)`, or dicts with `line` ("dashed", "thick") and `heads` ("end", "both", "none"); groups as `{title: [names]}` |
| `draw.timeline(…)` | `items, direction="right", title=None, narrow=0`: items as `(date, title[, detail[, style]])` |
| `draw.tree(…)` | `root, direction="down", title=None, narrow=0`: a node is a string, a `(label, [children])` pair, or a dict |

Each returns the diagram, so you can add a `d.note(...)` before `d.svg()`. Pass `narrow` on: that is how the phone
version is drawn. `title` is what a screen reader announces.

### Place every box yourself: `Diagram` {#diagram-class}

When you need exact positions, `bazinga.draw.Diagram` lets you place the boxes yourself. Coordinates are drawing
units; the drawing scales to the column. Saved as `drawings/by_hand.py`, this one is placed with
`::drawing by_hand.overview`:

```python
from bazinga.draw import Diagram


def overview(narrow=0):
    d = Diagram(720)                                   # 720 units wide, the reading column
    a, b, c = d.row(["Write", "Check", "Build"], y=20)  # three boxes in a row
    d.chain([a, b, c])                                  # arrows from each to the next
    out = d.box(560, 120, 140, text="Publish", style="main solid")
    d.arrow(c, out, label="when it passes")
    d.group("On your computer", [a, b, c])              # a dashed frame with a small-caps title
    d.note("Each step stops on an error.")              # a quiet note under everything
    return d.svg()
```

| Method | What it draws |
|---|---|
| `box(x, y, w, h=None, text, style, sub)` | a box with a bold first line and an optional second line; `h=None` fits the text |
| `node(x, y, w, h, text, sub, style, shape)` | a shape with centred text: `box`, `round`, `diamond`, `circle` or `data` (a cylinder) |
| `row(items, y)`, `column(items, x)`, `grid(items, cols)` | several boxes laid out at once; they return the boxes |
| `arrow(a, b, label, style, bend, both)` | an arrow between two boxes (or points); `bend` curves it, `both` puts heads at both ends |
| `chain(boxes, labels)` | arrows from each box to the next |
| `route(points, style, label, heads)` | a line through the points you give |
| `group(label, items)`, `frame(x, y, w, h, title)` | a dashed frame around boxes, or a panel with a small-caps title at a place you give |
| `label(x, y, text)`, `note(text)`, `anno(x, y, lines)` | text: a label, a note under everything, an annotation of several lines |

Styles are names, as in figures: `main`, `second`, `third`, `fourth`, `muted`, `highlight`, `solid`, `ghost` and
`dashed`, combined with spaces (`"main solid"`). The example site's `drawings/pipeline.py` is a longer one.

## What's next

Next, the map that shows how all your pages connect: [The map and topics](map-and-topics.md).

- Diagrams in a post, next to figures: [Writing, step 5](writing/figures-in-posts.md).
