# Recording the clips

The short looping videos in these pages are not screen recordings made by hand. A script records every one of them
from the real template, the same way each time. On this page you'll see which tools it uses, how it works, and how to
re-record a clip or add a new one with one command.

## The short version

From the repository root, with the template's own Python:

```bash
.venv/bin/python documentation/recordings/make.py                 # every clip
.venv/bin/python documentation/recordings/make.py figure-slider   # just one (or several names)
.venv/bin/python documentation/recordings/make.py --list          # what there is
```

**What you should see:** a line per clip as it is filmed, then a table of what was written:

```text
figure-slider           18.6 s   mp4   602 KB   webm   791 KB   poster  117 KB, gif 95 KB
```

The files land in `documentation/assets/clips/` (and README GIFs in `documentation/assets/gifs/`). Build the docs
and the clip plays in its page.

## What you need

| Tool | What it does here | Install |
|---|---|---|
| [Playwright](https://playwright.dev/) | drives Chrome through the browser clips: moves the mouse, types, drags sliders | `cd documentation/recordings && npm install` |
| Google Chrome | the browser that is filmed (Playwright's own Chromium works too: set `CLIP_CHANNEL=chromium` after `npx playwright install chromium`) | — |
| [VHS](https://github.com/charmbracelet/vhs) | records the terminal clips from small `.tape` scripts | `brew install vhs` (it brings `ttyd` and `ffmpeg`) |
| [ffmpeg](https://ffmpeg.org/) | turns the recordings into MP4, WebM, a poster frame and GIFs | `brew install ffmpeg` |
| [gifski](https://gif.ski/) | optional: makes nicer GIFs for the README | `brew install gifski` |

The clip scripts also need the template's Python environment (`.venv`, from `requirements.txt`), because they run
the real `python -m bazinga serve`.

## How it works

`make.py` does four things, in order:

1. **A fresh copy of the template.** Every file git tracks (except `documentation/`) is copied to
   `.cache/recordings/site` and made into its own git repository. Clips start from the example site exactly as a new
   user gets it, and they never touch your files. `.cache/` is git-ignored and sits outside `documentation/`, so
   MkDocs never sees it.
2. **Terminal clips.** Each `documentation/recordings/tapes/<name>.tape` is run with VHS. A tape is a list of
   keystrokes and pauses; a hidden first part moves into the copy and sets a short prompt.
3. **Browser clips.** `make.py` starts `python -m bazinga serve` on the copy (port 8020, the Editor on 8021). Then
   `lib/run.mjs` runs each `documentation/recordings/clips/<name>.mjs` in Chrome at a 1280×800 window, at twice the
   pixel density.
4. **Conversion.** ffmpeg turns each recording into the files the docs use (below).

### What a browser clip looks like on screen

`lib/run.mjs` draws a few things above the page while it films, so a newcomer can follow:

- **a mouse pointer,** a normal black arrow with a white edge, whose tip is exactly where the mouse is;
- **a ripple** (a blue ring that grows and fades) on every click, and a small press when a drag starts;
- **a yellow box** around a control just before it is used, when a clip asks for one;
- **a step caption,** a blue pill at the bottom: `1 · Drag the temperature slider`.

The mouse glides along a gentle eased curve, at about a hand's speed, and waits a moment before each click so the
viewer sees the target first.

### Sharp frames, and no waiting in the clip

The runner films with Chrome's own screencast ([`Page.startScreencast`](https://chromedevtools.github.io/devtools-protocol/tot/Page/),
through Playwright's CDP session). Chrome sends a JPEG of the page every time it changes, at the device's full
resolution: 2560×1600 for a 1280×800 window at 2x. ffmpeg then scales the frames down to 1280 px with a lanczos
filter, which keeps small text crisp. (Playwright's built-in
[`recordVideo`](https://playwright.dev/docs/videos) films at the window's CSS size, which looks soft next to a
2x screenshot.)

Waiting is cut out:

- everything before `h.start()` (opening the page, loading fonts and figures) is dropped;
- a page load in the middle of a clip runs inside `h.offCamera(…)` or `h.loaded(…)`, and those seconds are cut;
- the clip waits until fonts are in and every figure has drawn before filming starts, so there are no blank or
  half-drawn frames.

### What ffmpeg makes

For each clip, in `documentation/assets/clips/`:

| File | What it is |
|---|---|
| `<name>.webm` | VP9, the first choice of browsers that play it. Small. |
| `<name>.mp4` | H.264 with `+faststart` (it starts playing before it has fully downloaded), no audio. Plays everywhere. |
| `<name>.jpg` | the poster: the last frame, shown before the video starts and when videos are off. |
| `<name>.json` | what the window bar above the clip says (the page address, or "Terminal"), its length and size. |

A clip with `gif: true` also gets `documentation/assets/gifs/<name>.gif`, 640 px wide and about 8 seconds, for the
README, made with gifski when it is installed and otherwise with ffmpeg's `palettegen`/`paletteuse` filters.

## Why video and not GIF

A GIF stores every frame as a 256-colour picture, so a few seconds of a page come to megabytes and the text looks
grainy. A video codec stores only what changes between frames. The same clip as an MP4 or WebM is usually a tenth of
the size of the GIF, with full colour; web.dev's
[Replace animated GIFs with video](https://web.dev/articles/replace-gifs-with-videos) measures this and shows the
`<video autoplay loop muted playsinline>` pattern used here. A muted video with `autoplay` and `loop` behaves like a
GIF in every current browser.

GIFs are still made for one place: the README. GitHub does not reliably autoplay a video inside a README, and it
shows a GIF everywhere.

## How a clip gets into a page

Write one line in the Markdown of a page, on its own:

```markdown
::clip figure-slider | Drag the slider and the figure redraws as you move it.
```

The hook `documentation/hooks/clips.py` turns it into a framed, looping video with the right relative paths for that
page (MkDocs does not rewrite paths inside raw HTML, which is why a hook does it). If the clip has not been recorded,
`mkdocs build --strict` fails and names it. While you write, `BAZINGA_DOCS_DRAFT=1 mkdocs serve` shows a grey box in
its place instead.

## Re-recording a clip

After the template changes, run the clip again by name:

```bash
.venv/bin/python documentation/recordings/make.py editor-publish
```

To change only how a clip is cut or how fast it plays, edit its `meta` and re-encode the last recording without
filming again:

```bash
.venv/bin/python documentation/recordings/make.py --convert-only editor-publish
```

Before committing, look at the frames. This makes a sheet of six frames from a clip:

```bash
ffmpeg -i documentation/assets/clips/editor-publish.mp4 \
  -vf "fps=6/$(ffprobe -v error -show_entries format=duration -of csv=p=0 documentation/assets/clips/editor-publish.mp4),scale=640:-1,tile=3x2" \
  -frames:v 1 sheet.png
```

## Adding a browser clip

Create `documentation/recordings/clips/<name>.mjs`. It exports `meta` and one function that drives the page:

```js
export const meta = {
  path: "/reads/softmax-and-temperature/",          // shown in the window bar above the clip
  caption: "Drag the slider and the figure redraws.",
  gif: true, gif_start: 0, gif_seconds: 8,          // optional: a README GIF from these seconds
};

export default async function (page, h) {
  await h.goto(meta.path);                           // opened and fully drawn, off camera
  h.start();                                         // filming starts here
  await h.step("Drag the temperature slider");       // the caption pill
  await h.slide('input[name="t"]', 0.25, 1600);      // drag a slider to a value, in 1.6 s
  await h.step("Pick a preset");
  await h.click('button.fig-preset:has-text("Sharp")', { highlight: true });
  await h.pause(1200);
}
```

The helpers (`h.*`), all in `lib/run.mjs`:

| Helper | What it does |
|---|---|
| `h.goto(path)` | opens a page of the example site and waits until fonts and figures are drawn (cut from the clip) |
| `h.start()` | everything before this is cut |
| `h.step(text)` | shows the next numbered caption; `h.step(null)` hides it |
| `h.move(x, y)`, `h.moveTo(target)` | glides the pointer to a point or an element |
| `h.click(target, { highlight })` | glides there, waits a moment, clicks with a ripple |
| `h.type(text, delay)` | types at a human speed |
| `h.slide(range, value, ms)` | drags a slider's thumb to a value |
| `h.drag(target, dx, dy, ms)`, `h.dragFrom(x, y, dx, dy, ms)` | presses, drags, lets go |
| `h.scroll(dy, ms)` | scrolls with the mouse wheel, smoothly |
| `h.highlight(target)`, `h.unhighlight()` | the yellow box |
| `h.offCamera(fn)`, `h.loaded(selector)` | do something, or wait for a page, without filming it |
| `h.until(fn)` | waits until a test in the page is true (works under the Editor's strict security policy) |

`meta` may also set `speed` (1.2 plays 20% faster), `trim: [start, end]` (seconds to cut at each end), `poster` (the
second to use as the poster) and `bar` (other text for the window bar). The Editor clips share a few steps in
`lib/editor.mjs` (open the Editor with the Write button, start a draft, set the page text).

Then record it and place it:

```bash
.venv/bin/python documentation/recordings/make.py <name>
```

## Adding a terminal clip

Create `documentation/recordings/tapes/<name>.tape`. Copy an existing tape: the settings at the top (font, size,
colours) keep every terminal clip alike, and the hidden part moves into the fresh copy of the site. Then write what
to type:

```text
# caption: Build the site, then check every page.
Output raw/build.mp4
...
Type "python -m bazinga build"
Enter
Sleep 3s
```

The comment lines at the top are read by `make.py`: `caption`, `speed`, `trim` (two numbers), `gif`, `gif_width`,
`gif_start` and `gif_seconds`. The `Output` line must be `raw/<name>.mp4`. The commands are in
[VHS's README](https://github.com/charmbracelet/vhs#vhs-command-reference).

## How other projects do it

- **VHS** itself records its own demo GIFs from `.tape` files in its repository, so they can be re-made after every
  change; see the [README](https://github.com/charmbracelet/vhs).
- **Playwright** documents filming a browser session with [`recordVideo`](https://playwright.dev/docs/videos), the
  usual way test suites keep a video of a failing run.
- **Material for MkDocs** recommends plain images and figures with captions for documentation
  ([Images](https://squidfunk.github.io/mkdocs-material/reference/images/)); the clips here follow the same
  pattern, with a `<video>` in place of the `<img>`.
- **ffmpeg's** guides for [H.264](https://trac.ffmpeg.org/wiki/Encode/H.264) and
  [VP9](https://trac.ffmpeg.org/wiki/Encode/VP9) explain the quality settings `make.py` uses (`-crf`).

## The banner

The animated banner at the top of the README and of the docs home lives in `documentation/assets/brand/`
(`banner-light.gif`, `banner-dark.gif`). It is designed by hand and is not made by these scripts. If its source is
added as `documentation/recordings/banner/frames.mjs`, `make.py banner` runs it.

## What's next

[The demo GIF](demo-gif.md) explains the README's terminal demo, which is made the same way.
