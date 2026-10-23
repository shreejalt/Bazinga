# Theme and customising

In this guide you will change how the site looks and what it holds: colours, fonts, the menu, the kinds of pages,
and, when settings are not enough, the theme's own files. You never edit the engine to do any of this.

There are two levels:

1. **`site.yml`**: colours, fonts, the menu (`nav:`), the kinds of pages (`kinds:`) and which parts are on
   (`features:`).
2. **A `theme/` folder** in your site: your own copy of any template or stylesheet, which wins over the built-in one.

## Colours

The default look is a paper sheet on a recycled-paper ground, dark ink, and one blue accent. Set the accent in
`site.yml`:

```yaml
theme:
  accent: "#0F52BA"
```

The accent colours links, the current menu item and the read boxes on the map. A darker shade for hover is worked
out from it.

You can also set any of these, each a hex colour such as `"#FFFFFF"`. Leave one empty to keep the default.

| Key | What it colours | Default |
|---|---|---|
| `accent_dark` | the darker accent (hover) | worked out from `accent` |
| `ground` | the page around the sheet | `#E6DECD` |
| `paper` | the sheet | `#FBF7EC` |
| `tint` | soft fills (code, boxes) | `#F2EBDB` |
| `ink` | the main text | `#1D1A15` |
| `ink_2`, `ink_3` | quieter text | `#4A443A`, `#655D51` |
| `rule_2`, `rule_3` | lines and borders | `#CBC1AD`, `#E4DBC9` |
| `ref` | citations and the map's rings | `#A34A12` |
| `alert` | warnings | `#B8241A` |

A value that is not a hex colour stops the build with a message such as
`theme.paper must be a hex colour such as '#E6DECD'`.

**What you should see:** with `accent: "#2E7D32"` and `paper: "#FFFFFF"`, links turn green and the sheet turns
white after the page reloads. Figures and diagrams follow too, because they use style names, not colours.

## Fonts

Fonts are Google Fonts family names:

```yaml
theme:
  font_text: "STIX Two Text"
  font_ui: "Courier Prime"
  font_code: "Courier Prime"
  font_math: "STIX Two Math"
```

| Key | Used for |
|---|---|
| `font_text` | the body text |
| `font_code` | code, and also the default theme's labels, menu and buttons |
| `font_math` | equations; it needs a font with a maths table, such as STIX Two Math |
| `font_ui` | the font is downloaded, but the default theme does not use it (see below) |

Each family named here is loaded from Google Fonts with the weights the theme needs.

!!! note "Honest notes on three theme keys"
    - **`font_ui`**: the default theme draws its interface in the code font. Setting `font_ui` loads the font
      but changes nothing you can see. To change the interface font, change `font_code` (code changes with it),
      or override the stylesheet as shown below.
    - **`mode`**: accepted (`auto`, `light` or `dark`) but not used. The default theme is light only.
    - **`width`**: checked (480 to 1200) but not used by the default theme, whose column width is set in its
      stylesheet.

## The menu

The rail on the left lists `nav:` in order. `href` is a path on your site or a full address.

```yaml
nav:
  - {label: Home, href: /}
  - {label: Reads, href: /reads/}
  - {label: Papers, href: /papers/}
  - {label: Projects, href: /projects/}
  - {label: Series, href: /series/}
  - {label: Elsewhere, href: /elsewhere/}
  - {label: Explore, href: /explore/}
  - {label: Ask, href: /ask/}
  - {label: CV, href: /cv/}
```

Every item needs a `label` and an `href`, or the site does not build. On the home page, the rail shows the page's own
sections instead, then the Series, Ask and CV items from this list.

## Kinds of pages

Each kind is a folder `content/<kind>/` and a list page `/<kind>/`. The example site has four:

```yaml
kinds:
  reads:
    label: Reads
    singular: Read
    blurb: "Explanations of a concept, built from several papers rather than one."
    placeholder: "filter: attention, softmax, gradient ..."
  papers:
    label: Papers
    singular: Paper
  projects:
    label: Projects
    singular: Project
  elsewhere:
    label: Elsewhere
    singular: Article
    external: true
    word: articles
```

