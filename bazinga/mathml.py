r"""LaTeX to MathML, made safe for browsers.

latex2mathml does the conversion. Around it this module adds what browsers need (docs/research.md §5), in four steps:

**Diagnosis** (:func:`diagnose`, on the LaTeX as written): finds the mistakes people make most and says where they
are, what is wrong and what to write instead: an unclosed or extra brace, ``\left`` without ``\right``, a
``\begin{…}`` without its ``\end``, ``&`` or ``\\`` outside a block of rows, ``x^10`` (only the 1 is raised), a
double superscript, ``\frac`` with one part, a ``$`` inside the formula, unknown commands (with "did you mean"),
package commands that have no browser form, and maths inside ``\text{…}``.

**Pre-processing** (on the LaTeX):

- ``aligned``/``align``/``gather``/``split``/``multline``/``flalign``/``alignat`` become ``\begin{array}{rl…}``
  (latex2mathml would print a literal ``&`` and a line-break attribute browsers ignore); ``equation`` wrappers,
  ``\nonumber`` and ``\notag`` are dropped; rows separated by ``\\`` in display maths without a block are wrapped in
  one.
- ``\\[4pt]`` becomes ``\\`` (the spacing would be printed as text); ``%`` comments are removed.
- ``\arg``, ``\argmax``, ``\argmin`` and ``\operatorname*{…}`` become ``\operatorname{…}``; spacing commands inside the
  name are removed. Names written with a star keep their limits under them in display maths.
- ``\boldsymbol``, ``\bm``, ``\symbf`` and ``\pmb`` become ``\mathbf`` (Chromium ignores bold-italic); bold Greek
  becomes Unicode bold letters.
- ``\big( … \big)`` keep their size; their delimiter commands become characters (``\big\langle`` would leak).
- ``\xrightarrow{…}`` and friends become an arrow under its label; ``{n \choose k}`` becomes ``\binom{n}{k}``;
  ``\mathds``/``\mathbbm`` become ``\mathbb``; ``\mbox`` becomes ``\text``; ``\mathclap`` and its kin are unwrapped.
- ``\tag{..}`` and ``\label{..}`` are taken out by :func:`split_tag_label` and become the equation number.

**Post-processing** (on the MathML), so the output is plain MathML Core that Chrome, Safari and Firefox draw alike:
every ``mathvariant`` (bold, script, double-struck, fraktur, sans, monospace, italic …) becomes the Unicode letters
themselves; symbols are sorted into operators (``≤``, ``⟨``, ``→`` …) and ordinary symbols (``∞``, ``∂``, ``∇``,
``⊤``); ``|`` and ``‖`` get TeX's spacing; big operators (``\sum``, ``\prod``, ``\bigcup`` …) and ``\lim``/``\max``
names put their limits underneath in display maths and beside in text; colours, sizes, column alignment, ``\hline``
and ``c|c`` rules, boxes (``\boxed``) and strike-throughs (``\cancel``) become CSS on the element; ``mu`` and named
spaces become ``em``; ``\mathrm{ReLU}`` is one upright word; named operators get TeX's thin spaces; aligned rows sit
flush around their ``&`` and in display style.

**Validation** rejects any output that still holds a raw ``\command`` or an element or attribute outside MathML Core.
Each failure raises :class:`MathError` with what is wrong, what to write instead, and where (line and column inside
the formula).
"""
from __future__ import annotations

import difflib
import re
import unicodedata
import xml.etree.ElementTree as ET

from latex2mathml.converter import convert

MATHML_NS = "http://www.w3.org/1998/Math/MathML"


class MathError(Exception):
    """A formula that browsers cannot show correctly.

    ``message`` says what is wrong, ``hint`` what to write instead. ``offset`` is the 0-based line inside the formula
    and ``column`` the 0-based column on that line; ``index`` is the character position in the formula and ``length``
    how many characters the problem spans (for underlining). Positions are ``None`` when they are not known.
    """

    def __init__(self, message: str, hint: str = "", offset: int = 0, *, index: int | None = None,
                 column: int | None = None, length: int = 1):
        super().__init__(message)
        self.message, self.hint, self.offset = message, hint, offset
        self.index, self.column, self.length = index, column, max(1, length)

    @classmethod
    def at(cls, tex: str, index: int, message: str, hint: str = "", length: int = 1) -> "MathError":
        index = max(0, min(index, len(tex)))
        line = tex.count("\n", 0, index)
        column = index - (tex.rfind("\n", 0, index) + 1)
        return cls(message, hint, line, index=index, column=column, length=length)

    def __str__(self) -> str:
        return self.message + (f" Hint: {self.hint}" if self.hint else "")

    def to_dict(self) -> dict:
        return {"message": self.message, "hint": self.hint, "line": self.offset, "column": self.column,
                "index": self.index, "length": self.length}


# ------------------------------------------------------------------------------------------------- vocabulary
# Commands browsers cannot draw (or that only work in a full LaTeX document), with what to write instead.
UNSUPPORTED = {
    "eqref": "write [eq:name] in the text, outside the $$ … $$, to refer to a numbered equation",
    "ref": "write [eq:name] in the text, outside the $$ … $$, to refer to a numbered equation",
    "require": "extensions cannot be loaded; only standard LaTeX maths is available",
    "intertext": "end the equation, write the text as an ordinary sentence, and start a new $$ … $$",
    "shortintertext": "end the equation, write the text as an ordinary sentence, and start a new $$ … $$",
    "newcommand": "macros cannot be defined; write the full form each time, e.g. \\operatorname{tr}(A) or \\mathbb{R}",
    "renewcommand": "macros cannot be defined; write the full form each time, e.g. \\operatorname{tr}(A)",
    "def": "macros cannot be defined; write the full form each time, e.g. \\operatorname{tr}(A)",
    "let": "macros cannot be defined; write the full form each time",
    "DeclareMathOperator": "write \\operatorname{name} where you use it, e.g. \\operatorname{tr}(A)",
    "newenvironment": "environments cannot be defined; use aligned, cases or a matrix",
    "ce": "chemistry needs a package browsers do not have; write \\mathrm{H_2O} for formulas",
    "pu": "write units as text: 3\\,\\text{kg}",
    "si": "write units as text: \\text{m/s}",
    "SI": "write the number and the unit: 3\\,\\text{m/s}",
    "unit": "write units as text: \\text{m/s}",
    "qty": "write the number and the unit: 3\\,\\text{m/s}",
    "pdv": "write \\frac{\\partial f}{\\partial x}",
    "dv": "write \\frac{\\mathrm{d} f}{\\mathrm{d} x}",
    "href": "put links in the sentence around the equation, not inside it",
    "url": "put links in the sentence around the equation, not inside it",
    "verb": "write \\texttt{…} for code-like text",
    "unicode": "type the character itself (e.g. ⊛) instead of \\unicode",
    "class": "write \\color{…}{…} to colour part of a formula",
    "style": "write \\color{…}{…} to colour part of a formula",
    "cssId": "equations can be named with {#eq:name} after the closing $$",
    "sideset": "write {}_{a}^{b}\\sum for scripts on the left of an operator",
    "prescript": "write {}_{a}^{b}X for scripts on the left",
    "mathchoice": "write the version you want directly",
    "genfrac": "write \\frac{a}{b} or \\binom{n}{k}",
    "atop": "write \\begin{array}{c} a \\\\ b \\end{array}, or \\binom{a}{b} for a binomial",
    "raise": "move things with \\overset{…}{…} or \\underset{…}{…}",
    "lower": "move things with \\overset{…}{…} or \\underset{…}{…}",
    "hfill": "spaces inside maths are \\quad or \\qquad",
    "hfil": "spaces inside maths are \\quad or \\qquad",
    "displaybreak": "split long equations into rows with \\begin{aligned} … \\end{aligned}",
    "allowbreak": "split long equations into rows with \\begin{aligned} … \\end{aligned}",
    "hdashline": "use \\hline for a rule between rows (dashed rules are not available)",
    "cline": "use \\hline for a rule across the whole row",
    "label": "\\label only works in displayed equations; put the formula between $$ on its own lines",
    "tag": "\\tag only works in displayed equations; put the formula between $$ on its own lines",
    "operatornamewithlimits": "write \\operatorname*{name}",
}

# Common names people expect but LaTeX does not define, with what to write.
SUGGEST = {
    "softmax": "write \\operatorname{softmax}", "relu": "write \\operatorname{ReLU}", "ReLU": "write \\operatorname{ReLU}",
    "sigmoid": "write \\sigma or \\operatorname{sigmoid}", "tr": "write \\operatorname{tr}",
    "trace": "write \\operatorname{tr}", "diag": "write \\operatorname{diag}", "rank": "write \\operatorname{rank}",
    "sign": "write \\operatorname{sign}", "sgn": "write \\operatorname{sgn}", "Var": "write \\operatorname{Var}",
    "Cov": "write \\operatorname{Cov}", "KL": "write D_{\\mathrm{KL}}(p \\parallel q)",
    "softplus": "write \\operatorname{softplus}", "erf": "write \\operatorname{erf}",
    "R": "write \\mathbb{R}", "N": "write \\mathbb{N}", "Z": "write \\mathbb{Z}", "Q": "write \\mathbb{Q}",
    "C": "write \\mathbb{C}", "E": "write \\mathbb{E}", "P": "write \\mathbb{P} or P",
    "abs": "write \\lvert x \\rvert", "norm": "write \\lVert x \\rVert", "dd": "write \\mathrm{d}",
    "T": "write ^\\top for a transpose", "transpose": "write ^\\top", "eps": "write \\epsilon or \\varepsilon",
    "half": "write \\frac{1}{2}", "grad": "write \\nabla", "deriv": "write \\frac{\\mathrm{d}f}{\\mathrm{d}x}",
    "expval": "write \\langle x \\rangle", "vect": "write \\mathbf{v} or \\vec{v}", "bbR": "write \\mathbb{R}",
    "Reals": "write \\mathbb{R}", "naturals": "write \\mathbb{N}", "argsort": "write \\operatorname{argsort}",
    "sinc": "write \\operatorname{sinc}", "tensor": "write \\otimes", "dag": "write ^\\dagger",
    "bold": "write \\mathbf{…}", "mathbbm": "write \\mathbb{1}", "one": "write \\mathbb{1} or \\mathbf{1}",
    "indicator": "write \\mathbb{1}", "ind": "write \\mathbb{1}", "set": "write \\{ x \\mid x > 0 \\}",
    "Set": "write \\left\\{ x \\mid x > 0 \\right\\}", "lr": "write \\left( … \\right)",
    "ip": "write \\langle x, y \\rangle", "inner": "write \\langle x, y \\rangle",
}

