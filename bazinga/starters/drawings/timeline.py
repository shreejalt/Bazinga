"""Starter drawing: a timeline of dated events.

Copy it with  python -m bazinga figure new my_history --from timeline  (it lands in drawings/)
and put  ::drawing my_history.history | A caption  in a post.

Code earns its place over a ```diagram timeline block when the events come from data (a list in another file,
a loop over results). The phone version (narrow=1) runs top to bottom.
"""

from bazinga import draw

TITLE = "Timeline"
CAPTION = "Dated events in order, one of them marked"

EVENTS = [
    ("2012", "AlexNet", "deep nets win ImageNet"),
    ("2015", "ResNet", "152 layers, with skips"),
    ("2017", "Transformer", "attention only", "accent"),
    ("2020", "ViT", "images as patches"),
]


def history(narrow=0):
    d = draw.timeline(EVENTS, title="Four turning points in deep learning, 2012 to 2020", narrow=narrow)
    return d.svg()
