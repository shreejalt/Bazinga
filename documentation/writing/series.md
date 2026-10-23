# 7. Series

On this page you turn several posts into a series: posts meant to be read in order. You add one line to each post's
header, and Bazinga makes the rest: a page for the series, a list of its parts on every post, and a short set of
highlights for each part.

## Step 1: declare the series in each part

Add `series:` to the header of every post in the series, with the series' name and the part's number:

```yaml
series: {name: "Getting started", part: 1}
```

and in the next post:

```yaml
series: {name: "Getting started", part: 2}
```

Use exactly the same name in every part. The example site has two series built this way: "Getting started" (five
guides) and "Learning, Visually" (four posts).

**What you should see** after the next build:

- **On every part**, under the title, a numbered list of all the parts, with the current one in bold and the others
  as links. The block at the top of the page says **Series: Getting started, part 2 of 5**.
- **A page for the series** at `/series/<slug>/`, where the slug is the name in lowercase with dashes:
  "Getting started" becomes `/series/getting-started/`. It lists the parts in order, each with its kind, month,
  number of interactive figures and highlights, and has a **Start with part 1** button.
- **A page of all series** at `/series/`, with each series' parts.

::clip series-page | The series page: the parts in reading order with their highlights, then opening a part with its list of parts.

### How parts are ordered

Parts are sorted by their `part` number, then by date. They are numbered 1, 2, 3 … in that order on the pages, so the
numbers you write only need to sort correctly: parts 1, 2 and 5 show as 1, 2 and 3. A part number below 1 is an
error.

!!! note "Older and Newer"
    The **Older** and **Newer** links at the very end of a post go to the previous and next post of the same kind by
    date, not to the previous and next part. Inside a series, readers use the list of parts under the title.

A series' parts can be of different kinds: a read, a paper and an article from Elsewhere can be parts of one series.
A series made only of external articles is listed after your own series, with its authors.

## Step 2: see the highlights

Each part on the series page shows a few lines about what it covers. Until you write your own, Bazinga uses the
part's own `##` headings, up to five, and skips headings that start with "Reference", "What came next",
"Connections", "Conclusion", "Further reading" or "Papers". An external article shows its summary instead.

For example, part 2 of "Getting started" shows: *The basics · Numbering and references · Several lines · Matrices and
cases · Patterns you will use often*.

## Step 3: write your own highlights

Write them in `content/series/<slug>.yml`, one list per part, keyed by the part's page id. You can add an
`intro:` that appears under the series' title on both series pages:

```yaml
series: "Getting started"
intro: "Five short guides to writing with Bazinga, from the first post to figures and diagrams."
parts:
  read:welcome:
    - "Every feature a post can hold, each shown next to the text that makes it"
    - "Equations are numbered with {#eq:name} and referred to with [eq:name]"
```

**What you should see:** the intro under the series' name, and these two lines in place of the headings for part 1.
Parts you leave out keep their headings. At most four highlights are shown per part.

## Step 4: or have a model propose them

If you have set up a language model (see [Ask and the wiki](../ask-and-wiki.md)), one command proposes highlights
for every part from the part's own text. Give the series' name or its slug:

```bash
python -m bazinga wiki highlights "Getting started"
```

**What you should see:**

```text
Proposal: <your site folder>/proposals/highlights-getting-started.md
```

Nothing on your site changes. The command writes three files to `proposals/` (which git ignores): a `.md` to read, a
`.json`, and a `.yml` that is ready to copy. It also adds a line to `wiki/log.md`. The proposal looks like this
(shortened; this is real output from a free model):

```yaml
# content/series/getting-started.yml (proposal; copy it there when you accept it)
series: "Getting started"
parts:
  read:welcome:
    []
  read:writing-math:
    - "Bazinga converts LaTeX to MathML at build time so equations render instantly with no JavaScript, scale with text, and work in screen readers."
    - "Name equations with {#eq:name} after the closing $$ to number them, then reference them anywhere with [eq:name]; \\label and \\tag work too."
  read:making-figures:
    - "A figure is one small code file in figures/ that returns a description; the same code runs at build time and in the browser when a control moves."
```

A highlight that mentions a number not found in its page is dropped and listed under **Dropped** in the `.md`, so a
model cannot slip in a figure the page does not contain. Lines over 200 characters are dropped too, at most four are
kept per part, and if the model fails on a part, the reason is listed under Dropped. A part with `[]` got no
highlights and keeps its headings.

### Accept, edit or reject

Read the proposal first. Models make mistakes, and this text will appear on your site.

- **To accept it**, copy the `.yml` into place, then build:

    ```bash
    mkdir -p content/series
    cp proposals/highlights-getting-started.yml content/series/getting-started.yml
    python -m bazinga build
    ```

- **To edit it**, change the lines in `content/series/getting-started.yml` like any other file. Shorten them, fix
  them, add an `intro:`.
- **To reject it**, delete the files in `proposals/`, or just leave them there.

!!! warning "Highlights do not follow your edits"
    Accepted highlights stay as you wrote them. If you change a part a lot, update its lines in
    `content/series/<slug>.yml`, or delete them so the part shows its headings again.

## Turning series off

`series: false` under `features:` in `site.yml` leaves out the `/series/` pages. Posts that still have a `series:`
line keep their list of parts, and the "Series:" link at the top then leads nowhere. So when you turn series off,
also remove the `series:` lines from your posts and the Series item from `nav:`. See
[Configuration](../reference/configuration.md).

## What's next

Your series is in place. Before you publish anything, check the whole site for mistakes: [8. Checking](checking.md).
