# `tr` — 輸送計算

```{admonition} この章で学ぶこと
:class: tip

TASK/TR (1 次元トカマク輸送シミュレーション) を Python から呼び出す
ライブラリ `trlib` の使い方を学びます. 共有ライブラリのビルド,
最短 hello-world (5 行), パラメータ設定 (4 通り — スカラー / 配列 /
文字列 / `validate()`), FAQ, そしてテスト実行までカバーします.
```

```{toctree}
:hidden:

quickstart
api-reference
```

## 概要 — `tr` は何をする

**TASK/TR** は, トカマクや球状トカマクの **1 次元 (半径方向) 輸送シミュ
レーション** を行うモジュールです. 「プラズマの半径方向の分布が, 時間と
ともにどう変化するか」を, 粒子数・温度・電流・磁場の平衡を解きながら
追跡します.

得られる代表的な量:

- `RN[i][j]` — 半径点 $i$ での $j$ 番目の粒子種の密度
- `RT[i][j]` — 同じく温度
- `AJ[i]`    — 電流密度プロファイル
- `QP[i]`    — 安全係数 $q$ プロファイル
- スカラー: `T` (時間), `WPT` (蓄積エネルギー), `Q0` (中心 $q$),
  `BETAN` ($\beta_N$) など 13 種

Fortran 設計・パラメータレジストリの詳細は
{doc}`../common/architecture` および `docs/tr-library/architecture.md`
を参照.

## 前提とビルド

### ライブラリをビルドする

```bash
cd /path/to/task                     # TASK リポジトリのルート
make -C lib  libs_pic                # 下位ライブラリの PIC 版
make -C pl   libs_pic                # プラズマ共通モジュール
make -C eq   libs_pic                # 平衡モジュール
make -C mtxp libs_pic                # 疎行列ソルバ
make -C bpsd libs_pic                # BPSD データ橋渡し
make -C tr   libtrapi.so             # tr モジュールの共有ライブラリ本体
```

最後に `tr/libtrapi.so` というファイルが出来ていれば成功です.

```bash
$ ls -lh tr/libtrapi.so
-rwxr-xr-x 1 user user 8.2M 4月 23 14:00 tr/libtrapi.so
```

ファイルサイズは環境によって違いますが, だいたい 5 〜 10 MB くらいです.

### エクスポートされている関数を確認する

```bash
$ nm -D tr/libtrapi.so | grep ' T tr_'
000000000005a1b0 T tr_finalize
000000000005a090 T tr_get_state
0000000000059e10 T tr_init
0000000000059f80 T tr_run
0000000000059d30 T tr_set_param
0000000000059ca0 T tr_set_param_str
00000000000?????? T tr_validate            # PR #172 以降
```

`T` 列のシンボルが「エクスポートされた関数」を示します.

### Python から見えるようにする

```bash
export PYTHONPATH=/path/to/task/python:$PYTHONPATH
```

こうすると `import trlib` が通ります.

## 最短 hello-world (5 行)

```python
from trlib import Trlib            # (1) インポート
with Trlib() as tr:                # (2) 初期化 (= tr_init 自動)
    tr.set_params(RR=3.0, BB=3.0)  # (3) 大半径 3m, 磁場 3T
    tr.run(ntmax=10)               # (4) 10 ステップ時間発展
    state = tr.get_state()         # (5) 状態を取得 (型は TrState)
print(state.scalars["T"])          # 最終時刻 (秒)
```

### 行ごとの解説

- **(1) `from trlib import Trlib`** — パッケージ `trlib` からクラス
  `Trlib` を読み込みます. `Trlib` は共有ライブラリのハンドル (持ち手)
  です.
- **(2) `with Trlib() as tr:`** — `with` 文は Python のコンテキスト
  マネージャ機能. 入る時に `__enter__` (= `tr_init`), 抜けるときに
  `__exit__` (= `tr_finalize`) が自動で呼ばれ, 後片付けを忘れる
  心配がありません.
- **(3) `tr.set_params(RR=3.0, BB=3.0)`** — スカラー値を一括でセット
  するヘルパー. Fortran の `/TR/` ネームリストと同じ名前 (`RR` = 大半径,
  `BB` = トロイダル磁場) をキーワード引数で指定します.
