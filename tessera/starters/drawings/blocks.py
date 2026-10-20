"""Starter drawing: blocks in groups (an architecture sketch), laid out for you and by hand.

Copy it with  python -m tessera figure new my_blocks --from blocks  (it lands in drawings/)
and put  ::drawing my_blocks.stack | A caption  in a post.

stack() lets draw.flow() place everything; by_hand() places every box itself with the older kit
(Diagram.row, column, arrow, group), for the rare drawing whose layout must be exact.
"""

from tessera import draw
from tessera.draw import Diagram

TITLE = "Blocks"
CAPTION = "An encoder stack in a frame feeding two heads"


def stack(narrow=0):
    blocks = ["Block %d" % i for i in range(1, 4)]          # code earns its place: the boxes come from a loop
    d = draw.flow(
        nodes=[{"name": "Embedding", "style": "muted"}] + blocks
        + [{"name": "Classify", "sub": "one label", "style": "accent"}, ("Locate", "a box per object")],
        edges=[("Embedding", blocks[0])] + list(zip(blocks, blocks[1:]))
        + [(blocks[-1], "Classify"), (blocks[-1], "Locate")],
        # a group is a frame around its members; its title can be used in edges too
        groups={"Encoder": blocks, "Heads": ["Classify", "Locate"]},
        notes={"Encoder": "the same block, repeated"},
        direction="down",
        title="A small model: an embedding, an encoder of three blocks and two heads",
        narrow=narrow)
    return d.svg()


def by_hand():
    d = Diagram(720, title="The same model, with every box placed by hand")
    enc = d.column(["Embedding", "Block 1", "Block 2", "Block 3"], x=60, y=30, w=200, gap=22, style="muted")
    d.chain(enc)
    d.group("Encoder", enc[1:])
    heads = d.grid([("Classify", "one label"), ("Locate", "a box per object")], cols=1, x=440, y=enc[1].y, w=200, gap=40)
    for h in heads:
        d.arrow(enc[-1], h, start="right", end="left")
    d.group("Heads", heads)
    return d.svg()
