"""TASK リポジトリ フォルダ棚卸しスライド (日本語, 2026-06-09)。

実行方法::

    python3 docs/slides/build_folder_inventory_2026_06_09.py

出力: docs/slides/2026-06-09-task-folder-inventory.pptx
"""
from pathlib import Path

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

from build_slides import (
    SLIDE_W,
    SLIDE_H,
    COLOR_TITLE,
    COLOR_ACCENT,
    COLOR_TEXT,
    COLOR_DIM,
    add_title_bar,
    add_text_block,
    add_table,
    set_jp_font,
)

DECK_TAG = "TASK リポジトリ フォルダ棚卸し 2026-06-09"


def add_deck_footer(slide, page_no, total_pages):
    box = slide.shapes.add_textbox(
        Inches(0.3), Inches(7.05), Inches(12.7), Inches(0.35)
    )
    tf = box.text_frame
    tf.margin_top = Inches(0)
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.RIGHT
    r = p.add_run()
    r.text = f"{DECK_TAG} — {page_no} / {total_pages}"
    set_jp_font(r, size=10, color=COLOR_DIM)


def add_bullets_v2(slide, bullets, top, left=Inches(0.6),
                   width=Inches(12.1), height=Inches(5.6),
                   size=18, vertical_anchor=None):
    """空文字列を「バレット記号無しの小さなスペーサ段落」として扱うバレット描画。"""
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    if vertical_anchor is not None:
        tf.vertical_anchor = vertical_anchor
    first = True
    for item in bullets:
        if isinstance(item, tuple):
            text, level = item
        else:
            text, level = item, 0
            if text.startswith("  - "):
                level = 1
                text = text[4:]
            elif text.startswith("- "):
                text = text[2:]
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.level = level
        p.alignment = PP_ALIGN.LEFT
        if not text.strip():
            r = p.add_run()
            r.text = " "
            set_jp_font(r, size=8)
            continue
        prefix = "  " * level + ("• " if level == 0 else "– ")
        r = p.add_run()
        r.text = prefix + text
        set_jp_font(r, size=size - 2 * level)


# ---- スライド本体 ----------------------------------------------------------


def slide_title(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    bar = s.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, 0, Inches(1.9), SLIDE_W, Inches(2.7)
    )
    bar.line.fill.background()
    bar.fill.solid()
    bar.fill.fore_color.rgb = COLOR_TITLE
    add_text_block(
        s,
        ["TASK リポジトリ",
         "フォルダ棚卸し & 整理方針"],
        top=Inches(2.2), left=Inches(0.8), width=Inches(11.7),
        height=Inches(2.0), size=38,
        color=RGBColor(0xFF, 0xFF, 0xFF), bold=True,
    )
    add_text_block(
        s,
        ["— まず棚卸し: 約60個のトップレベルフォルダを分類。物理移動はしない —"],
        top=Inches(4.8), left=Inches(0.8), width=Inches(11.7),
        height=Inches(0.6), size=16, color=COLOR_ACCENT,
    )
    line = s.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(0.8), Inches(5.6), Inches(2.5), Inches(0.05),
    )
    line.line.fill.background()
    line.fill.solid()
    line.fill.fore_color.rgb = COLOR_ACCENT
    add_text_block(
        s,
        ["吉見一慶 (東京大学)",
         "2026-06-09"],
        top=Inches(5.8), left=Inches(0.8), width=Inches(11.7),
        height=Inches(1.0), size=14,
        color=RGBColor(0x55, 0x55, 0x55),
    )
    return s


# ---- メイン ----------------------------------------------------------------


BUILDERS = [
    slide_title,
]


def build():
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H

    total = len(BUILDERS)
    for i, builder in enumerate(BUILDERS, start=1):
        s = builder(prs)
        if i > 1:  # 表紙にはフッタを付けない
            add_deck_footer(s, i, total)

    out = Path(__file__).parent / "2026-06-09-task-folder-inventory.pptx"
    prs.save(out)
    print(f"Wrote {out} ({total} slides)")
    return out


if __name__ == "__main__":
    build()
