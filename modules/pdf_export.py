"""
PDF report generator using ReportLab.
Produces a multi-section report:
  1. Cover page
  2. Executive / Board summary
  3. Pillar-by-pillar gap assessment
  4. Disclosure drafts
  5. Remediation roadmap
"""

from io import BytesIO
from datetime import date

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.flowables import KeepTogether

from .framework import FRAMEWORK
from .scoring import STATUS_LABELS, score_overall
from .disclosure import generate_all_disclosures

# ── Colour palette ─────────────────────────────────────────────────────────────
NAVY = colors.HexColor("#1E3A8A")
SLATE = colors.HexColor("#475569")
LIGHT_GRAY = colors.HexColor("#F1F5F9")
MID_GRAY = colors.HexColor("#CBD5E1")
WHITE = colors.white
BLACK = colors.black

PILLAR_COLORS = {
    "Governance": colors.HexColor("#3B82F6"),
    "Strategy": colors.HexColor("#22C55E"),
    "Risk Management": colors.HexColor("#F97316"),
    "Metrics & Targets": colors.HexColor("#8B5CF6"),
}

STATUS_PDF_COLORS = {
    "met": colors.HexColor("#22C55E"),
    "partial": colors.HexColor("#F59E0B"),
    "not_met": colors.HexColor("#EF4444"),
    "": colors.HexColor("#9CA3AF"),
}

STATUS_PDF_BG = {
    "met": colors.HexColor("#DCFCE7"),
    "partial": colors.HexColor("#FEF3C7"),
    "not_met": colors.HexColor("#FEE2E2"),
    "": colors.HexColor("#F3F4F6"),
}

W, H = A4


# ── Document setup ─────────────────────────────────────────────────────────────

def _make_styles() -> dict:
    base = getSampleStyleSheet()
    styles = {}

    def s(name, **kw):
        styles[name] = ParagraphStyle(name, **kw)

    s("cover_title",
      fontSize=28, leading=34, textColor=WHITE,
      alignment=TA_LEFT, fontName="Helvetica-Bold")
    s("cover_sub",
      fontSize=13, leading=18, textColor=colors.HexColor("#CBD5E1"),
      alignment=TA_LEFT, fontName="Helvetica")
    s("cover_meta",
      fontSize=10, leading=14, textColor=colors.HexColor("#94A3B8"),
      alignment=TA_LEFT, fontName="Helvetica")

    s("section_heading",
      fontSize=16, leading=20, textColor=NAVY,
      spaceBefore=18, spaceAfter=6,
      fontName="Helvetica-Bold")
    s("sub_heading",
      fontSize=12, leading=16, textColor=NAVY,
      spaceBefore=10, spaceAfter=4,
      fontName="Helvetica-Bold")
    s("req_heading",
      fontSize=10, leading=14, textColor=NAVY,
      spaceBefore=8, spaceAfter=2,
      fontName="Helvetica-Bold")
    s("body",
      fontSize=9, leading=13, textColor=SLATE,
      spaceAfter=4, fontName="Helvetica")
    s("body_small",
      fontSize=8, leading=11, textColor=SLATE,
      spaceAfter=2, fontName="Helvetica")
    s("table_header",
      fontSize=8, leading=10, textColor=WHITE,
      alignment=TA_LEFT, fontName="Helvetica-Bold")
    s("table_cell",
      fontSize=8, leading=11, textColor=SLATE,
      fontName="Helvetica")
    s("table_cell_center",
      fontSize=8, leading=11, textColor=SLATE,
      alignment=TA_CENTER, fontName="Helvetica")
    s("disclosure_text",
      fontSize=8.5, leading=13, textColor=SLATE,
      spaceAfter=4, fontName="Helvetica",
      leftIndent=8, rightIndent=8)
    s("footer",
      fontSize=7, leading=9, textColor=MID_GRAY,
      alignment=TA_CENTER, fontName="Helvetica")
    s("page_num",
      fontSize=7, leading=9, textColor=MID_GRAY,
      alignment=TA_RIGHT, fontName="Helvetica")

    return styles


