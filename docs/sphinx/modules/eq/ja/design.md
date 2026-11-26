# Fortran 設計

`eq` ライブラリは, 既存 `eqx2` バイナリと同一の物理カーネル
(`eqcalq.f90`, `eqfunc.f90`, `eqcalc.f90` など約 32 本の `.f90` ソース)
の上に, C ABI 用の薄いエントリ層 (`eq_api.f90`) を被せて `libeqapi.so`
を構成しています. 共通の 3 層設計は
[共通アーキテクチャ](../../../portal/ja/common/architecture.md) を参照してください.
ここでは `eq` 固有の部分に絞って解説します.

## エントリ層 (`eq_api.f90`)

C から呼ばれる関数は **6 つ** + `eq_validate`, `eq_save` と `eq_get_psi_rz`. 標準の 5 関数に加えて
`eq_set_param_str` (文字列パラメータ用) があるのが eq の特徴です.

| C シンボル | Fortran 側 | 役割 |
|---|---|---|
| `eq_init`           | `eq_api_init`           | `pl_init` → `eq_init` (内部) で COMMON 初期化 |
| `eq_set_param`      | `eq_api_set_param`      | `eq_param_registry::eq_param_set` に委譲 |
| `eq_set_param_str`  | `eq_api_set_param_str`  | 同上 (文字列版) — **eq だけの 6 番目 ABI** |
| `eq_run`            | `eq_api_run`            | `mode` 引数で動作切り替え (時間発展なし) |
| `eq_get_state`      | `eq_api_get_state`      | EQCOMM のスカラー・ψ-面プロファイルを C 構造体にコピー |
| `eq_finalize`       | `eq_api_finalize`       | `eq_bpsd_reset` で SAVE フラグを再起動 |
| `eq_validate`       | `eq_api_validate`       | グリッド寸法 + `KNAMEQ` ファイル存在チェック |
| `eq_save`           | `eq_api_save`           | 直前の `eq_run` の平衡を `KNAMEQ` のファイルに保存 (`EQSAVE`). ファイルを開けない, または書いた長さより短い場合はエラー |
| `eq_get_psi_rz`     | `eq_api_get_psi_rz`     | 2 次元のポロイダル磁束 `PSIRZ` をコピー (R の添字が先). 現在のパラメータの平衡がない場合 (`eq_save` と同じ場合) は `EQ_ERR_INVALID` |

すべて `BIND(C, NAME="eq_xxx")` で C ABI シンボルを固定しています.

### `eq_run` の特殊性

`eq_run(mode)` は時間ステップ数ではなく **動作モード** を取ります.

| `mode` | 挙動 | 元 CLI |
|---|---|---|
| 0 | `EQCALC` (解析的 G-S 解) + `EQCALQ` (post-processing) | `R` → `F` |
| 1 (既定) | `equnit::eq_load` — `KNAMEQ` のファイルを読み平衡を構築 | `L` |
| 2 以上 | (将来拡張用) — `EqlibNotImplementedError` | — |

`tr` の `tr_run(ntmax)` とは引数の意味が違うので注意してください.

```{note}
`mode=0` は `MODELG ∈ {0, 1, 2}` (解析的幾何) で使います. 装置パラメータ
(`RR`, `RA`, `BB`, `RIP`) と圧力・電流プロファイル係数 (`PP*`, `PJ*`,
`FF*` 等) から解析的に Grad-Shafranov を解きます. 元 `eqx2` CLI の `R`
(Run) コマンドが対応する経路で, `EQCALC` で平衡を構築した後 `EQCALQ` で
post-processing して `qaxis`, `qsurf`, `betat`, `betap`, `pvol` 等の
診断量を埋めます.

`mode=1` は `MODELG ∈ {3, 5, 8}` (ファイル系) で使い, `KNAMEQ` で指定
された EQDSK ファイルを読み込みます.
```

### C 構造体レイアウト (`eq_state_t`)

`eq/eq_api.h` で定義されます. 主要部分:

```c
typedef struct {
    int    nrgmax, nzgmax, npsmax, nrmax, nthmax, nsumax, nrvmax;
    double raxis, zaxis, psi0, psipa, psita;
    double qaxis, qsurf, betat, betap, pvol, raave, ripx;
    double rg[EQ_MAX_NRGMAX];
    double zg[EQ_MAX_NZGMAX];
    double psips[EQ_MAX_NPSMAX];
    double ppps[EQ_MAX_NPSMAX];
    double ttps[EQ_MAX_NPSMAX];
    double qqps[EQ_MAX_NPSMAX];
    /* ... */
} eq_state_t;
```

`tr_state_t` と違って **時間ステップカウンタを持たない** 点に注意.

## パラメータレジストリ (`eq_param_registry.f90`)

`tr` と同じ `SELECT CASE` 方式で約 94 ケースを公開します.

- **78 個の数値スカラー**: `RR`, `RA`, `BB`, `RIP`, `Q0`, `QA`,
  `EPSEQ`, `MODELG`, `MDLEQF` など
- **5 個の配列ファミリ**:
  - `PSIB[0..5]` — **0-origin** (eqcom1_mod の宣言 `PSIB(0:5)` 由来)
  - `RIPFC[1..NPFCM]` (1-origin)
  - `RPFC[1..NPFCM]` (1-origin)
  - `ZPFC[1..NPFCM]` (1-origin)
  - `WPFC[1..NPFCM]` (1-origin)
