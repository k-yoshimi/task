# Fortran 設計

`tr` ライブラリは, 既存 `tr2` CLI 版と同一の物理カーネル (`trloop.f90`,
`trcalc.f90`, `trcoef_*.f90` など約 64 本の `.f90` ソース) の上に, C ABI
用の薄いエントリ層 (`tr_api.f90`) を被せて `libtrapi.so` を構成しています.
共通の 3 層設計は [共通アーキテクチャ](../../../portal/ja/common/architecture.md) を
参照してください. ここでは `tr` 固有の部分に絞って解説します.

## エントリ層 (`tr_api.f90`)

C から呼ばれる関数は **7 つ**: 標準の 5 関数 + `tr_set_param_str` (文字列用)
+ `tr_validate` (PR #172 の事前検証).

| C シンボル | Fortran 側 | 行数 (目安) | 役割 |
|---|---|---|---|
| `tr_init`          | `tr_api_init`          | ~30 | `pl_init` → `eq_init` → `tr_init` (namelist 既定値) → `ALLOCATE_TRCOMM` |
| `tr_set_param`     | `tr_api_set_param`     | ~15 | 入力文字列を `tr_param_registry::tr_param_set` に委譲 |
| `tr_set_param_str` | `tr_api_set_param_str` | ~10 | 同上 (文字列版) |
| `tr_run`           | `tr_api_run`           | ~30 | 初回のみ `tr_prep`, その後 `tr_loop(ntmax)`. `NTMAX` を一時退避 |
| `tr_get_state`     | `tr_api_get_state`     | ~40 | `TRCOMM` のスカラーと `RN/RT/AJ/QP` を C 構造体にコピー |
| `tr_finalize`      | `tr_api_finalize`      | ~10 | `DEALLOCATE_TRCOMM` + `g_*` フラグリセット |
| `tr_validate`      | `tr_api_validate`      | ~50 | 登録パラメータの値域 + `KNAMEQ` ファイル存在チェック |

すべて `BIND(C, NAME="tr_xxx")` で C ABI シンボルを固定しています.
Fortran 側の名前が `tr_api_*` なのは, 既存の `SUBROUTINE tr_init`
(`trinit.f90`) とシンボル衝突を避けるためです.

### C 構造体レイアウトとの対応

`tr/tr_api.h` で定義される `tr_state_t` と 1:1 対応します:

```c
typedef struct {
    int    nt, nrmax, nsmax;
    double T, WPT, AJT, Q0, BETA0, BETAP0, BETAA, BETAN;
    double TAUE1, TAUE2, ZEFF0, ALI, RQ1;
    double RN[TR_MAX_NRMAX][TR_MAX_NSMAX];   /* row-major in C */
    double RT[TR_MAX_NRMAX][TR_MAX_NSMAX];
    double AJ[TR_MAX_NRMAX];
    double QP[TR_MAX_NRMAX];
} tr_state_t;
```

`TR_MAX_NRMAX = 500`, `TR_MAX_NSMAX = 8` はコンパイル時固定. 実働の
`nrmax`/`nsmax` 部分だけが有効で残りはパディング扱いです.

## パラメータレジストリ (`tr_param_registry.f90`)

外部からの名前 (`"RR"`, `"PN[1]"`, `"CDW[3]"` など文字列) を TRCOMM 変数への
代入にマップする **ハンドコーディング `SELECT CASE` テーブル** です.

```fortran
FUNCTION tr_param_set(name, value) RESULT(ierr)
  CHARACTER(LEN=*), INTENT(IN) :: name
  REAL(rkind),      INTENT(IN) :: value
  ! name="PN[1]" のように添字付き名前に対応
  CALL parse_array_subscript(name, base, idx)
  SELECT CASE (TRIM(base))
  CASE ("RR");   RR   = value
  CASE ("PN");   IF (idx<1 .OR. idx>SIZE(PN)) THEN; ierr=1; ELSE; PN(idx)=value; END IF
  ...
  CASE DEFAULT;  ierr = 1   ! 登録されていない名前
  END SELECT
END FUNCTION
```

- **配列添字の取り扱い**: `parse_array_subscript` ヘルパが `"PN[1]"` を
  `base="PN"`, `idx=1` に分解.
- **境界検査**: `SIZE(arr)` と比較して範囲外は `ierr=1` でリジェクト.
- **特別なガード (`NSMAX`)**: `NSMAX=1` は `tr_prof_impurity` の零除算 →
  Fortran 側 `STOP` を誘発しホストプロセスを abort させるため,
  レジストリで早期に `[2, 8]` の範囲外を拒否しています
  (`tr_param_registry.f90:85-93` のコメント参照).

登録済みパラメータの全リストは {doc}`parameters` にあります.

### 文字列パラメータの別エントリ

`KNAMEQ` 等の `CHARACTER(LEN=80)` 変数は `REAL(rkind)` パイプラインに
乗らないので, 別関数 `tr_param_set_str` を用意しています. 現状は
`KNAMEQ` のみが登録済み. 追加 (`KNAMEQ2`, `KNAMTR` など) は `SELECT CASE`
に 1 行足すだけです.

## ライブラリ内部のソース構成

`tr/*.f90` 約 64 本を役割別に分類すると次のようになります.

| グループ | 主なファイル | 役割 |
|---|---|---|
| **API 層**           | `tr_api.f90`, `tr_param_registry.f90`, `tr_state.f90` | C ABI エントリ. 物理カーネルには触れない |
| **メインループ**     | `trmain.f90`, `trloop.f90`, `trexec.f90`, `trprep.f90` | 時間発展の司令塔 |
| **モデル本体**       | `trcalc.f90`, `trcoef*.f90`, `trcdbm.f90`, `tritg.f90`, `trmdlt.f90` | 輸送係数・抵抗・拡散の物理モデル |
| **プロファイル**     | `trprof.f90`, `trprf.f90`, `trgrad.f90`, `trmetric.f90` | 初期プロファイル生成, 勾配計算 |
| **加熱・電流駆動**   | `trpnb.f90`, `trpnf.f90`, `trpel.f90`, `trpsc.f90` | NBI, 核融合, ペレット, ソース |
| **共通モジュール**   | `trcomm.f90`, `trcomm_*.f90`, `trcom0.f90`, `trcom1.f90` | グローバル状態 (COMMON ブロックを MODULE 化) |
| **結果出力**         | `trrslt_globals.f90`, `trrslt_files.f90`, `trrslt_print.f90` | `TrState` スカラー (`WPT`, `BETAN`, …) の計算 |
| **UFILE I/O**        | `tr_ufile_*.f90`, `trufile.f90`, `trufsub.f90`, `tradat.f90` | 実験データ (UFILE) 読み込み |
| **BPSD 連携**        | `trbpsd*.f90` | モジュール間データ橋渡し |
| **グラフィクス**     | `tr_graphics_stubs.f90`, `trg*.f90`, `trview.f90` | ライブラリ版ではスタブ化 |
| **対話メニュー**     | `trmenu.f90`, `trhelp.f90` | `tr2` CLI 専用 (ライブラリ版では未使用) |
| **回帰用**           | `trregress.f90`, `tr_dump_state.f90` | Phase 0 ベースライン出力生成 |
| **サブディレクトリ** | `itg/`, `nclass/`, `cytran/`, `mbgb/`, `mmm95/`, `libmmm7_1/`, `glf/`, `adpost/` | 外部物理モデル (ITG, NCLASS, GLF23, mmm95, mmm7_1 等) |

### ライブラリ版で無効化される層

`tr_graphics_stubs.f90` は PGPlot など描画ライブラリへの呼び出しを
空の定義で上書きします. これにより, グラフィクスライブラリが
インストールされていない環境でも `libtrapi.so` をロード・実行できます.
同様に対話メニュー (`trmenu.f90`) はリンクされるもののエントリポイントから
到達しません.

## スカラー出力 (`TrState.scalars`) はどこで計算されるか

`tr_get_state` が返す 14 個のスカラーは, すべて `trrslt_globals.f90::TR_CALC_GLOBAL`
で計算され `TRCOMM` モジュール変数に格納されています. 抜粋:

```fortran
! trrslt_globals.f90 より抜粋
WPT   = WBULKT + WTAILT                                      ! 蓄積エネルギー [MJ]
AJT   = SUM(AJ(1:NRMAX)*DSRHO(1:NRMAX))*DR/1.D6              ! 全電流 [MA]
BETA0 = (4.D0*BETA(1) - BETA(2))/3.D0                        ! 軸上 β
BETAN = BETAA*1.D2/(RIP/(RA*BB))                             ! 規格化 β (Troyon)
TAUE1 = WPT/PINT                                             ! 閉じ込め時間
TAUE2 = WPT/(PINT-WPDOT)                                     !   (定常補正版)
ALI   = 4.D0*WPOL/(RMU0*RR*(AJTTOR*1.D6)**2)                 ! 内部インダクタンス
ZEFF0 = (4.D0*ZEFF(1) - ZEFF(2))/3.D0                        ! 軸上 Zeff
```

物理的意味は {doc}`state` の表を参照.

(reinit-constraints)=
## 再初期化の制約

`tr_finalize` → `tr_init` を同一プロセスで繰り返すと, モジュールレベルの
Fortran 状態が完全にはリセットされない箇所があります (全モジュール共通の
issue — [共通アーキテクチャ](../../../portal/ja/common/architecture.md) の
「モジュール状態のリセット」参照). テストで再初期化する場合は
`pytest --forked` でプロセス分離するか, `multiprocessing` で別プロセスに
隔離してください.

## PIC ビルドの依存関係

`libtrapi.so` は 5 つの PIC アーカイブに静的リンクされます:

```
libtrapi.so
├── lib/lib*_pic.a      (数学・入出力ユーティリティ)
├── pl/libplcomm_pic.a  (プラズマ共通モジュール)
├── eq/libeqcomm_pic.a  (平衡モジュール — MODELG=3/9 のとき必要)
├── mtxp/libmtxp_pic.a  (疎行列ソルバ)
└── bpsd/libbpsd_pic.a  (BPSD データ橋渡し)
```

各 `*_pic.a` は通常の `.a` (非 PIC, `tr2` バイナリ用) と並行に生成されるので,
ライブラリ化と既存 CLI の両立が可能です.

## 参考リンク

- [`docs/tr-library/architecture.md`](https://github.com/k-yoshimi/task/blob/develop/docs/tr-library/architecture.md)
  — リポジトリ直下の設計ノート (より詳しい設計意図と phase 記録)
- [共通アーキテクチャ](../../../portal/ja/common/architecture.md) — 全モジュール共通の 3 層設計
- `tr/tr_api.h` — C ABI ヘッダ (定数 `TR_MAX_NRMAX=500`, `TR_MAX_NSMAX=8`, error enum)
- `tr/tr_api.f90` — Fortran 側エントリ (7 関数)
- `tr/tr_param_registry.f90` — `set_param` の `SELECT CASE` テーブル
- `tr/tr_state.f90` — `tr_state_c` / `tr_diag_entry_c` の `TYPE` 定義
- `tr/trrslt_globals.f90` — スカラー量の算出
