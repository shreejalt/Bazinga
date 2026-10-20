"""Helpers for the core tests (no tests here): small sites in temporary folders."""
import shutil
import tempfile
import textwrap
from pathlib import Path

from tessera import config, content
from tessera.markdown import SiteIndex, render

REPO = Path(__file__).resolve().parents[1]

SITE_YML = """
site: {name: Test Site, author: Ada Lovelace, origin: "https://test.example", description: "A test site."}
kinds:
  posts: {label: Writing, singular: Post}
  projects: {label: Projects, singular: Project}
"""

TOPICS = """
groups:
  - name: Methods
    topics:
      - {slug: attention, label: Attention, blurb: "Weighting inputs."}
      - {slug: optimization, label: Optimization}
"""

REFERENCES = """
Vaswani17: {title: "Attention Is All You Need", authors: [Ashish Vaswani, Noam Shazeer, Niki Parmar], year: 2017, arxiv: "1706.03762"}
Kingma14: {title: "Adam", authors: [Diederik P. Kingma, Jimmy Ba], year: 2014, arxiv: "1412.6980"}
"""


def make_site(pages: dict | None = None, site_yml: str = SITE_YML) -> Path:
    """A site in a temp folder. ``pages`` maps 'posts/slug' to the file text. Returns the root (caller removes it)."""
    root = Path(tempfile.mkdtemp(prefix="tessera-core-"))
    (root / "site.yml").write_text(site_yml)
    (root / "content" / "posts").mkdir(parents=True)
    (root / "content" / "topics.yml").write_text(TOPICS)
    (root / "content" / "references.yml").write_text(REFERENCES)
    for rel, text in (pages or {}).items():
        path = root / "content" / f"{rel}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(text).lstrip())
    return root


def post(title="A post", date="2020-01-01", body="Hello.", **fields) -> str:
    """A content file. Defaults: a summary and topics [attention]; pass summary=None to leave a field out."""
    fields = {"summary": '"A summary."', "topics": "[attention]", **fields}
    extra = "".join(f"{k}: {v}\n" for k, v in fields.items() if v is not None)
    return f'---\ntitle: "{title}"\ndate: {date}\n{extra}---\n{body}\n'


def cleanup(root: Path) -> None:
    shutil.rmtree(root, ignore_errors=True)


def render_text(body: str, cfg=None, others=(), preview=False):
    """Render a body as a published post of a throwaway site; returns (page, Rendered)."""
    cfg = cfg or config.load(REPO)
    page = content.parse(post(body=body), Path("content/posts/t.md"), cfg)
    refs = {"Vaswani17": {"title": "Attention Is All You Need", "authors": ["A. Vaswani"], "year": 2017,
                          "arxiv": "1706.03762"},
            "Kingma14": {"title": "Adam", "authors": ["D. Kingma", "J. Ba"], "year": 2014}}
    site = SiteIndex([page, *others], refs, {"attention": {"slug": "attention", "label": "Attention"}}, cfg,
                     preview=preview)
    return page, render(page, site)


def copy_example(dest: Path) -> Path:
    """Copy the example site (config, content, figures, drawings, static) into ``dest``."""
    for name in ("site.yml",):
        shutil.copy(REPO / name, dest / name)
    for name in ("content", "figures", "drawings", "static"):
        if (REPO / name).exists():
            shutil.copytree(REPO / name, dest / name, ignore=shutil.ignore_patterns("__pycache__"))
    return dest
