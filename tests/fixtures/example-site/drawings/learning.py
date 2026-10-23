"""Diagrams for the "Learning, Visually" series."""

from bazinga.draw import Diagram

STEPS = [
    ("Scores", "q · k for every pair"),
    ("Scale", "divide by √d"),
    ("Softmax", "rows sum to 1"),
    ("Mix", "weighted sum of values"),
]
TITLE = ("Scaled dot-product attention: queries and keys give scores, the scores are divided by the square "
         "root of d and softmaxed, and the weights mix the values")


def attention(narrow=0):
    # narrow=1 is the phone layout: inputs in a row on top, the four steps stacked under them.
    if narrow:
        d = Diagram(400, title=TITLE)
        q, k, v = d.row([("Queries", "Q"), ("Keys", "K"), ("Values", "V")], y=30, w=104, gap=20, style="muted")
        scores, scale, soft, mix = d.column(STEPS, x=60, y=q.bottom + 50, w=220, gap=30)
        d.arrow(q, scores)
        d.arrow(k, scores)
        d.chain([scores, scale, soft, mix])
        d.arrow(v, mix, style="muted", bend=-60, start="bottom", end="right")
        mix.style = "main solid"
        return d.svg()
    d = Diagram(840, title=TITLE)
    q, k, v = d.column([("Queries", "Q"), ("Keys", "K"), ("Values", "V")], x=16, y=20, w=120, gap=20,
                       style="muted")
    steps = d.row(STEPS, y=q.y + 26, x=196, w=136, gap=34)
    scores, mix = steps[0], steps[-1]
    d.arrow(q, scores)
    d.arrow(k, scores)
    d.chain(steps)
    d.arrow(v, mix, "values", style="muted", start="right", end="bottom", bend=60)
    mix.style = "main solid"
    return d.svg()
