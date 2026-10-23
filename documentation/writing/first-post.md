# 1. Your first post

On this page you create a post with one command, fill in its header, and watch it appear in your browser as you
type. It takes about five minutes.

!!! note "Which `python`?"
    The commands below say `python`. Use the one in your site's virtual environment: either activate it first
    (`source .venv/bin/activate`) or write `.venv/bin/python` instead of `python`. All commands run in your site's
    folder, the one with `site.yml` in it.

## Step 1: create the file

Run this in your site's folder:

```bash
python -m bazinga new "My first post"
```

**What you should see:**

```text
Created content/reads/my-first-post.md (a draft). Preview it with: python -m bazinga serve --drafts
```

The file name comes from the title: lowercase words joined by dashes. If a file with that name already exists, the
command stops and says so:

```text
content/reads/my-first-post.md already exists; pick another title or pass --slug
```

Pick your own file name with `--slug` (the slug is the file name without `.md`, and the last part of the page's
address), and another folder with `--kind` (the folders are the kinds in `site.yml`;
the example site has `reads`, `papers`, `projects` and `elsewhere`):

```bash
python -m bazinga new "What I built this summer" --kind projects --slug summer-project
```

::clip new-post | Creating a post from the terminal and opening the new file.

## Step 2: look at the header

Open `content/reads/my-first-post.md`. The part between the two `---` lines is the header. It looks like this:

```yaml
---
title: "My first post"
date: 2026-10-22
status: draft
summary: "Two or three sentences that say what the reader will learn. Lists, the map and search results show them."
topics: [writing]
# description: "Optional: up to 155 characters for search engines (otherwise cut from the summary)."
# series: {name: "My series", part: 1}
# builds_on: [read:welcome]
# cites: [Vaswani17]
---
```

Below the header is a short example body: an opening line, two sections, an equation, a link and a tip. Replace it
with your own text whenever you like.

Change the summary to your own two or three sentences, and pick one to four topics from `content/topics.yml`:

```yaml
summary: "What a softmax temperature does, in two minutes, with a figure you can move."
topics: [attention, writing]
```

## The header fields

| Field | Needed? | What it does |
|---|---|---|
| `title` | always | The page's title. |
| `date` | to publish | `YYYY-MM-DD`. A date in the future schedules the page: it goes live on the first build on or after that day. |
| `status` | no | `draft` or `published`. Leave it out and the page counts as published. |
| `summary` | to publish | Two or three sentences. Shown at the top of the page, in lists, on the map and in search results. Keep it under 320 characters. |
| `topics` | to publish | One to four topic slugs from `content/topics.yml`. See [Links and topics](links-and-topics.md). |
| `description` | no | Up to 155 characters for search engines. Without it, the summary is cut to fit. |
| `builds_on` | no | Pages a reader should read first, as ids such as `read:welcome`. See [Links and topics](links-and-topics.md). |
| `cites` | no | Citation keys from `content/references.yml`. Keys you cite in the text with `[@Key]` are added for you. See [Citations](citations.md). |
| `series` | no | `{name: "…", part: 2}` puts the page in a series. See [Series](series.md). |
| `updated` | no | The date of a real revision, `YYYY-MM-DD`. Publishing a page again sets it for you. |
| `cover` | no | An image under `static/` used when the page is shared. |
| `seo_title` | no | A different `<title>` for search engines. The heading on the page stays `title`. |
| `short` | no | A short name used where space is tight: the map's "chain between" pickers and the "Sits under" trail. |
| `first_published` | no | Free text such as `"Medium, March 2021"`, shown as "First published: …" in the header block of a read or paper. |

!!! note "What a draft is"
    A page with `status: draft` is never written to the public site, the sitemap, the feed or the search data. It
    shows only in the Editor and in previews made with `--drafts`. The same is true of a page whose `date` is still
    in the future.

### Other kinds of page

The example site has four kinds, each a folder in `content/`:

| Folder | Id starts with | What it is |
|---|---|---|
| `content/reads/` | `read:` | A concept explained. This is what this section uses. |
| `content/papers/` | `paper:` | One paper explained. Add `explains: [Key]` with the paper's citation key. |
| `content/projects/` | `project:` | A project page. It has its own layout (Overview, Write-up, Related). |
| `content/elsewhere/` | `article:` | An article that lives on another site. It has no body: the header has `external:` (the address), `author:` and `publication:`, and the entry opens there. |

Look at `content/papers/attention-is-all-you-need.md`, `content/projects/bazinga.md` and
`content/elsewhere/the-illustrated-transformer.md` for one working example of each. The kinds themselves are set in
`site.yml`; see [Configuration](../reference/configuration.md).

### Project pages {#project-pages}

A project page takes a few more optional header fields. All of them were tried on a test page; this is what each one
shows:

```yaml
type: Research                 # "Research project" at the foot of the rail, and the Type column of /projects/
stack: "Python · NumPy"        # under the type, at the foot of the rail
tagline: "One thing, done well."              # a large line under the title
lead: "A longer opening line for the page."   # the opening paragraph (without it, the summary is used)
from: "Example Labs"           # adds a facts box: Type, From, Headline result (the summary) and Tags
github: "https://github.com/your-handle/demo-tool"   # "Source on GitHub" buttons, and a GitHub link in lists and the CV
usage: |                       # a Usage section, shown as a code block
  pip install demo-tool
limitations:                   # a Limitations section, as a list
  - Only works on small inputs.
credit: "Built with help from a friend."      # a small note under Connected work
order: 1                       # sorts the /projects/ list (smaller first; default 99, then by title)
```

What you should see: the page opens with the title, the tagline and the lead, then **Usage**, your write-up,
**Connected work** and **Limitations**. The `bazinga.md` example uses `type`, `stack` and `short`. (A `launch:` field is read into the site's data too, but
the default theme does not show it.)

## Step 3: watch it in the browser

Start the local server with drafts included:

```bash
python -m bazinga serve --drafts
```

**What you should see:**

```text
Building Your Name …
  built 16 pages in 0.94s
  The Editor runs at http://127.0.0.1:8001/ (the Write button opens it)

  Serving at http://127.0.0.1:8000/  (Ctrl+C to stop; pages reload when you save)
```

Open <http://127.0.0.1:8000/reads/my-first-post/>. At the top is a box that says **Draft. Only you can see this
preview; it is not on the public site.**

Now change a sentence in the file and save. The terminal prints

```text
  changed: my-first-post.md
  built 16 pages in 0.91s
```

and the page in your browser reloads by itself.

!!! tip "No drafts?"
    Without `--drafts`, the server shows only published pages, exactly like the live site. Your new post is then
    missing, because it is still a draft.

::clip editor-write | The same steps in the Editor: a new post, some text, and the preview following along.

## Step 4: write the body

Below the header, write ordinary Markdown: paragraphs, `## Headings`, lists, tables, code blocks, links and images.
Bazinga adds a few things of its own, and the next pages cover each one:

| You write | You get | Page |
|---|---|---|
| `## A heading` | a numbered section and a line in the table of contents | [Sections and contents](sections.md) |
| `$x^2$` and `$$ … $$` | an equation | [Equations](equations.md) |
| `[@Vaswani17]` | a numbered citation | [Citations](citations.md) |
| `::figure softmax_temperature` | a figure readers can move | [Figures and diagrams](figures-in-posts.md) |
| `[[read:welcome]]` | a link to another page, and a line on the map | [Links and topics](links-and-topics.md) |
| `> [!TIP]` | a coloured box (also `NOTE`, `WARNING`, `KEY`) | [below](#markdown) |

The example site's own guide, `content/reads/welcome.md` (`/reads/welcome/` when you serve it), shows every feature
next to the text that makes it.

## Boxes, footnotes and the rest of Markdown {#markdown}

Everything else is the Markdown you know, with a few small additions. Each line below was built on a test page.

| You write | You get |
|---|---|
| `> [!NOTE]`, `> [!TIP]`, `> [!WARNING]`, `> [!KEY]` on the first line of a quote | a coloured box titled Note, Tip, Warning or Key idea |
| `> [!IMPORTANT]`, `> [!CAUTION]` | the same boxes as Key idea and Warning, titled Important and Caution |
| `> [!TIP] Your own title` | the box with your title instead |
| `==a highlight==` and `~~a correction~~` | marked text and struck-through text |
| `a claim.[^1]` and, anywhere below, `[^1]: The note.` | a numbered footnote at the end of the page, with a link back |
| `![What it shows](static/uploads/tiles.svg "A caption.")` | the picture as a figure, with the quoted text as its caption |
| a Markdown table: a row of `---` cells under the header row | a table; a `--:` cell aligns its column right; wide tables scroll sideways on phones |
| a fenced code block with a language, such as ```` ```python ```` | code coloured when the site is built |
| `"quotes"`, `--` and `...` | curly quotes, a dash and an ellipsis |

```markdown
> [!KEY] The one thing to remember
> Dividing the scores by a temperature sharpens or flattens the softmax.

Softmax is a smooth arg max.[^name] It is ==differentiable everywhere==.

[^name]: "Soft arg max" would be the more accurate name.

![A mosaic of tiles](static/uploads/tiles.svg "Every page is a tile; links join them.")
```

What you should see: a box titled "The one thing to remember", a highlighted phrase, a small footnote
number that jumps to the note at the end, and the picture with its caption under it.

Two things the checks watch for. A box type that does not exist, such as `> [!SHOUT]`, stays a plain quote and gives
a warning: `[!SHOUT] is not a callout type`. A picture with empty brackets, `![](…)`, gives the warning
`an image has no alt text`; describe the picture in the brackets for readers who cannot see it. Put pictures in
`static/` (the Editor's image upload puts them in `static/uploads/`).

## What's next

Your post has a title, a summary and some text. Next, see how its headings turn into a numbered table of contents:
[2. Sections and contents](sections.md).
