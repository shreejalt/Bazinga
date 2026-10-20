"""The figure builder: a filled-in form (a JSON "spec") turned into an ordinary figure file.

Authors who do not write code pick a type and fill in a form in the Studio; this module checks the form and
writes ``figures/<name>.py``. The file it writes follows the figure contract exactly and is meant to be read and
edited by hand later, so it is plain, commented, standard-library code that does not import this module (it runs in
the reader's browser, where only the figure file and the renderer are shipped).

Expressions in the form (``a*sin(f*x)*exp(-d*x)``, ``x^2``, ``2pi r``) are parsed with :mod:`ast` against a
whitelist: numbers, the names the form declares, ``+ - * / ^ %``, comparisons, ``and``/``or``, and calls to a fixed
set of maths functions. Nothing is ever passed to ``eval``; the validated tree is turned back into source and written
into the file. Mistakes come back as plain messages that point at the bad part ("unknown name 'freqq' — did you mean
'freq'?").

The last lines of a generated file hold the spec (``# tessera-builder: {...}``) and a hash of everything above it,
so the Studio can reopen the figure in the builder, and can tell when the code was changed by hand (then it opens
as code and the builder leaves it alone).

    problems = validate(spec)          # [] or [{"path", "message", "col", "end", "text"}]
    source = generate(spec)            # raises SpecError(problems)
    info = read_spec(source)           # None, or {"spec": {...}, "edited": bool}
    spec = default_spec("function")    # a working example of each type
"""
from __future__ import annotations

import ast
import builtins
import csv
import difflib
import hashlib
import io
import json
import keyword
import math
import re

__all__ = ["TYPES", "SpecError", "ExprError", "parse_expr", "validate", "generate", "read_spec", "default_spec",
           "describe", "FUNCTIONS", "AGGREGATES", "MARK"]

VERSION = 1
MARK = "# tessera-builder: "

TYPES = {
    "function": {"label": "Function plot", "blurb": "One or more curves y = f(x), with sliders for the numbers in them."},
    "shapes": {"label": "Shapes and curves", "blurb": "Points, lines, arrows, circles and parametric curves placed by expressions."},
    "bars": {"label": "Bars", "blurb": "Bars whose heights are expressions, so they move with the sliders."},
    "heatmap": {"label": "Heatmap", "blurb": "A grid of cells, each coloured by an expression in its row i and column j."},
    "distribution": {"label": "Distribution", "blurb": "Normal, uniform, exponential, binomial or Poisson, with sliders for its parameters."},
    "data": {"label": "Data table", "blurb": "Paste a table (CSV) and draw it as lines, dots or bars, with a fitted line."},
}

# name -> (fewest arguments, most arguments, what it does). Calls to anything else are refused.
FUNCTIONS = {
    "sin": (1, 1, "sine (of an angle in radians)"), "cos": (1, 1, "cosine"), "tan": (1, 1, "tangent"),
    "asin": (1, 1, "inverse sine"), "acos": (1, 1, "inverse cosine"), "atan": (1, 1, "inverse tangent"),
    "atan2": (2, 2, "angle of the point (x, y): atan2(y, x)"),
    "sinh": (1, 1, "hyperbolic sine"), "cosh": (1, 1, "hyperbolic cosine"), "tanh": (1, 1, "hyperbolic tangent"),
    "exp": (1, 1, "e to the power"), "log": (1, 2, "natural logarithm; log(x, b) for base b"),
    "ln": (1, 1, "natural logarithm"), "log10": (1, 1, "logarithm base 10"), "log2": (1, 1, "logarithm base 2"),
    "sqrt": (1, 1, "square root"), "abs": (1, 1, "absolute value"), "sign": (1, 1, "−1, 0 or 1"),
    "floor": (1, 1, "round down"), "ceil": (1, 1, "round up"), "round": (1, 2, "round; round(x, 2) keeps 2 decimals"),
    "min": (2, 8, "the smallest of several numbers"), "max": (2, 8, "the largest of several numbers"),
    "hypot": (2, 2, "length of (x, y)"), "clamp": (3, 3, "clamp(x, low, high) keeps x between low and high"),
    "sigmoid": (1, 1, "1 / (1 + e^−x)"), "relu": (1, 1, "max(x, 0)"), "erf": (1, 1, "the error function"),
    "radians": (1, 1, "degrees to radians"), "degrees": (1, 1, "radians to degrees"),
    "where": (3, 3, "where(condition, a, b) is a when the condition holds, else b"),
}
# Functions of a whole curve or list (readouts): name -> (extra arguments, what it does)
AGGREGATES = {
    "max": (0, "the largest value"), "min": (0, "the smallest value"), "mean": (0, "the average"),
    "sum": (0, "the total"), "std": (0, "the standard deviation"), "area": (0, "the area under it (trapezoids)"),
    "argmax": (0, "where the largest value is (its x, or its position from 1)"),
    "argmin": (0, "where the smallest value is"), "first": (0, "the first value"), "last": (0, "the last value"),
    "at": (1, "at(y, 2) is the value at x = 2 (straight-line interpolation)"),
}
CONSTANTS = {"pi": "pi", "e": "e", "tau": "tau"}
_MATH = {"sin", "cos", "tan", "asin", "acos", "atan", "atan2", "sinh", "cosh", "tanh", "exp", "log", "log10", "log2",
         "sqrt", "floor", "ceil", "hypot", "erf", "radians", "degrees", "pi", "e", "tau"}
_HELPERS = {"sign", "clamp", "sigmoid", "relu"}

STYLE_COLOURS = ("main", "second", "third", "fourth", "muted", "faint", "highlight", "good", "bad", "ink")
STYLE_LINES = ("dashed", "dotted", "thick", "thin", "points", "stems", "area", "outline", "solid", "small")

# Names the generated code uses itself, or that mean something already.
_LOCALS = {"xs", "series", "shapes", "panel", "panels", "readouts", "spec", "matrix", "cells", "bars", "bar_list",
           "rows", "cols", "marks", "points", "data", "values", "items", "note", "title", "fit", "slope",
           "intercept", "r2", "mean", "variance", "std", "prob", "lo", "hi", "density", "x", "i", "j", "k",
           "heights", "ks", "probs", "ts", "pts", "corners", "ends", "known", "pick", "band_x", "band_y", "inside",
           "known_x", "curve_xs", "bar_dicts", "row_labels", "col_labels", "y_label", "t0", "t1", "running",
           "cumulative", "width", "show",
           "t", "n_", "compute", "math", "inf", "nan"}
_MODULE = {"TITLE", "CAPTION", "REQUIRES", "CONTROLS", "PRESETS", "DATA", "X_MIN", "X_MAX", "SAMPLES"}
RESERVED = (set(keyword.kwlist) | set(keyword.softkwlist) | set(FUNCTIONS) | set(AGGREGATES) | set(CONSTANTS)
            | _LOCALS | {n for n in dir(builtins) if n.islower()})
NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,30}$")

LIMITS = {"expr": 400, "nodes": 250, "samples": 1000, "curves": 8, "items": 60, "repeat": 200, "grid": 40,
          "controls": 12, "readouts": 8, "values": 16, "presets": 8, "rows": 2000, "columns": 12, "csv": 100_000}


# ==============================================================================================================
# errors

class ExprError(ValueError):
    """One bad expression: message, and where (character offsets in the text as the author wrote it)."""

    def __init__(self, message, col=None, end=None, text=""):
        super().__init__(message)
        self.message, self.col, self.end, self.text = message, col, end, text


class SpecError(ValueError):
    """The form has problems; .problems is the full list, str() the first one in words."""

    def __init__(self, problems):
        self.problems = list(problems)
        first = self.problems[0] if self.problems else {"path": "", "message": "unknown problem"}
        super().__init__(("%s: %s" % (where_words(first["path"]), first["message"])) if first["path"]
                         else first["message"])


def where_words(path):
    """'curves.0.expr' -> 'curve 1, expression' (for messages outside the form)."""
    parts = str(path).split(".")
    out = []
    i = 0
    while i < len(parts):
        p = parts[i]
        if i + 1 < len(parts) and parts[i + 1].isdigit():
            out.append("%s %d" % (p[:-1] if p.endswith("s") else p, int(parts[i + 1]) + 1))
            i += 2
            continue
        out.append({"expr": "expression", "x_min": "x from", "x_max": "x to"}.get(p, p.replace("_", " ")))
        i += 1
    return ", ".join(out)


# ==============================================================================================================
# expressions

_REPLACE = {"−": "-", "–": "-", "×": "*", "·": "*", "⋅": "*", "÷": "/", "π": "pi", "τ": "tau", "≤": "<=",
            "≥": ">=", "≠": "!=", "²": "^2", "³": "^3"}
_TOKEN = re.compile(r"""
     (?P<ws>\s+)
    |(?P<num>(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)
    |(?P<name>[A-Za-z_][A-Za-z_0-9]*)
    |(?P<str>'[^'\n]*'?|"[^"\n]*"?)
    |(?P<op>\*\*|//|<=|>=|==|!=|:=|[-+*/%^(),<>.\[\]{}:=!&|~@;])
    |(?P<other>.)
""", re.X)


class _Pre:
    """Text after the friendly rewrites (^ -> **, 2x -> 2*x, π -> pi), with a map back to the author's columns."""

    def __init__(self, text, known_scalars=()):
        chars, where = [], []
        for idx, ch in enumerate(text):
            rep = _REPLACE.get(ch, ch)
            for c in rep:
                chars.append(c)
                where.append(idx)
        s = "".join(chars)
        toks = []
        pos = 0
        while pos < len(s):
            m = _TOKEN.match(s, pos)
            kind = m.lastgroup
            if kind == "other":
                raise ExprError("the character %r cannot be used in an expression" % m.group(), where[pos],
                                where[pos] + 1, text)
            toks.append((kind, m.group(), m.start(), m.end()))
            pos = m.end()
        out, omap = [], []

        def emit(t, src_from, src_to):
            for n, c in enumerate(t):
                out.append(c)
                omap.append(where[src_from + min(n, src_to - src_from - 1)] if src_to > src_from else
                            (where[src_from] if src_from < len(where) else len(text)))

        prev = None
        gap = False
        for kind, val, a, b in toks:
            if kind == "ws":
                emit(" ", a, b)
                gap = True
                continue
            if prev is not None and prev[0] == "num" and kind == "name" and val in ("j", "J") and not gap:
                raise ExprError("imaginary numbers (with j) are not supported", where[prev[2]], where[b - 1] + 1, text)
            gap = False
            if prev is not None and not (kind == "name" and keyword.iskeyword(val)) \
                    and not (prev[0] == "name" and keyword.iskeyword(prev[1])):
                pk, pv = prev[0], prev[1]
                implicit = False
                if pk == "num" and (kind == "name" or val == "("):
                    implicit = True
                elif pv == ")" and (kind in ("name", "num") or val == "("):
                    implicit = True
                elif pk == "name" and val == "(" and (pv in known_scalars or pv in CONSTANTS):
                    implicit = True
                elif pk == "name" and pv in FUNCTIONS and kind in ("name", "num") and pv not in known_scalars:
                    raise ExprError("write %s(…) with brackets around what it applies to, e.g. %s(x)" % (pv, pv),
                                    where[a] if a < len(where) else len(text), None, text)
                elif pk == "name" and kind == "name" and not keyword.iskeyword(pv) and not keyword.iskeyword(val):
                    implicit = True
                if implicit:
                    emit("*", a, a + 1)
            if kind == "op" and val == "^":
                emit("**", a, b)
            else:
                emit(val, a, b)
            prev = (kind, val, a)
        self.text = text
        self.code = "".join(out)
        self.omap = omap

    def col(self, offset):
        """Author's column for an offset in self.code."""
        if offset is None:
            return None
        if offset >= len(self.omap):
            return len(self.text)
        return self.omap[offset]


