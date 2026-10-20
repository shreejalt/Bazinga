"""How a ```diagram block becomes a drawing (used in the guide, content/reads/drawing-diagrams.md)."""

from tessera import draw

# (step, what it does): the stages of tessera/diagram_text.py, in order
STAGES = [
    ("Read", "names, arrows, groups"),
    ("Layers", "a column per step"),
    ("Order", "fewest crossings"),
    ("Route", "arrows round boxes"),
    ("Draw", "in the theme"),
]


def stages(narrow=0):
    names = [s for s, _ in STAGES]
    d = draw.flow(
        nodes=[(s, what) for s, what in STAGES],
        edges=list(zip(names, names[1:])),
        groups={"When the site is built": names},
        title="A diagram block is read, split into layers, ordered, routed and drawn when the site is built",
        narrow=narrow)
    return d.svg()
