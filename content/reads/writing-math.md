---
title: "Writing Equations in Bazinga"
date: 2026-10-20
summary: "How to write maths that renders the same in every browser: the basics, numbering and references, several lines, matrices and cases, the patterns you will use most, the messages you may see and how to fix them, and the equation helper."
description: "How to write equations in Bazinga: inline and displayed maths, numbering, matrices and cases, common patterns, error messages and their fixes."
topics: [writing, tools]
series: {name: "Getting started", part: 2}
builds_on: [read:welcome]
---

Bazinga turns the LaTeX in your posts into MathML when the site is built. Browsers draw MathML themselves, so
equations appear at once, with no script and no flash of raw code; they scale with the text, and screen readers can
read them. You do not need to know much LaTeX: the patterns below cover most posts, the Studio's equation helper
builds the rest from buttons, and when something is wrong the message says where and what to write instead.

## The basics

Put `$…$` around maths inside a sentence, and `$$` on lines of their own around a displayed equation.

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

Three habits prevent most problems:

- **Group with braces.** `x^{10}` raises all of 10; `x^10` raises only the 1. The same goes for subscripts:
  `a_{ij}`, not `a_ij`.
- **Write names as names.** `\operatorname{softmax}(z)` gives an upright word with the right spacing; plain
  `softmax(z)` is read as seven letters multiplied together.
- **Use `\text{…}` for words.** `\text{if } x > 0` keeps the space after "if".

Money needs no escaping when a space or a digit follows the dollar sign: "it costs $5 and $10" stays text. Write `\$`
when a dollar sign sits next to maths, as in "costs \$5, so $x = 5$".

Unicode works too: `α ≤ β` is the same as `\alpha \le \beta`.

## Numbering and references

Name an equation with `{#eq:name}` after its closing `$$`. It gets the next number, and `[eq:name]` anywhere in the
page becomes a link that shows that number.

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
`\nonumber` and `\notag` are accepted and do nothing (only named equations are numbered). `\eqref` and `\ref` do not
work inside maths: write `[eq:name]` in the sentence instead.

## Several lines

For a derivation, put the rows in `aligned` (or `align`, `split`), end each row with `\\` and put `&` just before the
sign the rows should line up on.

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
by $1 - \beta_1^t$ and $1 - \beta_2^t$.

`gather` centres each row, and `multline` indents the rows after the first. If you forget the block and just write
rows with `\\` in a displayed equation, Bazinga wraps them for you (lined up at `&` if there is one). Spacing such as
`\\[4pt]` is accepted and ignored.

## Matrices and cases

The brackets come with the name: `pmatrix` ( ), `bmatrix` [ ], `vmatrix` | | for a determinant, `Bmatrix` { },
`Vmatrix` ‖ ‖ and `matrix` for none. Cells are separated by `&`, rows by `\\`.

```markdown
$$
\mathbf{W} = \begin{bmatrix} w_{11} & \cdots & w_{1n} \\ \vdots & \ddots & \vdots \\ w_{m1} & \cdots & w_{mn} \end{bmatrix}
$$
```

$$
\mathbf{W} = \begin{bmatrix} w_{11} & \cdots & w_{1n} \\ \vdots & \ddots & \vdots \\ w_{m1} & \cdots & w_{mn} \end{bmatrix}
$$

`cases` puts a brace in front of choices, with the condition after `&`:

$$
\operatorname{ReLU}(x) = \begin{cases} x & \text{if } x > 0 \\ 0 & \text{otherwise} \end{cases}
$$

`\begin{array}{c|c} … \end{array}` gives a grid with your own column alignment (`l`, `c`, `r`), a `|` draws a rule
between columns, and `\hline` a rule between rows.

## Patterns you will use often

| What | Write | Result |
|---|---|---|
| Fraction | `\frac{a}{b}` | $\frac{a}{b}$ |
| Full-size fraction in a sentence | `\dfrac{a}{b}` | $\dfrac{a}{b}$ |
| Sum with limits | `\sum_{i=1}^{n} x_i` | $\sum_{i=1}^{n} x_i$ |
| Integral | `\int_0^1 f(x)\,\mathrm{d}x` | $\int_0^1 f(x)\,\mathrm{d}x$ |
| Named function | `\operatorname{softmax}(z)` | $\operatorname{softmax}(z)$ |
| Arg max | `\argmax_{y} p(y)` | $\argmax_{y} p(y)$ |
| Bold vector | `\mathbf{x}`, `\boldsymbol{\theta}` | $\mathbf{x}$, $\boldsymbol{\theta}$ |
| Sets | `\mathbb{R}^{n \times d}` | $\mathbb{R}^{n \times d}$ |
| Script letters | `\mathcal{L}` | $\mathcal{L}$ |
| Transpose | `W^\top` | $W^\top$ |
| Norm | `\lVert x \rVert_2` | $\lVert x \rVert_2$ |
| Inner product | `\langle q, k \rangle` | $\langle q, k \rangle$ |
| Given | `p(y \mid x)` | $p(y \mid x)$ |
| Brackets that grow | `\left( \frac{a}{b} \right)` | $\left( \frac{a}{b} \right)$ |
| Words | `\text{if } x > 0` | $\text{if } x > 0$ |
| Hat, bar, tilde | `\hat{y}`, `\bar{x}`, `\tilde{z}` | $\hat{y}$, $\bar{x}$, $\tilde{z}$ |
| Root | `\sqrt{x}`, `\sqrt[3]{x}` | $\sqrt{x}$, $\sqrt[3]{x}$ |
| Binomial | `\binom{n}{k}` | $\binom{n}{k}$ |
| Over and under | `\overset{\text{def}}{=}`, `\underbrace{a+b}_{n}` | $\overset{\text{def}}{=}$, $\underbrace{a+b}_{n}$ |
| Arrow with a label | `A \xrightarrow{f} B` | $A \xrightarrow{f} B$ |
| Spaces | `a \, b \quad c \qquad d` | $a \, b \quad c \qquad d$ |
| Colour, box | `\color{red}{x}`, `\boxed{E}` | $\color{red}{x}$, $\boxed{E}$ |

