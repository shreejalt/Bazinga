---
title: "Templates for Figures and Diagrams"
date: 2026-10-20
summary: "Every ready-made figure, animation and diagram in one place, working, with the one line that copies it into your site. Pick the one closest to what you want, copy it, and change the words and numbers."
description: "Ready-made figures, animations and diagrams for Bazinga: see each one working and copy it into your site with one line."
topics: [visualization, tools]
series: {name: "Getting started", part: 5}
builds_on: [read:making-figures, read:drawing-diagrams]
---

The quickest way to a good figure is to start from one that already works. Every template below is live: move its
controls, press Play. Under each is the line that copies it into your site. After that it is your file, and you change
the words, numbers and formulas in it.

**How to copy one.** In the Editor, choose **Figure… → New figure → Start from an example** and pick it from the list. From a
terminal, run the command you build the site with, putting `figure new my_name --from <template>` in place of `build`.
The copy lands in `figures/my_name.py`. Then write `::figure my_name` in a post. Every part of each file has a comment
saying what it does. `figure starters` lists them all.

> [!TIP]
> For a simple plot you do not need a template, or any code: **Figure… → New figure → Fill in a form** builds a
> figure from formulas you type, such as `a*sin(f*x)`. See [[read:making-figures]].

## Plots

### A function with sliders

The starting point for most figures: a curve, two sliders, a reference line and two readouts.
Template: `slider_plot`.

::figure starter_slider_plot

### Your own data as lines

Paste a table of numbers over the example data. The reader can bring one series forward, smooth the lines, or show
the change from the first row. Template: `data_lines`.

::figure starter_data_lines

### Points and the line through them

Random points with a fixed seed, so the build and the browser draw the same ones, and the line that fits them best.
Template: `scatter_fit`.

::figure starter_scatter_fit

### A distribution

A bell curve with a shaded band and its probability. Template: `distribution`.

::figure starter_distribution

### Two panels that move together

One control drives both panels: a curve with its tangent, and the curve's slope. Template: `linked_panels`.

::figure starter_linked_panels

## Bars and grids

### Comparing bars

Values side by side, one picked out, upright or sideways. Template: `compare_bars`.

::figure starter_compare_bars

### A heatmap

A grid of values with row and column labels. Template: `heatmap`.

::figure starter_heatmap

## Animations

Each animation is a slider with a Play button. Pressing Play moves the slider, and the figure is redrawn at each new
value.

### A moving object

A thrown ball, with its path so far, its velocity and its height over time. Template: `animation`.

::figure starter_animation

### Data piling up

A die rolled again and again: the average settles and the counts even out. Template: `sampling`.

::figure starter_sampling

### A field of arrows and a path through it

Arrows that show where a system goes next, and a path that follows them. Template: `vector_field`.

::figure starter_vector_field

### An algorithm, one step at a time

Bubble sort, one comparison per step, with the step explained under the figure. Template: `step_through`.

::figure starter_step_through

## Geometry

### Shapes in the plane

A rotation and a stretch acting on a square and a circle. Template: `geometry2d`.

::figure starter_geometry2d

### A matrix moving the plane

Four sliders, one for each entry of a matrix, and the grid they move. Template: `matrix_transform`.

::figure starter_matrix_transform

## In 3-D

Drag the picture of any of these to turn it.

### A cube and its axes

The smallest 3-D figure: three numbered axes, a cube and a slider for its size. Template: `scene_basic`.

::figure starter_scene_basic

### A surface with sliders

A surface z = f(x, y), coloured by height, with a curve drawn on it. Template: `surface_plot`.

::figure starter_surface_plot

### Vectors and a plane

Two arrows whose tips you drag, their cross product and the plane through them. Template: `vectors_planes`.

::figure starter_vectors_planes

### A camera and its picture

A pinhole camera, the ray from a point to its centre, and the picture it takes. Drag the point or the camera, or open
the camera panels to move it, turn it and change its focal length. Template: `camera_rig`.

::figure starter_camera_rig

## Diagrams, written as text

A diagram needs no file at all. Copy one of these blocks into a post and change the words. [[read:drawing-diagrams]]
has every option.

### Steps in a row

~~~markdown
```diagram
Load [data] -> Clean -> Train [accent] -> Model [emphasis]
Clean -> Report [muted]: "optional"
```
~~~

```diagram
Load [data] -> Clean -> Train [accent] -> Model [emphasis]
Clean -> Report [muted]: "optional"
```

### A model, layer by layer

~~~markdown
```diagram
direction: down
[/Tokens/] -> Embedding -> Block -> Classifier [accent] -> Label [emphasis]
group Block {
  Self-attention -> Feed-forward
}
note Block: "x 6"
```
~~~

```diagram
direction: down
[/Tokens/] -> Embedding -> Block -> Classifier [accent] -> Label [emphasis]
group Block {
  Self-attention -> Feed-forward
}
note Block: "x 6"
```

### A decision

~~~markdown
```diagram
direction: down
(Start) -> Load a batch -> {Loss finite?}
Loss finite? ->|yes| Take a step -> (Done) [emphasis]
Loss finite? ->|no| Lower the rate -> Load a batch
```
~~~

```diagram
direction: down
(Start) -> Load a batch -> {Loss finite?}
Loss finite? ->|yes| Take a step -> (Done) [emphasis]
Loss finite? ->|no| Lower the rate -> Load a batch
```

### A timeline

~~~markdown
```diagram
kind: timeline
2012: AlexNet: "deep nets win ImageNet"
2017: Transformer [accent]: "attention only"
2020: ViT: "images as patches"
```
~~~

```diagram
kind: timeline
2012: AlexNet: "deep nets win ImageNet"
2017: Transformer [accent]: "attention only"
2020: ViT: "images as patches"
```

### A tree

~~~markdown
```diagram
kind: tree
Learning
  Supervised
    Classification
    Regression
  Unsupervised [accent]
```
~~~

```diagram
kind: tree
Learning
  Supervised
    Classification
    Regression
  Unsupervised [accent]
```

## Diagrams from a code file

When the boxes come from data or a loop, a drawing file is the better tool. These templates are copied with the same
`figure new my_name --from <template>` line. The copy lands in `drawings/`, and a post shows it with
`::drawing my_name.<function>`.

::drawing starter_pipeline.steps | Steps with labelled arrows and a data store. Template: `pipeline`, function `steps`.

::drawing starter_blocks.stack | Blocks stacked in a frame. Template: `blocks`, function `stack`.

::drawing starter_architecture.model | A model's layers with the repeated block as a frame. Template: `architecture`, function `model`.

::drawing starter_flowchart.decide | A flowchart with decisions. Template: `flowchart`, function `decide`.

::drawing starter_timeline.history | A timeline. Template: `timeline`, function `history`.

::drawing starter_tree.taxonomy | A tree. Template: `tree`, function `taxonomy`.
