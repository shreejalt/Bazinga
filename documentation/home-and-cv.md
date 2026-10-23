# Your home page and CV

In this guide you will put your own name, words and record on the site. Two files hold everything personal:

- `site.yml`, the `site:` and `home:` sections, for the home page;
- `content/cv.yml`, for the CV page at `/cv/`.

Keep `python -m bazinga serve` running while you edit. The page reloads every time you save.

::clip site-tour | The example site: the home page, then a list of posts and one post.

## Your name and links

Open `site.yml` and start with the `site:` section at the top.

```yaml
site:
  name: "Your Name"
  author: "Your Name"
  tagline: "Notes on the things I build and learn"
  description: "Reads, paper explainers and projects in machine learning, with interactive figures and a map of how every page connects."
  origin: "https://example.com"
  language: en
  avatar: ""
  links:
    github: "https://github.com/your-handle"
    linkedin: "https://www.linkedin.com/in/your-handle/"
    medium: "https://medium.com/@your-handle"
    scholar: ""
    x: ""
    email: "you@example.com"
```

| Field | Where it shows |
|---|---|
| `name` | the brand at the top of the rail, the browser tab, search results |
| `author` | the header block of every page, the feed, and search engines |
| `tagline` | the feed's subtitle; also the home page's search description when `description` is empty |
| `description` | what search engines show for the home page (155 characters at most) |
| `origin` | the address the site will live at, with no `/` at the end; used for canonical links, the sitemap and the feed |
| `avatar` | optional picture, such as `static/avatar.png`: the browser-tab icon and the share image. Without it, the tab shows the Bazinga mark |
| `links` | buttons on the home page, in this order; leave a value empty to hide it |

The link names `github`, `linkedin`, `medium`, `scholar`, `x`, `twitter`, `mastodon`, `bluesky`, `youtube`,
`website`, `orcid` and `substack` get a proper label (GitHub, LinkedIn, ...). Any other name is shown with its
first letter in capitals. `email` is special: it is never shown as a plain link; it feeds the Contact section's
email button instead.

**What you should see:** after saving, the rail shows your name and the home page shows your links.

## The home page, section by section

The home page is built from the `home:` section of `site.yml`. Every field is optional. A section whose fields are
missing is left out.

### The top

```yaml
home:
  title: "Your Name — Machine Learning Notes"
  photo: /static/images/photo.svg
  role: "Machine Learning Engineer"
  employer: "Example Labs"
  working_at: "Working at Example Labs"
  tagline: "Notes on how learning machines work, one figure at a time."
  statement: ""
  lead: >-
    Hi! I build machine learning systems and write down how they work.
```

| Field | What it does |
|---|---|
| `title` | the home page's `<title>` and its link-preview title (default: `site.name`) |
| `photo` | a square picture, shown round at 230 px; under it go `role` and `working_at` |
| `role` | first line under the photo; the CV page also says "role at employer" |
| `employer` | used only by the CV page's first line |
| `working_at` | second line under the photo |
| `tagline` | the big line at the top of the page |
| `statement` | an optional bold line under the tagline |
| `lead` | the opening paragraph |
| `intro` | optional extra paragraph, written in Markdown (links, emphasis) |

Under the lead you always get one button per kind of page (Reads, Papers, Projects, ...), then your links.

To use your own photo, put it in `static/images/` and point `photo:` at it, for example
`/static/images/me.jpg`. Note the leading `/`.

### About, and the "pick one" buttons

```yaml
  about:
    - >-
      Replace these paragraphs with a few lines about you.
    - >-
      When an idea finally clicks, I write it down: the concepts live under <a href="/reads/">Reads</a>.
  starters_label: "Pick one"
  starters:
    - {name: Tea,    mark: "🍵", say: "Tea. A person of patience."}
    - {name: Coffee, mark: "☕", say: "Coffee. We will get along just fine."}
```

`about` is a list of paragraphs. They are printed as written, so they may carry `<b>`, `<i>` and `<a>`.
`starters` are small buttons under About; clicking one shows its `say` line. Delete the list to hide them.

### Explore

```yaml
  map_text: "Everything I have written or built is on one map, each item below what it builds on."
```

This section points at the map and appears while `features.explore` is on. `map_text` replaces the default sentence.

### Experience and education

```yaml
  experience:
    - period: Jan 2024 – now
      role: Machine Learning Engineer
      org: Example Labs
      place: Remote
      points:
        - Built and maintain the training and evaluation pipeline for the team's vision models.
      pages: [project:bazinga]
  education:
    - {degree: "MSc, Computer Science", school: "Example University"}
  courses: "Machine Learning, Computer Vision, Optimization, Probability and Statistics."
```

