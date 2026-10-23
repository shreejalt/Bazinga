# 4. Citations

On this page you add a paper to your site's citation library, cite it in a post, and see the numbered list Bazinga
puts at the end of the page.

All the papers you cite live in one file, `content/references.yml`. Each paper has a short key, such as
`Vaswani17`. In a post, `[@Vaswani17]` becomes a numbered citation that links to the paper.

## Step 1: add a paper by its arXiv id or DOI

Run `cite` with an arXiv id, an arXiv address or a DOI. It looks the paper up online and writes the entry for you:

```bash
python -m bazinga cite 2010.11929
```

**What you should see:**

```text
Dosovitskiy20: Alexey Dosovitskiy et al. (2020). An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale
Cite it with [@Dosovitskiy20] (or [@Dosovitskiy20, p. 4]).
```

and at the end of `content/references.yml`:

```yaml
Dosovitskiy20:
  title: 'An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale'
  authors: [Alexey Dosovitskiy, Lucas Beyer, Alexander Kolesnikov, Dirk Weissenborn, Xiaohua Zhai, Thomas Unterthiner, Mostafa Dehghani, Matthias Minderer, Georg Heigold, Sylvain Gelly, Jakob Uszkoreit, Neil Houlsby]
  year: 2020
  arxiv: '2010.11929'
```

arXiv usually gives no venue; add a `venue:` line yourself if you want one.

The key is the first author's surname and the year's last two digits. If that key is taken by another paper, `cite`
adds b, c … (`He15b`). Choose your own with `--key`: it must start with a letter and not be in use yet. A DOI works
the same way:

```bash
python -m bazinga cite 10.1038/nature14539 --key LeCun15
```

```text
LeCun15: Yann LeCun et al. (2015). Deep learning
Cite it with [@LeCun15] (or [@LeCun15, p. 4]).
```

If the paper is already in the file, nothing is added and the command tells you its key:

```bash
python -m bazinga cite 1706.03762
```

```text
Vaswani17: Ashish Vaswani et al. (2017). Attention Is All You Need
Cite it with [@Vaswani17] (or [@Vaswani17, p. 4]).
```

!!! note "Needs the internet"
    `cite` asks arXiv or Crossref for the paper's details. Without a connection it stops with "Could not add the
    reference" and the reason. You can always write the entry by hand (Step 2).

## Step 2: or write the entry by hand

Each entry is a key with these fields. This is the `Hinton15` entry from the example file:

```yaml
Hinton15:
  title: "Distilling the Knowledge in a Neural Network"
  authors: [Geoffrey Hinton, Oriol Vinyals, Jeff Dean]
  year: 2015
  venue: "NIPS Deep Learning and Representation Learning Workshop"
  arxiv: "1503.02531"
```

| Field | What it is |
|---|---|
| `title` | The paper's title. |
| `authors` | A list of names. |
| `year` | The year. |
| `venue` | Optional: the journal or conference. The list shows it only for papers without an arXiv id. |
| `arxiv`, `doi`, `url` | At least one. The link in the list goes to `url` if there is one, otherwise to arXiv, otherwise to the DOI. |

## Step 3: cite it in a post

Write the key in square brackets after an `@`. Add a page or section after a comma if you like:

```markdown
Transformers are built from attention [@Vaswani17], and a softmax
with a temperature is also how knowledge distillation works [@Hinton15, sec. 2].
```

**What you should see:**

- In the text, **[1]** and **[2, sec. 2]**. Each number links to its entry, and hovering it shows the authors, year
  and title.
- At the end of the page, a section called **Papers** with the numbered list:

```text
[1] Ashish Vaswani et al., "Attention Is All You Need", arXiv:1706.03762, 2017. Explained here →
[2] Geoffrey Hinton, Oriol Vinyals and Jeff Dean, "Distilling the Knowledge in a Neural Network", arXiv:1503.02531, 2015.
```

Cite several at once with `[@Vaswani17; @Hinton15]`, which shows **[1, 2]**.

Papers are numbered in the order you first cite them. More than three authors become "First author et al.".
**Explained here →** appears when one of your paper pages explains that paper (`explains: [Vaswani17]` in its
header), and links to it.

Papers also appears in the [table of contents](sections.md), after Connections.

## Citing without a mention in the text

To list a paper that you do not cite in a sentence, add its key to the header:

```yaml
cites: [Vaswani17, He15]
```

These papers join the Papers list after the ones you cite in the text. Keys you cite in the text are collected for
you, so you do not need to repeat them here. Shared citations also
connect pages on the [map](../map-and-topics.md).

## When a key is wrong

A key that is not in `content/references.yml` is an error, with the closest key as a hint:

```text
content/reads/broken.md:10: error: [@Vaswani] is not in content/references.yml
    hint: did you mean Vaswani17?
```

`python -m bazinga build` (the build your host runs) stops on it, so a broken citation never reaches the live site.

## In the Editor

The Editor's citation panel does Step 1 and Step 3 at once: paste an arXiv id, an address or a DOI, check the
details, and it saves the entry and inserts `[@Key]`. See [The Editor](../editor.md).

::clip editor-citation | The citation panel: an arXiv id looked up, added to references.yml and cited at the cursor.

## What's next

Your post cites its sources. Next, add something readers can move: [5. Figures and diagrams in a post](figures-in-posts.md).
