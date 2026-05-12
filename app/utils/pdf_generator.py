"""
app/utils/pdf_generator.py
───────────────────────────
Auto-generates a professional portfolio PDF using ReportLab.

The PDF is saved to /tmp/portfolios/<portfolio_id>.pdf
In production replace with S3 upload after generation.

Layout (industry-aware):
    Page 1: Hero — name, tagline, profile photo, social stats, bio
    Page 2: Stats card — physical (fashion) OR creator stats (YouTube)
            + custom fields
    Page 3+: Portfolio items — images and brand collab cards

Font stack: Helvetica (always available, no download needed).
Color palette: Deep Navy (#1a1a2e) + Gold (#d4af37) — premium feel.
"""

import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

# ── Ensure output directory exists ────────────────────────────────────────────
PDF_DIR = "/tmp/furies_portfolios"
os.makedirs(PDF_DIR, exist_ok=True)

# ── Brand colours ─────────────────────────────────────────────────────────────
NAVY  = colors.HexColor("#1a1a2e")
GOLD  = colors.HexColor("#d4af37")
LIGHT = colors.HexColor("#f5f5f5")
MID   = colors.HexColor("#888888")
WHITE = colors.white
BLACK = colors.black


def _styles():
    base = getSampleStyleSheet()
    return {
        "name": ParagraphStyle(
            "name", fontName="Helvetica-Bold", fontSize=28,
            textColor=NAVY, spaceAfter=4, alignment=TA_CENTER,
        ),
        "tagline": ParagraphStyle(
            "tagline", fontName="Helvetica-Oblique", fontSize=13,
            textColor=GOLD, spaceAfter=8, alignment=TA_CENTER,
        ),
        "section_head": ParagraphStyle(
            "section_head", fontName="Helvetica-Bold", fontSize=14,
            textColor=NAVY, spaceBefore=14, spaceAfter=6,
            borderPad=4,
        ),
        "body": ParagraphStyle(
            "body", fontName="Helvetica", fontSize=10,
            textColor=BLACK, spaceAfter=4, leading=16,
        ),
        "label": ParagraphStyle(
            "label", fontName="Helvetica-Bold", fontSize=9,
            textColor=MID, spaceAfter=2,
        ),
        "value": ParagraphStyle(
            "value", fontName="Helvetica", fontSize=10,
            textColor=NAVY, spaceAfter=4,
        ),
        "footer": ParagraphStyle(
            "footer", fontName="Helvetica", fontSize=8,
            textColor=MID, alignment=TA_CENTER,
        ),
    }


def _stat_table(rows: list[tuple[str, str]]) -> Table:
    """
    Renders a clean two-column label/value table.
    rows = [("Height", "175 cm"), ("Weight", "62 kg"), ...]
    """
    data = [[Paragraph(label, ParagraphStyle("l", fontName="Helvetica-Bold",
                        fontSize=9, textColor=MID)),
             Paragraph(str(value), ParagraphStyle("v", fontName="Helvetica",
                        fontSize=10, textColor=NAVY))]
            for label, value in rows]

    t = Table(data, colWidths=[5.5 * cm, 10 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [WHITE, LIGHT]),
        ("GRID",      (0, 0), (-1, -1), 0.3, colors.HexColor("#dddddd")),
        ("LEFTPADDING",  (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING",   (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 6),
    ]))
    return t