class Expr:
    """A checked expression. .code is the source written into the figure file."""

    def __init__(self, text, code, names, arrays, calls):
        self.text, self.code, self.names, self.arrays, self.calls = text, code, names, arrays, calls

    def __repr__(self):
        return "Expr(%r -> %r)" % (self.text, self.code)

    @property
    def simple(self):
        """A plain name or number: needs no protection against errors."""
        return bool(re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*|-?\d+(\.\d+)?", self.code))


def _byte_to_char(code, off):
    if off is None:
        return None
    return len(code.encode("utf-8")[:off].decode("utf-8", errors="ignore"))


def _suggest(name, options):
    m = difflib.get_close_matches(name, sorted(options), n=1, cutoff=0.6)
    return m[0] if m else None


_OPS = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/", ast.Pow: "^", ast.Mod: "%", ast.FloorDiv: "//"}
_BAD_OPS = {ast.BitAnd: "&", ast.BitOr: "|", ast.BitXor: "^", ast.LShift: "<<", ast.RShift: ">>", ast.MatMult: "@"}
_CMP = (ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Eq, ast.NotEq)
_FORBIDDEN = {
    ast.Lambda: "lambda is not allowed: write the expression itself",
    ast.ListComp: "list comprehensions are not allowed: write one expression (to draw something several times, use Repeat)",
    ast.SetComp: "comprehensions are not allowed: write one expression",
    ast.DictComp: "comprehensions are not allowed: write one expression",
    ast.GeneratorExp: "generator expressions are not allowed: write one expression",
    ast.IfExp: "'… if … else …' is not allowed: write where(condition, a, b)",
    ast.Subscript: "[ ] indexing is not allowed: write one number expression",
    ast.List: "lists are not allowed: write a single number expression",
    ast.Tuple: "a comma outside a function's brackets: write one expression",
    ast.Dict: "{ } is not allowed: write a single number expression",
    ast.Set: "{ } is not allowed: write a single number expression",
    ast.Starred: "'*' unpacking is not allowed",
    ast.NamedExpr: "':=' is not allowed: give the value a name under Values instead",
    ast.JoinedStr: "text in quotes is not allowed: expressions are numbers only",
    ast.Await: "this is not allowed in an expression",
    ast.Yield: "this is not allowed in an expression",
    ast.YieldFrom: "this is not allowed in an expression",
    ast.Slice: "[ ] indexing is not allowed",
}


def parse_expr(text, scalars=(), arrays=(), local=(), where_x=None):
    """Check one expression and return an :class:`Expr`. Raises :class:`ExprError`.

    scalars  names that hold one number here (controls, values, x, i, j …)
    arrays   names that hold a whole list (curves, columns); allowed only inside max(y), mean(y), at(y, 2) …
    local    names that exist only at this spot (x inside a curve); used for "did you mean" and messages
    where_x  the code for the x positions of arrays (for area/argmax/at), e.g. "xs"; None means positions 1, 2, …
    """
    if not isinstance(text, str):
        text = "" if text is None else str(text)
    raw = text
    if not raw.strip():
        raise ExprError("write an expression here, for example 2*x or a*sin(x)", 0, 0, raw)
    if len(raw) > LIMITS["expr"]:
        raise ExprError("this expression is too long (%d characters; at most %d). Give parts of it a name under "
                        "Values." % (len(raw), LIMITS["expr"]), LIMITS["expr"], len(raw), raw)
    scalars, arrays = set(scalars), set(arrays)
    pre = _Pre(raw, scalars)
    code = pre.code
    depth = 0
    for n, ch in enumerate(code):
        depth += (ch == "(") - (ch == ")")
        if depth < 0:
            c = pre.col(n)
            raise ExprError("this ')' has no '(' to close", c, c + 1, raw)
    if depth > 0:
        c = pre.col(code.rfind("(") if code.count("(") else len(code))
        raise ExprError("a '(' is never closed: add ')'", c, (c or 0) + 1, raw)
    try:
        tree = ast.parse(code, mode="eval")
    except SyntaxError as exc:
        off = _byte_to_char(code, (exc.offset or 1) - 1)
        c = pre.col(off)
        msg = "this is not a complete expression"
        if code.rstrip().endswith(("+", "-", "*", "/", "**", "%", "<", ">", "=", ",")):
            msg = "the expression ends with an operator: something is missing after it"
        elif re.search(r"(?<![<>!=])=(?!=)", code):
            msg = "'=' is not allowed: an expression is only the right-hand side (write a*x, not y = a*x)"
        raise ExprError(msg, c, (c or 0) + 1, raw) from None
    except (RecursionError, MemoryError, ValueError):
        raise ExprError("this expression is nested too deeply", 0, len(raw), raw) from None
    nodes = list(ast.walk(tree))
    if len(nodes) > LIMITS["nodes"]:
        raise ExprError("this expression is too long; give parts of it a name under Values", 0, len(raw), raw)
    used, used_arrays, calls = [], [], set()

    def fail(msg, node):
        a = pre.col(_byte_to_char(code, getattr(node, "col_offset", None)))
        b = pre.col(_byte_to_char(code, getattr(node, "end_col_offset", None)))
        if a is not None and b is not None and b <= a:
            b = a + 1
        raise ExprError(msg, a, b, raw)

    known = scalars | arrays | set(CONSTANTS)

    def names_hint():
        visible = sorted(scalars - {"_narrow"})
        return (" Names you can use here: %s." % ", ".join(visible[:14])) if visible else ""

    def check(node, in_agg=False):
        t = type(node)
        if t in _FORBIDDEN:
            fail(_FORBIDDEN[t], node)
        if t is ast.Expression:
            return check(node.body)
        if t is ast.Constant:
            v = node.value
            if isinstance(v, bool) or v is None:
                fail("%r is not a number here: use 1 or 0" % (v,), node)
            if isinstance(v, str) or isinstance(v, bytes):
                fail("text in quotes is not allowed: expressions are numbers only", node)
            if isinstance(v, complex):
                fail("imaginary numbers (with j) are not supported", node)
            if isinstance(v, float) and not math.isfinite(v):
                fail("this number is too large", node)
            return
        if t is ast.Name:
            n = node.id
            if n.startswith("_"):
                fail("names starting with _ are not allowed", node)
            if n in arrays:
                if not in_agg:
                    fail("'%s' is a whole list of values, not one number: use it inside max(%s), mean(%s), "
                         "area(%s), at(%s, 2) …" % (n, n, n, n, n), node)
                used_arrays.append(n)
                return
            if n in scalars:
                used.append(n)
                return
            if n in CONSTANTS:
                calls.add(n)
                return
            if n in FUNCTIONS or n in AGGREGATES:
                fail("'%s' is a function: write %s(…) with what it applies to, e.g. %s(x)" % (n, n, n), node)
            if n in ("x", "i", "j", "k", "t") and n not in scalars:
                fail({"x": "x is only defined inside a curve's expression",
                      "i": "i (the row) is only defined inside a heatmap cell",
                      "j": "j (the column) is only defined inside a heatmap cell",
                      "k": "k is only defined inside an item that repeats (set Repeat)",
                      "t": "t is only defined inside a parametric curve"}[n], node)
            s = _suggest(n, known | set(local))
            fail("unknown name '%s'%s" % (n, (" — did you mean '%s'?" % s) if s else "." + names_hint()), node)
        if t is ast.Attribute:
            if isinstance(node.value, ast.Name) and node.value.id in ("math", "np", "numpy"):
                fail("'.' is not allowed: write %s(…), not %s.%s(…)" % (node.attr, node.value.id, node.attr), node)
            fail("'.' is not allowed here: names are single words like freq or a1", node)
        if t is ast.BinOp:
            if type(node.op) in _BAD_OPS:
                fail("the operator '%s' is not supported: use + − * / ^ (power) and %% (remainder)"
                     % _BAD_OPS[type(node.op)], node)
            if type(node.op) not in _OPS:
                fail("this operator is not supported", node)
            check(node.left)
            check(node.right)
            return
        if t is ast.UnaryOp:
            if isinstance(node.op, (ast.USub, ast.UAdd)):
                return check(node.operand)
            if isinstance(node.op, ast.Not):
                fail("'not' is not supported: write 1 - (condition)", node)
            fail("'~' is not supported", node)
        if t is ast.Compare:
            for op in node.ops:
                if not isinstance(op, _CMP):
                    fail("only < <= > >= == != can compare numbers here", node)
            check(node.left)
            for c in node.comparators:
                check(c)
            return
        if t is ast.BoolOp:
            for v in node.values:
                check(v)
            return
        if t is ast.Call:
            f = node.func
            if not isinstance(f, ast.Name):
                if isinstance(f, ast.Attribute):
                    check(f)
                fail("only maths functions can be called, by name, like sin(x)", node)
            name = f.id
            if node.keywords:
                fail("write %s(…) without name=value inside the brackets" % name, node)
            if any(isinstance(a, ast.Starred) for a in node.args):
                fail("'*' unpacking is not allowed", node)
            nargs = len(node.args)
            agg = (name in AGGREGATES and nargs >= 1 and isinstance(node.args[0], ast.Name)
                   and node.args[0].id in arrays)
            if agg:
                extra = AGGREGATES[name][0]
                if nargs != 1 + extra:
                    fail("%s takes %s" % (name, "one list, e.g. %s(y)" % name if not extra else
                                          "a list and a position, e.g. at(y, 2)"), node)
                calls.add("agg_" + name)
                check(node.args[0], in_agg=True)
                for a in node.args[1:]:
                    check(a)
                return
            if name in AGGREGATES and name not in FUNCTIONS:
                if arrays:
                    fail("%s(…) works on a whole list: one of %s" % (name, ", ".join(sorted(arrays))), node)
                fail("%s(…) needs a list of values, and there is none here" % name, node)
            if name not in FUNCTIONS:
                if name.startswith("_"):
                    fail("'%s' is not allowed: only maths functions can be called (sin, cos, exp, sqrt, …)" % name, node)
                s = _suggest(name, set(FUNCTIONS) | set(AGGREGATES))
                if name in scalars:
                    fail("'%s' is a number, not a function: write %s*(…) to multiply" % (name, name), node)
                fail("'%s' is not a function you can use%s" % (
                    name, (" — did you mean '%s'?" % s) if s else ". Functions: " + ", ".join(sorted(FUNCTIONS))), node)
            lo, hi, _doc = FUNCTIONS[name]
            if not lo <= nargs <= hi:
                if name in ("max", "min") and nargs == 1 and isinstance(node.args[0], ast.Name):
                    check(node.args[0], in_agg=True)     # an unknown or misspelt list name says so
                if name in ("max", "min") and nargs == 1:
                    fail("%s needs two or more numbers, or a whole list like %s(y)" % (name, name), node)
                want = ("%d number%s" % (lo, "" if lo == 1 else "s")) if lo == hi else "%d to %d numbers" % (lo, hi)
                fail("%s takes %s: %s" % (name, want, _doc), node)
            calls.add(name)
            for a in node.args:
                check(a)
            return
        fail("'%s' is not allowed in an expression" % t.__name__, node)

    check(tree)
    out = _Codegen(where_x, arrays).visit(tree)
    ast.fix_missing_locations(out)
    pycode = ast.unparse(out.body)
    return Expr(raw, pycode, list(dict.fromkeys(used)), list(dict.fromkeys(used_arrays)), calls)


class _Codegen(ast.NodeTransformer):
    """Validated tree -> the tree written into the figure file (ln -> log, where -> if/else, max(y) -> _max(y))."""

    def __init__(self, where_x, arrays):
        self.where_x, self.arrays = where_x, arrays

    def visit_Call(self, node):
        name = node.func.id
        args = [self.visit(a) for a in node.args]
        if name in AGGREGATES and args and isinstance(args[0], ast.Name) and args[0].id in self.arrays:
            pos = ast.Name(self.where_x, ast.Load()) if self.where_x else ast.Constant(None)
            if name in ("area", "argmax", "argmin", "at"):
                args = [args[0], pos] + args[1:]
            return ast.Call(ast.Name("_" + name, ast.Load()), args, [])
        if name == "ln":
            return ast.Call(ast.Name("log", ast.Load()), args, [])
        if name == "where":
            return ast.IfExp(args[0], args[1], args[2])
        return ast.Call(ast.Name(name, ast.Load()), args, [])

    def visit_BinOp(self, node):
        node.left, node.right = self.visit(node.left), self.visit(node.right)
        if isinstance(node.op, ast.Pow):
            # 9 ** 9 ** 9 with whole numbers would be computed exactly (and take forever); as a float it overflows
            # at once and the point is simply left out.
            if isinstance(node.left, ast.Constant) and isinstance(node.left.value, int):
                node.left = ast.Constant(float(node.left.value))
        return node


# ==============================================================================================================
# writing Python source

def _lit(v):
    """A Python literal for JSON-like data (True/False/None, strings with double quotes)."""
    if v is None:
        return "None"
    if isinstance(v, bool):
        return "True" if v else "False"
    if isinstance(v, int):
        return repr(v)
    if isinstance(v, float):
        return repr(v)
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(_lit(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{" + ", ".join("%s: %s" % (_lit(str(k)), _lit(x)) for k, x in v.items()) + "}"
    raise TypeError("cannot write %r" % (v,))


def _num_lit(v):
    """Numbers as the author typed them: 2 stays 2, 0.5 stays 0.5."""
    if isinstance(v, float) and v.is_integer() and abs(v) < 1e15:
        return str(int(v))
    return repr(v)


class _W:
    def __init__(self):
        self.lines = []

    def __call__(self, line="", indent=0):
        self.lines.append(("    " * indent + line) if line else "")

    def text(self):
        return "\n".join(self.lines).rstrip() + "\n"


def _comment(text):
    return " ".join(str(text).split())


# ==============================================================================================================
# the form (spec) -> problems

class _Ctx:
    """Collects problems while checking a spec, and keeps the parsed expressions for the code writer."""

    def __init__(self):
        self.problems = []
        self.exprs = {}

    def add(self, path, message, col=None, end=None, text=None):
        self.problems.append({"path": path, "message": message, "col": col, "end": end, "text": text})

    def expr(self, path, text, scalars, arrays=(), local=(), where_x=None, required=True):
        if text is None or (isinstance(text, str) and not text.strip()):
            if required:
                self.add(path, "write an expression here, for example 2*x or a*sin(x)", 0, 0, "")
            return None
        if isinstance(text, (int, float)) and not isinstance(text, bool):
            text = _num_lit(text)
        if not isinstance(text, str):
            self.add(path, "this must be an expression (text), like a*x")
            return None
        try:
            e = parse_expr(text, scalars, arrays, local, where_x)
        except ExprError as exc:
            self.add(path, exc.message, exc.col, exc.end, text)
            return None
        self.exprs[path] = e
        return e

    def template(self, path, text, scalars, arrays=(), where_x=None):
        """'T = {t:.2f}' -> list of parts: str or (Expr, decimals)."""
        if text is None:
            return []
        if not isinstance(text, str):
            text = str(text)
        parts = []
        pos = 0
        for m in re.finditer(r"\{\{|\}\}|\{([^{}]*)\}", text):
            if m.start() > pos:
                parts.append(text[pos:m.start()])
            tok = m.group(0)
            if tok in ("{{", "}}"):
                parts.append(tok[0])
            else:
                inner = m.group(1)
                dec = None
                fm = re.fullmatch(r"(.*?):\s*\.?(\d)f?\s*", inner)
                if fm:
                    inner, dec = fm.group(1), int(fm.group(2))
                try:
                    e = parse_expr(inner, scalars, arrays, (), where_x)
                except ExprError as exc:
                    off = m.start(1)
                    self.add(path, "in {%s}: %s" % (m.group(1), exc.message),
                             (exc.col or 0) + off if exc.col is not None else off,
                             (exc.end or 0) + off if exc.end is not None else m.end(), text)
                    e = None
                parts.append((e, dec))
            pos = m.end()
        if pos < len(text):
            parts.append(text[pos:])
        if re.search(r"(?<!\{)\{(?!\{)[^}]*$", text):
            self.add(path, "a '{' is never closed with '}'", text.rfind("{"), len(text), text)
        return parts


def _number(ctx, path, v, required=True, integer=False):
    if v is None or (isinstance(v, str) and not v.strip()):
        if required:
            ctx.add(path, "a number is needed here")
        return None
    if isinstance(v, bool):
        ctx.add(path, "a number is needed here")
        return None
    if isinstance(v, str):
        try:
            v = float(v.strip().replace("−", "-"))
        except ValueError:
            ctx.add(path, "%r is not a number" % v)
            return None
    if not isinstance(v, (int, float)) or not math.isfinite(v):
        ctx.add(path, "a number is needed here")
        return None
    if integer:
        if float(v) != int(v):
            ctx.add(path, "a whole number is needed here")
            return None
        return int(v)
    return int(v) if float(v).is_integer() and isinstance(v, int) else float(v)


def _style(ctx, path, s, default="main"):
    s = (s or default)
    if not isinstance(s, str):
        ctx.add(path, "a style is a name like main, second or 'muted dashed'")
        return default
    words = s.replace(",", " ").split()
    for w in words:
        if w not in STYLE_COLOURS and w not in STYLE_LINES:
            sug = _suggest(w, set(STYLE_COLOURS) | set(STYLE_LINES))
            ctx.add(path, "unknown style '%s'%s" % (w, (" — did you mean '%s'?" % sug) if sug else
                                                     ". Colours: %s; lines: %s" % (", ".join(STYLE_COLOURS), ", ".join(STYLE_LINES))))
    return " ".join(words) or default


def _list(ctx, path, v, limit):
    if v is None:
        return []
    if not isinstance(v, list):
        ctx.add(path, "this must be a list")
        return []
    if len(v) > limit:
        ctx.add(path, "at most %d here (there are %d)" % (limit, len(v)))
        return v[:limit]
    return v


def _check_name(ctx, path, name, taken, what):
    if not isinstance(name, str) or not name.strip():
        ctx.add(path, "give the %s a short name (letters, digits and _), like freq" % what)
        return None
    name = name.strip()
    if not NAME_RE.match(name):
        fixed = re.sub(r"[^a-z0-9_]", "_", name.lower()).strip("_")
        ctx.add(path, "a name is lowercase letters, digits and _, starting with a letter%s"
                % ((" (for example %s)" % fixed) if fixed and NAME_RE.match(fixed) else ""))
        return None
    if name in RESERVED or name in _MODULE:
        meaning = ("is the position across" if name == "x" else "is the row" if name == "i" else
                   "is the column" if name == "j" else "is a maths function" if name in FUNCTIONS or name in AGGREGATES
                   else "is a constant" if name in CONSTANTS else "already means something")
        ctx.add(path, "'%s' %s; pick another name" % (name, meaning))
        return None
    if name in taken:
        ctx.add(path, "the name '%s' is used twice" % name)
        return None
    taken.add(name)
    return name


def _controls(ctx, spec, taken):
    """Check the controls; returns (controls for the file, {name: kind}, numeric steps {name: [values]})."""
    out, kinds, numeric = [], {}, {}
    for n, c in enumerate(_list(ctx, "controls", spec.get("controls"), LIMITS["controls"])):
        p = "controls.%d" % n
        if not isinstance(c, dict):
            ctx.add(p, "each control is a small form (name, label, …)")
            continue
        name = _check_name(ctx, p + ".name", c.get("name"), taken, "control")
        kind = c.get("kind", "slider")
        if name:
            kinds[name] = kind if kind in ("slider", "toggle", "steps") else "slider"
        label = str(c.get("label") or (name or "")).strip() or (name or "")
        if kind not in ("slider", "toggle", "steps"):
            ctx.add(p + ".kind", "a control is a slider, a toggle or steps")
            continue
        if kind == "slider":
            lo = _number(ctx, p + ".min", c.get("min"))
            hi = _number(ctx, p + ".max", c.get("max"))
            st = _number(ctx, p + ".step", c.get("step"), required=False)
            val = _number(ctx, p + ".value", c.get("value"), required=False)
            if lo is None or hi is None:
                continue
            if not lo < hi:
                ctx.add(p + ".max", "the largest value must be above the smallest (%s)" % _num_lit(lo))
                continue
            if st is None:
                st = _nice_step((hi - lo) / 100.0)
            if st <= 0:
                ctx.add(p + ".step", "the step must be above 0")
                continue
            if (hi - lo) / st > 100000:
                ctx.add(p + ".step", "this step is too small for the range (more than 100,000 positions)")
                continue
            if val is None:
                val = lo
            if not lo <= val <= hi:
                ctx.add(p + ".value", "the starting value must be between %s and %s" % (_num_lit(lo), _num_lit(hi)))
                continue
            item = {"name": name, "kind": "slider", "label": label, "min": lo, "max": hi, "step": st, "value": val}
            if c.get("play"):
                item["play"] = True
        else:
            opts = c.get("options")
            if isinstance(opts, str):
                opts = [o.strip() for o in opts.split(",")]
            if not isinstance(opts, list) or not [o for o in opts if str(o).strip()]:
                ctx.add(p + ".options", "list the choices, separated by commas (for example: Hide, Show)")
                continue
            opts = [str(o).strip() for o in opts if str(o).strip()]
            if kind == "toggle" and len(opts) != 2:
                ctx.add(p + ".options", "a toggle has exactly two choices (use steps for more)")
                continue
            if len(opts) > 12:
                ctx.add(p + ".options", "at most 12 choices")
                continue
            val = c.get("value", 0)
            if isinstance(val, str) and val in opts:
                val = opts.index(val)
            val = _number(ctx, p + ".value", val, integer=True)
            if val is None:
                continue
            if not 0 <= val < len(opts):
                ctx.add(p + ".value", "the starting choice is a position from 0 to %d" % (len(opts) - 1))
                continue
            item = {"name": name, "kind": kind, "label": label, "options": opts, "value": val}
            if kind == "steps":
                nums = []
                for o in opts:
                    try:
                        nums.append(float(o.replace("−", "-")))
                    except ValueError:
                        nums = None
                        break
                if nums:
                    numeric[name] = [int(v) if v.is_integer() else v for v in nums]
        if name:
            kinds[name] = kind
            out.append(item)
    return out, kinds, numeric


def _nice_step(raw):
    if raw <= 0:
        return 1
    e = math.floor(math.log10(raw))
    for m in (1, 2, 5, 10):
        if m * 10 ** e >= raw:
            v = m * 10 ** e
            return int(v) if float(v).is_integer() else round(v, 12)
    return raw


def _presets(ctx, spec, controls):
    by = {c["name"]: c for c in controls}
    out, labels = [], set()
    for n, ps in enumerate(_list(ctx, "presets", spec.get("presets"), LIMITS["presets"])):
        p = "presets.%d" % n
        if not isinstance(ps, dict):
            ctx.add(p, "each preset has a label and values")
            continue
        label = str(ps.get("label") or "").strip()
        if not label:
            ctx.add(p + ".label", "a preset needs a label (the button's text)")
            continue
        if label.lower() == "reset":
            ctx.add(p + ".label", "'Reset' is added for you; pick another label")
            continue
        if label in labels:
            ctx.add(p + ".label", "the label '%s' is used twice" % label)
            continue
        labels.add(label)
        vals = ps.get("values") or {}
        if not isinstance(vals, dict) or not vals:
            ctx.add(p + ".values", "set at least one control's value")
            continue
        clean = {}
        for k, v in vals.items():
            if k not in by:
                s = _suggest(k, set(by))
                ctx.add(p + ".values", "'%s' is not a control%s" % (k, (" — did you mean '%s'?" % s) if s else ""))
                continue
            c = by[k]
            if c["kind"] == "slider":
                x = _number(ctx, p + ".values." + k, v)
                if x is None:
                    continue
                if not c["min"] <= x <= c["max"]:
                    ctx.add(p + ".values." + k, "%s must be between %s and %s" % (k, _num_lit(c["min"]), _num_lit(c["max"])))
                    continue
                clean[k] = x
            else:
                if isinstance(v, str) and v in c["options"]:
                    v = c["options"].index(v)
                x = _number(ctx, p + ".values." + k, v, integer=True)
                if x is None or not 0 <= x < len(c["options"]):
                    ctx.add(p + ".values." + k, "%s is one of its choices, by position 0 to %d" % (k, len(c["options"]) - 1))
                    continue
                clean[k] = x
        if clean:
            out.append({"label": label, "values": clean})
    return out


def _values(ctx, spec, scalars, taken, arrays=()):
    out = []
    for n, v in enumerate(_list(ctx, "values", spec.get("values"), LIMITS["values"])):
        p = "values.%d" % n
        if not isinstance(v, dict):
            ctx.add(p, "each value has a name and an expression")
            continue
        e = ctx.expr(p + ".expr", v.get("expr"), scalars, arrays)
        name = _check_name(ctx, p + ".name", v.get("name"), taken, "value")
        if name and e is not None:
            out.append((name, e))
            scalars.add(name)
        elif name:
            scalars.add(name)
    return out


def _readouts(ctx, spec, scalars, arrays, where_x):
    out = []
    for n, r in enumerate(_list(ctx, "readouts", spec.get("readouts"), LIMITS["readouts"])):
        p = "readouts.%d" % n
        if not isinstance(r, dict):
            ctx.add(p, "each readout has a label and an expression")
            continue
        label = str(r.get("label") or "").strip()
        if not label:
            ctx.add(p + ".label", "a readout needs a label, like Peak")
        e = ctx.expr(p + ".expr", r.get("expr"), scalars, arrays, where_x=where_x)
        dec = r.get("decimals")
        if dec in ("", None):
            dec = None
        else:
            dec = _number(ctx, p + ".decimals", dec, integer=True)
            if dec is not None and not 0 <= dec <= 6:
                ctx.add(p + ".decimals", "between 0 and 6 decimals")
                dec = None
        unit = str(r.get("unit") or "")
        note = ctx.template(p + ".note", r.get("note") or "", scalars, arrays, where_x)
        if label and e is not None:
            out.append({"label": label, "expr": e, "decimals": dec, "unit": unit, "note": note})
    return out


# ==============================================================================================================
# validate + generate

def validate(spec):
    """Every problem in the form: [{"path", "message", "col", "end", "text"}] (empty when it is fine)."""
    return _build(spec)[0]


def generate(spec):
    """The figure file for a spec (a string). Raises SpecError when the form has problems."""
    problems, source = _build(spec)
    if problems:
        raise SpecError(problems)
    return source


def _build(spec):
    ctx = _Ctx()
    if not isinstance(spec, dict):
        return [{"path": "", "message": "the form is empty", "col": None, "end": None, "text": None}], None
    kind = spec.get("type")
    if kind not in TYPES:
        ctx.add("type", "pick what to draw: %s" % ", ".join(t["label"] for t in TYPES.values()))
        return ctx.problems, None
    title = str(spec.get("title") or "").strip()
    if not title:
        ctx.add("title", "give the figure a title (shown above it)")
    if len(title) > 120:
        ctx.add("title", "keep the title under 120 characters")
    caption = str(spec.get("caption") or "").strip()
    if len(caption) > 400:
        ctx.add("caption", "keep the caption under 400 characters (one or two sentences)")
    taken = set()
    before, after = _type_controls(ctx, kind, spec)
    taken |= {c["name"] for c in before + after}
    own, kinds, numeric = _controls(ctx, spec, taken)
    controls = before + own + after
    presets = _presets(ctx, spec, controls)
    w = _W()
    gen = _Gen(ctx, spec, kind, title, caption, controls, kinds, numeric, presets, taken, w)
    try:
        getattr(gen, "type_" + kind)()
    except _Stop:
        pass
    if ctx.problems:
        return ctx.problems, None
    source = gen.finish()
    try:
        compile(source, "<figure>", "exec")
    except SyntaxError as exc:      # a bug here, not the author's: say so plainly
        return [{"path": "", "message": "the builder wrote code that does not compile (line %s): %s. Please "
                 "report this." % (exc.lineno, exc.msg), "col": None, "end": None, "text": None}], None
    return [], source


def _type_controls(ctx, kind, spec):
    """Controls a type brings itself: (before the author's own, after them)."""
    if kind == "distribution":
        fam_name = spec.get("family") or "normal"
        fam = FAMILIES.get(fam_name)
        if fam is None:
            return [], []
        params = []
        over = spec.get("params") if isinstance(spec.get("params"), dict) else {}
        for pname, d in fam["params"].items():
            o = over.get(pname) if isinstance(over.get(pname), dict) else {}
            c = {"name": pname, "kind": "slider", "label": str(o.get("label") or d["label"])}
            for key in ("min", "max", "step", "value"):
                v = _number(ctx, "params.%s.%s" % (pname, key), o.get(key, d[key]))
                c[key] = d[key] if v is None else v
            pp = "params.%s." % pname
            if fam_name == "binomial" and pname == "n":
                for key in ("min", "max", "step", "value"):
                    if float(c[key]) != int(c[key]):
                        ctx.add(pp + key, "the number of trials is a whole number")
                    c[key] = int(c[key])
                if c["min"] < 0 or c["max"] > 200:
                    ctx.add(pp + "max", "between 0 and 200 trials")
            if fam_name == "binomial" and pname == "p" and (c["min"] < 0 or c["max"] > 1):
                ctx.add(pp + "max", "a chance is between 0 and 1")
            if fam_name == "normal" and pname == "sigma" and c["min"] <= 0:
                ctx.add(pp + "min", "the standard deviation must stay above 0")
            if fam_name == "exponential" and c["min"] <= 0:
                ctx.add(pp + "min", "the rate must stay above 0")
            if fam_name == "poisson" and (c["min"] <= 0 or c["max"] > 100):
                ctx.add(pp + ("min" if c["min"] <= 0 else "max"), "the rate must be above 0 and at most 100")
            if not c["min"] < c["max"]:
                ctx.add(pp + "max", "the largest value must be above the smallest")
            elif not c["min"] <= c["value"] <= c["max"]:
                ctx.add(pp + "value", "the starting value must be in the range")
            if c["step"] <= 0:
                ctx.add(pp + "step", "the step must be above 0")
            params.append(c)
        after = []
        interval = spec.get("interval") if isinstance(spec.get("interval"), dict) else {}
        if interval.get("mode") == "sigma":
            after.append({"name": "width", "kind": "slider", "label": "Shaded band (± σ)",
                          "min": 0.25, "max": 3, "step": 0.05, "value": 1})
        if spec.get("cdf_toggle"):
            after.append({"name": "show", "kind": "toggle", "label": "Show",
                          "options": ["Probability", "Cumulative"], "value": 0})
        return params, after
    if kind == "data" and spec.get("fit_toggle") and spec.get("fit") == "line":
        return [], [{"name": "fit", "kind": "toggle", "label": "Fitted line", "options": ["Hide", "Show"], "value": 1}]
    return [], []


class _Stop(Exception):
    pass


FAMILIES = {
    "normal": {"label": "Normal", "discrete": False, "params": {
        "mu": {"label": "Mean μ", "min": -3, "max": 3, "step": 0.1, "value": 0},
        "sigma": {"label": "Standard deviation σ", "min": 0.3, "max": 2.5, "step": 0.05, "value": 1}}},
    "uniform": {"label": "Uniform", "discrete": False, "params": {
        "a": {"label": "Lower end a", "min": -5, "max": 4, "step": 0.1, "value": -1},
        "b": {"label": "Upper end b", "min": -4, "max": 5, "step": 0.1, "value": 2}}},
    "exponential": {"label": "Exponential", "discrete": False, "params": {
        "rate": {"label": "Rate λ", "min": 0.1, "max": 3, "step": 0.05, "value": 1}}},
    "binomial": {"label": "Binomial", "discrete": True, "params": {
        "n": {"label": "Trials n", "min": 1, "max": 40, "step": 1, "value": 10},
        "p": {"label": "Success chance p", "min": 0, "max": 1, "step": 0.01, "value": 0.5}}},
    "poisson": {"label": "Poisson", "discrete": True, "params": {
        "lam": {"label": "Average rate λ", "min": 0.5, "max": 20, "step": 0.1, "value": 4}}},
}


class _Gen:
    """Writes the figure file. Each type_* method checks its part of the form and writes compute()."""

    def __init__(self, ctx, spec, kind, title, caption, controls, kinds, numeric, presets, taken, w):
        self.ctx, self.spec, self.kind = ctx, spec, kind
        self.title, self.caption = title, caption
        self.controls, self.kinds, self.numeric, self.presets = controls, kinds, numeric, presets
        self.taken = taken
        self.w = w
        self.imports = set()
        self.helpers = set()
        self.pre = []          # module-level lines after PRESETS
        self.defs = []         # module-level functions (curves, cells)
        self.body = _W()       # compute()'s body
        self.curve_names = set()

    # --- shared pieces -----------------------------------------------------------------------------------------
    def scalars(self):
        # every control with a usable name, even one with other problems (so its uses are not reported too)
        return set(c["name"] for c in self.controls) | set(self.kinds)

    def note_calls(self, e):
        if e is None:
            return
        for c in e.calls:
            if c.startswith("agg_"):
                self.helpers.add("_" + c[4:])
            elif c in _MATH:
                self.imports.add(c)
            elif c in _HELPERS:
                self.helpers.add(c)
        if "log" in e.code and "ln" in e.calls:
            self.imports.add("log")
        if "ln" in e.calls:
            self.imports.add("log")
        self.helpers.add("_value")

    def val(self, e):
        """Code for an expression's value inside compute() (None when it is undefined)."""
        self.note_calls(e)
        if e.simple:
            return e.code
        return "_value(lambda: %s)" % e.code

    def tmpl(self, parts):
        """Code for a label with {expressions}."""
        if not parts:
            return '""'
        if all(isinstance(p, str) for p in parts):
            return _lit("".join(parts))
        self.helpers.add("_fmt")
        merged = []
        for p in parts:
            if isinstance(p, str) and merged and isinstance(merged[-1], str):
                merged[-1] += p
            else:
                merged.append(p)
        out = []
        for p in merged:
            if isinstance(p, str):
                out.append(_lit(p))
            else:
                e, dec = p
                if e is None:
                    continue
                out.append("_fmt(%s%s)" % (self.val(e), (", %d" % dec) if dec is not None else ""))
        return " + ".join(out) if out else '""'

    def control_lines(self):
        """Inside compute(): steps whose choices are numbers become those numbers."""
        for c in self.controls:
            if c["name"] in self.numeric:
                self.body("%s = %s[%s]   # the chosen option, as a number" % (
                    c["name"], "(" + ", ".join(_num_lit(v) for v in self.numeric[c["name"]]) + ("," if len(self.numeric[c["name"]]) == 1 else "") + ")", c["name"]), 1)

    def values_lines(self, values):
        if values:
            self.body("# values worked out from the controls (None where one is not defined)", 1)
            for name, e in values:
                self.body("%s = %s   # %s" % (name, self.val(e), _comment(e.text)), 1)
            self.body()

    def readouts_code(self, readouts):
        items = []
        for r in readouts:
            self.helpers.add("_fmt")
            v = "_fmt(%s%s)" % (self.val(r["expr"]), (", %d" % r["decimals"]) if r["decimals"] is not None else "")
            if r["unit"]:
                v += " + " + _lit((" " if not r["unit"].startswith(("%", "°")) else "") + r["unit"])
            item = '{"label": %s, "value": %s' % (_lit(r["label"]), v)
            if r["note"]:
                item += ', "note": %s' % self.tmpl(r["note"])
            items.append(item + "}")
        return items

    def finish(self):
        w = self.w
        doc = TYPES[self.kind]["label"].lower()
        w('"""%s' % self.title.replace('"""', "'''").replace("\\", "\\\\"))
        w()
        w("Made with the figure builder (a %s). Open it in the Studio to change it with the form, or edit" % doc)
        w("this file by hand: it is an ordinary figure file, and the Studio then opens it as code.")
        w()
        w("How it works: compute() receives the value of every control and returns a description of the picture")
        w("(panels, lines, bars, readouts). The site draws it when the page is built, and again in the reader's")
        w("browser each time a control moves, so compute() must be quick and give the same picture for the same")
        w("values. Styles are names (main, second, muted, dashed …); the site's theme gives them their colours.")
        w('"""')
        w()
        mods = sorted(self.imports - {"pi", "e", "tau"}) + sorted(self.imports & {"pi", "e", "tau"})
        needs_math = any(h in self.helpers for h in ("_value", "_fmt", "_std", "sigmoid")) or self.kind in ("distribution", "data")
        if needs_math:
            w("import math")
        if mods:
            w("from math import " + ", ".join(mods))
        if needs_math or mods:
            w()
        w("TITLE = %s" % _lit(self.title))
        w("CAPTION = %s" % _lit(self.caption))
        w("REQUIRES = []")
        w()
        controls = self.controls
        if controls:
            w("# The controls under the figure, in order. compute() receives each one by its name.")
            if any(c["kind"] == "toggle" for c in controls):
                w("# A toggle gives 0 or 1, steps give the position of the chosen option (or its number).")
            w("CONTROLS = [")
            for c in controls:
                w(_lit(c) + ",", 1)
            w("]")
        else:
            w("CONTROLS = []")
        w()
        if self.presets:
            w("# Buttons that set several controls at once (Reset is added for you).")
            w("PRESETS = [")
            for p in self.presets:
                w(_lit(p) + ",", 1)
            w("]")
        else:
            w("PRESETS = []")
        w()
        for line in self.pre:
            w(line)
        if self.pre:
            w()
            w()
        for d in self.defs:
            for line in d:
                w(line)
            w()
            w()
        args = ", ".join("%s=%s" % (c["name"], _num_lit(c["value"])) for c in controls)
        w("def compute(%s_narrow=0):" % ((args + ", ") if args else ""))
        w("    # _narrow is 1 when the figure is drawn for a phone.")
        for line in self.body.lines:
            w(line)
        w()
        w()
        self.write_helpers(w)
        body = w.text() + "\n"
        spec = clean_spec(self.spec)
        digest = _digest(body)
        tail = ("\n# " + "-" * 110 + "\n"
                "# The figure builder's settings. The Studio uses this line to reopen the figure in the builder; once\n"
                "# the code above is changed by hand, it opens the figure as code instead and leaves this line alone.\n"
                + MARK + json.dumps({"v": VERSION, "hash": digest, "spec": spec}, ensure_ascii=False,
                                    separators=(",", ":")) + "\n")
        return body + tail

    def write_helpers(self, w):
        hs = self.helpers
        if hs & {"_value", "_fmt", "_max", "_min", "_mean", "_sum", "_std", "_area", "_argmax", "_argmin",
                 "_first", "_last", "_at", "_count", "_add", "sign", "clamp", "sigmoid", "relu", "_fit_line"}:
            w("# " + "-" * 110)
            w("# Small helpers used above.")
            w()
        if "_value" in hs:
            w("def _value(fn, *args):")
            w('    """fn(*args) as a plain number, or None where it is not defined (log of 0, 1/0, an overflow …)."""')
            w("    try:")
            w("        v = fn(*args)")
            w("    except (ArithmeticError, ValueError, TypeError):")
            w("        return None")
            w("    if isinstance(v, bool):")
            w("        return 1.0 if v else 0.0")
            w("    if not isinstance(v, (int, float)):")
            w("        return None")
            w("    try:")
            w("        v = float(v)")
            w("    except OverflowError:")
            w("        return None")
            w("    return v if math.isfinite(v) else None")
            w()
            w()
        if "_fmt" in hs:
            w("def _fmt(v, decimals=None):")
            w('    """A number as readable text (− for minus); a dash when it is not defined."""')
            w("    if v is None:")
            w('        return "—"')
            w("    if decimals is not None:")
            w('        text = "%.*f" % (decimals, v)')
            w("    elif v == 0:")
            w('        text = "0"')
            w("    elif abs(v) >= 10000:")
            w('        text = "{:,.0f}".format(v)')
            w("    elif abs(v) >= 0.001:")
            w('        text = "%.4g" % v')
            w("    else:")
            w('        text = "%.2e" % v')
            w('    if text.lstrip("-").strip("0.") == "":')
            w('        text = text.lstrip("-")')
            w('    return text.replace("-", "−")')
            w()
            w()
        if hs & {"_max", "_min", "_mean", "_sum", "_std", "_area", "_argmax", "_argmin", "_first", "_last", "_at"}:
            w("def _known(ys, xs=None):")
            w('    """The (position, value) pairs where a value is defined; positions count from 1 when there is no x."""')
            w("    xs = xs if xs is not None else range(1, len(ys) + 1)")
            w("    return [(x, y) for x, y in zip(xs, ys) if y is not None and x is not None]")
            w()
            w()
        agg = {
            "_max": ["def _max(ys):", "    return max(y for _, y in _known(ys))"],
            "_min": ["def _min(ys):", "    return min(y for _, y in _known(ys))"],
            "_mean": ["def _mean(ys):", "    vals = [y for _, y in _known(ys)]", "    return sum(vals) / len(vals)"],
            "_sum": ["def _sum(ys):", "    return sum(y for _, y in _known(ys))"],
            "_std": ["def _std(ys):", "    vals = [y for _, y in _known(ys)]", "    m = sum(vals) / len(vals)",
                     "    return math.sqrt(sum((v - m) ** 2 for v in vals) / len(vals))"],
            "_area": ["def _area(ys, xs=None):", '    """The area under the values (trapezoids); with no x, the sum."""',
                      "    if xs is None:", "        return sum(y for _, y in _known(ys))",
                      "    total = 0.0", "    for (x0, y0), (x1, y1) in zip(zip(xs, ys), zip(xs[1:], ys[1:])):",
                      "        if None not in (x0, y0, x1, y1):", "            total += (x1 - x0) * (y0 + y1) / 2",
                      "    return total"],
            "_argmax": ["def _argmax(ys, xs=None):", '    """Where the largest value is: its x (or its position from 1)."""',
                        "    return max(_known(ys, xs), key=lambda p: p[1])[0]"],
            "_argmin": ["def _argmin(ys, xs=None):", "    return min(_known(ys, xs), key=lambda p: p[1])[0]"],
            "_first": ["def _first(ys):", "    return _known(ys)[0][1]"],
            "_last": ["def _last(ys):", "    return _known(ys)[-1][1]"],
            "_at": ["def _at(ys, xs, x):", '    """The value at x, on the straight line between the two nearest points."""',
                    "    pts = sorted(_known(ys, xs))", "    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):",
                    "        if x0 <= x <= x1:", "            return y0 if x1 == x0 else y0 + (y1 - y0) * (x - x0) / (x1 - x0)",
                    "    return None"],
        }
        for name in ("_max", "_min", "_mean", "_sum", "_std", "_area", "_argmax", "_argmin", "_first", "_last", "_at"):
            if name in hs:
                for line in agg[name]:
                    w(line)
                w()
                w()
        small = {
            "sign": ["def sign(v):", "    return (v > 0) - (v < 0)"],
            "clamp": ["def clamp(v, low, high):", "    return min(max(v, low), high)"],
            "sigmoid": ["def sigmoid(v):", "    return 1 / (1 + math.exp(-v)) if v >= -700 else 0.0"],
            "relu": ["def relu(v):", "    return max(v, 0)"],
            "_count": ["def _count(v, most):", '    """A repeat count: a whole number from 0 to most (0 when it is not defined)."""',
                       "    return 0 if v is None else int(min(max(round(v), 0), most))"],
            "_add": ["def _add(items, shape, needs):", '    """Add a shape unless one of its numbers is not defined."""',
                     "    if all(shape.get(k) is not None for k in needs) and shape.get(\"r\", 0) >= 0:",
                     "        items.append(shape)"],
            "_fit_line": ["def _fit_line(xs, ys):", '    """Slope, intercept and R² of the least-squares line through the defined points."""',
                          "    pts = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]",
                          "    if len(pts) < 2:", "        return None, None, None",
                          "    n = len(pts)", "    mx = sum(x for x, _ in pts) / n", "    my = sum(y for _, y in pts) / n",
                          "    sxx = sum((x - mx) ** 2 for x, _ in pts)", "    if sxx == 0:", "        return None, None, None",
                          "    slope = sum((x - mx) * (y - my) for x, y in pts) / sxx", "    intercept = my - slope * mx",
                          "    total = sum((y - my) ** 2 for _, y in pts)",
                          "    left = sum((y - slope * x - intercept) ** 2 for x, y in pts)",
                          "    return slope, intercept, (1 - left / total) if total else 1.0"],
        }
        for name in ("sign", "clamp", "sigmoid", "relu", "_count", "_add", "_fit_line"):
            if name in hs:
                for line in small[name]:
                    w(line)
                w()
                w()

    # --- curves (function plots and data tables) ---------------------------------------------------------------
    def curves(self, scalars, xs_name="xs", path="curves", required=True):
        """Check the curves; write their functions; return [(name, label parts, style, fill, show expr)]."""
        ctx = self.ctx
        raw = _list(ctx, path, self.spec.get("curves"), LIMITS["curves"])
        if required and not raw:
            ctx.add(path, "add at least one curve")
        names = []
        for n, c in enumerate(raw):
            nm = c.get("name") if isinstance(c, dict) else None
            names.append(nm.strip() if isinstance(nm, str) and NAME_RE.match(nm.strip() or "") else None)
        out = []
        for n, c in enumerate(raw):
            p = "%s.%d" % (path, n)
            if not isinstance(c, dict):
                ctx.add(p, "each curve has a name and an expression")
                continue
            name = _check_name(ctx, p + ".name", c.get("name") or ("y" + str(n + 1)), self.taken, "curve")
            if name:
                self.curve_names.add(name)
            e = ctx.expr(p + ".expr", c.get("expr"), scalars | {"x"}, local=("x",))
            style = _style(ctx, p + ".style", c.get("style"), ("main", "second", "third", "fourth", "muted")[min(n, 4)])
            label = ctx.template(p + ".label", c.get("label", name or ""), scalars)
            fill = (c.get("fill") or "").strip() if isinstance(c.get("fill"), str) else ""
            if fill and fill not in ("zero",) and fill not in [x for x in names if x]:
                s = _suggest(fill, set(x for x in names if x) | {"zero"})
                ctx.add(p + ".fill", "fill to 'zero' or to another curve's name%s" % ((" — did you mean '%s'?" % s) if s else ""))
            show = ctx.expr(p + ".show", c.get("show"), scalars, required=False)
            if name and e is not None:
                args = ["x"] + [a for a in e.names if a != "x"]
                self.note_calls(e)
                self.defs.append([
                    "def %s_at(%s):" % (name, ", ".join(args)),
                    '    """%s = %s"""' % (name, _comment(e.text).replace('"""', "'''").replace("\\", "\\\\")),
                    "    return %s" % e.code,
                ])
                out.append({"name": name, "args": args, "label": label, "style": style, "fill": fill, "show": show,
                            "expr": e})
        return out

    def curve_lines(self, curves, xs_name="xs"):
        """Inside compute(): one list of values per curve, then the series."""
        self.helpers.add("_value")
        for c in curves:
            self.body("%s = [_value(%s_at, %s) for x in %s]" % (c["name"], c["name"], ", ".join(c["args"]), xs_name), 1)
        self.body()
        self.body("series = []", 1)
        for c in curves:
            ind = 1
            if c["show"] is not None:
                self.body("if %s:   # shown when: %s" % (self.val(c["show"]), _comment(c["show"].text)), 1)
                ind = 2
            colour = c["style"].split()[0] if c["style"].split() and c["style"].split()[0] in STYLE_COLOURS else "main"
            if c["fill"] == "zero":
                self.body('series.append({"name": %s, "x": %s, "y": %s, "style": %s, "label_at": "none"})' % (
                    self.tmpl(c["label"]), xs_name, c["name"], _lit(colour + " area")), ind)
            elif c["fill"]:
                self.body('series.append({"name": %s, "x": %s, "y": %s, "base": %s, "style": %s, "label_at": "none"})' % (
                    self.tmpl(c["label"]), xs_name, c["name"], c["fill"], _lit(colour + " area")), ind)
            item = '{"name": %s, "x": %s, "y": %s, "style": %s}' % (self.tmpl(c["label"]), xs_name, c["name"], _lit(c["style"]))
            if not "".join(p for p in c["label"] if isinstance(p, str)).strip() and not any(not isinstance(p, str) for p in c["label"]):
                item = item[:-1] + ', "label_at": "none"}'
            self.body("series.append(%s)" % item, ind)

    def marks_and_points(self, scalars, arrays):
        ctx = self.ctx
        marks = []
        for n, m in enumerate(_list(ctx, "marks", self.spec.get("marks"), 12)):
            p = "marks.%d" % n
            if not isinstance(m, dict):
                continue
            axis = m.get("axis", "x")
            if axis not in ("x", "y"):
                ctx.add(p + ".axis", "a reference line is at an x (vertical) or a y (horizontal)")
                continue
            e = ctx.expr(p + ".expr", m.get("expr"), scalars, arrays, where_x="xs")
            label = ctx.template(p + ".label", m.get("label") or "", scalars, arrays, "xs")
            style = _style(ctx, p + ".style", m.get("style"), "muted")
            if e is not None:
                key = "value" if self.kind == "bars" else axis
                marks.append('{%s: %s, "label": %s, "style": %s}' % (_lit(key), self.val(e), self.tmpl(label), _lit(style)))
        pts = []
        for n, q in enumerate(_list(ctx, "points", self.spec.get("points"), 20)):
            p = "points.%d" % n
            if not isinstance(q, dict):
                continue
            ex = ctx.expr(p + ".x", q.get("x"), scalars, arrays, where_x="xs")
            ey = ctx.expr(p + ".y", q.get("y"), scalars, arrays, where_x="xs")
            label = ctx.template(p + ".label", q.get("label") or "", scalars, arrays, "xs")
            style = _style(ctx, p + ".style", q.get("style"), "highlight")
            if ex is not None and ey is not None:
                pts.append('{"type": "point", "x": %s, "y": %s, "label": %s, "style": %s}' % (
                    self.val(ex), self.val(ey), self.tmpl(label), _lit(style)))
        return marks, pts

    def axes_fields(self, kind="xy"):
        """x/y labels, fixed ranges and log scales from the form, as spec fields."""
        ctx, s = self.ctx, self.spec
        out = []
        for key in ("x_label", "y_label"):
            if s.get(key):
                out.append('"%s": %s' % (key, _lit(str(s[key]))))
        for key in ("y_min", "y_max"):
            v = _number(ctx, key, s.get(key), required=False)
            if v is not None:
                out.append('"%s": %s' % (key, _num_lit(v)))
        lo, hi = s.get("y_min"), s.get("y_max")
        try:
            if lo not in (None, "") and hi not in (None, "") and float(lo) >= float(hi):
                ctx.add("y_max", "the top of the y axis must be above its bottom")
        except (TypeError, ValueError):
            pass
        if kind == "xy":
            if s.get("x_log"):
                out.append('"x_log": True')
            if s.get("y_log"):
                out.append('"y_log": True')
            if s.get("grid"):
                out.append('"grid": "x"')
        return out

    def x_range(self, default=(0, 10)):
        ctx, s = self.ctx, self.spec
        lo = _number(ctx, "x_min", s.get("x_min", default[0]))
        hi = _number(ctx, "x_max", s.get("x_max", default[1]))
        n = _number(ctx, "samples", s.get("samples") or 200, integer=True)
        if lo is None or hi is None or n is None:
            raise _Stop()
        if not lo < hi:
            ctx.add("x_max", "x must run from a smaller to a larger number")
            raise _Stop()
        if s.get("x_log") and lo <= 0:
            ctx.add("x_min", "with a log x axis, x must start above 0")
            raise _Stop()
        if not 2 <= n <= LIMITS["samples"]:
            ctx.add("samples", "between 2 and %d points per curve" % LIMITS["samples"])
            raise _Stop()
        return lo, hi, n

    def panel_title(self, scalars, arrays=()):
        t = self.ctx.template("panel_title", self.spec.get("panel_title") or "", scalars, arrays)
        return ('"title": %s, ' % self.tmpl(t)) if t else ""

    def note_line(self, scalars, arrays=(), where_x=None):
        t = self.ctx.template("note", self.spec.get("note") or "", scalars, arrays, where_x)
        return self.tmpl(t) if t else None

    def ret(self, panel_lines, readouts, note=None, extra=None):
        b = self.body
        b("return {", 1)
        b('"panels": [{', 2)
        for line in panel_lines:
            b(line + ",", 3)
        b("}],", 2)
        if extra:
            for line in extra:
                b(line + ",", 2)
        if readouts:
            b('"readouts": [', 2)
            for r in readouts:
                b(r + ",", 3)
            b("],", 2)
        if note:
            b('"note": %s,' % note, 2)
        b("}", 1)

    # --- types -------------------------------------------------------------------------------------------------
    def type_function(self):
        ctx = self.ctx
        scalars = self.scalars()
        values = _values(ctx, self.spec, scalars, self.taken)
        lo, hi, n = self.x_range()
        curves = self.curves(scalars)
        arrays = set(self.curve_names)
        marks, pts = self.marks_and_points(scalars, arrays)
        readouts = _readouts(ctx, self.spec, scalars, arrays, "xs")
        axes = self.axes_fields()
        title = self.panel_title(scalars, arrays)
        note = self.note_line(scalars, arrays, "xs")
        if ctx.problems:
            raise _Stop()
        self.pre += ["# Where the curves are drawn: SAMPLES points from X_MIN to X_MAX.",
                     "X_MIN, X_MAX, SAMPLES = %s, %s, %d" % (_num_lit(lo), _num_lit(hi), n)]
        self.control_lines()
        self.values_lines(values)
        b = self.body
        if self.spec.get("x_log"):
            b("# x spaced evenly on a log scale", 1)
            b("xs = [X_MIN * (X_MAX / X_MIN) ** (n / (SAMPLES - 1)) for n in range(SAMPLES)]", 1)
        else:
            b("xs = [X_MIN + (X_MAX - X_MIN) * n / (SAMPLES - 1) for n in range(SAMPLES)]", 1)
        b("# each curve's value at every x (None where it is not defined, which leaves a gap)", 1)
        self.curve_lines(curves)
        b()
        panel = ['"kind": "xy"', '"series": series', '"x_min": X_MIN', '"x_max": X_MAX'] + axes
        if title:
            panel.insert(1, title.rstrip(", "))
        if marks:
            panel.append('"marks": [%s]' % ", ".join(marks))
        if pts:
            panel.append('"shapes": [%s]' % ", ".join(pts))
        self.ret(panel, self.readouts_code(readouts), note)

    def type_shapes(self):
        ctx, s = self.ctx, self.spec
        scalars = self.scalars()
        values = _values(ctx, s, scalars, self.taken)
        rng = {}
        for key, default in (("x_min", -5), ("x_max", 5), ("y_min", -5), ("y_max", 5)):
            rng[key] = _number(ctx, key, s.get(key, default))
        if None not in rng.values():
            if rng["x_min"] >= rng["x_max"]:
                ctx.add("x_max", "x must run from a smaller to a larger number")
            if rng["y_min"] >= rng["y_max"]:
                ctx.add("y_max", "y must run from a smaller to a larger number")
        items = _list(ctx, "items", s.get("items"), LIMITS["items"])
        if not items:
            ctx.add("items", "add at least one shape")
        fields = {"point": ("x", "y"), "line": ("x1", "y1", "x2", "y2"), "arrow": ("x1", "y1", "x2", "y2"),
                  "circle": ("x", "y", "r"), "rect": ("x", "y", "w", "h"), "text": ("x", "y"), "curve": ("x", "y"),
                  "polygon": ()}
        code = []
        for n, it in enumerate(items):
            p = "items.%d" % n
            if not isinstance(it, dict):
                ctx.add(p, "each shape is a small form")
                continue
            t = it.get("type")
            if t not in fields:
                ctx.add(p + ".type", "a shape is one of: %s" % ", ".join(fields))
                continue
            here = set(scalars)
            rep = None
            if it.get("repeat") not in (None, ""):
                rep = ctx.expr(p + ".repeat", it.get("repeat"), scalars)
                here.add("k")
            if t == "curve":
                here_t = here | {"t"}
                ex = ctx.expr(p + ".x", it.get("x"), here_t, local=("t",))
                ey = ctx.expr(p + ".y", it.get("y"), here_t, local=("t",))
                t0 = ctx.expr(p + ".t_min", it.get("t_min", "0"), here)
                t1 = ctx.expr(p + ".t_max", it.get("t_max", "2*pi"), here)
                ns = _number(ctx, p + ".samples", it.get("samples") or 120, integer=True)
                if ns is not None and not 2 <= ns <= 400:
                    ctx.add(p + ".samples", "between 2 and 400 points")
                parts = [ex, ey, t0, t1]
            elif t == "polygon":
                pts_text = it.get("points") or ""
                pairs = _split_points(pts_text) if isinstance(pts_text, str) else pts_text
                parsed = []
                if not isinstance(pairs, list) or len(pairs) < 3:
                    ctx.add(p + ".points", "a polygon needs three or more corners, one per line: x, y")
                else:
                    for m, pr in enumerate(pairs):
                        if not isinstance(pr, (list, tuple)) or len(pr) != 2:
                            ctx.add(p + ".points", "corner %d: write x, y (two expressions separated by a comma)" % (m + 1))
                            continue
                        a = ctx.expr(p + ".points", pr[0], here)
                        b2 = ctx.expr(p + ".points", pr[1], here)
                        parsed.append((a, b2))
                parts = [x for pr in parsed for x in pr]
            else:
                parts = [ctx.expr("%s.%s" % (p, f), it.get(f), here) for f in fields[t]]
            label = ctx.template(p + ".label", it.get("label") or it.get("text") or "", here)
            style = _style(ctx, p + ".style", it.get("style"), "main")
            if t == "text" and not label:
                ctx.add(p + ".label", "write the text to show")
            if any(x is None for x in parts):
                continue
            code.append((t, it, parts, label, style, rep))
        readouts = _readouts(ctx, s, scalars, set(), None)
        note = self.note_line(scalars)
        title = self.panel_title(scalars)
        if ctx.problems:
            raise _Stop()
        self.control_lines()
        self.values_lines(values)
        b = self.body
        self.helpers.add("_add")
        b("shapes = []", 1)
        for t, it, parts, label, style, rep in code:
            ind = 1
            if rep is not None:
                self.helpers.add("_count")
                b("for k in range(_count(%s, %d)):   # repeated: k = 0, 1, 2 …" % (self.val(rep), LIMITS["repeat"]), 1)
                ind = 2
            lab = self.tmpl(label) if label else None
            if t == "curve":
                ex, ey, t0, t1 = parts
                ns = int(it.get("samples") or 120)
                self.note_calls(ex)
                self.note_calls(ey)
                b("t0, t1 = %s, %s" % (self.val(t0), self.val(t1)), ind)
                b("if t0 is not None and t1 is not None:", ind)
                b("ts = [t0 + (t1 - t0) * n / %d for n in range(%d)]" % (ns - 1, ns), ind + 1)
                b("pts = [[_value(lambda: %s), _value(lambda: %s)] for t in ts]   # x(t), y(t)" % (ex.code, ey.code), ind + 1)
                b('shapes.append({"type": "line", "points": pts, "style": %s%s})' % (
                    _lit(style), (', "label": %s' % lab) if lab else ""), ind + 1)
            elif t == "polygon":
                corners = ", ".join("[%s, %s]" % (self.val(parts[m]), self.val(parts[m + 1])) for m in range(0, len(parts), 2))
                b("corners = [%s]" % corners, ind)
                b("if all(None not in c for c in corners):", ind)
                b('shapes.append({"type": "polygon", "points": corners, "style": %s%s})' % (
                    _lit(style), (', "label": %s' % lab) if lab else ""), ind + 1)
            else:
                fs = fields[t]
                kv = ", ".join('"%s": %s' % (f, self.val(e)) for f, e in zip(fs, parts))
                extra = ""
                if t == "text":
                    extra = ', "text": %s' % lab
                elif lab:
                    extra = ', "label": %s' % lab
                b('_add(shapes, {"type": "%s", %s, "style": %s%s}, %s)' % (t, kv, _lit(style), extra, _lit(list(fs))), ind)
        b()
        panel = ['"kind": "scene"', '"shapes": shapes'] + ['"%s": %s' % (k, _num_lit(v)) for k, v in rng.items()]
        if title:
            panel.insert(1, title.rstrip(", "))
        panel.append('"equal": %s' % ("False" if s.get("equal") is False else "True"))
        for key in ("axes", "grid", "origin"):
            if s.get(key):
                panel.append('"%s": True' % key)
        for key in ("x_label", "y_label"):
            if s.get(key):
                panel.append('"%s": %s' % (key, _lit(str(s[key]))))
        self.ret(panel, self.readouts_code(readouts), note)

    def type_bars(self):
        ctx, s = self.ctx, self.spec
        scalars = self.scalars()
        values = _values(ctx, s, scalars, self.taken)
        items = _list(ctx, "bars", s.get("bars"), 40)
        if not items:
            ctx.add("bars", "add at least one bar")
        rows = []
        for n, it in enumerate(items):
            p = "bars.%d" % n
            if not isinstance(it, dict):
                continue
            here = set(scalars)
            rep = None
            if it.get("repeat") not in (None, ""):
                rep = ctx.expr(p + ".repeat", it.get("repeat"), scalars)
                here.add("k")
            e = ctx.expr(p + ".expr", it.get("expr"), here)
            label = ctx.template(p + ".label", it.get("label") or "", here)
            style = _style(ctx, p + ".style", it.get("style"), "main")
            if e is not None:
                rows.append((e, label, style, rep))
        hl = s.get("highlight") or ""
        if hl not in ("", "max", "min"):
            ctx.add("highlight", "highlight the largest (max), the smallest (min), or none")
        dec = s.get("decimals")
        show = bool(s.get("show_values", True))
        if dec in (None, ""):
            dec = None
        else:
            dec = _number(ctx, "decimals", dec, integer=True)
        readouts = _readouts(ctx, s, scalars, {"bars"}, None)
        axes = self.axes_fields("bars")
        marks, _pts = self.marks_and_points(scalars, {"bars"})
        note = self.note_line(scalars, {"bars"})
        title = self.panel_title(scalars, {"bars"})
        if ctx.problems:
            raise _Stop()
        self.control_lines()
        self.values_lines(values)
        b = self.body
        self.helpers.add("_value")
        b("bar_list = []   # (label, value, style)", 1)
        for e, label, style, rep in rows:
            ind = 1
            if rep is not None:
                self.helpers.add("_count")
                b("for k in range(_count(%s, %d)):   # repeated: k = 0, 1, 2 …" % (self.val(rep), LIMITS["repeat"]), 1)
                ind = 2
            b("bar_list.append((%s, %s, %s))   # %s" % (self.tmpl(label), self.val(e), _lit(style), _comment(e.text)), ind)
        b("bars = [v for _, v, _ in bar_list]", 1)
        if hl:
            b("known = [v for v in bars if v is not None]", 1)
            b("pick = %s(known) if known else None   # the bar to highlight" % hl, 1)
        self.helpers.add("_fmt")
        style_code = ('"highlight" if v is not None and v == pick else st' if hl else "st")
        note_code = (', "note": _fmt(v%s)' % ((", %d" % dec) if dec is not None else "")) if show else ""
        b('bar_dicts = [{"label": lab, "value": v, "style": %s%s} for lab, v, st in bar_list]' % (style_code, note_code), 1)
        b()
        panel = ['"kind": "bars"', '"bars": bar_dicts'] + axes
        if title:
            panel.insert(1, title.rstrip(", "))
        if s.get("horizontal"):
            panel.append('"horizontal": True')
        if marks:
            panel.append('"marks": [%s]' % ", ".join(marks))
        self.ret(panel, self.readouts_code(readouts), note)

    def type_heatmap(self):
        ctx, s = self.ctx, self.spec
        scalars = self.scalars()
        values = _values(ctx, s, scalars, self.taken)
        er = ctx.expr("rows", s.get("rows", 8), scalars)
        ec = ctx.expr("cols", s.get("cols", 8), scalars)
        e = ctx.expr("expr", s.get("expr"), scalars | {"i", "j"}, local=("i", "j"))
        rlab = s.get("row_labels") or ""
        clab = s.get("col_labels") or ""
        rparts = ctx.template("row_labels", rlab, scalars | {"i"}) if "{" in rlab else None
        cparts = ctx.template("col_labels", clab, scalars | {"j"}) if "{" in clab else None
        lo = _number(ctx, "range_min", s.get("range_min"), required=False)
        hi = _number(ctx, "range_max", s.get("range_max"), required=False)
        if (lo is None) != (hi is None):
            ctx.add("range_max" if hi is None else "range_min", "give both ends of the colour range, or neither")
        elif lo is not None and lo >= hi:
            ctx.add("range_max", "the top of the colour range must be above its bottom")
        dec = s.get("decimals")
        dec = None if dec in (None, "") else _number(ctx, "decimals", dec, integer=True)
        readouts = _readouts(ctx, s, scalars, {"cells"}, None)
        note = self.note_line(scalars, {"cells"})
        title = self.panel_title(scalars, {"cells"})
        if ctx.problems:
            raise _Stop()
        args = ["i", "j"] + [a for a in e.names if a not in ("i", "j")]
        self.note_calls(e)
        self.defs.append(["def cell_at(%s):" % ", ".join(args),
                          '    """The value of the cell in row i, column j (both counted from 0): %s"""'
                          % _comment(e.text).replace('"""', "'''").replace("\\", "\\\\"),
                          "    return %s" % e.code])
        self.control_lines()
        self.values_lines(values)
        b = self.body
        self.helpers |= {"_value", "_count"}
        b("rows = _count(%s, %d)" % (self.val(er), LIMITS["grid"]), 1)
        b("cols = _count(%s, %d)" % (self.val(ec), LIMITS["grid"]), 1)
        b("if rows == 0 or cols == 0:", 1)
        b("rows, cols = max(rows, 1), max(cols, 1)", 2)
        b("matrix = [[_value(cell_at, %s) for j in range(cols)] for i in range(rows)]" % ", ".join(args), 1)
        b("cells = [v for row in matrix for v in row]", 1)
        panel = ['"kind": "heatmap"', '"matrix": matrix']
        if title:
            panel.insert(1, title.rstrip(", "))

        def labels(text, parts, var, count):
            if parts is not None:
                return "[%s for %s in range(%s)]" % (self.tmpl(parts), var, count)
            items = [x.strip() for x in text.split(",")] if text.strip() else []
            if not items:
                return None
            return "(%s + [\"\"] * %s)[:%s]" % (_lit(items), count, count)

        rl = labels(rlab, rparts, "i", "rows")
        cl = labels(clab, cparts, "j", "cols")
        if rl:
            b("row_labels = %s" % rl, 1)
            panel.append('"row_labels": row_labels')
        if cl:
            b("col_labels = %s" % cl, 1)
            panel.append('"col_labels": col_labels')
        b()
        if lo is not None:
            panel.append('"range": [%s, %s]' % (_num_lit(lo), _num_lit(hi)))
        if s.get("show_values"):
            panel.append('"show_values": True')
        if dec is not None:
            panel.append('"decimals": %d' % dec)
        for key in ("x_label", "legend"):
            if s.get(key):
                panel.append('"%s": %s' % (key, _lit(str(s[key]))))
        self.ret(panel, self.readouts_code(readouts), note)

    def type_distribution(self):
        ctx, s = self.ctx, self.spec
        fam_name = s.get("family") or "normal"
        fam = FAMILIES.get(fam_name)
        if fam is None:
            ctx.add("family", "pick one of: %s" % ", ".join(FAMILIES))
            raise _Stop()
        params = [c for c in self.controls if c["name"] in fam["params"]]
        interval = s.get("interval") if isinstance(s.get("interval"), dict) else {}
        mode = interval.get("mode") or "none"
        scalars = self.scalars() | {"mean", "variance", "std"}
        values = _values(ctx, s, scalars, self.taken)
        lo_e = hi_e = None
        if mode == "range":
            lo_e = ctx.expr("interval.lo", interval.get("lo"), scalars)
            hi_e = ctx.expr("interval.hi", interval.get("hi"), scalars)
        elif mode not in ("none", "sigma", ""):
            ctx.add("interval.mode", "shade nothing, ± some standard deviations, or a range")
        rscalars = scalars | ({"prob"} if mode in ("sigma", "range") else set())
        readouts = _readouts(ctx, s, rscalars, set(), None)
        note = self.note_line(rscalars)
        if ctx.problems:
            raise _Stop()
        b = self.body
        disc = fam["discrete"]
        P = {c["name"]: c for c in params}
        # the x range: wide enough for every slider position, unless the form sets it
        if disc:
            if fam_name == "binomial":
                kmax = int(P["n"]["max"])
            else:
                lmax = float(P["lam"]["max"])
                kmax = int(math.ceil(lmax + 4 * math.sqrt(lmax) + 2))
            x_lo, x_hi = -0.5, kmax + 0.5
        elif fam_name == "normal":
            m0, m1, sd = float(P["mu"]["min"]), float(P["mu"]["max"]), float(P["sigma"]["max"])
            x_lo, x_hi = m0 - 3 * sd, m1 + 3 * sd
        elif fam_name == "uniform":
            x_lo = min(float(P["a"]["min"]), float(P["b"]["min"])) - 1
            x_hi = max(float(P["a"]["max"]), float(P["b"]["max"])) + 1
        else:
            x_lo, x_hi = 0.0, 5.0 / float(P["rate"]["min"]) if float(P["rate"]["min"]) > 0 else 10.0
            x_hi = min(x_hi, 60.0)
        if s.get("x_min") not in (None, ""):
            v = _number(ctx, "x_min", s.get("x_min"))
            x_lo = v if v is not None else x_lo
        if s.get("x_max") not in (None, ""):
            v = _number(ctx, "x_max", s.get("x_max"))
            x_hi = v if v is not None else x_hi
        if x_lo >= x_hi:
            ctx.add("x_max", "x must run from a smaller to a larger number")
            raise _Stop()
        if not disc:
            x_lo, x_hi = _round_nice(x_lo), _round_nice(x_hi, up=True)
        if disc:
            self.pre += ["# The values the variable can take: 0, 1, 2 … K_MAX (wide enough for every slider position).",
                         "K_MAX = %d" % kmax]
        else:
            self.pre += ["# Where the curve is drawn (wide enough for every slider position).",
                         "X_MIN, X_MAX, SAMPLES = %s, %s, 241" % (_num_lit(x_lo), _num_lit(x_hi))]
        self.defs += _family_defs(fam_name)
        self.control_lines()
        b("mean, variance = moments(%s)" % ", ".join(P), 1)
        b("std = math.sqrt(variance)", 1)
        self.values_lines(values)
        self.helpers |= {"_value", "_fmt"}
        cum = bool(s.get("cdf_toggle"))
        if disc:
            b("ks = list(range(K_MAX + 1))", 1)
            b("probs = [pmf(k, %s) for k in ks]" % ", ".join(P), 1)
            if cum:
                b("if show == 1:   # cumulative: the chance of k or less", 1)
                b("running, cumulative = 0.0, []", 2)
                b("for v in probs:", 2)
                b("running += v", 3)
                b("cumulative.append(min(running, 1.0))", 3)
                b("heights = cumulative", 2)
                b("else:", 1)
                b("heights = probs", 2)
            else:
                b("heights = probs", 1)
        else:
            b("xs = [X_MIN + (X_MAX - X_MIN) * n / (SAMPLES - 1) for n in range(SAMPLES)]", 1)
            if fam_name == "uniform":
                b("# the exact ends, so the jumps are drawn straight up", 1)
                b("ends = [min(a, b), max(a, b)]", 1)
                b("xs = sorted(set(xs + [v for v in ends if X_MIN < v < X_MAX] + [v - 1e-9 for v in ends if X_MIN < v < X_MAX]))", 1)
            if cum:
                b("if show == 1:   # cumulative: the chance of a value at most x", 1)
                b("heights = [cdf(x, %s) for x in xs]" % ", ".join(P), 2)
                b("else:", 1)
                b("heights = [pdf(x, %s) for x in xs]" % ", ".join(P), 2)
            else:
                b("heights = [pdf(x, %s) for x in xs]" % ", ".join(P), 1)
        # the shaded band
        if mode in ("sigma", "range"):
            if mode == "sigma":
                b("lo, hi = mean - width * std, mean + width * std   # the shaded band", 1)
            else:
                b("lo, hi = %s, %s   # the shaded band" % (self.val(lo_e), self.val(hi_e)), 1)
                b("if lo is not None and hi is not None and lo > hi:", 1)
                b("lo, hi = hi, lo", 2)
            if disc:
                b("prob = sum(v for k, v in zip(ks, probs) if lo is not None and hi is not None and lo <= k <= hi)", 1)
            else:
                b("prob = (cdf(hi, %s) - cdf(lo, %s)) if lo is not None and hi is not None else None" % (
                    ", ".join(P), ", ".join(P)), 1)
        b()
        if disc:
            b('series = [{"name": "probability", "x": ks, "y": heights, "style": "main stems", "sizes": [4] * len(ks)}]', 1)
            if mode in ("sigma", "range"):
                b("inside = [h if lo is not None and hi is not None and lo <= k <= hi else None for k, h in zip(ks, heights)]", 1)
                b('series.append({"name": "in the band", "x": ks, "y": inside, "style": "highlight stems", "sizes": [5] * len(ks)})', 1)
            ylab = "probability"
        else:
            b('series = [{"name": "density", "x": xs, "y": heights, "style": "main", "label_at": "none"}]', 1)
            if mode in ("sigma", "range"):
                b("if lo is not None and hi is not None:", 1)
                b("band_x = [lo] + [x for x in xs if lo < x < hi] + [hi]", 2)
                fn = "cdf" if cum else "pdf"
                if cum:
                    b("band_y = [(cdf(x, %s) if show == 1 else pdf(x, %s)) for x in band_x]" % (", ".join(P), ", ".join(P)), 2)
                else:
                    b("band_y = [%s(x, %s) for x in band_x]" % (fn, ", ".join(P)), 2)
                b('series.insert(0, {"name": "band", "x": band_x, "y": band_y, "style": "main area", "label_at": "none"})', 2)
            ylab = "probability density"
        if cum:
            b('y_label = "chance of at most this value" if show == 1 else %s' % _lit(ylab), 1)
        else:
            b("y_label = %s" % _lit(s.get("y_label") or ylab), 1)
        panel = ['"kind": "xy"', '"series": series', '"y_min": 0', '"y_label": y_label',
                 '"x_label": %s' % _lit(s.get("x_label") or ("k" if disc else "x"))]
        if disc:
            panel += ['"x_min": -0.5', '"x_max": K_MAX + 0.5']
        else:
            panel += ['"x_min": X_MIN', '"x_max": X_MAX']
        panel.append('"marks": [{"x": mean, "label": "mean", "style": "muted"}]')
        if s.get("y_max") not in (None, ""):
            v = _number(ctx, "y_max", s.get("y_max"))
            if v is not None:
                panel.append('"y_max": %s' % ("1 if show == 1 else %s" % _num_lit(v) if cum else _num_lit(v)))
        ro = []
        if s.get("show_moments", True):
            ro += ['{"label": "Mean", "value": _fmt(mean, 2)}',
                   '{"label": "Variance", "value": _fmt(variance, 2)}',
                   '{"label": "Standard deviation", "value": _fmt(std, 2)}']
        if mode in ("sigma", "range"):
            ro.append('{"label": "Chance of the band", "value": _fmt(None if prob is None else 100 * prob, 1) + "%", '
                      '"note": "from " + _fmt(lo, 2) + " to " + _fmt(hi, 2)}')
        ro += self.readouts_code(readouts)
        self.ret(panel, ro, note)

    def type_data(self):
        ctx, s = self.ctx, self.spec
        table = parse_csv(ctx, s.get("csv"))
        if table is None:
            raise _Stop()
        headers, ids, cols = table
        chart = s.get("chart") or "line"
        if chart not in ("line", "scatter", "bar"):
            ctx.add("chart", "draw the table as a line, dots (scatter) or bars")
            raise _Stop()
        lookup = {}
        for h, i in zip(headers, ids):
            for key in (i, h, h.lower(), re.sub(r"[^a-z0-9]+", "_", h.lower()).strip("_")):
                lookup.setdefault(key, i)
        xcol = s.get("x") or ids[0]
        xcol = lookup.get(xcol, lookup.get(str(xcol).lower(), xcol))
        if xcol not in ids:
            sug = _suggest(str(xcol), set(ids))
            ctx.add("x", "no column '%s'%s. Columns: %s" % (xcol, (" — did you mean '%s'?" % sug) if sug else "",
                                                             ", ".join(ids)))
            raise _Stop()
        ycols = s.get("y") or [c for c in ids if c != xcol][:1]
        if isinstance(ycols, str):
            ycols = [ycols]
        ycols = [lookup.get(c, lookup.get(str(c).lower(), c)) for c in ycols]
        for yc in ycols:
            if yc not in ids:
                sug = _suggest(str(yc), set(ids))
                ctx.add("y", "no column '%s'%s" % (yc, (" — did you mean '%s'?" % sug) if sug else ""))
        if not ycols:
            ctx.add("y", "pick at least one column to draw")
        if ctx.problems:
            raise _Stop()
        numeric = {c: all(v is None or isinstance(v, (int, float)) for v in cols[c]) for c in ids}
        for yc in ycols:
            if not numeric[yc]:
                bad = next(n for n, v in enumerate(cols[yc]) if isinstance(v, str))
                ctx.add("y", "column '%s' has text in row %d (%r): only numbers can be drawn" % (
                    headers[ids.index(yc)], bad + 2, cols[yc][bad]))
        if chart != "bar" and not numeric[xcol]:
            bad = next(n for n, v in enumerate(cols[xcol]) if isinstance(v, str))
            ctx.add("x", "column '%s' has text in row %d (%r): a line or scatter needs numbers across; use bars "
                    "for labels" % (headers[ids.index(xcol)], bad + 2, cols[xcol][bad]))
        if chart == "bar" and len(ycols) > 1:
            ctx.add("y", "a bar chart shows one column; pick one, or draw lines")
        fit = s.get("fit") or "none"
        if fit not in ("none", "line"):
            ctx.add("fit", "the fitted line is 'line' or 'none'")
        if fit == "line" and chart == "bar":
            ctx.add("fit", "a fitted line needs numbers across: draw lines or dots")
        if ctx.problems:
            raise _Stop()
        self.taken |= set(ids)
        scalars = self.scalars()
        arrays = set(ids)
        if fit == "line":
            scalars |= {"slope", "intercept", "r2"}
        values = _values(ctx, s, scalars, self.taken, arrays)
        curves = self.curves(scalars, xs_name="curve_xs", required=False) if chart != "bar" else []
        arrays |= set(self.curve_names)
        readouts = _readouts(ctx, s, scalars, arrays, xcol)
        note = self.note_line(scalars, arrays, xcol)
        title = self.panel_title(scalars, arrays)
        axes = self.axes_fields("xy" if chart != "bar" else "bars")
        if ctx.problems:
            raise _Stop()
        self.pre.append("# The table as pasted (an empty cell is None). The keys are the column names.")
        self.pre.append("DATA = {")
        for c in ids:
            self.pre.append("    %s: %s," % (_lit(c), _lit(cols[c])))
        self.pre.append("}")
        if any(h != i for h, i in zip(headers, ids)):
            self.pre.append("HEADERS = %s   # the column titles as written" % _lit(dict(zip(ids, headers))))
        self.control_lines()
        b = self.body
        for c in ids:
            b('%s = DATA[%s]' % (c, _lit(c)), 1)
        if fit == "line":
            self.helpers.add("_fit_line")
            b("slope, intercept, r2 = _fit_line(%s, %s)   # the least-squares line" % (xcol, ycols[0]), 1)
        self.values_lines(values)
        label_of = dict(zip(ids, headers))
        styles = ("main", "second", "third", "fourth")
        if chart == "bar":
            self.helpers.add("_fmt")
            b("bar_dicts = [{\"label\": %s, \"value\": v, \"style\": \"main\", \"note\": _fmt(v)} for lab, v in zip(%s, %s)]" % (
                "_fmt(lab) if not isinstance(lab, str) else lab", xcol, ycols[0]), 1)
            panel = ['"kind": "bars"', '"bars": bar_dicts']
            if not s.get("y_label"):
                panel.append('"y_label": %s' % _lit(label_of[ycols[0]]))
            if not s.get("x_label"):
                panel.append('"x_label": %s' % _lit(label_of[xcol]))
            panel += axes
        else:
            b("series = []", 1)
            for n, yc in enumerate(ycols):
                style = styles[n % 4] + (" points" if chart == "scatter" else "")
                b('series.append({"name": %s, "x": %s, "y": %s, "style": %s})' % (
                    _lit(label_of[yc]), xcol, yc, _lit(style)), 1)
            if fit == "line":
                cond = "slope is not None" + (" and fit == 1" if s.get("fit_toggle") else "")
                b("if %s:" % cond, 1)
                b("ends = [min(v for v in %s if v is not None), max(v for v in %s if v is not None)]" % (xcol, xcol), 2)
                b('series.append({"name": "fitted line", "x": ends, "y": [slope * v + intercept for v in ends], '
                  '"style": "muted dashed"})', 2)
            if curves:
                b("known_x = [v for v in %s if v is not None]" % xcol, 1)
                b("curve_xs = [min(known_x) + (max(known_x) - min(known_x)) * n / 199 for n in range(200)]", 1)
                self.curve_lines(curves, "curve_xs")
            panel = ['"kind": "xy"', '"series": series']
            if not s.get("x_label"):
                panel.append('"x_label": %s' % _lit(label_of[xcol]))
            if not s.get("y_label") and len(ycols) == 1:
                panel.append('"y_label": %s' % _lit(label_of[ycols[0]]))
            panel += axes
        if title:
            panel.insert(1, title.rstrip(", "))
        b()
        ro = []
        if fit == "line" and s.get("show_fit", True):
            self.helpers.add("_fmt")
            ro += ['{"label": "Slope", "value": _fmt(slope, 3)}', '{"label": "Intercept", "value": _fmt(intercept, 3)}',
                   '{"label": "R²", "value": _fmt(r2, 3), "note": "share of the spread the line explains"}']
        ro += self.readouts_code(readouts)
        self.ret(panel, ro, note)


def _round_nice(v, up=False):
    """Round an axis end outward to a whole number (or to 0.5 for short ranges)."""
    step = 1.0 if abs(v) >= 3 else 0.5
    v = (math.ceil(v / step - 1e-9) if up else math.floor(v / step + 1e-9)) * step
    return int(v) if float(v).is_integer() else v


def _family_defs(name):
    """The probability formulas, written into the figure file (standard library only)."""
    if name == "normal":
        return [["def pdf(x, mu, sigma):", '    """The bell curve\'s height at x."""',
                 "    z = (x - mu) / sigma", "    return math.exp(-0.5 * z * z) / (sigma * math.sqrt(2 * math.pi))"],
                ["def cdf(x, mu, sigma):", '    """The chance of a value at most x."""',
                 "    return 0.5 * (1 + math.erf((x - mu) / (sigma * math.sqrt(2))))"],
                ["def moments(mu, sigma):", '    """Mean and variance."""', "    return mu, sigma * sigma"]]
    if name == "uniform":
        return [["def pdf(x, a, b):", '    """Flat between the two ends, zero outside."""',
                 "    lo, hi = min(a, b), max(a, b)", "    if hi - lo < 1e-12:", "        return 0.0",
                 "    return 1 / (hi - lo) if lo <= x <= hi else 0.0"],
                ["def cdf(x, a, b):", "    lo, hi = min(a, b), max(a, b)", "    if x <= lo:", "        return 0.0",
                 "    if x >= hi or hi - lo < 1e-12:", "        return 1.0", "    return (x - lo) / (hi - lo)"],
                ["def moments(a, b):", "    return (a + b) / 2, (b - a) ** 2 / 12"]]
    if name == "exponential":
        return [["def pdf(x, rate):", '    """Waiting times: rate · e^(−rate·x) for x ≥ 0."""',
                 "    return rate * math.exp(-rate * x) if x >= 0 else 0.0"],
                ["def cdf(x, rate):", "    return 1 - math.exp(-rate * x) if x >= 0 else 0.0"],
                ["def moments(rate):", "    return 1 / rate, 1 / rate ** 2"]]
    if name == "binomial":
        return [["def pmf(k, n, p):", '    """The chance of exactly k successes in n tries."""',
                 "    n = int(round(n))", "    if k > n:", "        return 0.0",
                 "    return math.comb(n, k) * p ** k * (1 - p) ** (n - k)"],
                ["def moments(n, p):", "    return n * p, n * p * (1 - p)"]]
    return [["def pmf(k, lam):", '    """The chance of exactly k events when lam are expected (worked out with logs, so it never overflows)."""',
             "    return math.exp(k * math.log(lam) - lam - math.lgamma(k + 1))"],
            ["def moments(lam):", "    return lam, lam"]]


def _split_points(text):
    """'1, 2\\n3, max(a, b)' -> [['1', '2'], ['3', 'max(a, b)']] (commas inside brackets are kept)."""
    out = []
    for line in str(text).replace(";", "\n").splitlines():
        if not line.strip():
            continue
        parts, depth, cur = [], 0, ""
        for ch in line:
            if ch in "([":
                depth += 1
            elif ch in ")]":
                depth -= 1
            if ch == "," and depth == 0:
                parts.append(cur.strip())
                cur = ""
            else:
                cur += ch
        parts.append(cur.strip())
        out.append(parts)
    return out


def _ident(text, taken):
    s = re.sub(r"[^a-z0-9]+", "_", str(text).strip().lower()).strip("_") or "column"
    if not s[0].isalpha():
        s = "c_" + s
    s = s[:28]
    if s in RESERVED or s in _MODULE:
        s = s + "_col"
    base, n = s, 2
    while s in taken:
        s = "%s_%d" % (base, n)
        n += 1
    taken.add(s)
    return s


def parse_csv(ctx, text):
    """(headers, column names, {name: values}) from pasted CSV (commas, semicolons or tabs)."""
    if not isinstance(text, str) or not text.strip():
        ctx.add("csv", "paste a table here: a first line of column names, then one row per line")
        return None
    if len(text) > LIMITS["csv"]:
        ctx.add("csv", "the table is too large (at most %d characters)" % LIMITS["csv"])
        return None
    sample = text[:2000]
    delim = "\t" if "\t" in sample else (";" if sample.count(";") > sample.count(",") else ",")
    rows = [r for r in csv.reader(io.StringIO(text.strip()), delimiter=delim) if any(c.strip() for c in r)]
    if len(rows) < 2:
        ctx.add("csv", "the table needs a line of column names and at least one row of values")
        return None
    headers = [h.strip() or "column %d" % (n + 1) for n, h in enumerate(rows[0])]
    if len(headers) > LIMITS["columns"]:
        ctx.add("csv", "at most %d columns" % LIMITS["columns"])
        return None
    if len(rows) - 1 > LIMITS["rows"]:
        ctx.add("csv", "at most %d rows" % LIMITS["rows"])
        return None
    taken = set()
    ids = [_ident(h, taken) for h in headers]
    cols = {i: [] for i in ids}
    for rn, row in enumerate(rows[1:]):
        if len(row) > len(headers):
            ctx.add("csv", "row %d has %d cells but there are %d column names" % (rn + 2, len(row), len(headers)))
            return None
        for n, c in enumerate(ids):
            cell = row[n].strip() if n < len(row) else ""
            if cell == "" or cell.lower() in ("na", "nan", "null", "-", "—"):
                cols[c].append(None)
                continue
            try:
                v = float(cell.replace(",", "") if delim != "," else cell)
                cols[c].append(int(v) if v.is_integer() and abs(v) < 1e15 and "." not in cell and "e" not in cell.lower() else v)
            except ValueError:
                cols[c].append(cell)
    return headers, ids, cols


# ==============================================================================================================
# round trip

def _digest(body):
    return hashlib.sha1(body.encode("utf-8")).hexdigest()[:16]


def clean_spec(spec):
    """The spec as stored in the file: JSON-safe, without empty optional fields."""
    def clean(v):
        if isinstance(v, dict):
            return {str(k): clean(x) for k, x in v.items() if x not in (None, "", [], {})}
        if isinstance(v, list):
            return [clean(x) for x in v]
        if isinstance(v, float) and v.is_integer():
            return int(v)
        return v
    out = clean(spec)
    out.pop("name", None)
    return out


def read_spec(source):
    """None when the file was not made with the builder; else {"spec", "edited"} (edited: changed by hand)."""
    if not isinstance(source, str):
        return None
    idx = source.rfind("\n" + MARK)
    if idx < 0:
        if source.startswith(MARK):
            idx = -1
        else:
            return None
    line_start = idx + 1
    line_end = source.find("\n", line_start)
    line = source[line_start: line_end if line_end >= 0 else len(source)]
    try:
        data = json.loads(line[len(MARK):])
    except ValueError:
        return None
    if not isinstance(data, dict) or not isinstance(data.get("spec"), dict):
        return None
    head = source[:line_start]
    # the comment block written before the marker is part of the generated tail, not the body
    tail_at = head.rfind("\n# " + "-" * 110 + "\n")
    body = head[:tail_at] if tail_at >= 0 else head
    rest = source[line_end + 1:] if line_end >= 0 else ""
    edited = _digest(body) != data.get("hash") or bool(rest.strip())
    return {"spec": data["spec"], "edited": edited, "version": data.get("v")}


# ==============================================================================================================
# examples and the description for the Studio's form

def default_spec(kind="function"):
    """A small working example of each type: what the form starts from."""
    if kind == "function":
        return {"type": "function", "title": "A damped wave",
                "caption": "Change the frequency and the damping and watch the envelope hold the wave in.",
                "controls": [
                    {"name": "a", "kind": "slider", "label": "Amplitude", "min": 0, "max": 2, "step": 0.1, "value": 1},
                    {"name": "f", "kind": "slider", "label": "Frequency", "min": 0.5, "max": 6, "step": 0.1, "value": 2},
                    {"name": "d", "kind": "slider", "label": "Damping", "min": 0, "max": 1, "step": 0.02, "value": 0.3}],
                "curves": [
                    {"name": "wave", "label": "wave", "expr": "a*sin(f*x)*exp(-d*x)", "style": "main"},
                    {"name": "envelope", "label": "envelope", "expr": "a*exp(-d*x)", "style": "muted dashed"}],
                "x_min": 0, "x_max": 10, "y_min": -2, "y_max": 2, "x_label": "time", "y_label": "height",
                "readouts": [{"label": "Highest point", "expr": "max(wave)", "decimals": 2},
                             {"label": "Period", "expr": "2*pi/f", "decimals": 2}],
                "presets": [{"label": "No damping", "values": {"d": 0}}]}
    if kind == "shapes":
        return {"type": "shapes", "title": "A point going round a circle",
                "caption": "Move the angle: the point's height is the sine of the angle, its distance across the cosine.",
                "controls": [{"name": "angle", "kind": "slider", "label": "Angle (degrees)", "min": 0, "max": 360,
                              "step": 1, "value": 40, "play": True}],
                "values": [{"name": "a", "expr": "radians(angle)"}],
                "items": [
                    {"type": "curve", "x": "cos(t)", "y": "sin(t)", "t_min": "0", "t_max": "2*pi", "style": "muted"},
                    {"type": "line", "x1": "0", "y1": "0", "x2": "cos(a)", "y2": "sin(a)", "style": "main"},
                    {"type": "line", "x1": "cos(a)", "y1": "0", "x2": "cos(a)", "y2": "sin(a)", "style": "second dashed",
                     "label": "sin = {sin(a):.2f}"},
                    {"type": "point", "x": "cos(a)", "y": "sin(a)", "style": "main", "label": "P"}],
                "x_min": -1.5, "x_max": 1.5, "y_min": -1.5, "y_max": 1.5, "axes": True, "origin": True,
                "readouts": [{"label": "sin", "expr": "sin(a)", "decimals": 3},
                             {"label": "cos", "expr": "cos(a)", "decimals": 3}]}
    if kind == "bars":
        return {"type": "bars", "title": "Splitting a budget",
                "caption": "Move the slider to shift money from rent to savings.",
                "controls": [{"name": "s", "kind": "slider", "label": "Savings share", "min": 0, "max": 0.5,
                              "step": 0.01, "value": 0.2}],
                "bars": [{"label": "Rent", "expr": "0.6 - s/2"}, {"label": "Food", "expr": "0.25"},
                         {"label": "Savings", "expr": "s"}, {"label": "Other", "expr": "0.15 - s/2"}],
                "highlight": "max", "decimals": 2, "y_min": 0, "y_max": 0.7, "y_label": "share",
                "readouts": [{"label": "Total", "expr": "sum(bars)", "decimals": 2}]}
    if kind == "heatmap":
        return {"type": "heatmap", "title": "Waves on a grid",
                "caption": "Each cell is sin(i·a)·cos(j·a): move a to change the pattern.",
                "controls": [{"name": "a", "kind": "slider", "label": "Frequency a", "min": 0.1, "max": 1.5,
                              "step": 0.05, "value": 0.5}],
                "rows": "10", "cols": "10", "expr": "sin(i*a)*cos(j*a)", "range_min": -1, "range_max": 1,
                "readouts": [{"label": "Largest cell", "expr": "max(cells)", "decimals": 2}]}
    if kind == "distribution":
        return {"type": "distribution", "title": "The normal distribution", "family": "normal",
                "caption": "Move the mean and the spread; the shaded band holds the values within a few standard "
                           "deviations of the mean.",
                "interval": {"mode": "sigma"}}
    if kind == "data":
        return {"type": "data", "title": "Height and arm span",
                "caption": "Ten people's height and arm span, with the straight line that fits them best.",
                "csv": "height (cm),arm span (cm)\n152,150\n158,160\n163,161\n165,168\n170,169\n172,175\n"
                       "176,174\n180,183\n184,182\n190,193",
                "chart": "scatter", "x": "height_cm", "y": ["arm_span_cm"], "fit": "line", "fit_toggle": True}
    raise ValueError("unknown figure type %r" % kind)


def describe():
    """What the Studio's form needs to know: types, functions, styles, families, limits."""
    return {
        "types": [{"type": k, **v} for k, v in TYPES.items()],
        "functions": [{"name": k, "args": lo if lo == hi else "%d-%d" % (lo, hi), "help": d}
                      for k, (lo, hi, d) in FUNCTIONS.items()],
        "aggregates": [{"name": k, "help": d} for k, (_x, d) in AGGREGATES.items()],
        "constants": sorted(CONSTANTS),
        "colours": list(STYLE_COLOURS),
        "lines": list(STYLE_LINES),
        "families": {k: {"label": v["label"], "discrete": v["discrete"], "params": v["params"]} for k, v in FAMILIES.items()},
        "limits": LIMITS,
        "examples": {k: default_spec(k) for k in TYPES},
    }
