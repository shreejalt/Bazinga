# 5. Figures and diagrams in a post

On this page you place three kinds of picture in a post: a figure readers can move, a diagram you write as text, and
a drawing made by a small code file. Each takes one line or one short block.

This page is about **placing** them. Making your own figure is its own guide: [Interactive figures](../figures.md).
The full diagram syntax is in [Diagrams](../diagrams.md).

## Step 1: place an interactive figure

A figure is a file in `figures/`. To place one, write `::figure` and the file's name (without `.py`) on a line of its
own:

```markdown
::figure softmax_temperature
```

**What you should see:** the figure's title, the picture, its controls (sliders, toggles, buttons) and its caption.
Drag a slider and the picture redraws. The picture is already drawn when the page loads, so it also shows in feed
readers, with scripts turned off, and to search engines. The first time a reader moves a control, the browser needs a
second or so to get ready; after that it redraws at once.

::clip figure-slider | Dragging a figure's slider: the picture follows the slider, then a preset button sets several controls at once.

To see which figures your site has, and where each is used:

```bash
python -m bazinga figure list
```

```text
attention_weights    Attention weights for five tokens     code             3 controls, 2 presets; papers/attention-is-all-you-need.md, reads/attention-from-scratch.md
coin_flips           Heads in n tosses                     form, then code  3 controls, 0 presets; reads/making-figures.md
compound_interest    Interest on interest                  form, then code  1 control, 2 presets; reads/making-figures.md
…
softmax_temperature  Softmax temperature                   code             2 controls, 2 presets; reads/softmax-and-temperature.md, reads/welcome.md
tangent_plane        The tangent plane and the way uphill  code             4 controls, 3 presets; reads/making-figures.md
unit_circle          Sine and cosine on the circle         form, then code  1 control, 0 presets; reads/making-figures.md

9 figures. Test them with: python -m bazinga figure test
```

Each line gives the figure's name, its title, how it was made (with the Editor's form, or as code), its controls and
presets, and the posts that use it.

## Step 2: open it at a preset

Many figures have presets: buttons that set several controls at once. A **Reset** button is always added. To open
the figure at one of its presets instead of its starting values, add `| start:` and the preset's label:

```markdown
::figure softmax_temperature | start: Sharp
```

**What you should see:** the same figure, drawn with the "Sharp" preset's values. You can place one figure several
times on a page, each at a different preset.

If the label does not match, the check names the presets the figure has:

```text
content/reads/broken.md:14: error: figure 'softmax_temperature': figure 'softmax_temperature' has no preset 'Sharpest' (presets: 'Sharp', 'Flat'). Did you mean 'Sharp'?
```

`start:` is the only option. Anything else after the `|` is a warning.

## Step 3: write a diagram as text

For boxes and arrows, write the diagram in the post, in a code block whose language is `diagram`:

````markdown
```diagram
Write -> Check -> Build -> Publish
Check -> Write: "fix"
Publish [accent]
```
````

**What you should see:** four boxes in a row joined by arrows, an arrow labelled "fix" going back from Check to
Write, and Publish outlined in the accent colour. The build lays the boxes out and draws them in the page's colours.
On a phone, a wide diagram is drawn again from top to bottom. Nothing runs in the reader's browser.

Arrows, shapes, labels, groups, flowcharts, timelines and trees are all written this way. See
[Diagrams](../diagrams.md) for the whole syntax, or `content/reads/drawing-diagrams.md` in the example site.

## Step 4: place a drawing made by code

When the boxes come from data or a loop, a small function in `drawings/` draws the picture instead. Place it with
`::drawing`, the file name and the function name, and an optional caption after a `|`:

```markdown
::drawing pipeline.overview | From a Markdown file to the live site.
```

**What you should see:** the drawing, with the caption under it. This one is the function `overview` in
`drawings/pipeline.py`. Drawings are made once when the site is built.

## Where else your figures appear

- **Topic pages** (`/topics/<slug>/`) show the live figures of the pages with that topic.
- **Publishing** a page runs the tests of every figure it uses first. A figure that fails its test stops the
  publish. See [Publishing](publishing.md).

## When a name is wrong

A figure that does not exist is an error, with the closest name:

```text
content/reads/broken.md:12: error: figure 'softmax_temprature': there is no figure 'softmax_temprature' (looked for <your site folder>/figures/softmax_temprature.py). Did you mean 'softmax_temperature'?
    hint: fix the figure file, or run: python -m bazinga figure test softmax_temprature
```

`python -m bazinga build` (the build your host runs) stops on it, so a missing figure never reaches the live site.

## In the Editor

In the Editor, **Figure…** in the toolbar (or `/` on an empty line) lets you pick a figure and see it working before
you insert it, or make a new one with a form, no code needed. **Diagram…** shows the drawing next to the text as you
type it. **Drawing from code…** lists the drawings in `drawings/` and inserts one. See [The Editor](../editor.md).

## What's next

Your post has pictures. Next, connect it to your other pages: [6. Links and topics](links-and-topics.md).