# ── Page templates ─────────────────────────────────────────────────────────────

class _HeaderFooter:
    def __init__(self, client_name: str, reporting_period: str, styles: dict):
        self.client_name = client_name
        self.reporting_period = reporting_period
        self.styles = styles

    def __call__(self, canvas, doc):
        canvas.saveState()
        if doc.page == 1:
            # Cover – navy background
            canvas.setFillColor(NAVY)
            canvas.rect(0, 0, W, H, fill=1, stroke=0)
            canvas.setFillColor(colors.HexColor("#2563EB"))
            canvas.rect(0, 0, W, 3.5 * cm, fill=1, stroke=0)
        else:
            # Header bar
            canvas.setFillColor(NAVY)
            canvas.rect(0, H - 1.2 * cm, W, 1.2 * cm, fill=1, stroke=0)
            canvas.setFont("Helvetica-Bold", 8)
            canvas.setFillColor(WHITE)
            canvas.drawString(1.5 * cm, H - 0.8 * cm,
                              f"AASB S2 Climate Risk Disclosure Assessment  |  {self.client_name}  |  {self.reporting_period}")
            canvas.drawRightString(W - 1.5 * cm, H - 0.8 * cm, f"Page {doc.page}")

            # Footer
            canvas.setFillColor(MID_GRAY)
            canvas.rect(0, 0, W, 0.9 * cm, fill=1, stroke=0)
            canvas.setFont("Helvetica", 7)
            canvas.setFillColor(SLATE)
            canvas.drawString(1.5 * cm, 0.32 * cm,
                              "CONFIDENTIAL – Prepared for advisory purposes only. This report does not constitute legal advice.")
            canvas.drawRightString(W - 1.5 * cm, 0.32 * cm,
                                   f"Generated {date.today().strftime('%d %B %Y')}")
        canvas.restoreState()


# ── Score bar helper ───────────────────────────────────────────────────────────

def _score_bar_table(pct: float, bar_color: colors.Color, width: float = 10 * cm) -> Table:
    filled = max(0.5, width * pct / 100)
    empty = width - filled
    data = [[""]]
    t = Table([[""]], colWidths=[filled], rowHeights=[0.4 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bar_color),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    t2 = Table([[""]], colWidths=[empty], rowHeights=[0.4 * cm])
    t2.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_GRAY),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    outer = Table([[t, t2]], colWidths=[filled, empty], rowHeights=[0.4 * cm])
    outer.setStyle(TableStyle([
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return outer


# ── Section builders ───────────────────────────────────────────────────────────

def _build_cover(client_data: dict, overall: dict, styles: dict) -> list:
    name = client_data.get("client_name", "")
    entity_type = client_data.get("entity_type", "")
    industry = client_data.get("industry", "")
    period = client_data.get("reporting_period", "")
    pct = overall["overall_pct"]
    maturity = overall["maturity_label"]

    story = [Spacer(1, 5 * cm)]
    story.append(Paragraph("AASB S2 Climate Risk", styles["cover_title"]))
    story.append(Paragraph("Disclosure Assessment", styles["cover_title"]))
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph(name, ParagraphStyle("cn",
        fontSize=18, leading=22, textColor=colors.HexColor("#93C5FD"),
        fontName="Helvetica-Bold")))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(f"{entity_type}  |  {industry}", styles["cover_sub"]))
    story.append(Paragraph(f"Reporting period: {period}", styles["cover_meta"]))
    story.append(Spacer(1, 1.5 * cm))

    # Overall score box
    score_data = [
        [Paragraph("Overall Readiness Score", ParagraphStyle("sl",
            fontSize=10, textColor=colors.HexColor("#94A3B8"), fontName="Helvetica")),
         Paragraph(f"{pct:.0f}%", ParagraphStyle("sp",
            fontSize=32, textColor=WHITE, fontName="Helvetica-Bold", alignment=TA_RIGHT))],
        [Paragraph(maturity, ParagraphStyle("sm",
            fontSize=13, textColor=colors.HexColor("#93C5FD"), fontName="Helvetica-Bold")),
         Paragraph(f"of {overall['max_score']} points", ParagraphStyle("spp",
            fontSize=10, textColor=colors.HexColor("#94A3B8"), fontName="Helvetica", alignment=TA_RIGHT))],
    ]
    score_table = Table(score_data, colWidths=[9 * cm, 6 * cm])
    score_table.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(score_table)
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph(
        f"Generated {date.today().strftime('%d %B %Y')}  |  Assessed against AASB S2 Climate-related Financial Disclosures",
        styles["cover_meta"]))
    story.append(PageBreak())
    return story


