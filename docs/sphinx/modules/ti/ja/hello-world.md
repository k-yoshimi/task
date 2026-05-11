# 最短 hello-world

```python
from tilib import Tilib

with Tilib() as ti:
    ti.set_params(RR=3.0, BB=3.0, NSMAX=2)  # (1) 装置と粒子種数
    ti.run(ntmax=10)                         # (2) 10 ステップ時間発展
    state = ti.get_state()                   # (3) 状態を取得 (型は TiState)
print(state.scalars["T"], state.scalars["residual_loop_max"])
```

## 行ごとの解説

- **(1) `set_params`**: 装置の幾何 (`RR`, `BB`) と粒子種数 (`NSMAX`) を一括
  設定. ti は tr と同じ namelist 形式のパラメータを受け取ります.
- **(2) `run(ntmax=10)`**: 時間発展を 10 ステップ進めます. ステップ幅は
  `DT` (既定 0.01 秒) 既定.
- **(3) `get_state()`**: 結果を `TiState` dataclass に写し取ります.
  詳細は {doc}`state`.

## 期待される出力例

```
0.1  3.45e-08
```

完全な実行可能例は {doc}`quickstart` を参照.

## `tr` との違い

- **物理範囲**: `tr` は単純な 1D 輸送, `ti` は **輸送と補助物理 (中性ビーム,
  RF 加熱, 不純物, 核融合) を統合** したフルパッケージ.
- **スカラー出力**: `tr` は 14 スカラー (BETAN, TAUE 等, AJRFT), `ti` は **2 スカラー
  + 2 反復カウンタ** (T と収束診断).
- **プロファイル**: `tr` は species 軸が外側 `RN[nr][ns]`, `ti` は active
  species 軸 `RNA[nr][nsa]` (内部で species をマッピング).
- **登録パラメータ**: `tr` は約 30, `ti` は **77 個** (補助物理モジュール
  切替が多いため).
