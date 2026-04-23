# 共通アーキテクチャ

```{admonition} この章で学ぶこと
:class: tip

本章では, `eq` / `tr` / `ti` / `fp` / `wr` / `wrx` / `tot` のすべてに共通する
核 3 層 (Python ラッパ → C ABI → Fortran バックエンド), 5 関数 C ABI,
エラーコード 0〜4, PIC ビルド, Python `ctypes` の 2 層設計を学びます.
以降の章はすべてこの章の応用です.
```

## 全体像 — 層構造

すべての `Xlib` (X は `eq` / `tr` / `ti` / `fp` / `wr` / `wrx` / `tot`
のどれか) は同じ構造を持ちます: 3 つの核ソフトウェア層 (Python ラッパ →
C ABI → Fortran バックエンド) の上にユーザ層が乗り, その 3 層を一つの
ロード可能なバイナリにまとめた成果物が共有ライブラリ `.so` です.

```text
┌───────────────────────────────────────────────────────────────────┐
│ ユーザ層 (Python スクリプト / C ドライバ / Jupyter Notebook)       │
└─────────────────────────────┬─────────────────────────────────────┘
                              │
┌─────────────────────────────▼─────────────────────────────────────┐
│ Python ラッパ層                                                    │
│   python/Xlib/: Xlib クラス, XState dataclass, 例外階層,            │
│                 _ffi.py (ctypes)                                    │
└─────────────────────────────┬─────────────────────────────────────┘
                              │
┌─────────────────────────────▼─────────────────────────────────────┐
│ C ABI 層 (5 関数 + 2 構造体)                                        │
│   X/X_api.h:                                                        │
│     X_init / X_run / X_set_param / X_get_state / X_finalize         │
└─────────────────────────────┬─────────────────────────────────────┘
                              │
┌─────────────────────────────▼─────────────────────────────────────┐
│ Fortran バックエンド (物理カーネル, 既存 tr2/eqx2/... と同一)       │
│   X/X_api.f90, X_param_registry.f90, Xloop/Xcalc/ ...               │
└─────────────────────────────┬─────────────────────────────────────┘
                              │
┌─────────────────────────────▼─────────────────────────────────────┐
│ 共有ライブラリ X/libXapi.so (PIC 依存ライブラリへ静的リンク)        │
└───────────────────────────────────────────────────────────────────┘
```

### 各層の役割 (やさしい説明)

- **ユーザ層** — あなたが書くコード. Python の関数呼び出しと同じ感覚で
  書けます.
- **Python ラッパ層** — Python から C の関数を呼び出すための「翻訳係」.
  内部で `ctypes` を使って `.so` ファイルを読み込みます.
- **C ABI 層** — C の関数呼び出し規約 (Application Binary Interface) で
  Fortran と Python/C を*つなぐ窓口*. わずか 5 個の関数に絞ってあるので
  覚えやすいです.
- **Fortran バックエンド** — 物理計算の本体. 既存の `tr2` / `eqx2` / ...
  バイナリと*全く同じソースコード*を使うので, 数値一致が保証されます.
- **共有ライブラリ** — 上記全部をひとまとめにしたバイナリファイル.
  拡張子 `.so` は *shared object* の略.

## 共有ライブラリ (.so) とは

```{admonition} 補足
:class: note

**共有ライブラリ** (`.so` ファイル) とは, 「プログラムが実行中に読み込んで
使う, 再利用可能なコードのかたまり」のことです. Windows の `.dll`, macOS の
`.dylib` に相当します.

通常のプログラムは自己完結した `.exe` で全機能を持ちますが, 共有ライブラリ
方式では

- Python から `ctypes.CDLL("libtrapi.so")` と書けば読み込める
- C から `dlopen()`, コンパイル時リンクは `gcc -ltrapi` で OK

という具合に **あとから好きな言語から呼べる** のが利点です.
```

## 5 関数 C ABI

各モジュール `X` につき, エクスポートされる C 関数はたった 5 種類です.
これを覚えれば `X_` の頭文字さえ差し替えれば 7 モジュールすべてに共通です.

```c
/* tr の例. 他モジュールは tr_ を eq_ / wr_ / wrx_ / ti_ / fp_ / tot_ に置換 */
int tr_init(void);                                   /* 初期化   */
int tr_run(int ntmax);                                /* 時間発展 */
int tr_set_param(const char* name, double value);     /* パラメタ */
int tr_get_state(tr_state_t* state);                  /* 状態取得 */
int tr_finalize(void);                                /* 後始末   */
```

いずれも返り値 `int` は **エラーコード** (次節参照) です.
モジュールによっては文字列用の `X_set_param_str`,
配列要素用の `X_set_param` (インデックス付き名前 `"PN[1]"`),
一括検証 `X_validate`, 型特化 `X_get_state_s/v/m` などが追加で
エクスポートされますが, 上記 5 関数が中核です.

## エラーコード 0〜4

C ABI の返り値は次の 5 段階しかありません. 覚えやすいので暗記して
しまってかまいません.

| コード | 定数名 | 意味 |
|:-:|---|---|
| 0 | `X_OK`              | 正常終了 |
| 1 | `X_ERR_INVALID`     | パラメータ名 / 値が不正 |
| 2 | `X_ERR_NOT_INIT`    | `X_init` を呼んでいない |
| 3 | `X_ERR_CALC_FAILED` | 計算が失敗した |
| 4 | `X_ERR_NOT_IMPL`    | 未実装 (Phase L-2 時点のスタブ) |