# Commands this module handles itself before conversion (in addition to the converter's own).
_OWN = {"argmax", "argmin", "arg", "boldsymbol", "bm", "symbf", "symit", "symcal", "symbb", "symrm", "symsf", "symtt",
        "mathbbm", "mathds", "mbox", "ensuremath", "mathclap", "mathrlap", "mathllap", "clap", "rlap", "llap", "notag",
        "nonumber", "xrightarrow", "xleftarrow", "xRightarrow", "xLeftarrow", "xleftrightarrow", "xLeftrightarrow",
        "xmapsto", "xlongequal", "xhookrightarrow", "xhookleftarrow", "xtwoheadrightarrow", "xtwoheadleftarrow",
        "choose", "cfrac", "dfrac", "tfrac", "dbinom", "tbinom", "intercal", "coloneqq", "eqqcolon", "lvert", "rvert",
        "lVert", "rVert", "text", "hline", "boxed", "cancel", "bcancel", "xcancel", "fbox", "color", "textcolor",
        "Bbbk", "mathscr", "vcentcolon", "iff", "implies", "impliedby", "land", "lor", "lnot", "gets", "to",
        "varnothing", "emptyset", "mid", "nmid", "parallel", "nparallel", "middle", "dotsc", "dotsb", "dotsm",
        "dotsi", "dotso", "mathbfit", "bmod", "pmod", "mod", "pod", "operatorname", "limits", "nolimits",
        "displaystyle", "textstyle", "scriptstyle", "scriptscriptstyle", "not", "neq", "ne", "colon", "tiny", "Tiny",
        "scriptsize", "footnotesize", "small", "normalsize", "large", "Large", "LARGE", "huge", "Huge",
        "lbrace", "rbrace", "lbrack", "rbrack", "lgroup", "rgroup", "lmoustache", "rmoustache"}

_ENV_TO_ARRAY = ("aligned", "align", "align*", "alignat", "alignat*", "gather", "gather*", "gathered", "split",
                 "flalign", "flalign*", "alignedat", "multline", "multline*", "eqnarray", "eqnarray*")
_ROW_ENVS = set(_ENV_TO_ARRAY) | {"array", "matrix", "pmatrix", "bmatrix", "Bmatrix", "vmatrix", "Vmatrix",
                                  "smallmatrix", "cases", "dcases", "rcases", "matrix*", "pmatrix*", "bmatrix*",
                                  "Bmatrix*", "vmatrix*", "Vmatrix*", "subarray", "substack", "darray", "CD"}
_ENVS = _ROW_ENVS | {"equation", "equation*", "displaymath", "math"}
_NO_ENV = {"CD", "darray"}

_LIMIT_NAMES = {"lim", "liminf", "limsup", "max", "min", "sup", "inf", "argmax", "argmin", "det", "Pr", "gcd",
                "arg max", "arg min", "plim", "injlim", "projlim"}
_BIG_OPS = set("\u2211\u220f\u2210\u22c3\u22c2\u2a01\u2a02\u2a00\u22c1\u22c0\u2a04\u2a06")
_ORDINARY = set("\u2026\u22ef\u22ee\u22f1\u221e\u2205\u2202\u2207\u22a4\u22a5\u2032\u2033\u2034\u2135\u210f\u2113\u2118\u25a1\u25fb\u220e"
                "\u2020\u2021\u266d\u266e\u266f\u2663\u2662\u2661\u2660\u2200\u2203\u2204")
_ORD_OPS_KEEP = set("\u2200\u2203\u2204")      # quantifiers stay operators (prefix, with a little space after)
_OPERATOR_LIKE = set("\u27e8\u27e9\u2308\u2309\u230a\u230b\u27e6\u27e7\u00b1\u2213\u00ac")
_BAR_CHARS = {"|", "\u2016", "\u2225", "\u2223"}

_BOLD_DIGIT = {str(d): chr(0x1D7CE + d) for d in range(10)}
_BOLD_UPPER = {chr(65 + i): chr(0x1D400 + i) for i in range(26)}
_BOLD_LOWER = {chr(97 + i): chr(0x1D41A + i) for i in range(26)}


def _known_commands() -> set:
    names = set(_OWN) | set(UNSUPPORTED)
    try:
        import latex2mathml.commands as c
        from latex2mathml.symbols_parser import SYMBOLS
        for n in dir(c):
            v = getattr(c, n)
            if isinstance(v, str) and v.startswith("\\"):
                names.add(v[1:])
            elif isinstance(v, (dict, set, tuple, list, frozenset)):
                for k in v:
                    if isinstance(k, str) and k.startswith("\\"):
                        names.add(k[1:])
        names.update(k[1:] for k in SYMBOLS if isinstance(k, str) and k.startswith("\\"))
    except Exception:  # noqa: BLE001 - the list only improves messages
        pass
    return {n for n in names if n and re.fullmatch(r"[A-Za-z]+\*?", n)}


KNOWN = _known_commands()

# The commands people write most, tried first for "did you mean".
_POPULAR = """alpha beta gamma delta epsilon varepsilon zeta eta theta vartheta iota kappa lambda mu nu xi pi rho sigma
tau upsilon phi varphi chi psi omega Gamma Delta Theta Lambda Xi Pi Sigma Phi Psi Omega frac dfrac tfrac sqrt sum prod
int iint oint lim limsup liminf max min sup inf argmax argmin log ln exp sin cos tan sinh cosh tanh det mathbb mathbf
mathcal mathrm mathit mathsf mathtt mathfrak boldsymbol bm operatorname text textbf textit left right langle rangle
lVert rVert lvert rvert mid parallel cdot cdots ldots vdots ddots times div pm mp le leq ge geq ne neq approx equiv sim
simeq propto in notin subset subseteq supset supseteq cup cap setminus emptyset varnothing forall exists neg land lor
to rightarrow leftarrow Rightarrow Leftarrow Leftrightarrow leftrightarrow mapsto implies iff infty partial nabla top
bot perp hat bar tilde vec dot ddot widehat widetilde overline underline overbrace underbrace overset underset stackrel
binom quad qquad begin end hline color boxed cancel xrightarrow intercal circ odot oplus otimes star ast dagger ell
hbar Re Im aleph prime cdotp colon coloneqq triangleq nonumber notag displaystyle limits nolimits""".split()


def _did_you_mean(name: str) -> str | None:
    for pool, cutoff in ((_POPULAR, 0.7), (sorted(KNOWN), 0.8)):
        close = difflib.get_close_matches(name, pool, n=1, cutoff=cutoff)
        if close:
            return close[0]
    return None


# --------------------------------------------------------------------------------------------- tags and labels
_TAG = re.compile(r"\\tag\*?\s*\{([^{}]*)\}")
_LABEL = re.compile(r"\\label\s*\{([^{}]*)\}")


def _blank(text: str) -> str:
    """Spaces of the same length (newlines kept), so positions in the formula stay where they were."""
    return re.sub(r"[^\n]", " ", text)


def split_tag_label(tex: str) -> tuple[str, str | None, str | None]:
    r"""Take ``\tag{..}`` and ``\label{..}`` out of a display formula: (formula, tag text, label).

    They are replaced by spaces, so line and column numbers of later errors still match the source.
    """
    tag = label = None
    m = _TAG.search(tex)
    if m:
        tag = m.group(1).strip()
        tex = tex[:m.start()] + _blank(m.group(0)) + tex[m.end():]
    m = _LABEL.search(tex)
    if m:
        label = m.group(1).strip()
        tex = tex[:m.start()] + _blank(m.group(0)) + tex[m.end():]
    return tex, tag, label


# ---------------------------------------------------------------------------------------------- reading helpers
def _skip_space(tex: str, i: int) -> int:
    while i < len(tex) and tex[i] in " \t\n\r":
        i += 1
    return i


def _group_end(tex: str, i: int) -> int:
    """``tex[i]`` is ``{``: the index just after its matching ``}`` (or len(tex) when it is never closed)."""
    depth = 0
    j = i
    while j < len(tex):
        c = tex[j]
        if c == "\\":
            j += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return j + 1
        j += 1
    return len(tex)


def _arg(tex: str, i: int) -> tuple[int, int] | None:
    """One argument starting at or after ``i``: a {group}, a \\command or one character. (start, end) or None."""
    i = _skip_space(tex, i)
    if i >= len(tex):
        return None
    c = tex[i]
    if c == "{":
        return i, _group_end(tex, i)
    if c in "}&^_$#":
        return None
    if c == "\\":
        m = re.match(r"\\(?:[A-Za-z]+|.)", tex[i:], re.S)
        if m.group(0) == "\\\\":
            return None
        return i, i + len(m.group(0))
    return i, i + 1


def _opt_arg(tex: str, i: int) -> tuple[int, int] | None:
    """An optional ``[…]`` argument at ``i`` (after spaces): (start, end) including the brackets."""
    j = _skip_space(tex, i)
    if j < len(tex) and tex[j] == "[":
        depth = 0
        for k in range(j, len(tex)):
            if tex[k] == "[":
                depth += 1
            elif tex[k] == "]":
                depth -= 1
                if depth == 0:
                    return j, k + 1
    return None


def _inner(tex: str, span: tuple[int, int]) -> str:
    s = tex[span[0]:span[1]]
    return s[1:-1] if s.startswith("{") and s.endswith("}") else s


def strip_comments(tex: str) -> str:
    """Remove ``%`` comments (an unescaped % to the end of its line), keeping positions."""
    return re.sub(r"(?<!\\)((?:\\\\)*)%[^\n]*", lambda m: m.group(1) + _blank(m.group(0)[len(m.group(1)):]), tex)


# --------------------------------------------------------------------------------------------------- diagnosis
_TEXT_CMDS = {"text", "textrm", "textbf", "textit", "textsf", "texttt", "textup", "textnormal", "textmd", "mbox",
              "hbox", "emph", "fbox", "operatorname", "operatorname*"}