def _build_executive_summary(overall: dict, styles: dict) -> list:
    story = [Paragraph("Executive Summary", styles["section_heading"]),
             HRFlowable(width="100%", thickness=1.5, color=NAVY, spaceAfter=10)]

    # Overall score table
    headers = ["Pillar", "Requirements", "Met", "Partial", "Not Met / N/A", "Score", "Maturity"]
    rows = [headers]
    for pillar_name, ps in overall["pillars"].items():
        not_met = ps["req_count"] - ps["met_count"] - ps["partial_count"]
        rows.append([
            pillar_name,
            str(ps["req_count"]),
            str(ps["met_count"]),
            str(ps["partial_count"]),
            str(not_met),
            f"{ps['score']}/{ps['max_score']}",
            ps["maturity_label"],
        ])
    # Total row
    total_req = sum(ps["req_count"] for ps in overall["pillars"].values())
    total_met = sum(ps["met_count"] for ps in overall["pillars"].values())
    total_partial = sum(ps["partial_count"] for ps in overall["pillars"].values())
    total_not_met = total_req - total_met - total_partial
    rows.append([
        "TOTAL",
        str(total_req),
        str(total_met),
        str(total_partial),
        str(total_not_met),
        f"{overall['total_score']}/{overall['max_score']}",
        f"{overall['overall_pct']:.0f}%  {overall['maturity_label']}",
    ])

    col_w = [4.5 * cm, 2 * cm, 1.5 * cm, 1.5 * cm, 2 * cm, 2 * cm, 3 * cm]
    t = Table(rows, colWidths=col_w, repeatRows=1)
    ts = TableStyle([
        # Header
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        # Body
        ("FONTNAME", (0, 1), (-1, -2), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -2), 8),
        ("TOPPADDING", (0, 1), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [WHITE, LIGHT_GRAY]),
        ("GRID", (0, 0), (-1, -1), 0.3, MID_GRAY),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        # Total row
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#E0E7FF")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, -1), (-1, -1), 8),
    ])
    t.setStyle(ts)
    story.append(t)
    story.append(Spacer(1, 0.5 * cm))

    # Pillar score bars
    story.append(Paragraph("Pillar Readiness", styles["sub_heading"]))
    for pillar_name, ps in overall["pillars"].items():
        bar_color = PILLAR_COLORS.get(pillar_name, NAVY)
        row_data = [[
            Paragraph(pillar_name, ParagraphStyle("pn",
                fontSize=9, fontName="Helvetica-Bold", textColor=NAVY)),
            _score_bar_table(ps["percentage"], bar_color, 9 * cm),
            Paragraph(f"{ps['percentage']:.0f}%  {ps['maturity_label']}",
                      ParagraphStyle("pp", fontSize=8, fontName="Helvetica", textColor=SLATE,
                                     alignment=TA_RIGHT)),
        ]]
        rt = Table(row_data, colWidths=[4 * cm, 9 * cm, 3.5 * cm])
        rt.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(rt)

    story.append(PageBreak())
    return story


