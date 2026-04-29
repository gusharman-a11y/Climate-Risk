"""
PowerPoint export of the ACCU Methods overview slide.

Produces a single 13.33 x 7.5 inch (16:9) slide laid out in the Pollination
deck style: eyebrow + headline at the top, a left-hand "Key Insights" rail,
and a right-hand methods table grouped by the five fixed categories. A
Pollination-style footer with confidentiality marker, page indicator and
sources is rendered along the bottom.
"""

from io import BytesIO

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Emu, Inches, Pt

from modules.accu_methods import (
    CATEGORIES,
    CATEGORY_COLORS,
    STATUS_LABELS,
    STATUS_BG,
    STATUS_COLORS,
    methods_by_category,
)

# 16:9 widescreen
SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)

# Palette
NAVY = RGBColor(0x0F, 0x17, 0x2A)
INK = RGBColor(0x1F, 0x29, 0x37)
MUTED = RGBColor(0x64, 0x74, 0x8B)
HAIRLINE = RGBColor(0xE2, 0xE8, 0xF0)
HEADER_BG = RGBColor(0xCB, 0xD5, 0xE1)
INSIGHT_BG = RGBColor(0x1E, 0x29, 0x3B)
INSIGHT_FG = RGBColor(0xE2, 0xE8, 0xF0)


def _hex_to_rgb(hexstr: str) -> RGBColor:
    h = hexstr.lstrip("#")
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _set_fill(shape, rgb: RGBColor) -> None:
    shape.fill.solid()
    shape.fill.fore_color.rgb = rgb
    shape.line.fill.background()


def _add_text(slide, left, top, width, height, text, *,
              size=10, bold=False, color=INK, align=PP_ALIGN.LEFT,
              anchor=MSO_ANCHOR.TOP, font="Calibri") -> None:
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = Emu(0)
    tf.margin_right = Emu(0)
    tf.margin_top = Emu(0)
    tf.margin_bottom = Emu(0)
    tf.vertical_anchor = anchor

    lines = text.split("\n") if isinstance(text, str) else list(text)
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        run = p.add_run()
        run.text = line
        run.font.name = font
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = color


def _add_pill(slide, left, top, width, height, text, *,
              fill: RGBColor, fg: RGBColor, size=8, bold=True) -> None:
    pill = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    pill.adjustments[0] = 0.5
    _set_fill(pill, fill)
    tf = pill.text_frame
    tf.margin_left = Emu(0)
    tf.margin_right = Emu(0)
    tf.margin_top = Emu(0)
    tf.margin_bottom = Emu(0)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    run = p.add_run()
    run.text = text
    run.font.name = "Calibri"
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = fg


def _add_rect(slide, left, top, width, height, fill: RGBColor) -> None:
    rect = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
    _set_fill(rect, fill)


def _add_hline(slide, left, top, width, color=NAVY, weight=1.25) -> None:
    line = slide.shapes.add_connector(1, left, top, left + width, top)
    line.line.color.rgb = color
    line.line.width = Pt(weight)


