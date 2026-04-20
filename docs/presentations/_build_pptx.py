"""TASK ライブラリ化プロジェクト 20 分プレゼン用 pptx を生成。

`python-pptx` の shape API を使い、図入りスライド (アーキテクチャ図、
テスト 4 層、TOML runner、MCP フロー) を含む 18 枚のスライドを構築します。
本文・タイトル・スピーカーノートはすべて日本語 (です・ます調) です。

Run:
    python3 docs/presentations/_build_pptx.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow ``python3 docs/presentations/_build_pptx.py`` (run from repo root)
# to pick up the sibling ``_pptx_helpers`` module without an __init__.py.
sys.path.insert(0, str(Path(__file__).resolve().parent))


from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

# ---------------------------------------------------------------------------
# 配色・フォント・ヘルパーは _pptx_helpers に集約 (docs/presentations 共有)。
# ---------------------------------------------------------------------------
from _pptx_helpers import (  # noqa: F401 (re-exported for module-level use)
    COLOR_FORTRAN, COLOR_C_ABI, COLOR_PYTHON, COLOR_MCP,
    COLOR_TOML, COLOR_TEST, COLOR_GRAY, COLOR_LIGHT_GRAY,
    COLOR_CODE_BG, COLOR_BLACK, COLOR_WHITE, COLOR_TITLE,
    COLOR_ACCENT, JP_FONT, MONO_FONT, SLIDE_W, SLIDE_H,
    set_slide_size, add_textbox, add_title_bar, add_box,
    add_arrow, add_code_block, add_table, add_speaker_notes,
    add_bullets,
)


# ---------------------------------------------------------------------------
# Slide builders
# ---------------------------------------------------------------------------


def build_slide_01_title(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank
    # 背景バー
    bg = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, 0, 0, SLIDE_W, SLIDE_H
    )
    bg.fill.solid()
    bg.fill.fore_color.rgb = RGBColor(0xF7, 0xFA, 0xFC)
    bg.line.fill.background()
    # タイトル帯
    band = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, 0, Inches(2.4), SLIDE_W, Inches(2.3)
    )
    band.fill.solid()
    band.fill.fore_color.rgb = COLOR_TITLE
    band.line.fill.background()

    add_textbox(
        slide,
        Inches(0.5),
        Inches(2.55),
        SLIDE_W - Inches(1.0),
        Inches(1.2),
        "TASK プラズマ輸送コード\nライブラリ化プロジェクト",
        font_size=40,
        bold=True,
        color=COLOR_WHITE,
        align=PP_ALIGN.CENTER,
    )
    add_textbox(
        slide,
        Inches(0.5),
        Inches(3.95),
        SLIDE_W - Inches(1.0),
        Inches(0.6),
        "変更内容と使い方",
        font_size=24,
        color=COLOR_WHITE,
        align=PP_ALIGN.CENTER,
    )

    add_textbox(
        slide,
        Inches(0.5),
        Inches(5.0),
        SLIDE_W - Inches(1.0),
        Inches(0.5),
        "発表日: 2026 年 4 月 19 日",
        font_size=16,
        color=COLOR_GRAY,
        align=PP_ALIGN.CENTER,
    )
    add_textbox(
        slide,
        Inches(0.5),
        Inches(5.5),
        SLIDE_W - Inches(1.0),
        Inches(0.5),
        "発表者: <発表者名> (東京大学)",
        font_size=16,
        color=COLOR_GRAY,
        align=PP_ALIGN.CENTER,
    )
    add_textbox(
        slide,
        Inches(0.5),
        Inches(6.6),
        SLIDE_W - Inches(1.0),
        Inches(0.4),
        "Phase L-0 〜 L-7 / Phase F-1 〜 F-5 / MCP サーバ / 96 PR merge",
        font_size=12,
        color=COLOR_GRAY,
        align=PP_ALIGN.CENTER,
    )

    add_speaker_notes(
        slide,
        "(想定 30 秒) こんにちは。本日は TASK プラズマ輸送コードのライブラリ化プロジェクトについて、"
        "「どのような変更を入れたのか」と「どのように使えるのか」を 20 分でお話しします。"
        "対象は tr / fp / ti / wr / wrx / eq / tot の 7 モジュールで、約 86 件の PR をマージしています。"
        "途中で立ち止まりたい場合や、後ほど質問がある場合は最後にまとめて受け付けますので、お気軽にお声がけください。",
    )


def build_slide_02_motivation(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_title_bar(slide, "背景・モチベーション", "なぜ TASK をライブラリ化するのか")

    add_bullets(
        slide,
        Inches(0.5),
        Inches(1.2),
        Inches(7.0),
        Inches(5.2),
        [
            "TASK は CLI ベースの Fortran コードで、対話メニュー + namelist 入力が前提です。",
            "Python から呼びたい (パラメータスイープ・最適化・データ同化など)。",
            "Jupyter / matplotlib / numpy など Python エコシステムと組み合わせたい。",
            "LLM (Claude / Cursor) から自然言語で計算を起動したい (MCP)。",
            "回帰テストを自動化し、改修時の数値安全性を機械的に保証したい。",
            "既存の CLI バイナリ (tr2 など) を壊さず、追加機能として提供したい。",
        ],
        font_size=16,
    )

    # 右側に Before / After のミニ図
    add_box(
        slide,
        Inches(8.0),
        Inches(1.5),
        Inches(4.8),
        Inches(2.2),
        "Before",
        "Fortran CLI のみ\n対話メニュー + namelist\nスクリプト化が困難",
        fill=COLOR_GRAY,
        title_size=16,
        sub_size=12,
    )
    add_box(
        slide,
        Inches(8.0),
        Inches(4.0),
        Inches(4.8),
        Inches(2.6),
        "After",
        "lib<X>api.so + Python ラッパ\n+ MCP サーバで LLM からも操作\nCLI バイナリは従来どおり",
        fill=COLOR_ACCENT,
        title_size=16,
        sub_size=12,
    )

    add_speaker_notes(
        slide,
        "(想定 1 分) これまでの TASK は、tr2 や fp などの CLI バイナリと、namelist で起動する形が基本でした。"
        "ところが、現代的な利用法としてはパラメータスイープや機械学習との結合が増えており、"
        "Python から呼べる API が必須となります。さらに最近は LLM クライアント (Claude や Cursor) からの"
        "自然言語呼び出しの需要も高まっています。今回のライブラリ化プロジェクトはこれらに応えるためのものです。"
        "重要なのは、既存の CLI バイナリは一切壊さず、追加機能として共有ライブラリと Python ラッパを提供している点です。",
    )


def build_slide_03_modules(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_title_bar(slide, "対象モジュール一覧", "tr / fp / ti / wr / wrx / eq / tot の 7 モジュール")

    rows = [
        ["モジュール", "役割", "L-0..L-7", "Phase F", "MCP", "備考"],
        ["tr", "1 次元輸送", "完了", "(対象外)", "完了", "リファレンス実装"],
        ["fp", "Fokker-Planck 解析", "完了", "(対象外)", "完了", "fp_finalize に既知問題"],
        ["ti", "不純物輸送", "完了", "(対象外)", "完了", "PA 配列で原子質量設定"],
        ["wr", "波動レイトレーシング", "完了", "(対象外)", "完了", "Bugbot HIGH 修正済み"],
        ["wrx", "拡張レイトレーシング", "完了", "(対象外)", "完了", "wr のスーパセット"],
        ["eq", "MHD 平衡", "完了", "F-1..F-5 完了", "未着手", "F90 modernization も完了"],
        ["tot", "統合輸送", "完了", "(対象外)", "完了", "namespace dispatch (eq:RR 等)"],
    ]
    add_table(
        slide,
        Inches(0.5),
        Inches(1.3),
        Inches(12.3),
        Inches(5.4),
        rows,
        font_size=14,
    )

    add_textbox(
        slide,
        Inches(0.5),
        Inches(6.85),
        Inches(12.3),
        Inches(0.5),
        "凡例: 「完了」= L-0 から L-7 まで develop merged。「未着手」= follow-up PR 予定。",
        font_size=11,
        color=COLOR_GRAY,
    )

    add_speaker_notes(
        slide,
        "(想定 1 分) 対象は 7 モジュールすべてが Phase L-0 から L-7、そして MCP サーバまで完了しました。"
        "eq は MHD 平衡計算で、F77 のレガシーコードが多かったため、Phase F (F-1..F-5 で F90 化 + shim 削除) も完了。"
        "tot は他 6 モジュールを namespace prefix (eq: / tr: 等) で束ねるオーケストレータで、L-5 Python wrapper + MCP まで完成。"
        "残作業は trlib の plot+TOML runner を他モジュールに横展開する作業のみ (スライド 15 参照)。",
    )


def build_slide_04_architecture(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_title_bar(slide, "アーキテクチャ全体図", "Fortran 計算本体 → C ABI → Python → MCP の 4 層構成")

    # 左から右に流れる横方向アーキ図
    box_w = Inches(2.6)
    box_h = Inches(1.5)
    y = Inches(2.6)

    # 4 つの層を横に並べる
    fortran_box = add_box(
        slide,
        Inches(0.4),
        y,
        box_w,
        box_h,
        "Fortran 計算本体",
        "tr / fp / ti / wr / wrx\n/ eq / tot\nCOMMON ブロック保持",
        fill=COLOR_FORTRAN,
        title_size=15,
        sub_size=11,
    )
    cabi_box = add_box(
        slide,
        Inches(3.5),
        y,
        box_w,
        box_h,
        "C ABI (BIND(C))",
        "lib<X>api.so\n5 関数 (init/set/run\n/get_state/finalize)",
        fill=COLOR_C_ABI,
        title_size=15,
        sub_size=11,
    )
    py_box = add_box(
        slide,
        Inches(6.6),
        y,
        box_w,
        box_h,
        "Python ラッパ",
        "python/<X>lib/\nctypes + dataclass\n例外階層 4 種",
        fill=COLOR_PYTHON,
        title_size=15,
        sub_size=11,
    )
    mcp_box = add_box(
        slide,
        Inches(9.7),
        y,
        box_w,
        box_h,
        "MCP サーバ",
        "python/mcp-servers/\n<X>_mcp/\n9 ツール / JSON-RPC",
        fill=COLOR_MCP,
        title_size=15,
        sub_size=11,
    )

    add_arrow(slide, fortran_box, cabi_box, label="BIND(C, NAME=...)")
    add_arrow(slide, cabi_box, py_box, label="ctypes (RTLD_LAZY)")
    add_arrow(slide, py_box, mcp_box, label="FastMCP")

    # 下段: ユーザのエントリポイント
    add_box(
        slide,
        Inches(0.4),
        Inches(5.0),
        box_w,
        Inches(0.9),
        "CLI バイナリ",
        "tr2 / fp / ti / ...\n(従来どおり)",
        fill=COLOR_GRAY,
        title_size=13,
        sub_size=10,
    )
    add_box(
        slide,
        Inches(3.5),
        Inches(5.0),
        box_w,
        Inches(0.9),
        "C / C++ ホスト",
        "ヘッダ <X>_api.h\nを直接 include",
        fill=COLOR_GRAY,
        title_size=13,
        sub_size=10,
    )
    add_box(
        slide,
        Inches(6.6),
        Inches(5.0),
        box_w,
        Inches(0.9),
        "Python スクリプト",
        "Jupyter / sweep\n/ 最適化",
        fill=COLOR_GRAY,
        title_size=13,
        sub_size=10,
    )
    add_box(
        slide,
        Inches(9.7),
        Inches(5.0),
        box_w,
        Inches(0.9),
        "LLM クライアント",
        "Claude / Cursor\nClaude Desktop",
        fill=COLOR_GRAY,
        title_size=13,
        sub_size=10,
    )

    add_textbox(
        slide,
        Inches(0.4),
        Inches(6.2),
        Inches(12.6),
        Inches(0.9),
        "色: 青=Fortran (kernel) / 緑=C ABI / オレンジ=Python / 紫=MCP / 灰=利用側エントリ。\n"
        "上段が「ライブラリ層」、下段が「利用側」です。CLI バイナリは並列に維持されます。",
        font_size=12,
        color=COLOR_GRAY,
    )

    add_speaker_notes(
        slide,
        "(想定 1 分 30 秒) こちらが今回のアーキテクチャの全体像です。"
        "左から右に向かって、Fortran 計算本体 → C ABI → Python ラッパ → MCP サーバの 4 層構成になっています。"
        "各層は色分けしており、青が Fortran、緑が C ABI、オレンジが Python、紫が MCP です。"
        "下段は利用側のエントリポイントで、従来の CLI バイナリも並列に維持しています。"
        "つまり Fortran のコア計算は唯一の真実のソースで、それを C ABI で薄く包み、Python で扱いやすくし、"
        "最終的に LLM からも触れる、というレイヤ構造になっています。",
    )


def build_slide_05_phase_l(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_title_bar(slide, "Phase L 概要 (8 フェーズ)", "L-0 baseline から L-7 docs まで段階的に積み上げ")

    rows = [
        ["フェーズ", "内容", "成果物"],
        ["L-0", "回帰テスト基盤 (env-guarded baseline dump)", "test_run/baselines/<mod>_<case>/"],
        ["L-1", "Makefile 分割 (CORE / GRAPHICS / MENU)", "<mod>/Makefile (CLI バイナリは bit 同一)"],
        ["L-2", "C ABI 雛形 (5 BIND(C) 関数 + ヘッダ)", "<mod>_api.f90 / <mod>_api.h"],
        ["L-3", "パラメータレジストリ + 実装", "<mod>_param_registry.f90 (~35 SELECT CASE)"],
        ["L-4", ".so 共有ライブラリビルド (PIC 化)", "<mod>/lib<mod>api.so + lib*_pic.a"],
        ["L-5", "Python ラッパ (ctypes)", "python/<mod>lib/ (4 ファイル + tests)"],
        ["L-6", "4 層テストスイート", "test_run/test_definitions.conf に登録"],
        ["L-7", "ユーザ向けドキュメント", "README + examples + architecture.md"],
    ]
    add_table(
        slide,
        Inches(0.5),
        Inches(1.3),
        Inches(12.3),
        Inches(5.5),
        rows,
        font_size=13,
    )
    add_textbox(
        slide,
        Inches(0.5),
        Inches(6.9),
        Inches(12.3),
        Inches(0.4),
        "PR は 1 フェーズ = 1 PR 単位で merge し、各 PR で Cursor Bugbot レビュー完了を待ってから次に進みます。",
        font_size=11,
        color=COLOR_GRAY,
    )

    add_speaker_notes(
        slide,
        "(想定 1 分 30 秒) 全モジュール共通の作業手順が Phase L-0 から L-7 までの 8 段階です。"
        "L-0 でまず回帰テスト基盤を整え、L-1 で Makefile を分割、L-2 で C ABI の雛形を作って、"
        "L-3 で SELECT CASE のパラメータレジストリを書き、L-4 で .so をビルドします。"
        "L-5 で Python ラッパ、L-6 でテスト、L-7 でドキュメント整備という流れです。"
        "1 フェーズ 1 PR で進めるため、各段階で Cursor Bugbot のレビュー完了を待ってから次のフェーズに進みます。"
        "この方法論は SKILL.md (PR #84) として文書化済みで、新規モジュールにも横展開できる形になっています。",
    )


def build_slide_06_phase_f(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_title_bar(slide, "Phase F: eq モジュールの F90 近代化", "F77 → F90 への段階的移行 + shim policy")

    add_bullets(
        slide,
        Inches(0.5),
        Inches(1.3),
        Inches(7.5),
        Inches(5.5),
        [
            "eq モジュールは F77 (.f / 固定形式) のレガシー資産が多く、ライブラリ化と並行して F90 化が必要でした。",
            "Phase F-1: COMMON ブロックを MODULE 化 (PR #71) — shim を併設し旧コードと両立。",
            "Phase F-2: LOW tier (PR #79) — 単純な .f を .f90 に書き換え、INCLUDE 由来の COMMON を USE に置換。",
            "Phase F-3: MED tier (PR #81) — INCLUDE shim 経由で段階的に置換 (9 ファイル)。",
            "Phase F-4: HIGH tier (PR #87) — file I/O や driver の F90 化 (8 ファイル)。",
            "Phase F-5: shim removal (PR #93) — eqcom{c,m,q,x}.inc 撤去 + grep clean。",
            "shim policy: 一時的に COMMON↔MODULE 両方を有効化し、grep ゼロ確認後に撤去します。",
        ],
        font_size=14,
    )

    # 右側にフェーズ進捗バー (図)
    phases = [
        ("F-1", "COMMON→MODULE", True),
        ("F-2", "LOW tier .f→.f90", True),
        ("F-3", "MED tier (INCLUDE shim)", True),
        ("F-4", "HIGH tier (driver)", False),
        ("F-5", "shim removal", False),
    ]
    base_top = Inches(1.6)
    for i, (label, desc, done) in enumerate(phases):
        fill = COLOR_ACCENT if done else COLOR_GRAY
        add_box(
            slide,
            Inches(8.4),
            base_top + Inches(i * 0.95),
            Inches(4.4),
            Inches(0.8),
            f"Phase {label}  {'(完了)' if done else '(残作業)'}",
            desc,
            fill=fill,
            title_size=13,
            sub_size=10,
        )

    add_speaker_notes(
        slide,
        "(想定 1 分) eq モジュールだけは特殊で、F77 のレガシーコードが多く Phase L と並行して"
        "F90 近代化 (Phase F) を実施しました。F-1 で COMMON ブロックを MODULE に置き換え、F-2 で軽量な .f を .f90 化、"
        "F-3 では INCLUDE 経由の shim を使って段階的に置換しました。F-4 と F-5 は今後の作業です。"
        "重要な工夫は shim policy で、一気に置換するのではなく、新旧両方を一時的に共存させ、"
        "grep でゼロ確認してから撤去するという慎重な方法を採っています。",
    )


def build_slide_07_test_layers(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_title_bar(slide, "テスト戦略: 4 層構成", "Layer 1 〜 4 を test_run/test_definitions.conf に登録")

    layer_w = Inches(2.95)
    layer_h = Inches(2.5)
    y = Inches(1.5)
    layers = [
        (
            "Layer 1\n等価性テスト",
            "Phase 0 baseline と比較\n許容差 1e-10\n例: trlib_equivalence",
            COLOR_TEST,
            Inches(0.4),
        ),
        (
            "Layer 2\nC ABI テスト",
            "make -C <mod> <mod>_api_check_all\nC 側スモーク + 異常系\n例: trlib_c_abi",
            COLOR_C_ABI,
            Inches(3.55),
        ),
        (
            "Layer 3\nPython ラッパテスト",
            "unittest discover\nctypes 配置 / 例外階層\n例: trlib_ffi / trlib_wrapper",
            COLOR_PYTHON,
            Inches(6.7),
        ),
        (
            "Layer 4\nスイープテスト",
            "3×3 グリッド (RR×BB)\nNaN 検知 + 完走確認\n例: trlib_sweep",
            COLOR_MCP,
            Inches(9.85),
        ),
    ]
    boxes = []
    for title, sub, fill, left in layers:
        b = add_box(
            slide,
            left,
            y,
            layer_w,
            layer_h,
            title,
            sub,
            fill=fill,
            title_size=14,
            sub_size=11,
        )
        boxes.append(b)

    # 4 層を「下から積み上がる」イメージで矢印を入れる
    for a, b in zip(boxes[:-1], boxes[1:]):
        add_arrow(slide, a, b)

    # 下段: 共通の入力 / 出力箱
    add_box(
        slide,
        Inches(0.4),
        Inches(4.4),
        Inches(12.4),
        Inches(0.7),
        "test_run/test_definitions.conf に <mod>lib_equivalence / _c_abi / _ffi / _wrapper / _sweep を登録",
        "",
        fill=COLOR_TITLE,
        title_size=13,
    )
    add_box(
        slide,
        Inches(0.4),
        Inches(5.3),
        Inches(12.4),
        Inches(0.7),
        "tools/compare_metrics.py で baseline vs library 出力を JSON 比較",
        "",
        fill=COLOR_GRAY,
        title_size=13,
    )

    add_textbox(
        slide,
        Inches(0.4),
        Inches(6.2),
        Inches(12.4),
        Inches(1.0),
        "ポイント: Layer 1 で「数値が変わっていないこと」を担保した上で、上位層で API 安全性を順次確認。\n"
        "tr_m0904 のように元コードが ~1e-8 で揺らぐケースは baseline を pin する運用にしています。",
        font_size=12,
        color=COLOR_GRAY,
    )

    add_speaker_notes(
        slide,
        "(想定 1 分 30 秒) テストは 4 層に分けています。Layer 1 は等価性テストで、"
        "Phase 0 で取った baseline と比較して 1e-10 で一致するかを確認します。"
        "Layer 2 は C ABI 側のスモークテスト、Layer 3 は Python ラッパの単体テスト、"
        "そして Layer 4 はパラメータグリッドを回すスイープテストです。"
        "全部 test_run/test_definitions.conf に登録してあり、CI で自動実行されます。"
        "tr_m0904 のように元コード自体が 1e-8 程度揺らぐケースは、"
        "baseline を pin する運用にして再現性を担保しています。",
    )


def build_slide_08_python_hello(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_title_bar(slide, "使い方 1: Python ライブラリの hello world", "5 行で TR シミュレーションを起動")

    code = (
        "from trlib import Trlib\n"
        "\n"
        "with Trlib() as tr:\n"
        "    tr.set_params(RR=8.5, RA=2.0, BB=5.3, NSMAX=2, DT=0.1)\n"
        "    tr.run(ntmax=50)\n"
        "    state = tr.get_state()\n"
        "\n"
        "print(state.scalars['T'], state.scalars['WPT'])"
    )
    add_code_block(
        slide,
        Inches(0.4),
        Inches(1.3),
        Inches(7.0),
        Inches(3.5),
        code,
        font_size=14,
        title="quickstart.py 抜粋",
    )

    # 右側に 5 段階フロー (init → set → run → get_state → close)
    steps = [
        ("init", "with Trlib() as tr", COLOR_PYTHON),
        ("set_param", "tr.set_params(RR=..., BB=...)", COLOR_PYTHON),
        ("run", "tr.run(ntmax=50)", COLOR_PYTHON),
        ("get_state", "state = tr.get_state()", COLOR_PYTHON),
        ("close", "(context manager)", COLOR_PYTHON),
    ]
    boxes = []
    for i, (title, sub, fill) in enumerate(steps):
        b = add_box(
            slide,
            Inches(7.7),
            Inches(1.3 + i * 1.05),
            Inches(5.2),
            Inches(0.85),
            title,
            sub,
            fill=fill,
            title_size=14,
            sub_size=11,
        )
        boxes.append(b)
    for a, b in zip(boxes[:-1], boxes[1:]):
        add_arrow(slide, a, b)

    add_textbox(
        slide,
        Inches(0.4),
        Inches(5.0),
        Inches(7.0),
        Inches(2.0),
        "ポイント:\n"
        "・ コンテキストマネージャで init / finalize を自動管理。\n"
        "・ 配列要素は set_param('PN[1]', 1.0) のように 1-origin で指定。\n"
        "・ 例外階層 (TrlibParamError 等) で ierr=1〜4 をマップ。",
        font_size=13,
        color=COLOR_BLACK,
    )

    add_speaker_notes(
        slide,
        "(想定 1 分) 実際の使い方を見ていきます。これが trlib の hello world で、"
        "わずか 5 行で TR を起動できます。with 文でコンテキストマネージャに入ると tr_init が呼ばれ、"
        "set_params で複数のスカラーパラメータを一度に設定できます。配列要素は set_param('PN[1]', 1.0) のように"
        "1-origin で指定する点だけ注意してください。run で時間ステップを進め、get_state で結果を取り出して、"
        "with を抜けると自動的に finalize が呼ばれます。"
        "右側の図はこの 5 段階のフローを箱で示したものです。"
        "ierr のエラーコードはそれぞれ TrlibParamError などの例外にマップされています。",
    )


def build_slide_09_toml_runner(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_title_bar(
        slide,
        "使い方 2: TOML config runner (今後)",
        "python -m trlib config.toml で計算 + プロットを一気通貫"
    )

    # フローチャート: TOML -> ライブラリ実行 -> プロット生成
    box_w = Inches(3.4)
    box_h = Inches(1.6)
    y = Inches(2.5)

    toml_box = add_box(
        slide,
        Inches(0.4),
        y,
        box_w,
        box_h,
        "1. TOML ファイル",
        "iter01.toml\n[geometry] [plasma]\n[run] [plot]",
        fill=COLOR_TOML,
        title_size=15,
        sub_size=12,
    )
    run_box = add_box(
        slide,
        Inches(4.95),
        y,
        box_w,
        box_h,
        "2. ライブラリ実行",
        "python -m trlib\nconfig.toml\n→ Trlib + set + run",
        fill=COLOR_PYTHON,
        title_size=15,
        sub_size=12,
    )
    plot_box = add_box(
        slide,
        Inches(9.5),
        y,
        box_w,
        box_h,
        "3. プロット生成",
        "tr.plot('RN')\n結果を PNG / PDF\nに自動保存",
        fill=COLOR_ACCENT,
        title_size=15,
        sub_size=12,
    )

    add_arrow(slide, toml_box, run_box, label="parse + validate")
    add_arrow(slide, run_box, plot_box, label="auto-plot")

    # 下段に補足
    add_textbox(
        slide,
        Inches(0.4),
        Inches(4.5),
        Inches(12.5),
        Inches(2.5),
        "想定する利用シナリオ:\n"
        "・ パラメータを TOML で版管理 → git diff でケース比較が容易。\n"
        "・ 1 コマンドで「計算 → 状態取得 → 既定プロット出力」までを完結。\n"
        "・ MCP server からも同じ TOML を渡せるため、LLM ワークフローと整合。\n"
        "・ ステータス: 設計 (deferred) — 各モジュールへ横展開予定。",
            font_size=14,
        color=COLOR_BLACK,
    )

    add_speaker_notes(
        slide,
        "(想定 1 分) もう少し高水準な使い方として、TOML config runner を計画しています。"
        "ユーザは TOML ファイルにパラメータと実行条件を書き、python -m trlib config.toml を一発実行するだけで、"
        "TOML パース → ライブラリ実行 → プロット出力までが自動で走ります。"
        "git でケースを版管理しやすく、MCP からも同じ TOML を渡せるので LLM ワークフローと整合します。"
        "現時点ではまだ deferred 状態ですが、各モジュールへ横展開する予定です。",
    )


def build_slide_10_toml_schema(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_title_bar(slide, "TOML schema 例", "iter01.toml (想定スキーマ抜粋)")

    code = (
        "# python/trlib/samples/iter01.toml (想定)\n"
        "[run]\n"
        "module = \"tr\"\n"
        "ntmax  = 50\n"
        "\n"
        "[geometry]\n"
        "RR    = 8.5    # major radius [m]\n"
        "RA    = 2.0    # minor radius [m]\n"
        "RKAP  = 1.7    # elongation\n"
        "BB    = 5.3    # toroidal field [T]\n"
        "\n"
        "[plasma]\n"
        "NSMAX = 2\n"
        "PN    = [1.0, 1.0]   # density [10^20 m^-3]\n"
        "PT    = [1.5, 1.5]   # temperature [keV]\n"
        "\n"
        "[transport]\n"
        "MDLKAI = 60     # transport model selector\n"
        "CK0    = 12.0\n"
        "CK1    = 12.0\n"
        "\n"
        "[plot]\n"
        "vars   = [\"RN\", \"RT\", \"AJ\", \"QP\"]\n"
        "format = \"png\"\n"
        "outdir = \"./out\"\n"
    )
    add_code_block(
        slide,
        Inches(0.4),
        Inches(1.3),
        Inches(8.0),
        Inches(5.7),
        code,
        font_size=12,
    )

    add_bullets(
        slide,
        Inches(8.6),
        Inches(1.3),
        Inches(4.4),
        Inches(5.7),
        [
            "[run]: モジュール選択と時間ステップ数。",
            "[geometry]: 装置形状 (RR/RA/RKAP/BB)。",
            "[plasma]: 種数と密度・温度配列。",
            "[transport]: 輸送係数モデル。",
            "[plot]: 自動プロット対象変数と出力先。",
            "未指定キーは namelist 既定値が継続。",
            "TOML はコメント付きで版管理しやすい。",
        ],
        font_size=13,
    )

    add_speaker_notes(
        slide,
        "(想定 50 秒) こちらが TOML schema の想定例です。"
        "[run] でモジュールとステップ数を指定し、[geometry] [plasma] [transport] にパラメータを書き、"
        "[plot] で自動プロット対象を列挙します。配列は TOML の自然な構文で書けるので、"
        "namelist より見通しが良くなります。未指定キーは namelist の既定値が継続するため、"
        "差分だけを書けば良いという運用ができます。",
    )


def build_slide_11_plot_api(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_title_bar(slide, "使い方 3: 可視化 API (今後)", "tr.plot('RN') で密度プロファイルを即可視化")

    code = (
        "with Trlib() as tr:\n"
        "    tr.set_params(RR=8.5, RA=2.0, BB=5.3,\n"
        "                  NSMAX=2, DT=0.1, NTSTEP=10)\n"
        "    tr.run(ntmax=50)\n"
        "\n"
        "    fig = tr.plot(\"RN\")           # 密度プロファイル\n"
        "    fig.savefig(\"density.png\")\n"
        "\n"
        "    tr.plot(\"RT\", show=True)     # 温度をその場表示\n"
    )
    add_code_block(
        slide,
        Inches(0.4),
        Inches(1.3),
        Inches(6.2),
        Inches(3.4),
        code,
        font_size=13,
    )

    img_path = Path(__file__).parent / "assets" / "mock_rnt_plot.png"
    if img_path.exists():
        slide.shapes.add_picture(
            str(img_path),
            Inches(6.9),
            Inches(1.3),
            width=Inches(6.0),
        )

    add_textbox(
        slide,
        Inches(0.4),
        Inches(4.9),
        Inches(6.2),
        Inches(2.3),
        "API 設計方針:\n"
        "・ Module ごとに plot(varname) を提供 (tr / fp / ti / ...)。\n"
        "・ 戻り値は matplotlib.figure.Figure。Jupyter で即表示可。\n"
        "・ MCP からは plot 結果を base64 PNG で返却 (今後拡張)。\n"
        "・ ステータス: deferred — TR 用 plot 設計を先行。",
        font_size=13,
        color=COLOR_BLACK,
    )

    add_textbox(
        slide,
        Inches(6.9),
        Inches(5.7),
        Inches(6.0),
        Inches(1.3),
        "右図は tr.plot('RN') の模擬出力イメージです。\n"
        "実装後は state.RN を直接 matplotlib に渡して描画します。",
        font_size=11,
        color=COLOR_GRAY,
    )

    add_speaker_notes(
        slide,
        "(想定 50 秒) 可視化 API も今後の拡張として準備しています。"
        "tr.plot('RN') と書くだけで、現在の状態の密度プロファイルが matplotlib の Figure として返ってきます。"
        "右側はその出力イメージで、ρ 方向に対する electron / deuteron / tritium の密度プロファイルを描いたものです。"
        "Jupyter で対話的に動かす場合に特に便利で、MCP からも plot を要求できるよう"
        "base64 PNG 返却に拡張する計画です。これは visualization followup として保留中の項目です。",
    )


def build_slide_12_mcp_flow(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_title_bar(slide, "使い方 4: MCP server (LLM 連携)", "Claude / Cursor から自然言語で計算を起動")

    box_w = Inches(2.7)
    box_h = Inches(1.6)
    y = Inches(2.4)

    user_box = add_box(
        slide,
        Inches(0.4),
        y,
        box_w,
        box_h,
        "ユーザー",
        "「TR を RR=6.5 で\n10 ステップ走らせて\nQ0 を教えて」",
        fill=COLOR_GRAY,
        title_size=15,
        sub_size=11,
    )
    llm_box = add_box(
        slide,
        Inches(3.55),
        y,
        box_w,
        box_h,
        "LLM (Claude)",
        "ツール呼出を選択\nrun_and_get_state\n(params, ntmax)",
        fill=COLOR_TITLE,
        title_size=15,
        sub_size=11,
    )
    mcp_box = add_box(
        slide,
        Inches(6.7),
        y,
        box_w,
        box_h,
        "MCP サーバ\n(<X>_mcp.server)",
        "stdio + JSON-RPC\nFastMCP runtime\n9 ツール公開",
        fill=COLOR_MCP,
        title_size=14,
        sub_size=11,
    )
    lib_box = add_box(
        slide,
        Inches(9.85),
        y,
        box_w,
        box_h,
        "ライブラリ\n(<X>lib + .so)",
        "ctypes -> BIND(C)\n-> Fortran kernel",
        fill=COLOR_FORTRAN,
        title_size=14,
        sub_size=11,
    )

    add_arrow(slide, user_box, llm_box, label="自然言語")
    add_arrow(slide, llm_box, mcp_box, label="JSON-RPC")
    add_arrow(slide, mcp_box, lib_box, label="Python 関数呼出")

    # 下段: 結果が逆向きに返ってくる
    add_textbox(
        slide,
        Inches(0.4),
        Inches(4.5),
        Inches(12.5),
        Inches(0.5),
        "戻りは逆向き: ライブラリ → MCP (dict) → LLM (要約) → ユーザー (自然言語回答)",
        font_size=13,
        color=COLOR_GRAY,
        align=PP_ALIGN.CENTER,
        bold=True,
    )

    code = (
        "$ claude mcp add task-tr -- python -m tr_mcp.server\n"
        "$ # Claude の会話で 「TR を RR=6.5 で 10 ステップ走らせて Q0 を教えて」 と入力するだけ"
    )
    add_code_block(
        slide,
        Inches(0.4),
        Inches(5.3),
        Inches(12.5),
        Inches(1.4),
        code,
        font_size=12,
        title="登録コマンド + 利用イメージ",
    )

    add_speaker_notes(
        slide,
        "(想定 1 分 30 秒) MCP サーバの使い方です。流れとしては、"
        "ユーザーが Claude や Cursor のチャット欄に自然言語でリクエストを書きます。"
        "LLM はそれを解釈して、登録された MCP ツール (例: run_and_get_state) を選んで呼び出します。"
        "MCP サーバは標準入出力経由の JSON-RPC でリクエストを受け、内部で trlib を介して .so を呼び、"
        "結果を辞書で返します。LLM はその結果を要約してユーザーに自然言語で回答します。"
        "登録は claude mcp add task-tr 一行で済むので、利用者側のセットアップはとても軽いです。",
    )


def build_slide_13_mcp_tools(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_title_bar(slide, "MCP ツール一覧 (9 ツール)", "<X>_mcp サーバが公開する関数群")

    rows = [
        ["ツール名", "目的", "主な引数"],
        ["init", "ライブラリ初期化", "なし"],
        ["set_param", "単一パラメータ設定", "name, value (NAME[i] 可)"],
        ["set_params", "まとめて設定 (scalar / list / dict)", "params"],
        ["run", "時間ステップ進行", "ntmax (default=1)"],
        ["get_state", "現在の状態取得", "なし"],
        ["finalize", "リソース解放", "なし"],
        ["describe_parameters", "パラメータ一覧と型・説明", "なし"],
        ["describe_state_schema", "get_state の JSON schema", "なし"],
        ["run_and_get_state", "init + set + run + get_state を一括", "params, ntmax"],
    ]
    add_table(
        slide,
        Inches(0.5),
        Inches(1.3),
        Inches(8.5),
        Inches(5.6),
        rows,
        font_size=12,
    )

    add_bullets(
        slide,
        Inches(9.2),
        Inches(1.3),
        Inches(3.7),
        Inches(5.6),
        [
            "全モジュール (tr / fp / ti / wr / wrx) で同じ 9 ツール構成。",
            "describe_* は LLM の自己発見用。",
            "run_and_get_state は会話ターン数を抑える複合ツール。",
            "Phase 2: plot ツール追加予定。",
            "Phase 3: TOML 入力対応予定。",
        ],
        font_size=13,
    )

    add_speaker_notes(
        slide,
        "(想定 1 分) MCP サーバが公開しているツールは 9 種類です。"
        "init / set_param / set_params / run / get_state / finalize の 6 つはライブラリ操作の素朴なラッパで、"
        "describe_parameters と describe_state_schema は LLM がツールを自己発見するための内省用ツールです。"
        "最後の run_and_get_state は init から get_state までを 1 回で呼べる複合ツールで、"
        "会話のラウンドトリップを節約するために用意しています。"
        "今後 plot ツールや TOML 入力対応も追加していく予定です。",
    )


def build_slide_14_summary(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_title_bar(slide, "成果サマリ (インフォグラフィック)", "数字で見るプロジェクト規模")

    # 4 つの指標を横並びに大きく表示
    items = [
        ("96+", "merged PR", "PR #1 〜 #96"),
        ("7", "対象モジュール", "全 module 完了"),
        ("28+", "tests / module", "4 層 × 7 モジュール"),
        ("9 × 6", "MCP ツール × server", "tr/fp/ti/wr/wrx/tot"),
    ]
    box_w = Inches(3.0)
    box_h = Inches(2.6)
    y = Inches(1.5)
    for i, (num, label, sub) in enumerate(items):
        left = Inches(0.4 + i * 3.2)
        bg = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE, left, y, box_w, box_h
        )
        bg.fill.solid()
        bg.fill.fore_color.rgb = [COLOR_TITLE, COLOR_ACCENT, COLOR_PYTHON, COLOR_MCP][i]
        bg.line.fill.background()
        tf = bg.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf.margin_top = Emu(54000)
        tf.margin_bottom = Emu(54000)
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = num
        r.font.size = Pt(56)
        r.font.bold = True
        r.font.color.rgb = COLOR_WHITE
        r.font.name = JP_FONT
        p2 = tf.add_paragraph()
        p2.alignment = PP_ALIGN.CENTER
        r2 = p2.add_run()
        r2.text = label
        r2.font.size = Pt(16)
        r2.font.bold = True
        r2.font.color.rgb = COLOR_WHITE
        r2.font.name = JP_FONT
        p3 = tf.add_paragraph()
        p3.alignment = PP_ALIGN.CENTER
        r3 = p3.add_run()
        r3.text = sub
        r3.font.size = Pt(11)
        r3.font.color.rgb = COLOR_WHITE
        r3.font.name = JP_FONT

    # 下段: 副次指標
    add_box(
        slide,
        Inches(0.4),
        Inches(4.4),
        Inches(12.6),
        Inches(0.9),
        "ドキュメント: SKILL.md (PR #84) + 日本語マニュアル PDF (PR #73) + 各モジュール architecture.md",
        "",
        fill=COLOR_GRAY,
        title_size=14,
    )
    add_box(
        slide,
        Inches(0.4),
        Inches(5.4),
        Inches(12.6),
        Inches(0.9),
        "テスト基盤: Phase 0 baseline 全モジュール整備 (test_run/baselines/) + 4 層テスト + Cursor Bugbot レビュー",
        "",
        fill=COLOR_GRAY,
        title_size=14,
    )
    add_box(
        slide,
        Inches(0.4),
        Inches(6.4),
        Inches(12.6),
        Inches(0.7),
        "互換性: 既存 CLI バイナリ (tr2 / fp / ti / wr / wrx / eq) は一切変更なし。共有ライブラリは追加機能。",
        "",
        fill=COLOR_ACCENT,
        title_size=14,
    )

    add_speaker_notes(
        slide,
        "(想定 1 分) ここまでの成果を数字でまとめます。"
        "merged PR は 96 件超、対象モジュール 7 つ全て Phase L-0..L-7 完了、"
        "各モジュール 28+ のテストケースを整備しました。"
        "MCP ツールは 9 種類 × 6 サーバ (tr/fp/ti/wr/wrx/tot) で展開済みです。"
        "ドキュメントとして、再利用可能な SKILL.md と日本語マニュアル PDF (55 ページ) も整備しました。"
        "重要なのは下段の通り、CLI バイナリは一切変更していない点です。共有ライブラリは純粋な追加機能であり、"
        "従来のユーザに何の影響も与えません。",
    )


def build_slide_15_remaining(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_title_bar(slide, "残作業", "Phase L 完遂と横展開タスク")

    add_bullets(
        slide,
        Inches(0.5),
        Inches(1.3),
        Inches(12.3),
        Inches(5.5),
        [
            "可視化 API: trlib に plot(varname) + TOML runner reference 実装中 (PR #83) → fp/ti/wr/wrx/eq/tot に横展開。",
            "TOML config runner: python -m <X>lib config.toml を全モジュールに展開。",
            "MCP plot ツール: base64 PNG 返却を 6 サーバ全部に追加 (plot/plot_sweep/plot_available)。",
            "Tutorial notebooks: Jupyter で利用シナリオ別に整備 (parameter sweep / 最適化 / LLM 連携)。",
            "Per-module Fortran-side README: 設計方針・invariant 集約 (English)。",
            "tot 最適化ドライバ: scipy/optuna 連携 (元 L-7 plan の延長)。",
            "MCP 利用マニュアル: 素人向け、Claude Desktop / Cursor 登録手順含む。",
        ],
        font_size=15,
    )

    add_speaker_notes(
        slide,
        "(想定 1 分) 残っている作業をまとめます。eq の L-6/L-7、tot の L-5 以降、"
        "Phase F-4/F-5 の HIGH tier F90 化、可視化 API、TOML runner、MCP の plot ツール、"
        "それから Jupyter notebook 形式のチュートリアルです。"
        "また、draft 状態になっている 6 件の plan PR をリベースして merge ready にすることも控えています。",
    )


def build_slide_16_future(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_title_bar(slide, "今後の発展", "ライブラリ化を起点とした応用展開")

    add_bullets(
        slide,
        Inches(0.5),
        Inches(1.3),
        Inches(12.3),
        Inches(5.5),
        [
            "Tutorial notebooks (Jupyter): モジュール別の入門 → 応用ストーリー。",
            "可視化レイヤ拡張: matplotlib + plotly を切替可能に、対話 GUI への接続。",
            "MCP 利用マニュアル: Claude Desktop / Claude Code / Cursor それぞれのセットアップ手順を整備。",
            "パラメータ最適化応用: scipy.optimize や bayesian-optimization と連携 (RR / BB / 輸送係数 など)。",
            "データ同化: 実験データへのフィッティング (TOKAMAK 実機計測との突合)。",
            "モジュール間結合: tot を介して tr ↔ wr ↔ fp を Python レベルで連結。",
            "MCP マルチエージェント: モジュールごとのサブエージェントによる協調計算。",
        ],
        font_size=15,
    )

    add_speaker_notes(
        slide,
        "(想定 1 分) 今後の発展としては、まず Jupyter チュートリアルの整備、"
        "可視化レイヤの拡張、MCP の利用マニュアル整備が直近の課題です。"
        "より発展的には、scipy.optimize と組み合わせたパラメータ最適化、実験データへのデータ同化、"
        "tot を介したモジュール間結合、そして MCP マルチエージェントによる協調計算など、"
        "ライブラリ化を起点に多様な応用が可能になります。",
    )


def build_slide_17_qa_design(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_title_bar(slide, "Q&A 用補足: 設計上の工夫", "実装を支えた 4 つの設計判断")

    items = [
        (
            "shim policy (Phase F)",
            "COMMON ↔ MODULE を一時的に共存。grep ゼロ後に旧 INCLUDE を撤去。",
            COLOR_FORTRAN,
        ),
        (
            "RTLD_LAZY + --unresolved-symbols",
            "graphics シンボル未解決でも .so は dlopen 可。CLI 側は従来どおり結合。",
            COLOR_C_ABI,
        ),
        (
            "Name collision: BIND(C, NAME=...) + USE alias",
            "Fortran 側名前衝突を BIND(C) のリネームと USE module, only: ... => alias で解消。",
            COLOR_PYTHON,
        ),
        (
            "Error code 0..4 + 例外階層",
            "0=success / 1=ParamError / 2=StateError / 3=RunError / 4=NotImplemented を一貫マップ。",
            COLOR_MCP,
        ),
    ]
    for i, (title, sub, color) in enumerate(items):
        row = i // 2
        col = i % 2
        left = Inches(0.4 + col * 6.35)
        top = Inches(1.4 + row * 2.5)
        add_box(
            slide,
            left,
            top,
            Inches(6.15),
            Inches(2.3),
            title,
            sub,
            fill=color,
            title_size=15,
            sub_size=12,
        )

    add_textbox(
        slide,
        Inches(0.4),
        Inches(6.4),
        Inches(12.6),
        Inches(0.6),
        "詳細はリポジトリの docs/superpowers/specs/ 配下と SKILL.md (PR #84) を参照してください。",
        font_size=12,
        color=COLOR_GRAY,
    )

    add_speaker_notes(
        slide,
        "(想定 1 分) Q&A 用に 4 つの設計工夫を挙げます。"
        "1 つ目は Phase F の shim policy で、新旧コードを共存させ grep ゼロ確認後に撤去します。"
        "2 つ目は RTLD_LAZY と --unresolved-symbols で、graphics シンボルが未解決でも .so の dlopen を許容します。"
        "3 つ目は名前衝突対策で、BIND(C, NAME=...) と USE alias を組み合わせます。"
        "4 つ目はエラーコードで、0 から 4 を Python の例外階層に一貫マップしています。"
        "より詳細は docs/superpowers/specs/ や SKILL.md を参照してください。",
    )


def build_slide_18_summary_refs(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_title_bar(slide, "まとめ・参考資料", "リポジトリ・マニュアル・SKILL.md")

    add_bullets(
        slide,
        Inches(0.5),
        Inches(1.3),
        Inches(12.3),
        Inches(2.6),
        [
            "TASK の 7 モジュールを共有ライブラリ + Python ラッパ + MCP サーバとして利用可能にしました。",
            "既存の CLI バイナリは無変更で、追加機能としての安全な拡張です。",
            "テストは 4 層構成 (等価性 / C ABI / Python / スイープ) で 1e-10 の数値同等性を保証。",
            "再利用可能な SKILL.md と日本語マニュアルにより、新規モジュールへの横展開が容易です。",
        ],
        font_size=15,
    )

    rows = [
        ["種別", "場所"],
        ["リポジトリ", "git@github.com:<org>/task-private.git (branch: develop)"],
        ["SKILL.md", "docs/superpowers/skills/module-library-ization/SKILL.md"],
        ["日本語マニュアル", "docs/manual/task-library-manual.tex / .pdf"],
        ["TR ラッパ README", "python/trlib/README.md"],
        ["TR MCP README", "python/mcp-servers/tr_mcp/README.md"],
        ["設計仕様", "docs/superpowers/specs/2026-04-17-tr-library-design.md"],
        ["変更履歴", "CHANGELOG.md"],
    ]
    add_table(
        slide,
        Inches(0.5),
        Inches(4.05),
        Inches(12.3),
        Inches(2.9),
        rows,
        font_size=13,
    )

    add_textbox(
        slide,
        Inches(0.5),
        Inches(7.0),
        Inches(12.3),
        Inches(0.4),
        "ご清聴ありがとうございました。質問は次の Q&A スライドで承ります。",
        font_size=14,
        bold=True,
        color=COLOR_TITLE,
        align=PP_ALIGN.CENTER,
    )

    add_speaker_notes(
        slide,
        "(想定 30 秒) まとめです。TASK の 7 モジュールを共有ライブラリ化し、Python と MCP から利用できるようにしました。"
        "テストは 4 層構成で数値等価性を保証し、SKILL.md とマニュアルで再現性も担保しています。"
        "参考資料は表に挙げたとおりです。ご清聴ありがとうございました。質問をお願いします。",
    )


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main() -> None:
    prs = Presentation()
    set_slide_size(prs)

    builders = [
        build_slide_01_title,
        build_slide_02_motivation,
        build_slide_03_modules,
        build_slide_04_architecture,
        build_slide_05_phase_l,
        build_slide_06_phase_f,
        build_slide_07_test_layers,
        build_slide_08_python_hello,
        build_slide_09_toml_runner,
        build_slide_10_toml_schema,
        build_slide_11_plot_api,
        build_slide_12_mcp_flow,
        build_slide_13_mcp_tools,
        build_slide_14_summary,
        build_slide_15_remaining,
        build_slide_16_future,
        build_slide_17_qa_design,
        build_slide_18_summary_refs,
    ]
    for fn in builders:
        fn(prs)

    out = (
        Path(__file__).parent
        / "2026-04-19-task-library-ization-overview.pptx"
    )
    prs.save(str(out))
    print(f"wrote {out}  ({out.stat().st_size:,} bytes, {len(prs.slides)} slides)")


if __name__ == "__main__":
    main()
