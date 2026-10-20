---
title: "Welcome to Tessera"
date: 2026-10-20
summary: "A tour of everything a post can hold: equations that render without scripts, numbered and referenced; citations; links between pages; callouts, footnotes, tables and code; and figures you can move."
description: "A tour of Tessera's Markdown: equations, citations, page links, callouts, footnotes, tables, code, and interactive figures."
topics: [writing, tools, visualization]
series: {name: "Getting started", part: 1}
cites: [Vaswani17]
---

Tessera is a template for technical writing. You write Markdown; the build turns it into pages with real equations,
a numbered reference list, interactive figures and a map of how your pages connect. This post uses every feature
once. Each section shows **what you type** in a code block, then **what you get** right under it.

Open `content/reads/welcome.md` next to this page to see the whole source.

## Equations

Put inline maths between single dollar signs. The build turns it into MathML, which every current browser draws
natively, so the page needs no script to show it and stays sharp at any zoom.

```markdown
The softmax turns scores $z_i$ into probabilities $p_i = e^{z_i} / \sum_j e^{z_j}$.
```

The softmax turns scores $z_i$ into probabilities $p_i = e^{z_i} / \sum_j e^{z_j}$.

A displayed equation goes between `$$` lines. Add `{#eq:name}` after the closing `$$` to number it, then refer to
it anywhere with `[eq:name]`:

```markdown
$$
p_i = \frac{\exp(z_i / T)}{\sum_{j=1}^{K} \exp(z_j / T)}
$$ {#eq:softmax}

The temperature $T$ in [eq:softmax] controls how sharp the distribution is.
```

