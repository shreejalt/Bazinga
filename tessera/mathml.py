r"""LaTeX to MathML, made safe for browsers.

latex2mathml does the conversion. Around it this module adds the fixes that browsers need (see docs/research.md §5):

**Pre-processing** (on the LaTeX):

- ``aligned``/``align``/``align*``/``gather``/``gather*``/``split`` become ``\begin{array}{rl…}`` (latex2mathml would
  print a literal ``&`` and a line-break attribute browsers ignore); ``equation`` wrappers are dropped.
- ``\\[4pt]`` becomes ``\\`` (the spacing would be printed as text).
- ``\arg``, ``\argmax``, ``\argmin`` and ``\operatorname*{…}`` become ``\operatorname{…}``; spacing commands inside the
  name are removed (``arg\,max`` would break the name into letters). Names written with a star keep their limits
  under them in display maths.
- ``\boldsymbol`` and ``\bm`` become ``\mathbf`` (Chromium ignores bold-italic).
- ``\big``, ``\Big``, ``\bigg``, ``\Bigg`` and their ``l``/``r``/``m`` forms are dropped (MathML stretches fences).
- ``\not=`` becomes ``\neq``; a one-letter ``\mathrm{d}`` stays upright.
- ``\tag{..}`` and ``\label{..}`` are taken out by :func:`split_tag_label` and become the equation number.

**Post-processing** (on the MathML): bold digits become Unicode bold digits, ``\mathrm{ReLU}`` becomes one upright
identifier, symbols that latex2mathml marks as identifiers (``\langle``, ``\pm``, ``\sim`` …) become operators, a
negative thin space gets a real width, ``\text`` keeps its edge spaces, and in display maths ``\max_x``, ``\lim`` and
starred operator names put their subscript underneath.

**Validation** rejects any output that still holds a raw ``\command``, ``menclose``, ``mfenced`` or ``linebreak=``.
Each failure raises :class:`MathError` with a plain-English hint and the line inside the LaTeX where it happened.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from latex2mathml.converter import convert

MATHML_NS = "http://www.w3.org/1998/Math/MathML"


class MathError(Exception):
    """A formula that browsers cannot show correctly.

    ``message`` says what is wrong, ``hint`` how to fix it, ``offset`` is the 0-based line inside the formula.
    """

    def __init__(self, message: str, hint: str = "", offset: int = 0):
        super().__init__(message)
        self.message, self.hint, self.offset = message, hint, offset

    def __str__(self) -> str:
        return self.message + (f" Hint: {self.hint}" if self.hint else "")


# Commands browsers cannot draw, with what to do instead. Checked before conversion for a precise message.
UNSUPPORTED = {
    "cancel": "\\cancel is not supported in browsers' math; try \\not, colour (\\color{gray}{x}) or a note in the text",
    "bcancel": "\\bcancel is not supported in browsers' math; try colour (\\color{gray}{x}) or a note in the text",
    "xcancel": "\\xcancel is not supported in browsers' math; try colour (\\color{gray}{x}) or a note in the text",
    "boxed": "\\boxed is not supported in browsers' math; put the formula in a callout (> [!KEY]) instead",
    "fbox": "\\fbox is not supported in browsers' math; put the formula in a callout (> [!KEY]) instead",
    "eqref": "write [eq:name] in the text, outside the $$ … $$, to refer to a numbered equation",
    "ref": "write [eq:name] in the text, outside the $$ … $$, to refer to a numbered equation",
    "require": "extensions cannot be loaded; only standard LaTeX maths is available",
    "hline": "horizontal rules inside arrays are not supported; leave a blank row or use a table",
    "intertext": "\\intertext is not supported; end the equation, write the text, and start a new one",
    "multline": "multline is not supported; use \\begin{array}{l} … \\end{array} with one line per row",
}

_ENV_TO_ARRAY = ("aligned", "align", "align*", "alignat", "alignat*", "gather", "gather*", "gathered", "split",
                 "flalign", "flalign*")
_LIMIT_NAMES = {"lim", "liminf", "limsup", "max", "min", "sup", "inf", "argmax", "argmin", "det", "Pr", "gcd",
                "arg max", "arg min"}
_MI_TO_MO = {"\u27e8", "\u27e9", "\u00b1", "\u007e", "\u27fa", "\u27c2", "\u2223", "\u2225", "\u00ac", "\u2026"}
_BOLD_DIGIT = {str(d): chr(0x1D7CE + d) for d in range(10)}
_BOLD_UPPER = {chr(65 + i): chr(0x1D400 + i) for i in range(26)}
_BOLD_LOWER = {chr(97 + i): chr(0x1D41A + i) for i in range(26)}


# --------------------------------------------------------------------------------------------- tags and labels
_TAG = re.compile(r"\\tag\*?\s*\{([^{}]*)\}")
_LABEL = re.compile(r"\\label\s*\{([^{}]*)\}")


def split_tag_label(tex: str) -> tuple[str, str | None, str | None]:
    r"""Take ``\tag{..}`` and ``\label{..}`` out of a display formula: (formula, tag text, label)."""
    tag = label = None
    m = _TAG.search(tex)
    if m:
        tag = m.group(1).strip()
        tex = tex[:m.start()] + tex[m.end():]
    m = _LABEL.search(tex)
    if m:
        label = m.group(1).strip()
        tex = tex[:m.start()] + tex[m.end():]
    return tex, tag, label


# ------------------------------------------------------------------------------------------------ pre-processing
def _line_of(tex: str, index: int) -> int:
    return tex.count("\n", 0, max(0, index))


def _check_unsupported(tex: str) -> None:
    for m in re.finditer(r"\\([A-Za-z]+)", tex):
        name = m.group(1)
        if name in UNSUPPORTED:
            raise MathError(f"\\{name} cannot be shown in browsers.", UNSUPPORTED[name], _line_of(tex, m.start()))
        if name == "begin":
            env = re.match(r"\\begin\s*\{([^}]*)\}", tex[m.start():])
            if env and env.group(1) in UNSUPPORTED:
                raise MathError(f"the {env.group(1)} environment cannot be shown in browsers.",
                                UNSUPPORTED[env.group(1)], _line_of(tex, m.start()))
    for m in _TAG.finditer(tex):
        raise MathError("\\tag only works in display maths.", "put the formula on its own lines between $$ … $$",
                        _line_of(tex, m.start()))
    for m in _LABEL.finditer(tex):
        raise MathError("\\label only works in display maths.", "put the formula on its own lines between $$ … $$",
                        _line_of(tex, m.start()))


def _rewrite_environments(tex: str) -> str:
    """aligned/align/gather/split -> array with rl column pairs; equation wrappers dropped."""
    tex = re.sub(r"\\(?:begin|end)\s*\{equation\*?\}", "", tex)

    def repl(m: re.Match) -> str:
        env, inner = m.group(1), m.group(3)
        rows = re.split(r"\\\\", inner)
        if env.startswith("gather"):
            cols = "c"
        else:
            n = max((len(re.findall(r"(?<!\\)&", r)) for r in rows), default=0) + 1
            cols = ("rl" * n)[:n]
        # "&=" would start a cell with a bare relation; "{}" gives it a left operand so it is spaced as in TeX.
        inner = re.sub(r"(?<!\\)&\s*(?=[=<>+\-]|\\(?:le|ge|leq|geq|approx|equiv|sim|simeq|propto|neq|to|in|"
                       r"subset|subseteq|cdot|times|coloneqq|triangleq|ll|gg)\b)", "&{}", inner)
        return f"\\begin{{array}}{{{cols}}}{inner}\\end{{array}}"

    names = "|".join(re.escape(e) for e in _ENV_TO_ARRAY)
    pattern = re.compile(r"\\begin\s*\{(" + names + r")\}(\{[^}]*\})?(.*?)\\end\s*\{\1\}", re.S)
    prev = None
    while prev != tex:
        prev, tex = tex, pattern.sub(repl, tex)
    return tex


def _clean_operator_names(tex: str, starred: set) -> str:
    def repl(m: re.Match) -> str:
        star, name = m.group(1), m.group(2)
        clean = re.sub(r"\\[,;:! ]|\\quad|\\qquad|\s+", "", name)
        if star:
            starred.add(clean)
        return f"\\operatorname{{{clean}}}"

    return re.sub(r"\\operatorname(\*?)\s*\{([^{}]*)\}", repl, tex)


_GREEK_LOWER = ["alpha", "beta", "gamma", "delta", "varepsilon", "zeta", "eta", "theta", "iota", "kappa", "lambda",
                "mu", "nu", "xi", "omicron", "pi", "rho", "varsigma", "sigma", "tau", "upsilon", "varphi", "chi",
                "psi", "omega", "partial", "epsilon", "vartheta", "varkappa", "phi", "varrho", "varpi"]
_GREEK_UPPER = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta", "Eta", "Theta", "Iota", "Kappa", "Lambda", "Mu",
                "Nu", "Xi", "Omicron", "Pi", "Rho", "varTheta", "Sigma", "Tau", "Upsilon", "Phi", "Chi", "Psi",
                "Omega", "nabla"]


def _bold_greek(tex: str) -> str:
    r"""Greek letters inside \mathbf / \boldsymbol / \bm become Unicode bold letters (browsers ignore bold styles).

    \boldsymbol and \bm give bold italic lowercase, as TeX does; \mathbf gives bold upright.
    """
    def letter(name: str, italic: bool) -> str | None:
        if name in _GREEK_LOWER:
            return chr((0x1D736 if italic else 0x1D6C2) + _GREEK_LOWER.index(name))
        if name in _GREEK_UPPER:
            return chr((0x1D71C if italic else 0x1D6A8) + _GREEK_UPPER.index(name))
        return None

    def group(m: re.Match) -> str:
        italic = m.group(1) != "mathbf"
        arg = m.group(2) if m.group(2) is not None else m.group(3)
        new = re.sub(r"\\([A-Za-z]+)", lambda g: letter(g.group(1), italic) or g.group(0), arg)
        return f"\\mathbf{{{new}}}"

    return re.sub(r"\\(mathbf|boldsymbol|bm)(?![A-Za-z])\s*(?:\{([^{}]*)\}|(\\[A-Za-z]+))", group, tex)


def preprocess(tex: str) -> tuple[str, set]:
    """Apply every LaTeX rewrite. Returns the new LaTeX and the operator names that take limits underneath."""
    starred: set = set()
    tex = _rewrite_environments(tex)
    tex = re.sub(r"\\\\\s*\[[^\]]*\]", r"\\\\", tex)                         # \\[4pt] -> \\
    tex = re.sub(r"\\argmax(?![A-Za-z])", r"\\operatorname*{argmax}", tex)
    tex = re.sub(r"\\argmin(?![A-Za-z])", r"\\operatorname*{argmin}", tex)
    tex = re.sub(r"\\arg(?![A-Za-z])", r"\\operatorname{arg}", tex)
    tex = _clean_operator_names(tex, starred)
    tex = _bold_greek(tex)
    tex = re.sub(r"\\(?:boldsymbol|bm)(?![A-Za-z])", r"\\mathbf", tex)
    tex = re.sub(r"\\(?:big|Big|bigg|Bigg)[lrm]?(?![A-Za-z])\s*", "", tex)
    tex = re.sub(r"\\not\s*=", r"\\neq ", tex)
    tex = re.sub(r"\\mathrm\s*\{\s*([A-Za-z])\s*\}", r"\\text{\1}", tex)
    return tex, starred


# ----------------------------------------------------------------------------------------------- post-processing
def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _to_unicode_bold(text: str) -> str:
    return "".join(_BOLD_DIGIT.get(c) or _BOLD_UPPER.get(c) or _BOLD_LOWER.get(c) or c for c in text)


def _fix_tokens(root: ET.Element) -> None:
    for el in root.iter():
        tag = _local(el.tag)
        variant = el.get("mathvariant")
        if tag in ("mi", "mn", "mo") and variant and variant.startswith("bold"):
            el.text = _to_unicode_bold(el.text or "")
            del el.attrib["mathvariant"]
        elif tag == "mtext" and variant:
            if "bold" in variant:
                el.set("style", "font-weight:bold")
            if "italic" in variant:
                el.set("style", (el.get("style", "") + ";font-style:italic").lstrip(";"))
            del el.attrib["mathvariant"]
        if tag == "mi" and (el.text or "") in _MI_TO_MO:
            el.tag = el.tag[:-2] + "mo"
        if tag == "mspace" and el.get("width") == "negativethinmathspace":
            el.set("width", "-0.1667em")
        if tag == "mtext" and el.text:
            el.text = re.sub(r"^ | $", "\u00a0", el.text)


def _merge_upright_runs(root: ET.Element) -> None:
    r"""``<mi mathvariant=normal>R</mi><mi …>e</mi>…`` (from \mathrm{ReLU}) -> one ``<mi>ReLU</mi>``."""
    for parent in root.iter():
        children = list(parent)
        i = 0
        while i < len(children):
            run = []
            while (i + len(run) < len(children) and _local(children[i + len(run)].tag) == "mi"
                   and children[i + len(run)].get("mathvariant") == "normal"):
                run.append(children[i + len(run)])
            if len(run) > 1:
                first = run[0]
                first.text = "".join(c.text or "" for c in run)
                del first.attrib["mathvariant"]
                for extra in run[1:]:
                    parent.remove(extra)
                children = list(parent)
            i += 1


def _limits_underneath(root: ET.Element, starred: set) -> None:
    """In display maths, ``\\max_x`` and friends put the subscript under the operator, as TeX does."""
    names = _LIMIT_NAMES | starred
    swap = {"msub": "munder", "msup": "mover", "msubsup": "munderover"}
    for el in root.iter():
        tag = _local(el.tag)
        if tag in swap and len(el) and _local(el[0].tag) == "mo" and (el[0].text or "").strip() in names:
            el.tag = el.tag[: -len(tag)] + swap[tag]
            el[0].set("movablelimits", "true")


_FENCES = set("([{|\u2016\u27e8\u2308\u230a)]}\u27e9\u2309\u230b")
_FUNCTIONS = {"log", "ln", "lg", "exp", "sin", "cos", "tan", "sec", "csc", "cot", "sinh", "cosh", "tanh", "coth",
              "arcsin", "arccos", "arctan", "dim", "ker", "deg", "hom", "Pr", "det", "gcd", "max", "min", "sup",
              "inf", "lim", "liminf", "limsup", "arg"}
_SCRIPTED = {"msub", "msup", "msubsup", "munder", "mover", "munderover"}


def _display_tables(root: ET.Element) -> None:
    """In display maths, rows made from aligned/array are display style (big sums, full-size fractions), as in TeX.

    Tables next to a fence (matrices, cases) keep the compact style.
    """
    for parent in root.iter():
        kids = list(parent)
        for i, el in enumerate(kids):
            if _local(el.tag) != "mtable":
                continue
            near = [kids[j] for j in (i - 1, i + 1) if 0 <= j < len(kids)]
            fenced = any(_local(n.tag) == "mo" and (n.text or "").strip() in _FENCES for n in near)
            if not fenced:
                el.set("displaystyle", "true")


def _operator_spacing(root: ET.Element) -> None:
    """Named operators (softmax, log, max …) are upright words with TeX's spacing: a thin space before them unless an
    operator precedes, and none after them when a bracket follows."""
    parents = {c: p for p in root.iter() for c in p}
    for el in list(root.iter()):
        tag, text = _local(el.tag), (el.text or "").strip()
        if tag not in ("mi", "mo") or len(text) < 2 or not text.replace(" ", "").isalpha():
            continue
        if tag == "mi" and text not in _FUNCTIONS:
            continue
        el.tag = el.tag[: -len(tag)] + "mo"
        outer = el
        parent = parents.get(el)
        if parent is not None and _local(parent.tag) in _SCRIPTED and len(parent) and parent[0] is el:
            outer, parent = parent, parents.get(parent)
        if parent is None:
            continue
        kids = list(parent)
        i = kids.index(outer)
        prev = kids[i - 1] if i > 0 else None
        nxt = kids[i + 1] if i + 1 < len(kids) else None
        el.set("lspace", "0" if prev is None or _local(prev.tag) == "mo" else "0.1667em")
        opens = nxt is not None and ((_local(nxt.tag) == "mo" and (nxt.text or "").strip() in _FENCES) or
                                     (_local(nxt.tag) == "mrow" and len(nxt) and _local(nxt[0].tag) == "mo"
                                      and (nxt[0].text or "").strip() in _FENCES))
        el.set("rspace", "0" if opens or nxt is None or _local(nxt.tag) == "mo" else "0.1667em")


def _serialise(root: ET.Element) -> str:
    ET.register_namespace("", MATHML_NS)
    out = ET.tostring(root, encoding="unicode", short_empty_elements=False)
    return out.replace(f' xmlns:ns0="{MATHML_NS}"', "").replace("ns0:", "")


def postprocess(mathml: str, display: bool, starred: set, tex: str) -> str:
    root = ET.fromstring(mathml)
    _fix_tokens(root)
    _merge_upright_runs(root)
    _operator_spacing(root)
    if display:
        _limits_underneath(root, starred)
        _display_tables(root)
    root.set("display", "block" if display else "inline")
    # Keep the source as an annotation: copy-paste, screen readers and search all see the LaTeX.
    body = list(root)
    root.clear()
    root.set("display", "block" if display else "inline")
    semantics = ET.SubElement(root, f"{{{MATHML_NS}}}semantics")
    row = ET.SubElement(semantics, f"{{{MATHML_NS}}}mrow")
    row.extend(body)
    ann = ET.SubElement(semantics, f"{{{MATHML_NS}}}annotation", {"encoding": "application/x-tex"})
    ann.text = tex.strip()
    return _serialise(root)


# ------------------------------------------------------------------------------------------------------ validation
_LEAK = re.compile(r"<(m[a-z]+)[^>]*>\s*(\\[A-Za-z]+|\\[^A-Za-z\s])")


def validate(mathml: str, tex: str) -> None:
    """Reject output that browsers would show wrongly. The LaTeX is used to find the offending line."""
    body = mathml.split("<annotation", 1)[0]
    m = _LEAK.search(body)
    if m:
        cmd = m.group(2)
        raise MathError(f"{cmd} is not a command this converter knows, so it would show as raw text.",
                        _hint_for_unknown(cmd), _line_of(tex, tex.find(cmd)))
    if "menclose" in body:
        raise MathError("this formula uses a box or strike-through that browsers cannot draw.",
                        UNSUPPORTED["cancel"], 0)
    if "mfenced" in body:
        raise MathError("this formula produced a fence browsers do not support.",
                        "use \\left( … \\right) or plain brackets", 0)
    if "linebreak=" in body:
        idx = tex.find("\\\\")
        raise MathError("a line break (\\\\) outside an array is ignored by browsers.",
                        "wrap the rows in \\begin{array}{l} … \\end{array} (or {rl} with & to align)",
                        _line_of(tex, idx))
    if re.search(r"<munderover>\s*</munderover>", body):
        raise MathError("\\limits must follow an operator such as \\sum.", "write \\sum\\limits_{i}", 0)


_SUGGEST = {
    "\\softmax": "write \\operatorname{softmax}",
    "\\relu": "write \\operatorname{ReLU}",
    "\\R": "write \\mathbb{R}",
    "\\N": "write \\mathbb{N}",
    "\\Z": "write \\mathbb{Z}",
    "\\E": "write \\mathbb{E}",
    "\\abs": "write \\lvert x \\rvert",
    "\\norm": "write \\lVert x \\rVert",
    "\\dd": "write \\mathrm{d}",
    "\\T": "write ^\\top for a transpose",
}


def _hint_for_unknown(cmd: str) -> str:
    if cmd in _SUGGEST:
        return _SUGGEST[cmd]
    if cmd.startswith("\\") and cmd[1:].isalpha():
        return (f"check the spelling of {cmd}; for a named function write \\operatorname{{{cmd[1:]}}}, "
                f"for words write \\text{{…}}")
    return "escape special characters: \\{ \\} \\% \\# \\_ \\$"


# ---------------------------------------------------------------------------------------------------------- public
def to_mathml(tex: str, display: bool) -> str:
    """Convert one formula. Raises MathError with a hint when browsers could not show it correctly.

    ``tex`` must not contain ``\\tag``/``\\label`` (use :func:`split_tag_label` on display maths first).
    """
    if not tex.strip():
        raise MathError("the formula is empty.", "write something between the $ signs, or remove them")
    if tex.count("{") - tex.count("\\{") != tex.count("}") - tex.count("\\}"):
        raise MathError("the braces { } are not balanced.", "every { needs a matching }", 0)
    _check_unsupported(tex)
    clean, starred = preprocess(tex)
    try:
        raw = convert(clean, display="block" if display else "inline")
    except Exception as exc:                                                     # noqa: BLE001 - library errors vary
        raise MathError(f"the formula could not be read ({type(exc).__name__}: {exc}).",
                        "look for a missing brace, a stray & or an unfinished \\begin{…}", 0) from None
    try:
        out = postprocess(raw, display, starred, tex)
    except ET.ParseError as exc:
        raise MathError(f"the formula produced invalid markup ({exc}).", "simplify the formula", 0) from None
    validate(out, tex)
    return out
