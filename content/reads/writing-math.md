---
title: "Writing Equations in Tessera"
date: 2026-10-20
summary: "How to write maths that renders the same in every browser: the patterns you will use most, what browsers can and cannot draw, and what each error message means and how to fix it."
description: "How to write equations in Tessera: common LaTeX patterns, what browsers can draw, and the error messages you might see with their fixes."
topics: [writing, tools]
series: {name: "Getting started", part: 2}
builds_on: [read:welcome]
---

Tessera turns the LaTeX in your posts into MathML when the site is built. Browsers draw MathML themselves, so
equations appear instantly, with no script and no flash of raw code, they scale with the text, and screen readers can
read them. The cost is that a few LaTeX commands have no MathML equivalent. This guide shows what works, and what to
do when something does not.

The short version: write ordinary LaTeX maths, run `python -m tessera check`, and follow the hint if a line is
flagged.

## Inline and displayed

Use `$…$` inside a sentence and `$$…$$` on lines of their own for a displayed equation.

```markdown
A vector $\mathbf{x} \in \mathbb{R}^d$ has length $\lVert \mathbf{x} \rVert$.

$$
\lVert \mathbf{x} \rVert = \sqrt{\sum_{i=1}^{d} x_i^2}
$$
```

A vector $\mathbf{x} \in \mathbb{R}^d$ has length $\lVert \mathbf{x} \rVert$.

$$
\lVert \mathbf{x} \rVert = \sqrt{\sum_{i=1}^{d} x_i^2}
$$

A dollar sign that is money, not maths, needs no escaping when a space or a digit follows it: "it costs $5 and $10"
stays text. Write `\$` when you need a literal dollar sign anywhere else.

## Numbering and references

Name an equation with `{#eq:name}` after its closing `$$`. It gets the next number, and `[eq:name]` anywhere in the
page becomes a link showing that number.

```markdown
$$
\nabla_\theta \mathcal{L} = \mathbb{E}_{x \sim p}\left[ \nabla_\theta \ell(x; \theta) \right]
$$ {#eq:expected-gradient}

Stochastic gradient descent estimates [eq:expected-gradient] with a mini-batch.
```

