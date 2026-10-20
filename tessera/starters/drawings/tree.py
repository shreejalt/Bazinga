"""Starter drawing: a hierarchy (a tree), root on top.

Copy it with  python -m tessera figure new my_tree --from tree  (it lands in drawings/)
and put  ::drawing my_tree.taxonomy | A caption  in a post.

A node is a string (a leaf), a (label, [children]) pair, or a dict with label, children, sub and style. The phone
version (narrow=1) is an indented outline.
"""

from tessera import draw

TITLE = "Tree"
CAPTION = "A hierarchy, root on top"

TAXONOMY = ("Machine learning", [
    ("Supervised", ["Classification", "Regression"]),
    ("Unsupervised", ["Clustering", "Embeddings"]),
    {"label": "Reinforcement", "style": "accent"},
])


def taxonomy(narrow=0):
    d = draw.tree(TAXONOMY, title="Three kinds of machine learning and what each is used for", narrow=narrow)
    return d.svg()