In a displayed equation, `\sum`, `\max`, `\lim` and `\argmax` put their limits underneath, as in print; inside a
sentence the limits sit beside them so the line keeps its height:

$$
\hat{y} = \argmax_{y \in \mathcal{Y}} \; p(y \mid x)
$$

## What browsers draw

All current browsers draw MathML: Chrome and Edge since version 109, Firefox, and Safari. Bazinga writes only the
part of MathML they all share, and turns the rest into something they draw the same way:

- Bold, script, blackboard and fraktur letters (`\mathbf`, `\mathcal`, `\mathbb`, `\mathfrak`) become the Unicode
  letters themselves, so they look right everywhere; `\boldsymbol` and `\bm` give bold italic.
- Column alignment in `aligned`, colours (`\color`), boxes (`\boxed`), strike-throughs (`\cancel`), `\overline` and
  rules in arrays are drawn with the page's styles, not with features one browser lacks.
- `\big(`, `\Big[` … keep their size; `\left( … \right)` and matrix brackets grow with what they hold.
- Long displayed equations scroll sideways on phones instead of spilling off the page. Still, keep rows under about
  60 characters and split longer ones into `aligned` rows; the checks warn above that.

A few differences remain. Safari places accents like $\hat{x}$ a little higher than Chrome does, Chrome does not
stretch a wide tilde over several letters, and an arrow with a long label (`\xrightarrow{\text{a long label}}`) keeps
its length in Chrome. A math font with the right tables (STIX Two Math) is loaded with the page, because many phones
and Windows machines have none.

## Messages you may see, and the fixes

A formula never breaks silently. A production build stops, and a preview, `python -m bazinga check` and the Studio
show the file, the line and the column, what is wrong and what to write instead. The ones you are most likely to meet:

| Message | What to write instead |
|---|---|
| `\alpah` is not a known command | the right spelling (the message suggests one: `\alpha`); `\operatorname{name}` for a function, `\text{…}` for words |
| `^10` raises only the 1 | `x^{10}`; braces around everything that goes up or down |
| two superscripts in a row | `x^{a^b}` or `{x^a}^b` |
| this `{` is never closed / this `}` has no `{` | the missing brace; the message points at the one without a partner |
| `\left` has no matching `\right` | `\right)` where the bracket closes, or `\right.` for nothing |
| `&` lines up rows, so it only works inside aligned | wrap the rows in `\begin{aligned} … \end{aligned}`, or `\&` for the sign |
| a line break `\\` only works inside a block of rows | put the equation between `$$` on its own lines; wrap the rows in `aligned` |
| `\begin{pmatrix}` has no `\end{pmatrix}` | the `\end{…}` after the last row, with the same name |
| `\frac` needs two parts in braces | `\frac{top}{bottom}` |
| a `$` inside `\text{…}` is shown as a dollar sign | close the text first: `\text{if } x > 0` |
| `\newcommand` cannot be shown | the full form each time, such as `\mathbb{R}` or `\operatorname{tr}` |
| `\eqref` cannot be shown | `[eq:name]` in the sentence |
| this `$` looks like money | `\$5` when a price sits next to maths |
| display maths opened with `$$` is never closed | the closing `$$` on its own line |
| `[eq:name]` refers to an equation that does not exist | the name as written after the equation's `$$`: `{#eq:name}` |

To try a formula on its own, without a page:

```text
python -m bazinga math "x^10 + \alpah"
line 1, column 2: ^10 raises only the 1; the rest stays on the line.
    x^10 + \alpah
     ^^^
Instead: write ^{10}
```

Add `--display` for a displayed equation and `--html preview.html` to write a page that shows it.

## The equation helper

In the Studio, type `/` on an empty line and pick **Equation**, press the Σ button in the toolbar, or press ⌘M (Ctrl+M
on Windows and Linux). With the cursor inside an existing equation, the same shortcut, the **Edit equation** button
that appears above it, or a double-click on its `$` opens it for editing in place.

- **It renders as you type.** A mistake is underlined at its place in the formula, with the message and what to
  write instead; click the line and column to jump there.
- **The palette** has tabs for Greek letters, operators and relations, arrows, accents and fonts, big operators,
  brackets and structures. Structures insert a fraction, a root, scripts and more with empty boxes; press Tab to go
  from one box to the next. The matrix, cases and derivation builders make the whole block for the size you choose.
- **Templates** holds about twenty equations that ML posts use (softmax, cross-entropy, attention, gradient descent,
  Adam, KL divergence, Bayes' rule, the normal density, layer norm and more). Insert one and change what you need.
- **On its own line or inside a sentence** decides between `$$` and `$`.
- **Number this equation** asks for a name, adds `{#eq:name}` and tells you the `[eq:name]` to refer to it (copied for
  you). The page's numbered equations are listed with **Insert reference** buttons.
- In the writing surface, hovering over an equation shows it rendered, and equations with a mistake are underlined
  with the message.

When the site has a writing model set up, **Describe in words** turns a sentence like "the softmax of z, component
i" into a first draft of the LaTeX for you to check.
