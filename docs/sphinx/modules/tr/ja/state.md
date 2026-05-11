# 出力されるパラメータ・物理量 (`TrState`)

`tr.get_state()` は `TrState` dataclass を返します. これがシミュレーション
結果として取得できる量の全リストです. フィールドは `tr/tr_api.h` の
C 構造体 `tr_state_t` と対応します.

## 次元情報 (dimension fields)

```python
state.nt              # 時刻ステップカウンタ
state.nrmax           # 実働の半径点数 (<= TR_MAX_NRMAX=500)
state.nsmax           # 実働の粒子種数 (<= TR_MAX_NSMAX=8)
```

## スカラー量 (14 個, `state.scalars` 辞書)

プラズマ全体を代表する時空間積分量. 以下 14 個が常に取得できます.

| キー | 単位 | 意味 |
|---|---|---|
| `T`       | s  | シミュレーション時刻 |
| `WPT`     | MJ | 全蓄積プラズマエネルギー (`WBULKT + WTAILT`) |
| `AJT`     | MA | 全プラズマ電流 (全半径で積分した `AJ`) |
| `Q0`      | — | 磁気軸上の安全係数 |
| `BETA0`   | — | 軸上トロイダル $\beta$ |
| `BETAP0`  | — | 軸上ポロイダル $\beta$ |
| `BETAA`   | — | セパラトリクス上のトロイダル $\beta$ |
| `BETAN`   | — | 規格化 $\beta_N$ (Troyon $\beta$: $\beta_A \cdot 100 / (I_p / (aB))$) |
| `TAUE1`   | s | エネルギー閉じ込め時間 ($W_{PT}/P_{\mathrm{IN}}$) |
| `TAUE2`   | s | エネルギー閉じ込め時間 ($W_{PT}/(P_{\mathrm{IN}}-\dot{W})$, 定常補正版) |
| `ZEFF0`   | — | 軸上の実効電荷数 $Z_\text{eff}$ |
| `ALI`     | — | プラズマ内部インダクタンス $\ell_i$ |
| `RQ1`     | m | $q=1$ 面の半径 (存在しない場合は `RA`) |
| `AJRFT`   | MA | 全 RF + 外部駆動電流 (L-7b-i) |

取得例:

```python
state.scalars["T"]       # 現在時刻
state.scalars["WPT"]     # 蓄積エネルギー
state.scalars["BETAN"]   # Troyon β
state.scalars["TAUE1"]   # τ_E
```

## プロファイル量 (radial profiles)

半径方向分布. 2 次元量は `[radius_index][species_index]` の順で C 行優先
(共通アーキテクチャの節参照).

```python
state.RN[nr][ns]      # 密度プロファイル [10^20 m^-3]
state.RT[nr][ns]      # 温度プロファイル [keV]
state.AJ[nr]          # 電流密度プロファイル [MA/m^2]
state.QP[nr]          # 安全係数プロファイル
```

インデックスは 0-origin (Python 流儀). 例えば境界値は
`state.RT[state.nrmax-1][0]` で電子温度の縁での値が取れます.

## 補助メソッド

```python
state.to_dict()       # Phase 0 ベースライン互換の JSON-ready dict
```

完全な属性リストは {doc}`api-reference` の `TrState` autodoc を参照.
