# 入力パラメータの指定方法

`tot` は他モジュールと違って **パラメータ名にプレフィックスを必ず付け**
ます. これにより内部で適切なサブモジュールにルーティングします.

## 方法 A — スカラー (`set_param` / `set_params`)

```python
tot.set_param("eq:RR", 6.5)         # eq の RR
tot.set_param("tr:NSMAX", 2)        # tr の NSMAX
```

または `set_params` で dict 形式:

```python
tot.set_params({
    "eq:RR": 6.5,
    "eq:BB": 5.3,
    "tr:NSMAX": 2,
    "tr:NTMAX": 100,
    "wr:RF": 170e9,
})
```

## プレフィックス一覧

`tot/tot_param_registry.f90` の `SELECT CASE` でルーティングされる
プレフィックス:

| プレフィックス | 渡されるサブモジュール | 例 |
|---|---|---|
| `eq:` | `eq` (MHD 平衡) | `eq:RR`, `eq:BB`, `eq:KNAMEQ` |
| `tr:` | `tr` (1D 輸送) | `tr:NSMAX`, `tr:DT`, `tr:MDLKAI` |
| `ti:` | `ti` (統合輸送) | `ti:MODEL_NB`, `ti:MODEL_KAI` |
| `fp:` | `fp` (Fokker-Planck) | `fp:NPMAX`, `fp:NTHMAX` |
| `wr:` | `wr` (レイトレース) | `wr:RF`, `wr:RPI` |
| `wrx:` | `wrx` (beam tracing) | `wrx:RFIN[1]`, `wrx:RBRADAIN[1]` |

## 方法 B — 配列要素

サブモジュール側の配列パラメータはプレフィックス + 添字で指定します.

```python
tot.set_param("tr:PN[1]", 1.0)       # tr の PN[1]
tot.set_param("eq:PSIB[0]", 2.0)     # eq の PSIB[0] (0-origin)
tot.set_param("wrx:RFIN[1]", 170e9)  # wrx の RFIN[1]
```

## 方法 C — 文字列パラメータ (`set_param_str`)

`KNAMEQ` などの文字列も同じプレフィックス規則です. tot が文字列を渡すのは
`eq:` と `tr:` だけです.

```python
tot.set_param_str("eq:KNAMEQ", "eqdata.ITER01")
tot.set_param_str("tr:KNAMEQ", "eqdata.ITER01")  # tr も同じファイル参照
```

`fp:KNAMEQ` はここでは拒否されます. `totlib.TotPipeline.set_param` で設定して
ください (`tot_mcp` では `run_pipeline` の `params`). fp が読むのは `pl` の
`KNAMEQ` で, これは eq のものと同じです. 両者が `pl` を 1 つ共有する場合
(mono イメージなど) は, `eq:KNAMEQ` が fp のファイルも決めます.

## 事前検証 (`validate`)

```{important}
`tot` は現時点で `validate()` API を実装していません. パラメータ違反は
`set_param` 時の即時エラー (`TotlibInvalidParamError`), 計算失敗は
`run()` 時の `TotlibCalculationFailedError` で検出します.
```

## 設定パターンの典型例

### 平衡 + 輸送 + 加熱の最小セット

```python
tot.set_params({
    # 平衡
    "eq:RR": 6.2, "eq:RA": 2.0, "eq:BB": 5.3, "eq:RIP": 15.0,
    # 輸送
    "tr:NSMAX": 2,
    "tr:DT": 0.01, "tr:NTMAX": 100,
    "tr:MDLKAI": 31,            # CDBM
    # NBI 加熱 (tr 経由)
    "tr:MDLNB": 1,
})
```

### EQDSK 平衡 + ECRH レイトレース

```python
tot.set_param("eq:MODELG", 3)
tot.set_param_str("eq:KNAMEQ", "eqdata.ITER01")
tot.set_params({
    "tr:NSMAX": 2,
    "wr:RF": 170e9,
    "wr:RPI": 8.5,
    "wr:ZPI": 1.5,
})
tot.run(ntmax=10)
```

### 高速イオン解析 (fp 統合)

```python
tot.set_params({
    "eq:RR": 6.2, "eq:BB": 5.3, "eq:RIP": 15.0,
    "tr:NSMAX": 2, "tr:MDLNB": 1,
    "fp:NSAMAX": 2,                  # fp の active species
    "fp:NPMAX": 100, "fp:NTHMAX": 50, # fp の 5D グリッド
})
tot.run(ntmax=50)
```

## プレフィックスを忘れたら?

```python
tot.set_param("RR", 6.5)            # ← TotlibInvalidParamError
```

`tot` は **プレフィックス無しの名前を受け付けません**. 必ず `eq:RR`,
`tr:RR` などと書いてください.
