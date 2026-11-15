# サポートされている入力パラメータ

`tot/tot_param_registry.f90` は **9 個のプレフィックス CASE** だけを持ち,
個別パラメータは各サブモジュールに **ルーティング** します. つまり
`tot` 自身が直接持つパラメータはなく, eq/tr/ti/fp/wr/wrx の **すべての
パラメータがプレフィックス付きで使えます**.

## 必須・推奨パラメータ

### 必須

`tot` 自体には必須パラメータはありません. 各サブモジュールの必須要件を
プレフィックスを付けて満たします.

例: `MODELG=3` で EQDSK 経由なら以下が必須:

```python
tot.set_param("eq:MODELG", 3)
tot.set_param_str("eq:KNAMEQ", "eqdata.ITER01")
```

### 強く推奨

実用シミュレーションでは少なくとも以下を設定:

| プレフィックス | パラメータ | 推奨値 (ITER 想定) |
|---|---|---|
| `eq:` | `RR`, `RA`, `BB`, `RIP` | 6.2 m, 2.0 m, 5.3 T, 15.0 MA |
| `tr:` | `NSMAX`, `DT`, `NTMAX` | 2, 0.01 s, 100 |

## ルーティング規則

`tot` の `SELECT CASE` は冒頭部分のキー (`:` 前) でモジュールを判定します.

| キー (プレフィックス) | ルーティング先 | カバーするパラメータ範囲 |
|---|---|---|
| `eq:`  | `eq_param_set` | eq の全 94 パラメータ (`docs/sphinx/modules/eq/ja/parameters.md` 参照) |
| `tr:`  | `tr_param_set` | tr の全 ~30 パラメータ |
| `ti:`  | `ti_param_set` | ti の全 77 パラメータ |
| `fp:`  | `fp_param_set` | fp の全 55 パラメータ |
| `wr:`  | `wr_param_set` | wr の全 103 パラメータ |
| `wrx:` | `wrx_param_set` | wrx の全 70 パラメータ |

各サブモジュールの完全パラメータリストは, それぞれの parameters.md を
参照してください.

## 文字列パラメータ

`set_param_str` も同じプレフィックス規則です. ただし tot が文字列を
渡すのは `eq:` と `tr:` の名前空間だけです (`tot/tot_param_registry.f90`).
`fp:`, `ti:`, `wr:`, `wrx:` では `TotlibInvalidParamError` になります.

```python
tot.set_param_str("eq:KNAMEQ", "eqdata.ITER01")
tot.set_param_str("tr:KNAMEQ", "eqdata.ITER01")
```

`fp:KNAMEQ` は `totlib.TotPipeline.set_param("fp:KNAMEQ", ...)` で設定します.
これは fplib 自身の `set_param_str` に渡されます (`tot_mcp` では
`run_pipeline` の `params` に文字列値として渡します). `ti`, `wr`, `wrx` には
文字列パラメータがありません. tr は自身の `KNAMEQ` を持ちます. eq の
`KNAMEQ` は `pl` (`plcomm`) のもので, fp もこれを読みます. eq と fp が
`pl` を 1 つ共有する場合 (mono イメージ `libtotapi_mono.so` など) は,
`eq:KNAMEQ` が fp の読むファイルも決めます.

## 推奨ワークフロー

```python
from totlib import Tot

with Tot() as tot:
    # 1. 共通: 装置パラメータ (eq に渡す)
    tot.set_params({
        "eq:RR": 6.2, "eq:RA": 2.0, "eq:BB": 5.3, "eq:RIP": 15.0,
    })

    # 2. 輸送計算 (tr)
    tot.set_params({
        "tr:NSMAX": 2,
        "tr:DT": 0.01, "tr:NTMAX": 100,
        "tr:MDLKAI": 31,           # CDBM
    })

    # 3. (オプション) ECRH レイトレース
    tot.set_params({
        "wr:RF": 170e9,
        "wr:RPI": 8.5, "wr:ZPI": 0.0,
    })

    # 4. (オプション) 高速イオン解析
    tot.set_params({
        "fp:NSAMAX": 1,
        "fp:NPMAX": 50, "fp:NTHMAX": 25,
    })

    # 5. 全部結合して時間発展
    tot.run(ntmax=10)
    state = tot.get_state()
```

## どのプレフィックスが使えるか

`Tot()` で初期化されたサブモジュールでないと使えません. 通常は全部
init されますが, 個別の present フラグは `state.<mod>_present` で確認:

```python
state = tot.get_state()
print("tr ok:" , state.tr_present)
print("fp ok:" , state.fp_present)
print("wr ok:" , state.wr_present)
```

`*_present = 0` のモジュールに対するパラメータ設定はエラーになります.

## 各モジュールのパラメータ詳細

詳細は各モジュールの parameters ページを参照してください:

- `tr` のパラメータ: `docs/sphinx/modules/tr/ja/parameters.md`
- `eq` のパラメータ: `docs/sphinx/modules/eq/ja/parameters.md`
- `ti` のパラメータ: `docs/sphinx/modules/ti/ja/parameters.md`
- `fp` のパラメータ: `docs/sphinx/modules/fp/ja/parameters.md`
- `wr` のパラメータ: `docs/sphinx/modules/wr/ja/parameters.md`
- `wrx` のパラメータ: `docs/sphinx/modules/wrx/ja/parameters.md`
