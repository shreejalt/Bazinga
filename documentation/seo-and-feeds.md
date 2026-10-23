# SEO and feeds

In this guide you will see what every build writes for search engines, feed readers and language models, and the
few header fields that steer it. There is nothing to install or switch on: it all comes with `python -m bazinga build`.

The examples below come from building the example site with `origin: "https://example.com"`.

## What each page carries

Open any built page, for instance `_site/reads/welcome/index.html`, and look at its `<head>`:

```html
<title>Welcome to Bazinga — Your Name</title>
<meta name="description" content="A tour of Bazinga's Markdown: equations, citations, page links, callouts, footnotes, tables, code, and interactive figures.">
<link rel="canonical" href="https://example.com/reads/welcome/">
<meta property="og:site_name" content="Your Name">
<meta property="og:title" content="Welcome to Bazinga">
<meta property="og:description" content="A tour of Bazinga's Markdown: …">
<meta property="og:url" content="https://example.com/reads/welcome/">
<meta property="og:type" content="article">
<meta property="og:locale" content="en">
<meta name="twitter:card" content="summary">
<meta property="article:published_time" content="2026-10-20">
<meta property="article:author" content="Your Name">
<link rel="alternate" type="application/atom+xml" title="Your Name" href="/feed.xml">
<link rel="alternate" type="text/markdown" href="/reads/welcome/index.md">
<link rel="describedby" type="text/markdown" href="/llms.txt">
<script type="application/ld+json">{"@context":"https://schema.org","@type":"BlogPosting","headline":"Welcome to Bazinga", ...}</script>
```

| Tag | Where the value comes from |
|---|---|
| `<title>` | the page title, plus " — " and `site.name` while the whole stays within 65 characters |
| description | the page's `description:`, else its `summary:` cut at a sentence or clause near 155 characters; on the home page, `site.description`, else `site.tagline` |
| canonical (the one official address of the page) | `site.origin` + the page's address |
| Open Graph (what chat apps and social sites show in a link preview) | title, description, address, type (`article` for reads, papers and projects), language from `site.language` |
| share image | the page's `cover:`, else `site.avatar` if that file exists; without either there is no `og:image` |
| `twitter:card` | `summary_large_image` when the page has a cover, else `summary` |
| `article:*` | the page's `date`, its `updated` when set, and `site.author` |
| JSON-LD (a short description of the page that search engines read) | a `BlogPosting` for reads, papers and projects (headline, description, dates, topics as keywords, author with your `links` as `sameAs`); `WebSite` and `Person` on the home page; `WebPage` elsewhere |

!!! tip "The home page's title"
    The home page uses `home.title`, and the site name is added after it while it fits. The example's
    `"Your Name — Machine Learning Notes"` therefore becomes `Your Name — Machine Learning Notes — Your Name`.
    Leave your name out of `home.title` to avoid the repeat.

!!! tip "For a portfolio"
    The home page tells search engines who you are: a `Person` with your `site.author` and every address in
    `site.links` as `sameAs`, so your GitHub, LinkedIn and Scholar profiles are tied to your name. Fill in
    `site.description`, `home.title` and `site.links`; a portfolio needs nothing else here.

## Header fields that matter

```yaml
---
title: "Attention, Step by Step"
date: 2026-10-20
updated: 2026-11-02
summary: "Two or three sentences for lists, search and the map."
description: "Attention as weights from similarities, step by step, with a figure you can move."
cover: static/uploads/attention.png
topics: [attention, transformers]
---
```

- **`description`** is optional, and at most 155 characters. A longer one is an error in the checks and stops the
  build, with the message `the description is 171 characters; search engines cut it at 155` and the hint
  `shorten it, or remove it to use the summary`. Without it, the summary is cut for you.
- **`updated`** says when a page was really revised. It becomes `article:modified_time`, the JSON-LD
  `dateModified`, the sitemap's `lastmod` and the feed's `updated`. Publishing a page again from the Editor sets it.
- **`cover`** is the share image for that page.

## Files at the root of the site

| File | What it holds |
|---|---|
| `/sitemap.xml` | the home page, every list page, every public page, the CV, topic pages, series pages, the map and Ask, with `lastmod` from `updated` or `date` |
| `/robots.txt` | allows everything and points at the sitemap |
| `/feed.xml` | an Atom feed of the 30 newest pages, with summaries, topics and the full text |
| `/llms.txt` | a short guide to the site for language models (see below) |
| `/llms-full.txt` | every public page as Markdown, in one file |
| `/<kind>/<slug>/index.md` | a Markdown copy of each page, next to its `index.html` |
| `/404.html` | the "Page not found" page ("There is nothing at this address."); static hosts such as Vercel, Netlify and GitHub Pages serve a file with this name for an address that does not exist |

The example site's `robots.txt`:

```text
User-agent: *
Allow: /

Sitemap: https://example.com/sitemap.xml
```

and the start of its `sitemap.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/</loc><lastmod>2026-10-20</lastmod></url>
  <url><loc>https://example.com/reads/</loc><lastmod>2026-10-20</lastmod></url>
  <url><loc>https://example.com/papers/</loc><lastmod>2026-10-19</lastmod></url>
```

Drafts and scheduled pages never appear in any of these files. A `--drafts` build writes no sitemap or feed, and its
`robots.txt` says `Disallow: /`.

Entries of an external kind, such as Elsewhere, live on other sites: their list page is in the sitemap, but the
entries are not in the sitemap, the feed or `llms.txt`.

On a site under a folder (such as `https://you.github.io/notes`), every address above carries the folder. Search
engines read `robots.txt` only at the root of the host, so submit `https://you.github.io/notes/sitemap.xml` in their
webmaster tools yourself.

## The feed

The feed is Atom, at `/feed.xml`, linked from every page's head so feed readers find it from any address. Each entry
carries the title, address, published and updated dates, summary, topics and the page's full HTML. The figures are
in it as they were drawn at build time, so they show in feed readers too.

Turn it off with `features: {feed: false}` in `site.yml`.

## llms.txt and the Markdown copies

`/llms.txt` follows the [llmstxt.org](https://llmstxt.org/) layout: the site name as a heading, the site
description as a quote, then a list per kind with a link and the summary of each page. The example's begins:

```markdown
# Your Name

> Reads, paper explainers and projects in machine learning, with interactive figures and a map of how every page connects.

Pages by Your Name. Every page below is also available as Markdown at the same address followed by `index.md`. The whole site as one file: https://example.com/llms-full.txt

## Reads

- [Drawing Diagrams](https://example.com/reads/drawing-diagrams/index.md): How to draw a diagram by writing it as text in a post: ...
```

Each page's Markdown copy starts with its title, summary, date and topics, then the body:

```markdown
# Welcome to Bazinga

> A tour of everything a post can hold: equations that render without scripts, ...

Published 2026-10-20 · topics: writing, tools, visualization · source: https://example.com/reads/welcome/
```

`features: {llms_txt: false}` leaves out `llms.txt` and `llms-full.txt`. The per-page Markdown copies are always
written.

## Checklist before you launch

1. `site.origin` is your real address, with no `/` at the end.
2. `site.description` (155 characters at most) says what the site is.
3. `python -m bazinga check` reports no errors.
4. After deploying, open `https://<your address>/sitemap.xml` and `/feed.xml` and check the addresses start with your
   origin.
5. Submit the sitemap in your search engine's webmaster tools, if you use them.

## What's next

Next, every command and option in one place: [Commands](reference/commands.md).

- Every key in one table: [Configuration reference](reference/configuration.md).