- **(4) `tr.run(ntmax=10)`** — 時間発展を 10 ステップ進めます. ステップ幅
  は `DT` (デフォルト 0.01 秒) です.
- **(5) `state = tr.get_state()`** — 現在の状態を `TrState` dataclass に
  写し取ります. `state.scalars["T"]` で現在時刻, `state.RT[i][j]` で温度
  プロファイルが取れます.

### 期待される出力例

```bash
$ PYTHONPATH=python python3 examples/quickstart.py
NT=50  NRMAX=50  NSMAX=2
T    = 0.5
WPT  = 8.3e+05
Q0   = 0.96
BETAA= 0.42
```

完全な実行可能 notebook: {doc}`quickstart`.

## パラメータの指定方法

4 通りあります.

### 方法 A — スカラー (`set_params`)

Python のキーワード引数で一括指定できます.

```python
tr.set_params(RR=7.5, RA=2.0, BB=5.3, DT=0.05, NTMAX=200)
```

### 方法 B — 配列要素 (`set_param`)

キーワード引数には `[` `]` が使えないので, 配列要素は `set_param` を
使います. **1-origin** (1 始まり) です.

```python
tr.set_param("PN[1]", 1.0)   # 1 番目の粒子種の密度
tr.set_param("PN[2]", 1.0)   # 2 番目
tr.set_param("CDW[12]", 0.5) # 配列 CDW の 12 番目
```

### 方法 C — 文字列パラメータ (`set_param_str`)

TR には平衡データファイル名 `KNAMEQ` など文字列パラメータがあります.
これは専用 API で与えます.

```python
tr.set_param_str("KNAMEQ", "eqdata.ITER01")
```

### 方法 D — 事前検証 (`validate`) <!-- PR #172 -->

```{admonition} 新機能 (PR #172)
:class: important

`validate()` はパラメータを `run()` に渡す前に一括検査する API です.
値域逸脱, 整合性違反, ファイル不在などを診断 dataclass のリストで
返します. パラメータ設定後, `run()` の前に呼ぶのが推奨フローです.
```

```python
from trlib import Trlib, TrDiagCode

with Trlib() as tr:
    tr.set_params(RR=3.0, BB=3.0, NSMAX=2)
    tr.set_param_str("KNAMEQ", "eqdata.missing")  # 存在しないファイル

    diags = tr.validate()
    for d in diags:
        print(f"[{TrDiagCode(d.code).name}] {d.param}: {d.message}")
    if diags:
        raise SystemExit("fix the diagnostics before running")

    tr.run(ntmax=10)
```

診断コードの一覧:

| コード | 意味 |
|---|---|
| `OUT_OF_RANGE`           | 値が許容範囲外 |
| `INCONSISTENT_PAIR`      | 関連パラメータ対の不整合 |
| `OUT_OF_RANGE_AFTER_DEP` | 依存パラメータ評価後の範囲逸脱 |
| `FILE_MISSING`           | 指定されたファイルが存在しない (`KNAMEQ` など) |
| `MISSING_REQUIRED`       | 必須パラメータが未設定 |

## コンテキストマネージャ `with` の解説

```{admonition} 補足
:class: note

Python の `with` 文は「ブロックに入るときと抜けるときに必ず後片付けを
走らせる」仕組みです. ファイル操作の `with open(...) as f:` と同じ発想
です. `Trlib` も `__enter__` / `__exit__` を実装してあるので, 例外が
発生しても `tr_finalize` が必ず呼ばれます.
```

明示的に書くなら次と同じ意味です:

```python
tr = Trlib()
try:
    tr.set_params(RR=3.0)
    tr.run(ntmax=10)
    state = tr.get_state()
finally:
    tr.close()
```

## FAQ / つまずきどころ

### Q1. `FileNotFoundError: libtrapi.so not found ...` が出る

まだビルドしていないか, 場所が違います. 次を試してください:

1. `ls tr/libtrapi.so` が存在するか確認
2. 無ければ `make -C tr libtrapi.so` を実行
3. どうしても別の場所に置きたければ
   `export TRLIB_PATH=/path/to/libtrapi.so`

### Q2. `TrlibParamError: ierr=1` が出る

