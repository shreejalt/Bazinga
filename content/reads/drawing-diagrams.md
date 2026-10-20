---
title: "Drawing Diagrams"
date: 2026-10-20
summary: "How to draw a diagram by writing it as text in a post: boxes and arrows, shapes, labels, groups, flowcharts, timelines and trees, laid out and drawn when the site is built. Also when a small code file is the better tool, and the habits that keep a diagram readable."
description: "How to draw diagrams in Tessera by writing them as text: arrows, shapes, labels, groups, flowcharts, timelines, trees, and diagrams from code."
topics: [writing, visualization]
series: {name: "Getting started", part: 4}
builds_on: [read:welcome]
---

I used to draw every diagram in a drawing program, export a picture, and paste it in. Then I changed one word in the
text and the picture was wrong, and the source was a file I could no longer find. So in Tessera a diagram is
written in the post itself, as text: you name the boxes and join them with arrows, and the build lays them out and
draws them in the page's own paper, ink and blue. Nothing runs in the reader's browser, the drawing stays sharp at any
zoom, and changing a word is changing a word.

This guide shows every part of the syntax. Each section has **what you type**, then **what you get** right under it.
In the Studio, type `/` on an empty line and choose **Diagram…** to write one with the drawing next to your text.

## The shortest diagram

A diagram is a code block whose language is `diagram`. Each arrow `->` joins two names, and every name becomes a
box. You never declare a box before you use it.

~~~markdown
```diagram
Question -> Search -> Answer
```
~~~

```diagram
Question -> Search -> Answer
```

Names may have spaces, and a name you write twice is the same box (capital letters do not matter), so a branch is
just another line:

~~~markdown
```diagram
Raw text -> Tokenizer -> Model -> Next word
Tokenizer -> Vocabulary
```
~~~

```diagram
Raw text -> Tokenizer -> Model -> Next word
Tokenizer -> Vocabulary
```

## Kinds of arrow, and labels

| You write | You get |
| --- | --- |
| `A -> B` | an arrow from A to B (`-->` works too) |
| `A <- B` | an arrow from B to A |
| `A <-> B` | heads at both ends |
| `A -- B` | a plain line, no head |
| `A -.-> B` | a dashed arrow, for something optional or indirect |
| `A ==> B` | a thick arrow, for the main path |
| `A -> B & C` | one arrow to B and one to C |

Put a label on an arrow after a colon. On a chain, the colon's label goes on the last arrow; to label one arrow in
the middle of a chain, write the label between bars right after it.

~~~markdown
```diagram
Images ==> Encoder -> Decoder: "tokens"
Encoder ->|features| Probe
Decoder -.-> Cache: "keys, values"
```
~~~

```diagram
Images ==> Encoder -> Decoder: "tokens"
Encoder ->|features| Probe
Decoder -.-> Cache: "keys, values"
```

The build leaves room between the columns for every label, so a label never covers a box or another arrow.

## Shapes

A box is a rectangle unless you say otherwise. Write the shape around the name the first time it appears:

| You write | Shape | Use it for |
| --- | --- | --- |
| `[Load]` | rectangle | a step (the default) |
| `(Start)` | rounded ends | where something starts or stops |
| `{Valid?}` | diamond | a decision |
| `((Merge))` | circle | a junction or a single operation |
| `[/Dataset/]` | cylinder | data: a dataset, a table, a store |

~~~markdown
```diagram
(Start) -> [/Raw images/] -> Resize -> {Too dark?}
Too dark? ->|yes| Brighten -> ((Join))
Too dark? ->|no| Join
Join -> (Done)
```
~~~

```diagram
(Start) -> [/Raw images/] -> Resize -> {Too dark?}
Too dark? ->|yes| Brighten -> ((Join))
Too dark? ->|no| Join
Join -> (Done)
```

After the first time, write the plain name (`Too dark?`, not `{Too dark?}`).

## Styles

Four styles, each a colour from the page's own palette. Put the style in square brackets after a name:

| Style | Looks like | Use it for |
| --- | --- | --- |
| `[accent]` | blue outline and blue text | the one box the paragraph is about |
| `[emphasis]` | solid blue | the result, the thing to remember |
| `[muted]` | faint, dashed | a detail, something optional or skipped |
| `[data]` | rust outline | inputs and outputs that are data, not steps |

