"""Starter drawing: steps in a row, joined by labelled arrows.

Copy it with  python -m tessera figure new my_steps --from pipeline  (it lands in drawings/)
and put  ::drawing my_steps.steps | A caption  in a post.

A drawing is a function that returns SVG text. It runs once, when the site is built; nothing runs in the
reader's browser. draw.flow() places the boxes and routes the arrows for you, the same way a ```diagram block in
a post is drawn, so you only say what is connected to what. (For a diagram this simple, a ```diagram block is
quicker: write  Load -> Clean -> Train  in the post. Code earns its place when the boxes come from data or a loop.)

Phones: the `narrow` parameter is 1 for the phone version, which flow() draws top to bottom.
"""

from tessera import draw

TITLE = "Pipeline"
CAPTION = "Steps in a row with labelled arrows and a data store"

STEPS = [("Load", "read the files"), ("Clean", "drop bad rows"), ("Train", "fit the model")]


def steps(narrow=0):
    d = draw.flow(
        # a node is a name, a (name, second line) pair, or a dict with style / shape / note
        nodes=STEPS + [{"name": "Model", "shape": "cylinder", "sub": "saved to disk"}],
        # an edge is (from, to) or (from, to, label); names are matched without regard to case
        edges=[("Load", "Clean", "rows"), ("Clean", "Train", "clean rows"), ("Train", "Model")],
        title="Data flows from input to a saved model in three steps",
        narrow=narrow)
    # flow() returns the Diagram: you can still add to it before drawing it
    d.note("Each step only reads what the one before it wrote.")
    return d.svg()
