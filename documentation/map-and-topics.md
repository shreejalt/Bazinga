# The map and topics

Every build draws a map of your whole site at `/explore/` and writes a page for each topic at `/topics/<slug>/`.
You do not draw or maintain either one: they come from the header fields and links you already write. On this page
you will see what the map shows, how a page lands on it, and how topics work.

## The map (`/explore/`)

Open `/explore/` on your site (with `serve` running, <http://127.0.0.1:8000/explore/>).

**What you should see:** every page as a box, coloured by its kind (Read, Paper, Project, Article), each one hung
below the pages it builds on. A legend under the map explains the lines: *builds on*, *also builds on*, *placed by a
shared tag*.

Hover a box (on a phone, tap it once):

1. **Nearest first.** The pages closest to it light up ring by ring, each marked with how many links away it is.
2. **The reading order.** A dot then walks the reading order through the page, numbering each item on the way.
3. Everything neither walk reaches fades until the next hover.

Under the map the hovered page's connections are listed in two columns, **Related, nearest first** and **Reading
order through it** (*Start with*, *You are here*, *Then*). A line under the map says what is playing, for example:

```text
First, nearest first: 10 items within 2 links, one ring every 0.7 s. Then the reading order: 6 items, walked in 4.7 s.
```

Click a box (on a phone, tap it again) to open the page.

::clip explore-map | Hovering pages on the map: rings nearest first, then the reading order.

Above the map you can search by title or word, show one tag (**Any tag**), and filter by kind. The map is wider than
a phone screen; swipe it sideways.

### Series found on the map

Under the map, **Series, generated from the map** finds reading orders in it. Pick two pages and press **Chain
between** for the chain from one to the other, or pick a tag and press **In reading order** for everything under it,
each page after the pages it builds on. These are suggestions to read from; a series you declare yourself is
described in [Writing, step 7](writing/series.md).

## How a page lands on the map

The map is drawn from one graph of your site. A page joins it through:

| You write | What it adds |
|---|---|
| `builds_on: [read:softmax-and-temperature]` in the header | the page hangs below the page it builds on, and comes after it in reading orders |
| `[[read:welcome]]` in the text | a link between the two pages |
| `[@Key]` or `cites: [Key]` | a link through the paper both pages cite |
| `topics: [attention]` | a link to other pages with the same topic (the weakest kind) |
| `series: {name: …, part: n}` | the parts are linked in order |

A page that builds on nothing starts a tree of its own. A page with only topics in common with others is
*placed by a shared tag*. The layout is worked out when the site is built and is the same on every build, so pages
do not jump around between visits.

Every kind is on the map, including the articles in `content/elsewhere/` that open on other sites. Drafts and
scheduled pages are not.

[Writing, step 6](writing/links-and-topics.md) shows how to write each of these.

## Connections on every post

The same graph gives each read and paper its **Connections** section: a small figure of what the page builds on,
cites and links to, and what points back at it, followed by related pages. You do not write it; the build appends
it.

## Topics

Topics are the tags of your site. Pages may only use the topics listed in `content/topics.yml`, so you never end up
with `attention`, `Attention` and `attn` as three tags.

```yaml
groups:
  - name: Foundations
    topics:
      - {slug: linear-algebra, label: Linear algebra, blurb: "Vectors, matrices and the geometry behind them."}
      - {slug: probability, label: Probability, blurb: "Distributions, expectations and how uncertainty is measured."}
  - name: Machine learning
    topics:
      - {slug: attention, label: Attention, blurb: "Weighting inputs by relevance, the core of transformers."}
```

| Field | What it is |
|---|---|
| `slug` | what pages write in `topics: [...]`; also the address, `/topics/<slug>/` |
| `label` | the name readers see |
| `blurb` | the first line of the topic's page |
| `name` (of a group) | a heading on the `/topics/` page; groups only organise that page |

A page uses one to four topics:

```yaml
topics: [attention, transformers]
```

A topic that is not in the list stops the build with a "did you mean". Add, rename or remove topics freely; the build
tells you about pages that still use a removed slug.

### The topic pages

- **`/topics/`** lists every topic that at least one public page uses, in their groups, with how many pages and
  figures each has.
- **`/topics/<slug>/`** starts with the blurb, lists every page with that topic **in reading order** (a page comes
  after the pages it builds on, with a "read first" note), shows the **live figures** those pages use, each one
  working, and lists nearby topics that share pages with this one.

A topic that no public page uses has no page yet.

## What's next

- Write the links that build the map: [Writing, step 6](writing/links-and-topics.md).
- Turn a chain of pages into a series: [Writing, step 7](writing/series.md).
- Let readers ask questions of your pages: [Ask and the wiki](ask-and-wiki.md).
