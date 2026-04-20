"""Shared shape / layout helpers for docs/presentations pptx builders.

Both _build_pptx.py (TASK library-isation overview, 2026-04-19) and
_build_trlib_usage.py (trlib usage guide, 2026-04-20) used the same
8 helpers plus the same 16:9 widescreen canvas and the same
Japanese-first font choices. Extracting them here removes the
copy-paste so future presentations can import from here.
"""
from __future__ import annotations

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

COLOR_FORTRAN = RGBColor(0x1F, 0x4E, 0x79)   # 濃い青
COLOR_C_ABI = RGBColor(0x2E, 0x7D, 0x32)     # 緑
COLOR_PYTHON = RGBColor(0xEF, 0x6C, 0x00)    # オレンジ
COLOR_MCP = RGBColor(0x6A, 0x1B, 0x9A)       # 紫
COLOR_TOML = RGBColor(0x00, 0x69, 0x7C)      # ティール
COLOR_TEST = RGBColor(0xC6, 0x28, 0x28)      # 赤
COLOR_GRAY = RGBColor(0x55, 0x55, 0x55)
COLOR_LIGHT_GRAY = RGBColor(0xEE, 0xEE, 0xEE)
COLOR_CODE_BG = RGBColor(0xF5, 0xF5, 0xF5)
COLOR_BLACK = RGBColor(0x10, 0x10, 0x10)
COLOR_WHITE = RGBColor(0xFF, 0xFF, 0xFF)
COLOR_TITLE = RGBColor(0x0D, 0x47, 0xA1)
COLOR_ACCENT = RGBColor(0x1B, 0x5E, 0x20)

JP_FONT = "Noto Sans CJK JP"
MONO_FONT = "DejaVu Sans Mono"

SLIDE_W = Inches(13.333)  # 16:9 widescreen
SLIDE_H = Inches(7.5)


def set_slide_size(prs: Presentation) -> None:
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H


def add_textbox(
    slide,
    left,
    top,
    width,
    height,
    text: str,
    *,
    font_size: int = 14,
    bold: bool = False,
    color: RGBColor = COLOR_BLACK,
    align=PP_ALIGN.LEFT,
    font_name: str = JP_FONT,
    anchor=MSO_ANCHOR.TOP,
):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = Emu(36000)
    tf.margin_right = Emu(36000)
    tf.margin_top = Emu(18000)
    tf.margin_bottom = Emu(18000)
    tf.vertical_anchor = anchor
    lines = text.split("\n")
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        run = p.add_run()
        run.text = line
        run.font.size = Pt(font_size)
        run.font.bold = bold
        run.font.color.rgb = color
        run.font.name = font_name
    return box


def add_title_bar(slide, title: str, subtitle: str | None = None):
    """各スライド上部に薄い色帯 + タイトルを描画。"""
    bar = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, 0, 0, SLIDE_W, Inches(0.85)
    )
    bar.line.fill.background()
    bar.fill.solid()
    bar.fill.fore_color.rgb = COLOR_TITLE
    add_textbox(
        slide,
        Inches(0.4),
        Inches(0.12),
        SLIDE_W - Inches(0.8),
        Inches(0.65),
        title,
        font_size=26,
        bold=True,
        color=COLOR_WHITE,
        align=PP_ALIGN.LEFT,
        anchor=MSO_ANCHOR.MIDDLE,
    )
    if subtitle:
        add_textbox(
            slide,
            Inches(0.4),
            Inches(0.92),
            SLIDE_W - Inches(0.8),
            Inches(0.4),
            subtitle,
            font_size=14,
            color=COLOR_GRAY,
            align=PP_ALIGN.LEFT,
        )


def add_box(
    slide,
    left,
    top,
    width,
    height,
    title: str,
    subtitle: str = "",
    *,
    fill: RGBColor = COLOR_FORTRAN,
    text_color: RGBColor = COLOR_WHITE,
    title_size: int = 16,
    sub_size: int = 11,
    shape=MSO_SHAPE.ROUNDED_RECTANGLE,
):
    """角丸長方形に Bold タイトル + 補足を描画。"""
    box = slide.shapes.add_shape(shape, left, top, width, height)
    box.fill.solid()
    box.fill.fore_color.rgb = fill
    box.line.color.rgb = RGBColor(0x33, 0x33, 0x33)
    box.line.width = Pt(0.75)
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = Emu(36000)
    tf.margin_right = Emu(36000)
    tf.margin_top = Emu(36000)
    tf.margin_bottom = Emu(36000)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = title
    r.font.size = Pt(title_size)
    r.font.bold = True
    r.font.color.rgb = text_color
    r.font.name = JP_FONT
    if subtitle:
        for line in subtitle.split("\n"):
            p2 = tf.add_paragraph()
            p2.alignment = PP_ALIGN.CENTER
            r2 = p2.add_run()
            r2.text = line
            r2.font.size = Pt(sub_size)
            r2.font.color.rgb = text_color
            r2.font.name = JP_FONT
    return box