Each role is a line that opens to show its `points`. `pages` takes ids of pages on your site about that work, and
they are linked under the points. An id that does not exist stops the build with a hint, so typos never reach the
site. Education shows the degree and the school only. `courses` is folded away under "Courses and electives".

### Contact

```yaml
  contact:
    lead: >-
      Have a project where machine learning should help but does not yet? Write a short note.
    areas:
      - {mark: "👁️", name: Computer vision, what: "Detection, tracking and recognition in images and video."}
    stack:
      - {area: Machine learning, tools: [PyTorch, NumPy, scikit-learn]}
    close: "Send me a short note on what you want to build."
    email_button: "Email me about a project"
    links_text: "Code, career record, and where the articles were first published."
    elsewhere:
      - {label: "Elsewhere on this site", url: /elsewhere/, text: "Articles that live on other sites."}
```

| Field | What it shows |
|---|---|
| `lead` | the opening line (inline HTML allowed) |
| `areas` | "What I work on": a mark, a name and one line each |
| `stack` | "Tech stack": a group name and its tools |
| `close` | the line next to the email button |
| `email_button` | the button's text; the button appears when `site.links.email` is set |
| `links_text` | the line under your links in "Elsewhere" |
| `elsewhere` | more entries for "Elsewhere": a label, an address and a line |

When `site.links.linkedin` is set, a "Message on LinkedIn" button appears next to the email button.

### The rail on the home page

On the home page the rail lists the page's own sections (About, Explore, Experience, Education, Contact, each only if
it is shown), followed by the Series, Ask and CV items from your `nav:`.

## The CV page

The CV lives in `content/cv.yml`. The page at `/cv/` lays it out; you only fill in the record. If the file does
not exist, there is no CV page.

```yaml
contact:
  email: you@example.com
  links:
    - {label: github.com/your-handle, url: "https://github.com/your-handle"}

experience:
- org: Example Labs
  role: Machine Learning Engineer
  place: Remote
  period: January 2024 – Present
  points:
  - Built and maintain the training and evaluation pipeline for the team's vision models.
  tags: [computer-vision, training, tools]
  pages: [project:bazinga]
  used: [PyTorch, Docker, evaluation dashboards]

education:
- degree: MSc, Computer Science
  school: Example University
  place: City, Country
  period: 2019 – 2021

patents: []

achievements:
- what: Graduate research scholarship
  when: 2019–21
  detail: For a study on efficient vision models

skills:
- area: Languages
  items: Python, C++, SQL, JavaScript

open_source:
- text: A template for technical writing with real equations, interactive figures and a map of the site
  page: project:bazinga
```

| Section | Each entry holds |
|---|---|
| `contact` | `email`, and `links` as `{label, url}` |
| `experience` | `org`, `role`, `place`, `period`, `points`; optional `tags`, `pages`, `used`, `link` |
| `education` | `degree`, `school`, `place`, `period` |
| `patents` | `number`, `title`, `note`, `url` (an empty list hides the section) |
| `achievements` | `what`, `when`, `detail` |
| `skills` | `area`, and `items` as one comma-separated line |
| `open_source` | `text`, and optionally `page`: the id of the page about it |

Per role:

- `tags` are topic slugs from `content/topics.yml`; they link to the topic pages.
- `pages` are ids of pages on your site about that work.
- `used` lists the tools and methods the role's lines name.
- `link` is one more page or address for the role, as `{label, url}`.

The build checks the `tags` and `pages`. An unknown one stops the build with a message such as
`cv.yml: unknown topic 'vison' under Example Labs` and a hint. Project pages with a `github:` header field that are
not already listed under `open_source` are added to the open-source section by themselves.

The CV's first line reads "role at employer" from `home.role` and `home.employer` in `site.yml`.

### A PDF copy

To offer a download, put the file under `static/` and name it in `site.yml`:

```yaml
cv:
  pdf: /static/cv.pdf
```

A full address works too. With a PDF set, the home page's button says **Download CV** and the CV page gets a
**Download the PDF** button. Without it, the home page's button says **Read the CV**.

**What you should see:** open `http://127.0.0.1:8000/cv/`. Your roles, education and skills are laid out in the
same order as the file.

## What's next

- Change the colours and fonts: [Theme and customising](theme.md).
- Put the site online: [Deploying](deploying.md).
- Every key in one table: [Configuration reference](reference/configuration.md).
