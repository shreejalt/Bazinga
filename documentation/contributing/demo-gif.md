# The demo GIF

The README has a short terminal demo: the example site is built, a figure is added and tested, and the site is
served. On this page you'll see which tool makes it, how to make it again with one command, and what to do when the
tool will not start.

::clip demo | The demo, as it appears in the README.

## The tool

[VHS](https://github.com/charmbracelet/vhs) records a terminal from a small script called a tape. The tape is
`documentation/recordings/tapes/demo.tape`. It sets the look (font size 18, 1200×760, 16 frames a second, typing
at 35 ms a key, the site's paper and ink colours), then:

1. in a hidden part, copies the template into a throwaway temporary folder and sets a short prompt;
2. shows `python -m bazinga build`;
3. shows `python -m bazinga figure new my_plot --from slider_plot`;
4. shows `python -m bazinga figure test my_plot`;
5. shows `python -m bazinga serve`, then stops it with Ctrl+C.

Because the tape types the real commands into a real shell, the output in the GIF is whatever the template prints
today.

## Make it again

From the repository root, with the template's Python environment:

```bash
.venv/bin/python documentation/recordings/make.py demo
```

**What you should see:** VHS runs the tape, then a line such as

```text
demo                    17.9 s   mp4    80 KB   webm    95 KB   poster   40 KB, gif 410 KB
```

It writes:

| File | Used by |
|---|---|
| `documentation/assets/gifs/demo.gif` | the README (GitHub shows GIFs everywhere; videos do not autoplay there) |
| `documentation/assets/clips/demo.{mp4,webm,jpg}` | this page |

Keep the GIF under about 800 KB and 20 seconds. If it grows, shorten the `Sleep` lines in the tape.

## If VHS will not start

VHS runs the shell inside [ttyd](https://github.com/tsl0922/ttyd) and films it with a headless browser. On macOS, a
Homebrew VHS sometimes stops with `could not open ttyd` or `ERR_CONNECTION_REFUSED`. In that order, try:

1. `brew install ttyd` (or `brew upgrade ttyd`), then run the command again;
2. a newer VHS: `brew install charmbracelet/tap/vhs` installs the latest release from Charm's own tap;
3. the fallback: record the same commands with [asciinema](https://asciinema.org/) and turn the recording into a GIF
   with [agg](https://github.com/asciinema/agg):

   ```bash
   asciinema rec demo.cast        # type the five commands, then Ctrl+D
   agg --font-size 18 demo.cast documentation/assets/gifs/demo.gif
   ```

For this repository, VHS 0.12.1 from Homebrew worked as it is.

## What's next

[Coverage](coverage.md) lists every part of Bazinga and the page that documents it. Every other clip is covered
in [Recording the clips](recording-clips.md).
