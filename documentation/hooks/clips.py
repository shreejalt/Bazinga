"""MkDocs hook: turn a line ``::clip <name> | <caption>`` into a looping video.

The clip files come from documentation/recordings/make.py and live in documentation/assets/clips/:
<name>.webm and <name>.mp4 (the video) and <name>.jpg (the poster frame shown before it plays), and <name>.json (what the window bar above the clip says).
MkDocs does not rewrite paths inside raw HTML, so this hook writes each path relative to the page.

A terminal clip is also followed by the commands typed in it (read from recordings/tapes/<name>.tape), as a code
block with a copy button that shows on narrow screens only, where the clip's text is too small to read.

A clip that has not been recorded yet is a warning, so `mkdocs build --strict` fails until it exists.
Set BAZINGA_DOCS_DRAFT=1 while writing to show a grey placeholder instead.
"""
from __future__ import annotations

import html
import json
import logging
import os
import re
from pathlib import Path

log = logging.getLogger("mkdocs.hooks.clips")
CLIP = re.compile(r"^(\s*)::clip\s+([a-z0-9][a-z0-9-]*)\s*(?:\|\s*(.+?))?\s*$")
FENCE = re.compile(r"^\s*(```|~~~)")
TYPED = re.compile(r"""^Type\s+(?:"(.*)"|'(.*)'|`(.*)`)\s*$""")


def _typed(tape: Path) -> list[str]:
    """The commands typed on camera in a VHS tape (between Show and Hide), one per Enter."""
    if not tape.exists():
        return []
    shown, cmds, line = True, [], ""
    for raw in tape.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if raw == "Hide":
            shown = False
        elif raw == "Show":
            shown, line = True, ""
        elif shown and TYPED.match(raw):
            m = TYPED.match(raw)
            line += next(g for g in m.groups() if g is not None)
        elif shown and raw.startswith("Enter") and line:
            cmds.append(line)
            line = ""
    return cmds


def _prefix(page) -> str:
    url = page.url.strip("/")
    return "../" * (len(url.split("/")) if url else 0)


def on_page_markdown(markdown, page, config, files):
    clips = Path(config["docs_dir"]) / "assets" / "clips"
    out, fence = [], None
    for line in markdown.split("\n"):
        m = FENCE.match(line)
        if m:
            fence = None if fence == m.group(1) else (fence or m.group(1))
        match = None if fence else CLIP.match(line)
        if not match:
            out.append(line)
            continue
        indent, name, caption = match.group(1), match.group(2), html.escape(match.group(3) or "")
        missing = [ext for ext in ("mp4", "webm", "jpg") if not (clips / f"{name}.{ext}").exists()]
        if missing:
            msg = f"{page.file.src_uri}: clip '{name}' is not recorded yet (missing {', '.join(missing)})"
            if os.environ.get("BAZINGA_DOCS_DRAFT"):
                log.info(msg)
                out.append(f'{indent}<div class="clip clip-missing">Clip “{name}” will appear here.</div>')
                continue
            log.warning(msg)
            continue
        base = _prefix(page) + "assets/clips/" + name
        label = caption or name.replace("-", " ")
        info = {}
        if (clips / f"{name}.json").exists():
            info = json.loads((clips / f"{name}.json").read_text(encoding="utf-8"))
        kind = info.get("kind", "browser")
        bar = html.escape(info.get("bar") or ("Terminal" if kind == "terminal" else ""))
        w, h = info.get("width", 1280), info.get("height", 800)
        out.append(
            f'{indent}<figure class="clip clip-{kind}">'
            f'<div class="clip-bar" aria-hidden="true"><i></i><i></i><i></i><span>{bar}</span></div>'
            f'<video autoplay loop muted playsinline preload="none" poster="{base}.jpg" '
            f'width="{w}" height="{h}" aria-label="{label}">'
            f'<source src="{base}.webm" type="video/webm"><source src="{base}.mp4" type="video/mp4">'
            f'</video>' + (f"<figcaption>{caption}</figcaption>" if caption else "") + "</figure>")
        cmds = _typed(Path(config["docs_dir"]) / "recordings" / "tapes" / f"{name}.tape") if kind == "terminal" else []
        if cmds:
            out += ["", f'{indent}<div class="clip-steps" markdown>', "",
                    f'{indent}```bash title="Typed in the clip"', *[indent + c for c in cmds], f"{indent}```",
                    "", f"{indent}</div>", ""]
    return "\n".join(out)