$$
\nabla_\theta \mathcal{L} = \mathbb{E}_{x \sim p}\left[ \nabla_\theta \ell(x; \theta) \right]
$$ {#eq:expected-gradient}

Stochastic gradient descent estimates [eq:expected-gradient] with a mini-batch.

`\label{eq:name}` inside the equation does the same as `{#eq:name}`, and `\tag{★}` sets the label text yourself.
`\eqref` and `\ref` do not work inside maths; use `[eq:name]` in the sentence instead.

## Several lines

`aligned`, `align`, `gather` and `split` all work; the build turns them into an `array`, which browsers lay out
reliably. End each row with `\\` and put `&` where the rows should line up.

```markdown
$$
\begin{aligned}
m_t &= \beta_1 m_{t-1} + (1 - \beta_1)\, g_t \\
v_t &= \beta_2 v_{t-1} + (1 - \beta_2)\, g_t^2 \\
\theta_t &= \theta_{t-1} - \alpha\, \frac{\hat{m}_t}{\sqrt{\hat{v}_t} + \epsilon}
\end{aligned}
$$ {#eq:adam}
```

$$
\begin{aligned}
m_t &= \beta_1 m_{t-1} + (1 - \beta_1)\, g_t \\
v_t &= \beta_2 v_{t-1} + (1 - \beta_2)\, g_t^2 \\
\theta_t &= \theta_{t-1} - \alpha\, \frac{\hat{m}_t}{\sqrt{\hat{v}_t} + \epsilon}
\end{aligned}
$$ {#eq:adam}

These are the updates of the Adam optimiser [@Kingma14], where $\hat{m}_t$ and $\hat{v}_t$ are $m_t$ and $v_t$ divided
by $1 - \beta_1^t$ and $1 - \beta_2^t$. Spacing such as `\\[4pt]` is accepted and ignored.

## Patterns you will use often

| What | Write | Result |
|---|---|---|
| Fraction | `\frac{a}{b}` | $\frac{a}{b}$ |
| Sum with limits | `\sum_{i=1}^{n} x_i` | $\sum_{i=1}^{n} x_i$ |
| Named function | `\operatorname{softmax}(z)` | $\operatorname{softmax}(z)$ |
| Arg max | `\argmax_{y} p(y)` | $\argmax_{y} p(y)$ |
| Bold vector | `\mathbf{x}`, `\boldsymbol{\theta}` | $\mathbf{x}$, $\boldsymbol{\theta}$ |
| Sets | `\mathbb{R}^{n \times d}` | $\mathbb{R}^{n \times d}$ |
| Script letters | `\mathcal{L}` | $\mathcal{L}$ |
| Transpose | `W^\top` | $W^\top$ |
| Norm | `\lVert x \rVert_2` | $\lVert x \rVert_2$ |
| Words | `\text{if } x > 0` | $\text{if } x > 0$ |
| Hat and bar | `\hat{y}`, `\bar{x}` | $\hat{y}$, $\bar{x}$ |
| Matrix | `\begin{pmatrix} a & b \\ c & d \end{pmatrix}` | $\begin{pmatrix} a & b \\ c & d \end{pmatrix}$ |
| Cases | `\begin{cases} x & x > 0 \\ 0 & \text{else} \end{cases}` | $\begin{cases} x & x > 0 \\ 0 & \text{else} \end{cases}$ |

Under a display, `\max`, `\lim` and `\argmax` put their subscripts underneath, as in print:

$$
\hat{y} = \argmax_{y \in \mathcal{Y}} \; p(y \mid x)
$$

## What browsers draw, and what they do not

All current browsers draw MathML: Chrome and Edge since version 109, Firefox, and Safari, together about 96% of
people. Each browser has small quirks. Firefox draws the finest maths; Chromium places the index of a root a little
far left; Safari does not break long equations across lines. Tessera works around the larger gaps:

- `\boldsymbol` and `\bm` become true bold letters, because Chromium ignores bold-italic styling.
- `\big`, `\Big`, `\bigg` are dropped: `\left( … \right)` and plain brackets stretch by themselves.
- `\argmax`, `\argmin` and `\operatorname*{…}` become one upright word, not loose letters.
- Long displayed equations scroll sideways on phones instead of spilling off the page. Still, keep rows under about
  60 characters and split longer ones into `aligned` rows; the checks warn above 90.

A math font with the right tables is loaded with the page (STIX Two Math), because many phones and Windows machines
have none.

## Error messages and fixes

The build never shows a broken formula silently. A production build stops, and a preview shows the formula in a red
box, with the file, the line and a hint. The messages you are most likely to see:

**"\foo is not a command this converter knows, so it would show as raw text."** Usually a typo (`\alpah`) or a macro
from a LaTeX package. For a named function write `\operatorname{name}`; for words write `\text{…}`.

**"\cancel cannot be shown in browsers."** Strike-throughs and boxes (`\cancel`, `\boxed`, `\fbox`) have no MathML
form. Show the idea with colour, `\color{gray}{x}`, or put the formula in a `> [!KEY]` callout.

**"a line break (\\\\) outside an array is ignored by browsers."** Wrap the rows in
`\begin{aligned} … \end{aligned}`, or in `\begin{array}{l} … \end{array}` for left-aligned rows.

**"the braces { } are not balanced."** Count them; an editor with bracket matching (the Studio has one) helps.

**"display maths opened with $$ is never closed."** Add the closing `$$` on its own line.

**"`[eq:name]` refers to an equation that does not exist."** Check the spelling, and that the equation has
`{#eq:name}` after its closing `$$`.

> [!TIP]
> In the Studio, the equation helper shows the result as you type and gives the same messages, before the formula
> ever reaches the page.
