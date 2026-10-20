"""Load and validate ``site.yml``.

Everything a site can configure lives in one YAML file at the site root. ``load()`` merges it over ``DEFAULTS`` (so a
nearly empty file works), validates the values that would otherwise break a build later in a confusing way, and
returns a :class:`Config`: a dict that also allows attribute access (``cfg.site.name``) and knows the site's paths.

The site root is the current working directory unless :func:`set_root` (tests) or ``load(root=...)`` says otherwise.
"""
from __future__ import annotations

import copy
import re
from pathlib import Path

import yaml

ROOT: Path = Path.cwd()

DEFAULTS: dict = {
    "site": {
        "name": "Tessera",
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
    "home": {"intro": "", "show": ["latest", "series", "map"]},
    "theme": {
        "accent": "#3b5bdb",
        "font_text": "Source Serif 4",
        "font_ui": "Inter",
        "font_code": "JetBrains Mono",
        "font_math": "STIX Two Math",
        "width": 720,
        "mode": "auto",
    },
    "cv": {"pdf": ""},
    "features": {"ask": True, "explore": True, "series": True, "feed": True, "llms_txt": True},
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
        return self["site"]["origin"]


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


def load(root=None) -> Config:
    """Read ``<root>/site.yml`` (optional), merge it over DEFAULTS and validate it."""
    root = Path(root).resolve() if root else ROOT
    path = root / "site.yml"
    data: dict = {}
    if path.exists():
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            mark = getattr(exc, "problem_mark", None)
            where = f" (line {mark.line + 1})" if mark else ""
            raise ConfigError(f"site.yml is not valid YAML{where}: {getattr(exc, 'problem', exc)}") from None
        if not isinstance(data, dict):
            raise ConfigError("site.yml must be a mapping of sections (site:, nav:, theme: ...)")
    merged = deep_merge(DEFAULTS, data)
    # A site that defines its own kinds replaces the default kinds instead of adding to them.
    if isinstance(data.get("kinds"), dict):
        merged["kinds"] = copy.deepcopy(data["kinds"])
    _validate(merged)
    return Config(merged, root)


def _validate(cfg: dict) -> None:
    """Normalise and check the values that later code relies on."""
    site = cfg["site"]
    site["origin"] = str(site.get("origin") or "https://example.com").rstrip("/")
    if not re.match(r"^https?://", site["origin"]):
        raise ConfigError(f"site.origin must start with http:// or https:// (got {site['origin']!r})")
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
    if theme.get("mode") not in ("auto", "light", "dark"):
        raise ConfigError("theme.mode must be auto, light or dark")
    try:
        theme["width"] = int(theme.get("width") or 720)
    except (TypeError, ValueError):
        raise ConfigError("theme.width must be a number of pixels, e.g. 720") from None
    if not 480 <= theme["width"] <= 1200:
        raise ConfigError("theme.width should be between 480 and 1200 pixels")

    home = cfg["home"]
    if not isinstance(home.get("show"), list):
        raise ConfigError("home.show must be a list, e.g. [latest, series, map]")


def kind_id_prefix(cfg, kind: str) -> str:
    """The id prefix for a kind: the singular label in lowercase (``posts`` -> ``post``)."""
    singular = str(cfg["kinds"][kind].get("singular") or kind)
    return re.sub(r"[^a-z0-9]+", "-", singular.lower()).strip("-") or kind