def add_arrow(
    slide,
    start_box,
    end_box,
    *,
    label: str | None = None,
    label_offset_y: float = -0.25,
):
    """2 つの shape を矢印で接続。中央寄りの辺を自動推定して結ぶ。"""
    sx = start_box.left + start_box.width // 2
    sy = start_box.top + start_box.height // 2
    ex = end_box.left + end_box.width // 2
    ey = end_box.top + end_box.height // 2
    dx = ex - sx
    dy = ey - sy
    # 主軸方向の判定
    if abs(dx) >= abs(dy):
        # 横方向
        if dx >= 0:
            x1 = start_box.left + start_box.width
            x2 = end_box.left
        else:
            x1 = start_box.left
            x2 = end_box.left + end_box.width
        y1 = sy
        y2 = ey
    else:
        if dy >= 0:
            y1 = start_box.top + start_box.height
            y2 = end_box.top
        else:
            y1 = start_box.top
            y2 = end_box.top + end_box.height
        x1 = sx
        x2 = ex
    conn = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, x1, y1, x2, y2)
    conn.line.color.rgb = COLOR_GRAY
    conn.line.width = Pt(2.0)
    # 矢じりを終端に
    line = conn.line
    line_elem = line._get_or_add_ln()
    from pptx.oxml.ns import qn
    from lxml import etree

    tail = etree.SubElement(line_elem, qn("a:tailEnd"))
    tail.set("type", "triangle")
    tail.set("w", "med")
    tail.set("len", "med")

    if label:
        mid_x = (x1 + x2) // 2
        mid_y = (y1 + y2) // 2
        add_textbox(
            slide,
            mid_x - Inches(0.9),
            mid_y + Inches(label_offset_y),
            Inches(1.8),
            Inches(0.3),
            label,
            font_size=10,
            color=COLOR_GRAY,
            align=PP_ALIGN.CENTER,
        )
    return conn


def add_code_block(
    slide,
    left,
    top,
    width,
    height,
    code: str,
    *,
    font_size: int = 12,
    title: str | None = None,
):
    """薄いグレー背景に monospace でコードを表示。"""
    bg = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, left, top, width, height
    )
    bg.fill.solid()
    bg.fill.fore_color.rgb = COLOR_CODE_BG
    bg.line.color.rgb = RGBColor(0xCC, 0xCC, 0xCC)
    bg.line.width = Pt(0.75)
    tf = bg.text_frame
    tf.word_wrap = True
    tf.margin_left = Emu(72000)
    tf.margin_right = Emu(72000)
    tf.margin_top = Emu(54000)
    tf.margin_bottom = Emu(54000)
    tf.vertical_anchor = MSO_ANCHOR.TOP
    p = tf.paragraphs[0]
    if title:
        r = p.add_run()
        r.text = title
        r.font.size = Pt(font_size + 1)
        r.font.bold = True
        r.font.color.rgb = COLOR_GRAY
        r.font.name = JP_FONT
        # When title is set, the first code line gets a fresh paragraph
        # (don't reuse the title paragraph).
    lines = code.split("\n")
    for i, line in enumerate(lines):
        if i == 0 and title is None:
            p_use = p
        else:
            p_use = tf.add_paragraph()
        r = p_use.add_run()
        r.text = line if line else " "
        r.font.size = Pt(font_size)
        r.font.color.rgb = COLOR_BLACK
        r.font.name = MONO_FONT
    return bg


def add_table(
    slide,
    left,
    top,
    width,
    height,
    rows: list[list[str]],
    *,
    header: bool = True,
    font_size: int = 12,
    header_fill: RGBColor = COLOR_TITLE,
):
    n_rows = len(rows)
    n_cols = len(rows[0]) if rows else 0
    if n_rows == 0 or n_cols == 0:
        return None
    tbl_shape = slide.shapes.add_table(n_rows, n_cols, left, top, width, height)
    tbl = tbl_shape.table
    for i, row in enumerate(rows):
        for j, val in enumerate(row):
            cell = tbl.cell(i, j)
            cell.text = ""
            tf = cell.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.LEFT
            r = p.add_run()
            r.text = val
            r.font.size = Pt(font_size)
            r.font.name = JP_FONT
            if header and i == 0:
                r.font.bold = True
                r.font.color.rgb = COLOR_WHITE
                cell.fill.solid()
                cell.fill.fore_color.rgb = header_fill
            else:
                r.font.color.rgb = COLOR_BLACK
                cell.fill.solid()
                if i % 2 == 0:
                    cell.fill.fore_color.rgb = COLOR_LIGHT_GRAY
                else:
                    cell.fill.fore_color.rgb = COLOR_WHITE
    return tbl


def add_speaker_notes(slide, notes: str) -> None:
    notes_slide = slide.notes_slide
    tf = notes_slide.notes_text_frame
    tf.text = notes


def add_bullets(slide, left, top, width, height, bullets: list[str], *, font_size: int = 16):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = Emu(36000)
    tf.margin_right = Emu(36000)
    tf.margin_top = Emu(18000)
    tf.margin_bottom = Emu(18000)
    for i, line in enumerate(bullets):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.LEFT
        p.level = 0
        r = p.add_run()
        r.text = "・ " + line
        r.font.size = Pt(font_size)
        r.font.color.rgb = COLOR_BLACK
        r.font.name = JP_FONT
        p.space_after = Pt(6)
    return box


__all__ = [
    "COLOR_FORTRAN", "COLOR_C_ABI", "COLOR_PYTHON", "COLOR_MCP",
    "COLOR_TOML", "COLOR_TEST", "COLOR_GRAY", "COLOR_LIGHT_GRAY",
    "COLOR_CODE_BG", "COLOR_BLACK", "COLOR_WHITE", "COLOR_TITLE",
    "COLOR_ACCENT", "JP_FONT", "MONO_FONT", "SLIDE_W", "SLIDE_H",
    "set_slide_size", "add_textbox", "add_title_bar", "add_box",
    "add_arrow", "add_code_block", "add_table", "add_speaker_notes",
    "add_bullets",
]
