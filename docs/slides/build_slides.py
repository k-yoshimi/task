"""Generate the TASK Python/MCP overview slide deck (.pptx).

Run with::

    python3 docs/slides/build_slides.py

Output: docs/slides/2026-04-task-python-mcp.pptx (16 slides, JA, 15-min talk).
"""
from pathlib import Path

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR


# ---- Style constants -------------------------------------------------------

JP_FONT = "Hiragino Kaku Gothic ProN"
JP_FONT_FALLBACK = "Yu Gothic"
MONO_FONT = "Menlo"

COLOR_TITLE = RGBColor(0x1F, 0x3A, 0x5F)
COLOR_ACCENT = RGBColor(0x2E, 0x86, 0xAB)
COLOR_TEXT = RGBColor(0x33, 0x33, 0x33)
COLOR_DIM = RGBColor(0x88, 0x88, 0x88)
COLOR_CODE_BG = RGBColor(0xF5, 0xF5, 0xF5)
COLOR_CODE_FG = RGBColor(0x22, 0x22, 0x22)

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)


# ---- Helpers ---------------------------------------------------------------


def set_jp_font(run, size=18, bold=False, color=COLOR_TEXT, mono=False):
    run.font.name = MONO_FONT if mono else JP_FONT
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color


def add_title_bar(slide, title_text):
    """Add a header bar with the slide title."""
    bar = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, 0, 0, SLIDE_W, Inches(0.85)
    )
    bar.line.fill.background()
    bar.fill.solid()
    bar.fill.fore_color.rgb = COLOR_TITLE
    tf = bar.text_frame
    tf.margin_left = Inches(0.4)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    run = p.add_run()
    run.text = title_text
    set_jp_font(run, size=24, bold=True, color=RGBColor(0xFF, 0xFF, 0xFF))


def add_footer(slide, page_no, total_pages):
    """Page number + project tag at the bottom."""
    box = slide.shapes.add_textbox(
        Inches(0.3), Inches(7.05), Inches(12.7), Inches(0.35)
    )
    tf = box.text_frame
    tf.margin_top = Inches(0)
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.RIGHT
    r = p.add_run()
    r.text = f"TASK Python/MCP — {page_no} / {total_pages}"
    set_jp_font(r, size=10, color=COLOR_DIM)


def add_bullets(slide, bullets, top=Inches(1.2), left=Inches(0.6),
                width=Inches(12.1), height=Inches(5.6), size=18):
    """bullets : list of str OR (str, level) tuples.

    A leading "* " or "+ " on a string becomes a primary bullet;
    "  - " becomes a sub-bullet (level 1).
    """
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
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
        prefix = "  " * level + ("• " if level == 0 else "– ")
        run = p.add_run()
        run.text = prefix + text
        set_jp_font(run, size=size - 2 * level)