_TWO_ARGS = {"frac": "\\frac{top}{bottom}", "dfrac": "\\dfrac{top}{bottom}", "tfrac": "\\tfrac{top}{bottom}",
             "cfrac": "\\cfrac{top}{bottom}", "binom": "\\binom{n}{k}", "dbinom": "\\dbinom{n}{k}",
             "tbinom": "\\tbinom{n}{k}", "overset": "\\overset{above}{base}", "underset": "\\underset{below}{base}",
             "stackrel": "\\stackrel{above}{base}", "textcolor": "\\textcolor{red}{x}"}
_ONE_ARG = {"sqrt": "\\sqrt{x}", "hat": "\\hat{x}", "bar": "\\bar{x}", "tilde": "\\tilde{x}", "vec": "\\vec{x}",
            "dot": "\\dot{x}", "ddot": "\\ddot{x}", "widehat": "\\widehat{xy}", "widetilde": "\\widetilde{xy}",
            "overline": "\\overline{x}", "underline": "\\underline{x}", "overbrace": "\\overbrace{a+b}^{n}",
            "underbrace": "\\underbrace{a+b}_{n}", "mathbf": "\\mathbf{x}", "mathbb": "\\mathbb{R}",
            "mathcal": "\\mathcal{L}", "mathrm": "\\mathrm{d}", "boldsymbol": "\\boldsymbol{\\theta}",
            "bm": "\\bm{\\theta}", "text": "\\text{words}", "operatorname": "\\operatorname{name}",
            "boxed": "\\boxed{x}", "cancel": "\\cancel{x}", "color": "\\color{red}{x}", "mathit": "\\mathit{x}",
            "mathsf": "\\mathsf{x}", "mathtt": "\\mathtt{x}", "mathfrak": "\\mathfrak{g}", "xrightarrow": "\\xrightarrow{f}"}
_LEFT_DELIMS = set("()[]|./<>") | {"\\{", "\\}", "\\|", "\\langle", "\\rangle", "\\lvert", "\\rvert", "\\lVert",
                                    "\\rVert", "\\vert", "\\Vert", "\\lfloor", "\\rfloor", "\\lceil", "\\rceil",
                                    "\\lbrace", "\\rbrace", "\\lbrack", "\\rbrack", "\\uparrow", "\\downarrow",
                                    "\\updownarrow", "\\Uparrow", "\\Downarrow", "\\backslash", "\\lgroup",
                                    "\\rgroup", "\\llbracket", "\\rrbracket", "\\langle", "\\rangle", "\\|"}


def looks_like_money(tex: str) -> bool:
    """``$5 and $`` in a sentence: inline maths that is really two dollar amounts with words between them."""
    if not re.match(r"\s*\d", tex):
        return False
    words = re.findall(r"(?<![\\A-Za-z])[A-Za-z]{3,}", tex)
    return len(words) >= 2 and "\\" not in tex and "{" not in tex


def diagnose(tex: str, display: bool) -> dict:
    """Find the common mistakes in ``tex`` (comments already removed). Raises :class:`MathError` at the first one.

    Returns facts the pre-processing needs: ``{"top_rows": bool, "top_amp": bool}`` (``\\\\`` / ``&`` outside any
    block, which display maths wraps into one).
    """
    err = MathError.at
    braces: list[tuple[int, str, dict]] = []  # (index, kind, saved script flags); kind: "{", "script" or "text"
    envs: list[tuple[str, int, int]] = []   # (name, index, brace depth)
    lefts: list[tuple[int, int, int]] = []  # (index, brace depth, env depth)
    text_depth: int | None = None           # brace depth at which a \text{…} argument ends
    facts = {"top_rows": False, "top_amp": False}
    script = {"^": False, "_": False}       # scripts already attached to the current atom
    held_script: list[dict] = []            # flags to restore after a script written as a command (x^\prime)
    n = len(tex)
    i = 0

    def atom_done():
        if held_script:
            script.update(held_script.pop())
            return
        script["^"] = script["_"] = False

    while i < n:
        c = tex[i]
        in_text = text_depth is not None
        if c == "\\":
            m = re.match(r"\\([A-Za-z]+\*?|.)", tex[i:], re.S)
            if not m:
                raise err(tex, i, "a backslash ends the formula.", "remove the \\ at the end, or write \\backslash")
            tok, name = m.group(0), m.group(1)
            j = i + len(tok)
            if name.endswith("*") and name[:-1] not in ("operatorname",) and name not in KNOWN:
                name, tok, j = name[:-1], tok[:-1], j - 1
            if in_text:
                if name.isalpha() and name not in _TEXT_CMDS and name not in {"textbf", "textit", "emph", "S", "P",
                                                                              "ldots", "dots", "quad", "qquad"}:
                    raise err(tex, i, f"\\{name} inside \\text{{…}} is shown as written, not as a symbol.",
                              f"close the text first: \\text{{… }} \\{name} \\text{{ …}}", len(tok))
                if name == "\\":
                    raise err(tex, i, "a line break \\\\ inside \\text{…} is shown as written.",
                              "end the \\text{…} before the \\\\", 2)
                i = j
                continue
            if name == "'":
                raise err(tex, i, "\\' is an accent for text, not a prime.", "write f'(x) or f^{\\prime}(x)", 2)
            if name == "\\":
                if not any(e[0] in _ROW_ENVS for e in envs) and not braces_inside_substack(tex, braces):
                    if display and not envs:
                        facts["top_rows"] = True
                    else:
                        raise err(tex, i, "a line break \\\\ only works inside a block of rows.",
                                  "put the rows on their own lines between $$ … $$ and wrap them in "
                                  "\\begin{aligned} … \\end{aligned}" if not display else
                                  "wrap the rows in \\begin{aligned} … \\end{aligned}", 2)
                atom_done()
                i = j
                continue
            if not name.isalpha() and not name.endswith("*"):
                atom_done()
                i = j
                continue
            base = name.rstrip("*")
            if base in UNSUPPORTED and not (display and base in ("label", "tag")):
                what = {"label": "\\label only works in displayed equations.",
                        "tag": "\\tag only works in displayed equations."}.get(
                    base, f"\\{base} cannot be shown in browsers.")
                raise err(tex, i, what, UNSUPPORTED[base], len(tok))
            if base in ("begin", "end"):
                em = re.match(r"\s*\{([^{}]*)\}", tex[j:])
                if not em:
                    raise err(tex, i, f"\\{base} needs the name of a block in braces.",
                              f"write \\{base}{{aligned}}, \\{base}{{pmatrix}} or \\{base}{{cases}}", len(tok))
                env = em.group(1).strip()
                span = len(tok) + em.end()
                if base == "begin":
                    if env not in _ENVS or env in _NO_ENV:
                        close = difflib.get_close_matches(env, sorted(_ENVS - _NO_ENV), n=1, cutoff=0.6)
                        raise err(tex, i, f"the block \\begin{{{env}}} is not available.",
                                  (f"write \\begin{{{close[0]}}} if that is what you meant. " if close else "") +
                                  "Rows: aligned, gather, multline; grids: matrix, pmatrix, bmatrix, vmatrix, "
                                  "array; choices: cases", span)
                    envs.append((env, i, len(braces)))
                else:
                    if not envs:
                        raise err(tex, i, f"\\end{{{env}}} has no \\begin{{{env}}} before it.",
                                  f"add \\begin{{{env}}} where the block starts, or remove this \\end", span)
                    top = envs[-1]
                    if top[0] != env:
                        raise err(tex, i, f"\\end{{{env}}} closes \\begin{{{top[0]}}}.",
                                  f"write \\end{{{top[0]}}} here (blocks close in the reverse order they open)",
                                  span)
                    if len(braces) != top[2]:
                        bi = braces[-1][0]
                        raise err(tex, bi, f"a {{ inside the {env} block is never closed.",
                                  "add the missing } before \\end{" + env + "}")
                    while lefts and lefts[-1][2] > len(envs) - 1:
                        li = lefts[-1][0]
                        raise err(tex, li, "\\left has no matching \\right inside this block.",
                                  "add \\right) (or \\right. for nothing) before \\end{" + env + "}", 5)
                    envs.pop()
                i = j + em.end()
                atom_done()
                continue
            if base == "left":
                d = _delimiter(tex, j)
                if d is None:
                    raise err(tex, i, "\\left needs a bracket after it.",
                              "write \\left( … \\right), \\left[ … \\right] or \\left. … \\right| ", 5)
                lefts.append((i, len(braces), len(envs)))
                i = d
                continue
            if base == "right":
                d = _delimiter(tex, j)
                if d is None:
                    raise err(tex, i, "\\right needs a bracket after it.",
                              "write \\right) or \\right. (a dot means no bracket)", 6)
                if not lefts or lefts[-1][1] != len(braces) or lefts[-1][2] != len(envs):
                    raise err(tex, i, "\\right has no matching \\left before it.",
                              "add \\left( where the bracket opens, or write a plain ) without \\right", 6)
                lefts.pop()
                atom_done()
                i = d
                continue
            if base == "middle":
                if not lefts:
                    raise err(tex, i, "\\middle only works between \\left and \\right.",
                              "write \\left( a \\middle| b \\right), or \\mid on its own", 7)
                d = _delimiter(tex, j)
                i = d if d is not None else j
                continue
            if base in ("color", "textcolor", "colorbox"):
                k = _skip_space(tex, j)
                cm = re.match(r"\{([^{}]*)\}", tex[k:])
                if not cm:
                    raise err(tex, i, f"\\{base} needs a colour in braces.", f"write \\{base}{{red}}{{x}}", len(tok))
                colour = cm.group(1).strip()
                if not _COLOR.match(colour):
                    raise err(tex, k + 1, f"the colour {colour!r} is not one browsers know.",
                              "write a colour name (red, blue, gray …) or a hex value like #e03131", len(cm.group(1)))
                i = k + cm.end()
                if base != "color":
                    a = _arg(tex, i)
                    if a is None:
                        raise err(tex, i - cm.end(), f"\\{base} needs something to colour.",
                                  f"write \\{base}{{{colour}}}{{x}}", len(tok))
                continue
            if base in ("limits", "nolimits"):
                before = tex[:i].rstrip()
                if not before or before[-1] in "{(&=+-":
                    raise err(tex, i, f"\\{base} must follow an operator such as \\sum.",
                              f"write \\sum\\{base}_{{i}}", len(tok))
                i = j
                continue
            if base in _TWO_ARGS or base in _ONE_ARG:
                k = j
                if base == "sqrt":
                    o = _opt_arg(tex, k)
                    if o:
                        k = o[1]
                need = 2 if base in _TWO_ARGS else 1
                for _ in range(need):
                    a = _arg(tex, k)
                    if a is None:
                        example = _TWO_ARGS.get(base) or _ONE_ARG.get(base)
                        if need == 2:
                            raise err(tex, i, f"\\{base} needs two parts in braces.", f"write {example}", len(tok))
                        raise err(tex, i, f"\\{base} needs something to act on.", f"write {example}", len(tok))
                    k = a[1]
                if base in ("text", "operatorname") and _skip_space(tex, j) < n and tex[_skip_space(tex, j)] == "{":
                    # look inside the text argument for maths that will not work
                    a = _arg(tex, j)
                    body = tex[a[0] + 1:a[1] - 1]
                    if base == "text" and re.search(r"(?<!\\)\$", body):
                        k2 = a[0] + 1 + re.search(r"(?<!\\)\$", body).start()
                        raise err(tex, k2, "a $ inside \\text{…} is shown as a dollar sign, not as maths.",
                                  "close the text before the maths: \\text{if } x > 0 \\text{ holds}")
            if name.isalpha() and base not in KNOWN:
                if base in SUGGEST:
                    raise err(tex, i, f"\\{base} is not a LaTeX command.", SUGGEST[base], len(tok))
                close = _did_you_mean(base)
                hint = (f"write \\{close} if that is what you meant; otherwise, " if close else "") + \
                    f"for a named function write \\operatorname{{{base}}}, for words \\text{{{base}}}"
                raise err(tex, i, f"\\{base} is not a known command, so it would show as raw text.",
                          hint, len(tok))
            if base in _TEXT_CMDS - {"operatorname", "operatorname*", "fbox"}:
                k = _skip_space(tex, j)
                if k < n and tex[k] == "{":
                    braces.append((k, "text", dict(script)))
                    text_depth = len(braces)
                    i = k + 1
                    continue
            if base in ("limits", "nolimits"):
                i = j
                continue
            atom_done()
            i = j
            continue
        if c == "{":
            braces.append((i, "{", dict(script)))
            script["^"] = script["_"] = False
            i += 1
            continue
        if c == "}":
            if not braces:
                raise err(tex, i, "this } has no { before it.", "remove it, or add the { where the group starts")
            if text_depth is not None and len(braces) == text_depth:
                text_depth = None
            if lefts and lefts[-1][1] == len(braces):
                raise err(tex, lefts[-1][0], "\\left has no matching \\right before the group closes.",
                          "add \\right) (or \\right. for nothing) before the }", 5)
            if envs and envs[-1][2] == len(braces):
                raise err(tex, envs[-1][1], f"\\begin{{{envs[-1][0]}}} is not closed before this group ends.",
                          f"add \\end{{{envs[-1][0]}}} before the }}", 6)
            _, kind, saved = braces.pop()
            script.update(saved if kind == "script" else {"^": False, "_": False})
            i += 1
            continue
        if in_text:
            if c == "$":
                raise err(tex, i, "a $ inside \\text{…} is shown as a dollar sign, not as maths.",
                          "close the text before the maths: \\text{if } x > 0 \\text{ holds}")
            i += 1
            continue
        if c == "$":
            raise err(tex, i, "a $ sign inside the formula would end it early.",
                      "write \\$ for a dollar sign, or remove the extra $")
        if c == "#":
            raise err(tex, i, "# is a special character in LaTeX.", "write \\# for the symbol")
        if c == "&":
            if not any(e[0] in _ROW_ENVS for e in envs):
                if display and not envs:
                    facts["top_amp"] = True
                else:
                    raise err(tex, i, "& lines up rows, so it only works inside aligned, a matrix or cases.",
                              "wrap the rows in \\begin{aligned} … \\end{aligned}, or write \\& for the symbol")
            atom_done()
            i += 1
            continue
        if c in "^_":
            other = "superscript" if c == "^" else "subscript"
            if script[c]:
                raise err(tex, i, f"two {other}s in a row on the same symbol.",
                          "group them: x^{a^b} or {x^a}^b" if c == "^" else "group them: x_{i_j} or x_{ij}")
            a = _arg(tex, i + 1)
            if a is None:
                raise err(tex, i, f"{c} has nothing after it.",
                          f"write x{c}{{2}}, or remove the {c}" if c == "^" else f"write x{c}{{i}}, or remove the {c}")
            body = tex[a[0]:a[1]]
            if re.fullmatch(r"\d", body) and a[1] < n and tex[a[1]].isdigit():
                m2 = re.match(r"\d+", tex[a[0]:])
                num = m2.group(0)
                raise err(tex, i, f"{c}{num} {'raises' if c == '^' else 'lowers'} only the {num[0]}; "
                          f"the rest stays on the line.", f"write {c}{{{num}}}", 1 + len(num))
            script[c] = True
            if body.startswith("{"):
                braces.append((a[0], "script", dict(script)))
                script["^"] = script["_"] = False
                i = a[0] + 1                   # scan inside the group; its closing brace restores the flags
                continue
            if body.startswith("\\"):
                i = a[0]                       # a command as the script: read it normally (it may take arguments)
                held_script.append(dict(script))
                continue
            i = a[1]
            continue
        if c == "'":
            i += 1
            continue
        if c in " \t\n\r":
            i += 1
            continue
        atom_done()
        i += 1
    if text_depth is not None:
        raise err(tex, braces[text_depth - 1][0], "\\text{ is never closed.", "add } after the words")
    if braces:
        bi = braces[-1][0]
        raise err(tex, bi, "this { is never closed.", "add the matching } where the group ends")
    if envs:
        name, bi, _ = envs[-1]
        raise err(tex, bi, f"\\begin{{{name}}} has no \\end{{{name}}}.", f"add \\end{{{name}}} after the last row",
                  len(name) + 8)
    if lefts:
        raise err(tex, lefts[-1][0], "\\left has no matching \\right.",
                  "add \\right) after the bracketed part (\\right. if it closes with nothing)", 5)
    return facts


