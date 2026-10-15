# サポートされている入力パラメータ

`eq/eq_param_registry.f90` には全 94 件 (≈78 数値スカラー, 5 配列ファミリ,
7 文字列) が登録されています. 名前は Fortran の `/EQ/` ネームリストと
一致しています. 既定値は `eq/eqinit.f90::EQINIT` で設定されます.

## 必須・推奨パラメータ

ほとんどのパラメータは既定値があるため最小構成では何も指定しなくても
`run()` できます. ただし **特定の条件で必須** になるものと, **物理的に
意味のある結果を得るには上書きすべき** ものがあります.

### 必須 (条件付き)

| 条件 | 必須パラメータ | 理由 |
|---|---|---|
| `MODELG ∈ {3, 5, 8}` | **`KNAMEQ`** (文字列) | 平衡データファイル名. 未設定だと `validate()` が `FILE_MISSING` 診断を返し, `run()` は不正な平衡を出す |

```python
eq.set_param("MODELG", 3)
eq.set_param_str("KNAMEQ", "eqdata.ITER01")
```

`MODELG=2` (解析的トロイダル幾何, 既定) なら `KNAMEQ` 不要なので
**厳密な意味で必須なパラメータはありません**.

### 強く推奨 (既定値が generic すぎる)

既定値はジェネリック小型トカマクを想定したダミーなので, 解析対象の装置
が決まっているなら以下は明示的に上書きすべきです.

| 名前 | 既定値 | 推奨上書き例 (ITER 想定) |
|---|---|---|
| `RR`     | 3.0 m  | 6.2 m |
| `RA`     | 1.0 m  | 2.0 m |
| `BB`     | 3.0 T  | 5.3 T |
| `RIP`    | 3.0 MA | 15.0 MA |
| `RKAP`   | 1.0    | 1.7 |
| `RDLT`   | 0.0    | 0.5 |

### グリッド寸法 (通常は既定で十分)

| 名前 | 既定値 | 上限 |
|---|---|---|
| `NSGMAX` (Grad-Shafranov 半径) | 32 | コンパイル時最大値 |
| `NRGMAX` (R-Z 横メッシュ) | 33 | 同上 |
| `NPSMAX` (磁束面サンプル) | 21 | 同上 |
| `NRMAX` (磁束座標半径) | 50 | 同上 |
| `NTHMAX` (ポロイダル) | 64 | 同上 |

`validate()` でコンパイル時最大値超過は `OUT_OF_RANGE` 診断として
事前検出できます.

### 推奨ワークフロー

```python
from eqlib import Eq, EqDiagCode

with Eq() as eq:
    # 1. 必ず指定するもの
    eq.set_params(RR=6.2, RA=2.0, BB=5.3, RIP=15.0,
                  RKAP=1.7, RDLT=0.5)

    # 2. MODELG=3 にするなら KNAMEQ 必須
    eq.set_param("MODELG", 3)
    eq.set_param_str("KNAMEQ", "eqdata.ITER01")

    # 3. 設定後, run の前に validate
    diags = eq.validate()
    for d in diags:
        print(f"[{EqDiagCode(d.code).name}] {d.param}: {d.message}")
    if diags:
        raise SystemExit("fix the diagnostics before running")

    eq.run()  # mode=1
    state = eq.get_state()
```

---

## 1. 幾何・装置 (Geometry / device)

プラズマの空間形状と磁場強度. `RR`, `RA`, `BB`, `RIP` の 4 つが最も
重要です.

| 名前 | 型 | 既定値 | 単位 | 意味 |
|---|---|---|---|---|
| `RR`    | double | 3.0 | m | プラズマ大半径 |
| `RA`    | double | 1.0 | m | プラズマ小半径 |
| `RB`    | double | 1.2 | m | 壁の小半径 |
| `RKAP`  | double | 1.0 | — | elongation (楕円率) |
| `RDLT`  | double | 0.0 | — | triangularity |
| `BB`    | double | 3.0 | T | 中心トロイダル磁場 |
| `RIP`   | double | 3.0 | MA | プラズマ電流 |
| `FRBIN` | double | 1.0 | — | $(R_{B,\text{in}} - R_A) / (R_{B,\text{out}} - R_A)$ |