def build_pptx(data: dict) -> bytes:
    """Render the ACCU Methods overview slide and return raw .pptx bytes."""
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H

    blank_layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(blank_layout)

    margin_x = Inches(0.5)
    content_top = Inches(0.45)
    content_w = SLIDE_W - margin_x * 2

    # ── Eyebrow ──────────────────────────────────────────────────────────────
    _add_text(
        slide, margin_x, content_top, content_w, Inches(0.3),
        data.get("eyebrow", ""), size=10, bold=True, color=NAVY,
    )
    _add_hline(slide, margin_x, Inches(0.78), content_w, color=NAVY, weight=1.25)

    # ── Headline ─────────────────────────────────────────────────────────────
    _add_text(
        slide, margin_x, Inches(0.85), content_w, Inches(0.85),
        data.get("headline", ""), size=22, bold=False, color=NAVY,
    )

    # ── Two-column area: Key Insights (left) + Methods table (right) ─────────
    body_top = Inches(1.85)
    body_h = Inches(4.95)

    insights_w = Inches(3.4)
    insights_left = margin_x

    table_left = insights_left + insights_w + Inches(0.25)
    table_w = SLIDE_W - margin_x - table_left

    # ── Key Insights panel ───────────────────────────────────────────────────
    _add_text(
        slide, insights_left, body_top, insights_w, Inches(0.3),
        "KEY INSIGHTS", size=11, bold=True, color=NAVY,
    )

    insights = data.get("key_insights", [])
    insight_lines = [f"•  {t}" for t in insights]

    box = slide.shapes.add_textbox(
        insights_left, body_top + Inches(0.35),
        insights_w, body_h - Inches(0.35),
    )
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = Emu(0)
    tf.margin_right = Emu(0)
    for i, line in enumerate(insight_lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.LEFT
        p.space_after = Pt(6)
        run = p.add_run()
        run.text = line
        run.font.name = "Calibri"
        run.font.size = Pt(10)
        run.font.color.rgb = INK

    # ── Methods table ────────────────────────────────────────────────────────
    grouped = methods_by_category(data)
    total_rows = sum(1 for cat in CATEGORIES for _ in grouped[cat]) + len(CATEGORIES)
    total_rows += 1  # header row

    # Column widths (out of table_w)
    col_pcts = [0.42, 0.16, 0.18, 0.24]  # Methodology / Type / Status / Updates

    # Pre-compute header
    header_top = body_top
    header_h = Inches(0.32)

    # Header row
    _add_rect(slide, table_left, header_top, table_w, header_h, HEADER_BG)
    headers = ["METHODOLOGY", "TYPE", "STATUS / TIMING", "UPDATES"]
    x = table_left
    pad = Inches(0.08)
    for i, h in enumerate(headers):
        cw = Emu(int(table_w * col_pcts[i]))
        _add_text(
            slide, x + pad, header_top, cw - pad * 2, header_h,
            h, size=9, bold=True, color=NAVY,
            anchor=MSO_ANCHOR.MIDDLE,
        )
        x += cw

    # Body rows: iterate categories, then their methods
    row_top = header_top + header_h
    body_remaining = body_h - header_h

    # Estimate row heights so the table fits the body.
    method_count = sum(len(grouped[c]) for c in CATEGORIES)
    cat_count = sum(1 for c in CATEGORIES if grouped[c])
    units = method_count * 1.0 + cat_count * 0.55
    if units == 0:
        units = 1
    available = body_remaining
    method_row_h = Emu(int(available / units))
    cat_row_h = Emu(int(method_row_h * 0.55))

    for cat in CATEGORIES:
        rows = grouped[cat]
        if not rows:
            continue

        # Category band
        cat_color = _hex_to_rgb(CATEGORY_COLORS[cat])
        _add_rect(slide, table_left, row_top, table_w, cat_row_h, cat_color)
        _add_text(
            slide, table_left + pad, row_top, table_w - pad * 2, cat_row_h,
            cat.upper(), size=9, bold=True, color=RGBColor(0xFF, 0xFF, 0xFF),
            anchor=MSO_ANCHOR.MIDDLE,
        )
        row_top = row_top + cat_row_h

        for j, m in enumerate(rows):
            # Zebra striping
            if j % 2 == 1:
                _add_rect(slide, table_left, row_top, table_w, method_row_h,
                          RGBColor(0xF8, 0xFA, 0xFC))
            # hairline above each method row
            _add_hline(slide, table_left, row_top, table_w,
                       color=HAIRLINE, weight=0.5)

            x = table_left
            cells = [
                m.get("methodology", ""),
                cat,
                m.get("status_timing", ""),
                m.get("updates", ""),
            ]
            for i, val in enumerate(cells):
                cw = Emu(int(table_w * col_pcts[i]))

                if i == 2:
                    # Status pill + status_timing text
                    status = m.get("status", "")
                    label = STATUS_LABELS.get(status, "")
                    pill_w = Inches(0.95)
                    pill_h = Inches(0.22)
                    _add_pill(
                        slide,
                        x + pad,
                        row_top + Emu(int((method_row_h - pill_h) / 2)),
                        pill_w, pill_h, label,
                        fill=_hex_to_rgb(STATUS_BG.get(status, "#F3F4F6")),
                        fg=_hex_to_rgb(STATUS_COLORS.get(status, "#374151")),
                        size=8,
                    )
                    # Optional sub-line: e.g. "Sunsetting – closing to new registrations"
                    sub = val if val and val != label else ""
                    if sub:
                        _add_text(
                            slide,
                            x + pad + pill_w + Inches(0.05),
                            row_top, cw - pad * 2 - pill_w - Inches(0.05),
                            method_row_h,
                            sub, size=8, color=MUTED,
                            anchor=MSO_ANCHOR.MIDDLE,
                        )
                else:
                    _add_text(
                        slide, x + pad, row_top, cw - pad * 2, method_row_h,
                        val, size=8.5, color=INK,
                        bold=(i == 0),
                        anchor=MSO_ANCHOR.MIDDLE,
                    )
                x += cw

            row_top = row_top + method_row_h

    # Footnote (small italic line under the table area)
    footnote = data.get("footnote", "")
    if footnote:
        _add_text(
            slide, table_left, Inches(6.8), table_w, Inches(0.25),
            footnote, size=7, color=MUTED,
        )

    # ── Footer ───────────────────────────────────────────────────────────────
    footer_top = Inches(7.12)
    _add_hline(slide, margin_x, footer_top, content_w, color=NAVY, weight=0.75)
    _add_text(
        slide, margin_x, footer_top + Inches(0.05), Inches(7),
        Inches(0.25),
        "Pollination  |  CDC CARBON PROJECT DUE DILIGENCE  |  CONFIDENTIAL",
        size=8, color=NAVY, bold=True,
    )

    # Sources, on the right side of the footer
    sources = data.get("sources", [])
    if sources:
        src_text = "Sources: " + "  ·  ".join(sources)
        _add_text(
            slide, margin_x, footer_top + Inches(0.27), content_w,
            Inches(0.18),
            src_text, size=6.5, color=MUTED,
        )

    out = BytesIO()
    prs.save(out)
    return out.getvalue()
