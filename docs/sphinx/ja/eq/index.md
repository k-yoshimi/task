# `eq` — MHD 平衡

```{admonition} この章で学ぶこと
:class: tip

TASK/EQ (**MHD 平衡** ソルバ: EQDSK 形式の平衡データ, または解析プロファ
イルを入力に ψ サーフェスと派生量を計算) を Python から呼ぶ `eqlib`
の使い方を学びます. `tr` と異なり `eq` は **時間発展を持たない**
モジュールで, `run()` の引数は `mode` (動作モード) です.  また,
**6 番目** の C ABI `eq_set_param_str` を持ち, `KNAMEQ` 等の文字列
パラメータ専用 API があります.
```

```{toctree}
:hidden:

quickstart
api-reference
```

## 概要 — `eq` は何をする

**TASK/EQ** はトカマクの **MHD 平衡** を解くモジュールです. 入力は

- EQDSK 形式 (G-EQDSK) の平衡データファイル, または
- 解析プロファイル (圧力 $p(\psi)$, 安全係数 $q(\psi)$ 等)

を取り, 出力としては磁気軸位置 (`raxis`, `zaxis`), 中心 q (`qaxis`),
表面 q (`qsurf`), プラズマ $\beta$ (`betat`, `betap`), プラズマ体積
(`pvol`) などのスカラーと, R-Z 格子, ψ-面プロファイル (`psips`, `ppps`,
`ttps`, `qqps`) を返します.

PR #164/#165 でライブラリ / Python ラッパ / `validate()` API が揃い,
L-6 等価性ゲートを 1e-10 で通過済みです.

## 前提とビルド

```bash
cd /path/to/task                     # TASK リポジトリのルート
make -C lib   libs_pic
make -C pl    libs_pic
make -C bpsd  libs_pic
make -C mtxp  libs_pic
make -C eq    libeqapi.so
```

成功すると `eq/libeqapi.so` が出来ます. `nm` で **6 個** のシンボルが
確認できます (eq だけは 6 個, 他は 5 個):

```bash
$ nm -D eq/libeqapi.so | grep ' T eq_'
... T eq_finalize
... T eq_get_state
... T eq_init
... T eq_run
... T eq_set_param
... T eq_set_param_str       # <-- 6 番目: EQ 固有
... T eq_validate            # PR #164 以降
```

## 最短 hello-world

```python
from eqlib import Eq
with Eq() as eq:
    eq.set_param("RR", 6.5)                    # 大半径 [m]
    eq.set_param("BB", 5.3)                    # 磁場 [T]
    eq.set_param("RIP", 1.5)                   # 電流 [MA]
    eq.set_param("MODELG", 3)                  # EQDSK 経路
    eq.set_param_str("KNAMEQ", "eqdata.ITER")  # ファイル名
    eq.run()                                   # mode=1 デフォルト
    st = eq.get_state()
print(f"raxis={st.scalars['raxis']:.4f}  qaxis={st.scalars['qaxis']:.4f}")
```

完全な実行可能 notebook: {doc}`quickstart`.

## パラメータの指定方法 — 4 通り

### A. スカラー (`set_param`)

`tr` と違い, `eq` の `set_params(**kwargs)` はスカラー専用 (位置引数で
mapping を受ける形もサポート, 下記 B 参照). 通常は 1 つずつ
`set_param("NAME", value)`:

```python
eq.set_param("RR", 6.5)
eq.set_param("MODELG", 3)      # int は double で渡して OK
eq.set_param("RIPFC[1]", 0.5)  # PF コイル電流 (1-origin, 1..10)
```

```{admonition} `PSIB` だけは 0-origin
:class: warning

Fortran 宣言が `REAL(KIND=8) :: PSIB(0:5)` で 0 から始まるため, 添字も
`PSIB[0]` 〜 `PSIB[5]` です. 添字無しの裸の `"PSIB"` はレジストリで
明示的に拒否されます (`EqlibInvalidParamError`). 他の 1-D 配列
(`RIPFC`, `RPFC`, `ZPFC`, `WPFC`) は 1-origin です.
```

