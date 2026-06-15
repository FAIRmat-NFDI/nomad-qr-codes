#!/usr/bin/env python3
"""Generate a branded QR code with rounded dots and corners.

Dependencies:
    pip install "qrcode>=7.4" cairosvg

Examples:
  python scripts/generate_nomad_qr.py \
        "https://discord.gg/Gyzx3ukUw8" \
    --output "assets/qr/nomad-discord-qr.png"

  python scripts/generate_nomad_qr.py \
        "https://discord.gg/Gyzx3ukUw8" \
    --format svg \
    --output "assets/qr/nomad-discord-qr.svg"
"""

from __future__ import annotations

import argparse
import base64
from importlib import resources
import math
from pathlib import Path

import cairosvg
import qrcode
from qrcode.constants import ERROR_CORRECT_H


DEFAULT_PRESET_COLOR = "#192E87"
DEFAULT_PRESET_EYELET_COLOR = "#2A4CDF"
DARK_PRESET_COLOR = "#6162A5"
DARK_PRESET_EYELET_COLOR = "#8B8CEC"


def normalize_hex_color(hex_color: str) -> str:
    value = hex_color.strip().lstrip("#")
    if len(value) != 6:
        raise ValueError(f"Expected a 6-digit hex color, got: {hex_color}")
    return f"#{value.upper()}"


def build_qr_matrix(data: str) -> list[list[bool]]:
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_H,
        box_size=18,
        # Keep matrix border at 0 here; SVG rendering adds border explicitly.
        border=0,
    )
    qr.add_data(data)
    qr.make(fit=True)
    return qr.get_matrix()


def rotate_matrix_ccw(matrix: list[list[bool]]) -> list[list[bool]]:
    return [list(row) for row in zip(*matrix)][::-1]


def finder_bounds(size: int) -> list[tuple[int, int, int, int]]:
    return [
        (0, 0, 6, 6),
        (0, size - 7, 6, size - 1),
        (size - 7, size - 7, size - 1, size - 1),
    ]


def in_bounds(x: int, y: int, bounds: tuple[int, int, int, int]) -> bool:
    x0, y0, x1, y1 = bounds
    return x0 <= x <= x1 and y0 <= y <= y1


def circle_intersects_rect(
    cx: float,
    cy: float,
    radius: float,
    rx: float,
    ry: float,
    rw: float,
    rh: float,
) -> bool:
    closest_x = min(max(cx, rx), rx + rw)
    closest_y = min(max(cy, ry), ry + rh)
    dx = cx - closest_x
    dy = cy - closest_y
    return dx * dx + dy * dy <= radius * radius


def quadratic_tangent_control(
    start: tuple[float, float],
    start_tangent: tuple[float, float],
    end: tuple[float, float],
    end_tangent: tuple[float, float],
) -> tuple[float, float]:
    """Return a quadratic control point that matches tangent at both endpoints.

    The control lies at the intersection of:
    - start + a * start_tangent
    - end   - b * end_tangent
    """
    sx, sy = start
    ex, ey = end
    sdx, sdy = start_tangent
    edx, edy = end_tangent

    det = sdx * edy - sdy * edx
    if abs(det) < 1e-9:
        # Degenerate case: tangent lines are nearly parallel.
        return ((sx + ex) / 2, (sy + ey) / 2)

    rx = ex - sx
    ry = ey - sy
    a = (rx * edy - ry * edx) / det
    return (sx + a * sdx, sy + a * sdy)


