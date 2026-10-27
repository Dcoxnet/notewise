from __future__ import annotations

import html
import textwrap
from pathlib import Path
from typing import Any


WIDTH = 960
HEIGHT = 150
INK = "#273142"
MUTED = "#66758B"
ACCENT = "#4969E8"
LINE = "#DCE3F1"
PAPER = "#FFFFFF"


def _wrapped_lines(value: str, width: int, max_lines: int) -> list[str]:
    lines = textwrap.wrap(value.strip(), width=width, break_long_words=True, break_on_hyphens=False)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(" .,;:") + "…"
    return lines


def _text(
    x: float,
    y: float,
    lines: list[str],
    *,
    size: int,
    color: str,
    weight: int = 400,
    line_height: int = 17,
    anchor: str = "start",
) -> str:
    spans = "".join(
        f'<tspan x="{x:.1f}" dy="{0 if index == 0 else line_height}">{html.escape(line)}</tspan>'
        for index, line in enumerate(lines)
    )
    return f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" fill="{color}" font-size="{size}" font-weight="{weight}">{spans}</text>'


def _diagram_svg(visual: dict[str, Any]) -> str | None:
    kind = visual.get("type")
    if kind not in {"flow", "cards"}:
        return None
    items = visual.get("items")
    if not isinstance(items, list):
        return None
    items = [item for item in items if isinstance(item, dict) and str(item.get("title", "")).strip()]
    items = items[:4]
    if len(items) < 2:
        return None

    margin, gap, card_y, card_h = 22, 26, 8, 135
    card_w = (WIDTH - 2 * margin - gap * (len(items) - 1)) / len(items)
    pieces = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
        '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto"><path d="M0 0 L7 4 L0 8 Z" fill="#8495C9"/></marker></defs>',
    ]

    for index, item in enumerate(items):
        x = margin + index * (card_w + gap)
        if kind == "flow" and index < len(items) - 1:
            start_x = x + card_w + 3
            end_x = x + card_w + gap - 5
            pieces.append(f'<line x1="{start_x:.1f}" y1="105" x2="{end_x:.1f}" y2="105" stroke="#8495C9" stroke-width="2.5" marker-end="url(#arrow)"/>')
        pieces.append(f'<rect x="{x:.1f}" y="{card_y}" width="{card_w:.1f}" height="{card_h}" rx="12" fill="{PAPER}" stroke="{LINE}" stroke-width="2"/>')
        pieces.append(f'<rect x="{x + 16:.1f}" y="{card_y + 15}" width="30" height="30" rx="9" fill="#EEF1FF"/>')
        pieces.append(_text(x + 31, card_y + 36, [f"{index + 1:02d}"], size=12, color=ACCENT, weight=700, line_height=14, anchor="middle"))
        title = str(item.get("title", "")).strip()[:60]
        detail = str(item.get("detail", "")).strip()[:160]
        title_lines = _wrapped_lines(title, max(12, int((card_w - 32) / 8.2)), 2)
        detail_lines = _wrapped_lines(detail, max(15, int((card_w - 32) / 7.1)), 3)
        pieces.append(_text(x + 16, card_y + 61, title_lines, size=15, color=INK, weight=700, line_height=18))
        detail_y = card_y + (101 if len(title_lines) > 1 else 88)
        pieces.append(_text(x + 16, detail_y, detail_lines, size=12, color=MUTED, line_height=14))

    pieces.append("</svg>")
    return "".join(pieces)


def write_slide_diagrams(summary: dict[str, Any], output_dir: Path) -> None:
    diagram_dir = output_dir / "diagrams"
    diagram_dir.mkdir(parents=True, exist_ok=True)
    for index, slide in enumerate(summary.get("slides", []), start=1):
        visual = slide.get("visual")
        svg = _diagram_svg(visual) if isinstance(visual, dict) else None
        if not svg:
            slide["diagram"] = ""
            continue
        filename = f"slide-{index:02d}.svg"
        (diagram_dir / filename).write_text(svg, encoding="utf-8")
        slide["diagram"] = f"diagrams/{filename}"
