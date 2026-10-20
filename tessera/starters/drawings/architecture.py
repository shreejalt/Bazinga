"""Starter drawing: a model's architecture, layer by layer, with a repeated block drawn as a group.

Copy it with  python -m tessera figure new my_model --from architecture  (it lands in drawings/)
and put  ::drawing my_model.model | A caption  in a post.
"""

from tessera import draw

TITLE = "Model architecture"
CAPTION = "Layers top to bottom, the repeated block as a frame, a skip connection"


def model(narrow=0, layers=6):
    block = ["Self-attention", "norm1", "Feed-forward", "norm2"]
    d = draw.flow(
        nodes=[
            {"name": "Tokens", "shape": "cylinder"},
            "Embedding",
            *block,
            # label= shows other text than the name, so two boxes can both read "Add & norm"
            {"name": "norm1", "label": "Add & norm", "style": "muted"},
            {"name": "norm2", "label": "Add & norm", "style": "muted"},
            {"name": "Classifier", "style": "accent"},
            {"name": "Label", "shape": "cylinder"},
        ],
        edges=[("Tokens", "Embedding"), ("Embedding", "Self-attention"), *zip(block, block[1:]),
               {"a": "Embedding", "b": "norm1", "label": "residual", "line": "dashed"},
               ("norm2", "Classifier"), ("Classifier", "Label")],
        groups={"Encoder block x %d" % layers: block},
        direction="down",
        title="An encoder-only Transformer: tokens, an embedding, %d encoder blocks and a classifier" % layers,
        narrow=narrow)
    return d.svg()
