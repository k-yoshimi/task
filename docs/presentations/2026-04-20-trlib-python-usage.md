# trlib (TASK/TR Python wrapper) 使い方ガイド

**発表日:** 2026 年 4 月 20 日
**想定時間:** 18 分
**スライド枚数:** 17 枚
**スライドファイル:** [`2026-04-20-trlib-python-usage.pptx`](2026-04-20-trlib-python-usage.pptx)
**生成スクリプト:** [`_build_trlib_usage.py`](_build_trlib_usage.py)

このドキュメントは、上記 pptx の発表用 outline (各スライドの要点 + speaker
notes) です。pptx 本体には全スライドにスピーカーノートが埋め込まれて
いますが、こちらでも一覧できるように整理しています。**本文・タイトル・
notes すべて日本語 (です・ます調)** です。

---

## スライド一覧と想定時間配分 (合計 約 18 分)

| # | タイトル | 想定時間 |
|---|----------|----------|
| 1 | タイトル | 0:30 |
| 2 | 全体像: tr2 バイナリ vs libtrapi.so + trlib | 1:30 |
| 3 | ビルド手順 | 1:00 |
| 4 | Hello world: 5 行で TR を駆動 | 1:00 |
| 5 | パラメータ設定の 3 種類 | 1:30 |
| 6 | 実行とステップ制御: tr.run(ntmax) | 1:30 |
| 7 | 状態取得: TrState と to_dict() | 1:30 |
| 8 | ライフサイクル: with / close / 再利用 | 1:00 |
| 9 | 既存 .in からの fixture 化 | 1:00 |
| 10 | パラメータスイープ例 | 1:30 |
| 11 | プロット例: matplotlib | 1:00 |
| 12 | デバッグ: dump-and-diff | 1:30 |
| 13 | 他モジュールへの拡張 | 0:30 |
| 14 | tr_mcp サーバ概要 | 1:00 |
| 15 | 起動と接続例 | 1:00 |
| 16 | LLM 経由での実行例 | 1:00 |
| 17 | まとめ + 参考 | 0:30 |

合計: 約 18 分。

---

## スライド 1: タイトル

- 演題: 「trlib (TASK/TR Python wrapper) 使い方ガイド」
- 副題: 「Python から TASK/TR プラズマ輸送計算を駆動する」
- 発表日: 2026 年 4 月 20 日
- 対象: tr/libtrapi.so + python/trlib (Layer 1 1e-10 等価性確認済)

**Speaker notes:** 本日は trlib、つまり TASK/TR の Python ラッパーの使い方を
ご紹介します。tr モジュールは 1 次元プラズマ輸送計算を担当する Fortran コード
で、従来は CLI バイナリ tr2 として動かしていました。今回、共有ライブラリ
libtrapi.so と Python ラッパー trlib を介して、Python スクリプトから直接
呼べるようになっています。想定時間は 15 分です。

## スライド 2: 全体像: tr2 バイナリ vs libtrapi.so + trlib

- 上段 (CLI): namelist .in → tr2 バイナリ → ファイル出力
- 下段 (Python): Python script → libtrapi.so (BIND(C) 5 関数) → Fortran カーネル → TrState
- Fortran カーネルは tr2 と libtrapi.so で同一実装。
- trlib は ctypes 越しの薄い層、状態は TrState dataclass。

**Speaker notes:** 全体像です。上段が従来の CLI 経路で、namelist .in を tr2
バイナリに食わせてファイル出力するという流れです。下段が今回追加した Python
経路で、Python から ctypes 越しに libtrapi.so の 5 つの BIND(C) 関数を
呼びます。重要なのは Fortran カーネルが共通である点で、Layer 1 等価性テスト
で 1e-10 の同等性を確認済みです。

## スライド 3: ビルド手順

```bash
$ make -C tr libtrapi.so          # 1. 共有ライブラリのビルド
$ export PYTHONPATH=$PWD/python   # 2. Python パスを通す
$ python3 -c 'from trlib import Trlib; print(Trlib)'  # 3. 動作確認
$ export TRLIB_LIBRARY=/path/to/libtrapi.so           # 4. (任意) パス上書き
```

- 依存: gfortran / lapack / blas (CLI と同じ)。
- ctypes のみ使用 — pip install 不要。
- graphics シンボル未解決でも RTLD_LAZY で dlopen 可。
- トラブル: OSError → `make -C tr libtrapi.so` を再実行。

