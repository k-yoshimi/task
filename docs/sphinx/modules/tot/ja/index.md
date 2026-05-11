# `tot` — オーケストレータ

```{admonition} この章で学ぶこと
:class: tip

TASK/TOT (**オーケストレータ**: eq / tr / ti / fp / wr / wrx の各モジュール
を 1 つのライブラリで統合実行) を Python から呼ぶ `totlib` の使い方を
学びます. 共有ライブラリのビルド, **プレフィックス付きパラメータ規則**
(`eq:RR`, `tr:NSMAX` 等), サブモジュール連携, 4 層テストまでカバーします.
```

## 概要 — `tot` は何をする

**TASK/TOT** はトカマクプラズマシミュレーションの **オーケストレータ**
です. eq / tr / ti / fp / wr / wrx の各モジュールを 1 つのプロセス内で
統合実行し, **動的にデータを受け渡し** ます.

例えば「平衡 + 輸送 + ECRH 加熱 + 高速イオン解析」という統合シミュレーション
では, 通常なら `Eq()`, `Trlib()`, `Wrlib()`, `Fplib()` を順次呼んで結果を
手作業で受け渡すコードが必要ですが, `Tot()` 1 つで完結します:

```python
with Tot() as tot:
    tot.set_param("eq:RR", 6.5)
    tot.set_param("tr:NSMAX", 2)
    tot.set_param("wr:RF", 170e9)
    tot.run(ntmax=10)
```

得られる主な量 (TR ベース):

- スカラー (14 個): `T`, `WPT`, `BETAN`, `TAUE1`, ..., `AJRFT`
- プロファイル: `RN`, `RT`, `AJ`, `QP` (TR 互換)
- 追加: `tr_present`, `ti_present`, `fp_present`, `wr_present` (サブモジュール
  存在フラグ)

## 使い方ガイド

```{toctree}
:maxdepth: 1

build
hello-world
parameters
parameter-setting
state
context-manager
faq
applications
```

## リファレンス

```{toctree}
:maxdepth: 1

quickstart
api-reference
```

## 内部情報

```{toctree}
:maxdepth: 1

design
mcp
testing
```

## 付録

```{toctree}
:maxdepth: 1

appendix-sensitivity
```

## 読みすすめ方

1. {doc}`build` — 全サブモジュールビルド + tot 本体
2. {doc}`hello-world` — プレフィックスを使った最短例
3. {doc}`parameters` — プレフィックスルーティング規則
4. {doc}`parameter-setting` — `eq:RR`, `tr:NSMAX` などの設定方法
5. {doc}`state` — 統合出力 + presence flags
6. {doc}`context-manager` — 全モジュール init/finalize の同時管理

困ったときは {doc}`faq` を. API の完全仕様は {doc}`api-reference`.
入力 ↔ 出力の対応関係は {doc}`appendix-sensitivity` へ.

## 他モジュールとの違い (要約)

| | `tr`/`eq`/`fp`/`wr`/`wrx`/`ti` | `tot` |
|---|---|---|
| **対象モジュール** | 1 つのみ | **全部** (orchestrator) |
| **パラメータ名** | `RR`, `BB`, `NSMAX` | `eq:RR`, `tr:NSMAX` (プレフィックス必須) |
| **メモリ消費** | 単独分のみ | 全モジュール合計 |
| **C ABI** | 5–6 関数 | 6 関数 (`set_param_str` 含む) |
| **典型用途** | モジュール単独の解析 | **整合性のある統合シミュレーション** |

## いつ `tot` を使う?

- **時間発展する整合シミュレーション** が必要 (平衡 → 輸送 → 加熱 → 平衡 …)
- 単独モジュールの結果を **動的に他モジュールに渡したい**
- 個別 lib を順次呼ぶコードを書く手間を省きたい

逆に **単独モジュールの方が良い** のは:

- 1 モジュールの単体テスト・ベンチマーク
- メモリを節約したい (tot は全モジュール展開で重い)
- サブモジュール出力の詳細 (eq の `raxis`, fp の `RJT` 等) が必要 — tot
  の State にはこれらは入っていない