def braces_inside_substack(tex: str, braces) -> bool:
    """``\\\\`` inside ``\\substack{…}`` is a row break."""
    for idx, *_ in braces:
        if re.search(r"\\substack\s*$", tex[:idx]):
            return True
    return False


def _delimiter(tex: str, j: int) -> int | None:
    """After \\left / \\right / \\middle: the index after the delimiter, or None when there is none."""
    k = _skip_space(tex, j)
    if k >= len(tex):
        return None
    m = re.match(r"\\[A-Za-z]+|\\[{}|]|[()\[\]|./<>]|[\u27e8\u27e9\u2016\u230a\u230b\u2308\u2309]", tex[k:])
    if not m:
        return None
    tok = m.group(0)
    if tok.startswith("\\") and len(tok) > 2 and tok not in _LEFT_DELIMS:
        return None
    return k + len(tok)


# ------------------------------------------------------------------------------------------------ pre-processing
def _rewrite_environments(tex: str) -> str:
    """aligned/align/gather/split/multline -> array with rl column pairs; equation wrappers dropped."""
    tex = re.sub(r"\\(?:begin|end)\s*\{(?:equation\*?|displaymath|math)\}", "", tex)

    def repl(m: re.Match) -> str:
        env, inner = m.group(1), m.group(3)
        if env.startswith("alignat") or env == "alignedat":
            inner = re.sub(r"^\s*\{[^{}]*\}", "", inner)
        rows = re.split(r"\\\\", inner)
        if env.startswith("gather"):
            cols = "c"
        elif env.startswith("multline"):
            cols = "l"
            inner = "\\\\".join(r if k == 0 or not r.strip() else "\\qquad " + r for k, r in enumerate(rows))
        else:
            n = max((len(re.findall(r"(?<!\\)&", r)) for r in rows), default=0) + 1
            cols = ("rl" * n)[:n]
            if env.startswith("eqnarray"):
                cols = ("rcl" * n)[:n]
        # "&=" would start a cell with a bare relation; "{}" gives it a left operand so it is spaced as in TeX.
        inner = re.sub(r"(?<!\\)&\s*(?=[=<>+\-]|\\(?:le|ge|leq|geq|approx|equiv|sim|simeq|propto|neq|ne|to|in|"
                       r"subset|subseteq|cdot|times|coloneqq|triangleq|ll|gg|Rightarrow|Leftrightarrow|implies|iff|"
                       r"mapsto|leftarrow|rightarrow|cong|pm|mp)\b)", "&{}", inner)
        return f"\\begin{{array}}{{{cols}}}{inner}\\end{{array}}"

    names = "|".join(re.escape(e) for e in _ENV_TO_ARRAY)
    pattern = re.compile(r"\\begin\s*\{(" + names + r")\}(\{[^}]*\})?(.*?)\\end\s*\{\1\}", re.S)
    prev = None
    while prev != tex:
        prev, tex = tex, pattern.sub(repl, tex)
    # pmatrix*[r] and friends: an array with the alignment, inside the brackets
    def starred(m: re.Match) -> str:
        kind, opt, inner = m.group(1), (m.group(2) or "[c]")[1:-1].strip() or "c", m.group(3)
        n = max((len(re.findall(r"(?<!\\)&", r)) for r in re.split(r"\\\\", inner)), default=0) + 1
        fences = {"": ("", ""), "p": ("(", ")"), "b": ("[", "]"), "B": ("\\{", "\\}"), "v": ("|", "|"),
                  "V": ("\\|", "\\|")}[kind]
        arr = f"\\begin{{array}}{{{opt[0] * n}}}{inner}\\end{{array}}"
        return f"\\left{fences[0]}{arr}\\right{fences[1]}" if fences[0] else arr
    tex = re.sub(r"\\begin\s*\{([pbBvV]?)matrix\*\}(\[[^\]]*\])?(.*?)\\end\s*\{\1matrix\*\}", starred, tex,
                 flags=re.S)
    # cases with display-style rows; rcases (brace on the right)
    tex = re.sub(r"\\begin\s*\{dcases\}(.*?)\\end\s*\{dcases\}",       # display-style rows: full-size fractions
                 lambda m: "\\begin{cases}" + re.sub(r"\\[td]?frac(?![A-Za-z])", r"\\dfrac", m.group(1)) + "\\end{cases}",
                 tex, flags=re.S)
    tex = re.sub(r"\\begin\s*\{rcases\}(.*?)\\end\s*\{rcases\}",
                 lambda m: "\\left.\\begin{array}{ll}" + m.group(1) + "\\end{array}\\right\\}", tex, flags=re.S)
    tex = re.sub(r"\\begin\s*\{subarray\}\s*\{[^}]*\}(.*?)\\end\s*\{subarray\}",
                 lambda m: "\\substack{" + m.group(1) + "}", tex, flags=re.S)
    return tex