### B. 一括 dict / kwargs (`set_params`)

```python
eq.set_params(RR=6.5, BB=5.3, MODELG=3)       # kwargs 形式
eq.set_params({"RR": 6.5, "BB": 5.3})          # 位置引数 mapping 形式
```

### C. 文字列パラメータ (`set_param_str`)

EQDSK 系ファイル名は `CHARACTER(LEN=80)` で, **専用 API** が必須です.
`set_param` には渡せません.

```python
eq.set_param_str("KNAMEQ",  "eqdata.ITER01")
eq.set_param_str("KNAMWR",  "wrdata.dat")
```

対応するキーは **7 個**:
`KNAMEQ`, `KNAMEQ2`, `KNAMWR`, `KNAMWM`, `KNAMFP`, `KNAMFO`, `KNAMPF`.

### D. 事前検証 (`validate`) — PR #164

```python
from eqlib import Eq, EqDiagCode

with Eq() as eq:
    eq.set_params(RR=6.5, BB=5.3, RIP=1.5, MODELG=3)
    eq.set_param_str("KNAMEQ", "eqdata.missing")

    diags = eq.validate()
    for d in diags:
        print(f"[{EqDiagCode(d.code).name}] {d.param}: {d.message}")
    if diags:
        raise SystemExit("fix the diagnostics before running")

    eq.run()
```

診断コードは `tr` と共通の 5 種類 (`OUT_OF_RANGE`, `INCONSISTENT_PAIR`,
`OUT_OF_RANGE_AFTER_DEP`, `FILE_MISSING`, `MISSING_REQUIRED`). `eq_validate`
は 10 個のグリッド寸法 (`NSGMAX`, `NTGMAX`, `NUGMAX`, `NRGMAX`, `NZGMAX`,
`NPSMAX`, `NRMAX`, `NTHMAX`, `NSUMAX`, `NRVMAX`) と, 必要な幾何モードで
`KNAMEQ` / `KNAMPF` のファイル存在をチェックします.

## FAQ — `eq` 固有

### Q1. なぜ `PSIB` だけ 0-origin?

`eqcom1_mod.f90` で `REAL(8) :: PSIB(0:5)` と宣言されており, ψ 境界
条件として $\psi = 0$ (磁気軸) から数えるのが物理的に自然だからです.
PF コイル系配列 (`RIPFC`, `RPFC`, `ZPFC`, `WPFC`) は 1-origin の
慣習に従います.

### Q2. なぜ `eq.run()` のデフォルトが `mode=1`?

`mode=1` は `equnit::eq_load` を呼び, 現在の `KNAMEQ` (EQDSK ファイル)
を読んで平衡を構築する EQDSK 駆動の標準ワークフローだからです. `mode=0`
(直接 EQCALQ 呼び出し) は予約済みで, 現状 `EqlibNotImplementedError`
を返します. `tr`/`ti`/`wr`/`fp` の `run` は時間ステップ数 `ntmax` を
取りますが, EQ は時間発展を持たないため引数の意味が違います.

### Q3. `KNAMEQ` を kwargs で渡すとエラー

`set_params(KNAMEQ="...")` は **NG**. 文字列パラメータは
`set_param_str("KNAMEQ", "...")` を使ってください.

### Q4. `EqlibError: libeqapi.so does not export eq_set_param_str` が出る

Phase L-3 以前の古い `libeqapi.so` を読み込んでいます.
`make -C eq libeqapi.so` で再ビルドしてください.

## 登録パラメータ (抜粋)

`eq/eq_param_registry.f90` には全 94 件の `CASE` (≈78 数値スカラー,
5 配列ファミリ, 7 文字列) が登録されています. 主なものを下表に示します.

