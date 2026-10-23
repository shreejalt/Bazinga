"""Load and validate ``site.yml``.

Everything a site can configure lives in one YAML file at the site root. ``load()`` merges it over ``DEFAULTS`` (so a
nearly empty file works), validates the values that would otherwise break a build later in a confusing way, and
returns a :class:`Config`: a dict that also allows attribute access (``cfg.site.name``) and knows the site's paths.

The site root is the current working directory unless :func:`set_root` (tests) or ``load(root=...)`` says otherwise.
"""
from __future__ import annotations

import copy
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

import yaml

ROOT: Path = Path.cwd()

DEFAULTS: dict = {
    "site": {
        "name": "Bazinga",
        "author": "Your Name",
        "tagline": "Notes on things I am learning",
        "description": "",
        "origin": "https://example.com",
        "language": "en",
        "avatar": "",
        "links": {"github": "", "x": "", "linkedin": "", "email": "", "scholar": ""},
    },
    "nav": [
        {"label": "Writing", "href": "/posts/"},
        {"label": "Projects", "href": "/projects/"},
        {"label": "Map", "href": "/explore/"},
        {"label": "Ask", "href": "/ask/"},
    ],
    "kinds": {
        "posts": {"label": "Writing", "singular": "Post"},
        "projects": {"label": "Projects", "singular": "Project"},
    },
    "home": {"intro": ""},
    "theme": {
        "accent": "#3b5bdb",
        "font_text": "Source Serif 4",
        "font_ui": "JetBrains Mono",    # the typewriter face of the rail, labels and memo pages
        "font_code": "JetBrains Mono",  # code blocks and inline code
        "font_math": "STIX Two Math",
        "width": None,                  # the reading column in px; None keeps the theme's (about 780)
    },
    "cv": {"pdf": ""},
    "features": {"ask": True, "explore": True, "series": True, "feed": True, "llms_txt": True, "credit": True},
    "llm": {"base_url": "https://openrouter.ai/api/v1", "model": "", "key_env": "LLM_API_KEY"},
    "ask": {"written_answers": True, "per_visitor": 5, "daily_cap": 300},
    "publish": {"commit": True, "push": True, "command": "", "author": ""},
}

ROLES = ("read", "paper", "project", "external")
# Optional theme colours (site.yml theme:), each a CSS variable of the default theme; empty keeps the theme's value.
THEME_COLOURS = ("accent_dark", "ground", "paper", "tint", "ink", "ink_2", "ink_3", "rule_2", "rule_3", "ref", "alert")
_HEX = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
_KIND = re.compile(r"^[a-z][a-z0-9-]*$")


class ConfigError(Exception):
    """``site.yml`` is unreadable or holds a value the build cannot use."""


class Config(dict):
    """A dict with attribute access for nested sections, plus the site's paths.

    ``cfg.site.name`` and ``cfg["site"]["name"]`` are the same value. Nested dicts are wrapped on access, so
    templates and code can use either style.
    """

    root: Path

    def __init__(self, data: dict, root: Path):
        super().__init__(data)
        object.__setattr__(self, "root", Path(root))

    def __getattr__(self, name: str):
        try:
            return _wrap(self[name])
        except KeyError:
            raise AttributeError(name) from None

    # --- paths -------------------------------------------------------------------------------------------------
    @property
    def content_dir(self) -> Path:
        return self.root / "content"

    @property
    def figures_dir(self) -> Path:
        return self.root / "figures"

    @property
    def drawings_dir(self) -> Path:
        return self.root / "drawings"

    @property
    def static_dir(self) -> Path:
        return self.root / "static"

    @property
    def out_dir(self) -> Path:
        return self.root / "_site"

    @property
    def theme_dir(self) -> Path:
        """The site's own theme overrides (may not exist)."""
        return self.root / "theme"

    @property
    def wiki_dir(self) -> Path:
        return self.root / "wiki"

    @property
    def origin(self) -> str:
        """Where the site lives, with its path if it has one (``https://alice.github.io/notes``)."""
        return self["site"]["origin"]

    @property
    def base(self) -> str:
        """The path the site is served under: ``/notes`` for ``https://alice.github.io/notes``, else ``""``."""
        return self["site"].get("base", "")

    def url(self, path: str) -> str:
        """A path on this site as the built pages link to it: :func:`site_url` with this site's base."""
        return site_url(self.base, path)


