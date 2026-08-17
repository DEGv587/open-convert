"""Render the supported worksheet LaTeX subset to transparent PNG images.

LibreOffice does not reliably import Word's native OMML equations.  The PDF
pipeline therefore uses these images in its *temporary* DOCX while the Word
pipeline continues to emit editable OMML.
"""

from __future__ import annotations

import os
import re
import tempfile
import threading
from dataclasses import dataclass
from functools import lru_cache
from io import BytesIO


_CACHE_DIR = os.path.join(tempfile.gettempdir(), "docconvert-matplotlib")
os.makedirs(_CACHE_DIR, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", _CACHE_DIR)
os.environ.setdefault("XDG_CACHE_HOME", _CACHE_DIR)

import matplotlib

matplotlib.use("Agg")

from matplotlib import rc_context
from matplotlib.font_manager import FontProperties, fontManager
from matplotlib.mathtext import math_to_image
from PIL import Image, ImageDraw, ImageFont

from converters.latex2omml import normalize


DPI = 300
FONT_SIZE_PT = 10.5
MAX_IMAGE_WIDTH_PX = round(6.0 * DPI)
_ENV_RE = re.compile(
    r"\A\s*\\begin\{(align\*?|aligned|gather\*?)\}(.*?)\\end\{\1\}\s*\Z",
    re.S,
)
_ROW_SPLIT_RE = re.compile(r"\\\\(?:\s*\[[^\]]*\])?")
_STYLE_COMMAND_RE = re.compile(r"\\(?:boldsymbol|mathbf|bf)\s*\{")
_MATH_RENDER_LOCK = threading.Lock()


@dataclass
class _Rendered:
    image: Image.Image
    depth: int

    @property
    def ascent(self) -> int:
        return self.image.height - self.depth


@lru_cache(maxsize=1)
def _font_path() -> str:
    preferred = (
        "Noto Sans CJK SC",
        "Noto Sans CJK JP",
        "WenQuanYi Micro Hei",
        "WenQuanYi Zen Hei",
        "PingFang SC",
        "Heiti SC",
        "Arial Unicode MS",
        "DejaVu Sans",
    )
    fonts = list(fontManager.ttflist)
    for family in preferred:
        match = next((entry for entry in fonts if entry.name == family), None)
        if match:
            return match.fname
    return fonts[0].fname


def _render_text(value: str, *, bold: bool = False) -> _Rendered:
    text = normalize(value) or " "
    size = round(FONT_SIZE_PT * DPI / 72)
    font = ImageFont.truetype(_font_path(), size=size)
    left, top, right, bottom = font.getbbox(text, anchor="ls")
    width = max(1, right - left)
    height = max(1, bottom - top)
    image = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)
    # Simulate bold only for text segments; mathematical bold is handled by
    # mathtext itself whenever the source syntax is supported.
    stroke = 1 if bold else 0
    draw.text(
        (-left, -top),
        text,
        font=font,
        fill=(0, 0, 0, 255),
        stroke_width=stroke,
        anchor="ls",
    )
    return _Rendered(image, max(0, bottom))


def _fraction_atom(source: str, start: int):
    cursor = start
    while cursor < len(source) and source[cursor].isspace():
        cursor += 1
    if cursor >= len(source):
        return None
    if source[cursor] == "{":
        depth = 1
        end = cursor + 1
        while end < len(source) and depth:
            if source[end] == "{":
                depth += 1
            elif source[end] == "}":
                depth -= 1
            end += 1
        if depth:
            return None
        return end, "{" + _normalize_fractions(source[cursor + 1:end - 1]) + "}"
    if source[cursor] == "\\":
        match = re.match(r"\\(?:[A-Za-z]+|.)", source[cursor:])
        if match:
            return cursor + match.end(), "{" + match.group(0) + "}"
    return cursor + 1, "{" + source[cursor] + "}"


def _normalize_fractions(source: str) -> str:
    """Expand accepted shorthand such as ``\\dfrac13`` for mathtext."""
    output = []
    cursor = 0
    while cursor < len(source):
        match = re.match(r"\\(?:dfrac|tfrac|frac)(?![A-Za-z])", source[cursor:])
        if not match:
            output.append(source[cursor])
            cursor += 1
            continue
        numerator = _fraction_atom(source, cursor + match.end())
        denominator = _fraction_atom(source, numerator[0]) if numerator else None
        if not numerator or not denominator:
            output.append(source[cursor])
            cursor += 1
            continue
        output.append(r"\frac" + numerator[1] + denominator[1])
        cursor = denominator[0]
    return "".join(output)


def _mathtext_source(source: str) -> str:
    value = normalize(source).strip()
    if value.startswith("$") and value.endswith("$") and len(value) >= 2:
        value = value[1:-1]
    return _normalize_fractions(value).replace(r"\boldsymbol", r"\mathbf").replace(
        r"\triangle", r"\Delta"
    )


def _strip_style_commands(source: str) -> str:
    """Remove unsupported nested bold wrappers without removing their body."""
    output = []
    index = 0
    while index < len(source):
        match = _STYLE_COMMAND_RE.match(source, index)
        if not match:
            output.append(source[index])
            index += 1
            continue
        depth = 1
        cursor = match.end()
        body_start = cursor
        while cursor < len(source) and depth:
            if source[cursor] == "{":
                depth += 1
            elif source[cursor] == "}":
                depth -= 1
            cursor += 1
        if depth:
            # Preserve malformed source.  It will be rendered as readable text
            # by the caller if mathtext also rejects it.
            output.append(source[index])
            index += 1
            continue
        output.append(_strip_style_commands(source[body_start:cursor - 1]))
        index = cursor
    return "".join(output)


