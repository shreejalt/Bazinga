"""How a post goes from a Markdown file to the live site."""

from bazinga.draw import Diagram

STEPS = [
    ("Write", "Markdown, equations, figures"),
    ("Check", "maths, links, citations"),
    ("Build", "pages, map, wiki files"),
]


def overview(narrow=0):
    # narrow=1 is the phone layout: the same steps, stacked.
    title = "From a Markdown file to the live site: write, check, build, publish"
    if narrow:
        d = Diagram(400, title=title)
        write, check, build = d.column(STEPS, y=40, w=240, gap=34)
        d.chain([write, check, build])
        d.arrow(check, write, "fix", style="muted dashed", bend=40, start="right", end="right")
        d.group("On your machine", [write, check, build], pad=22)
        publish = d.box(build.x, build.bottom + 56, build.w, None, "Publish", style="main solid", sub="commit, push, deploy")
        d.arrow(build, publish)
        d.note("Nothing reaches the site until you press Publish.", y=publish.bottom + 34)
        return d.svg()
    d = Diagram(840, title=title)
    write, check, build = d.row(STEPS, y=44, w=170, gap=44, x=16)
    d.chain([write, check, build])
    d.arrow(check, write, "fix", style="muted dashed", bend=-30, start="bottom", end="bottom")
    d.group("On your machine", [write, check, build], pad=30)
    publish = d.box(build.right + 64, build.y, 150, build.h, "Publish", style="main solid", sub="commit, push, deploy")
    d.arrow(build, publish)
    d.note("Nothing reaches the site until you press Publish.", y=build.bottom + 70)
    return d.svg()
