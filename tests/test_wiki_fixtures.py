"""A small site used by the wiki tests: real Page objects (content.parse) and Rendered-like objects.

No tests here; the other test_wiki_* modules import ``make_site``.
"""
import datetime as dt
import tempfile
import textwrap
from pathlib import Path
from types import SimpleNamespace

from tessera import config, content
from tessera.graph import build_graph

TOPICS = {
    "attention": {"slug": "attention", "label": "Attention"},
    "transformers": {"slug": "transformers", "label": "Transformers"},
    "vision": {"slug": "vision", "label": "Vision"},
    "state-space": {"slug": "state-space", "label": "State-space models"},
    "robotics": {"slug": "robotics", "label": "Robotics"},
    "math": {"slug": "math", "label": "Mathematics"},
}

PAGES = {
    "posts/attention.md": ("""
        title: "Attention, Step by Step"
        date: 2026-03-01
        summary: "How a token looks at every other token: queries, keys, values and a softmax."
        topics: [attention, transformers]
        cites: [VASW17]
        builds_on: [post:qkv]
        """, """
        Attention lets every token look at every other token. See [[post:qkv]] for the three projections.

        ## Scaled dot product {#scaled}

        The score between a query and a key is their dot product. We divide the score by the square root of the key
        dimension, 64 in the base model, so the softmax does not saturate. The weights then mix the values.

        ## Many heads

        Eight heads run in parallel, each on a 64-dimensional slice, and their outputs are joined again.
        ::figure softmax_temp
        """, [("", "", "Attention lets every token look at every other token. See Queries, Keys and Values for the three projections."),
              ("scaled", "Scaled dot product", "The score between a query and a key is their dot product. We divide the score by the square root of the key dimension, 64 in the base model, so the softmax does not saturate. The weights then mix the values."),
              ("many-heads", "Many heads", "Eight heads run in parallel, each on a 64-dimensional slice, and their outputs are joined again.")],
        ["post:qkv"], ["softmax_temp"]),
    "posts/qkv.md": ("""
        title: "Queries, Keys and Values"
        date: 2026-02-01
        summary: "Three linear maps turn one token into a query, a key and a value."
        topics: [attention]
        cites: [VASW17]
        series: {name: "Transformers", part: 1}
        """, """
        Each token is multiplied by three learned matrices.

        ## The three projections

        The query asks, the key answers and the value carries the content.
        """, [("", "", "Each token is multiplied by three learned matrices."),
              ("the-three-projections", "The three projections", "The query asks, the key answers and the value carries the content.")],
        [], []),
    "posts/vit.md": ("""
        title: "Vision Transformers"
        date: 2026-04-01
        summary: "Cut an image into 16 by 16 patches and treat them as tokens."
        topics: [transformers, vision]
        builds_on: [post:attention]
        cites: [DOSO21]
        series: {name: "Transformers", part: 2}
        """, """
        A picture becomes a sentence of patches.

        ## Patches as tokens

        A 224 pixel image cut into 16 by 16 patches gives 196 tokens. Each patch is flattened and projected.

        ## Position embeddings

        Learned position embeddings tell the model where each patch came from.
        """, [("", "", "A picture becomes a sentence of patches."),
              ("patches-as-tokens", "Patches as tokens", "A 224 pixel image cut into 16 by 16 patches gives 196 tokens. Each patch is flattened and projected."),
              ("position-embeddings", "Position embeddings", "Learned position embeddings tell the model where each patch came from.")],
        [], []),
    "posts/mamba.md": ("""
        title: "Mamba and Selective Scan"
        date: 2026-05-01
        summary: "A state-space model whose parameters depend on the input."
        topics: [state-space]
        """, """
        Mamba keeps a hidden state and updates it token by token.

        ## Selective scan

        The step size and the input and output matrices depend on the current token, so the model can choose what to
        remember. The scan runs in linear time in the sequence length.
        """, [("", "", "Mamba keeps a hidden state and updates it token by token."),
              ("selective-scan", "Selective scan", "The step size and the input and output matrices depend on the current token, so the model can choose what to remember. The scan runs in linear time in the sequence length.")],
        [], []),
    "projects/robot.md": ("""
        title: "A Robot Arm"
        date: 2026-01-10
        summary: "A six-joint arm that sorts blocks by colour."
        topics: [robotics]
        """, """
        The arm has six joints and a camera on the wrist.
        """, [("", "", "The arm has six joints and a camera on the wrist.")], [], []),
    "posts/softmax.md": ("""
        title: "Softmax and Temperature"
        date: 2026-02-15
        summary: "Dividing logits by a temperature sharpens or flattens the softmax."
        topics: [math, attention]
        """, """
        The softmax turns scores into weights that sum to one. It is used in [[post:attention]].
        """, [("", "", "The softmax turns scores into weights that sum to one. It is used in Attention, Step by Step.")],
        ["post:attention"], []),
    "posts/draft.md": ("""
        title: "Unfinished"
        date: 2026-01-01
        status: draft
        summary: "Not public."
        topics: [math]
        """, "Secret draft text.\n", [("", "", "Secret draft text.")], [], []),
}

REFERENCES = {
    "VASW17": {"title": "Attention Is All You Need", "authors": ["Ashish Vaswani", "Noam Shazeer"], "year": 2017, "arxiv": "1706.03762"},
    "DOSO21": {"title": "An Image is Worth 16x16 Words", "authors": ["Alexey Dosovitskiy"], "year": 2021, "arxiv": "2010.11929"},
}


def make_site(root=None):
    """Write the fixture site to a temp dir and return (cfg, pages, rendered, site, graph)."""
    root = Path(root or tempfile.mkdtemp(prefix="tessera-wiki-"))
    (root / "site.yml").write_text(textwrap.dedent("""
        site: {name: "Fixture", author: "Ada", description: "Notes on attention and other things.", origin: "https://ex.org"}
        llm: {base_url: "http://127.0.0.1:9/v1", model: "a/one, b/two", key_env: "TESSERA_TEST_KEY"}
        """), encoding="utf-8")
    (root / "content").mkdir(parents=True, exist_ok=True)
    import yaml
    (root / "content" / "references.yml").write_text(yaml.safe_dump(REFERENCES), encoding="utf-8")
    cfg = config.load(root)
    pages, rendered = [], {}
    for rel, (fm, body, sections, mentions, figures) in PAGES.items():
        path = root / "content" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("---\n" + textwrap.dedent(fm).strip() + "\n---\n" + textwrap.dedent(body).lstrip(), encoding="utf-8")
        page = content.parse(path.read_text(encoding="utf-8"), path, cfg)
        pages.append(page)
        rendered[page.id] = SimpleNamespace(
            html="", toc=[{"level": 2, "id": a, "text": t} for a, t, _ in sections if a], mentions=list(mentions),
            cites=list(page.cites), figures=list(figures), drawings=[], issues=[],
            sections=[{"id": a, "title": t, "text": x} for a, t, x in sections])
    public = [p for p in pages if p.public]
    site = SimpleNamespace(pages={p.id: p for p in public}, references=REFERENCES, topics=TOPICS)
    graph = build_graph(public, rendered, site)
    return cfg, public, rendered, site, graph


def make_state(cfg, pages, rendered, site, graph):
    from tessera.llm import State
    return State(pages, rendered, graph, TOPICS, site)


TODAY = dt.date(2026, 10, 20)