| 名前 | 型 | 意味 |
|---|---|---|
| `RR`, `RA`, `RB`                  | double | 大半径 / 小半径 / 壁半径 [m] |
| `RKAP`, `RDLT`                    | double | elongation, triangularity |
| `BB`                              | double | トロイダル磁場 [T] |
| `RIP`                             | double | プラズマ電流 [MA] |
| `Q0`, `QA`, `QMIN`                | double | 中心 / 表面 / 最小 q |
| `RHOMIN`, `RHOEDG`                | double | 規格化半径 |
| `PP0`, `PP1`, `PP2`               | double | 圧力プロファイル係数 |
| `PROFP0..2`                       | double | 圧力プロファイル指数 |
| `PJ0`, `PJ1`, `PJ2`               | double | 電流プロファイル係数 |
| `PROFJ0..2`                       | double | 電流プロファイル指数 |
| `FF0`, `FF1`, `FF2`               | double | $F(\psi)$ 係数 |
| `PROFF0..2`                       | double | $F(\psi)$ 指数 |
| `PT0..2`, `PROFTP0..2`            | double | 温度プロファイル |
| `PV0..2`, `PROFV0..2`             | double | 速度プロファイル |
| `PROFR0..2`                       | double | 半径プロファイル |
| `PTSEQ`, `PN0EQ`                  | double | 端温度 / 中心密度 |
| `EPSEQ`, `EPSNW`, `DELNW`         | double | 反復収束判定 |
| `NLPMAX`, `NLPNW`                 | int    | 最大反復数 |
| `RGMIN`, `RGMAX`, `ZGMIN`, `ZGMAX` | double | R-Z 計算領域 |
| `ZLIMP`, `ZLIMM`, `FRBIN`         | double | リミタ位置 |
| `MODELG`                          | int    | 1: 解析, 3: EQDSK, 7: VMEC |
| `MODELQ`, `IDEBUG`, `MODEFR`, `MODEFW` | int | モデル切替 |
| `MDLEQF`, `MDLEQC`, `MDLEQA`, `MDLEQX`, `MDLEQV` | int | EQ 内部モデル選択 |
| `NPRINT`                          | int    | 出力詳細度 |
| `NRMAX`, `NTHMAX`, `NSUMAX`, `NSGMAX`, `NTGMAX`, `NUGMAX` | int | ψ-メッシュ |
| `NRGMAX`, `NZGMAX`, `NPSMAX`, `NRVMAX`, `NTVMAX`, `NPFCMAX` | int | 出力グリッド |
| `PSIB[0..5]`                      | double 1D | **0-origin**, ψ 境界 |
| `RIPFC[1..10]`, `RPFC[1..10]`, `ZPFC[1..10]`, `WPFC[1..10]` | double 1D | PF コイル (1-origin) |
| `KNAMEQ`, `KNAMEQ2`, `KNAMWR`, `KNAMWM`, `KNAMFP`, `KNAMFO`, `KNAMPF` | 文字列 | `set_param_str` 専用 |

## `EqState` 出力

```python
state.nrgmax, state.nzgmax       # 実働 R, Z 格子点数
state.npsmax                     # 実働 ψ-面サンプル数
state.nrmax, state.nthmax        # ψ-メッシュ, 極角メッシュ
state.nrvmax                     # 体積グリッド半径点 (MODELG=3 のみ)
state.nsgmax, state.ntgmax       # TASK ネイティブ面グリッド (MODELG=3 のみ)
state.scalars["raxis"]           # 磁気軸 R [m]
state.scalars["zaxis"]           # 磁気軸 Z [m]
state.scalars["qaxis"]           # 中心 q
state.scalars["qsurf"]           # 表面 q
state.scalars["betat"]           # トロイダル beta
state.scalars["betap"]           # ポロイダル beta
state.scalars["pvol"]            # プラズマ体積 [m^3]
state.scalars["raave"]           # 体積平均小半径 [m]
state.scalars["ripx"]            # プラズマ電流 [MA]
state.rg                         # [nrgmax] R 軸座標
state.zg                         # [nzgmax] Z 軸座標
state.psips, state.ppps          # [npsmax] ψ サーフェス値, 圧力
state.ttps, state.qqps           # [npsmax] T (= R·Bφ), q
state.to_dict()                  # JSON 用
```

