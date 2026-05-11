# 出力されるパラメータ・物理量 (`TotState`)

`tot.get_state()` は `TotState` dataclass を返します. **`TrState` をベース
にサブモジュール存在フラグを追加した** 構造です.

## サブモジュール存在フラグ (presence flags)

各サブモジュールが正常に init されたかを 0/1 で示します.

| フィールド | 意味 |
|---|---|
| `state.tr_present`  | TR がロードされていれば 1 |
| `state.ti_present`  | TI がロードされていれば 1 |
| `state.fp_present`  | FP がロードされていれば 1 |
| `state.wr_present`  | WR がロードされていれば 1 |

通常はすべて 1. 0 のモジュールはそのプレフィックスのパラメータ設定が
エラーになります.

## 次元情報 (dimension fields)

| フィールド | 意味 |
|---|---|
| `state.nt`     | 時刻ステップカウンタ (TR が源) |
| `state.nrmax`  | 半径点数 (TR が源) |
| `state.nsmax`  | 粒子種数 (TR が源) |

```{note}
これらの次元は **TR モジュール由来** です. eq/fp/wr など他モジュールの
プロファイルは取得できません — そのためには各モジュールを単独で
インスタンス化してください.
```

## スカラー量 (14 個, `state.scalars` 辞書)

`TrState` と **完全に同じ** 14 スカラーを返します. プラズマ全体の
代表量です.

| キー | 単位 | 意味 |
|---|---|---|
| `T`       | s  | シミュレーション時刻 |
| `WPT`     | MJ | 全蓄積プラズマエネルギー |
| `AJT`     | MA | 全プラズマ電流 |
| `Q0`      | — | 磁気軸上の安全係数 |
| `BETA0`   | — | 軸上トロイダル $\beta$ |
| `BETAP0`  | — | 軸上ポロイダル $\beta$ |
| `BETAA`   | — | セパラトリクス上のトロイダル $\beta$ |
| `BETAN`   | — | 規格化 $\beta_N$ |
| `TAUE1`   | s | エネルギー閉じ込め時間 |
| `TAUE2`   | s | エネルギー閉じ込め時間 (定常補正版) |
| `ZEFF0`   | — | 軸上の実効電荷数 |
| `ALI`     | — | プラズマ内部インダクタンス |
| `RQ1`     | m | $q=1$ 面の半径 |
| `AJRFT`   | MA | 全 RF + 外部駆動電流 (L-7b-i) |

各スカラーの物理的意味と算出式は
`tr` モジュールの state ページ (`docs/sphinx/modules/tr/ja/state.md`)
を参照してください.

```python
state.scalars["T"]
state.scalars["BETAN"]
```

## プロファイル量 (radial profiles)

`TrState` と同じく `tr` の半径プロファイルを返します.

```python
state.RN[nr][ns]      # 密度プロファイル [10^20 m^-3]
state.RT[nr][ns]      # 温度プロファイル [keV]
state.AJ[nr]          # 電流密度プロファイル [MA/m^2]
state.QP[nr]          # 安全係数プロファイル
```

`tr` で計算された後, eq, ti, fp, wr の影響を反映した **最新の値** が
取得できます.

## 補助メソッド

```python
state.to_dict()       # JSON-ready dict
```

完全な属性リストは {doc}`api-reference` の `TotState` autodoc を参照.

## サブモジュール固有の出力を取りたい場合

`TotState` は **TR ベース + presence フラグ** だけです. 例えば:

- eq の `raxis`, `qaxis` などは取得できない
- fp の `RJT`, `RWT` などは取得できない
- wr の `pwr_nrs[]` プロファイルは取得できない

これらが必要なら, **`Tot` ではなく単独モジュール** (`Eq`, `Fplib`,
`Wrlib`) でシミュレーションするか, `Tot` の API 拡張を待ってください.

## `TrState` との関係

| | `TrState` (tr 単独) | `TotState` (tot 統合) |
|---|---|---|
| **次元** | nt, nrmax, nsmax | + tr_present, ti_present, fp_present, wr_present |
| **スカラー** | 14 個 | 14 個 (同一) |
| **プロファイル** | RN, RT, AJ, QP | RN, RT, AJ, QP (同一) |
| **計算源** | 単独 tr | tr (eq/ti/fp/wr の影響反映) |