**Speaker notes:** ビルド手順は 3 ステップだけです。tr ディレクトリで
make libtrapi.so、PYTHONPATH に repo/python を通し、import が通るか確認します。
TRLIB_LIBRARY 環境変数または Trlib(lib_path=...) で .so の位置を上書きできます。

## スライド 4: Hello world: 5 行で TR を駆動

```python
from trlib import Trlib

with Trlib() as tr:
    tr.run(0)              # tr_prep のみを起動 (0 ステップ)
    state = tr.get_state() # TrState を取得

print(state.nrmax, state.nsmax, state.nt)
print(state.scalars['T'], state.scalars['WPT'])
```

- with 文で tr_init / tr_finalize を自動管理。
- run(0) は 0 ステップ実行 = tr_prep のみ起動 (有効なスモーク)。
- Trlib() は process 内シングルトン (libtrapi.so の COMMON が一つ)。
- ierr は raise_for_ierr() で TrlibError 派生例外に変換。

**Speaker notes:** 最小の hello world です。with Trlib() as tr で tr_init が
呼ばれ、run(0) で tr_prep だけが走ります。get_state で TrState を取り出せます。
重要なのは Trlib() がプロセス内シングルトンになっていることです。

## スライド 5: パラメータ設定の 3 種類

```python
with Trlib() as tr:
    tr.set_param('RR', 6.2)             # スカラー
    tr.set_param('PA[2]', 1.0)          # 配列要素 (1-origin)
    tr.set_param('PN[1]', 0.7)
    tr.set_param_str('KNAMEQ', 'eqdata.TST-2')   # 文字列
    tr.set_params(RR=6.2, BB=5.3, NSMAX=2, DT=1.0e-5)  # kwargs
```

- 添字 [i] は 1-origin、2D は [i,j] (registry が解析)。
- set_param_str は文字列専用。
- set_params の kwargs に [ ] は書けないので配列要素は set_param で。
- 利用可能な名前は `tr/tr_param_registry.f90` の SELECT CASE を参照。

**Speaker notes:** パラメータ設定には 3 種類あります。set_param が基本、
配列要素は PA[2] のように 1-origin の添字を文字列で書きます。
set_param_str は KNAMEQ などのファイル参照用。set_params はキーワード引数で
複数のスカラーをまとめて設定できます。

## スライド 6: 実行とステップ制御: tr.run(ntmax)

```python
with Trlib() as tr:
    tr_tst2_params.apply(tr)
    tr.run(0)        # tr_prep のみ
    tr.run(5)        # 5 ステップ → NT=5
    tr.run(5)        # さらに 5 ステップ → NT=10
    print(tr.get_state().nt)  # 10
```

- run(N) は内部で tr_run(N) を呼ぶ。
- N=0 は tr_prep のみ起動 (合法)。
- N>0 は累積で NT が増加。
- 再度 run() を呼んでも tr_prep は再実行されない。
- ierr=3 で TrlibRunError (収束失敗等)。

**検証: run(5)+run(5) vs run(10) (tst2 で実測):**
- `run(10)`:                ZEFF0 = 1.3292981098481862
- `run(5)+run(5)`:          ZEFF0 = 1.3292981098485062  (digit 13 で差)
- `run(3)+run(3)+run(4)`:   ZEFF0 = 1.3292981098507612  (digit 11 で差)
- → 12 桁一致するが bit-identical ではない。Layer 1 1e-10 tol 内なので test は通るが、
  step 分割の noise は API ユーザに告知すべき仕様 (CPU 時刻・累積 statics 等の影響)。

**Speaker notes:** tr.run の呼び出し意味論についてです。run(N) は tr_run(N) を
呼んで N ステップ進めます。N=0 は tr_prep のみを起動する合法なケースです。
重要なのは累積セマンティクスで、run(5) を呼んだあとに run(5) を呼ぶと、
状態は run(10) と同じになるはずです — 検証結果は親プロセスから埋めてください。

## スライド 7: 状態取得: TrState と to_dict()

```python
state = tr.get_state()
state.nt        # int
state.nrmax     # int
state.nsmax     # int
state.scalars   # dict (T, WPT, AJT, Q0, BETA0, BETAP0, BETAA, BETAN,
                #       TAUE1, TAUE2, ZEFF0, ALI, RQ1)
state.RN        # [nrmax][nsmax]
state.RT        # [nrmax][nsmax]
state.AJ        # [nrmax]
state.QP        # [nrmax]

import json
json.dump(state.to_dict(), open('out.json', 'w'))
```

