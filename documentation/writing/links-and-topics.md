# 6. Links and topics

On this page you connect your post to the rest of your site: link to other pages from the text, say which pages a
reader should read first, and tag the post with topics.

Every link you make here is also a line on your site's map, and it fills the **Connections** section at the end of
the page. See [The map and topics](../map-and-topics.md) for what readers see.

## Page ids

Bazinga names every page by an id: the kind, a colon, and the file name without `.md`. The kind is the folder's
singular name in lowercase:

| File | Id |
|---|---|
| `content/reads/welcome.md` | `read:welcome` |
| `content/papers/attention-is-all-you-need.md` | `paper:attention-is-all-you-need` |
| `content/projects/bazinga.md` | `project:bazinga` |
| `content/elsewhere/the-illustrated-transformer.md` | `article:the-illustrated-transformer` |

## Step 1: link to another page from the text

Write the id between double square brackets. Add `|` and your own words to change the link text:

```markdown
Next, read [[read:writing-math]], or [[read:writing-math|the guide to equations]].
```

**What you should see:** "Next, read *Writing Equations in Bazinga*, or *the guide to equations*." Both are links to
`/reads/writing-math/`. Without your own words, the link shows the other page's title, and it stays right when you
rename that page.

The build checks every link. A wrong id is an error, with the closest id as a hint:

```text
content/reads/broken.md:10: error: [[read:writing-maths]] is not a page of this site
    hint: did you mean read:writing-math?
```

A published page may not link to a draft. That is an error too ("links to a page that is not public yet"), so the
live site never has a link to a missing page. Publish the other page first, or remove the link for now.

!!! tip "Ordinary Markdown links work too"
    `[the guide](/reads/writing-math/)` is a normal link. The checks warn you when its address does not match a page
    of your site. A `[[ … ]]` link is safer, because it follows the page if its title changes, and it adds a line to
    the map.

## Step 2: say what a reader should read first

`builds_on` in the header lists the pages your post assumes the reader knows:

```yaml
builds_on: [read:welcome, read:softmax-and-temperature]
```

**What you should see:**

- A line **Builds on:** in the block at the top of the page, linking to those pages.
- In **Connections** at the end, a small figure of the pages it builds on and the pages that link to it, plus
  **Related**, **Go deeper** and **Go broader** lists.
- On the [map](../map-and-topics.md), your post sits below the pages it builds on.

::clip explore-map | On the map, every page hangs below what it builds on; pointing at one shows what is nearest.

The checks stop the obvious mistakes: an id that does not exist (with "did you mean"), a page that builds on itself,
and a published page that builds on a draft.

## Step 3: tag it with topics

`topics` in the header takes one to four topic slugs:

```yaml
topics: [attention, writing]
```

The slugs must come from `content/topics.yml`, which lists every topic your site allows, in groups:

```yaml
groups:
  - name: Machine learning
    topics:
      - {slug: attention, label: Attention, blurb: "Weighting inputs by relevance, the core of transformers."}
      - {slug: transformers, label: Transformers, blurb: "The architecture built from attention and feed-forward blocks."}
  - name: Craft
    topics:
      - {slug: writing, label: Writing, blurb: "How to explain technical ideas clearly."}
```

**What you should see:**

- A line **Tags:** in the block at the top of the page, with each topic's label as a link.
- A topic page for each topic in use, at `/topics/<slug>/`: the blurb, the pages with that topic in reading order,
  the live figures from those pages, and nearby topics. `/topics/` lists them all by group.

A slug that is not in the file is an error, with a hint:

```text
content/reads/broken.md:6: error: unknown topic 'attenton'
    hint: did you mean attention?
```

More than four topics is an error. A page with no topics gets a warning while it is a draft, and an error once it is
published.

### Adding a topic

Add a line to a group in `content/topics.yml`, with a `slug` (lowercase words and dashes, used in addresses), a
`label` (what readers see) and a one-line `blurb` (the topic page's introduction). Groups only arrange the `/topics/`
page; add, rename or remove them freely. If you remove a slug that pages still use, the build tells you which pages.

## What's next

Your post is connected to the rest of your site. If it is one of several posts meant to be read in order, make them a
series: [7. Series](series.md).
