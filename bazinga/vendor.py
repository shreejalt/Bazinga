"""Every third-party URL the site or the Studio loads, pinned to exact versions in one place.

Nothing here is downloaded at build time. Pages reference these URLs; a test checks that each carries an exact
version (no ``@latest``, no bare major version). Update a version here and nowhere else.
"""
from __future__ import annotations

from urllib.parse import quote_plus

PYODIDE_VERSION = "314.0.7"   # CPython 3.14; module workers only (see docs/research.md §4)
PYODIDE_INDEX_URL = f"https://cdn.jsdelivr.net/pyodide/v{PYODIDE_VERSION}/full/"
PYODIDE_MODULE = PYODIDE_INDEX_URL + "pyodide.mjs"

# CodeMirror 6 for the Studio's editor, through esm.sh's "*" prefix so @codemirror/state loads once.
CODEMIRROR_IMPORT_MAP = {
    "codemirror": "https://esm.sh/*codemirror@6.0.2",
    "@codemirror/state": "https://esm.sh/*@codemirror/state@6.7.6",
    "@codemirror/view": "https://esm.sh/*@codemirror/view@6.43.13",
    "@codemirror/commands": "https://esm.sh/*@codemirror/commands@6.11.1",
    "@codemirror/language": "https://esm.sh/*@codemirror/language@6.12.4",
    "@codemirror/autocomplete": "https://esm.sh/*@codemirror/autocomplete@6.20.3",
    "@codemirror/search": "https://esm.sh/*@codemirror/search@6.7.2",
    "@codemirror/lint": "https://esm.sh/*@codemirror/lint@6.9.7",
    "@codemirror/lang-markdown": "https://esm.sh/*@codemirror/lang-markdown@6.5.2",
    "@codemirror/lang-html": "https://esm.sh/*@codemirror/lang-html@6.4.12",
    "@codemirror/lang-css": "https://esm.sh/*@codemirror/lang-css@6.3.1",
    "@codemirror/lang-javascript": "https://esm.sh/*@codemirror/lang-javascript@6.2.5",
    "@codemirror/lang-python": "https://esm.sh/*@codemirror/lang-python@6.2.1",
    "@lezer/common": "https://esm.sh/*@lezer/common@1.5.3",
    "@lezer/highlight": "https://esm.sh/*@lezer/highlight@1.2.5",
    "@lezer/lr": "https://esm.sh/*@lezer/lr@1.4.10",
    "@lezer/markdown": "https://esm.sh/*@lezer/markdown@1.7.2",
    "@lezer/html": "https://esm.sh/*@lezer/html@1.3.13",
    "@lezer/css": "https://esm.sh/*@lezer/css@1.3.8",
    "@lezer/javascript": "https://esm.sh/*@lezer/javascript@1.5.6",
    "@lezer/python": "https://esm.sh/*@lezer/python@1.1.18",
    "style-mod": "https://esm.sh/style-mod@4.1.4",
    "w3c-keyname": "https://esm.sh/w3c-keyname@2.2.8",
    "crelt": "https://esm.sh/crelt@1.0.7",
    "@marijn/find-cluster-break": "https://esm.sh/@marijn/find-cluster-break@1.0.4",
}

GOOGLE_FONTS_CSS = "https://fonts.googleapis.com/css2"
FONT_PRECONNECT = ["https://fonts.googleapis.com", "https://fonts.gstatic.com"]

# Axes requested per role. One stylesheet per family, so a family without one of these weights cannot break the rest.
_FONT_AXES = {
    "font_text": "ital,wght@0,400;0,700;1,400",
    "font_ui": "wght@400;700",
    "font_code": "ital,wght@0,400;0,700;1,400",
    "font_math": "",
}


def font_url(family: str, axes: str = "") -> str:
    """The Google Fonts stylesheet URL for one family."""
    spec = quote_plus(family.strip()) + (f":{axes}" if axes else "")
    return f"{GOOGLE_FONTS_CSS}?family={spec}&display=swap"


def font_urls(theme: dict) -> list[str]:
    """Stylesheet URLs for the fonts named in ``site.yml`` (empty names are skipped; duplicates once)."""
    urls: list[str] = []
    seen: set = set()
    # the code font first, so a family used for both code and the interface is requested once, with its italics
    for role in ("font_text", "font_code", "font_ui", "font_math"):
        family = str(theme.get(role) or "").strip()
        if family and family.lower() not in ("system-ui", "serif", "sans-serif", "monospace", "math") \
                and family.lower() not in seen:
            seen.add(family.lower())
            urls.append(font_url(family, _FONT_AXES[role]))
    return urls


def urls() -> dict:
    """What templates receive as ``vendor``."""
    return {"pyodide_version": PYODIDE_VERSION, "pyodide_index": PYODIDE_INDEX_URL, "pyodide": PYODIDE_MODULE,
            "codemirror": CODEMIRROR_IMPORT_MAP, "font_preconnect": FONT_PRECONNECT}


def pinned_urls() -> list[str]:
    """Every versioned URL (for the pin test)."""
    return [PYODIDE_MODULE, PYODIDE_INDEX_URL, *CODEMIRROR_IMPORT_MAP.values()]