def _render_math(source: str) -> _Rendered:
    value = _mathtext_source(source)
    attempts = [(value, False)]
    stripped = _strip_style_commands(value)
    if stripped != value:
        attempts.append((stripped, True))

    last_error = None
    for candidate, bold in attempts:
        stream = BytesIO()
        settings = {"mathtext.fontset": "stix"}
        if bold:
            settings["mathtext.default"] = "bf"
        try:
            # Matplotlib's rcParams and mathtext parser caches are global.
            # Conversion jobs run in a thread pool, so serialize this small
            # rendering section to avoid cross-job style/cache corruption.
            with _MATH_RENDER_LOCK:
                with rc_context(settings):
                    depth = math_to_image(
                        f"${candidate}$",
                        stream,
                        format="png",
                        dpi=DPI,
                        prop=FontProperties(size=FONT_SIZE_PT),
                        color="black",
                    )
            stream.seek(0)
            image = Image.open(stream).convert("RGBA")
            return _Rendered(image, max(0, min(image.height, round(depth))))
        except Exception as exc:  # pragma: no cover - exact parser errors vary
            last_error = exc

    raise ValueError(f"无法渲染数学公式: {source}") from last_error


def _text_command(source: str, start: int):
    commands = ((r"\textbf{", True), (r"\textrm{", False), (r"\text{", False))
    command = next(((token, bold) for token, bold in commands if source.startswith(token, start)), None)
    if command is None:
        return None
    token, bold = command
    depth = 1
    cursor = start + len(token)
    body_start = cursor
    while cursor < len(source) and depth:
        if source[cursor] == "{":
            depth += 1
        elif source[cursor] == "}":
            depth -= 1
        cursor += 1
    if depth:
        return None
    return cursor, source[body_start:cursor - 1], bold


def _split_text_segments(source: str):
    segments = []
    math_start = 0
    cursor = 0
    while cursor < len(source):
        command = _text_command(source, cursor)
        if command is None:
            cursor += 1
            continue
        end, body, bold = command
        if cursor > math_start:
            segments.append(("math", source[math_start:cursor], False))
        segments.append(("text", body, bold))
        cursor = end
        math_start = end
    if math_start < len(source):
        segments.append(("math", source[math_start:], False))
    return segments


def _join_on_baseline(parts: list[_Rendered], gap: int = 0) -> _Rendered:
    if not parts:
        return _render_text(" ")
    ascent = max(part.ascent for part in parts)
    depth = max(part.depth for part in parts)
    width = sum(part.image.width for part in parts) + gap * (len(parts) - 1)
    image = Image.new("RGBA", (max(1, width), max(1, ascent + depth)), (255, 255, 255, 0))
    left = 0
    for part in parts:
        image.alpha_composite(part.image, (left, ascent - part.ascent))
        left += part.image.width + gap
    return _Rendered(image, depth)


def _render_inline(source: str) -> _Rendered:
    parts = []
    for kind, value, bold in _split_text_segments(source):
        if not value:
            continue
        parts.append(_render_text(value, bold=bold) if kind == "text" else _render_math(value))
    return _join_on_baseline(parts)


def _render_aligned(environment: str, body: str) -> _Rendered:
    rows = [row.strip() for row in _ROW_SPLIT_RE.split(body) if row.strip()]
    grid = [[_render_inline(cell.strip()) for cell in row.split("&")] for row in rows]
    if not grid:
        return _render_text(normalize(body))

    columns = max(len(row) for row in grid)
    column_widths = [
        max((row[column].image.width for row in grid if column < len(row)), default=1)
        for column in range(columns)
    ]
    column_gap = round(DPI * 0.04)
    row_gap = round(DPI * 0.035)
    row_metrics = [
        (max(cell.ascent for cell in row), max(cell.depth for cell in row))
        for row in grid
    ]
    width = sum(column_widths) + column_gap * (columns - 1)
    height = sum(ascent + depth for ascent, depth in row_metrics) + row_gap * (len(grid) - 1)
    image = Image.new("RGBA", (max(1, width), max(1, height)), (255, 255, 255, 0))
    top = 0
    for row, (ascent, depth) in zip(grid, row_metrics):
        left = 0
        for column, cell in enumerate(row):
            if environment.startswith("gather") or columns == 1:
                x = (width - cell.image.width) // 2
            elif column == 0:
                x = left + column_widths[column] - cell.image.width
            else:
                x = left
            image.alpha_composite(cell.image, (x, top + ascent - cell.ascent))
            left += column_widths[column] + column_gap
        top += ascent + depth + row_gap
    return _Rendered(image, row_metrics[-1][1])


@lru_cache(maxsize=512)
def render_latex_png(source: str) -> bytes:
    """Return a transparent PNG, falling back to visible source on bad LaTeX."""
    value = normalize(source).strip()
    try:
        environment = _ENV_RE.match(value)
        if environment:
            rendered = _render_aligned(environment.group(1), environment.group(2))
        else:
            rendered = _render_inline(value)
    except Exception:
        # PDF formulas must never disappear.  Unsupported syntax remains
        # readable as source text instead of becoming a blank drawing.
        rendered = _render_text(value)

    image = rendered.image
    if image.width > MAX_IMAGE_WIDTH_PX:
        ratio = MAX_IMAGE_WIDTH_PX / image.width
        image = image.resize(
            (MAX_IMAGE_WIDTH_PX, max(1, round(image.height * ratio))),
            Image.Resampling.LANCZOS,
        )
    output = BytesIO()
    image.save(output, format="PNG", dpi=(DPI, DPI), optimize=True)
    return output.getvalue()