## 2. 安全係数 (Safety factor)

| 名前 | 型 | 既定値 | 意味 |
|---|---|---|---|
| `Q0`     | double | 1.0 | 中心 $q$ |
| `QA`     | double | 3.0 | 表面 $q$ |
| `QMIN`   | double | 1.5 | 反転シア時の最小 $q$ |
| `RHOMIN` | double | 0.0 | 最小 $q$ の位置 (規格化半径; 通常シアなら 0) |
| `RHOEDG` | double | 1.0 | 端での平滑化開始位置 (1 で平滑化なし) |

## 3. 圧力プロファイル (Pressure profile)

$$p(\psi) = P_{P0}(1-\psi^{P_{R0}})^{P_{PROFP0}} + P_{P1}(1-\psi^{P_{R1}})^{P_{PROFP1}} + P_{P2}\,(\text{ITB 内部のみ})$$

| 名前 | 型 | 既定値 | 単位 | 意味 |
|---|---|---|---|---|
| `PP0`     | double | 0.001 | MPa | 主成分の圧力振幅 |
| `PP1`     | double | 0.0   | MPa | 副成分 |
| `PP2`     | double | 0.0   | MPa | ITB 内部の追加成分 |
| `PROFP0`  | double | 1.5   | — | 主成分の指数 |
| `PROFP1`  | double | 1.5   | — | 副成分の指数 |
| `PROFP2`  | double | 2.0   | — | ITB 成分の指数 |

## 4. 電流プロファイル (Current profile)

| 名前 | 型 | 既定値 | 意味 |
|---|---|---|---|
| `PJ0`     | double | 1.0 | 中心電流密度 (主成分) |
| `PJ1`     | double | 0.0 | 副成分 |
| `PJ2`     | double | 0.0 | ITB 成分 |
| `PROFJ0`  | double | 1.5 | 主成分の指数 |
| `PROFJ1`  | double | 1.5 | 副成分の指数 |
| `PROFJ2`  | double | 1.5 | ITB 成分の指数 |

## 5. $F(\psi)$ 関数 (toroidal flux function)

$$F(\psi) = B_T R + \mathrm{FF}_0 (1-\psi^{P_{R0}})^{P_{F0}} + \cdots$$

| 名前 | 型 | 既定値 | 意味 |
|---|---|---|---|
| `FF0`     | double | 1.0 | 主成分振幅 |
| `FF1`     | double | 0.0 | 副成分 |
| `FF2`     | double | 0.0 | ITB 成分 |
| `PROFF0`  | double | 1.5 | 主成分の指数 |
| `PROFF1`  | double | 1.5 | 副成分の指数 |
| `PROFF2`  | double | 1.5 | ITB 成分の指数 |

## 6. 温度・密度プロファイル (Temperature / density)

| 名前 | 型 | 既定値 | 単位 | 意味 |
|---|---|---|---|---|
| `PT0`      | double | 1.0  | keV | 中心温度 |
| `PT1`      | double | 0.0  | keV | 副成分 |
| `PT2`      | double | 0.0  | keV | ITB 成分 |
| `PTSEQ`    | double | 0.05 | keV | 端温度 |
| `PROFTP0`  | double | 1.5  | — | 主成分指数 |
| `PROFTP1`  | double | 1.5  | — | 副成分指数 |
| `PROFTP2`  | double | 2.0  | — | ITB 成分指数 |
| `PN0EQ`    | double | 1.0×10²⁰ | m⁻³ | 中心数密度 (定数) |

## 7. トロイダル回転 (Velocity profile)

| 名前 | 型 | 既定値 | 単位 | 意味 |
|---|---|---|---|---|
| `PV0`     | double | 0.0 | m/s | 主成分 |
| `PV1`     | double | 0.0 | m/s | 副成分 |
| `PV2`     | double | 0.0 | m/s | ITB 成分 |
| `PROFV0`  | double | 1.5 | — | 主成分指数 |
| `PROFV1`  | double | 1.5 | — | 副成分指数 |
| `PROFV2`  | double | 2.0 | — | ITB 成分指数 |