def _clean_operator_names(tex: str, starred: set) -> str:
    def repl(m: re.Match) -> str:
        star, name = m.group(1), m.group(2)
        clean = re.sub(r"\\[,;:! ]|\\quad|\\qquad|\\mathrm|\s+|[{}]", "", name)
        if star:
            starred.add(clean)
        return f"\\operatorname{{{clean}}}"

    return re.sub(r"\\operatorname(\*?)\s*\{((?:[^{}]|\{[^{}]*\})*)\}", repl, tex)


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
        if italic and m.group(2) is not None and re.fullmatch(r"[A-Za-z]+", arg):
            return f"\\mathbfit{{{arg}}}"
        return f"\\mathbf{{{new}}}"

    return re.sub(r"\\(mathbf|boldsymbol|bm|symbf|pmb)(?![A-Za-z])\s*(?:\{([^{}]*)\}|(\\[A-Za-z]+))", group, tex)


_DELIM_CHARS = {"\\langle": "\u27e8", "\\rangle": "\u27e9", "\\lVert": "\u2016", "\\rVert": "\u2016",
                "\\Vert": "\u2016", "\\|": "\u2016", "\\lvert": "|", "\\rvert": "|", "\\vert": "|",
                "\\lfloor": "\u230a", "\\rfloor": "\u230b", "\\lceil": "\u2308", "\\rceil": "\u2309",
                "\\lbrace": "\\{", "\\rbrace": "\\}"}

_ARROWS = {"xrightarrow": "\\rightarrow", "xleftarrow": "\\leftarrow", "xRightarrow": "\\Rightarrow",
           "xLeftarrow": "\\Leftarrow", "xleftrightarrow": "\\leftrightarrow", "xLeftrightarrow": "\\Leftrightarrow",
           "xmapsto": "\\mapsto", "xlongequal": "=", "xhookrightarrow": "\\hookrightarrow",
           "xhookleftarrow": "\\hookleftarrow", "xtwoheadrightarrow": "\\twoheadrightarrow",
           "xtwoheadleftarrow": "\\twoheadleftarrow"}


def _rewrite_commands(tex: str) -> str:
    """Commands with arguments that need rewriting: extensible arrows, \\choose, wrappers to unwrap."""
    out, i, n = [], 0, len(tex)
    while i < n:
        m = re.match(r"\\([A-Za-z]+)", tex[i:]) if tex[i] == "\\" else None
        if not m:
            if tex[i] == "\\" and i + 1 < n:
                out.append(tex[i:i + 2])
                i += 2
                continue
            out.append(tex[i])
            i += 1
            continue
        name, j = m.group(1), i + len(m.group(0))
        if name in _ARROWS:
            below = _opt_arg(tex, j)
            k = below[1] if below else j
            above = _arg(tex, k)
            top = _rewrite_commands(_inner(tex, above)) if above else ""
            end = above[1] if above else k
            arrow = f"\\overset{{\\;{top}\\;}}{{{_ARROWS[name]}}}" if top.strip() else _ARROWS[name]
            if below:
                low = _rewrite_commands(tex[below[0] + 1:below[1] - 1])
                arrow = f"\\underset{{\\;{low}\\;}}{{{arrow}}}"
            out.append(arrow)
            i = end
            continue
        if name in ("ensuremath", "mathclap", "mathrlap", "mathllap", "clap", "rlap", "llap"):
            a = _arg(tex, j)
            if a:
                out.append("{" + _rewrite_commands(_inner(tex, a)) + "}")
                i = a[1]
                continue
        if name in ("mathds", "mathbbm"):
            out.append("\\mathbb")
            i = j
            continue
        if name == "color":
            cm = re.match(r"\s*\{[^{}]*\}\s*(?=\{)", tex[j:])
            if cm:                                   # \color{red}{x}: colour only x (as MathJax does)
                out.append("\\textcolor")
                i = j
                continue
        if name == "mbox":
            out.append("\\text")
            i = j
            continue
        if name == "cfrac":
            out.append("\\dfrac")
            i = j
            continue
        if name in ("symit",):
            out.append("\\mathit")
            i = j
            continue
        if name in ("symcal",):
            out.append("\\mathcal")
            i = j
            continue
        if name in ("symbb",):
            out.append("\\mathbb")
            i = j
            continue
        if name in ("symrm",):
            out.append("\\mathrm")
            i = j
            continue
        if name in ("symsf",):
            out.append("\\mathsf")
            i = j
            continue
        if name in ("symtt",):
            out.append("\\mathtt")
            i = j
            continue
        if name in ("intercal",):
            out.append("\\top ")
            i = j
            continue
        out.append(m.group(0))
        i = j
    tex = "".join(out)
    # {n \choose k} -> \binom{n}{k}
    prev = None
    while prev != tex:
        prev = tex
        m = re.search(r"\\choose(?![A-Za-z])", tex)
        if not m:
            break
        depth, start = 0, -1
        for k in range(m.start() - 1, -1, -1):
            if tex[k] == "}" and (k == 0 or tex[k - 1] != "\\"):
                depth += 1
            elif tex[k] == "{" and (k == 0 or tex[k - 1] != "\\"):
                if depth == 0:
                    start = k
                    break
                depth -= 1
        if start < 0:
            break
        end = _group_end(tex, start)
        top, bottom = tex[start + 1:m.start()], tex[m.end():end - 1]
        tex = tex[:start] + f"\\binom{{{top}}}{{{bottom}}}" + tex[end:]
    return tex


def _wrap_top_rows(tex: str, facts: dict) -> str:
    """Display maths with ``\\\\`` (or ``&``) outside any block: wrap the whole formula in one, as authors mean."""
    if facts.get("top_rows") or facts.get("top_amp"):
        env = "aligned" if facts.get("top_amp") else "gathered"
        return f"\\begin{{{env}}}{tex}\\end{{{env}}}"
    return tex


def preprocess(tex: str, display: bool = True, facts: dict | None = None) -> tuple[str, set]:
    """Apply every LaTeX rewrite. Returns the new LaTeX and the operator names that take limits underneath."""
    starred: set = set()
    tex = strip_comments(tex)
    tex = tex.replace("\u00a0", " ").replace("\u200b", "").replace("\u2009", " ")
    tex = re.sub(r"\\(?:nonumber|notag)(?![A-Za-z])", "", tex)
    if display and facts:
        tex = _wrap_top_rows(tex, facts)
    tex = _rewrite_environments(tex)
    tex = re.sub(r"\\\\\s*\[[^\]]*\]", r"\\\\", tex)                         # \\[4pt] -> \\
    tex = _rewrite_commands(tex)
    tex = re.sub(r"\\argmax(?![A-Za-z])", r"\\operatorname*{argmax}", tex)
    tex = re.sub(r"\\argmin(?![A-Za-z])", r"\\operatorname*{argmin}", tex)
    tex = re.sub(r"\\arg(?![A-Za-z])", r"\\operatorname{arg}", tex)
    tex = re.sub(r"\\operatornamewithlimits(?![A-Za-z])", r"\\operatorname*", tex)
    tex = _clean_operator_names(tex, starred)
    tex = _bold_greek(tex)
    tex = re.sub(r"\\(?:boldsymbol|bm|symbf|pmb)(?![A-Za-z])", r"\\mathbf", tex)
    # \big( … \big): keep the size, but give the converter plain characters for the delimiters
    tex = re.sub(r"(\\(?:big|Big|bigg|Bigg)[lrm]?)(?![A-Za-z])\s*(\\[A-Za-z]+|\\[{}|])",
                 lambda m: m.group(1) + (_DELIM_CHARS.get(m.group(2), m.group(2))), tex)
    tex = re.sub(r"\\not\s*=", r"\\neq ", tex)
    tex = re.sub(r"\\not\s*\\in(?![A-Za-z])", r"\\notin ", tex)
    tex = re.sub(r"\\mathrm\s*\{\s*([A-Za-z])\s*\}", r"\\text{\1}", tex)
    tex = re.sub(r"\\mathrm\s+([A-Za-z])(?![A-Za-z])", r"\\text{\1}", tex)
    tex = re.sub(r"\\(lvert|lVert)(?![A-Za-z])", lambda m: "\\" + m.group(1) + " ", tex)
    return tex, starred


# ----------------------------------------------------------------------------------------------- post-processing
def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _q(tag: str) -> str:
    return f"{{{MATHML_NS}}}{tag}"


