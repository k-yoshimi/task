# 出力されるパラメータ・物理量 (`EqState`)

`eq.get_state()` は `EqState` dataclass を返します. これが平衡計算の
結果として取得できる量の全リストです. フィールドは `eq/eq_api.h` の
C 構造体 `eq_state_t` と対応します.

## 次元情報 (dimension fields)

| フィールド | 意味 |
|---|---|
| `state.nrgmax`  | 実働の R 格子点数 |
| `state.nzgmax`  | 実働の Z 格子点数 |
| `state.npsmax`  | 実働の磁束面サンプル数 |
| `state.nrmax`   | ψ-メッシュの半径点数 |
| `state.nthmax`  | ψ-メッシュのポロイダル点数 |
| `state.nsumax`  | 境界点数 |
| `state.nrvmax`  | 体積グリッドの半径点数 (`MODELG=3` のみ) |

## スカラー量 (12 個, `state.scalars` 辞書)

平衡解の最も重要な代表量. プラズマ全体を 1 つの数で要約したもの.

| キー | 単位 | 意味 |
|---|---|---|
| `raxis`  | m | 磁気軸の R 座標 |
| `zaxis`  | m | 磁気軸の Z 座標 |
| `psi0`   | Wb/rad | 磁気軸での ψ |
| `psipa`  | Wb/rad | プラズマ表面での ψ_p (ポロイダル磁束) |
| `psita`  | Wb/rad | プラズマ表面での ψ_t (トロイダル磁束) |
| `qaxis`  | — | 磁気軸での安全係数 $q$ |
| `qsurf`  | — | プラズマ表面での $q$ |
| `betat`  | — | トロイダル $\beta$ |
| `betap`  | — | ポロイダル $\beta$ |
| `pvol`   | m³ | プラズマ体積 |
| `raave`  | m | 体積平均小半径 |
| `ripx`   | MA | 計算で得られたプラズマ電流 |

取得例:

```python
state.scalars["raxis"]   # 磁気軸 R
state.scalars["qaxis"]   # 中心 q
state.scalars["betat"]   # トロイダル β
state.scalars["pvol"]    # プラズマ体積
```

```{note}
`ripx` (出力) と `RIP` (入力) は独立: 解いた結果の総電流が `ripx` で,
入力した目標値が `RIP`. 両者がほぼ一致しないなら平衡が収束していない
可能性があります.
```

## グリッド・プロファイル量

### R-Z 座標

```python
state.rg   # [nrgmax] R 軸座標
state.zg   # [nzgmax] Z 軸座標
```

固定刻みの直交座標系で `psirz` (R-Z 上の ψ 値) のサンプリング点を表します.

### 磁束面プロファイル

ψ-面 (磁気面) ごとに 1 個の値を持つ 1 次元配列. `state.npsmax` 個の
サンプル点があります.

```python
state.psips   # [npsmax] 磁束面の ψ 値
state.ppps    # [npsmax] 圧力プロファイル p(ψ)
state.ttps    # [npsmax] T(ψ) = 2π · R · B_φ
state.qqps    # [npsmax] q(ψ) 安全係数プロファイル
```

`state.psips` をｘ軸に, 他をｙ軸にプロットすると **磁束面ごとの物理量
分布** がわかります.

```python
import matplotlib.pyplot as plt
plt.plot(state.psips, state.qqps)
plt.xlabel("ψ")
plt.ylabel("q")
plt.title("Safety factor profile")
```

## 補助メソッド

```python
state.to_dict()   # Phase 0 ベースライン互換の JSON-ready dict
```

完全な属性リストは {doc}`api-reference` の `EqState` autodoc を参照.

## `tr` の `TrState` との違い

| | `TrState` (tr) | `EqState` (eq) |
|---|---|---|
| **次元** | `nrmax` × `nsmax` (粒子種) | `nrgmax` × `nzgmax` (R-Z 格子) + `npsmax` (磁束面) |
| **時間** | `nt` (時間ステップカウンタ) を持つ | 時間概念なし |
| **スカラー数** | 13 (`T`, `WPT`, `BETAN`, ...) | 12 (`raxis`, `qaxis`, `betat`, ...) |
| **主な物理量** | 密度・温度・電流・q プロファイル | ψ サーフェス幾何 + p, T, q |

`eq` は時間発展せず「与えられた条件で平衡を解く」だけなので, 出力は
**1 時刻のスナップショット** に相当します.