def add_code_block(slide, code_lines, top, left=Inches(0.6),
                   width=Inches(12.1), height=Inches(2.2), size=14):
    box = slide.shapes.add_textbox(left, top, width, height)
    box.fill.solid()
    box.fill.fore_color.rgb = COLOR_CODE_BG
    box.line.color.rgb = COLOR_DIM
    tf = box.text_frame
    tf.margin_left = Inches(0.2)
    tf.margin_right = Inches(0.2)
    tf.margin_top = Inches(0.1)
    tf.margin_bottom = Inches(0.1)
    tf.word_wrap = False
    for i, line in enumerate(code_lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.LEFT
        r = p.add_run()
        r.text = line if line else " "
        set_jp_font(r, size=size, color=COLOR_CODE_FG, mono=True)


def add_text_block(slide, lines, top, left=Inches(0.6), width=Inches(12.1),
                   height=Inches(1.0), size=14, color=COLOR_TEXT, bold=False):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.LEFT
        r = p.add_run()
        r.text = line
        set_jp_font(r, size=size, color=color, bold=bold)


def add_table(slide, header, rows, top, left=Inches(0.6),
              col_widths=None, row_height=Inches(0.42), header_size=14, body_size=13):
    n_cols = len(header)
    n_rows = len(rows) + 1
    if col_widths is None:
        col_widths = [Inches(12.1 / n_cols)] * n_cols
    total_w = sum(col_widths, Emu(0))
    table_shape = slide.shapes.add_table(
        n_rows, n_cols, left, top, total_w, row_height * n_rows
    ).table
    for c, w in enumerate(col_widths):
        table_shape.columns[c].width = w
    for c, h in enumerate(header):
        cell = table_shape.cell(0, c)
        cell.fill.solid()
        cell.fill.fore_color.rgb = COLOR_TITLE
        tf = cell.text_frame
        tf.margin_left = Inches(0.08); tf.margin_right = Inches(0.08)
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = h
        set_jp_font(r, size=header_size, bold=True,
                    color=RGBColor(0xFF, 0xFF, 0xFF))
    for ri, row in enumerate(rows, start=1):
        for c, val in enumerate(row):
            cell = table_shape.cell(ri, c)
            cell.fill.solid()
            cell.fill.fore_color.rgb = (
                RGBColor(0xFA, 0xFA, 0xFA) if ri % 2 else
                RGBColor(0xFF, 0xFF, 0xFF)
            )
            tf = cell.text_frame
            tf.margin_left = Inches(0.08); tf.margin_right = Inches(0.08)
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.LEFT
            r = p.add_run()
            r.text = str(val)
            set_jp_font(r, size=body_size, color=COLOR_TEXT)


# ---- Slide builders --------------------------------------------------------


def slide_title(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])  # blank
    bar = s.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, 0, Inches(2.4), SLIDE_W, Inches(2.7)
    )
    bar.line.fill.background()
    bar.fill.solid()
    bar.fill.fore_color.rgb = COLOR_TITLE
    add_text_block(
        s,
        ["TASK プラズマライブラリの",
         "Python ラッパー化と MCP サーバ化"],
        top=Inches(2.7), left=Inches(0.8), width=Inches(11.7),
        height=Inches(2.0), size=40, color=RGBColor(0xFF, 0xFF, 0xFF), bold=True
    )
    add_text_block(
        s,
        ["— 大規模 Fortran 物理コードを LLM から呼び出せる形に —"],
        top=Inches(5.3), left=Inches(0.8), width=Inches(11.7),
        height=Inches(0.6), size=18, color=COLOR_ACCENT
    )
    add_text_block(
        s,
        ["k-yoshimi (東京大学)",
         "2026 年 4 月"],
        top=Inches(6.0), left=Inches(0.8), width=Inches(11.7),
        height=Inches(1.0), size=14, color=COLOR_DIM
    )
    return s