def _variant_char(c: str, variant: str) -> str:
    """One character in a mathvariant, as the Unicode Mathematical Alphanumeric Symbol."""
    try:
        name = unicodedata.name(c)
    except ValueError:
        return c
    prefix = {
        "bold": "MATHEMATICAL BOLD", "italic": "MATHEMATICAL ITALIC", "bold-italic": "MATHEMATICAL BOLD ITALIC",
        "double-struck": "MATHEMATICAL DOUBLE-STRUCK", "script": "MATHEMATICAL SCRIPT",
        "bold-script": "MATHEMATICAL BOLD SCRIPT", "fraktur": "MATHEMATICAL FRAKTUR",
        "bold-fraktur": "MATHEMATICAL BOLD FRAKTUR", "sans-serif": "MATHEMATICAL SANS-SERIF",
        "bold-sans-serif": "MATHEMATICAL SANS-SERIF BOLD", "sans-serif-italic": "MATHEMATICAL SANS-SERIF ITALIC",
        "sans-serif-bold-italic": "MATHEMATICAL SANS-SERIF BOLD ITALIC", "monospace": "MATHEMATICAL MONOSPACE",
    }.get(variant)
    if not prefix:
        return c
    m = re.fullmatch(r"LATIN (CAPITAL|SMALL) LETTER ([A-Z])", name)
    if m:
        target = f"{prefix} {m.group(1)} {m.group(2)}"
    else:
        m = re.fullmatch(r"DIGIT (\w+)", name)
        if m:
            target = f"{prefix} DIGIT {m.group(1)}"
        else:
            m = re.fullmatch(r"GREEK (CAPITAL|SMALL) LETTER (\w+)", name)
            if not m:
                return c
            target = f"{prefix} {m.group(1)} {m.group(2)}"
    # letters that live in the Letterlike Symbols block (ℝ, ℒ, ℎ …) have other names
    holes = {"MATHEMATICAL ITALIC SMALL H": "\u210e", "MATHEMATICAL SCRIPT CAPITAL B": "\u212c",
             "MATHEMATICAL SCRIPT CAPITAL E": "\u2130", "MATHEMATICAL SCRIPT CAPITAL F": "\u2131",
             "MATHEMATICAL SCRIPT CAPITAL H": "\u210b", "MATHEMATICAL SCRIPT CAPITAL I": "\u2110",
             "MATHEMATICAL SCRIPT CAPITAL L": "\u2112", "MATHEMATICAL SCRIPT CAPITAL M": "\u2133",
             "MATHEMATICAL SCRIPT CAPITAL R": "\u211b", "MATHEMATICAL SCRIPT SMALL E": "\u212f",
             "MATHEMATICAL SCRIPT SMALL G": "\u210a", "MATHEMATICAL SCRIPT SMALL O": "\u2134",
             "MATHEMATICAL FRAKTUR CAPITAL C": "\u212d", "MATHEMATICAL FRAKTUR CAPITAL H": "\u210c",
             "MATHEMATICAL FRAKTUR CAPITAL I": "\u2111", "MATHEMATICAL FRAKTUR CAPITAL R": "\u211c",
             "MATHEMATICAL FRAKTUR CAPITAL Z": "\u2128", "MATHEMATICAL DOUBLE-STRUCK CAPITAL C": "\u2102",
             "MATHEMATICAL DOUBLE-STRUCK CAPITAL H": "\u210d", "MATHEMATICAL DOUBLE-STRUCK CAPITAL N": "\u2115",
             "MATHEMATICAL DOUBLE-STRUCK CAPITAL P": "\u2119", "MATHEMATICAL DOUBLE-STRUCK CAPITAL Q": "\u211a",
             "MATHEMATICAL DOUBLE-STRUCK CAPITAL R": "\u211d", "MATHEMATICAL DOUBLE-STRUCK CAPITAL Z": "\u2124"}
    if target in holes:
        return holes[target]
    try:
        return unicodedata.lookup(target)
    except KeyError:
        return c


def _to_unicode_bold(text: str) -> str:
    return "".join(_BOLD_DIGIT.get(c) or _BOLD_UPPER.get(c) or _BOLD_LOWER.get(c) or c for c in text)


_TEXT_VARIANT_CSS = {"bold": "font-weight:bold", "italic": "font-style:italic",
                     "bold-italic": "font-weight:bold;font-style:italic", "monospace": "font-family:monospace",
                     "sans-serif": "font-family:sans-serif", "bold-sans-serif": "font-family:sans-serif;font-weight:bold"}
_NAMED_SPACE = {"veryverythinmathspace": "0.0556em", "verythinmathspace": "0.1111em", "thinmathspace": "0.1667em",
                "mediummathspace": "0.2222em", "thickmathspace": "0.2778em", "verythickmathspace": "0.3333em",
                "veryverythickmathspace": "0.3889em", "negativethinmathspace": "-0.1667em",
                "negativemediummathspace": "-0.2222em", "negativethickmathspace": "-0.2778em"}
_LENGTH = re.compile(r"^-?(?:\d+\.?\d*|\.\d+)(?:em|ex|px|pt|in|cm|mm|pc|%)?$")


def _length(value: str) -> str | None:
    """A MathML length as CSS: named spaces and mu become em; relative (+1em) or pseudo-unit values become None."""
    v = (value or "").strip()
    if v in _NAMED_SPACE:
        return _NAMED_SPACE[v]
    m = re.fullmatch(r"(-?(?:\d+\.?\d*|\.\d+))mu", v)
    if m:
        return f"{float(m.group(1)) / 18:.4g}em"
    if v == "0":
        return "0"
    return v if _LENGTH.match(v) else None


def _add_style(el: ET.Element, css: str) -> None:
    old = el.get("style", "").rstrip(";")
    el.set("style", (old + ";" + css).lstrip(";") if old else css)


_COLOR = re.compile(r"^(?:#[0-9A-Fa-f]{3,8}|[A-Za-z]{3,20}|rgba?\([\d\s.,%]+\))$")


def _fix_tokens(root: ET.Element) -> None:
    for el in root.iter():
        tag = _local(el.tag)
        variant = el.get("mathvariant")
        if variant is not None:
            if tag in ("mi", "mn", "mo") and variant != "normal":
                el.text = "".join(_variant_char(c, variant) for c in (el.text or ""))
                del el.attrib["mathvariant"]
            elif tag == "mtext":
                css = _TEXT_VARIANT_CSS.get(variant)
                if css:
                    _add_style(el, css)
                del el.attrib["mathvariant"]
            elif tag == "mi" and variant == "normal" and len(el.text or "") != 1:
                del el.attrib["mathvariant"]
            elif tag not in ("mi",):
                del el.attrib["mathvariant"]
        for attr, css in (("mathcolor", "color"), ("mathbackground", "background")):
            v = el.get(attr)
            if v is not None:
                del el.attrib[attr]
                if not _COLOR.match(v.strip()):
                    raise MathError(f"the colour {v!r} is not one browsers know.",
                                    "write a colour name (red, blue, gray …) or a hex value like #e03131")
                _add_style(el, f"{css}:{v.strip()}")
        size = el.get("mathsize")
        if size is not None:
            del el.attrib["mathsize"]
            css = _length(size) or {"small": "0.85em", "big": "1.2em", "normal": "1em"}.get(size)
            if css:
                _add_style(el, f"font-size:{css}")
        if tag == "mspace":
            for attr in ("width", "height", "depth"):
                if el.get(attr) is not None:
                    v = _length(el.get(attr))
                    if v is None:
                        del el.attrib[attr]
                    else:
                        el.set(attr, v)
            if "linebreak" in el.attrib:
                pass                                                   # validation explains it
        if tag == "mpadded":
            for attr in ("width", "height", "depth", "lspace", "voffset"):
                if el.get(attr) is not None:
                    v = _length(el.get(attr))
                    if v is None:
                        del el.attrib[attr]
                    else:
                        el.set(attr, v)
        if tag == "mo":
            for attr in ("lspace", "rspace", "minsize", "maxsize"):
                if el.get(attr) is not None:
                    v = _length(el.get(attr))
                    if v is None:
                        del el.attrib[attr]
                    else:
                        el.set(attr, v)
            if "accent" in el.attrib:
                del el.attrib["accent"]
            leaked = {"\\{": "{", "\\}": "}", "\\|": "\u2016", "\u00b7": "\u22c5"}
            if (el.text or "") in leaked:
                el.text = leaked[el.text]
        if tag == "mtext" and el.text:
            el.text = re.sub(r"^ | $", "\u00a0", el.text)


def _classify_symbols(root: ET.Element) -> None:
    """Relations, arrows and brackets the converter left as identifiers become operators; ordinary symbols (∞, ∂ …)
    it made operators become identifiers. Bars get TeX's spacing (none) unless they stretch."""
    for el in root.iter():
        tag, text = _local(el.tag), (el.text or "")
        if len(el):
            continue
        if tag == "mi" and len(text) == 1:
            c = text
            if c == "~":
                el.tag, el.text = _q("mo"), "\u223c"
            elif c == ":":
                el.tag = _q("mo")
                el.set("lspace", "0")
                el.set("rspace", "0.1667em")
            elif c == "\u00b7":
                el.tag, el.text = _q("mo"), "\u22c5"
            elif c in _OPERATOR_LIKE or c in _BAR_CHARS or (
                    c not in _ORDINARY and (unicodedata.category(c) == "Sm" or 0x2190 <= ord(c) <= 0x21FF
                                            or 0x27F0 <= ord(c) <= 0x27FF or 0x2900 <= ord(c) <= 0x297F)):
                el.tag = _q("mo")
        elif tag == "mo" and len(text) == 1 and text in _ORDINARY and text not in _ORD_OPS_KEEP:
            el.tag = _q("mi")
            for a in ("stretchy", "fence", "form", "lspace", "rspace"):
                el.attrib.pop(a, None)
        if _local(el.tag) == "mo" and text in ("|", "\u2016") and el.get("stretchy") != "true" \
                and el.get("minsize") is None:
            el.set("lspace", "0")
            el.set("rspace", "0")


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


def _merge_italic_runs(root: ET.Element) -> None:
    r"""Runs of single-letter identifiers inside ``\mathit{…}`` are already Unicode italic; join them into one word."""
    for parent in root.iter():
        children = list(parent)
        i = 0
        while i < len(children):
            run = []
            while i + len(run) < len(children):
                c = children[i + len(run)]
                t = c.text or ""
                if _local(c.tag) == "mi" and len(t) == 1 and 0x1D434 <= ord(t) <= 0x1D467 or t == "\u210e" \
                        and _local(c.tag) == "mi":
                    run.append(c)
                else:
                    break
            if len(run) > 1:
                run[0].text = "".join(c.text or "" for c in run)
                for extra in run[1:]:
                    parent.remove(extra)
                children = list(parent)
            i += 1


def _limits_underneath(root: ET.Element, starred: set) -> None:
    """Big operators (∑ ∏ ⋃ …) and \\lim/\\max names put their limits under and over them; ``movablelimits`` moves
    them beside the operator wherever TeX would (inline maths, fractions, scripts)."""
    names = _LIMIT_NAMES | starred
    swap = {"msub": "munder", "msup": "mover", "msubsup": "munderover"}
    for el in root.iter():
        tag = _local(el.tag)
        if tag in swap and len(el) and _local(el[0].tag) == "mo":
            text = re.sub(r"\s+", "", el[0].text or "")
            if text in names or text in _BIG_OPS:
                el.tag = el.tag[: -len(tag)] + swap[tag]
                el[0].set("movablelimits", "true")


_FENCES = set("([{|\u2016\u27e8\u2308\u230a)]}\u27e9\u2309\u230b")
_FUNCTIONS = {"log", "ln", "lg", "exp", "sin", "cos", "tan", "sec", "csc", "cot", "sinh", "cosh", "tanh", "coth",
              "arcsin", "arccos", "arctan", "dim", "ker", "deg", "hom", "Pr", "det", "gcd", "max", "min", "sup",
              "inf", "lim", "liminf", "limsup", "arg", "mod"}