## 8. 半径プロファイル形状 (Radial profile shape)

| 名前 | 型 | 既定値 | 意味 |
|---|---|---|---|
| `PROFR0` | double | 1.0 | 主成分の半径ベース指数 |
| `PROFR1` | double | 2.0 | 副成分の半径ベース指数 |
| `PROFR2` | double | 2.0 | ITB 成分の半径ベース指数 |

## 9. メッシュ寸法 (Grid dimensions)

`validate()` でコンパイル時最大値超過がチェックされる項目です.

| 名前 | 型 | 既定値 | 用途 |
|---|---|---|---|
| `NSGMAX` | int | 32  | Grad-Shafranov 半径方向メッシュ |
| `NTGMAX` | int | 32  | Grad-Shafranov ポロイダルメッシュ |
| `NUGMAX` | int | 32  | 磁束面平均量の半径メッシュ |
| `NRGMAX` | int | 33  | R-Z 平面の R 方向 |
| `NZGMAX` | int | 33  | R-Z 平面の Z 方向 |
| `NPSMAX` | int | 21  | 磁束面サンプル数 |
| `NRMAX`  | int | 50  | 磁束座標の半径メッシュ |
| `NTHMAX` | int | 64  | 磁束座標のポロイダルメッシュ |
| `NSUMAX` | int | 65  | 境界点数 |
| `NRVMAX` | int | 50  | 面平均の半径メッシュ |
| `NTVMAX` | int | 400 | 面平均のポロイダルメッシュ |
| `NPFCMAX` | int | 0  | PF コイル数 |

## 10. 反復・収束 (Iteration / convergence)

| 名前 | 型 | 既定値 | 意味 |
|---|---|---|---|
| `EPSEQ`  | double | 1×10⁻⁶ | 平衡反復の収束判定 |
| `NLPMAX` | int    | 100    | 平衡反復の最大数 |
| `EPSNW`  | double | 1×10⁻² | Newton 法の収束判定 |
| `DELNW`  | double | 1×10⁻² | Newton 法での微分の刻み幅 |
| `NLPNW`  | int    | 20     | Newton 法の最大反復数 |

## 11. 動作モード (Mode switches)

`MODELG` (幾何モデル) が最も重要です.

| 名前 | 型 | 既定値 | 意味 |
|---|---|---|---|
| `MODELG` | int switch | 2 | 幾何モデル選択 |
| `MODELN` | int switch | 0 | プラズマプロファイル供給源 |
| `MODELQ` | int switch | 0 | $q$ プロファイル制御 (`MODELG=0,1,2` 用) |
| `MDLEQF` | int switch | 0 | 与えるプロファイルの種類 |
| `MDLEQA` | int switch | 0 | $\rho$ の取り方 |
| `MDLEQC` | int switch | 0 | ポロイダル座標の選択 |
| `MDLEQX` | int switch | 0 | 自由境界計算の方式 |
| `MDLEQV` | int switch | 3 | 真空領域での $\psi$ 外挿次数 |
| `NPRINT` | int switch | 0 | 出力詳細度 |
| `IDEBUG` | int switch | 0 | デバッグ出力フラグ |
| `MODEFR` | int switch | 0 | (内部用) |
| `MODEFW` | int switch | 0 | (内部用) |

`MODELG` の許容値:

| 値 | 挙動 |
|---|---|
| 0 | Slab geometry (平板近似) |
| 1 | Cylindrical geometry (円柱近似) |
| 2 (既定) | Toroidal geometry (解析的トロイダル) |
| 3 | TASK/EQ 出力ファイル経路 (`KNAMEQ` 必要) |
| 4 | VMEC 出力経路 |
| 5 | EQDSK ファイル経路 (`KNAMEQ` 必要) |
| 6 | Boozer 座標出力 |
| 8 | (TASK 内専用パス, `KNAMEQ` 必要) |

