"""Render the architecture diagram to a committed SVG.

GitHub's Mermaid renderer fails intermittently with an error that comes from
inside their lazily loaded bundle, so a mermaid fence in a README is not a
reliable way to show a diagram. This script writes the SVG directly, with
explicit intrinsic dimensions and a painted background, so it renders
identically on GitHub, in an editor preview, in a PDF export, and offline.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "docs" / "img" / "architecture.svg"

WIDTH, HEIGHT = 980, 560

BOX = "fill=\"#ffffff\" stroke=\"#4a5568\" stroke-width=\"1.6\" rx=\"6\""
ACCENT = "fill=\"#fff8e6\" stroke=\"#b7791f\" stroke-width=\"1.8\" rx=\"6\""
MUTED = "fill=\"#f7fafc\" stroke=\"#a0aec0\" stroke-width=\"1.4\" rx=\"6\""
LABEL = 'font-family="Helvetica,Arial,sans-serif" font-size="13" fill="#1a202c"'
SMALL = 'font-family="Helvetica,Arial,sans-serif" font-size="11" fill="#4a5568"'
TITLE = 'font-family="Helvetica,Arial,sans-serif" font-size="12" font-weight="bold" fill="#2d3748"'


def box(x, y, w, h, style, lines, line_style=LABEL):
    parts = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" {style}/>']
    start = y + h / 2 - (len(lines) - 1) * 8
    for index, line in enumerate(lines):
        style_for_line = line_style if index == 0 else SMALL
        parts.append(
            f'<text x="{x + w / 2}" y="{start + index * 16 + 4}" text-anchor="middle" '
            f"{style_for_line}>{line}</text>"
        )
    return "\n".join(parts)


def arrow(x1, y1, x2, y2, label=""):
    parts = [
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#4a5568" '
        'stroke-width="1.5" marker-end="url(#head)"/>'
    ]
    if label:
        parts.append(
            f'<text x="{(x1 + x2) / 2}" y="{(y1 + y2) / 2 - 6}" text-anchor="middle" '
            f"{SMALL}>{label}</text>"
        )
    return "\n".join(parts)


def build() -> str:
    body = [
        f'<rect x="0" y="0" width="{WIDTH}" height="{HEIGHT}" fill="#ffffff"/>',
        f'<text x="{WIDTH / 2}" y="30" text-anchor="middle" '
        'font-family="Helvetica,Arial,sans-serif" font-size="16" font-weight="bold" '
        'fill="#1a202c">forecast-skill-vs-mix: where the answer comes from</text>',
        box(40, 60, 190, 70, MUTED, ["weekly demand panel", "sku, week, actual, forecast"]),
        box(40, 170, 190, 70, MUTED, ["seeded generator", "planted ground truth"]),
        arrow(135, 170, 135, 134),
        arrow(230, 95, 300, 95),
        box(300, 60, 210, 80, BOX, ["validate and aggregate", "to two period totals", "ADR-003"]),
        arrow(405, 140, 405, 185),
        box(300, 185, 210, 105, ACCENT, [
            "split into four populations",
            "decomposable / entrants",
            "exits / dormant",
            "only the first is defined",
        ]),
        arrow(510, 100, 600, 100),
        box(600, 60, 180, 80, BOX, ["seasonal naive referee", "week aligned", "ADR-004"]),
        arrow(510, 235, 600, 235),
        box(600, 185, 340, 105, ACCENT, [
            "decompose in four conventions",
            "skill, mix, interaction",
            "they disagree: the spread is",
            "published, not hidden.  ADR-002",
        ]),
        arrow(770, 290, 770, 330),
        box(600, 330, 340, 75, BOX, [
            "bootstrap the skill effect over SKUs",
            "an interval that covers zero is not an effect",
        ]),
        arrow(405, 290, 405, 440),
        arrow(600, 370, 500, 440),
        box(260, 440, 290, 80, ACCENT, [
            "verdict",
            "0 attributed  \u00b7  1 answered no",
            "2 cannot answer  \u00b7  3 usage",
        ]),
        box(600, 440, 340, 80, ACCENT, [
            "unattributable remainder, always reported",
            "entrants and exits have no counterfactual",
            "ADR-005 states what the fixture cannot show",
        ]),
        arrow(550, 480, 596, 480),
    ]
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}">\n'
        '<defs><marker id="head" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" '
        'markerHeight="6" orient="auto-start-reverse">'
        '<path d="M 0 0 L 10 5 L 0 10 z" fill="#4a5568"/></marker></defs>\n'
        + "\n".join(body)
        + "\n</svg>\n"
    )


def main() -> int:
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(build())
    print(f"wrote {TARGET.relative_to(ROOT)} ({TARGET.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