```json
{
  "NT": 10, "NRMAX": 50, "NSMAX": 2,
  "scalars": {"T": 1.0e-4, "WPT": 1.23e-3, "Q0": 1.05, ...},
  "profile": [
    {"NR": 1, "RN": [...], "RT": [...], "AJ": ..., "QP": ...},
    ...
  ]
}
```

- `to_dict()` 形状は Phase 0 baseline (`extract_tr_metrics.py`) と一致 →
  `tools/compare_metrics.py` でそのまま 1e-10 比較可。

**Speaker notes:** get_state は TrState という dataclass を返します。
属性として nt, nrmax, nsmax, scalars 辞書 (14 個のスカラー)、4 つの
プロファイル配列を持ちます。numpy には依存していないので、to_dict() の結果は
そのまま JSON にダンプできます。

## スライド 8: ライフサイクル: with / close / 再利用

```python
# パターン 1: with 文 (推奨)
with Trlib() as tr:
    tr.run(10)

# パターン 2: try/finally
tr = Trlib()
try:
    tr.run(10)
finally:
    tr.close()
    tr.close()    # 冪等 (no-op)

# パターン 3: ループで再利用
for case in cases:
    with Trlib() as tr:
        case.apply(tr)
        tr.run(case.NTMAX)
        results.append(tr.get_state().to_dict())
```

- `__del__` も close を試みる (例外は呑む)。
- Trlib() を 2 個同時に開くと COMMON が共有される。
- ループでは毎回 with で開閉 → 状態リーク回避。

**Speaker notes:** ライフサイクルの 3 パターンです。with 文が推奨、close() は
冪等。libtrapi.so は COMMON ブロックを持つシングルトン状態なので、
スイープでは毎ループで with を抜けて再 init することで前回の状態漏れを
防ぎます。ヒープ再利用による状態漏れも対策済みです。

## スライド 9: 既存 .in からの fixture 化

namelist と Python fixture の対応:

```fortran
! test_run/inputs/tr_tst2.in
&TR
  modelg=3
  KNAMEQ='eqdata.TST-2'
  NSMAX=2
  PA(2)=1.D0
  PN =0.010D0,0.010D0
  DT=1.D-5
  NTMAX=10
&END
```

```python
# python/trlib/tests/fixtures/tr_tst2_params.py
SCALARS = {'MODELG': 3, 'NSMAX': 2, 'DT': 1.0e-5, 'NTMAX': 10}
ARRAYS  = {'PA': {2: 1.0}, 'PN': [0.010, 0.010]}
STRINGS = {'KNAMEQ': 'eqdata.TST-2'}

def apply(tr):
    for k, v in STRINGS.items(): tr.set_param_str(k, str(v))
    for k, v in SCALARS.items(): tr.set_param(k, float(v))
    for n, a in ARRAYS.items():  _apply_array(tr, n, a)
```

- 規約: SCALARS / ARRAYS / STRINGS の 3 辞書で分類。
- ARRAYS は dict (添字付き) または list (1-origin 全要素)。

**Speaker notes:** 既存の namelist 入力ファイルから fixture モジュールへ
転記する方法です。3 つの辞書 SCALARS / ARRAYS / STRINGS に分類するだけです。
apply(tr) 関数で順番に set_param_str → set_param → 配列展開を呼びます。
string が先なのは KNAMEQ などのファイル参照を tr_prep より前に読ませるためです。

## スライド 10: パラメータスイープ例

```python
from trlib import Trlib
from trlib.tests.fixtures import tr_iter01_params
import os
from pathlib import Path

RR_VALUES = (7.5, 8.0, 8.5)
BB_VALUES = (4.5, 5.0, 5.5)
NTMAX = 5

os.chdir(Path('test_run/test_output/tr_iter01'))

results = []
for rr in RR_VALUES:
    for bb in BB_VALUES:
        with Trlib() as tr:
            tr_iter01_params.apply(tr)
            tr.set_param('RR', float(rr))
            tr.set_param('BB', float(bb))
            tr.run(NTMAX)
            wpt = tr.get_state().scalars['WPT']
            results.append((rr, bb, wpt))
```