def slide_background(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_title_bar(s, "1. 背景と目的")
    add_bullets(s, [
        "TASK は核融合プラズマ統合シミュレーションの大規模 Fortran ライブラリ",
        "  - tr (transport), eq (equilibrium), ti (ion), fp (Fokker-Planck), wr/wrx (ray tracing), tot (orchestrator)",
        "  - 元々はインタラクティブ CLI (eqx2, trx 等) で操作する設計",
        "課題: 自動化・スイープ解析・LLM 統合がやりにくい",
        "  - Fortran バイナリは入出力がインライン NAMELIST + 標準入力ベース",
        "  - エラーは PAUSE / STOP で host を巻き込み, Python から扱えない",
        "  - パラメータの組合せ検証 (validate) が CLI に無い",
        "目的:",
        "  - Fortran カーネルを共有ライブラリ化 (libXapi.so)",
        "  - Python ラッパー (with 構文 / 例外型 / validate)",
        "  - MCP サーバで LLM から自然言語で操作",
    ])
    return s


def slide_overview(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_title_bar(s, "2. 全体像 — 7 モジュールの依存関係")
    add_table(s,
        ["モジュール", "役割", "依存先 (init 順)"],
        [
            ["tr", "transport (1D 拡散方程式)", "pl, eq → tr"],
            ["eq", "equilibrium (Grad-Shafranov 解)", "pl → eq"],
            ["ti", "ion transport (重イオン)", "pl, eq → ti"],
            ["fp", "Fokker-Planck (速度空間)", "pl, eq → fp"],
            ["wr / wrx", "ray tracing (RF 波)", "pl, eq → wr/wrx"],
            ["tot", "orchestrator (統合実行)", "tr + ti + fp + wrx をまとめて init"],
        ],
        top=Inches(1.2),
        col_widths=[Inches(2.0), Inches(5.3), Inches(4.8)]
    )
    add_text_block(s, [
        "現在: tot は L-6 で transport (TR) のみ実行. eq/ti/fp/wr の",
        "cross-module coupling は L-7 で実装予定.",
    ], top=Inches(5.5), size=14, color=COLOR_ACCENT)
    return s


def slide_layers(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_title_bar(s, "3. 3 層構成")
    add_table(s,
        ["層", "実体", "提供するもの"],
        [
            ["L1: Fortran 共有ライブラリ", "lib<mod>api.so",
             "C ABI 関数 (init/run/get_state/set_param/validate/finalize)"],
            ["L2: Python ラッパー", "python/<mod>lib/<mod>.py",
             "ctypes バインディング, 例外型, with 構文, NumPy 連携"],
            ["L3: MCP サーバ", "python/mcp-servers/<mod>_mcp/server.py",
             "FastMCP ツール (init / set_param / run / get_state / validate / ...)"],
        ],
        top=Inches(1.2),
        col_widths=[Inches(3.5), Inches(3.5), Inches(5.1)]
    )
    add_code_block(s, [
        "[Fortran F90/F77]",
        "    ↓ -shared, BIND(C, NAME=...)",
        "[lib<mod>api.so]   ← 旧 CLI と同じ計算カーネルを共有",
        "    ↓ ctypes (python/<mod>lib/_ffi.py)",
        "[Python wrapper]   ← Eq, Trlib, Tot, ...",
        "    ↓ MCP SDK (FastMCP)",
        "[MCP server]       ← Claude Desktop / Cursor 等から接続",
    ], top=Inches(4.2), height=Inches(2.7))
    return s


def slide_wrapper_1(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_title_bar(s, "4. Python ラッパーの共通設計 (1/2)")
    add_text_block(s, ["with 構文 + 単一プロセスシングルトン:"], top=Inches(1.1), size=16, bold=True)
    add_code_block(s, [
        "from eqlib import Eq",
        "",
        "with Eq() as eq:                    # __enter__: eq_init",
        "    eq.set_params(RR=3.0, RA=1.0, BB=3.0, RIP=1.5)",
        "    eq.run(mode=0)                  # 解析 GS 解",
        "    state = eq.get_state()          # → EqState (dataclass)",
        "    print(state.scalars['raxis'])   # 3.0709",
        "                                    # __exit__: eq_finalize",
    ], top=Inches(1.6), height=Inches(2.5))
    add_text_block(s, ["共通 API 形:"], top=Inches(4.4), size=16, bold=True)
    add_bullets(s, [
        "set_param(name, value) / set_param_str(name, str_val) — 単一値",
        "set_params(**kwargs) — 一括設定",
        "run(...) — モジュール固有の引数 (mode, ntmax, nray_request)",
        "get_state() → 専用 dataclass (scalars / 配列 / 識別子)",
        "validate() → diagnostics list (eq, tr のみ native)",
    ], top=Inches(4.9), height=Inches(2.0), size=15)
    return s


def slide_wrapper_2(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_title_bar(s, "5. Python ラッパーの共通設計 (2/2) — エラー型階層")
    add_table(s,
        ["例外クラス", "原因", "リトライ可否"],
        [
            ["XxxLibInitError", "init 失敗 (lib 未配置, シンボル欠損)", "× 環境問題"],
            ["XxxLibInvalidParamError", "set_param で無効な名前/値", "○ 値を直して再試行"],
            ["XxxLibCalculationFailedError", "run 中の数値発散・非収束", "○ DT 半減等"],
            ["XxxLibNotInitializedError", "init 前に run/get_state", "○ init 呼ぶ"],
            ["XxxLibStateError", "get_state でメモリ不整合", "△ 通常 init 漏れ"],
            ["XxxLibNotImplementedError", "未実装 mode (例: 旧 mode=0)", "× 実装待ち"],
        ],
        top=Inches(1.2),
        col_widths=[Inches(3.8), Inches(5.5), Inches(2.8)]
    )
    add_text_block(s, [
        "Fortran 側の C ABI return code (0=OK, 1=invalid, 2=not_init, 3=calc_failed,",
        "4=not_impl) を ctypes で受け取り, raise_for_rc() で適切な例外型に変換.",
    ], top=Inches(5.5), size=14, color=COLOR_ACCENT)
    return s


def slide_validate(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_title_bar(s, "6. validate API — 設定の事前検証")
    add_text_block(s, [
        "run() 前に「組合せが妥当か」を検査. 早期発見 + LLM への自動修正提案.",
    ], top=Inches(1.1), size=15)
    add_code_block(s, [
        "diags = eq.validate()                          # List[EqDiagEntry]",
        "for d in diags:",
        "    print(f'[{EqDiagCode(d.code).name}] {d.param}: {d.message}')",
        "",
        "# 例:",
        "#   [FILE_MISSING] KNAMEQ: MODELG=3/5/8 requires non-blank KNAMEQ",
        "#   [OUT_OF_RANGE] NRMAX: value 9999 exceeds compile-time maximum 1001",
    ], top=Inches(1.7), height=Inches(2.3))
    add_table(s,
        ["EqDiagCode", "意味", "発火例"],
        [
            ["OUT_OF_RANGE", "値が compile-time 上限超え", "NRMAX=9999 (max 1001)"],
            ["INCONSISTENT_PAIR", "2 値の整合性違反", "RB < RA"],
            ["FILE_MISSING", "必須ファイルパス未設定", "KNAMEQ='' (mode=1)"],
            ["MISSING_REQUIRED", "必須パラメータ未設定", "PA[i] (NSMAX>2 時)"],
        ],
        top=Inches(4.4),
        col_widths=[Inches(3.0), Inches(4.6), Inches(4.5)]
    )
    add_text_block(s, [
        "native validate あり: eq, tr のみ. 他 (ti/fp/wr/wrx) は",
        "applications.md に hand-rolled preflight を提供.",
    ], top=Inches(6.4), size=13, color=COLOR_ACCENT)
    return s


def slide_pattern_1(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_title_bar(s, "7. 応用パターン (1) StableXxxRunner — 失敗自動回避")
    add_text_block(s, [
        "run() が CalculationFailedError を投げたら DT を半減して再試行.",
    ], top=Inches(1.1), size=15)
    add_code_block(s, [
        "class StableTrRunner:",
        "    def run(self, ntmax):",
        "        for attempt in range(self.max_retries):",
        "            try:",
        "                self._tr.run(ntmax=ntmax)",
        "                return self._tr.get_state()",
        "            except TrlibRunError as e:",
        "                if self.dt <= self.dt_floor:",
        "                    raise RuntimeError(f'DT={self.dt} まで縮めても発散')",
        "                self.dt /= 2",
        "                self._tr.set_param('DT', self.dt)",
        "                self.retries += 1",
    ], top=Inches(1.7), height=Inches(3.6))
    add_bullets(s, [
        "tr/ti/fp で有効: 数値発散時にタイムステップ縮小で回避",
        "eq/wr/wrx は性質が違う (geometry エラー等) → safe_run / smart_run で代替",
    ], top=Inches(5.6), size=14, height=Inches(1.5))
    return s


def slide_pattern_2(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_title_bar(s, "8. 応用パターン (2) sweep — 多次元パラメータスキャン")
    add_code_block(s, [
        "def sweep(*, rr_values, bb_values, ntmax=10):",
        "    results = []",
        "    for rr, bb in itertools.product(rr_values, bb_values):",
        "        with Trlib() as tr:",
        "            tr.set_params(RR=rr, BB=bb, NSMAX=2)",
        "            tr.run(ntmax=ntmax)",
        "            state = tr.get_state()",
        "        results.append({'RR': rr, 'BB': bb,",
        "                        'BETAN': state.scalars['BETAN'],",
        "                        'WPT': state.scalars['WPT']})",
        "    return results",
    ], top=Inches(1.2), height=Inches(3.4))
    add_bullets(s, [
        "各点で独立な with ... — シングルトン Fortran state を毎回クリーン化",
        "結果を pandas.DataFrame に流せばヒートマップ化が簡単",
        "multiprocessing.Pool で並列化可 (プロセス間で Fortran state は分離)",
        "拡張: StableXxxRunner と組合せれば一部発散点も自動回避",
    ], top=Inches(4.8), size=14, height=Inches(2.3))
    return s


def slide_pattern_3(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_title_bar(s, "9. 応用パターン (3) auto_setup — 装置プリセット + validate")
    add_code_block(s, [
        "DEVICE_PRESETS = {",
        "    'ITER':  dict(RR=6.2, RA=2.0, BB=5.3, RIP=15.0, RKAP=1.7),",
        "    'JET':   dict(RR=2.96, RA=1.0, BB=3.4, RIP=4.0, RKAP=1.6),",
        "    'DIIID': dict(RR=1.67, RA=0.67, BB=2.1, RIP=2.0, RKAP=1.8),",
        "}",
        "",
        "def auto_setup(device='ITER', extra_params=None, eq_file=None):",
        "    eq = Eq().__enter__()",
        "    params = DEVICE_PRESETS[device].copy()",
        "    params.setdefault('RB', params['RA'] * 1.2)  # 壁半径自動算出",
        "    eq.set_params(**params)",
        "    diags = eq.validate()",
        "    if any(d.code in BLOCKING for d in diags):",
        "        raise RuntimeError(...)  # FILE_MISSING 等で即停止",
        "    return eq",
    ], top=Inches(1.2), height=Inches(4.5))
    add_text_block(s, [
        "全 7 モジュール (tr/eq/ti/fp/wr/wrx/tot) に同形パターンを展開済み",
        "(docs/sphinx/modules/*/ja/applications.md, 18 commit で追加).",
    ], top=Inches(6.0), size=14, color=COLOR_ACCENT)
    return s


def slide_mcp_arch(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_title_bar(s, "10. MCP サーバ構成")
    add_text_block(s, [
        "Model Context Protocol (Anthropic 仕様): LLM から外部ツールを呼ぶ標準",
        "実装は FastMCP (Python). 6 モジュール分の MCP サーバを提供.",
    ], top=Inches(1.1), size=15)
    add_table(s,
        ["MCP ツール", "対応 Python API", "用途"],
        [
            ["init", "Eq().__init__()", "ライブラリの初期化"],
            ["set_param / set_param_str", "eq.set_param(name, val)", "数値 / 文字列パラメータ"],
            ["set_params", "eq.set_params(**kw)", "一括設定 (dict)"],
            ["run", "eq.run(mode=0|1)", "計算実行"],
            ["get_state", "eq.get_state().to_dict()", "結果の dict 化"],
            ["validate", "eq.validate()", "事前検証"],
            ["describe_parameters", "(MCP 専用)", "パラメータ一覧 (LLM 自己発見用)"],
            ["run_and_get_state", "(複合)", "init+set+run+get の one-shot"],
            ["finalize", "eq.__exit__()", "クリーンアップ"],
        ],
        top=Inches(2.2), row_height=Inches(0.36),
        col_widths=[Inches(3.2), Inches(4.0), Inches(4.9)]
    )
    return s


def slide_mcp_usage(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_title_bar(s, "11. MCP 利用シナリオ — Claude Desktop からの操作例")
    add_text_block(s, ["ユーザ自然言語:"], top=Inches(1.1), size=14, bold=True)
    add_code_block(s, [
        "「ITER スケールの解析平衡を解いて, qaxis と qsurf を教えて」",
    ], top=Inches(1.5), height=Inches(0.6), size=15)
    add_text_block(s, ["LLM が選ぶツール (順序):"], top=Inches(2.3), size=14, bold=True)
    add_code_block(s, [
        "1. eq_mcp:init",
        "2. eq_mcp:set_params({RR:6.2, RA:2.0, BB:5.3, RIP:15.0, RB:2.4})",
        "3. eq_mcp:validate                      → []  (問題なし)",
        "4. eq_mcp:run({mode:0})                 → 'eq_run completed (mode=0)'",
        "5. eq_mcp:get_state()                   → {scalars:{raxis:6.249, qaxis:0.596, ...}}",
        "6. (LLM が結果を自然言語で要約)",
    ], top=Inches(2.7), height=Inches(2.5))
    add_text_block(s, ["LLM 応答例:"], top=Inches(5.4), size=14, bold=True)
    add_code_block(s, [
        "「ITER スケール (RR=6.2 m, BB=5.3 T, RIP=15 MA) の解析的平衡を解きました.",
        " 中心 q (qaxis) は 0.596 で 1 を下回るため sawtooth 不安定領域,",
        " 縁 q (qsurf) は 3.565 で安全係数 q95 ~ 3 の典型的 ITER 設計値です.」",
    ], top=Inches(5.8), height=Inches(1.3), size=12)
    return s


def slide_mode_zero(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_title_bar(s, "12. 実装例: eq.run(mode=0) — 旧 CLI の R コマンド復活")
    add_text_block(s, [
        "課題: デフォルト MODELG=2 (解析座標) では eq_load (mode=1) が",
        "「UNKNOWN MODELG」で失敗. 解析的平衡が走らない状態だった.",
    ], top=Inches(1.1), size=14)
    add_table(s,
        ["mode", "Fortran 呼出", "対応 CLI コマンド", "条件"],
        [
            ["0 (新規)", "EQCALC + EQCALQ", "R (Run) + F (Fields)", "MODELG ∈ {0,1,2} 解析"],
            ["1 (既存)", "equnit::eq_load", "L (Load)", "MODELG ∈ {3,5,8} ファイル"],
        ],
        top=Inches(2.4),
        col_widths=[Inches(2.0), Inches(3.7), Inches(3.5), Inches(2.9)]
    )
    add_code_block(s, [
        "with Eq() as eq:",
        "    eq.set_params(RR=3.0, RA=1.0, BB=3.0, RIP=1.5)",
        "    eq.run(mode=0)              # ← 新規: 解析 GS 解 + post-process",
        "    state = eq.get_state()",
        "    # state.scalars: raxis=3.0709, qaxis=0.9918, qsurf=3.7668,",
        "    #                betat=8.47e-05, betap=8.46e-03, pvol=59.16",
    ], top=Inches(4.0), height=Inches(2.4))
    add_text_block(s, [
        "EQCALC のみだと qaxis 等 post-processed scalar が空 → EQCALQ も chain.",
        "CLI の R → F 連続実行と等価.",
    ], top=Inches(6.5), size=13, color=COLOR_ACCENT)
    return s


def slide_build(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_title_bar(s, "13. ビルド・インストール")
    add_text_block(s, ["ワンショットセットアップ (Linux / macOS):"], top=Inches(1.1), size=15, bold=True)
    add_code_block(s, [
        "$ git clone <repo> task && cd task",
        "$ scripts/setup.sh           # bpsd clone + lib*api.so 全ビルド",
        "$ export PYTHONPATH=$(pwd)/python:$PYTHONPATH",
        "$ python3 -c 'from eqlib import Eq; print(Eq)'",
    ], top=Inches(1.6), height=Inches(1.6))
    add_text_block(s, ["MCP サーバ起動 (Claude Desktop / Cursor 設定例):"], top=Inches(3.5), size=15, bold=True)
    add_code_block(s, [
        '{',
        '  "mcpServers": {',
        '    "task-eq": {',
        '      "command": "python", "args": ["-m", "eq_mcp.server"],',
        '      "env": {',
        '        "PYTHONPATH": "/abs/path/to/task/python",',
        '        "EQLIB_PATH": "/abs/path/to/task/eq/libeqapi.so"',
        '      }',
        '    }',
        '  }',
        '}',
    ], top=Inches(4.0), height=Inches(2.8))
    return s


def slide_future(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_title_bar(s, "14. 今後の予定")
    add_bullets(s, [
        "L-7: cross-module coupling 実装",
        "  - tot.run() で wr → tr (RF 加熱) / fp → tr (電流駆動) / eq → tr (時刻ごと平衡更新)",
        "  - tot.run_module(name) / tot.run_pipeline(steps) / tot.couple(src, dst)",
        "ベンチマーク + CI 強化",
        "  - 等価性テスト 1e-10 を全モジュールで継続",
        "  - 大規模スイープ (RR × BB × RKAP × RDLT) の自動回帰",
        "Web GUI / Notebook 統合",
        "  - Jupyter quickstart notebook (eq, tr 既存) → 全モジュール",
        "  - ipywidgets で interactive parameter sweep",
        "LLM 連携の高度化",
        "  - validate 出力の自然言語化 → LLM が修正提案を返す",
        "  - 装置プリセットの自動推薦 (ユーザ自然言語 → DEVICE_PRESETS マッチング)",
    ])
    return s


def slide_summary(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_title_bar(s, "15. まとめ")
    add_bullets(s, [
        "TASK の Fortran カーネルを 3 層に再構成",
        "  - L1 共有ライブラリ (lib*api.so) → L2 Python ラッパー → L3 MCP サーバ",
        "全 7 モジュール (tr/eq/ti/fp/wr/wrx/tot) で API 形を統一",
        "  - with 構文, set_param[s], run, get_state, validate, finalize",
        "応用パターンを 3 種に整理",
        "  - StableXxxRunner / sweep / auto_setup with validate",
        "Sphinx 日本語+英語マニュアルで全パターンを動作検証付きで文書化",
        "  - 18 commits でモジュール間横展開 + EN 翻訳完了",
        "MCP 経由で LLM から自然言語操作が可能",
        "  - Claude Desktop / Cursor から ITER 解析平衡を 1 クエリで取得実証済",
    ], size=15)
    return s


def slide_resources(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    add_title_bar(s, "16. リソース")
    add_table(s,
        ["項目", "場所"],
        [
            ["リポジトリ", "github.com/k-yoshimi/task (chore/pre-push-hook-worktree-compat)"],
            ["Sphinx ドキュメント (ja/en)", "docs/sphinx/modules/<mod>/{ja,en}/index.html"],
            ["Python ラッパー", "python/<mod>lib/ (eqlib, trlib, tilib, fplib, wrlib, wrxlib, totlib)"],
            ["MCP サーバ", "python/mcp-servers/<mod>_mcp/ (eq, tr, ti, fp, wr, wrx, tot)"],
            ["Quickstart ノートブック", "docs/sphinx/modules/{tr,eq}/{ja,en}/<mod>-quickstart.ipynb"],
            ["セットアップスクリプト", "scripts/setup.sh"],
            ["スライド (本資料) 生成", "docs/slides/build_slides.py"],
        ],
        top=Inches(1.2), row_height=Inches(0.5),
        col_widths=[Inches(3.5), Inches(8.6)]
    )
    add_text_block(s, [
        "本資料は python-pptx で生成. 本文の差分は build_slides.py の編集で再生成可能.",
    ], top=Inches(5.6), size=13, color=COLOR_ACCENT)
    add_text_block(s, ["ご清聴ありがとうございました."],
                   top=Inches(6.3), size=20, bold=True, color=COLOR_TITLE)
    return s


# ---- Main ------------------------------------------------------------------


def build():
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H

    builders = [
        slide_title,
        slide_background,
        slide_overview,
        slide_layers,
        slide_wrapper_1,
        slide_wrapper_2,
        slide_validate,
        slide_pattern_1,
        slide_pattern_2,
        slide_pattern_3,
        slide_mcp_arch,
        slide_mcp_usage,
        slide_mode_zero,
        slide_build,
        slide_future,
        slide_summary,
        slide_resources,
    ]
    total = len(builders)
    for i, build_fn in enumerate(builders, start=1):
        s = build_fn(prs)
        if i > 1:  # title slide gets no footer
            add_footer(s, i, total)

    out = Path(__file__).with_name("2026-04-task-python-mcp.pptx")
    prs.save(out)
    return out


if __name__ == "__main__":
    out = build()
    print(f"wrote {out} ({out.stat().st_size:,} bytes)")