Python 側では, 0 以外が返ると `Xlib`\ `Error` の **派生例外** が投げられます.
例: `TrlibParamError`, `FplibNotInitError`.

## 5 関数のライフサイクル

```text
  X_init ──▶ X_set_param ──▶ X_run ──▶ X_get_state ──▶ X_finalize
                 ▲     │
                 └─────┘
              (繰り返し)
```

- `X_init` — 1 プロセス 1 回だけ呼ぶ. Fortran 側の COMMON ブロックを
  初期化します.
- `X_set_param` — 何度でも呼べます. 例: `"RR"` (大半径), `"BB"` (磁場),
  `"PN[1]"` (1 番目のイオン密度) に値を与えます.
- `X_run` — 指定したステップ数だけ時間発展を進めます.
- `X_get_state` — 現在の状態を `X_state_t` 構造体 (C) に書き出します.
  Python では `XState` dataclass になります.
- `X_finalize` — 片付け. 通常は `with` 文が自動で呼んでくれます.

```{admonition} モジュール状態のリセット
:class: warning

`X_finalize` を呼んだ後に再度 `X_init` してもモジュールレベルの状態は
完全にはリセットされません. テストで同一プロセス内再初期化を行う場合は
`pytest --forked` で物理的に分離してください. 詳細は memory
`feedback_never_skip_tests` および本マニュアルのテスト章を参照.
```

## PIC (位置独立コード) とは

```{admonition} 補足
:class: note

**PIC** = Position Independent Code. 共有ライブラリ (`.so`) を作るときに
*どのアドレスにロードされても動く* ように `gcc` / `gfortran` が吐くコードの
ことです. 通常の静的ライブラリ (`.a`) には要りません.

TASK では, 旧来の `.a` アーカイブ (非 PIC) を保存したまま, PIC 版
`lib*_pic.a` を並行して生成するように各モジュールの `Makefile` を修正
しました. これで `tr2` / `eqx2` バイナリのビルドは一切変わらず, 共有
ライブラリも作れるようになっています.
```

### PIC 用の Makefile ターゲット

各モジュールには次のターゲットが追加されています.

```bash
make -C lib  libs_pic    # lib/ 配下の PIC アーカイブ
make -C pl   libs_pic    # pl/plcomm_pic.a など
make -C eq   libs_pic
make -C mtxp libs_pic
make -C bpsd libs_pic
make -C tr   libtrapi.so   # 最終成果物 (eqx / fpx / ... も同様)
```

## Python ラッパの 2 層設計

Python 側は **わざと 2 層** に分けてあります.

```text
┌────────────────────────────────────────────────────────────┐
│ 高レベル:                                                   │
│   Trlib, TrState, TrlibError 階層                           │
└──────────────────────────┬─────────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────────┐
│ 低レベル:                                                   │
│   trlib._ffi  (ctypes CDLL, TrStateC 構造体)                │
└──────────────────────────┬─────────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────────┐
│ tr/libtrapi.so  (dlopen される)                             │
└────────────────────────────────────────────────────────────┘
```

低レベル `_ffi.py` は C ABI の *鏡写し* で, `ctypes.Structure` で
`X_state_t` の各フィールドを同じ順序・同じ型で並べています. バイト単位で
一致するので, Fortran が書き出した生データをそのまま Python 側で読めます.

高レベル `Xlib.py` は Python らしい API (`with` 文, dataclass, 例外クラス)
を提供します.

## ライブラリの探し方

`Xlib()` を引数なしで呼ぶと, 次の順で `.so` を探します.

1. 環境変数 `XLIB_PATH` (例: `TRLIB_PATH`, `FPLIB_PATH`, `EQLIB_PATH`,
   `WRLIB_PATH`, `WRXLIB_PATH`, `TILIB_PATH`, `TOTLIB_PATH`)
2. `<リポジトリ root>/X/libXapi.so` (標準ビルド場所)
3. `<リポジトリ root>/lib/libXapi.so` (将来のインストール先)

明示的に指定したい場合は `Trlib(lib_path="/絶対/パス")` とします.

## RTLD_LAZY ロード

```{admonition} 補足
:class: note

`ctypes.CDLL(..., mode=RTLD_LAZY)` は「実際にその関数が呼ばれる瞬間まで
シンボル解決を遅らせる」オプションです. TASK の共有ライブラリは,
グラフィクス関連のシンボルが一部残ったまま作られるため, `RTLD_NOW`
(即時解決) だとロードに失敗することがあります. `RTLD_LAZY` なら, 呼ばない
パスの解決を後回しにできるので安全です.
```

## メモリレイアウト (C と Fortran の違い)

```{admonition} 注意
:class: warning

C は **行優先**, Fortran は **列優先** でデータを並べます. たとえば
C の `double RN[NRMAX][NSMAX]` は Fortran の
`REAL(KIND=8) :: RN(NSMAX, NRMAX)` と **バイト単位で一致** しますが,
添字の順序が逆です. Python 側の `XState` dataclass は `nrmax` 側を外側の
リスト, `nsmax` を内側のリストとして見せるので, C 流の順番です.
```

## 本章のまとめ

以降の章は, 「API は 5 つ, エラーは 0〜4, 例外は `Xlib`\ `Error` 派生,
`with` で書く」という **1 つのパターンを 7 回繰り返す** だけで
読み進められます. 最初は {doc}`../tr/index` を読み, そこから
`eq` / `ti` / `fp` / `wr` / `wrx` / `tot` の各章へ横展開するのを推奨します.
