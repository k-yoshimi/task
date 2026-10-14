# 出力されるパラメータ・物理量 (`FpState`)

`fp.get_state()` は `FpState` dataclass を返します. fp は分布関数 $f(r, p, \theta)$
そのものは返さず, **モーメント量** (積分された物理量) のみを公開します.

## 次元情報 (dimension fields)

| フィールド | 意味 |
|---|---|
| `state.nrmax`  | プロファイル配列の半径メッシュ点数 (run で配列が確保された後は、現在の `NRMAX` とその確保サイズの小さい方。`NRMAX` を上げた場合は次の run から反映。最初の run の前は `NRMAX` そのもので、プロファイルは 0) |
| `state.nsamax` | プロファイル配列の active species 数 (分布関数を解いた粒子種。同じく現在の `NSAMAX` と確保サイズの小さい方) |
| `state.npmax`  | 運動量メッシュ点数 |
| `state.nthmax` | ピッチ角メッシュ点数 |
| `state.ntg2`   | 長時間軸カウンタ |

## スカラー量

シミュレーション時刻はトップレベルのフィールドで, `state.scalars` は
**7 個の大域量** の dict です. うち 6 個は体積積分された診断量で, active
粒子種について和をとった最新の大域診断サンプル (`NTG1`) の値, 残る 1 個は
プラズマ体積 (`TVOLR`, 半径方向セル体積の和) です.

```python
state.timefp                      # シミュレーション時刻 [s]
state.scalars["TOTAL_IP"]         # 全プラズマ電流 [MA]
```

| `state.scalars` のキー | 物理量 | 単位 |
|---|---|---|
| `TOTAL_IP`         | 全プラズマ電流 | MA |
| `STORED_ENERGY`    | 蓄積エネルギー | MJ |
| `COLLISION_POWER`  | 衝突パワーの合計 | MW |
| `ABSORPTION_POWER` | 波動吸収パワーの合計 | MW |
| `ABSORPTION_WR`    | そのうちレイトレーシング (WR) 分 | MW |
| `ABSORPTION_WM`    | そのうちフルウェーブ (WM) 分 | MW |
| `PLASMA_VOLUME`    | プラズマ体積 | m³ |

7 個とも最初の `run()` までは 0 で, `set_param` の後は次に `run()` が
実行されるまで再び 0 になります (その間もプロファイルは直前の run のままです).
下の単位体積あたりのプロファイルと違い, 体積要素を通じて
平衡に依存します. tr/eq のようなプラズマ性能指標は引き続き持ちません —
派生量 (`BETA`, `TAUE` など) はユーザ側で計算する設計です.

## プロファイル量 (radial × species のモーメント配列)

fp の主要出力. **`[nsamax][nrmax]` の 2 次元配列** で, active 粒子種ごとに
半径方向プロファイルを返します.

| フィールド | 物理量 | 単位 |
|---|---|---|
| `state.RNT[isa][nr]`  | 粒子数密度 (分布関数の 0 次モーメント) | 10²⁰ m⁻³ |
| `state.RWT[isa][nr]`  | エネルギー密度 (2 次モーメント) | MJ/m³ |
| `state.RTT[isa][nr]`  | 平均温度 (`RWT/RNT` から) | keV |
| `state.RJT[isa][nr]`  | 電流密度 (1 次モーメント, ピッチ角依存) | MA/m² |
| `state.RPCT[isa][nr]` | 衝突によるパワー授受 | MW/m³ |
| `state.RPWT[isa][nr]` | 波動加熱によるパワー授受 | MW/m³ |

```python
state.RNT[0][0]      # 0 番目 active species の軸上密度
state.RTT[0]         # 0 番目 active species の温度プロファイル全体
state.RJT[1]         # 1 番目 active species の電流密度プロファイル
```

## 5D 分布関数の取得

`FpState` には **分布関数本体 $f(r, p, \theta)$ は含まれません**. 5D グリッド
を直接展開すると JSON 化が破綻するためです. 必要な場合は:

1. C ABI レベルで `FpStateC` 構造体の追加フィールドを利用 (実装依存)
2. 代替: モーメント量 (RNT, RWT, RJT) で十分な解析を組み立てる
3. 別の API (`fp_get_distribution(species, ir)` など; 将来追加予定) を待つ

## 補助メソッド

```python
state.to_dict()   # JSON-ready dict
```

完全な属性リストは {doc}`api-reference` の `FpState` autodoc を参照.

## `tr`/`ti` の State との違い

| | `TrState` (tr) | `TiState` (ti) | `FpState` (fp) |
|---|---|---|---|
| **種別軸** | NSMAX | active NSA_MAX | active NSAMAX |
| **位相空間** | 1D 半径 | 1D 半径 | **5D** (r, p, θ, species, t) |
| **スカラー数** | 13 | 2 + 2int | **7** 大域量 (+ `timefp`) |
| **主出力** | RN, RT, AJ, QP | RNA, RTA, RUA, RBP, ZEFF, BETA | RNT, RWT, RTT, RJT, RPCT, RPWT |
| **意味** | 流体モーメント | 統合輸送モーメント | 分布関数モーメント |
| **メモリ消費** | 低 | 中 | **高** (5D) |
