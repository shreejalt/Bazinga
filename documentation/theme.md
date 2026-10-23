# Theme and customising

In this guide you will change how the site looks and what it holds: colours, fonts, the menu, the kinds of pages,
and, when settings are not enough, the theme's own files. You never edit the engine to do any of this.

There are two levels:

1. **`site.yml`**: colours, fonts, the width of the text, the menu (`nav:`), the kinds of pages (`kinds:`) and which
   parts are on (`features:`).
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
| `font_ui` | the typewriter face: the menu, labels, buttons, and the text of reads and papers |
| `font_code` | code blocks and code in the text |
| `font_math` | equations; it needs a font with a maths table, such as STIX Two Math |

Each family named here is loaded from Google Fonts with the weights the theme needs.

If you set `font_code` and leave out `font_ui`, the menu and labels use your code font too. If you delete a key,
Bazinga uses its own default: Source Serif 4 for text, JetBrains Mono for the interface and code, STIX Two Math for
equations, and `#3b5bdb` for the accent. Keep the keys to keep the look of the example site.

**What you should see:** with `font_ui: "IBM Plex Mono"`, the menu and labels change after the page reloads, and code
keeps its own font.

## The width of the text

The reading column is about 780 pixels wide. Set `width` to make it narrower or wider:

```yaml
theme:
  width: 860
```

It takes a number from 480 to 1200. Any other number stops the build with
`theme.width should be between 480 and 1200 pixels`. Leave it out to keep the theme's own width.

**What you should see:** after the page reloads, the text of every page runs wider (or narrower). On a phone the
column still fits the screen.

## Light only

The site has one look: the paper sheet, in light colours. It has no dark mode, and no setting turns one on. (These
docs have a light and a dark look; your site does not.) To change the colours, use the keys under
[Colours](#colours).

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

Every item needs a `label` and an `href`, or the site does not build. The home page's rail is different; see
[The rail on the home page](home-and-cv.md#the-rail-on-the-home-page).

## Kinds of pages

Each kind is a folder `content/<kind>/` and a list page `/<kind>/`. The example site has four:

```yaml
kinds:
  reads:
    label: Reads
    singular: Read
    blurb: "Explanations of a concept, built from several papers rather than one."
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
```

Every field of a kind (`label`, `singular`, `role`, `external`, `blurb`, `placeholder`, `word`) and its default is in
[Configuration: kinds](reference/configuration.md#kinds). The `role` sets the layout:

- **read**: a concept explained, in the memo layout (header block, summary, contents, numbered sections,
  Connections).
- **paper**: one paper explained; its header names the paper with `explains: [KEY]`.
- **project**: a project page.
- **external**: attributed entries with no body. Their header has `external:` (the address), `author:` and
  `publication:`. They are listed, placed on the map, and open where they were published.

A kind's name must be lowercase letters, digits or `-`, because it is a folder and part of the address. When you
define `kinds:`, your list replaces the default kinds; it is not added to them.

## Turning parts on and off

`features:` in `site.yml` turns off Ask, the map, series, the feed, `llms.txt` and the "Made with Bazinga" link; what
each switch removes is in [Configuration: features](reference/configuration.md#features). Take the matching item out
of `nav:` too. A portfolio with no blog turns most of them off: see
[A portfolio without the blog](home-and-cv.md#a-portfolio-without-the-blog).

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

The same works for stylesheets. Copy the layout sheet and edit the copy (for fonts, colours and the width of the
text, the settings above are enough):

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
| `assets/css/wiki.css` (you create it, under `theme/`) | extra styles; when the file exists, every page loads it, with no other change |
| `templates/partials/lists.html` | the shared lists: Related, Go deeper, Go broader |
| `assets/js/site.js`, `pager.js` | the rail and menus, and the ten-per-page lists |
| `assets/js/figure.js`, `pyworker.js` | figure controls, and the worker that redraws figures in the browser |
| `assets/js/explore.js`, `ask.js` | the map, and Ask |
| `assets/img/` | the Bazinga mark (the default tab icon) and the paper textures |

A new file you add (say `theme/assets/css/extra.css`) is copied to the site, but nothing links to it until you
also override `base.html` to load it. The one exception is `wiki.css`, which `base.html` already loads when it
exists. The colours of code blocks (`assets/css/pygments.css`) are written by every build, so a copy under `theme/`
is replaced.

You can also replace the starter that `python -m bazinga new` copies: put your own at `theme/starters/post.md`.

!!! tip
    Copy as little as you can. A copied file no longer gets fixes from newer versions of Bazinga, while the files
    you did not copy do.

## What's next

- Put the site online: [Deploying](deploying.md).
- Every key in one table: [Configuration reference](reference/configuration.md).
