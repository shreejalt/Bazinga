# Writing

This section walks you from an empty folder to a published post, one step at a time. Read it top to bottom the first
time. Each page ends with a link to the next one.

You need a working copy of the template first. If you have not built the example site yet, do
[Getting started](../getting-started.md) and come back.

## The path

| Step | Page | You will |
|---|---|---|
| 1 | [Your first post](first-post.md) | create a post with one command, fill in its header and watch it in the browser |
| 2 | [Sections and contents](sections.md) | learn how headings become the numbered table of contents, with page numbers |
| 3 | [Equations](equations.md) | write maths that renders in every browser, number it and refer to it |
| 4 | [Citations](citations.md) | add papers to `content/references.yml` and cite them with `[@Key]` |
| 5 | [Figures and diagrams in a post](figures-in-posts.md) | place a figure readers can move, a drawing, or a diagram written as text |
| 6 | [Links and topics](links-and-topics.md) | link pages to each other, say what a page builds on, and tag it |
| 7 | [Series](series.md) | group posts into a series and give each part its highlights |
| 8 | [Checking](checking.md) | find every problem, with its line and a fix, before you publish |
| 9 | [Publishing](publishing.md) | turn a draft into a live page, from the Editor or a terminal |

## Two ways to write

Every step works in two ways, and both change the same file:

- **In any text editor.** You edit `content/reads/<name>.md` and the page in your browser reloads when you save.
  This section shows this way, because every step is then a line you can copy.
- **In the Editor**, a writing window with a live preview that runs on your own computer. It has buttons for the
  same things: equations, figures, citations, links and publishing. See [The Editor](../editor.md).

!!! tip "Keep the server running"
    Start `python -m bazinga serve --drafts` once in a terminal and leave it open while you write. It rebuilds the
    site every time you save a file and reloads the page in your browser.

## What's next

Start with step 1: [Your first post](first-post.md).