_CLOSERS = set(")]}\u27e9\u2309\u230b|\u2016")
_SCRIPTED = {"msub", "msup", "msubsup", "munder", "mover", "munderover"}


def _tables(root: ET.Element, display: bool) -> None:
    """Tables as MathML Core draws them: alignment, rules and spacing as CSS on the cells.

    Aligned rows (r l r l … columns) sit flush around their ``&``, a little apart between pairs, in display style;
    matrices get TeX's column gap; cases put a quad before their conditions; ``\\hline`` and ``c|c`` become borders.
    """
    parents = {c: p for p in root.iter() for c in p}
    for table in [e for e in root.iter() if _local(e.tag) == "mtable"]:
        rows = [r for r in table if _local(r.tag) == "mtr"]
        rowlines = (table.attrib.pop("rowlines", "") or "").split()
        collines = (table.attrib.pop("columnlines", "") or "").split()
        frame = table.attrib.pop("frame", None)
        for a in ("rowspacing", "columnspacing", "columnalign", "rowalign", "align", "equalrows", "equalcolumns",
                  "columnwidth", "width", "framespacing"):
            table.attrib.pop(a, None)
        parent = parents.get(table)
        sibs = list(parent) if parent is not None else []
        k = sibs.index(table) if parent is not None else -1
        prev = sibs[k - 1] if k > 0 else None
        nxt = sibs[k + 1] if 0 <= k < len(sibs) - 1 else None
        fenced = any(n is not None and _local(n.tag) == "mo" and (n.text or "").strip() in _FENCES for n in (prev, nxt))
        cases = prev is not None and _local(prev.tag) == "mo" and (prev.text or "").strip() == "{" and \
            (nxt is None or (_local(nxt.tag) == "mo" and not (nxt.text or "").strip()))
        aligns = []
        for r in rows:
            aligns.append([c.get("columnalign") for c in r if _local(c.tag) == "mtd"])
        pattern = max(aligns, key=len) if aligns else []
        aligned = len(pattern) >= 2 and all(a == ("right" if j % 2 == 0 else "left") for j, a in enumerate(pattern))
        small = parent is not None and _local(parent.tag) == "mstyle" and parent.get("scriptlevel") == "1"
        single = len(pattern) == 1 and pattern[0] in ("center", "left")
        if display and not fenced and not small and (aligned or single):
            table.set("displaystyle", "true")
        if fenced:                                    # matrix brackets grow with the matrix
            for n in (prev, nxt):
                if n is not None and _local(n.tag) == "mo" and (n.text or "").strip() in _FENCES:
                    n.set("stretchy", "true")
                    n.set("lspace", "0")
                    n.set("rspace", "0")
        for ri, r in enumerate(rows):
            r.attrib.pop("columnalign", None)
            r.attrib.pop("rowalign", None)
            cells = [c for c in r if _local(c.tag) == "mtd"]
            for ci, cell in enumerate(cells):
                css = []
                align = cell.attrib.pop("columnalign", None)
                cell.attrib.pop("rowalign", None)
                if align in ("left", "right"):
                    # Chromium only aligns table cells with the prefixed keyword; others take the plain one.
                    css.append(f"text-align:{align};text-align:-webkit-{align}")
                if aligned:
                    left = "0" if ci % 2 == 1 else ("0" if ci == 0 else "1em")
                    css.append(f"padding-left:{left};padding-right:0")
                elif cases:
                    css.append("padding-left:1em" if ci > 0 else "padding-left:0")
                elif not small:
                    edge_l = "0.2em" if fenced else "0"
                    css.append(f"padding-left:{edge_l if ci == 0 else '0.5em'};"
                               f"padding-right:{edge_l if ci == len(cells) - 1 else '0.5em'}")
                if ri < len(rowlines) and rowlines[ri] in ("solid", "dashed"):
                    css.append(f"border-bottom:0.06em {rowlines[ri]} currentColor")
                if ci < len(collines) and collines[ci] in ("solid", "dashed") and ci < len(cells) - 1:
                    css.append(f"border-right:0.06em {collines[ci]} currentColor")
                if css:
                    _add_style(cell, ";".join(css))
        if frame in ("solid", "dashed"):
            _add_style(table, f"border:0.06em {frame} currentColor")
        # rules above the first row: \hline before any row (latex2mathml puts it in rowlines' first slot only
        # between rows, so nothing to do)


def _enclosures(root: ET.Element) -> None:
    """\\boxed and \\cancel (menclose, which browsers do not draw) as CSS on an mrow."""
    for el in root.iter():
        if _local(el.tag) != "menclose":
            continue
        notation = set((el.get("notation") or "box").split())
        el.tag = _q("mrow")
        el.attrib.pop("notation", None)
        css = []
        if "box" in notation:
            css.append("border:0.067em solid currentColor;padding:0.2em 0.3em")
        lines = []
        if "updiagonalstrike" in notation:
            lines.append("linear-gradient(to top right,transparent calc(50% - 0.04em),currentColor calc(50% - 0.04em),"
                         "currentColor calc(50% + 0.04em),transparent calc(50% + 0.04em))")
        if "downdiagonalstrike" in notation:
            lines.append("linear-gradient(to bottom right,transparent calc(50% - 0.04em),currentColor "
                         "calc(50% - 0.04em),currentColor calc(50% + 0.04em),transparent calc(50% + 0.04em))")
        if "horizontalstrike" in notation:
            lines.append("linear-gradient(transparent calc(50% - 0.04em),currentColor calc(50% - 0.04em),"
                         "currentColor calc(50% + 0.04em),transparent calc(50% + 0.04em))")
        if lines:
            css.append("background:" + ",".join(lines))
            css.append("padding:0 0.1em")
        _add_style(el, ";".join(css))


def _accents(root: ET.Element) -> None:
    """Accents in the forms both Chromium and WebKit draw well (checked in both):

    ``\\hat``/``\\tilde`` are fixed-size spacing accents; ``\\widehat`` is U+0302, the one hat Chromium stretches;
    ``\\bar`` on one letter is U+02C9; ``\\overline``/``\\underline`` (and ``\\bar`` over several letters) are a CSS
    rule, since neither browser places a stretched bar reliably; braces stretch; arrows over labels stretch where the
    browser can and are long arrows where it cannot.
    """
    for el in list(root.iter()):
        tag = _local(el.tag)
        if tag in ("mover", "munder", "munderover") and len(el) >= 2 and _local(el[0].tag) == "mrow" \
                and len(el[0]) == 1 and _local(el[0][0].tag) == "mo" and not (el[0][0].text or "").isalpha():
            inner = el[0][0]                                            # \overset{f}{\rightarrow}: the arrow itself
            el.remove(el[0])
            el.insert(0, inner)
            if (inner.text or "") in "\u2192\u2190\u21d2\u21d0\u2194\u21d4\u21a6\u21aa\u21a9\u27f6\u27f5\u27f9\u27f8=":
                long = {"\u2192": "\u27f6", "\u2190": "\u27f5", "\u21d2": "\u27f9", "\u21d0": "\u27f8",
                        "\u2194": "\u27f7", "\u21d4": "\u27fa", "\u21a6": "\u27fc"}
                inner.text = long.get(inner.text, inner.text)
                inner.set("stretchy", "true")
        if tag not in ("mover", "munder") or len(el) != 2 or _local(el[1].tag) != "mo":
            continue
        mo = el[1]
        mark = mo.text or ""
        letters = "".join(el[0].itertext())
        if mark == "\u2015" or (mark == "\u00af" and len(letters) > 1):
            el.remove(mo)
            el.tag = _q("mrow")
            el.attrib.clear()
            side = "top" if tag == "mover" else "bottom"
            _add_style(el, f"border-{side}:0.06em solid currentColor;padding-{side}:0.08em")
            continue
        if mark == "^":
            if el.get("accent") == "true":
                mo.text = "\u02c6"
                mo.set("stretchy", "false")
            else:
                mo.text = "\u0302"
                mo.set("stretchy", "true")
        elif mark == "~":
            if mo.get("stretchy") == "false":
                mo.text = "\u02dc"
            else:
                mo.set("stretchy", "true")
        elif mark == "\u00af":
            mo.text = "\u02c9"
            mo.set("stretchy", "false")
        elif mark in ("\u02d9", "\u00a8", "\u02c7", "\u02d8", "\u00b4", "`", "\u02da", "\u20db"):
            mo.set("stretchy", "false")                                  # fixed accents stay their own size
        elif mark in ("\u23de", "\u23df", "\u23b4", "\u23b5", "\u23dc", "\u23dd"):
            mo.set("stretchy", "true")
        elif mark == "\u2192" and mo.get("stretchy") == "true" and len(letters) <= 1:
            mo.set("stretchy", "false")                                  # \vec{v}: a small arrow, as in print
            mo.set("style", "font-size:0.8em")
        mo.attrib.pop("accent", None)
        if tag == "mover" and mark in ("^", "\u02c6", "~", "\u02dc", "\u00af", "\u02d9", "\u00a8", "\u02c7",
                                       "\u02d8", "\u00b4", "`", "\u02da", "\u20db", "\u2192", "\u2190", "\u2194"):
            el.set("accent", "true")


def _operator_spacing(root: ET.Element) -> None:
    """Named operators (softmax, log, max …) are upright words with TeX's spacing: a thin space before them unless an
    operator precedes, and none after them when a bracket follows."""
    parents = {c: p for p in root.iter() for c in p}
    for el in list(root.iter()):
        tag, text = _local(el.tag), re.sub(r"\s+", "", el.text or "")
        if tag not in ("mi", "mo") or len(text) < 2 or not text.isalpha() or len(el):
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
        closes = prev is not None and _local(prev.tag) == "mo" and (prev.text or "").strip() in _CLOSERS
        el.set("lspace", "0" if prev is None or (_local(prev.tag) == "mo" and not closes) else "0.1667em")
        opens = nxt is not None and ((_local(nxt.tag) == "mo" and (nxt.text or "").strip() in _FENCES) or
                                     (_local(nxt.tag) == "mrow" and len(nxt) and _local(nxt[0].tag) == "mo"
                                      and (nxt[0].text or "").strip() in _FENCES))
        el.set("rspace", "0" if opens or nxt is None or _local(nxt.tag) == "mo" else "0.1667em")