~~~markdown
```diagram
Prompt [data] -> Retriever -> Generator [accent] -> Answer [emphasis]
Retriever -> Reranker [muted] -> Generator
```
~~~

```diagram
Prompt [data] -> Retriever -> Generator [accent] -> Answer [emphasis]
Retriever -> Reranker [muted] -> Generator
```

A shape word works in the brackets too (`Check [diamond]`), and so do several settings at once, separated by commas:
`Model [accent, round]`. The long form names each setting: `Model [style=accent, shape=round]`.

## Second lines, other text, notes and captions

A colon after a box on its own line gives it a second, quieter line. `label=` shows other text than the name, which
is how two boxes can say the same thing: name them `norm1` and `norm2` and give both the label "Add & norm".

~~~markdown
```diagram
Encoder -> norm1 -> Decoder
Encoder: "12 layers"
norm1 [label="Add & norm", muted]
note Decoder: "reads the encoder's output"
note: "Every block keeps the width of its input."
caption: "A note sits beside its box; a caption goes under the figure."
```
~~~

```diagram
Encoder -> norm1 -> Decoder
Encoder: "12 layers"
norm1 [label="Add & norm", muted]
note Decoder: "reads the encoder's output"
note: "Every block keeps the width of its input."
caption: "A note sits beside its box; a caption goes under the figure."
```

`note Name: "…"` puts a small note beside a box, `note: "…"` puts one under the whole diagram, and `caption:` adds a
caption under the figure, like the caption of a picture.

## Groups

A group draws a frame around some boxes, with its title in small capitals. Arrows to the group's title go to the
frame, so a group can stand for a whole block of a model while still showing what is inside it. Write the members
between braces, on one line or on several, and put arrows inside too.

~~~markdown
```diagram
Image -> Patches -> Encoder -> Head -> Class [emphasis]
group Encoder {
  Attention -> MLP
}
note Encoder: "x 12"
```
~~~

```diagram
Image -> Patches -> Encoder -> Head -> Class [emphasis]
group Encoder {
  Attention -> MLP
}
note Encoder: "x 12"
```

Groups can hold groups, and an arrow may run from a box inside a group to a box outside it. A box belongs to the
first group it is written in.

## Direction, and how it looks on a phone

Diagrams run left to right unless you write `direction: down`. Left to right suits a pipeline, top to bottom suits
a model's layers or a flowchart.

~~~markdown
```diagram
direction: down
[/Tokens/] -> Embedding -> Self-attention
group "Encoder block x 6" {
  Self-attention -> norm1 -> Feed-forward -> norm2
}
norm1 [label="Add & norm", muted]
norm2 [label="Add & norm", muted]
Embedding -.-> norm1: "residual"
norm2 -> Classifier [accent] -> [/Label/]
```
~~~

```diagram
direction: down
[/Tokens/] -> Embedding -> Self-attention
group "Encoder block x 6" {
  Self-attention -> norm1 -> Feed-forward -> norm2
}
norm1 [label="Add & norm", muted]
norm2 [label="Add & norm", muted]
Embedding -.-> norm1: "residual"
norm2 -> Classifier [accent] -> [/Label/]
```

You do not have to think about phones. A diagram wider than a phone is drawn a second time, top to bottom with
narrower boxes, and the page shows that version on small screens. Open this page on your phone, or make the window
narrow, and the pipelines above turn into columns. If even the phone version is too wide, it keeps readable text and
scrolls sideways inside its frame.

## Flowcharts

A flowchart is the same syntax with diamonds. Two things make it read well, and the layout does both for you: a
decision lines up with its first answer, so the main path runs straight, and the other answers leave by its sides;
arrows that loop back go around the boxes instead of through them.

~~~markdown
```diagram
direction: down
(Start) -> Load a batch -> {Loss finite?}
Loss finite? ->|yes| Take a step -> {Last batch?}
Loss finite? ->|no| Halve the learning rate -> Load a batch
Last batch? ->|no| Load a batch
Last batch? ->|yes| (Done) [emphasis]
```
~~~

```diagram
direction: down
(Start) -> Load a batch -> {Loss finite?}
Loss finite? ->|yes| Take a step -> {Last batch?}
Loss finite? ->|no| Halve the learning rate -> Load a batch
Last batch? ->|no| Load a batch
Last batch? ->|yes| (Done) [emphasis]
```

Write the answer you want on the straight path first.