def build_svg_qr(
    data: str,
    color: str,
    logo_svg_bytes: bytes,
    white_background: bool = False,
    eyelet_color: str | None = None,
) -> str:
    matrix = rotate_matrix_ccw(build_qr_matrix(data))
    size = len(matrix)
    module = 18
    border = 2
    canvas = (size + border * 2) * module
    fill = normalize_hex_color(color)
    eyelet_fill = normalize_hex_color(eyelet_color or color)

    finder_areas = finder_bounds(size)

    logo_size = int(canvas * 0.18)
    logo_x = (canvas - logo_size) // 2
    logo_y = (canvas - logo_size) // 2
    # Slightly larger keepout zone prevents tiny module clipping near the logo edge.
    pad = max(12, canvas // 64)
    bg_x = logo_x - pad
    bg_y = logo_y - pad
    bg_w = logo_size + 2 * pad
    bg_h = logo_size + 2 * pad

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas}" height="{canvas}" viewBox="0 0 {canvas} {canvas}">'
    )
    if white_background:
        parts.append(f'<rect width="{canvas}" height="{canvas}" fill="white"/>')

    dot_radius = module * 0.42
    active_dots: list[list[bool]] = [[False for _ in range(size)] for _ in range(size)]
    dot_parts: list[str] = []

    for y, row in enumerate(matrix):
        for x, dark in enumerate(row):
            if not dark:
                continue
            if any(in_bounds(x, y, area) for area in finder_areas):
                continue
            cx = (x + border + 0.5) * module
            cy = (y + border + 0.5) * module
            # Reserve a clean center area so logo and backing do not clip neighboring dots.
            if circle_intersects_rect(cx, cy, dot_radius, bg_x, bg_y, bg_w, bg_h):
                continue
            active_dots[y][x] = True
            dot_parts.append(
                f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{dot_radius:.2f}" fill="{fill}"/>'
            )

    # Draw smooth bridges between neighboring dots using Bezier curves.
    # Anchors are placed on the 45/135/225/315-degree circle points.
    quadrant_offset = dot_radius / math.sqrt(2)
    curve_bend = module * 0.03

    for y in range(size):
        for x in range(size):
            if not active_dots[y][x]:
                continue

            cx = (x + border + 0.5) * module
            cy = (y + border + 0.5) * module

            if x + 1 < size and active_dots[y][x + 1]:
                nx = (x + 1 + border + 0.5) * module
                # Build two opposite side curves (top/bottom) and fill between them.
                top_sign = -1
                bot_sign = 1

                start_top_x = cx + quadrant_offset
                start_top_y = cy + top_sign * quadrant_offset
                end_top_x = nx - quadrant_offset
                end_top_y = cy + top_sign * quadrant_offset
                top_ctrl_x, top_ctrl_y = quadratic_tangent_control(
                    (start_top_x, start_top_y),
                    (1.0, 1.0),
                    (end_top_x, end_top_y),
                    (1.0, -1.0),
                )
                top_ctrl_y -= top_sign * curve_bend

                start_bot_x = cx + quadrant_offset
                start_bot_y = cy + bot_sign * quadrant_offset
                end_bot_x = nx - quadrant_offset
                end_bot_y = cy + bot_sign * quadrant_offset
                bot_ctrl_x, bot_ctrl_y = quadratic_tangent_control(
                    (start_bot_x, start_bot_y),
                    (1.0, -1.0),
                    (end_bot_x, end_bot_y),
                    (1.0, 1.0),
                )
                bot_ctrl_y -= bot_sign * curve_bend

                parts.append(
                    f'<path d="M {start_top_x:.2f} {start_top_y:.2f} '
                    f'Q {top_ctrl_x:.2f} {top_ctrl_y:.2f}, '
                    f'{end_top_x:.2f} {end_top_y:.2f} '
                    f'L {end_bot_x:.2f} {end_bot_y:.2f} '
                    f'Q {bot_ctrl_x:.2f} {bot_ctrl_y:.2f}, '
                    f'{start_bot_x:.2f} {start_bot_y:.2f} Z" '
                    f'fill="{fill}" stroke="none"/>'
                )

            if y + 1 < size and active_dots[y + 1][x]:
                ny = (y + 1 + border + 0.5) * module
                # Build two opposite side curves (left/right) and fill between them.
                left_sign = -1
                right_sign = 1

                start_left_x = cx + left_sign * quadrant_offset
                start_left_y = cy + quadrant_offset
                end_left_x = cx + left_sign * quadrant_offset
                end_left_y = ny - quadrant_offset
                left_ctrl_x, left_ctrl_y = quadratic_tangent_control(
                    (start_left_x, start_left_y),
                    (1.0, 1.0),
                    (end_left_x, end_left_y),
                    (-1.0, 1.0),
                )
                left_ctrl_x -= left_sign * curve_bend

                start_right_x = cx + right_sign * quadrant_offset
                start_right_y = cy + quadrant_offset
                end_right_x = cx + right_sign * quadrant_offset
                end_right_y = ny - quadrant_offset
                right_ctrl_x, right_ctrl_y = quadratic_tangent_control(
                    (start_right_x, start_right_y),
                    (-1.0, 1.0),
                    (end_right_x, end_right_y),
                    (1.0, 1.0),
                )
                right_ctrl_x -= right_sign * curve_bend

                parts.append(
                    f'<path d="M {start_left_x:.2f} {start_left_y:.2f} '
                    f'Q {left_ctrl_x:.2f} {left_ctrl_y:.2f}, '
                    f'{end_left_x:.2f} {end_left_y:.2f} '
                    f'L {end_right_x:.2f} {end_right_y:.2f} '
                    f'Q {right_ctrl_x:.2f} {right_ctrl_y:.2f}, '
                    f'{start_right_x:.2f} {start_right_y:.2f} Z" '
                    f'fill="{fill}" stroke="none"/>'
                )

    parts.extend(dot_parts)

    # Draw finder eyes as circular outer ring + circular inner dot.
    for x0, y0, _, _ in finder_areas:
        px = (x0 + border) * module
        py = (y0 + border) * module
        outer = 7 * module
        inner_cut = 5 * module
        inner_dot = 3 * module
        cx = px + outer / 2
        cy = py + outer / 2
        outer_r = outer / 2
        inner_cut_r = inner_cut / 2
        inner_dot_r = inner_dot / 2

        if not white_background:
            parts.append(
                f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{(outer_r - module * 0.5):.2f}" '
                f'fill="none" stroke="{eyelet_fill}" stroke-width="{module:.2f}"/>'
            )
        else:
            parts.append(
                f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{outer_r:.2f}" fill="{eyelet_fill}"/>'
            )
            parts.append(
                f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{inner_cut_r:.2f}" fill="white"/>'
            )
        parts.append(
            f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{inner_dot_r:.2f}" fill="{eyelet_fill}"/>'
        )

    logo_b64 = base64.b64encode(logo_svg_bytes).decode("ascii")

    if white_background:
        parts.append(
            f'<rect x="{bg_x}" y="{bg_y}" width="{bg_w}" height="{bg_h}" rx="{max(10, pad * 2)}" fill="white"/>'
        )
    parts.append(
        f'<image x="{logo_x}" y="{logo_y}" width="{logo_size}" height="{logo_size}" href="data:image/svg+xml;base64,{logo_b64}"/>'
    )

    parts.append("</svg>")
    return "".join(parts)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a styled NOMAD QR code.")
    parser.add_argument("data", help="Encoded URL/text")
    parser.add_argument(
        "--preset",
        choices=("default", "dark", "oasis", "dtu"),
        default="default",
        help="Color preset (default: default).",
    )
    parser.add_argument(
        "--output",
        default="generated-nomad-qr.png",
        help="Output path (default: generated-nomad-qr.png)",
    )
    parser.add_argument(
        "--logo",
        default=None,
        help="Path to center logo SVG (default: assets/logos/nomad.svg)",
    )
    parser.add_argument(
        "--color",
        default=None,
        help="QR foreground color in hex (overrides selected preset)",
    )
    parser.add_argument(
        "--eyelet-color",
        default=None,
        help="Optional finder eyelet color in hex (overrides selected preset).",
    )
    parser.add_argument(
        "--format",
        choices=("png", "svg"),
        default=None,
        help="Output format. If omitted, inferred from --output extension (defaults to png).",
    )
    parser.add_argument(
        "--white-background",
        action="store_true",
        help="Use white background (default: transparent).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.preset == "dark":
        preset_color = DARK_PRESET_COLOR
        preset_eyelet_color = DARK_PRESET_EYELET_COLOR
        preset_logo_name = "nomad-dark.svg"
    elif args.preset == "oasis":
        preset_color = "#008A68"
        preset_eyelet_color = "#2A4CDF"
        preset_logo_name = "oasis.svg"
    elif args.preset == "dtu":
        preset_color = "#990000"
        preset_eyelet_color = "#990000"
        preset_logo_name = "dtu-red.svg"
    else:
        preset_color = DEFAULT_PRESET_COLOR
        preset_eyelet_color = DEFAULT_PRESET_EYELET_COLOR
        preset_logo_name = "nomad.svg"

    selected_color = args.color or preset_color
    selected_eyelet_color = args.eyelet_color or preset_eyelet_color

    if args.logo:
        logo_path = Path(args.logo)
        if not logo_path.is_absolute():
            logo_path = Path.cwd() / logo_path
        if not logo_path.exists():
            raise FileNotFoundError(f"Logo file not found: {logo_path}")
        logo_svg_bytes = logo_path.read_bytes()
    else:
        logo_svg_bytes = (
            resources.files("nomad_qr_codes")
            .joinpath("assets", "logos", preset_logo_name)
            .read_bytes()
        )

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = Path.cwd() / output_path

    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_format = args.format
    if output_format is None:
        output_format = "svg" if output_path.suffix.lower() == ".svg" else "png"

    if output_format == "svg":
        svg_markup = build_svg_qr(
            args.data,
            selected_color,
            logo_svg_bytes,
            white_background=args.white_background,
            eyelet_color=selected_eyelet_color,
        )
        output_path.write_text(svg_markup, encoding="utf-8")
    else:
        svg_markup = build_svg_qr(
            args.data,
            selected_color,
            logo_svg_bytes,
            white_background=args.white_background,
            eyelet_color=selected_eyelet_color,
        )
        cairosvg.svg2png(bytestring=svg_markup.encode("utf-8"), write_to=str(output_path))

    print(f"Saved {output_format.upper()} QR code to: {output_path}")


if __name__ == "__main__":
    main()