存在しないパラメータ名を指定した, または配列の添字が範囲外です.
`tr/tr_param_registry.f90` の `SELECT CASE` 節に登録されているかを
確認してください. 追加するには Fortran 側に 1 行足すだけです
(再ビルドが必要).

### Q3. `set_params(PN__1=1.0)` と書いてしまった

`__` (アンダースコア 2 つ) を含むキーは, 配列構文の書き間違いとみなして
明示的にエラーを出します. 正しくは `tr.set_param("PN[1]", 1.0)` です.

### Q4. 同じプロセスで 2 個の `Trlib()` を作れる?

**作れません**. #171 以降, `Trlib` は weakref でシングルトン境界を
明示的に守ります. 2 つ目の `Trlib()` は `TrlibStateError` を上げます.
マルチインスタンスが必要な場合は `multiprocessing` でプロセス分離
してください.

### Q5. 結果が `tr2` (CLI 版) と一致しない

回帰テスト `trlib_equivalence` を実行して Phase 0 ベースラインとの
差分を確認してください.

```bash
bash test_run/run_tests.sh trlib_equivalence
```

tolerance は `1e-10`. 許容値以上ずれる場合は, おそらく登録漏れの
パラメータを指定していません.

### Q6. NumPy が必要?

**不要**. `TrState` は Python の `list` です. NumPy を使いたい場合は
`import numpy as np; np.array(state.RT)` で変換できます.

## サポートされているパラメータ

`tr/tr_param_registry.f90` に登録されている主なパラメータ. 名前は
Fortran の `/TR/` ネームリストと一致しています. 型の "double 配列" は
`set_param("NAME[i]", value)` 構文で 1-origin 添字で指定します.

| 名前 | 型 | 意味 |
|---|---|---|
| `RR`      | double      | プラズマ大半径 [m] |
| `RA`      | double      | 小半径 [m] |
| `RKAP`    | double      | elongation (縦横比) |
| `RDLT`    | double      | triangularity |
| `BB`      | double      | トロイダル磁場 [T] |
| `PHIA`    | double      | 全磁束 [Wb] |
| `RIPS`    | double      | 開始時刻のプラズマ電流 [MA] |
| `RIPE`    | double      | 終了時刻のプラズマ電流 [MA] |
| `MODELG`  | int         | 幾何モデル (1:解析, 3:eqdata, 7:VMEC) |
| `NSMAX`   | int         | 粒子種の数 |
| `PA[i]`   | double 配列 | 質量数 (i 番目の粒子種) |
| `PZ[i]`   | double 配列 | 電荷 |
| `PN[i]`   | double 配列 | 中心密度 |
| `PNS[i]`  | double 配列 | 縁密度 |
| `PT[i]`   | double 配列 | 中心温度 |
| `PTS[i]`  | double 配列 | 縁温度 |
| `DT`      | double      | 時間ステップ [s] |
| `NTMAX`   | int         | 時間ステップ数 |
| `NTSTEP`  | int         | 出力間引き |
| `EPSLTR`  | double      | 反復収束判定 |
| `LMAXTR`  | int         | 最大反復数 |
| `MDLKAI`  | int         | 輸送モデル (カイ) 選択 |
| `MDLETA`  | int         | 抵抗モデル |
| `MDLAD`   | int         | 輸送項切替 |
| `MDLAVK`  | int         | 輸送平均 k 切替 |
| `CDW[i]`  | double 配列 | 輸送係数 (12 要素) |
| `CHP`, `CK0`, `CK1` | double | カイ補正係数 |
| `MDLNB`, `MDLEC`, `MDLLH`, `MDLIC` | int | NBI/EC/LH/IC 加熱モデル |
| `MDLJBS`  | int         | ブートストラップ電流モデル |
| `MDLPEL`, `MDLST`, `MDLNF`, `MDLUF` | int | ペレット/ソース/核融合/UFILE |
| `PROFN1`, `PROFN2` | double | 密度プロファイル形状 |
| `PNC`, `MDLIMP` | --       | 不純物混入 |
| `PNBR0`, `PNBRW`, `PNBENG`, `PNBRTG` | double | NBI 位置/幅/エネルギー |
| `PICCD`, `PICR0`, `PICRW`, `PICNPR` | double | ICRF パラメータ |
| `PECCD`, `PECR0`, `PECRW`, `PECNPR` | double | ECRF パラメータ |
| `PLHCD`, `PLHR0`, `PLHRW`, `PLHNPR`, `PLHTOT` | double | LH パラメータ |
| `NGTSTP`, `NGRSTP` | int | グラフ出力間引き |
| `KNAMEQ`  | 文字列      | 平衡データファイル名 (`set_param_str`) |

