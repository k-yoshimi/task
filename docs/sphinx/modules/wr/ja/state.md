# 出力されるパラメータ・物理量 (`WrState`)

`wr.get_state()` は `WrState` dataclass を返します. これがレイトレース
結果として取得できる量の全リストです.

## 次元情報 (dimension fields)

| フィールド | 意味 |
|---|---|
| `state.nraymax` | 実際にトレースされたレイの本数 |
| `state.nrsmax`  | 半径方向 (minor radius) プロファイル点数 |
| `state.nrlmax`  | 主半径方向 (major radius) プロファイル点数 |

## スカラー量 (4 個, `state.scalars` 辞書)

`wr` の主要出力. 全レイを通じてのピークパワーの位置と値.

| キー | 単位 | 意味 |
|---|---|---|
| `pos_pwrmax_rs` | m | minor radius プロファイル全体でのピークパワー位置 |
| `pwrmax_rs`     | -- | 同上の値 |
| `pos_pwrmax_rl` | m | major radius プロファイル全体でのピークパワー位置 |
| `pwrmax_rl`     | -- | 同上の値 |

```python
state.scalars["pos_pwrmax_rs"]   # minor radius でピーク位置
state.scalars["pwrmax_rs"]       # 値
state.scalars["pos_pwrmax_rl"]   # major radius でピーク位置
state.scalars["pwrmax_rl"]       # 値
```

ECRH/ECCD のパワー堆積位置を確認する典型的な使い方:

```python
print(f"ECRH 堆積位置: r/a ≈ {state.scalars['pos_pwrmax_rs']/RA:.2f}")
```

## レイ別の終端情報 (per-ray)

各レイがどこで終わったか, ピークパワーがどこにあったかを返します.
配列インデックスは 0-origin (Python 流儀).

| フィールド | 型 | 意味 |
|---|---|---|
| `state.nstp_end[i]`           | int   | i 番目レイの終端ステップ番号 |
| `state.pos_pwrmax_rs_nray[i]` | float | i 番目レイのピーク位置 (rs) |
| `state.pwrmax_rs_nray[i]`     | float | 同上の値 |
| `state.pos_pwrmax_rl_nray[i]` | float | i 番目レイのピーク位置 (rl) |
| `state.pwrmax_rl_nray[i]`     | float | 同上の値 |
| `state.rays_end[i][k]`        | float | i 番目レイの終端における k 番目の物理量 (`NRAY_EQ` 個) |

`rays_end[i]` には終端での位置, 波数ベクトル, パワーなどが入ります
(レイの方程式変数).

## プロファイル量 (radial profiles)

吸収パワーの半径方向分布. レイすべての寄与の和.

```python
state.pos_nrs[k]   # k 番目の minor radius サンプル位置 [m]
state.pwr_nrs[k]   # 同位置のパワー堆積率
state.pos_nrl[k]   # k 番目の major radius サンプル位置 [m]
state.pwr_nrl[k]   # 同位置のパワー堆積率
```

可視化例:

```python
import matplotlib.pyplot as plt
plt.plot(state.pos_nrs, state.pwr_nrs, label="rs profile")
plt.plot(state.pos_nrl, state.pwr_nrl, label="rl profile")
plt.xlabel("R [m]")
plt.ylabel("Absorbed power")
plt.legend()
```

## 補助メソッド

```python
state.to_dict()   # JSON-ready dict
```

完全な属性リストは {doc}`api-reference` の `WrState` autodoc を参照.

## `tr`/`fp` の State との違い

| | `TrState` (tr) | `FpState` (fp) | `WrState` (wr) |
|---|---|---|---|
| **時間** | あり (`nt`) | あり (`timefp`) | **なし** (空間積分) |
| **次元** | 半径 × 種 | 5D 位相空間 (モーメント化) | **レイ × ステップ** + 半径プロファイル |
| **スカラー** | 13 (T, BETAN, ...) | 7 大域量 (+ `timefp`) | **4** (ピーク位置 + 値) |
| **主要出力** | プロファイル | モーメント | **レイ軌跡 + 吸収プロファイル** |
| **物理単位** | 流体量 | 分布関数モーメント | RF パワー堆積 |
