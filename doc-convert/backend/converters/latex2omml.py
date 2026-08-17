"""Small LaTeX-to-OMML converter for pasted educational text.

The supported subset intentionally focuses on formula constructs commonly
copied from math worksheets: fractions, roots, scripts, aligned equations,
Greek letters and elementary operators. Unsupported commands are emitted as
upright text instead of making the whole document fail.
"""

from __future__ import annotations

import re
from xml.sax.saxutils import escape

M_NS = 'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"'

SYMBOLS = {
    "cdot": "·", "times": "×", "div": "÷", "pm": "±", "mp": "∓",
    "neq": "≠", "ne": "≠", "leq": "≤", "le": "≤", "geq": "≥",
    "ge": "≥", "approx": "≈", "ldots": "…", "dots": "…", "cdots": "⋯",
    "infty": "∞", "pi": "π", "alpha": "α", "beta": "β", "gamma": "γ",
    "delta": "δ", "theta": "θ", "lambda": "λ", "mu": "μ", "sigma": "σ",
    "angle": "∠", "triangle": "△", "circ": "∘", "because": "∵",
    "therefore": "∴", "quad": " ", "qquad": "  ", ",": " ", ";": " ",
    ":": " ", "!": "", " ": " ", "%": "%", "$": "$", "#": "#", "&": "&",
}
STYLE_ONE_ARG = {
    "boldsymbol": {"bold": True}, "mathbf": {"bold": True, "nor": True},
    "bf": {"bold": True}, "text": {"nor": True},
    "textbf": {"nor": True, "bold": True}, "textrm": {"nor": True},
    "mathrm": {"nor": True}, "operatorname": {"nor": True},
}
_ENV_RE = re.compile(r"\A\s*\\begin\{(align\*?|aligned|gather\*?)\}(.*?)\\end\{\1\}\s*\Z", re.S)


def normalize(src: str) -> str:
    return (src.replace("‑", "-").replace("‐", "-").replace("–", "-")
            .replace("—", "-").replace("−", "-").replace(" ", " ")
            .replace("＿", "_"))


def _run(text: str, bold: bool = False, upright: bool = False) -> str:
    if not text:
        return ""
    props = []
    if upright:
        props.append("<m:nor/>")
    if bold:
        props.append('<m:sty m:val="%s"/>' % ("b" if upright else "bi"))
    rpr = "<m:rPr>%s</m:rPr>" % "".join(props) if props else ""
    return '<m:r>%s<m:t xml:space="preserve">%s</m:t></m:r>' % (rpr, escape(text))


def _sup(base: str, value: str) -> str:
    return f"<m:sSup><m:sSupPr><m:ctrlPr/></m:sSupPr><m:e>{base or _run('')}</m:e><m:sup>{value}</m:sup></m:sSup>"


def _sub(base: str, value: str) -> str:
    return f"<m:sSub><m:sSubPr><m:ctrlPr/></m:sSubPr><m:e>{base or _run('')}</m:e><m:sub>{value}</m:sub></m:sSub>"


def _subsup(base: str, sub: str, sup: str) -> str:
    return f"<m:sSubSup><m:sSubSupPr><m:ctrlPr/></m:sSubSupPr><m:e>{base}</m:e><m:sub>{sub}</m:sub><m:sup>{sup}</m:sup></m:sSubSup>"


def _frac(num: str, den: str) -> str:
    return f"<m:f><m:fPr><m:ctrlPr/></m:fPr><m:num>{num}</m:num><m:den>{den}</m:den></m:f>"


def _rad(degree: str | None, body: str) -> str:
    hidden = '<m:degHide m:val="1"/>' if degree is None else ""
    degree_xml = "<m:deg/>" if degree is None else f"<m:deg>{degree}</m:deg>"
    return f"<m:rad><m:radPr>{hidden}<m:ctrlPr/></m:radPr>{degree_xml}<m:e>{body}</m:e></m:rad>"


def _tokenize(src: str) -> list[tuple[str, str]]:
    tokens = []
    i = 0
    while i < len(src):
        char = src[i]
        if char == "\\":
            match = re.match(r"\\([A-Za-z]+|.)", src[i:], re.S)
            if match:
                tokens.append(("cmd", match.group(1)))
                i += match.end()
            else:
                i += 1
        elif char in "{}^_":
            tokens.append((char, char))
            i += 1
        elif char.isspace():
            tokens.append(("space", " "))
            i += 1
        else:
            tokens.append(("char", char))
            i += 1
    return tokens


