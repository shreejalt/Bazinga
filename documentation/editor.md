# The Editor

The Editor is Bazinga's writing window. It is a list of your pages, a Markdown pane with a live preview of the real
page, helpers for equations, figures, diagrams and citations, the checks, saved versions, and a Publish button. On
this page you will open it, write in it, and publish from it with a dry run first.

You write every kind of page here: reads and papers for the blog, and projects for your portfolio (pick **Project**
as the kind). Your home page and CV are not edited in the Editor: they live in `site.yml` and `content/cv.yml`; see
[Your portfolio](home-and-cv.md).

It only ever runs on your own computer. Nothing of it is copied into the built site, so the live site cannot be
changed through it.

## Open it

There are two ways. Both open the same Editor.

=== "From serve (most of the time)"

    ```bash
    python -m bazinga serve
    ```

    The Editor starts with the site, on the serve port + 1 (or a free port if that one is taken):

    ```text
      The Editor runs at http://127.0.0.1:8001/ (the Write button opens it)
    ```

    Open <http://127.0.0.1:8000>, then press **Write** in the column on the left of the page (the rail), or
    **Edit this page** on a page.

    `serve --no-editor` leaves the Editor and the Write button out; `serve --editor-port 9001` picks its port.

=== "On its own"

    ```bash
    python -m bazinga editor
    ```

    ```text
    Bazinga Editor for <your site folder>
      http://127.0.0.1:53817/?token=…
      Local only: this address works on this computer and nowhere else. Press Ctrl+C to stop.
    ```

    Your browser opens at that address. Add `--port 9000` to choose the port and `--no-browser` to open it
    yourself.

**What you should see:** a page called **Your pages**, with every page of the site, its status and its checks.