## `TrState` 出力

`tr.get_state()` は `TrState` dataclass を返します. フィールドは
`tr/tr_api.h` の C 構造体 `tr_state_t` と対応します.

```python
state.nt              # 時間ステップ数
state.nrmax           # 実働の半径点数 (<= 500)
state.nsmax           # 実働の粒子種数 (<= 8)
state.scalars["T"]    # 時間 (秒)
state.scalars["WPT"]  # 蓄積エネルギー
state.scalars["Q0"]   # 中心 q
state.scalars["BETAN"]# beta_N
state.RN[0][0]        # RN[半径=0][粒子=0]
state.RT              # [nrmax][nsmax] の 2 次元リスト
state.AJ[0]           # 電流密度 (先頭)
state.QP[-1]          # 端 q
state.to_dict()       # JSON 化用 dict
```

完全な属性リストは {doc}`api-reference` の `TrState` autodoc を参照.

## Fortran 設計

`tr` の Fortran 側設計 (C ABI / `tr_api.f90` / `tr_param_registry.f90` /
COMMON ブロック) の詳細は次を参照:

- [`docs/tr-library/architecture.md`](https://github.com/k-yoshimi/task/blob/develop/docs/tr-library/architecture.md)
  — リポジトリ直下の設計ノート
- {doc}`../common/architecture` — 全モジュール共通の 3 層設計
- `tr/tr_api.f90` — ライブラリ側のエントリポイント (5 関数 + `tr_validate`)
- `tr/tr_param_registry.f90` — `set_param` の `SELECT CASE` テーブル

## MCP サーバ

LLM から Python を書かずに `tr` を駆動する Model Context Protocol
サーバを同梱しています.

```bash
cd python/mcp-servers/tr_mcp
uv run python -m tr_mcp          # 起動方法は README 参照
```

詳細: `python/mcp-servers/tr_mcp/README.md`.

## テスト

4 層の回帰テストを用意しています.

```bash
# 単一層
bash test_run/run_tests.sh trlib_equivalence  # Layer 1
bash test_run/run_tests.sh trlib_c_abi        # Layer 2
bash test_run/run_tests.sh trlib_ffi          # Layer 3 (低レベル)
bash test_run/run_tests.sh trlib_wrapper      # Layer 3 (高レベル)
bash test_run/run_tests.sh trlib_sweep        # Layer 4
```

または pytest 直接:

```bash
cd python/trlib
pytest --forked --timeout=120 --timeout-method=signal tests/
```

等価性テストは `1e-10` tolerance で PASS しなければなりません
(`feedback_equivalence_must_pass` 参照).

## 変更履歴 — Phase L-0 〜 L-7 と validate API

| Phase / PR | 日付 | 内容 |
|---|---|---|
| L-0 (#2)   | 2026-04-18 | Phase 0 回帰テスト基盤: 3 JSON ベースライン |
| L-1 (#21)  | 2026-04-18 | `tr/Makefile` のグラフィクス分離 |
| L-2 (#27)  | 2026-04-18 | C ABI 基盤 (5 関数スタブ ierr=4) |
| L-3 (#33)  | 2026-04-18 | パラメータレジストリ (38 ケース) |
| L-4 (#35)  | 2026-04-18 | `make -C tr libtrapi.so` で `.so` 生成 |
| L-5 (#44)  | 2026-04-18 | Python ラッパ `python/trlib/` |
| L-6 (#53)  | 2026-04-18 | 4 層テスト (equivalence 1e-10 PASS) |
| L-7        | 2026-04-18 | ドキュメント整備 (architecture.md, README, examples/) |
| #171       | 2026-04-23 | シングルトン境界, 寸法検証, C 文字列検証 |
| **#172**   | 2026-04-23 | **`tr_validate` API (`#143` パイロット)** — 事前検証 |