def generate_portfolio_pdf(portfolio) -> str:
    """
    Generate a PDF for the given Portfolio ORM object.
    Returns the file path of the saved PDF.

    portfolio: Portfolio ORM instance with all relationships loaded
               (items, physical_stats, creator_stats, custom_fields)
    """
    file_path = os.path.join(PDF_DIR, f"{portfolio.id}.pdf")
    doc = SimpleDocTemplate(
        file_path,
        pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm,  bottomMargin=2 * cm,
    )

    S = _styles()
    W = A4[0] - 4 * cm   # usable page width
    story = []

    # ─── PAGE 1: HERO ─────────────────────────────────────────────────────────

    # Gold top bar
    story.append(HRFlowable(width=W, thickness=4, color=GOLD, spaceAfter=12))

    # Furies platform branding
    story.append(Paragraph(
        "<font color='#d4af37'>FURIES</font> — Creator Portfolio",
        ParagraphStyle("brand", fontName="Helvetica-Bold", fontSize=10,
                       textColor=MID, alignment=TA_RIGHT, spaceAfter=8)
    ))

    # Name + tagline
    story.append(Paragraph(portfolio.display_name, S["name"]))
    if portfolio.tagline:
        story.append(Paragraph(portfolio.tagline, S["tagline"]))

    # Industry badge
    story.append(Paragraph(
        portfolio.industry_type.value.replace("_", " ").upper(),
        ParagraphStyle("badge", fontName="Helvetica-Bold", fontSize=11,
                       textColor=WHITE,
                       backColor=NAVY, alignment=TA_CENTER,
                       borderPad=6, spaceAfter=12),
    ))

    # Location
    location_parts = [p for p in [portfolio.city, portfolio.state, portfolio.country] if p]
    if location_parts:
        story.append(Paragraph(
            "📍 " + ", ".join(location_parts),
            ParagraphStyle("loc", fontName="Helvetica", fontSize=10,
                           textColor=MID, alignment=TA_CENTER, spaceAfter=8)
        ))

    story.append(HRFlowable(width=W, thickness=1, color=colors.HexColor("#dddddd"), spaceAfter=12))

    # Bio
    if portfolio.bio:
        story.append(Paragraph("About", S["section_head"]))
        story.append(Paragraph(portfolio.bio, S["body"]))

    # Social links
    social_links = [
        ("Instagram", portfolio.instagram_url),
        ("YouTube",   portfolio.youtube_url),
        ("Twitter/X", portfolio.twitter_url),
        ("TikTok",    portfolio.tiktok_url),
        ("Website",   portfolio.website_url),
    ]
    social_rows = [(label, url) for label, url in social_links if url]
    if social_rows:
        story.append(Paragraph("Social & Links", S["section_head"]))
        story.append(_stat_table(social_rows))

    story.append(PageBreak())

    # ─── PAGE 2: STATS CARD ───────────────────────────────────────────────────

    story.append(HRFlowable(width=W, thickness=4, color=GOLD, spaceAfter=12))
    story.append(Paragraph(f"{portfolio.display_name} — Stats & Details", S["section_head"]))

    # Physical stats (fashion / modelling)
    ps = portfolio.physical_stats
    if ps:
        story.append(Paragraph("Physical Measurements", S["section_head"]))
        phys_rows = []
        if ps.height_cm:       phys_rows.append(("Height",       f"{ps.height_cm} cm"))
        if ps.weight_kg:       phys_rows.append(("Weight",       f"{ps.weight_kg} kg"))
        if ps.bust_cm:         phys_rows.append(("Bust",         f"{ps.bust_cm} cm"))
        if ps.waist_cm:        phys_rows.append(("Waist",        f"{ps.waist_cm} cm"))
        if ps.hips_cm:         phys_rows.append(("Hips",         f"{ps.hips_cm} cm"))
        if ps.shoe_size_eu:    phys_rows.append(("Shoe Size (EU)", str(ps.shoe_size_eu)))
        if ps.dress_size:      phys_rows.append(("Dress Size",   ps.dress_size))
        if ps.skin_tone:       phys_rows.append(("Skin Tone",    ps.skin_tone.value.title()))
        if ps.hair_color:      phys_rows.append(("Hair Color",   ps.hair_color.value.title()))
        if ps.eye_color:       phys_rows.append(("Eye Color",    ps.eye_color.value.title()))
        if ps.years_experience:phys_rows.append(("Experience",   f"{ps.years_experience} years"))
        if ps.languages:       phys_rows.append(("Languages",    ps.languages))
        phys_rows.append(("Willing to Travel", "Yes" if ps.willing_to_travel else "No"))
        if phys_rows:
            story.append(_stat_table(phys_rows))

    # Creator stats (YouTube / Instagram)
    cs = portfolio.creator_stats
    if cs:
        story.append(Paragraph("Creator Statistics", S["section_head"]))
        cr_rows = []
        if cs.primary_platform:       cr_rows.append(("Primary Platform",    cs.primary_platform))
        if cs.subscriber_count:       cr_rows.append(("Subscribers/Followers",
                                                       f"{cs.subscriber_count:,}"))
        if cs.avg_views_per_video:    cr_rows.append(("Avg Views / Video",
                                                       f"{cs.avg_views_per_video:,}"))
        if cs.avg_likes_per_post:     cr_rows.append(("Avg Likes / Post",
                                                       f"{cs.avg_likes_per_post:,}"))
        if cs.avg_comments:           cr_rows.append(("Avg Comments",
                                                       f"{cs.avg_comments:,}"))
        if cs.posting_frequency:      cr_rows.append(("Posting Frequency",   cs.posting_frequency))
        if cs.audience_age_range:     cr_rows.append(("Audience Age Range",  cs.audience_age_range))
        if cs.audience_gender_split:  cr_rows.append(("Audience Gender",     cs.audience_gender_split))
        if cs.top_audience_countries: cr_rows.append(("Top Countries",       cs.top_audience_countries))
        if cs.content_categories:     cr_rows.append(("Content Categories",  cs.content_categories))
        if cs.collab_types_offered:   cr_rows.append(("Collab Types",        cs.collab_types_offered))
        if cr_rows:
            story.append(_stat_table(cr_rows))

    # Custom fields
    if portfolio.custom_fields:
        public_fields = [f for f in portfolio.custom_fields if f.is_public]
        if public_fields:
            story.append(Paragraph("Additional Details", S["section_head"]))
            custom_rows = [(f.field_name, f.field_value)
                           for f in sorted(public_fields, key=lambda x: x.display_order)]
            story.append(_stat_table(custom_rows))

    story.append(PageBreak())

    # ─── PAGE 3+: PORTFOLIO ITEMS ─────────────────────────────────────────────

    if portfolio.items:
        story.append(HRFlowable(width=W, thickness=4, color=GOLD, spaceAfter=12))
        story.append(Paragraph("Portfolio & Past Work", S["section_head"]))
        story.append(Spacer(1, 0.3 * cm))

        sorted_items = sorted(portfolio.items, key=lambda x: x.display_order)
        for item in sorted_items:
            # Item type badge
            type_label = item.item_type.value.replace("_", " ").upper()
            story.append(Paragraph(
                type_label,
                ParagraphStyle("item_badge", fontName="Helvetica-Bold", fontSize=8,
                               textColor=GOLD, spaceAfter=2),
            ))

            if item.title:
                story.append(Paragraph(item.title, ParagraphStyle(
                    "item_title", fontName="Helvetica-Bold", fontSize=12,
                    textColor=NAVY, spaceAfter=4,
                )))

            if item.brand_name:
                story.append(Paragraph(f"Brand: {item.brand_name}", S["label"]))

            if item.description:
                story.append(Paragraph(item.description, S["body"]))

            if item.media_url:
                story.append(Paragraph(f"🔗 {item.media_url}", ParagraphStyle(
                    "link", fontName="Helvetica", fontSize=9,
                    textColor=colors.HexColor("#0066cc"), spaceAfter=4,
                )))

            if item.results:
                story.append(Paragraph(f"Results: {item.results}", ParagraphStyle(
                    "results", fontName="Helvetica-Bold", fontSize=10,
                    textColor=colors.HexColor("#2e7d32"), spaceAfter=4,
                )))

            if item.collab_date:
                story.append(Paragraph(
                    f"Date: {item.collab_date.strftime('%B %Y')}",
                    S["label"],
                ))

            story.append(HRFlowable(width=W, thickness=0.5,
                          color=colors.HexColor("#eeeeee"), spaceAfter=10))

    # ─── FOOTER ────────────────────────────────────────────────────────────────
    generated = datetime.now(timezone.utc).strftime("%d %B %Y, %H:%M UTC")
    story.append(Spacer(1, 1 * cm))
    story.append(HRFlowable(width=W, thickness=1, color=GOLD, spaceAfter=6))
    story.append(Paragraph(
        f"Generated by Furies Platform · {generated} · furies.app",
        S["footer"],
    ))

    doc.build(story)
    return file_path
