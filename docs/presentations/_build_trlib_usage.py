"""trlib (TASK/TR Python wrapper) 使い方ガイド pptx を生成。

Mirrors the architecture and helpers of ``_build_pptx.py`` (色パレット・
フォント・レイアウトヘルパー・16:9 widescreen)。

Run:
    python3 docs/presentations/_build_trlib_usage.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow ``python3 docs/presentations/_build_trlib_usage.py`` (run from
# repo root) to pick up the sibling ``_pptx_helpers`` module without an
# __init__.py.
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
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    bg = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, 0, 0, SLIDE_W, SLIDE_H
    )
    bg.fill.solid()
    bg.fill.fore_color.rgb = RGBColor(0xF7, 0xFA, 0xFC)
    bg.line.fill.background()
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
        "trlib (TASK/TR Python wrapper)\n使い方ガイド",
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
        "Python から TASK/TR プラズマ輸送計算を駆動する",
        font_size=22,
        color=COLOR_WHITE,
        align=PP_ALIGN.CENTER,
    )

    add_textbox(
        slide,
        Inches(0.5),
        Inches(5.0),
        SLIDE_W - Inches(1.0),
        Inches(0.5),
        "発表日: 2026 年 4 月 20 日",
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
        "発表者: <発表者名>",
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
        "対象: tr/libtrapi.so + python/trlib (Layer 1 1e-10 等価性確認済)",
        font_size=12,
        color=COLOR_GRAY,
        align=PP_ALIGN.CENTER,
    )

    add_speaker_notes(
        slide,
        "本日は trlib、つまり TASK/TR の Python ラッパーの使い方をご紹介します。"
        "tr モジュールは 1 次元プラズマ輸送計算を担当する Fortran コードで、"
        "従来は CLI バイナリ tr2 として動かしていました。"
        "今回、共有ライブラリ libtrapi.so と Python ラッパー trlib を介して、"
        "Python スクリプトから直接呼べるようになっています。"
        "想定時間は 15 分です。基本フロー、パラメータ設定、状態取得、スイープ、"
        "デバッグ、他モジュールへの拡張という流れでお話しします。",
    )


def build_slide_02_overview(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_title_bar(
        slide,
        "全体像: tr2 バイナリ vs libtrapi.so + trlib",
        "Fortran カーネルは共通、利用形態だけが変わる",
    )

    box_w = Inches(2.7)
    box_h = Inches(1.5)
    y_top = Inches(2.0)
    y_bot = Inches(4.6)

    # 上段: 従来の CLI 経路
    cli_in = add_box(
        slide,
        Inches(0.4),
        y_top,
        box_w,
        box_h,
        "namelist .in",
        "test_run/inputs/\ntr_tst2.in など",
        fill=COLOR_GRAY,
        title_size=14,
        sub_size=11,
    )
    cli_bin = add_box(
        slide,
        Inches(3.5),
        y_top,
        box_w,
        box_h,
        "tr2 バイナリ",
        "対話メニュー\n+ 標準入出力",
        fill=COLOR_FORTRAN,
        title_size=14,
        sub_size=11,
    )
    cli_out = add_box(
        slide,
        Inches(6.6),
        y_top,
        box_w,
        box_h,
        "ファイル出力",
        "tr2.<case>.gs\nregression.log",
        fill=COLOR_GRAY,
        title_size=14,
        sub_size=11,
    )
    add_textbox(
        slide,
        Inches(9.6),
        y_top + Inches(0.35),
        Inches(3.4),
        Inches(0.9),
        "従来 (CLI):\n対話 + namelist 一発実行",
        font_size=12,
        color=COLOR_GRAY,
    )
    add_arrow(slide, cli_in, cli_bin)
    add_arrow(slide, cli_bin, cli_out)

    # 下段: 新しい Python 経路
    py_script = add_box(
        slide,
        Inches(0.4),
        y_bot,
        box_w,
        box_h,
        "Python スクリプト",
        "from trlib import Trlib\nwith Trlib() as tr:",
        fill=COLOR_PYTHON,
        title_size=14,
        sub_size=11,
    )
    py_lib = add_box(
        slide,
        Inches(3.5),
        y_bot,
        box_w,
        box_h,
        "libtrapi.so",
        "BIND(C) 5 関数\ntr_init / tr_set_param /\ntr_run / tr_get_state /\ntr_finalize",
        fill=COLOR_C_ABI,
        title_size=14,
        sub_size=10,
    )
    py_kernel = add_box(
        slide,
        Inches(6.6),
        y_bot,
        box_w,
        box_h,
        "Fortran カーネル",
        "TR* 計算ルーチン\n(CLI と同一コード)",
        fill=COLOR_FORTRAN,
        title_size=14,
        sub_size=11,
    )
    py_state = add_box(
        slide,
        Inches(9.7),
        y_bot,
        box_w,
        box_h,
        "TrState",
        "dataclass\n.scalars / .RN / .RT\n.AJ / .QP",
        fill=COLOR_PYTHON,
        title_size=14,
        sub_size=11,
    )
    add_arrow(slide, py_script, py_lib, label="ctypes")
    add_arrow(slide, py_lib, py_kernel, label="同一コア")
    add_arrow(slide, py_kernel, py_state, label="get_state")

    add_textbox(
        slide,
        Inches(0.4),
        Inches(6.4),
        Inches(12.5),
        Inches(0.9),
        "ポイント: Fortran カーネルは tr2 / libtrapi.so で同一実装。"
        "trlib は ctypes 越しに 5 つの C ABI 関数を呼ぶ薄い層で、状態は TrState dataclass で受け取ります。",
        font_size=12,
        color=COLOR_GRAY,
    )

    add_speaker_notes(
        slide,
        "全体像です。上段が従来の CLI 経路で、namelist .in を tr2 バイナリに食わせて"
        "ファイル出力するという流れです。下段が今回追加した Python 経路で、Python から"
        "ctypes 越しに libtrapi.so の 5 つの BIND(C) 関数を呼びます。"
        "重要なのは Fortran カーネルが共通である点で、同じ計算式が動きます。"
        "Layer 1 等価性テストで 1e-10 の同等性を確認済みです。"
        "結果は TrState という dataclass で取り出せます。",
    )


def build_slide_03_build(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_title_bar(
        slide,
        "ビルド手順",
        "libtrapi.so の準備と Python パスの通し方",
    )

    code = (
        "# 1. 共有ライブラリのビルド\n"
        "$ make -C tr libtrapi.so\n"
        "  → tr/libtrapi.so が生成されます\n"
        "\n"
        "# 2. Python パスを通す (リポジトリルートから)\n"
        "$ export PYTHONPATH=$PWD/python\n"
        "\n"
        "# 3. 動作確認\n"
        "$ python3 -c 'from trlib import Trlib; print(Trlib)'\n"
        "  <class 'trlib.trlib.Trlib'>\n"
        "\n"
        "# 4. デフォルト .so 検索パスを上書きしたい場合\n"
        "$ export TRLIB_LIBRARY=/path/to/libtrapi.so\n"
        "  あるいは Trlib(lib_path='/path/to/libtrapi.so')\n"
    )
    add_code_block(
        slide,
        Inches(0.4),
        Inches(1.3),
        Inches(7.6),
        Inches(4.8),
        code,
        font_size=13,
        title="シェル手順",
    )

    add_bullets(
        slide,
        Inches(8.2),
        Inches(1.3),
        Inches(4.8),
        Inches(4.8),
        [
            "依存: gfortran, lapack, blas (CLI と同じ)。",
            "PIC ビルドのため標準 Makefile で完結。",
            "graphics シンボルは未解決のままでも dlopen 可。",
            "Python は 3.8+ で動作確認済み。",
            "ctypes のみを使うため追加 pip install は不要。",
        ],
        font_size=14,
    )

    # Troubleshooting
    add_box(
        slide,
        Inches(0.4),
        Inches(6.3),
        Inches(12.5),
        Inches(0.9),
        "トラブル: libtrapi.so not built",
        "Trlib() で OSError: libtrapi.so not found → make -C tr libtrapi.so を再実行。CLEAN ビルドは make -C tr clean.libtrapi.so から。",
        fill=COLOR_TEST,
        title_size=13,
        sub_size=11,
    )

    add_speaker_notes(
        slide,
        "ビルド手順は 3 ステップだけです。tr ディレクトリで make libtrapi.so、"
        "それから PYTHONPATH に repo/python を通し、import が通るか確認します。"
        "TRLIB_LIBRARY 環境変数または Trlib(lib_path=...) で .so の位置を上書きできます。"
        "graphics 系のシンボルは libtrapi.so では未解決ですが、RTLD_LAZY で dlopen する設計のため動作には影響しません。"
        "もし OSError が出たら、まず make -C tr libtrapi.so でビルドし直してください。",
    )


def build_slide_04_hello(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_title_bar(
        slide,
        "Hello world: 5 行で TR を駆動",
        "with Trlib() as tr: tr.run(0); state = tr.get_state()",
    )

    code = (
        "from trlib import Trlib\n"
        "\n"
        "with Trlib() as tr:\n"
        "    tr.run(0)              # tr_prep のみを起動 (0 ステップ)\n"
        "    state = tr.get_state() # TrState を取得\n"
        "\n"
        "print(state.nrmax, state.nsmax, state.nt)\n"
        "print(state.scalars['T'], state.scalars['WPT'])\n"
    )
    add_code_block(
        slide,
        Inches(0.4),
        Inches(1.3),
        Inches(7.4),
        Inches(3.5),
        code,
        font_size=14,
        title="hello.py",
    )

    # 5 段階フロー
    steps = [
        ("init", "with Trlib() as tr"),
        ("(set_param)", "省略可 — defaults でも動く"),
        ("run", "tr.run(0) または tr.run(N)"),
        ("get_state", "state = tr.get_state()"),
        ("finalize", "with を抜けて自動 close"),
    ]
    for i, (title, sub) in enumerate(steps):
        add_box(
            slide,
            Inches(8.1),
            Inches(1.3 + i * 1.05),
            Inches(4.8),
            Inches(0.9),
            title,
            sub,
            fill=COLOR_PYTHON,
            title_size=14,
            sub_size=11,
        )

    add_textbox(
        slide,
        Inches(0.4),
        Inches(5.0),
        Inches(7.4),
        Inches(2.0),
        "ポイント:\n"
        "・ with 文で tr_init / tr_finalize を自動管理。\n"
        "・ run(0) は 0 ステップ実行 = tr_prep のみ起動 (有効なスモーク)。\n"
        "・ Trlib() は process 内シングルトン (libtrapi.so の COMMON が一つ)。\n"
        "・ ierr は raise_for_ierr() で TrlibError 派生例外に変換。",
        font_size=13,
    )

    add_speaker_notes(
        slide,
        "最小の hello world です。with Trlib() as tr で tr_init が呼ばれ、"
        "run(0) で tr_prep だけが走ります。この 0 ステップ実行は L-2 のスモークテストでも"
        "使われている合法な呼び方です。get_state で TrState を取り出せます。"
        "重要なのは Trlib() がプロセス内シングルトンになっていることです。"
        "libtrapi.so の COMMON ブロックがプロセス内で一つしか持てないため、"
        "二つ目の Trlib() を作るとリセットされる仕様になっています。"
        "with を抜けると自動で close、つまり tr_finalize が呼ばれます。",
    )


def build_slide_05_set_param(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_title_bar(
        slide,
        "パラメータ設定の 3 種類",
        "set_param / set_param_str / set_params",
    )

    code = (
        "with Trlib() as tr:\n"
        "    # 1. スカラーを 1 個ずつ\n"
        "    tr.set_param('RR', 6.2)        # 主半径 [m]\n"
        "    tr.set_param('BB', 5.3)        # トロイダル磁場 [T]\n"
        "\n"
        "    # 2. 配列要素 (1-origin、Fortran 慣習)\n"
        "    tr.set_param('PA[2]', 1.0)     # 2 種目の質量数\n"
        "    tr.set_param('PN[1]', 0.7)     # 1 種目の密度\n"
        "    tr.set_param('PN[2]', 0.3)\n"
        "\n"
        "    # 3. 文字列パラメータ (KNAMEQ など)\n"
        "    tr.set_param_str('KNAMEQ', 'eqdata.TST-2')\n"
        "\n"
        "    # 4. キーワードでまとめてスカラー\n"
        "    tr.set_params(RR=6.2, BB=5.3, NSMAX=2, DT=1.0e-5)\n"
    )
    add_code_block(
        slide,
        Inches(0.4),
        Inches(1.3),
        Inches(8.4),
        Inches(5.4),
        code,
        font_size=13,
        title="param.py",
    )

    add_bullets(
        slide,
        Inches(9.0),
        Inches(1.3),
        Inches(3.9),
        Inches(5.4),
        [
            "set_param: 数値を 1 個。",
            "添字 [i] は 1-origin。",
            "2D 配列は [i,j] (registry が解析)。",
            "set_param_str: 文字列専用。",
            "set_params: kwargs (スカラーのみ)。",
            "set_params に [ ] は書けないので、配列要素は set_param で。",
            "ierr=1 で TrlibParamError。",
        ],
        font_size=13,
    )

    add_textbox(
        slide,
        Inches(0.4),
        Inches(6.85),
        Inches(12.5),
        Inches(0.5),
        "解析は tr/tr_param_registry.f90 で実装。利用可能な名前は同ファイルの SELECT CASE を参照。",
        font_size=11,
        color=COLOR_GRAY,
    )

    add_speaker_notes(
        slide,
        "パラメータ設定には 3 種類のメソッドがあります。"
        "set_param が最も基本で、名前と数値を渡します。"
        "配列要素は PA[2] のように 1-origin の添字を文字列で書きます。Fortran の慣習に合わせています。"
        "2 次元配列は PNB[i,j] のような形でも書けます。これは tr_param_registry.f90 が解析します。"
        "set_param_str は文字列パラメータ専用で、KNAMEQ のような eqdata ファイル名を渡すときに使います。"
        "set_params はキーワード引数で複数のスカラーをまとめて設定できます。"
        "ただし Python の kwargs に [ や ] は書けないので、配列要素は必ず set_param を使ってください。"
        "set_params に PN__1 のような名前を渡すと TrlibError で弾く実装になっています。",
    )


def build_slide_06_run(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_title_bar(
        slide,
        "実行とステップ制御: tr.run(ntmax)",
        "累積セマンティクス — run(5)+run(5) は run(10) と等価",
    )

    code = (
        "with Trlib() as tr:\n"
        "    tr_tst2_params.apply(tr)\n"
        "\n"
        "    tr.run(0)        # tr_prep のみ (有効な no-op)\n"
        "    tr.run(5)        # 5 ステップ進行 → NT=5\n"
        "    tr.run(5)        # さらに 5 ステップ → NT=10\n"
        "\n"
        "    state = tr.get_state()\n"
        "    print(state.nt)  # 10\n"
    )
    add_code_block(
        slide,
        Inches(0.4),
        Inches(1.3),
        Inches(7.6),
        Inches(3.4),
        code,
        font_size=13,
        title="incremental.py",
    )

    add_bullets(
        slide,
        Inches(8.2),
        Inches(1.3),
        Inches(4.8),
        Inches(3.4),
        [
            "run(N) は内部で tr_run(N) を呼ぶ。",
            "N=0 は tr_prep のみ起動 (合法)。",
            "N>0 は累積で NT が増加。",
            "再度 run() を呼んでも tr_prep は再実行されない。",
            "ierr=3 で TrlibRunError (収束失敗等)。",
        ],
        font_size=13,
    )

    # 検証結果プレースホルダ
    add_box(
        slide,
        Inches(0.4),
        Inches(5.0),
        Inches(12.5),
        Inches(2.0),
        "検証: run(5)+run(5) vs run(10) 同一性 (tst2 で実測)",
        "  run(10):                ZEFF0 = 1.3292981098481862\n"
        "  run(5)+run(5):          ZEFF0 = 1.3292981098485062  (digit 13 で差)\n"
        "  run(3)+run(3)+run(4):   ZEFF0 = 1.3292981098507612  (digit 11 で差)\n"
        "→ 12 桁一致するが bit-identical ではない (Layer 1 1e-10 tol 内)。\n"
        "  step 分割の仕方で末尾桁の noise が変わる仕様、API ユーザは留意。",
        fill=COLOR_GRAY,
        title_size=14,
        sub_size=11,
    )

    add_speaker_notes(
        slide,
        "tr.run の呼び出し意味論についてです。run(N) は tr_run(N) を呼んで N ステップ進めます。"
        "N=0 は tr_prep のみを起動する合法なケースで、L-2 スモークテストで使われています。"
        "重要なのは累積セマンティクスで、run(5) を呼んだあとに run(5) を呼ぶと、"
        "状態は run(10) と同じになります — 少なくとも設計上はそうなるはずです。"
        "次のスライドの注釈に検証結果プレースホルダを置いてあるので、親プロセスからの結果を埋めてください。"
        "tr_prep は init 直後に最初の run() で 1 度だけ呼ばれ、以降の run では呼ばれません。"
        "計算が発散・収束失敗した場合は ierr=3 が返り、TrlibRunError が投げられます。",
    )


def build_slide_07_get_state(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_title_bar(
        slide,
        "状態取得: TrState と to_dict()",
        "scalars 13 種 + profile (NRMAX 点) を Python リストで",
    )

    code = (
        "state = tr.get_state()\n"
        "\n"
        "# 属性アクセス (dataclass)\n"
        "state.nt        # int  時間ステップカウンタ\n"
        "state.nrmax     # int  実効ラジアル点数\n"
        "state.nsmax     # int  実効種数\n"
        "state.scalars   # dict T / WPT / AJT / Q0 / BETA0 / ... 14 個 (AJRFT 含む)\n"
        "state.RN        # [nrmax][nsmax]  密度プロファイル\n"
        "state.RT        # [nrmax][nsmax]  温度プロファイル\n"
        "state.AJ        # [nrmax]         電流密度プロファイル\n"
        "state.QP        # [nrmax]         安全係数プロファイル\n"
        "\n"
        "import json\n"
        "json.dump(state.to_dict(), open('out.json', 'w'))\n"
    )
    add_code_block(
        slide,
        Inches(0.4),
        Inches(1.3),
        Inches(7.6),
        Inches(4.8),
        code,
        font_size=12,
        title="state.py",
    )

    json_snippet = (
        "{\n"
        "  \"NT\": 10,\n"
        "  \"NRMAX\": 50,\n"
        "  \"NSMAX\": 2,\n"
        "  \"scalars\": {\n"
        "    \"T\": 1.0e-4, \"WPT\": 1.23e-3,\n"
        "    \"AJT\": 0.015, \"Q0\": 1.05,\n"
        "    \"BETA0\": ..., \"ZEFF0\": ...\n"
        "  },\n"
        "  \"profile\": [\n"
        "    {\"NR\": 1, \"RN\": [...], \"RT\": [...],\n"
        "     \"AJ\": ..., \"QP\": ...},\n"
        "    ... NRMAX rows ...\n"
        "  ]\n"
        "}\n"
    )
    add_code_block(
        slide,
        Inches(8.2),
        Inches(1.3),
        Inches(4.8),
        Inches(4.8),
        json_snippet,
        font_size=11,
        title="state.to_dict() 形状",
    )

    add_textbox(
        slide,
        Inches(0.4),
        Inches(6.3),
        Inches(12.5),
        Inches(1.0),
        "to_dict() の形状は Phase 0 baseline (extract_tr_metrics.py) と一致するため、"
        "tools/compare_metrics.py でそのまま 1e-10 比較できます (Layer 1 等価性テストはこの仕組み)。",
        font_size=12,
        color=COLOR_GRAY,
    )

    add_speaker_notes(
        slide,
        "get_state は TrState という dataclass を返します。"
        "属性として nt, nrmax, nsmax の整数、scalars 辞書 (14 個のスカラー)、"
        "それから 4 つのプロファイル配列を持ちます。RN / RT は 2 次元のネストリスト、AJ / QP は 1 次元です。"
        "numpy には依存していないので、to_dict() の結果はそのまま JSON にダンプできます。"
        "右側に JSON の形状を示しました。NT, NRMAX, NSMAX, scalars, profile という 5 つのトップレベルキーで、"
        "profile は NRMAX 個の辞書のリストになっています。"
        "この形状は Phase 0 baseline と完全一致するように設計されており、"
        "tools/compare_metrics.py でそのまま 1e-10 比較できます。",
    )


def build_slide_08_lifecycle(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_title_bar(
        slide,
        "ライフサイクル: with / close / 再利用",
        "context manager は冪等、close() は何度呼んでも安全",
    )

    code = (
        "# パターン 1: 推奨 — with 文で自動 finalize\n"
        "with Trlib() as tr:\n"
        "    tr.run(10)\n"
        "    state = tr.get_state()\n"
        "# ここで自動的に tr_finalize\n"
        "\n"
        "# パターン 2: 明示的に close()\n"
        "tr = Trlib()\n"
        "try:\n"
        "    tr.run(10)\n"
        "finally:\n"
        "    tr.close()\n"
        "    tr.close()    # 冪等 (no-op)\n"
        "\n"
        "# パターン 3: 連続再利用 (新しいインスタンス)\n"
        "for case in cases:\n"
        "    with Trlib() as tr:        # 毎回 tr_init\n"
        "        case.apply(tr)\n"
        "        tr.run(case.NTMAX)\n"
        "        results.append(tr.get_state().to_dict())\n"
    )
    add_code_block(
        slide,
        Inches(0.4),
        Inches(1.3),
        Inches(8.0),
        Inches(5.6),
        code,
        font_size=12,
        title="lifecycle.py",
    )

    add_bullets(
        slide,
        Inches(8.6),
        Inches(1.3),
        Inches(4.4),
        Inches(5.6),
        [
            "with 文を使うのが最も安全。",
            "close() は二重呼出も OK (no-op)。",
            "__del__ も close を試みる (例外は呑む)。",
            "Trlib() を 2 個同時に開くと COMMON が共有される。",
            "ループでは毎回 with で開閉し、状態リーク回避。",
            "新規 init は前回の COMMON をリセット。",
        ],
        font_size=13,
    )

    add_speaker_notes(
        slide,
        "ライフサイクルの 3 パターンです。"
        "パターン 1 が推奨で、with 文に入れて自動 finalize させます。"
        "パターン 2 は明示的に close() を呼ぶ書き方で、冪等なので何度呼んでも安全です。"
        "パターン 3 はパラメータスイープのときの書き方で、毎回新しい Trlib() を開きます。"
        "libtrapi.so は COMMON ブロックを持つシングルトン状態なので、Trlib() を 2 個同時に開いても"
        "状態は共有されます。スイープでは毎ループで with を抜けて再 init することで、"
        "前回の状態漏れを防ぎます。"
        "ヒープ再利用による状態漏れも対策済みで、allocate_trcomm_profile で配列をゼロ初期化しています。",
    )


def build_slide_09_fixture(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_title_bar(
        slide,
        "既存 .in からの fixture 化",
        "namelist の値を Python 辞書に転記する規約",
    )

    nm_code = (
        "! test_run/inputs/tr_tst2.in (抜粋)\n"
        "&TR\n"
        "  modelg=3\n"
        "  KNAMEQ='eqdata.TST-2'\n"
        "  NSMAX=2\n"
        "  PA(2)=1.D0\n"
        "  PZ(2)=1.D0\n"
        "  PN =0.010D0,0.010D0\n"
        "  PT =0.010D0,0.0010D0\n"
        "  DT=1.D-5\n"
        "  NTMAX=10\n"
        "&END\n"
    )
    add_code_block(
        slide,
        Inches(0.4),
        Inches(1.3),
        Inches(6.0),
        Inches(5.6),
        nm_code,
        font_size=12,
        title="namelist 入力",
    )

    py_code = (
        "# python/trlib/tests/fixtures/tr_tst2_params.py\n"
        "SCALARS = {\n"
        "    'MODELG': 3,\n"
        "    'NSMAX':  2,\n"
        "    'DT':     1.0e-5,\n"
        "    'NTMAX':  10,\n"
        "}\n"
        "ARRAYS = {\n"
        "    'PA': {2: 1.0},     # 添字付き dict\n"
        "    'PZ': {2: 1.0},\n"
        "    'PN': [0.010, 0.010],  # 1-origin リスト\n"
        "    'PT': [0.010, 0.0010],\n"
        "}\n"
        "STRINGS = {\n"
        "    'KNAMEQ': 'eqdata.TST-2',\n"
        "}\n"
        "\n"
        "def apply(tr):\n"
        "    for k, v in STRINGS.items():\n"
        "        tr.set_param_str(k, str(v))\n"
        "    for k, v in SCALARS.items():\n"
        "        tr.set_param(k, float(v))\n"
        "    for name, arr in ARRAYS.items():\n"
        "        _apply_array(tr, name, arr)\n"
    )
    add_code_block(
        slide,
        Inches(6.6),
        Inches(1.3),
        Inches(6.4),
        Inches(5.6),
        py_code,
        font_size=11,
        title="Python fixture",
    )

    add_textbox(
        slide,
        Inches(0.4),
        Inches(7.0),
        Inches(12.5),
        Inches(0.4),
        "規約: SCALARS / ARRAYS / STRINGS の 3 辞書で分類し、apply(tr) で順に set_param 系を呼ぶ。",
        font_size=11,
        color=COLOR_GRAY,
    )

    add_speaker_notes(
        slide,
        "既存の namelist 入力ファイルから fixture モジュールへ転記する方法です。"
        "左が tr_tst2.in の抜粋で、右が python/trlib/tests/fixtures/tr_tst2_params.py の対応です。"
        "規約は単純で、3 つの辞書 SCALARS / ARRAYS / STRINGS に分類するだけです。"
        "ARRAYS では一部要素のみ指定したい場合は dict 形式 (例: PA: {2: 1.0})、"
        "1 から順に全要素を書く場合はリスト形式 (例: PN: [0.010, 0.010]) を使います。"
        "apply(tr) 関数で順番に set_param_str → set_param → 配列展開を呼びます。"
        "string が先なのは KNAMEQ などのファイル参照を tr_prep より前に読ませるためです。"
        "tr_iter01_params.py も同じ形式で書かれています。",
    )


def build_slide_10_sweep(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_title_bar(
        slide,
        "パラメータスイープ例",
        "RR × BB の 2D グリッドを Python ループで",
    )

    code = (
        "from trlib import Trlib\n"
        "from trlib.tests.fixtures import tr_iter01_params\n"
        "import os\n"
        "from pathlib import Path\n"
        "\n"
        "RR_VALUES = (7.5, 8.0, 8.5)\n"
        "BB_VALUES = (4.5, 5.0, 5.5)\n"
        "NTMAX = 5\n"
        "\n"
        "os.chdir(Path('test_run/test_output/tr_iter01'))  # eqdata.ITER01 を読むため\n"
        "\n"
        "results = []\n"
        "for rr in RR_VALUES:\n"
        "    for bb in BB_VALUES:\n"
        "        with Trlib() as tr:\n"
        "            tr_iter01_params.apply(tr)         # ベース fixture\n"
        "            tr.set_param('RR', float(rr))      # 軸を上書き\n"
        "            tr.set_param('BB', float(bb))\n"
        "            tr.run(NTMAX)\n"
        "            wpt = tr.get_state().scalars['WPT']\n"
        "            results.append((rr, bb, wpt))\n"
        "\n"
        "for rr, bb, wpt in results:\n"
        "    print(f'RR={rr:.2f} BB={bb:.2f} WPT={wpt:.4e}')\n"
    )
    add_code_block(
        slide,
        Inches(0.4),
        Inches(1.3),
        Inches(8.4),
        Inches(5.7),
        code,
        font_size=12,
        title="sweep.py (test_sweep.py を簡略化)",
    )

    add_bullets(
        slide,
        Inches(9.0),
        Inches(1.3),
        Inches(3.9),
        Inches(5.7),
        [
            "ベース fixture を共通化。",
            "毎ループ Trlib() を再生成。",
            "状態リーク防止 (前ページ参照)。",
            "WPT が finite かを Layer 4 で確認。",
            "MODELG=3 では eqdata の chdir が必要。",
            "scipy.optimize と組み合わせ可。",
        ],
        font_size=13,
    )

    add_textbox(
        slide,
        Inches(0.4),
        Inches(7.05),
        Inches(12.5),
        Inches(0.4),
        "実装例は python/trlib/tests/test_sweep.py を参照 (Layer 4 スモークテスト)。",
        font_size=11,
        color=COLOR_GRAY,
    )

    add_speaker_notes(
        slide,
        "パラメータスイープの実装例です。test_sweep.py を簡略化したもので、"
        "RR と BB を 3 段階ずつ振って 3×3 のグリッドを回します。"
        "ベースとなる物理パラメータは tr_iter01_params.apply(tr) で fixture から流し込み、"
        "RR と BB だけを上書きします。毎ループで Trlib() を with 文で開き直すのがポイントで、"
        "前回の COMMON 状態を完全にリセットしてから次のケースに入ります。"
        "MODELG=3 のケースでは eqdata.ITER01 を読むため、test_run/test_output/tr_iter01 に chdir する必要があります。"
        "Layer 4 テストでは結果の WPT が NaN や Inf にならないことを確認しています。"
        "この骨格をベースに scipy.optimize や bayesian-optimization と組み合わせて最適化することもできます。",
    )


def build_slide_11_plot(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_title_bar(
        slide,
        "プロット例: matplotlib で温度プロファイル",
        "state.to_dict() からそのまま描画",
    )

    code = (
        "import matplotlib.pyplot as plt\n"
        "from trlib import Trlib\n"
        "from trlib.tests.fixtures import tr_tst2_params\n"
        "import os\n"
        "\n"
        "os.chdir('test_run/test_output/tr_tst2')\n"
        "\n"
        "with Trlib() as tr:\n"
        "    tr_tst2_params.apply(tr)\n"
        "    tr.run(tr_tst2_params.NTMAX)\n"
        "    state = tr.get_state()\n"
        "\n"
        "d = state.to_dict()\n"
        "rho = [row['NR'] / d['NRMAX'] for row in d['profile']]\n"
        "te  = [row['RT'][0]            for row in d['profile']]  # 1 種目 = 電子\n"
        "ti  = [row['RT'][1]            for row in d['profile']]  # 2 種目 = イオン\n"
        "\n"
        "fig, ax = plt.subplots()\n"
        "ax.plot(rho, te, label='Te')\n"
        "ax.plot(rho, ti, label='Ti')\n"
        "ax.set_xlabel(r'$\\rho$  (normalised radius)')\n"
        "ax.set_ylabel('temperature [keV]')\n"
        "ax.legend()\n"
        "fig.savefig('te_profile.png')\n"
    )
    add_code_block(
        slide,
        Inches(0.4),
        Inches(1.3),
        Inches(8.4),
        Inches(5.7),
        code,
        font_size=12,
        title="plot.py",
    )

    add_bullets(
        slide,
        Inches(9.0),
        Inches(1.3),
        Inches(3.9),
        Inches(5.7),
        [
            "to_dict() は素の Python list/dict。",
            "numpy なしでも plot 可能。",
            "RT[0] が電子、RT[1] が主イオン。",
            "AJ / QP も同様に取り出せる。",
            "Jupyter なら plt.show() で対話的に。",
            "可視化 API (tr.plot) は将来拡張予定。",
        ],
        font_size=13,
    )

    add_textbox(
        slide,
        Inches(0.4),
        Inches(7.05),
        Inches(12.5),
        Inches(0.4),
        "to_dict() の profile 配列は NR=1..NRMAX。各要素は RN / RT / AJ / QP を持ちます。",
        font_size=11,
        color=COLOR_GRAY,
    )

    add_speaker_notes(
        slide,
        "プロット例です。matplotlib に直接 state.to_dict() を渡す書き方です。"
        "to_dict() の profile キーは長さ NRMAX のリストで、各要素が NR / RN / RT / AJ / QP を持ちます。"
        "ここでは radial 方向に温度プロファイルを描画しています。"
        "RT[0] が 1 種目で通常は電子、RT[1] が主イオンです。"
        "to_dict() は素の Python list と dict を返すので、numpy がなくても matplotlib に渡せます。"
        "Jupyter notebook であれば plt.show() でその場で可視化できます。"
        "tr.plot('RT') のような可視化 API は将来の visualization followup として保留中です。",
    )


def build_slide_12_dump(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_title_bar(
        slide,
        "デバッグ: dump-and-diff",
        "TR_DUMP_STATE で binary vs library のずれを 1 発で特定",
    )

    code = (
        "# 1. バイナリ側で state を dump\n"
        "$ rm -f /tmp/dump_bin.txt\n"
        "$ TR_DUMP_STATE=/tmp/dump_bin.txt \\\n"
        "      bash test_run/run_tests.sh tr_tst2\n"
        "\n"
        "# 2. ライブラリ (Python) 側で同じ条件で dump\n"
        "$ rm -f /tmp/dump_lib.txt\n"
        "$ TR_DUMP_STATE=/tmp/dump_lib.txt python3 -c \"\n"
        "import os, sys; sys.path.insert(0, 'python')\n"
        "from trlib import Trlib\n"
        "from trlib.tests.fixtures import tr_tst2_params as f\n"
        "os.chdir('test_run/test_output/tr_tst2')\n"
        "with Trlib() as tr:\n"
        "    f.apply(tr); tr.run(0)\n"
        "\"\n"
        "\n"
        "# 3. 差分を見る\n"
        "$ diff /tmp/dump_bin.txt /tmp/dump_lib.txt | head -60\n"
    )
    add_code_block(
        slide,
        Inches(0.4),
        Inches(1.3),
        Inches(8.4),
        Inches(5.4),
        code,
        font_size=12,
        title="dump-and-diff の手順",
    )

    add_bullets(
        slide,
        Inches(9.0),
        Inches(1.3),
        Inches(3.9),
        Inches(5.4),
        [
            "実装: tr/tr_dump_state.f90。",
            "env 未設定なら no-op (本番ゼロコスト)。",
            "binary / library で同じ tr_prep 末尾でフック。",
            "ヒープゴミ値 (1e-307 等) → uninit 配列。",
            "微小 ULP 差 → 数値ドリフト。",
            "片方ゼロ片方ゴミ → uninit + ヒープ偶然。",
            "詳細: feedback_dump_diff_approach.md。",
        ],
        font_size=12,
    )

    add_textbox(
        slide,
        Inches(0.4),
        Inches(6.85),
        Inches(12.5),
        Inches(0.5),
        "実例: PNSS / PTSA 未初期化バグはこの方法で 1 発で局所化 (2026-04-20)。"
        "新規モジュールに横展開する場合は <MOD>_DUMP_STATE 環境変数で同じパターンを採用してください。",
        font_size=11,
        color=COLOR_GRAY,
    )

    add_speaker_notes(
        slide,
        "デバッグ用の dump-and-diff 手法をご紹介します。"
        "tr/tr_dump_state.f90 が実装で、TR_DUMP_STATE 環境変数にファイルパスを設定するとそのファイルに状態をダンプします。"
        "未設定なら何もしないので、本番性能には一切影響しません。"
        "使い方は 3 ステップで、まずバイナリ tr2 で dump、次にライブラリ Python で同じ条件で dump、"
        "最後に diff コマンドで差分を取るだけです。"
        "tr_prep 末尾でフックされているため、binary と library の両方で同じタイミングのスナップショットが取れます。"
        "差分の読み方ですが、1e-307 のようなヒープゴミ値が出ていたら未初期化配列です。"
        "極小の ULP 差なら数値ドリフトで、それも累積上流の uninit が原因のことが多いです。"
        "片方ゼロ片方ゴミならフレッシュヒープの偶然で、ライブラリ側がバグを暴露しています。"
        "実例として、PNSS や PTSA の未初期化バグはこの方法で 1 発で局所化できました。",
    )


def build_slide_13_other_modules(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_title_bar(
        slide,
        "他モジュールへの拡張",
        "trlib と同じ API パターンで全モジュールが利用可能",
    )

    rows = [
        ["モジュール", "Python パッケージ", "クラス", "役割"],
        ["tr",   "python/trlib",   "Trlib",   "1 次元プラズマ輸送 (本日の主役)"],
        ["fp",   "python/fplib",   "Fplib",   "Fokker-Planck 解析"],
        ["ti",   "python/tilib",   "Tilib",   "不純物輸送"],
        ["wr",   "python/wrlib",   "Wrlib",   "波動レイトレーシング"],
        ["wrx",  "python/wrxlib",  "Wrxlib",  "拡張レイトレーシング"],
        ["eq",   "python/eqlib",   "Eqlib",   "MHD 平衡"],
        ["tot",  "python/totlib",  "Totlib",  "統合輸送 (他モジュール束ね)"],
    ]
    add_table(
        slide,
        Inches(0.4),
        Inches(1.3),
        Inches(12.5),
        Inches(3.6),
        rows,
        font_size=13,
    )

    add_bullets(
        slide,
        Inches(0.4),
        Inches(5.1),
        Inches(12.5),
        Inches(2.0),
        [
            "全モジュールが with X() as h: → set_param → run → get_state という同一パターン。",
            "fixture 規約も共通: SCALARS / ARRAYS / STRINGS の 3 辞書 + apply(h) 関数。",
            "tot は他モジュールを namespace prefix で束ねる (例: 'eq:RR' が eq モジュールの RR)。",
            "Layer 1 等価性、Layer 4 スイープテストも全モジュールで整備済み。",
            "MCP server (各モジュール 9 ツール) も同じ API の上に構築されている。",
        ],
        font_size=13,
    )

    add_speaker_notes(
        slide,
        "他モジュールへの拡張です。tr/fp/ti/wr/wrx/eq/tot の 7 モジュール全てが同じ API パターンで揃っています。"
        "Python パッケージ名は <mod>lib、クラス名は <Mod>lib という命名規則です。"
        "fixture 規約も共通で、SCALARS / ARRAYS / STRINGS の 3 辞書と apply(h) 関数を持ちます。"
        "tot は少し特殊で、他モジュールを namespace prefix で束ねる設計になっており、"
        "例えば 'eq:RR' と書くと eq モジュールの RR にアクセスできます。"
        "Layer 1 等価性テストと Layer 4 スイープテストも全モジュールで整備済みで、"
        "MCP サーバ (各モジュール 9 ツール) もこの API の上に構築されています。"
        "新しいモジュールを覚える際は trlib の感覚そのままで使えます。",
    )


def build_slide_14_mcp_overview(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_title_bar(
        slide,
        "tr_mcp サーバ概要",
        "LLM (Claude / Cursor) から JSON-RPC で trlib を駆動",
    )

    box_w = Inches(2.7)
    box_h = Inches(1.5)
    y_mid = Inches(2.1)

    llm = add_box(
        slide,
        Inches(0.4),
        y_mid,
        box_w,
        box_h,
        "LLM クライアント",
        "Claude Desktop\nClaude Code / Cursor",
        fill=COLOR_GRAY,
        title_size=14,
        sub_size=11,
    )
    server = add_box(
        slide,
        Inches(3.5),
        y_mid,
        box_w,
        box_h,
        "tr_mcp サーバ",
        "FastMCP (stdio)\npython/mcp-servers/\ntr_mcp/server.py",
        fill=COLOR_MCP,
        title_size=14,
        sub_size=10,
    )
    trlib_box = add_box(
        slide,
        Inches(6.6),
        y_mid,
        box_w,
        box_h,
        "trlib (Python)",
        "Trlib() ラッパー\nset_param / run /\nget_state",
        fill=COLOR_PYTHON,
        title_size=14,
        sub_size=11,
    )
    libso = add_box(
        slide,
        Inches(9.7),
        y_mid,
        box_w,
        box_h,
        "libtrapi.so",
        "Fortran カーネル\n(BIND(C) ABI)",
        fill=COLOR_FORTRAN,
        title_size=14,
        sub_size=11,
    )
    add_arrow(slide, llm, server, label="JSON-RPC")
    add_arrow(slide, server, trlib_box, label="handle_*")
    add_arrow(slide, trlib_box, libso, label="ctypes")

    add_textbox(
        slide,
        Inches(0.4),
        Inches(3.95),
        Inches(7.4),
        Inches(0.4),
        "公開ツール (FastMCP @mcp.tool() で 9 個):",
        font_size=14,
        bold=True,
        color=COLOR_MCP,
    )
    add_bullets(
        slide,
        Inches(0.4),
        Inches(4.35),
        Inches(7.4),
        Inches(2.6),
        [
            "中核 5: init / set_param / run / get_state / finalize",
            "一括設定: set_params (scalar / list / dict / str を許容)",
            "一発実行: run_and_get_state (init+set+run+get_state)",
            "補助: describe_parameters (登録済み param 一覧 + 型/group)",
            "補助: describe_state_schema (state の JSON-Schema)",
        ],
        font_size=13,
    )

    add_box(
        slide,
        Inches(8.0),
        Inches(4.35),
        Inches(4.9),
        Inches(2.6),
        "想定ユースケース",
        "・ 自然言語でのパラメータ探索\n"
        "・ 対話的な数値デバッグ\n"
        "・ ノートブック的な計算依頼\n"
        "・ LLM agent から sweep 自動化\n"
        "・ describe_* で自己発見的に学習",
        fill=COLOR_MCP,
        title_size=14,
        sub_size=12,
    )

    add_textbox(
        slide,
        Inches(0.4),
        Inches(7.05),
        Inches(12.5),
        Inches(0.4),
        "サーバ名は \"task-tr\"。1 プロセス = 1 Trlib インスタンス (libtrapi.so の COMMON シングルトン制約)。",
        font_size=11,
        color=COLOR_GRAY,
    )

    add_speaker_notes(
        slide,
        "ここからは MCP サーバ経由での使い方をご紹介します。"
        "tr_mcp は FastMCP ベースの MCP サーバで、Claude Desktop や Claude Code、"
        "Cursor といった LLM クライアントから JSON-RPC 越しに呼び出せます。"
        "サーバの中身は trlib の Trlib クラスを薄くラップしたもので、最終的には libtrapi.so に到達します。"
        "公開しているツールは全部で 9 個ですが、覚えるべき中核は 5 つで、init / set_param / run /"
        "get_state / finalize の 5 段階フローです。これは前半で説明した Python API と全く同じ構造です。"
        "加えて bulk 設定の set_params、一発実行の run_and_get_state、"
        "そして LLM が自己発見的にパラメータや state 構造を学べる describe_parameters と"
        "describe_state_schema の 2 つの補助ツールが揃っています。"
        "サーバ名は task-tr で、1 プロセス 1 インスタンスの制約は trlib と同じです。",
    )


def build_slide_15_mcp_setup(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_title_bar(
        slide,
        "起動と接続例",
        "python -m tr_mcp.server + Claude / Cursor 設定スニペット",
    )

    launch_code = (
        "# 1. 依存導入 (libtrapi.so は事前に make 済みであること)\n"
        "$ pip install 'mcp>=0.9'\n"
        "$ pip install -e python/mcp-servers/tr_mcp\n"
        "\n"
        "# 2. 直接起動 (stdio モード) — 動作確認用\n"
        "$ python -m tr_mcp.server\n"
        "$ python -m tr_mcp.server --print-tools   # 9 ツールを列挙\n"
        "$ python -m tr_mcp.server --help\n"
        "\n"
        "# 3. インストール済みなら entry-point script でも同じ\n"
        "$ tr-mcp\n"
    )
    add_code_block(
        slide,
        Inches(0.4),
        Inches(1.3),
        Inches(6.1),
        Inches(2.5),
        launch_code,
        font_size=12,
        title="起動方法",
    )

    config_code = (
        "// claude_desktop_config.json (macOS:\n"
        "//   ~/Library/Application Support/Claude/...\n"
        "//   Linux: ~/.config/claude-desktop/...) — パス要修正\n"
        "{\n"
        "  \"mcpServers\": {\n"
        "    \"task-tr\": {\n"
        "      \"command\": \"python\",\n"
        "      \"args\": [\"-m\", \"tr_mcp.server\"],\n"
        "      \"env\": {\n"
        "        \"PYTHONPATH\": \"/abs/path/to/task/python\",\n"
        "        \"TRLIB_PATH\":  \"/abs/path/to/task/tr/libtrapi.so\"\n"
        "      }\n"
        "    }\n"
        "  }\n"
        "}\n"
    )
    add_code_block(
        slide,
        Inches(6.7),
        Inches(1.3),
        Inches(6.2),
        Inches(2.5),
        config_code,
        font_size=11,
        title="Claude Desktop 設定",
    )

    cli_code = (
        "# Claude Code の場合 — CLI から登録できます\n"
        "$ claude mcp add task-tr \\\n"
        "    --env PYTHONPATH=/abs/path/to/task/python \\\n"
        "    --env TRLIB_PATH=/abs/path/to/task/tr/libtrapi.so \\\n"
        "    -- python -m tr_mcp.server\n"
        "\n"
        "# Cursor / VS Code 等も command/args は同じ要領\n"
    )
    add_code_block(
        slide,
        Inches(0.4),
        Inches(3.95),
        Inches(6.1),
        Inches(1.5),
        cli_code,
        font_size=12,
        title="Claude Code / Cursor",
    )

    add_box(
        slide,
        Inches(6.7),
        Inches(3.95),
        Inches(6.2),
        Inches(1.5),
        "トラブルシュート",
        "・ libtrapi.so 未ビルド → make -C tr libtrapi.so\n"
        "・ ModuleNotFoundError: mcp → pip install 'mcp>=0.9'\n"
        "・ ModuleNotFoundError: trlib → PYTHONPATH を再確認",
        fill=COLOR_TEST,
        title_size=14,
        sub_size=11,
    )

    add_box(
        slide,
        Inches(0.4),
        Inches(5.65),
        Inches(12.5),
        Inches(1.5),
        "stdout を JSON-RPC で汚染しないこと",
        "MCP は stdio で JSON-RPC を流すため、Fortran 側の print 出力が混ざると"
        "クライアントが parse error を起こします。tr_mcp は LLM 向けレスポンスのみ "
        "stdout に流す設計です。Fortran カーネル由来のログは scratch unit に逃がし、"
        "デバッグメッセージは stderr へ出します。\n"
        "新しく Fortran 側に WRITE(6,*) を追加した場合は scratch unit 経由に変更してください。",
        fill=COLOR_GRAY,
        title_size=14,
        sub_size=11,
    )

    add_textbox(
        slide,
        Inches(0.4),
        Inches(7.2),
        Inches(12.5),
        Inches(0.3),
        "上の JSON は説明用のサンプルです。実環境ではパスを絶対パスで書き換えてください。",
        font_size=10,
        color=COLOR_GRAY,
    )

    add_speaker_notes(
        slide,
        "起動方法と LLM クライアントへの登録方法です。"
        "まず python/mcp-servers/tr_mcp に対して pip install -e でインストールし、"
        "別途 mcp パッケージも入れます。"
        "起動は python -m tr_mcp.server で stdio モードに入ります。"
        "動作確認には --print-tools オプションが便利で、登録済みの 9 ツールが列挙されます。"
        "Claude Desktop の場合は claude_desktop_config.json に mcpServers エントリを追加します。"
        "ここに示した JSON は説明用のサンプルですので、PYTHONPATH と TRLIB_PATH は皆さんの環境に合わせて"
        "絶対パスで書き換えてください。"
        "Claude Code であれば claude mcp add コマンドで CLI から一発登録できます。"
        "Cursor や VS Code でも command と args の指定は同じ要領です。"
        "トラブルシュートとしては libtrapi.so 未ビルド、mcp パッケージ未導入、PYTHONPATH 漏れの 3 つが代表的です。"
        "もう一つ重要なのは stdout 汚染で、MCP は標準入出力で JSON-RPC を流すため、"
        "Fortran 側の print 出力が混入するとクライアントが parse error を起こします。"
        "tr_mcp はレスポンス以外を stdout に出さない設計になっており、"
        "Fortran ログは scratch unit に逃がしてあります。"
        "新しく WRITE(6,*) を追加した場合はこの設計を破らないよう注意してください。",
    )


def build_slide_16_mcp_session(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_title_bar(
        slide,
        "LLM 経由での実行例",
        "自然言語の依頼が JSON-RPC ツール呼び出しに展開される",
    )

    chat_text = (
        "User:\n"
        "  ITER ベースで NSMAX=4, RR=6.2, BB=5.3 にして\n"
        "  100 ステップ走らせて、TE プロファイルだけ返して。\n"
        "\n"
        "Assistant (内部 thought):\n"
        "  parameter 名は describe_parameters で確認済み。\n"
        "  RR/BB はスカラー、NSMAX は整数。\n"
        "  init → set_params → run(100) → get_state でいけそう。\n"
        "\n"
        "Assistant (返答):\n"
        "  100 ステップ実行しました。電子温度プロファイルです:\n"
        "    TE(0)       = 15.2 keV\n"
        "    TE(NRMAX/2) =  4.7 keV\n"
        "    TE(NRMAX)   =  0.4 keV\n"
        "  必要なら全 NRMAX 点のリストもお出しします。\n"
    )
    add_code_block(
        slide,
        Inches(0.4),
        Inches(1.3),
        Inches(6.1),
        Inches(5.6),
        chat_text,
        font_size=11,
        title="チャット風ログ (例示)",
    )

    rpc_text = (
        "// 1. 初期化\n"
        "{\"method\":\"tools/call\",\n"
        " \"params\":{\"name\":\"init\",\"arguments\":{}}}\n"
        "\n"
        "// 2. パラメータ一括設定\n"
        "{\"method\":\"tools/call\",\n"
        " \"params\":{\"name\":\"set_params\",\n"
        "   \"arguments\":{\"params\":{\n"
        "     \"NSMAX\":4, \"RR\":6.2, \"BB\":5.3}}}}\n"
        "\n"
        "// 3. 100 ステップ進める\n"
        "{\"method\":\"tools/call\",\n"
        " \"params\":{\"name\":\"run\",\n"
        "   \"arguments\":{\"ntmax\":100}}}\n"
        "\n"
        "// 4. 状態取得 (TE は profile[*].RT[0])\n"
        "{\"method\":\"tools/call\",\n"
        " \"params\":{\"name\":\"get_state\",\"arguments\":{}}}\n"
        "\n"
        "// 5. 後始末 (任意)\n"
        "{\"method\":\"tools/call\",\n"
        " \"params\":{\"name\":\"finalize\",\"arguments\":{}}}\n"
    )
    add_code_block(
        slide,
        Inches(6.7),
        Inches(1.3),
        Inches(6.2),
        Inches(5.6),
        rpc_text,
        font_size=10,
        title="JSON-RPC (LLM が裏で呼ぶ呼び出し列)",
    )

    add_box(
        slide,
        Inches(0.4),
        Inches(7.0),
        Inches(12.5),
        Inches(0.5),
        "運用上の注意",
        "・ アクセス制御: stdio は同一マシン内のみ。リモート公開時は SSH トンネル等で認可を担保。"
        "・ 長時間ジョブ: run(N) は同期呼出。N が大きい時はクライアントの timeout 延長を検討。",
        fill=COLOR_GRAY,
        title_size=12,
        sub_size=11,
    )

    add_speaker_notes(
        slide,
        "最後に LLM 経由での実行例です。"
        "左がチャット風のログで、ユーザが「ITER ベースで NSMAX=4, RR=6.2, BB=5.3 で 100 ステップ走らせて"
        "TE プロファイルだけ返して」と自然言語で依頼するシナリオです。"
        "LLM は事前に describe_parameters で名前と型を確認したうえで、"
        "右側に示した JSON-RPC 呼び出し列に展開してくれます。"
        "順序は init、set_params で 3 つのスカラーをまとめて設定、run(100) で 100 ステップ進行、"
        "get_state で結果取得、最後に必要なら finalize、という流れです。"
        "示した数値 TE(0)=15.2 keV などは説明用の架空値ですので、実物の値とは異なります。"
        "運用上の注意として、stdio トランスポートは同一マシン内のローカル通信ですので、"
        "リモートから呼ばせたい場合は SSH トンネルなど別途認可機構を挟んでください。"
        "また run(N) は同期呼び出しなので、N が大きく時間がかかる場合はクライアント側の"
        "タイムアウト設定を伸ばしておく必要があります。"
        "本日のお話は以上で、最後にまとめスライドに進みます。",
    )


def build_slide_17_summary(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_title_bar(slide, "まとめ + 参考", "5 行から始められる Python TR 計算")

    add_bullets(
        slide,
        Inches(0.4),
        Inches(1.3),
        Inches(12.5),
        Inches(2.5),
        [
            "trlib は ctypes 越しに libtrapi.so を呼ぶ薄い Python ラッパー。",
            "with Trlib() as tr: tr.run(N); state = tr.get_state() の 5 段階フロー。",
            "set_param / set_param_str / set_params の 3 種で全パラメータを設定。",
            "TrState dataclass + to_dict() で結果を JSON / matplotlib に直結。",
            "デバッグは TR_DUMP_STATE による dump-and-diff が確実。",
            "MCP 経由 (tr_mcp) で LLM から自然言語駆動も可能。",
            "他モジュール (fp/ti/wr/wrx/eq/tot) も同じ API パターン。",
        ],
        font_size=15,
    )

    rows = [
        ["種別", "場所"],
        ["Trlib クラス",          "python/trlib/trlib.py"],
        ["TrState dataclass",     "python/trlib/state.py"],
        ["例外階層",              "python/trlib/errors.py"],
        ["fixture 例 (TST-2)",    "python/trlib/tests/fixtures/tr_tst2_params.py"],
        ["fixture 例 (ITER01)",   "python/trlib/tests/fixtures/tr_iter01_params.py"],
        ["Layer 1 等価性テスト",  "python/trlib/tests/test_equivalence.py"],
        ["Layer 4 スイープテスト","python/trlib/tests/test_sweep.py"],
        ["dump モジュール",       "tr/tr_dump_state.f90"],
        ["パッケージ README",     "python/trlib/README.md"],
        ["MCP サーバ実装",        "python/mcp-servers/tr_mcp/server.py"],
        ["MCP サーバ README",     "python/mcp-servers/tr_mcp/README.md"],
    ]
    add_table(
        slide,
        Inches(0.4),
        Inches(3.95),
        Inches(12.5),
        Inches(3.2),
        rows,
        font_size=12,
    )

    add_textbox(
        slide,
        Inches(0.4),
        Inches(7.2),
        Inches(12.5),
        Inches(0.3),
        "ご清聴ありがとうございました。",
        font_size=14,
        bold=True,
        color=COLOR_TITLE,
        align=PP_ALIGN.CENTER,
    )

    add_speaker_notes(
        slide,
        "まとめです。trlib は 5 行で TR 計算を回せる薄いラッパーで、"
        "with Trlib() as tr というコンテキストマネージャ、3 種類のパラメータ設定メソッド、"
        "そして to_dict() で素の Python オブジェクトとして状態を取り出せます。"
        "デバッグは TR_DUMP_STATE による dump-and-diff が一番確実な手法です。"
        "他のモジュールも全く同じ API パターンなので、trlib に慣れれば fplib / wrlib なども"
        "そのまま使えます。"
        "参考リンクは表のとおりで、まずは README.md と test_equivalence.py を見ると実際の使い方がよく分かると思います。"
        "ご清聴ありがとうございました。",
    )


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main() -> None:
    prs = Presentation()
    set_slide_size(prs)

    builders = [
        build_slide_01_title,
        build_slide_02_overview,
        build_slide_03_build,
        build_slide_04_hello,
        build_slide_05_set_param,
        build_slide_06_run,
        build_slide_07_get_state,
        build_slide_08_lifecycle,
        build_slide_09_fixture,
        build_slide_10_sweep,
        build_slide_11_plot,
        build_slide_12_dump,
        build_slide_13_other_modules,
        build_slide_14_mcp_overview,
        build_slide_15_mcp_setup,
        build_slide_16_mcp_session,
        build_slide_17_summary,
    ]
    for fn in builders:
        fn(prs)

    out = (
        Path(__file__).parent
        / "2026-04-20-trlib-python-usage.pptx"
    )
    prs.save(str(out))
    print(f"wrote {out}  ({out.stat().st_size:,} bytes, {len(prs.slides)} slides)")


if __name__ == "__main__":
    main()
