# 3. Equations

On this page you write maths in a post: inside a sentence, on its own line, numbered and referred to, and over
several aligned rows. You also learn to read the messages Bazinga gives when a formula is wrong.

You write ordinary LaTeX. When the site is built, Bazinga turns it into MathML, which every current browser draws
by itself. Readers' browsers load no maths library, equations appear at once, and screen readers can read them.

## Step 1: maths inside a sentence

Put the formula between single dollar signs:

```markdown
The softmax turns scores $z_i$ into probabilities $p_i = e^{z_i} / \sum_j e^{z_j}$.
```

**What you should see:** the sentence with the formula set in maths type, the same height as the text around it.

A dollar sign followed by a digit or a space stays a dollar sign, so "it costs $5 and $10" needs nothing special.
Write `\$` when a price sits right next to maths, as in `costs \$5, so $x = 5$`.

## Step 2: an equation on its own line

Put `$$` on a line by itself before and after the equation:

```markdown
$$
p_i = \frac{\exp(z_i / T)}{\sum_{j=1}^{K} \exp(z_j / T)}
$$
```

**What you should see:** the equation centred on its own line:

$$
p_i = \frac{\exp(z_i / T)}{\sum_{j=1}^{K} \exp(z_j / T)}
$$

## Step 3: number it and refer to it

Add `{#eq:name}` right after the closing `$$`. The equation gets the next number. Write `[eq:name]` anywhere in the
page to refer to it:

```markdown
$$
p_i = \frac{\exp(z_i / T)}{\sum_{j=1}^{K} \exp(z_j / T)}
$$ {#eq:softmax}

The temperature $T$ in [eq:softmax] controls how sharp the distribution is.
```

**What you should see:** the equation with **(1)** at its right edge, and the sentence reading "The temperature *T*
in (1) controls …", where (1) is a link that jumps to the equation.

- Only named equations are numbered, in the order they appear: (1), (2), (3) …
- `\label{eq:name}` inside the equation does the same as `{#eq:name}`.
- `\tag{A}` inside the equation sets the label yourself: the equation shows **(A)**.
- `\eqref` and `\ref` do not work inside maths. Write `[eq:name]` in the sentence instead.
- A reference to a name that does not exist is an error: `[eq:missing] refers to an equation that does not exist`.

## Step 4: several rows, lined up

For a derivation, put the rows in `aligned`. End each row with `\\` and put `&` just before the sign the rows line
up on:

```markdown
$$
\begin{aligned}
\mathcal{L} &= -\sum_{i=1}^{K} y_i \log p_i \\
\frac{\partial \mathcal{L}}{\partial z_i} &= \frac{1}{T}\,(p_i - y_i)
\end{aligned}
$$ {#eq:gradient}
```

**What you should see:** two rows, with their `=` signs one above the other, and the number **(2)** if it is the
second named equation on the page.

`align`, `split`, `gather` and `multline` work too: the build rewrites them into a form every browser lays out the
same way. Keep each row under about 60 characters. Longer rows scroll sideways on phones, and the checks warn you.

## Matrices and cases

The brackets come with the name: `pmatrix` ( ), `bmatrix` [ ], `vmatrix` | |, `Bmatrix` { }, `Vmatrix` ‖ ‖ and
`matrix` for none. Cells are separated by `&`, rows by `\\`:

```markdown
$$
\operatorname{ReLU}(x) = \begin{cases} x & \text{if } x > 0 \\ 0 & \text{otherwise} \end{cases}
$$
```

## Three habits that prevent most problems

- **Group with braces.** `x^{10}` raises all of 10; `x^10` raises only the 1. The same for subscripts: `a_{ij}`.
- **Write names as names.** `\operatorname{softmax}(z)` gives an upright word with the right spacing.
- **Use `\text{…}` for words.** `\text{if } x > 0` keeps the space after "if".

## Step 5: check a formula on its own

You can try one formula without a page. This prints the MathML when the formula is fine, or what is wrong and
where:

```bash
python -m bazinga math "x^10 + \alpah"
```

**What you should see:**

```text
line 1, column 2: ^10 raises only the 1; the rest stays on the line.
    x^10 + \alpah
     ^^^
Instead: write ^{10}
```

Fix that and run it again, and it points at the next problem:

```text
line 1, column 1: \alpah is not a known command, so it would show as raw text.
    \alpah
    ^^^^^^
Instead: write \alpha if that is what you meant; otherwise, for a named function write \operatorname{alpah}, for words \text{alpah}
```

Add `--display` to check it as an equation on its own line, and `--html preview.html` to write a small page that
shows it rendered.

::clip math-check | Checking one formula in the terminal: the message points at the mistake and says what to write.

The same messages appear in `python -m bazinga check`, in the Editor and in the build, with the file and line. A
formula with an error stops the production build, so a broken equation never reaches the live site.

## In the Editor

The Editor has an equation helper: a palette, ready-made equations, numbering, and a live preview that underlines a
mistake as you type. Type `/` on an empty line and pick **Equation**, or press ++cmd+m++ (++ctrl+m++ on Windows
and Linux). See [The Editor](../editor.md).

::clip editor-equation | The equation helper: type a formula and watch it drawn, number it, and insert it.

## More

The example site has the full guide: `content/reads/writing-math.md` (`/reads/writing-math/` when you serve it). It
lists the patterns you will use often, what each browser draws, and every message with its fix.

## What's next

Your post has equations. Next, cite the papers they come from: [4. Citations](citations.md).