class _Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.index = 0

    def done(self):
        return self.index >= len(self.tokens)

    def peek(self):
        return None if self.done() else self.tokens[self.index]

    def next(self):
        token = self.tokens[self.index]
        self.index += 1
        return token

    def skip_space(self):
        while not self.done() and self.peek()[0] == "space":
            self.index += 1

    def group(self, bold=False, upright=False):
        self.skip_space()
        if self.done():
            return _run("")
        if self.peek()[0] == "{":
            self.next()
            value = self.sequence(bold, upright, stop_at_brace=True)
            if not self.done() and self.peek()[0] == "}":
                self.next()
            return value or _run("")
        return self.atom(bold, upright) or _run("")

    def raw_group(self):
        self.skip_space()
        if self.done():
            return ""
        if self.peek()[0] != "{":
            kind, value = self.next()
            return value if kind == "char" else ""
        self.next()
        depth, output = 1, []
        while not self.done():
            kind, value = self.next()
            if kind == "{":
                depth += 1
            elif kind == "}":
                depth -= 1
                if depth == 0:
                    break
            output.append(SYMBOLS.get(value, "") if kind == "cmd" else value)
        return "".join(output)

    def atom(self, bold=False, upright=False):
        self.skip_space()
        if self.done():
            return ""
        kind, value = self.next()
        if kind == "char":
            return _run(value, bold, upright)
        if kind == "{":
            body = self.sequence(bold, upright, stop_at_brace=True)
            if not self.done() and self.peek()[0] == "}":
                self.next()
            return body
        if kind == "cmd":
            return self.command(value, bold, upright)
        return ""

    def command(self, name, bold=False, upright=False):
        if name in ("frac", "dfrac", "tfrac"):
            return _frac(self.group(bold, upright), self.group(bold, upright))
        if name == "sqrt":
            self.skip_space()
            degree = None
            if not self.done() and self.peek() == ("char", "["):
                self.next()
                parts = []
                while not self.done() and self.peek() != ("char", "]"):
                    parts.append(self.atom(bold, upright))
                if not self.done():
                    self.next()
                degree = "".join(parts)
            return _rad(degree, self.group(bold, upright))
        if name in STYLE_ONE_ARG:
            options = STYLE_ONE_ARG[name]
            new_bold = bold or options.get("bold", False)
            new_upright = upright or options.get("nor", False)
            if options.get("nor"):
                return _run(self.raw_group(), new_bold, True)
            return self.group(new_bold, new_upright)
        if name in ("left", "right"):
            self.skip_space()
            if self.done():
                return ""
            kind, value = self.next()
            if value == ".":
                return ""
            return _run(SYMBOLS.get(value, value), bold, upright)
        if name in SYMBOLS:
            return _run(SYMBOLS[name], bold, upright)
        return _run(name, bold, True)

    def sequence(self, bold=False, upright=False, stop_at_brace=False):
        output = []
        while not self.done():
            kind, _ = self.peek()
            if kind == "}" and stop_at_brace:
                break
            if kind == "space":
                self.next()
                continue
            if kind in ("^", "_"):
                script_kind, _ = self.next()
                script = self.group(bold, upright)
                base = output.pop() if output else _run("")
                output.append(_sup(base, script) if script_kind == "^" else _sub(base, script))
                self.skip_space()
                if not self.done() and self.peek()[0] in ("^", "_") and self.peek()[0] != script_kind:
                    other_kind, _ = self.next()
                    other = self.group(bold, upright)
                    wrapper = output.pop()
                    match = re.search(r"<m:e>(.*)</m:e>", wrapper, re.S)
                    base_xml = match.group(1) if match else base
                    output.append(_subsup(base_xml, other, script) if script_kind == "^" else _subsup(base_xml, script, other))
                continue
            output.append(self.atom(bold, upright))
        return "".join(output)


def _inline(src: str) -> str:
    return _Parser(_tokenize(normalize(src))).sequence()


def _aligned_rows(body: str) -> str:
    rows_source = [line for line in re.split(r"\\\\", body) if line.strip()]
    grid = [line.split("&") for line in rows_source]
    columns = max((len(row) for row in grid), default=1)
    rows = []
    for cells in grid:
        cells = cells + [""] * (columns - len(cells))
        rows.append("<m:mr>%s</m:mr>" % "".join(f"<m:e>{_inline(cell)}</m:e>" for cell in cells))
    column_props = ['<m:mc><m:mcPr><m:count m:val="1"/><m:mcJc m:val="right"/></m:mcPr></m:mc>']
    if columns > 1:
        column_props.append(f'<m:mc><m:mcPr><m:count m:val="{columns - 1}"/><m:mcJc m:val="left"/></m:mcPr></m:mc>')
    matrix = f"<m:m><m:mPr><m:mcs>{''.join(column_props)}</m:mcs><m:plcHide m:val=\"1\"/><m:ctrlPr/></m:mPr>{''.join(rows)}</m:m>"
    return f"<m:oMathPara {M_NS}><m:oMath>{matrix}</m:oMath></m:oMathPara>"


def to_omml(src: str) -> str:
    source = normalize(src).strip()
    environment = _ENV_RE.match(source)
    if environment:
        return _aligned_rows(environment.group(2))
    return f"<m:oMath {M_NS}>{_inline(source)}</m:oMath>"


def is_display(src: str) -> bool:
    return bool(_ENV_RE.match(normalize(src).strip()))