def _build_gap_assessment(overall: dict, styles: dict) -> list:
    story = [Paragraph("Gap Assessment Detail", styles["section_heading"]),
             HRFlowable(width="100%", thickness=1.5, color=NAVY, spaceAfter=10)]

    for pillar_name, ps in overall["pillars"].items():
        story.append(Paragraph(pillar_name, styles["sub_heading"]))
        bar_color = PILLAR_COLORS.get(pillar_name, NAVY)
        story.append(_score_bar_table(ps["percentage"], bar_color, 16.5 * cm))
        story.append(Paragraph(
            f"{ps['percentage']:.0f}% – {ps['maturity_label']}  |  "
            f"{ps['met_count']} Met, {ps['partial_count']} Partial, "
            f"{ps['req_count'] - ps['met_count'] - ps['partial_count']} Not Met",
            styles["body_small"]))
        story.append(Spacer(1, 0.2 * cm))

        rows = [["Req ID", "Ref", "Requirement", "Status", "Notes"]]
        all_reqs = FRAMEWORK[pillar_name]["requirements"]
        pillar_key = {"Governance": "governance", "Strategy": "strategy",
                      "Risk Management": "risk_management", "Metrics & Targets": "metrics"}[pillar_name]

        from .framework import PILLAR_DATA_KEYS
        client_pillar = {}  # populated from overall dict via gaps + met items

        for req in all_reqs:
            rid = req["id"]
            # find gap entry or construct met entry
            gap = next((g for g in ps["gaps"] if g["id"] == rid), None)
            if gap:
                status = gap["status"]
                notes = gap["notes"]
            else:
                status = "met"
                notes = ""
            label = STATUS_LABELS.get(status, "Not Assessed")
            rows.append([
                Paragraph(rid, styles["table_cell"]),
                Paragraph(req["ref"], styles["table_cell"]),
                Paragraph(req["title"], styles["table_cell"]),
                Paragraph(label, ParagraphStyle("sl",
                    fontSize=8, fontName="Helvetica-Bold",
                    textColor=STATUS_PDF_COLORS.get(status, BLACK))),
                Paragraph(notes[:120] + ("…" if len(notes) > 120 else ""), styles["table_cell"]),
            ])

        col_w = [1.8 * cm, 1.8 * cm, 6.5 * cm, 2 * cm, 4.4 * cm]
        t = Table(rows, colWidths=col_w, repeatRows=1)
        ts = TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
            ("GRID", (0, 0), (-1, -1), 0.3, MID_GRAY),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ])
        # Colour status column cells
        for i, req in enumerate(all_reqs, start=1):
            rid = req["id"]
            gap = next((g for g in ps["gaps"] if g["id"] == rid), None)
            status = gap["status"] if gap else "met"
            bg = STATUS_PDF_BG.get(status, LIGHT_GRAY)
            ts.add("BACKGROUND", (3, i), (3, i), bg)
        t.setStyle(ts)
        story.append(t)
        story.append(Spacer(1, 0.4 * cm))

    story.append(PageBreak())
    return story


def _build_disclosures(client_data: dict, all_disclosures: dict, styles: dict) -> list:
    story = [Paragraph("Draft Disclosure Text", styles["section_heading"]),
             Paragraph(
                 "The following draft disclosure text is generated from the data entered. "
                 "It should be reviewed, refined and approved by management and the board "
                 "before inclusion in financial statements or sustainability reports.",
                 styles["body"]),
             HRFlowable(width="100%", thickness=1.5, color=NAVY, spaceAfter=10)]

    for pillar_name, disclosures in all_disclosures.items():
        story.append(Paragraph(pillar_name, styles["sub_heading"]))
        for disc in disclosures:
            block = [
                Paragraph(f"{disc['id']}  {disc['title']}  [{disc['ref']}]",
                          styles["req_heading"]),
                Paragraph(disc["text"].replace("\n", "<br/>"), styles["disclosure_text"]),
                Spacer(1, 0.15 * cm),
            ]
            story.append(KeepTogether(block))
        story.append(Spacer(1, 0.3 * cm))

    story.append(PageBreak())
    return story