- ベース fixture を共通化。
- 毎ループ Trlib() を再生成 → 状態リーク防止。
- MODELG=3 では eqdata の chdir が必要。
- 実装例: `python/trlib/tests/test_sweep.py` (Layer 4 スモークテスト)。

**Speaker notes:** test_sweep.py を簡略化したものです。RR と BB を 3 段階ずつ
振って 3×3 のグリッドを回します。毎ループで Trlib() を with 文で開き直すのが
ポイントです。MODELG=3 のケースでは eqdata.ITER01 を読むため、
test_run/test_output/tr_iter01 に chdir する必要があります。
scipy.optimize や bayesian-optimization と組み合わせて最適化することもできます。

## スライド 11: プロット例: matplotlib

```python
import matplotlib.pyplot as plt
from trlib import Trlib
from trlib.tests.fixtures import tr_tst2_params
import os

os.chdir('test_run/test_output/tr_tst2')

with Trlib() as tr:
    tr_tst2_params.apply(tr)
    tr.run(tr_tst2_params.NTMAX)
    state = tr.get_state()

d = state.to_dict()
rho = [row['NR'] / d['NRMAX'] for row in d['profile']]
te  = [row['RT'][0]            for row in d['profile']]
ti  = [row['RT'][1]            for row in d['profile']]

fig, ax = plt.subplots()
ax.plot(rho, te, label='Te')
ax.plot(rho, ti, label='Ti')
ax.set_xlabel(r'$\rho$  (normalised radius)')
ax.set_ylabel('temperature [keV]')
ax.legend()
fig.savefig('te_profile.png')
```

- to_dict() は素の Python list/dict (numpy 不要)。
- RT[0] が電子、RT[1] が主イオン。
- AJ / QP も同様に取り出せる。

**Speaker notes:** matplotlib に直接 state.to_dict() を渡す書き方です。
to_dict() の profile キーは長さ NRMAX のリストで、各要素が NR / RN / RT / AJ /
QP を持ちます。tr.plot('RT') のような可視化 API は将来の visualization
followup として保留中です。

## スライド 12: デバッグ: dump-and-diff

```bash
# 1. バイナリ側で state を dump
$ rm -f /tmp/dump_bin.txt
$ TR_DUMP_STATE=/tmp/dump_bin.txt bash test_run/run_tests.sh tr_tst2

# 2. ライブラリ (Python) 側で同じ条件で dump
$ rm -f /tmp/dump_lib.txt
$ TR_DUMP_STATE=/tmp/dump_lib.txt python3 -c "
import os, sys; sys.path.insert(0, 'python')
from trlib import Trlib
from trlib.tests.fixtures import tr_tst2_params as f
os.chdir('test_run/test_output/tr_tst2')
with Trlib() as tr:
    f.apply(tr); tr.run(0)
"

# 3. 差分を見る
$ diff /tmp/dump_bin.txt /tmp/dump_lib.txt | head -60
```

- 実装: `tr/tr_dump_state.f90` (env 未設定なら no-op、本番ゼロコスト)。
- binary / library で同じ tr_prep 末尾でフック。
- ヒープゴミ値 (1e-307 等) → uninit 配列。
- 微小 ULP 差 → 数値ドリフト。
- 詳細: `feedback_dump_diff_approach.md` (memory)。

**Speaker notes:** TR_DUMP_STATE 環境変数にファイルパスを設定するとそのファイル
に状態をダンプします。未設定なら何もしないので本番性能には一切影響しません。
3 ステップ (binary dump → library dump → diff) で binary vs library の
ずれを 1 発で局所化できます。実例として、PNSS や PTSA の未初期化バグはこの
方法で 1 発で局所化できました。

## スライド 13: 他モジュールへの拡張

| モジュール | Python パッケージ | クラス | 役割 |
|---|---|---|---|
| tr   | python/trlib   | Trlib   | 1 次元プラズマ輸送 (本日の主役) |
| fp   | python/fplib   | Fplib   | Fokker-Planck 解析 |
| ti   | python/tilib   | Tilib   | 不純物輸送 |
| wr   | python/wrlib   | Wrlib   | 波動レイトレーシング |
| wrx  | python/wrxlib  | Wrxlib  | 拡張レイトレーシング |
| eq   | python/eqlib   | Eqlib   | MHD 平衡 |
| tot  | python/totlib  | Totlib  | 統合輸送 (他モジュール束ね) |