- **7 個の文字列**: `KNAMEQ`, `KNAMEQ2`, `KNAMWR`, `KNAMWM`, `KNAMFP`,
  `KNAMFO`, `KNAMPF`

### 文字列の別エントリ

`KNAMEQ` 等は `CHARACTER(LEN=80)` で `REAL(rkind)` パイプラインに乗らない
ため, `eq_param_set_str` を別関数として用意しています. これが C ABI の
**6 番目** の関数 `eq_set_param_str` の存在理由です.

`tr` も後から `tr_set_param_str` を追加しましたが, eq では設計初期から
EQDSK ファイル名を扱うため必須でした.

## ライブラリ内部のソース構成

`eq/*.f90` 約 32 本を役割別に分類すると次のようになります.

| グループ | 主なファイル | 役割 |
|---|---|---|
| **API 層**           | `eq_api.f90`, `eq_param_registry.f90`, `eq_state.f90` | C ABI エントリ. 物理カーネルには触れない |
| **メインソルバ**     | `eqcalq.f90`, `eqcalc.f90`, `eqcalv.f90`, `equnit.f90` | Grad-Shafranov 反復, 自由境界計算 |
| **プロファイル**     | `eqfunc.f90`, `eqsub.f90`, `eqsplf.f90`, `eqgetp.f90` | $p(\psi)$, $F(\psi)$, $q(\psi)$ の評価 |
| **共通モジュール**   | `eqcom0_mod.f90`〜`eqcom3_mod.f90`, `equcom.f90` | グローバル状態 (COMMON ブロックを MODULE 化) |
| **入出力**           | `eqfile.f90`, `equread.f90`, `eq-eqdsk.f90`, `eqgout.f90` | EQDSK 読み, 結果出力 |
| **BPSD 連携**        | `eqbpsd.f90`, `eqintf.f90`, `equintf.f90` | モジュール間データ橋渡し |
| **グラフィクス**     | `eq_graphics_stubs.f90`, `eqgsub.f90` | ライブラリ版ではスタブ化 |
| **対話メニュー**     | `eqmenu.f90` | `eqx2` CLI 専用 (ライブラリ版では未使用) |
| **その他**           | `eq-qst.f90`, `eqlib.f90`, `eqrppl.f90` | 補助ルーチン |

## F90 モダナイゼーション (F-1 〜 F-5)

`eq/` ツリーには大量の F77 fixed-form ソースと `eqcom*.inc` INCLUDE
ファイルがありましたが, ライブラリ化と並行して段階的に F90 化しました.

| Phase | PR | 内容 |
|---|---|---|
| F-1 | #71 | COMMON → `eqcom{0..3}_mod.f90` (shim 並存) |
| F-2 | #79 | fixed-form → free-form (LOW tier) |
| F-3 | #81 | fixed-form → free-form (MED tier, 9 ファイル) |
| F-4 | #87 | fixed-form → free-form (HIGH tier, 8 ファイル) |
| F-5 | #93 | shim 撤去, `INCLUDE` → `USE` に全面切替 |

F-5 完了で `eq/` 配下のソースは F90 のみ. 他モジュールから
`USE eqcom*_mod` で直接参照できます.

## 再初期化と SAVE フラグ

`eq_finalize` は明示的に `eq_bpsd_reset` を呼び, `eqbpsd` モジュールの
`SAVE` 状態フラグ `eq_bpsd_init_flag` を再起動します. 詳細:

- 同一プロセスで `init` → `finalize` → `init` を繰り返す場合, BPSD 描画
  記述子が 2 回目以降のサイクルで再ゼロ化される必要があります.
- これを忘れると suite-level SEGV (テストの `test_reinit_divergence`)
  が再発します.
- 詳細は issue #110 / PR #163 を参照.

## PIC ビルドの依存関係

`libeqapi.so` は次の PIC アーカイブに静的リンクされます:

```
libeqapi.so
├── lib/lib*_pic.a      (数学・入出力ユーティリティ)
├── pl/libplcomm_pic.a  (プラズマ共通モジュール)
├── mtxp/libmtxp_pic.a  (疎行列ソルバ — Grad-Shafranov 用)
└── bpsd/libbpsd_pic.a  (BPSD データ橋渡し)
```

`tr` と違い `eq` は自分自身が平衡計算の主体なので, eq の PIC アーカイブには
依存しません.

## 参考リンク

- [`docs/eq-library/architecture.md`](https://github.com/k-yoshimi/task/blob/develop/docs/eq-library/architecture.md)
  — リポジトリ直下の設計ノート
- [共通アーキテクチャ](../../../portal/ja/common/architecture.md) — 全モジュール共通の 3 層設計
- `eq/eq_api.h` — C ABI ヘッダ
- `eq/eq_api.f90` — Fortran 側エントリ
- `eq/eq_param_registry.f90` — `set_param` の `SELECT CASE` テーブル
- `eq/eq_state.f90` — `eq_state_c` / `eq_diag_entry_c` の `TYPE` 定義
- `eq/eqcalq.f90` — Grad-Shafranov ソルバの本体
