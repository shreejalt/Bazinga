"""Starter drawing: blocks in a stack and in groups (an architecture sketch).

Copy it with  python -m tessera figure new my_blocks --from blocks  (it lands in drawings/)
and put  ::drawing my_blocks.stack | A caption  in a post.
"""

from tessera.draw import Diagram


def stack():
    d = Diagram(720, title="A small model: an encoder stack feeding two heads")

    # column() stacks boxes top to bottom (centred when x is not given).
    enc = d.column(["Embedding", "Block 1", "Block 2", "Block 3"], x=60, y=30, w=200, gap=22, style="muted")
    enc[0].style = "second"            # any box's style can be changed after it is made
    d.chain(enc)
    d.group("Encoder", enc)            # a labelled dashed frame around some boxes

    # grid() lays boxes out in rows of `cols`.
    heads = d.grid([("Classify", "one label"), ("Locate", "a box per object")], cols=1,
                   x=440, y=enc[1].y, w=200, gap=40)
    for h in heads:
        # start/end pick the sides the arrow leaves and enters; bend curves it.
        d.arrow(enc[-1], h, style="main", start="right", end="left")
    d.group("Heads", heads)

    d.label(160, enc[-1].bottom + 40, "the same blocks, repeated", style="muted")
    return d.svg()
