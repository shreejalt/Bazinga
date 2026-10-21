"""Starter drawing: a flowchart with decisions (diamonds) and loops back.

Copy it with  python -m bazinga figure new my_flow --from flowchart  (it lands in drawings/)
and put  ::drawing my_flow.decide | A caption  in a post.

A decision lines up with its first answer; the others leave by its sides. Arrows that loop back are routed
around the boxes.
"""

from bazinga import draw

TITLE = "Flowchart"
CAPTION = "Decisions with yes and no, and loops back"


def decide(narrow=0):
    d = draw.flow(
        nodes=[{"name": "Start", "shape": "round"}, "Load a batch",
               {"name": "Loss finite?", "shape": "diamond"}, "Take a step",
               {"name": "Last batch?", "shape": "diamond"}, "Halve the learning rate",
               {"name": "Done", "shape": "round", "style": "emphasis"}],
        edges=[("Start", "Load a batch"), ("Load a batch", "Loss finite?"),
               ("Loss finite?", "Take a step", "yes"), ("Loss finite?", "Halve the learning rate", "no"),
               ("Take a step", "Last batch?"), ("Halve the learning rate", "Load a batch"),
               ("Last batch?", "Load a batch", "no"), ("Last batch?", "Done", "yes")],
        direction="down",
        title="A training loop: load a batch; if the loss is finite take a step, else halve the learning rate",
        narrow=narrow)
    return d.svg()