def _unary_signs(root: ET.Element) -> None:
    """A sign right after a relation, an operator or an opening bracket is unary (``= -\\sum``), so it gets no space."""
    for parent in root.iter():
        kids = list(parent)
        for i, el in enumerate(kids):
            if i == 0 or _local(el.tag) != "mo" or (el.text or "") not in ("+", "\u2212", "-", "\u00b1", "\u2213"):
                continue
            prev = kids[i - 1]
            if _local(prev.tag) == "mo" and (prev.text or "").strip() not in _CLOSERS and prev.get("form") != "postfix":
                el.set("form", "prefix")
                el.set("lspace", "0")
                el.set("rspace", "0")


def _primes(root: ET.Element) -> None:
    """``f'`` is a prime beside the letter, at full size: the prime glyph is already raised, so a superscript would
    lift it twice."""
    for el in root.iter():
        if _local(el.tag) == "msup" and len(el) == 2 and _local(el[1].tag) in ("mi", "mo") \
                and (el[1].text or "") and set(el[1].text) <= set("\u2032\u2033\u2034\u2057"):
            el.tag = _q("mrow")
            el[1].tag = _q("mi")


def _script_spacing(root: ET.Element) -> None:
    """Inside sub- and superscripts TeX puts no space around relations and binary operators (x_{<t}, i=1)."""
    for el in root.iter():
        tag = _local(el.tag)
        if tag not in _SCRIPTED or len(el) < 2 or el.get("accent") == "true":
            continue
        for script in list(el)[1:]:
            for mo in script.iter():
                if _local(mo.tag) == "mo" and mo.get("lspace") is None and mo.get("rspace") is None \
                        and mo.get("stretchy") != "true" and len((mo.text or "").strip()) == 1:
                    mo.set("lspace", "0")
                    mo.set("rspace", "0")


def _serialise(root: ET.Element) -> str:
    ET.register_namespace("", MATHML_NS)
    out = ET.tostring(root, encoding="unicode", short_empty_elements=False)
    return out.replace(f' xmlns:ns0="{MATHML_NS}"', "").replace("ns0:", "")


def postprocess(mathml: str, display: bool, starred: set, tex: str) -> str:
    root = ET.fromstring(mathml)
    _enclosures(root)
    _accents(root)
    _fix_tokens(root)
    _merge_italic_runs(root)
    _primes(root)
    _classify_symbols(root)
    _unary_signs(root)
    _merge_upright_runs(root)
    _operator_spacing(root)
    _limits_underneath(root, starred)
    _tables(root, display)
    _script_spacing(root)
    # Keep the source as an annotation: copy-paste, screen readers and search all see the LaTeX.
    body = list(root)
    root.clear()
    root.set("display", "block" if display else "inline")
    semantics = ET.SubElement(root, _q("semantics"))
    row = ET.SubElement(semantics, _q("mrow"))
    row.extend(body)
    ann = ET.SubElement(semantics, _q("annotation"), {"encoding": "application/x-tex"})
    ann.text = re.sub(r"[ \t]+\n", "\n", tex.strip())
    return _serialise(root)


# ------------------------------------------------------------------------------------------------------ validation
# MathML Core: the elements and the attributes browsers implement (https://www.w3.org/TR/mathml-core/).
CORE_ELEMENTS = {"math", "semantics", "annotation", "annotation-xml", "mrow", "mi", "mn", "mo", "mtext", "ms",
                 "mspace", "msub", "msup", "msubsup", "munder", "mover", "munderover", "mmultiscripts", "mprescripts",
                 "none", "mfrac", "msqrt", "mroot", "mtable", "mtr", "mtd", "mstyle", "mpadded", "mphantom",
                 "merror"}
_GLOBAL = {"style", "class", "id", "dir", "displaystyle", "scriptlevel", "mathcolor", "mathbackground", "mathsize",
           "tabindex"}
CORE_ATTRIBUTES = {
    "math": {"display", "alttext", "xmlns"}, "annotation": {"encoding"}, "mi": {"mathvariant"},
    "mo": {"form", "fence", "separator", "lspace", "rspace", "stretchy", "symmetric", "maxsize", "minsize", "largeop",
           "movablelimits"},
    "mspace": {"width", "height", "depth"}, "mpadded": {"width", "height", "depth", "lspace", "voffset"},
    "mfrac": {"linethickness"}, "munder": {"accentunder"}, "mover": {"accent"},
    "munderover": {"accent", "accentunder"}, "mtd": {"columnspan", "rowspan"},
}
_LEAK = re.compile(r"<(m[a-z]+)[^>]*>\s*(\\[A-Za-z]+|\\[^A-Za-z\s])")


def validate(mathml: str, tex: str) -> None:
    """Reject output that browsers would show wrongly. The LaTeX is used to find where the problem is."""
    body = mathml.split("<annotation", 1)[0]
    m = _LEAK.search(body)
    if m:
        cmd = m.group(2)
        idx = tex.find(cmd)
        name = cmd[1:]
        hint = SUGGEST.get(name) or _hint_for_unknown(cmd)
        raise MathError.at(tex, idx if idx >= 0 else 0,
                           f"{cmd} is not a known command, so it would show as raw text.", hint,
                           len(cmd))
    if "linebreak=" in body:
        idx = tex.find("\\\\")
        raise MathError.at(tex, max(idx, 0), "a line break \\\\ only works inside a block of rows.",
                           "wrap the rows in \\begin{aligned} … \\end{aligned}", 2)
    if re.search(r"<munderover>\s*</munderover>", body):
        idx = tex.find("\\limits")
        raise MathError.at(tex, max(idx, 0), "\\limits must follow an operator such as \\sum.",
                           "write \\sum\\limits_{i}", 7)
    root = ET.fromstring(mathml)
    for el in root.iter():
        tag = _local(el.tag)
        if tag not in CORE_ELEMENTS:
            raise MathError(f"this formula needs <{tag}>, which browsers do not draw.",
                            "simplify the formula, or put that part in the surrounding text")
        allowed = _GLOBAL | CORE_ATTRIBUTES.get(tag, set())
        for attr in el.attrib:
            if attr not in allowed and not attr.startswith("data-"):
                raise MathError(f"this formula sets {attr} on <{tag}>, which browsers ignore.",
                                "simplify the formula; if it still fails, write it another way")
        if tag == "mi" and el.get("mathvariant") not in (None, "normal"):
            raise MathError("this formula uses a font style browsers ignore.", "use \\mathbf, \\mathbb or \\mathcal")
        if tag == "mo" and len(el):
            raise MathError.at(tex, max(tex.find("\\mathop"), 0), "\\mathop around a formula cannot be drawn.",
                               "write \\operatorname{name} for a named operator", 7)


def _hint_for_unknown(cmd: str) -> str:
    name = cmd[1:]
    if name in SUGGEST:
        return SUGGEST[name]
    if cmd.startswith("\\") and name.isalpha():
        close = _did_you_mean(name)
        return (f"write \\{close} if that is what you meant; otherwise, " if close else "") + \
            f"for a named function write \\operatorname{{{name}}}, for words \\text{{…}}"
    return "escape special characters: \\{ \\} \\% \\# \\_ \\$"


# ---------------------------------------------------------------------------------------------------------- public
def to_mathml(tex: str, display: bool) -> str:
    """Convert one formula. Raises MathError with a hint when browsers could not show it correctly.

    ``tex`` must not contain ``\\tag``/``\\label`` (use :func:`split_tag_label` on display maths first).
    """
    if not tex.strip():
        raise MathError("the formula is empty.", "write something between the $ signs, or remove them",
                        index=0, column=0)
    source = strip_comments(tex)
    if not source.strip():
        raise MathError("the formula is only a comment.", "remove the % or write the formula before it",
                        index=0, column=0)
    try:
        facts = diagnose(source, display)
        clean, starred = preprocess(source, display, facts)
        raw = convert(clean, display="block" if display else "inline")
    except MathError as exc:
        raise _placed(exc, tex) from None
    except Exception as exc:                                                     # noqa: BLE001 - library errors vary
        raise _placed(_library_error(exc, tex), tex) from None
    try:
        out = postprocess(raw, display, starred, tex)
        validate(out, tex)
    except ET.ParseError as exc:
        raise _placed(MathError(f"the formula produced invalid markup ({exc}).", "simplify the formula"), tex) from None
    except MathError as exc:
        raise _placed(exc, tex) from None
    return out


def _placed(exc: MathError, tex: str) -> MathError:
    """Every error has a position: the start of its line when nothing more precise is known."""
    if exc.column is None or exc.index is None:
        line = max(0, exc.offset or 0)
        starts = [0] + [m.end() for m in re.finditer("\n", tex)]
        exc.index = starts[min(line, len(starts) - 1)]
        exc.column = 0
    return exc



def _library_error(exc: Exception, tex: str) -> MathError:
    name = type(exc).__name__
    if "DoubleSuperscripts" in name:
        return MathError("two superscripts in a row on the same symbol.", "group them: x^{a^b} or {x^a}^b")
    if "DoubleSubscripts" in name:
        return MathError("two subscripts in a row on the same symbol.", "group them: x_{ij} or x_{i_j}")
    if "MissingSuperScriptOrSubscript" in name:
        return MathError("a ^ or _ has nothing after it.", "write x^{2} or x_{i}")
    if "MissingEnd" in name:
        return MathError("a \\begin{…} has no \\end{…}.", "add the \\end{…} after the last row")
    if "ExtraLeftOrMissingRight" in name:
        return MathError("\\left and \\right do not pair up.", "every \\left( needs a \\right) in the same group")
    if "NoAvailableTokens" in name:
        return MathError("a command at the end of the formula has nothing to act on.",
                         "give it its argument in braces, e.g. \\sqrt{x}")
    return MathError(f"the formula could not be read ({name}).",
                     "look for a missing brace, a stray & or an unfinished \\begin{…}")


def check(tex: str, display: bool) -> dict:
    """Convert with the details the Editor and the command line show.

    Returns ``{"ok": True, "mathml", "tag", "label"}`` or ``{"ok": False, "error": {message, hint, line, column,
    index, length}}``. Display formulas may carry ``\\tag``/``\\label``; they are taken out first.
    """
    tag = label = None
    source = tex
    if display:
        source, tag, label = split_tag_label(tex)
    try:
        return {"ok": True, "mathml": to_mathml(source, display), "tag": tag, "label": label}
    except MathError as exc:
        return {"ok": False, "error": exc.to_dict(), "tag": tag, "label": label}