class _Section(dict):
    """Attribute access for a nested section of the configuration."""

    def __getattr__(self, name: str):
        try:
            return _wrap(self[name])
        except KeyError:
            raise AttributeError(name) from None


def _wrap(value):
    if isinstance(value, dict) and not isinstance(value, _Section):
        return _Section(value)
    return value


def set_root(path) -> Path:
    """Point the engine at another site root (used by tests and the CLI's ``--root``)."""
    global ROOT
    ROOT = Path(path).resolve()
    return ROOT


def deep_merge(base: dict, over: dict) -> dict:
    """Return ``base`` updated recursively with ``over``; lists and scalars in ``over`` replace those in ``base``."""
    out = copy.deepcopy(base)
    for key, value in (over or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


ORIGIN_ENV = ("BAZINGA_ORIGIN", "SITE_URL")   # `bazinga build` takes site.origin from these when set (first wins)


def origin_from_env(environ=None) -> str | None:
    """The address a deploy sets for ``python -m bazinga build`` (``BAZINGA_ORIGIN``, else ``SITE_URL``), or None."""
    environ = os.environ if environ is None else environ
    for name in ORIGIN_ENV:
        if (environ.get(name) or "").strip():
            return environ[name].strip()
    return None


def site_url(base: str, path):
    """``/reads/x/`` -> ``/notes/reads/x/`` when the site lives under ``/notes``. Anything that is not a path on this
    site (``https://…``, ``//host/…``, ``#id``, ``mailto:``, a relative path) is returned unchanged. Apply it once, where
    a link is written: a site under ``/posts`` may well have a ``/posts/`` list of its own."""
    if not base or not isinstance(path, str) or not path.startswith("/") or path.startswith("//"):
        return path
    return base + path


_ATTR_PATH = re.compile(r"""(\s(?:href|src|poster|action)\s*=\s*)(["'])(/(?!/)[^"']*)\2""", re.I)


def site_links(base: str, html: str) -> str:
    """An HTML fragment written by hand or by Markdown (``<a href="/cv/">``) with each ``href``/``src``/``poster``/
    ``action`` that is a path on this site given ``base``. Used once on each fragment, where it is rendered."""
    if not base or not html:
        return html
    return _ATTR_PATH.sub(lambda m: m.group(1) + m.group(2) + base + m.group(3) + m.group(2), html)


def load(root=None, local: bool = False, origin: str | None = None) -> Config:
    """Read ``<root>/site.yml`` (optional), merge it over DEFAULTS and validate it.

    ``origin`` replaces ``site.origin`` (``python -m bazinga build`` passes :func:`origin_from_env`, so a deploy can set
    the address without editing site.yml). When the origin has a path (a GitHub Pages project site,
    ``https://alice.github.io/notes``), every link the build writes starts with that path (``cfg.base``).
    ``local=True`` (the development server and the Editor, which serve the site at the root of 127.0.0.1) keeps the
    base empty."""
    root = Path(root).resolve() if root else ROOT
    path = root / "site.yml"
    data: dict = {}
    if path.exists():
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            mark = getattr(exc, "problem_mark", None)
            where = f":{mark.line + 1}" if mark else ""
            raise ConfigError(f"site.yml{where}: not valid YAML: {getattr(exc, 'problem', exc)}") from None
        except ValueError as exc:         # YAML reads 2026-02-30 as a date and Python refuses it
            from .content import impossible_date
            bad = impossible_date(path.read_text(encoding="utf-8"))
            where = f"site.yml:{bad[0]}: {bad[1]} is" if bad else "site.yml:"
            raise ConfigError(f"{where} not a real date ({exc}); write dates as YYYY-MM-DD") from None
        if not isinstance(data, dict):
            raise ConfigError("site.yml must be a mapping of sections (site:, nav:, theme: ...)")
    merged = deep_merge(DEFAULTS, data)
    user_theme = data.get("theme") if isinstance(data.get("theme"), dict) else {}
    if user_theme.get("font_code") and not user_theme.get("font_ui"):
        merged["theme"]["font_ui"] = user_theme["font_code"]     # before font_ui existed, font_code set both
    if origin:
        merged["site"]["origin"] = origin
    # A site that defines its own kinds replaces the default kinds instead of adding to them.
    if isinstance(data.get("kinds"), dict):
        merged["kinds"] = copy.deepcopy(data["kinds"])
    _validate(merged)
    if local:
        merged["site"]["base"] = ""
    return Config(merged, root)


def _validate(cfg: dict) -> None:
    """Normalise and check the values that later code relies on."""
    site = cfg["site"]
    site["origin"] = str(site.get("origin") or "https://example.com").rstrip("/")
    if not re.match(r"^https?://", site["origin"]):
        raise ConfigError(f"site.origin must start with http:// or https:// (got {site['origin']!r})")
    parts = urlsplit(site["origin"])
    if not parts.netloc or parts.query or parts.fragment:
        raise ConfigError(f"site.origin must be an address such as https://example.com or "
                          f"https://you.github.io/repo (got {site['origin']!r})")
    # the path the site is served under ("" at the root of its host), without a trailing slash
    site["base"] = "/".join(s for s in parts.path.split("/") if s)
    site["base"] = "/" + site["base"] if site["base"] else ""
    for key in ("name", "author", "tagline", "description", "language"):
        site[key] = "" if site.get(key) is None else str(site[key])
    if not isinstance(site.get("links"), dict):
        raise ConfigError("site.links must be a mapping such as {github: 'https://github.com/you'}")
    if not isinstance(cfg.get("home"), dict):
        raise ConfigError("home must be a mapping of the home page's fields (see site.yml)")
    if not isinstance(cfg.get("cv"), dict):
        cfg["cv"] = {"pdf": str(cfg.get("cv") or "")}

    if not isinstance(cfg["nav"], list) or not all(isinstance(n, dict) and "label" in n and "href" in n
                                                   for n in cfg["nav"]):
        raise ConfigError("nav must be a list of {label: ..., href: ...} items")

    kinds = cfg["kinds"]
    if not isinstance(kinds, dict) or not kinds:
        raise ConfigError("kinds must name at least one content folder, e.g. posts: {label: Writing, singular: Post}")
    for name, spec in kinds.items():
        if not _KIND.match(str(name)):
            raise ConfigError(f"kind {name!r} must be lowercase letters, digits or '-' (it is a folder and a URL)")
        spec = kinds[name] = dict(spec or {})
        spec.setdefault("label", name.title())
        spec.setdefault("singular", spec["label"].rstrip("s") or name)
        spec["external"] = bool(spec.get("external"))
        # role: how the theme lays the kind out (memo pages, a paper table, project pages, attributed entries)
        default_role = "external" if spec["external"] else {"papers": "paper", "projects": "project"}.get(name, "read")
        spec.setdefault("role", default_role)
        if spec["role"] not in ROLES:
            raise ConfigError(f"kinds.{name}.role must be one of {', '.join(ROLES)} (got {spec['role']!r})")
        if spec["external"]:
            spec["role"] = "external"
        for key in ("blurb", "placeholder", "word"):
            spec[key] = str(spec.get(key) or "")

    theme = cfg["theme"]
    if not _HEX.match(str(theme.get("accent", ""))):
        raise ConfigError(f"theme.accent must be a hex colour such as '#3b5bdb' (got {theme.get('accent')!r})")
    for key in THEME_COLOURS:
        value = str(theme.get(key) or "")
        if value and not _HEX.match(value):
            raise ConfigError(f"theme.{key} must be a hex colour such as '#E6DECD' (got {value!r})")
        theme[key] = value
    if theme.get("width") not in (None, ""):
        try:
            theme["width"] = int(theme["width"])
        except (TypeError, ValueError):
            raise ConfigError("theme.width must be a number of pixels, e.g. 760") from None
        if not 480 <= theme["width"] <= 1200:
            raise ConfigError("theme.width should be between 480 and 1200 pixels")
    else:
        theme["width"] = None


def kind_id_prefix(cfg, kind: str) -> str:
    """The id prefix for a kind: the singular label in lowercase (``posts`` -> ``post``)."""
    singular = str(cfg["kinds"][kind].get("singular") or kind)
    return re.sub(r"[^a-z0-9]+", "-", singular.lower()).strip("-") or kind