$$
p_i = \frac{\exp(z_i / T)}{\sum_{j=1}^{K} \exp(z_j / T)}
$$ {#eq:softmax}

The temperature $T$ in [eq:softmax] controls how sharp the distribution is.

Several aligned rows use `aligned` (or `align`); the build rewrites them into a form browsers lay out correctly.
Numbering works the same way:

```markdown
$$
\begin{aligned}
\mathcal{L} &= -\sum_{i=1}^{K} y_i \log p_i \\
\frac{\partial \mathcal{L}}{\partial z_i} &= \frac{1}{T}\,(p_i - y_i)
\end{aligned}
$$ {#eq:gradient}
```

$$
\begin{aligned}
\mathcal{L} &= -\sum_{i=1}^{K} y_i \log p_i \\
\frac{\partial \mathcal{L}}{\partial z_i} &= \frac{1}{T}\,(p_i - y_i)
\end{aligned}
$$ {#eq:gradient}

The gradient in [eq:gradient] shrinks as $T$ grows. To choose the label yourself, write `\tag{…}` inside the
equation:

```markdown
$$
\operatorname{Attention}(Q, K, V) = \operatorname{softmax}\left(\frac{QK^\top}{\sqrt{d_k}}\right) V \tag{A}
$$
```

$$
\operatorname{Attention}(Q, K, V) = \operatorname{softmax}\left(\frac{QK^\top}{\sqrt{d_k}}\right) V \tag{A}
$$

> [!NOTE]
> If a formula uses something browsers cannot draw, the build stops and names the line, with a hint such as
> "`\cancel` is not supported; try colour". [[read:writing-math|The maths guide]] lists what works and the messages
> you might see.

## Figures you can move

A figure is a small code file in `figures/`. One line places it; readers drag the slider and the plot is
recomputed in their browser. Before anyone touches it, the figure is already drawn, so it also works in feed readers
and with scripts turned off.

```markdown
::figure softmax_temperature
```

::figure softmax_temperature

Add `| start: <preset>` to open the same figure at one of its presets:

```markdown
::figure softmax_temperature | start: Sharp
```

::figure softmax_temperature | start: Sharp

## Diagrams

Write a diagram as text in a `diagram` block: name the boxes and join them with arrows. The build lays it out and
draws it in the page's own ink, paper and blue, with no script in the reader's browser. [[read:drawing-diagrams]]
has the whole syntax: shapes, labels, groups, flowcharts, timelines and trees.

~~~markdown
```diagram
Write -> Check -> Build -> Publish
Check -> Write: "fix"
Publish [accent]
```
~~~

```diagram
Write -> Check -> Build -> Publish
Check -> Write: "fix"
Publish [accent]
```

When a diagram needs a loop or data to draw it, a small code file in `drawings/` returns the picture instead, drawn
once at build time.

```markdown
::drawing pipeline.overview | From a Markdown file to the live site.
```

::drawing pipeline.overview | From a Markdown file to the live site.

## Citations and links between pages

Cite a paper from `content/references.yml` with `[@KEY]`, optionally with a page or section. The page gets a numbered
reference list at the end, and each number links to its entry.

```markdown
Transformers are built from attention [@Vaswani17], and a softmax
with a temperature is also how knowledge distillation works [@Hinton15, sec. 2].
```

Transformers are built from attention [@Vaswani17], and a softmax with a temperature is also how knowledge
distillation works [@Hinton15, sec. 2].

Add a paper with `python -m tessera cite 1706.03762` (an arXiv id or a DOI) and the entry is written for you.

Link another page by its id: the kind and the file name. The build checks that the page exists, keeps the title up
to date, and records the link in the map.

```markdown
Next, read [[read:writing-math]], or [[read:writing-math|the guide to equations]].
```

Next, read [[read:writing-math]], or [[read:writing-math|the guide to equations]].

## Callouts

Start a quote with `[!NOTE]`, `[!TIP]`, `[!WARNING]` or `[!KEY]`. Text after the marker becomes the title.

```markdown
> [!TIP]
> Keep one idea per callout.

> [!KEY] The one thing to remember
> Dividing scores by a temperature before the softmax sharpens it when $T < 1$
> and flattens it when $T > 1$.
```

> [!TIP]
> Keep one idea per callout.

> [!KEY] The one thing to remember
> Dividing scores by a temperature before the softmax sharpens it when $T < 1$
> and flattens it when $T > 1$.

> [!WARNING]
> A very small temperature makes $\exp(z_i / T)$ overflow in naive code. Subtract the largest score first.

## Footnotes, highlights and corrections

```markdown
Softmax is a smooth version of arg max.[^name] It is ==differentiable everywhere==,
which is ~~a happy accident~~ the whole point.

[^name]: "Soft arg max" would be the more accurate name.
```

Softmax is a smooth version of arg max.[^name] It is ==differentiable everywhere==, which is ~~a happy accident~~ the
whole point.

[^name]: "Soft arg max" would be the more accurate name.

## Tables

```markdown
| Temperature | Top class | Entropy |
|---|--:|--:|
| 0.2 | 98% | 0.1 nats |
| 1.0 | 52% | 1.3 nats |
| 4.0 | 27% | 1.6 nats |
```

| Temperature | Top class | Entropy |
|---|--:|--:|
| 0.2 | 98% | 0.1 nats |
| 1.0 | 52% | 1.3 nats |
| 4.0 | 27% | 1.6 nats |

These are the five scores of the figure above (3.0, 2.2, 1.6, 1.1 and 0.4) at three temperatures; move its slider to
see the rest.

## Code

Fenced code is coloured at build time, in both light and dark mode, and gets a copy button.

````markdown
```python
import math

def softmax(z, t=1.0):
    m = max(z)  # subtract the largest score so exp() cannot overflow
    e = [math.exp((v - m) / t) for v in z]
    s = sum(e)
    return [v / s for v in e]
```
````

```python
import math

def softmax(z, t=1.0):
    m = max(z)  # subtract the largest score so exp() cannot overflow
    e = [math.exp((v - m) / t) for v in z]
    s = sum(e)
    return [v / s for v in e]
```

## Images

Images live in `static/`. The text in brackets describes the picture for people who cannot see it; the quoted text
becomes the caption.

```markdown
![A mosaic of blue tiles, some linked by lines](static/uploads/tiles.svg "Every page is a tile; links join them.")
```

![A mosaic of blue tiles, some linked by lines](static/uploads/tiles.svg "Every page is a tile; links join them.")

## Headings with fixed anchors {#anchors}

Every section heading gets an anchor and a link that appears on hover. Add `{#name}` to choose the anchor yourself,
so links to it keep working when you reword the heading:

```markdown
## Headings with fixed anchors {#anchors}
```

That is the whole syntax. The page you are reading is also in the map, and the **Ask** button answers questions from
the text of every page on the site.