`MDLEQF` の許容値:

| 値 | 与えるプロファイル |
|---|---|
| 0 (既定) | $P, J_\text{tor}, T, V_\varphi$ + $I_p$ (解析) |
| 1 | $P, F$ + $I_p$ (解析) |
| 2 | $P, J_\parallel$ + $I_p$ (解析) |
| 3 | $P, J_\parallel$ (解析) |
| 4 | $P, q$ (解析) |
| 5–9 | スプライン版 (上記 0–4 と同じ組合せ) |

## 12. 計算領域・リミタ (Computation domain)

| 名前 | 型 | 既定値 | 単位 | 意味 |
|---|---|---|---|---|
| `RGMIN` | double | 1.5  | m | 計算領域の最小 R |
| `RGMAX` | double | 4.5  | m | 計算領域の最大 R |
| `ZGMIN` | double | -2.0 | m | 計算領域の最小 Z |
| `ZGMAX` | double | 2.0  | m | 計算領域の最大 Z |
| `ZLIMP` | double | 2.5  | m | 上側 X 点の Z |
| `ZLIMM` | double | -2.5 | m | 下側 X 点の Z |

## 13. ψ 境界 (`PSIB` — **0-origin**)

ポロイダル磁束 ψ の境界における **多重極展開係数**. 0-origin 配列です.

| 名前 | 型 | 既定値 | 意味 |
|---|---|---|---|
| `PSIB[0]` | double | 2.0 | 0 次 (定数項) |
| `PSIB[1]` | double | 0.5 | 1 次 |
| `PSIB[2]` | double | 0.0 | 2 次 |
| `PSIB[3]` | double | 0.0 | 3 次 |
| `PSIB[4]` | double | 0.0 | 4 次 |
| `PSIB[5]` | double | 0.0 | 5 次 |

```{warning}
他の 1-D 配列 (`RIPFC`, `RPFC`, `ZPFC`, `WPFC`) は 1-origin です. `PSIB`
だけが Fortran 宣言 `PSIB(0:5)` の理由は, $\psi=0$ (磁気軸) から数えるのが
物理的に自然だから ({doc}`faq` Q1 参照).
```

## 14. PF コイル (`RIPFC`, `RPFC`, `ZPFC`, `WPFC` — 1-origin)

| 名前 | 型 | 既定値 | 単位 | 意味 |
|---|---|---|---|---|
| `RIPFC[i]` | double[NPFCM] | 0.0   | MA | i 番目のコイル電流 |
| `RPFC[i]`  | double[NPFCM] | 3.0   | m  | i 番目のコイル R 位置 |
| `ZPFC[i]`  | double[NPFCM] | -1.75 | m  | i 番目のコイル Z 位置 |
| `WPFC[i]`  | double[NPFCM] | 0.75  | m  | i 番目のコイル幅 |

`NPFCMAX` (既定 0) でアクティブなコイル数を制御します.

## 15. 文字列 (Strings — `set_param_str` 専用)

| 名前 | 型 | 既定値 | 意味 |
|---|---|---|---|
| `KNAMEQ`  | CHARACTER(80) | `'eqdata'`  | 平衡データファイル (`MODELG=3,5,8` で必須) |
| `KNAMEQ2` | CHARACTER(80) | `'eqdata2'` | 追加平衡データ |
| `KNAMWR`  | CHARACTER(80) | `'wrdata'`  | レイトレースデータ |
| `KNAMWM`  | CHARACTER(80) | `'wmdata'`  | フルウェーブデータ |
| `KNAMFP`  | CHARACTER(80) | `'fpdata'`  | Fokker-Planck データ |
| `KNAMFO`  | CHARACTER(80) | `'fodata'`  | ファイル出力 |
| `KNAMPF`  | CHARACTER(80) | `'pfdata'`  | プロファイルデータ |

文字列パラメータは **`set_param` には渡せません**. `set_param_str` を
使ってください ({doc}`parameter-setting` 方法 C 参照).