- 全モジュールが with X() as h: → set_param → run → get_state という
  同一パターン。
- fixture 規約も共通: SCALARS / ARRAYS / STRINGS + apply(h)。
- tot は他モジュールを namespace prefix で束ねる (例: 'eq:RR')。
- Layer 1 等価性、Layer 4 スイープテストも全モジュールで整備済み。
- MCP server (各モジュール 9 ツール) も同じ API の上に構築。

**Speaker notes:** 7 モジュール全てが同じ API パターンで揃っています。
fixture 規約も共通で、SCALARS / ARRAYS / STRINGS の 3 辞書と apply(h) 関数を
持ちます。新しいモジュールを覚える際は trlib の感覚そのままで使えます。

## スライド 14: tr_mcp サーバ概要

- LLM (Claude Desktop / Claude Code / Cursor) → JSON-RPC → tr_mcp サーバ →
  trlib → libtrapi.so の 4 段パイプライン。
- 公開ツール 9 個: 中核 5 (`init` / `set_param` / `run` / `get_state` /
  `finalize`)、一括 `set_params`、一発 `run_and_get_state`、補助
  `describe_parameters` / `describe_state_schema`。
- 用途: 自然言語でのパラメータ探索、対話的な数値デバッグ、ノートブック的な
  計算依頼、LLM agent での sweep 自動化。
- サーバ名は `task-tr`、1 プロセス = 1 Trlib インスタンス (COMMON 単一状態)。

**Speaker notes:** tr_mcp は FastMCP ベースの MCP サーバで、trlib を薄く
ラップして LLM クライアントに公開します。中核 5 ツールは Python API と同じ
5 段階フローで、加えて bulk 設定・一発実行・自己発見用の describe 系が揃って
います。サーバ名は task-tr、1 プロセス 1 インスタンスの制約は trlib と同じです。

## スライド 15: 起動と接続例

```bash
# 1. 依存導入 (libtrapi.so は事前に make 済み)
$ pip install 'mcp>=0.9,<2'
$ pip install -e python/mcp-servers/tr_mcp

# 2. 直接起動 (stdio モード)
$ python -m tr_mcp.server
$ python -m tr_mcp.server --print-tools   # 9 ツール列挙
$ python -m tr_mcp.server --help

# 3. entry-point script 経由
$ tr-mcp
```

```jsonc
// claude_desktop_config.json — パスは要修正
{
  "mcpServers": {
    "task-tr": {
      "command": "python",
      "args": ["-m", "tr_mcp.server"],
      "env": {
        "PYTHONPATH": "/abs/path/to/task/python",
        "TRLIB_PATH":  "/abs/path/to/task/tr/libtrapi.so"
      }
    }
  }
}
```

```bash
# Claude Code
$ claude mcp add task-tr \
    --env PYTHONPATH=/abs/path/to/task/python \
    --env TRLIB_PATH=/abs/path/to/task/tr/libtrapi.so \
    -- python -m tr_mcp.server
```

- トラブル: `libtrapi.so` 未ビルド → `make -C tr libtrapi.so`。
- `ModuleNotFoundError: mcp` → `pip install 'mcp>=0.9,<2'`。
- `ModuleNotFoundError: trlib` → `PYTHONPATH` に `<repo>/python` を追加。
- **stdout 汚染注意:** MCP は stdio で JSON-RPC を流すので Fortran 側の
  `WRITE(6,*)` が混入すると parse error。tr_mcp は scratch unit にログを
  逃がす設計。

**Speaker notes:** 起動は `python -m tr_mcp.server` で stdio モードに入ります。
Claude Desktop では `claude_desktop_config.json` に `mcpServers` エントリを
追加します。上に示した JSON は説明用サンプルですので、`PYTHONPATH` と
`TRLIB_PATH` は皆さんの環境に合わせて絶対パスで書き換えてください。
Claude Code は `claude mcp add` で CLI 一発登録できます。stdio は標準入出力で
JSON-RPC を流すため、Fortran 側の print 出力が混ざるとクライアントが parse
error を起こします。tr_mcp はレスポンス以外を stdout に出さない設計です。

## スライド 16: LLM 経由での実行例

**チャット風ログ (例示):**