| Field | What it does | Default |
|---|---|---|
| `label` | the list page's title and its button on the home page | the folder name, capitalised |
| `singular` | one item's name; also the start of page ids (`Read` gives `read:welcome`) | `label` without its last "s" |
| `role` | the layout: `read`, `paper`, `project` or `external` | `paper` for `papers`, `project` for `projects`, else `read` |
| `external` | entries that live on another site (no body) | `false` |
| `blurb` | the line under the list's title | "<label> by <author>." |
| `placeholder` | the hint in the list's filter box | "filter: a word from a title or a topic …" |
| `word` | what the list calls its items | the label in lower case |

The roles:

- **read**: a concept explained, in the memo layout (header block, summary, contents, numbered sections,
  Connections).
- **paper**: one paper explained; its header names the paper with `explains: [KEY]`.
- **project**: a project page.
- **external**: attributed entries with no body. Their header has `external:` (the address), `author:` and
  `publication:`. They are listed, placed on the map, and open where they were published.

A kind's name must be lowercase letters, digits or `-`, because it is a folder and part of the address. When you
define `kinds:`, your list replaces the default kinds; it is not added to them.

## Turning parts on and off

```yaml
features: {ask: true, explore: true, series: true, feed: true, llms_txt: true, credit: true}
```

| Key | When off |
|---|---|
| `ask` | no `/ask/` page and no Ask button |
| `explore` | no `/explore/` map and no Explore section on the home page |
| `series` | no `/series/` pages |
| `feed` | no `/feed.xml` |
| `llms_txt` | no `/llms.txt` or `/llms-full.txt` |
| `credit` | no small "Made with Bazinga" link at the foot of the side rail |

Remember to take the matching item out of `nav:` too.

## Your own copy of a theme file

Every template, stylesheet and script of the default theme lives in `bazinga/theme/`. To change one, copy it to the
same path under a `theme/` folder in your site and edit the copy. The build takes `theme/<path>` first and falls back
to `bazinga/theme/<path>` for everything you did not copy.

```bash
mkdir -p theme/templates
cp bazinga/theme/templates/404.html theme/templates/404.html
```

Now edit `theme/templates/404.html` and build. **What you should see:** your change on `/404.html`, and every other
page unchanged.

The same works for stylesheets. The default theme's labels, menu and buttons use the CSS variable `--mono`, the
same one as code. To give them a font of their own, copy the layout sheet and replace `var(--mono)` where you want
the other font:

```bash
mkdir -p theme/assets/css
cp bazinga/theme/assets/css/site.css theme/assets/css/site.css
```

Useful files to know:

| Path under `bazinga/theme/` | What it is |
|---|---|
| `templates/base.html` | the frame of every page (head, rail, scripts) |
| `templates/home.html`, `cv.html`, `page.html`, `project.html`, `list.html` | the home page, CV, posts, projects, lists |
| `templates/series.html`, `topic.html`, `topics.html`, `explore.html`, `ask.html`, `404.html` | the other pages |
| `assets/css/tokens.css` | every colour and font, as CSS variables |
| `assets/css/site.css` | the layout |
| `assets/css/figure.css`, `math.css`, `diagram.css` | figures, equations, diagrams |
| `templates/partials/lists.html` | the shared lists: Related, Go deeper, Go broader |
| `assets/js/site.js`, `pager.js` | the rail and menus, and the ten-per-page lists |
| `assets/js/figure.js`, `pyworker.js` | figure controls, and the worker that redraws figures in the browser |
| `assets/js/explore.js`, `ask.js` | the map, and Ask |
| `assets/img/` | the Bazinga mark (the default tab icon) and the paper textures |

A new file you add (say `theme/assets/css/extra.css`) is copied to the site, but nothing links to it until you
also override `base.html` to load it.

You can also replace the starter that `python -m bazinga new` copies: put your own at `theme/starters/post.md`.

!!! tip
    Copy as little as you can. A copied file no longer gets fixes from newer versions of Bazinga, while the files
    you did not copy do.

## What's next

- Put the site online: [Deploying](deploying.md).
- Every key in one table: [Configuration reference](reference/configuration.md).