![The Editor's list of pages](assets/images/editor-library.jpg){ .shot }

## Only you see the Write button

The **Write** button in the rail and the **Edit this page** button on a page appear only while you run
`python -m bazinga serve` on your own computer. They are added to the page as it is served to you; they are never
written into the built site.

| Where | Write and Edit this page | The Editor |
|---|---|---|
| `python -m bazinga serve` on your computer | shown | runs on `127.0.0.1`, for you only |
| `python -m bazinga build` (what your host publishes) | not there | not there: none of its files are in `_site/` |
| Your live site | not there | cannot be reached |

So visitors to your live site never see these buttons, and nobody can edit your site from the internet. A test in
`tests/` builds the site and fails if any Editor file or button ends up in `_site/`.

## Your pages

The list shows every page with a pill for its status (**Draft**, **Scheduled** or **Published**), its kind, its
date, its word count, how many figures it has, when you last edited it, and whether its checks pass.

- The tabs **All**, **Drafts**, **Scheduled** and **Published** filter by status.
- **All kinds** filters by kind (Reads, Papers, Projects, Elsewhere on the example site).
- **Search titles, summaries, topics** finds a page as you type. ++cmd+k++ (++ctrl+k++ on Windows and Linux)
  jumps to the search box.
- **Live site** opens your published site, at the `origin` set in `site.yml` (until you set it, that is the
  placeholder `https://example.com`). The moon button switches the Editor between light and dark.

## Start a post

1. Press **New post**.
2. Type a **Title**, for example `My first post`.
3. Pick a **Kind** (Read, Paper, Project or Article on the example site).
4. Press **Create draft**.

**What you should see:** the writing screen, with your title, a summary to replace, and a starting text that shows
the basics: two headings, an equation with a number, a link, a citation and a tip box. Replace it with your own. The
file is `content/reads/my-first-post.md`, with `status: draft` and the topic `writing`.
A draft is private until you publish it.

::clip editor-write | Write opens the Editor; a new post, a paragraph and an equation, and the preview following.

## The writing screen

- **Left:** the title, the summary, then the body in Markdown. Equations, `[[links]]`, `[@citations]` and
  `::figure` lines are marked up as you type, and completion helps with page ids, citation keys, figure names and
  LaTeX commands.
- **Right:** the preview. It is the real page, drawn by the same code as the site, with its contents list, its
  figures working and a red **Draft** note. It follows your typing within a moment and keeps its scroll position.
  The two buttons above it switch between **Wide** and **Phone width**, and the arrow opens it in a new tab.
- **Top bar:** **Pages** (back to the list), the status pill and **Saved**, **Earlier versions** (the clock),
  **Details**, the checks button (**Checks pass**, or the number of problems), **Show or hide the preview** (the
  eye), light or dark, and **Publish**.

The Editor saves by itself about two seconds after you stop typing. ++cmd+s++ saves at once and keeps a version.

Drag the line between the two panes to resize them. On a narrow window (under about 980 px) the preview is hidden;
the eye button swaps between text and preview.

If you change the same file in another program while the Editor has it open, a bar says **This page was changed
outside the Editor since you opened it.** Press **Load the file** to take the other version, or **Keep my version**
to overwrite it.

### The toolbar and the "/" menu

The row of icons above the text, and the menu you get by typing `/` at the start of an empty line, hold the same
items:

| Item | What it puts in |
|---|---|
| Heading | `## A section title` |
| Equation… | an equation, with a live preview and templates (++cmd+m++) |
| Inline math | `$x^2$` inside a sentence |
| Figure… | an interactive figure |
| Diagram… | boxes and arrows, a flowchart, a timeline or a tree, written as text |
| Drawing from code… | a diagram drawn by a small code file |
| Citation… | a paper by arXiv id or DOI |
| Link to page… | `[[another page]]` (++cmd+k++) |
| Callout | `> [!NOTE]`, a highlighted box |
| Table | a small table to fill in |
| Image upload | PNG, JPEG, GIF or WebP |
| Code block | fenced code |
| Footnote | `[^1]` with its text at the end |
| Divider | `---` |

++cmd+slash++ opens the same menu anywhere in a line.

### Keyboard shortcuts

On Windows and Linux use ++ctrl++ where this says ++cmd++.

| Keys | What they do |
|---|---|
| ++cmd+s++ | save now and keep a version |
| ++cmd+p++ | show or hide the preview |
| ++cmd+slash++ | the "/" menu at the cursor |
| ++cmd+m++ | the equation helper |
| ++cmd+k++ | link to a page |
| ++cmd+b++, ++cmd+i++ | bold and italic around the selection |
| ++cmd+enter++ | insert, in the equation and diagram helpers |
| ++esc++ | close a dialog |

Close the **Details** or **Checks** drawer with its × button, or press the same button again.

## The helpers

### Equation

**Equation…** opens a box where you type LaTeX, or build it from a palette (Templates, Structures, Greek,
Operators & relations, Arrows, Accents & fonts, Big operators, Brackets). The rendered equation shows as you type.
If the formula has a mistake, the message says where and what to write instead, the same message the build would
give. Choose **On its own line** or **Inside a sentence**, and give a displayed equation a name if you want to refer
to it as `[eq:name]`. ++cmd+enter++ inserts it.

Tick **Number this equation** to number it; **Insert reference** puts `[eq:name]` for an equation already on the
page. **Structures** builds a matrix, cases or a derivation of lined-up lines. Click an equation in your text to open
it here again (**Update equation**). With a model set up, describe the equation in words and press **Write it**.

[Writing, step 3](writing/equations.md#in-the-editor) covers the LaTeX itself and has a clip of this helper.

### Figure

**Figure…** (the figure button in the toolbar) shows **Your figures**, each one live with how it was made (**Made
with the form**, **Form, then code** or **Code**), its controls and the pages it is used in. Pick one to try it and place it in the text, or press **New figure** and choose:

- **Fill in a form:** no code. Pick a kind, type expressions such as `a*sin(f*x)`, add sliders, readouts and
  presets, and watch the preview and its test as you type. **Save and place in the text** writes
  `figures/<name>.py` and adds `::figure <name>` at the cursor.
- **Start from an example:** a working figure file with a comment on every part.

When a model is set up (see [Ask and the wiki](ask-and-wiki.md)), a third way appears that drafts a figure from a
description. The figure is always tested before you can save it.

[Interactive figures](figures.md#make-one-with-the-form-no-code) explains each kind and the code behind them, with a
clip of the form.

### Diagram

**Diagram…** opens a text box with examples (Pipeline, Model architecture, Flowchart, Timeline, Tree) and a
preview in **Wide** and **Phone** layouts. Write the boxes and arrows, watch the drawing, and press
**Insert diagram**. A mistake turns the line red and says what to write instead. An existing diagram block in the
text has an **Edit diagram** button that opens it here again (**Update diagram**). **From a code file…** switches to
Drawing from code. [Diagrams](diagrams.md) has the syntax and a clip of this helper.

### Drawing from code

**Drawing from code…** lists the drawings in `drawings/` (for example `pipeline.overview`). Pick one to see it, edit
its code, give it a caption and press **Insert drawing**, or press **New drawing** to start from a starter. See
[Diagrams](diagrams.md#diagrams-from-code).

### Citation

**Citation…** has **Look it up**: paste an arXiv id or URL, or a DOI, and the paper is fetched (this needs the
internet), shown, saved to `content/references.yml` and cited as `[@Key]`. Below it, **Or cite one you already
have** lists your references. See [Writing, step 4](writing/citations.md).

### Link to page

**Link to page…** (++cmd+k++) lists every page with its status and id, such as `read:welcome`. Pick one and
`[[read:welcome]]` goes in. Readers see the page's title as the link. Select some words first and they become the
link text: `[[read:welcome|these words]]`.

### Image upload

Paste or drop an image into the text, or use **Image upload**. It is saved under `static/uploads/` and placed in the
text. PNG, JPEG, GIF, WebP and AVIF are accepted, up to 8 MB; SVG and HTML are refused. The file name is put in the
brackets as a description. Replace it with what the picture shows; the checks warn about an image without one.

## Details

**Details** opens the page's header as a form:

| Field | What it is |
|---|---|
| Title | the page title |
| Address | the page's address, such as `example.com/reads/my-first-post/`. **Rename** changes it and updates links to it |
| Summary | shown under the title, in lists and on the map; two or three sentences |
| Description | what search engines show, up to 155 characters, with a counter |
| Topics | one to four, from your topics list |
| Series, part | pages in the same series are read in part order |
| Builds on | pages a reader should read first |
| Share image | optional, shown when the page is shared |
| Date, Updated | publishing sets today's date, or schedule it from Publish |

When a model is set up, Description gets a **Suggest** button. Type a topic that does not exist yet and choose it to
add it to `content/topics.yml`. Renaming a published page changes its live address the next time you publish.

## Checks

The checks button opens the **Checks** drawer. With nothing wrong it says **All clear**. Otherwise it lists each
problem (an equation that will not render, an unknown link, citation or topic, an image without a description, a
missing summary, a description that is too long, and so on). Click one to jump to its line or field. These are the
same checks as `python -m bazinga check` and the build; see [Writing, step 8](writing/checking.md).

## Versions

**Earlier versions** (the clock) lists saved copies of the page, newest first, with their word counts. Pick one to
read it and restore it. A version is kept each time you press ++cmd+s++, and at most once a minute while you write;
the last 60 are kept. **Restore this version** keeps your current text as a version first. They are kept on this
computer only, in `.studio/history/`, which git ignores.

## Publish

**Publish** checks, builds, commits and pushes the page, the same steps as `python -m bazinga publish`; each step is
explained in [Writing, step 9: Publishing](writing/publishing.md#step-2-publish).

It opens a dialog with two tabs, **Publish now** and **Schedule**. On a published page the first tab is **Publish
changes**; on a scheduled page the second is **Reschedule**. Both have a third tab, **Unpublish**. On a page that is
already published, **Publish changes** keeps its first date and sets `updated:` to today.

Before you publish for real, tick **Dry run**: it goes through every step on a copy of the site and changes nothing.

**What you should see:** the steps tick off one by one: Check the page, Set status and date, Test its figures, Build
the site, Update the wiki files, Suggested links and topics, Commit, Push, Deploy command, Live address. A dry run
ends with **The dry run went through every step** and the address the page would have.

::clip editor-publish | Publish with a dry run: every step runs on a copy, and nothing changes.

Without **Dry run** the same steps run for real. Errors stop it; warnings need the **Publish anyway** box ticked.
When a model is set up, **Ask for links and topics** shows suggestions you can **Accept** or **Reject**; nothing
changes unless you accept. **Schedule** sets a future date instead, and **Unpublish** turns the page back into a
draft. Its settings and what to do when a push fails are in [Writing, step 9: Publishing](writing/publishing.md).

## Why it is safe

- It listens on `127.0.0.1` only, so other computers cannot reach it.
- It needs a new key (the `token` in its address) every time it starts. The key is swapped for a cookie and leaves
  the address bar.
- It refuses requests from other sites and other host names.
- Previews of your pages and figures open from a second local port that can only read. A page's script or a
  figure's code runs there, so it cannot save anything through the Editor.
- Every change it saves needs a write key that is new each time the Editor starts and that only the Editor's own
  page has. You never see it or type it.
- It can only write inside `content/`, `figures/`, `drawings/`, `static/uploads/` and your references and topics
  files.
- None of its files are copied to `_site/`, and a test checks that.

## What's next

Next, make figures with the form or in code: [Interactive figures](figures.md).

- Follow the writing path from the start: [Writing, step 1](writing/first-post.md).
