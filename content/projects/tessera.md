---
title: "Tessera, the Template Behind This Site"
date: 2026-10-19
summary: "An open-source template for technical writing: Markdown posts with real equations, citations and interactive figures, a map of how every page connects, topic and series pages, and an Ask box that answers from the site's own text. This page describes what it does and how it is built."
description: "What Tessera does and how it is built: Markdown to static pages, equations as MathML, figures in Python, a site graph, and Ask from the site's own text."
topics: [tools, writing, visualization]
short: "Tessera"
type: Open-source
stack: "Python · Markdown · MathML"
builds_on: [read:welcome]
---

Tessera is the template this site is made with. I wanted a place for technical writing where an equation is real
text, a figure can be moved, and every page knows which other pages it leans on. This page is the plain description
of how it does that. For the syntax itself, start with [[read:welcome]].

## What you write

A page is one Markdown file in `content/reads/` or `content/projects/`, with a short header: title, date, summary,
one to four topics from `content/topics.yml`, and optionally a series, the pages it builds on, and citations. In the
text, `[[read:name]]` links another page, `[@Key]` cites a paper from `content/references.yml`, `::figure name` places
an interactive figure and `::drawing module.function` a diagram. That is enough to produce everything below.

## How it is built

The engine is a small Python package. `python -m tessera build` reads every page, checks it, and writes a plain
static site to `_site/`, which any static host can serve.

::drawing pipeline.overview | From a Markdown file to the live site.

- **Equations** are converted from LaTeX to MathML at build time, so browsers draw them without a script. Commands
  that browsers cannot draw are caught with the line number and a hint, as [[read:writing-math]] explains.
- **Figures** are Python files in `figures/`. Each one declares its controls and a `compute()` function that returns
  a description of the plot; a renderer that uses only the standard library turns that into SVG. The build runs it
  once at the default settings, so the page shows a finished figure even without scripts. When a reader moves a
  control, the browser loads a Python runtime compiled for the web in a background worker and runs the *same* file and the same
  renderer again. The heatmap in [[read:attention-from-scratch]] is one of these.
- **Diagrams** are Python functions in `drawings/` that return SVG, drawn once at build time.
- **Checks** run on every page: unknown topics, links to pages that do not exist, citation keys that are not in the
  library, maths that would not render, missing summaries. A production build stops on any error.

## The map, topics and series

Every public page is a node in one graph. Its edges come from the header and the text: "builds on" links, `[[...]]`
mentions, consecutive parts of a series, shared citations and shared topics, each with its own weight. From that
graph the build computes each page's backlinks and related pages, a hub page per topic with the figures of its
pages, a page per series with its parts in order, and a fixed layout for the map at `/explore/`. Hovering a node
there lights up the pages one, two and three steps away. The series on this site,
[[read:gradient-descent|Learning, Visually]], is held together by exactly these links.

## Ask

Every section of every page becomes a passage in `data/passages.json`. The Ask box ranks those passages against a
question with a classic keyword-ranking formula from search engines, gives extra weight to the page you are on and its neighbours
on the map, and answers with the best few sentences and links to their pages. That runs in your browser and needs no
server. If the site owner configures a language model, a second button asks it to write an answer from the same
passages only, with per-visitor and daily limits; nothing is stored.

## Writing and publishing

`python -m tessera studio` opens a local editor with a live preview, an equation helper, figure and citation panels
and the same checks. It listens on 127.0.0.1 only and needs a token printed at launch. Publishing from it (or from
`python -m tessera publish`) checks the page, builds, commits and pushes; the deployed site itself can only answer
questions, never write.

> [!NOTE]
> The runtime needs Markdown, PyYAML, Jinja2, latex2mathml and Pygments; numpy is installed only because the Fourier
> example figure uses it. The code is MIT-licensed and the example posts are CC BY 4.0.