```
User:
  ITER ベースで NSMAX=4, RR=6.2, BB=5.3 にして
  100 ステップ走らせて、TE プロファイルだけ返して。

Assistant (返答):
  100 ステップ実行しました。電子温度プロファイルです:
    TE(0)       = 15.2 keV
    TE(NRMAX/2) =  4.7 keV
    TE(NRMAX)   =  0.4 keV
```

**LLM が裏で呼ぶ JSON-RPC 順序:**

```jsonc
{"method":"tools/call",
 "params":{"name":"init","arguments":{}}}

{"method":"tools/call",
 "params":{"name":"set_params",
   "arguments":{"params":{"NSMAX":4,"RR":6.2,"BB":5.3}}}}

{"method":"tools/call",
 "params":{"name":"run","arguments":{"ntmax":100}}}

{"method":"tools/call",
 "params":{"name":"get_state","arguments":{}}}

{"method":"tools/call",
 "params":{"name":"finalize","arguments":{}}}
```

- `set_params` で 3 つのスカラーをまとめて設定 (個別の `set_param` でも可)。
- `get_state` の戻り値から profile[*].RT[0] を抜いて TE プロファイルとする。
- 上の数値 `TE(0)=15.2 keV` などは説明用の架空値。
- **アクセス制御:** stdio は同一マシン内のみ。リモート公開時は SSH トンネル
  等で認可を担保。
- **長時間ジョブ:** `run(N)` は同期呼出。N が大きい時はクライアントの
  timeout 延長を検討。

**Speaker notes:** ユーザが自然言語で「ITER ベースで NSMAX=4 / RR=6.2 / BB=5.3
で 100 ステップ走らせて TE プロファイルだけ返して」と依頼するシナリオです。
LLM は事前に `describe_parameters` で名前と型を確認したうえで、右側に示した
JSON-RPC 呼び出し列に展開します。順序は init → set_params → run(100) →
get_state → finalize の 5 段階です。示した数値は説明用の架空値ですので実物の
値とは異なります。stdio は同一マシン内の通信ですので、リモート呼び出しには
SSH トンネル等を別途挟んでください。

## スライド 17: まとめ + 参考

- trlib は ctypes 越しに libtrapi.so を呼ぶ薄い Python ラッパー。
- with Trlib() as tr: tr.run(N); state = tr.get_state() の 5 段階フロー。
- set_param / set_param_str / set_params の 3 種で全パラメータを設定。
- TrState dataclass + to_dict() で結果を JSON / matplotlib に直結。
- デバッグは TR_DUMP_STATE による dump-and-diff が確実。
- MCP 経由 (tr_mcp) で LLM から自然言語駆動も可能。
- 他モジュール (fp/ti/wr/wrx/eq/tot) も同じ API パターン。

| 種別 | 場所 |
|---|---|
| Trlib クラス               | `python/trlib/trlib.py` |
| TrState dataclass          | `python/trlib/state.py` |
| 例外階層                   | `python/trlib/errors.py` |
| fixture 例 (TST-2)         | `python/trlib/tests/fixtures/tr_tst2_params.py` |
| fixture 例 (ITER01)        | `python/trlib/tests/fixtures/tr_iter01_params.py` |
| Layer 1 等価性テスト       | `python/trlib/tests/test_equivalence.py` |
| Layer 4 スイープテスト     | `python/trlib/tests/test_sweep.py` |
| dump モジュール            | `tr/tr_dump_state.f90` |
| パッケージ README          | `python/trlib/README.md` |
| MCP サーバ実装             | `python/mcp-servers/tr_mcp/server.py` |
| MCP サーバ README          | `python/mcp-servers/tr_mcp/README.md` |

**Speaker notes:** trlib は 5 行で TR 計算を回せる薄いラッパーです。デバッグは
TR_DUMP_STATE による dump-and-diff が一番確実な手法です。MCP 経由なら LLM
から自然言語で叩けるので、対話的なパラメータ探索やデバッグに便利です。
他モジュールも全く同じ API パターンなので、trlib に慣れれば fplib / wrlib
などもそのまま使えます。ご清聴ありがとうございました。

---

## 補足: pptx 再生成手順

```bash
cd <repo root>
python3 docs/presentations/_build_trlib_usage.py
```

依存: `python-pptx >= 1.0`、Noto Sans CJK JP フォント
(`/usr/share/fonts/opentype/noto/`)。