## Timelines

Start a block with `kind: timeline` (or open it with `diagram timeline`) and write one event per line: a date, a
colon, what happened, and optionally a second colon and a detail. The dates are written as you like (`2017`,
`Jun 2017`, `2017-06-12`), and the events stay in the order you wrote them.

~~~markdown
```diagram
kind: timeline
2012: AlexNet: "deep nets win ImageNet"
2015: ResNet: "152 layers, with skips"
2017: Transformer [accent]: "attention only"
2020: ViT: "images as patches"
2022: Diffusion at scale
```
~~~

```diagram
kind: timeline
2012: AlexNet: "deep nets win ImageNet"
2015: ResNet: "152 layers, with skips"
2017: Transformer [accent]: "attention only"
2020: ViT: "images as patches"
2022: Diffusion at scale
```

A timeline runs along a line on wide screens and down the page on phones; `direction: down` makes it run down the
page everywhere.

## Trees

`kind: tree` draws a hierarchy from indentation: one box per line, and a line indented under another is its child.
Spaces or tabs both work, as long as brothers and sisters line up. You can paste a list with `-` bullets, or the
output of the `tree` command, and the marks are ignored.

~~~markdown
```diagram
kind: tree
Machine learning
  Supervised
    Classification
    Regression
  Unsupervised
    Clustering
    Embeddings
  Reinforcement [accent]
```
~~~

```diagram
kind: tree
Machine learning
  Supervised
    Classification
    Regression
  Unsupervised
    Clustering
    Embeddings
  Reinforcement [accent]
```

`direction: right` puts the root on the left. On a phone a wide tree becomes an indented outline.

## When something is wrong

A mistake never draws a wrong picture. The page shows a short note where the diagram would be, and the checks (in
the Studio, in the check command and in the build) name the line in your file and what to write instead:

| You wrote | The check says |
| --- | --- |
| `Input -> ` | this arrow has nothing on its right (write A -> B) |
| `Model [acent]` | 'acent' is not a style or a shape (did you mean accent?) |
| `group Encoder` | a group needs { after its title |
| `note Decoderr: "x"` | note on 'Decoderr', which is not in the diagram (did you mean Decoder?) |
| `2017 Transformer` in a timeline | a timeline item is a date, a colon and what happened |

In the Studio's diagram editor the line turns red as you type, and clicking the message takes you to it.

## Diagrams from a small code file

Text is the right tool for almost every diagram. A small code file is better when the boxes come from data or a
loop, or when a layout needs exact positions. A drawing is a function in `drawings/` that returns the picture; the
same layout is one call away, so you still say only what connects to what:

```python
from tessera import draw

STAGES = [("Read", "names, arrows, groups"), ("Layers", "a column per step"), ...]

def stages(narrow=0):
    names = [s for s, _ in STAGES]
    d = draw.flow(
        nodes=[(s, what) for s, what in STAGES],
        edges=list(zip(names, names[1:])),
        groups={"When the site is built": names},
        narrow=narrow)
    return d.svg()
```

and the post says `::drawing diagrams.stages`:

::drawing diagrams.stages | How a diagram block becomes a drawing, as a small code file draws it.

`draw.flow` takes the same shapes, styles, labels, notes and groups as the text; `draw.timeline` and `draw.tree` do
the same for the other two kinds. The `narrow` argument is how the phone version gets drawn. Six starting points
are in the Studio (pipeline, blocks, model architecture, flowchart, timeline, tree): choose **Drawing from code…**
in the `/` menu.

## Tips

- **One idea per diagram.** If a diagram needs more than about a dozen boxes, it is usually two diagrams, or a
  group that a second diagram opens up.
- **Name boxes the way the text does.** The reader matches the words in the paragraph to the words in the boxes.
- **Use one accent.** `[accent]` marks the box the paragraph is about; if every box is blue, none is.
- **Write the main path first,** in one chain. The layout follows the order you wrote things in when it has a
  choice, so the first chain becomes the straight line.
- **Label the arrows that need it,** not all of them. An arrow from "Tokenizer" to "Embedding" says enough.
- **Prefer down for deep things, right for processes.** Ten layers stacked read better than ten boxes in a row.
- **Give it a caption** with `caption:` when the diagram needs a sentence of explanation, and a `title:` when the
  first few names do not say what it shows: that is what a screen reader announces.