def _build_roadmap(overall: dict, styles: dict) -> list:
    story = [Paragraph("Remediation Roadmap", styles["section_heading"]),
             Paragraph(
                 "Requirements below are ordered by priority (highest gap first). "
                 "Address Not Met items before Partial items to achieve the greatest "
                 "improvement in overall readiness.",
                 styles["body"]),
             HRFlowable(width="100%", thickness=1.5, color=NAVY, spaceAfter=10)]

    gaps = overall["priority_gaps"]
    if not gaps:
        story.append(Paragraph("All requirements are currently assessed as Met.", styles["body"]))
        return story

    rows = [["Priority", "Req ID", "Requirement", "Pillar", "Current Status", "Recommended Action"]]
    priority = 1
    for g in gaps:
        if not g["status"] or g["status"] == "not_met":
            action = "Develop disclosure and supporting documentation from scratch."
        else:
            action = "Enhance existing disclosure to address outstanding elements."
        rows.append([
            str(priority),
            Paragraph(g["id"], styles["table_cell"]),
            Paragraph(g["title"], styles["table_cell"]),
            Paragraph(g["id"].split("-")[0], styles["table_cell_center"]),
            Paragraph(STATUS_LABELS.get(g["status"], "Not Assessed"),
                      ParagraphStyle("rl", fontSize=8, fontName="Helvetica-Bold",
                                     textColor=STATUS_PDF_COLORS.get(g["status"], BLACK))),
            Paragraph(action, styles["table_cell"]),
        ])
        priority += 1

    col_w = [1.4 * cm, 1.8 * cm, 5 * cm, 1.5 * cm, 2 * cm, 4.8 * cm]
    t = Table(rows, colWidths=col_w, repeatRows=1)
    ts = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
        ("GRID", (0, 0), (-1, -1), 0.3, MID_GRAY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
    ])
    for i, g in enumerate(gaps, start=1):
        bg = STATUS_PDF_BG.get(g["status"], LIGHT_GRAY)
        ts.add("BACKGROUND", (4, i), (4, i), bg)
    t.setStyle(ts)
    story.append(t)
    return story


# ── Public API ─────────────────────────────────────────────────────────────────

def generate_pdf(client_data: dict) -> bytes:
    overall = score_overall(client_data)
    all_disclosures = generate_all_disclosures(client_data)
    styles = _make_styles()

    buf = BytesIO()

    hf = _HeaderFooter(
        client_data.get("client_name", ""),
        client_data.get("reporting_period", ""),
        styles,
    )

    margins = dict(leftMargin=1.5 * cm, rightMargin=1.5 * cm,
                   topMargin=1.8 * cm, bottomMargin=1.5 * cm)

    doc = BaseDocTemplate(buf, pagesize=A4, **margins)

    # Cover uses full-page frame (no header/footer margins needed – drawn in canvas)
    cover_frame = Frame(0, 0, W, H, leftPadding=2 * cm, rightPadding=2 * cm,
                        topPadding=0, bottomPadding=1.5 * cm)
    body_frame = Frame(margins["leftMargin"], margins["bottomMargin"] + 0.9 * cm,
                       W - margins["leftMargin"] - margins["rightMargin"],
                       H - margins["topMargin"] - 1.2 * cm - margins["bottomMargin"] - 0.9 * cm)

    doc.addPageTemplates([
        PageTemplate(id="cover", frames=[cover_frame], onPage=hf),
        PageTemplate(id="body", frames=[body_frame], onPage=hf),
    ])

    story = []
    story.extend(_build_cover(client_data, overall, styles))
    story.append(PageBreak())  # trigger switch to body template... handled via NextPageTemplate
    story.extend(_build_executive_summary(overall, styles))
    story.extend(_build_gap_assessment(overall, styles))
    story.extend(_build_disclosures(client_data, all_disclosures, styles))
    story.extend(_build_roadmap(overall, styles))

    # Switch to body template after cover
    from reportlab.platypus import NextPageTemplate
    story.insert(len(_build_cover(client_data, overall, styles)), NextPageTemplate("body"))

    doc.build(story)
    return buf.getvalue()