完全な属性リストは {doc}`api-reference` の `EqState` autodoc を参照.

## Fortran 設計

- [`docs/eq-library/architecture.md`](https://github.com/k-yoshimi/task/blob/develop/docs/eq-library/architecture.md)
  — リポジトリ直下の設計ノート
- {doc}`../common/architecture` — 全モジュール共通の 3 層設計
- `eq/eq_api.f90` — ライブラリ側のエントリポイント (5 核 + `eq_set_param_str` + `eq_validate`)
- `eq/eq_param_registry.f90` — パラメータレジストリ
- `eq/eqcom{0..3}_mod.f90` — COMMON ブロックを MODULE 化 (Phase F-1 / F-5)

### F90 モダナイゼーション (F-1 〜 F-5)

`eq/` ツリーには大量の F77 fixed-form ソースと `eqcom*.inc` INCLUDE
ファイルがありましたが, ライブラリ化と並行して段階的に F90 化:

| Phase | PR | 内容 |
|---|---|---|
| F-1 | #71 | COMMON → `eqcom{0..3}_mod.f90` (shim 並存) |
| F-2 | #79 | fixed-form → free-form (LOW tier) |
| F-3 | #81 | fixed-form → free-form (MED tier, 9 ファイル) |
| F-4 | #87 | fixed-form → free-form (HIGH tier, 8 ファイル) |
| F-5 | #93 | shim 撤去, `INCLUDE` → `USE` に全面切替 |

F-5 完了で `eq/` 配下のソースは F90 のみ. 他モジュールから
`USE eqcom*_mod` で直接参照できます.

## MCP サーバ

`eq_mcp` サーバ (PR #167) が Model Context Protocol 経由で LLM から
`eq` を駆動可能にします.

```bash
cd python/mcp-servers/eq_mcp
uv run python -m eq_mcp
```

詳細: `python/mcp-servers/eq_mcp/README.md`.

## テスト

```bash
bash test_run/run_tests.sh eqlib_equivalence eqlib_c_abi \
     eqlib_ffi eqlib_wrapper eqlib_sweep

# または pytest 直接:
cd python/eqlib
pytest --forked --timeout=120 --timeout-method=signal tests/
```

等価性テストは `1e-10` tolerance で PASS 必須 (SKIP 禁止 — memory
`feedback_equivalence_must_pass` 参照).

## 変更履歴 — L-0 〜 L-7 + F-1 〜 F-5 + validate API

| Phase / PR | 日付 | 内容 |
|---|---|---|
| L-0 (#54)  | 2026-04-18 | `eq_iter01` / `eq_tst2` ベースライン, `eqregress.f90` |
| L-1 (#65)  | 2026-04-18 | `eq/Makefile` CORE/GRAPHICS/MENU 分割 |
| L-2 (#70)  | 2026-04-18 | C ABI スタブ (`eq_api.h`, 5 関数) |
| L-3 (#78)  | 2026-04-18 | パラメータレジストリ (94 ケース) + 6 番目 ABI `eq_set_param_str` |
| L-4 (#80)  | 2026-04-18 | `libeqapi.so` ビルド + 明示的 PIC 依存 |
| L-5 (#86)  | 2026-04-18 | Python ラッパ `python/eqlib/` (`run()` は `mode=1` デフォルト) |
| L-6 (#92)  | 2026-04-19 | 4 層統合テスト (`eqlib_*`) |
| L-7 (#89)  | 2026-04-19 | ドキュメント整備 (`README.md`, `architecture.md`) |
| F-1..F-5 (#71 … #93) | 2026-04-18/19 | F90 モダナイゼーション: COMMON → module, fixed → free, shim 撤去 |
| #163       | 2026-04-22 | `EQFINI` で `eq_bpsd_init_flag` を rearm (#110) |
| **#164**   | 2026-04-22 | **事前検証 API パイロット (#143)** |
| #165       | 2026-04-22 | `Eq.validate()` Python ラッパ (#143 follow-up) |
| **#167**   | 2026-04-22 | **EQ モジュール用 MCP サーバ** |
