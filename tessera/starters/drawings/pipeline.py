"""Starter drawing: steps in a row, joined by arrows.

Copy it with  python -m tessera figure new my_steps --from pipeline  (it lands in drawings/)
and put  ::drawing my_steps.steps | A caption  in a post.

A drawing is a function that returns SVG text. It runs once, when the site is built; nothing runs in
the reader's browser. Styles are names ("main", "second", "muted", "solid", "ghost", "dashed"); the
theme gives them colours, in light and dark mode.

Phones: a drawing scales down to the screen. If the text gets too small, give the function a
`narrow=0` parameter and draw a stacked layout (about 400 wide) when narrow is 1; the site shows
that version on phones (see drawings/pipeline.py in the example site). Without it, the drawing keeps
a readable size on phones and scrolls sideways inside its frame.
"""

from tessera.draw import Diagram


def steps():
    # 720 units wide matches the reading column; the drawing scales to fit any screen.
    d = Diagram(720, title="Data flows from input to output in three steps")

    # row() places boxes side by side and centres them. Each item is "Text" or ("Text", "second line").
    load, clean, train = d.row([
        ("Load", "read the files"),
        ("Clean", "drop bad rows"),
        ("Train", "fit the model"),
    ], y=24, w=160, gap=96)

    # chain() draws an arrow between each pair; the labels sit on the arrows.
    d.chain([load, clean, train], labels=["rows", "clean rows"])

    # A box anywhere: x, y, width, (height fits the text), text, style, second line.
    out = d.box(train.x, train.bottom + 56, train.w, None, "Model", style="main solid", sub="saved to disk")
    d.arrow(train, out)

    # A quiet note under everything.
    d.note("Each step only reads what the one before it wrote.")
    return d.svg()
