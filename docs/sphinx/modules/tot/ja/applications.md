# ライブラリの応用例 (Python ラッパー)

`Tot` は他の 5 モジュール (eq / tr / ti / fp / wr) を 1 プロセス内で
起動するオーケストレータです. ここでは典型的な 3 パターンを示します.

```{admonition} L-6 段階の制約
:class: warning

現在の `Tot` (Phase L-6) は **transport 部分 (TR) のみ実際に時間発展**
させます. `eq` / `ti` / `fp` / `wr` は同じプロセス内で初期化されます
が, `tot.run()` ではそれらの計算は呼ばれません. 言い換えると:

- `tot.set_param("eq:RR", 6.5)` のような **namespaced 設定は 5
  モジュール全部に分配される**.
- `tot.run(ntmax)` は **`tr_api_run(ntmax)` のみを呼ぶ**.
- `tot.get_state()` は **TR の state を集約**して返す
  (`state.tr_present == 1`, `state.ti_present == 0`, ...).

L-7a で `fp` → `tr` (driven current scalar) の coupling が `TotPipeline`
として実装済みです (本ページ §3 参照). `wr` → `tr` (波加熱沈着 profile),
`eq` → `tr` (q-profile) 等の profile-level coupling は L-7b 以降で
BPSD broker 経由の実装が予定されています.
```

```{admonition} このページの位置付け
:class: note

ここで紹介するのは **`totlib` を Python から使う応用パターン** です.
LLM クライアントから自然言語で操作するシナリオは {doc}`mcp` を
参照してください.
```

---

## 1. 統合 init + namespaced セットアップ

`Tot()` は 1 回の `__init__` で 4 つのサブモジュール (tr / ti / fp / wr)
を上げます. 各モジュール用パラメータは `<ns>:<name>` 形式の prefix で
区別:

```python
from totlib import Tot


with Tot() as tot:
    # eq の geometry をセット (各サブモジュールに配信)
    tot.set_param("eq:RR", 6.2)
    tot.set_param("eq:RA", 2.0)
    tot.set_param("eq:BB", 5.3)
    tot.set_param("eq:RIP", 15.0)

    # tr の transport 設定
    tot.set_param("tr:RR", 6.2)
    tot.set_param("tr:RA", 2.0)
    tot.set_param("tr:BB", 5.3)
    tot.set_param("tr:NSMAX", 2)
    tot.set_param("tr:DT", 0.01)
    tot.set_param("tr:NTMAX", 100)

    # 1 ステップだけ進めて state を確認
    tot.run(1)
    state = tot.get_state()
    print(f"tr_present={state.tr_present}, T={state.scalars['T']:.3f}s")
```

期待される出力:

```text
tr_present=1, T=0.010s
```

利用可能な prefix:

| Prefix | 対応モジュール | 備考 |
|---|---|---|
| `eq:` | equilibrium | 解析/EQDSK 共用 geometry |
| `tr:` | transport | 1D 拡散方程式 |
| `ti:` | ion transport | 重イオン輸送 (使用するときのみ) |
| `fp:` | Fokker-Planck | 速度空間分布 |
| `wr:` / `wrx:` | ray tracing | 波の伝搬 |

`describe_parameters` (各モジュール MCP) で名前空間ごとの定義を
列挙できます ({doc}`mcp` 参照).

### 拡張案

- 装置プリセット (ITER / JET / DIIID) を 1 つの dict にまとめて
  `_apply_namespaced(tot, preset)` で一括展開
- 「同じ `RR/RA/BB` を eq と tr と wr に配るのは冗長」と感じたら,
  `geometry_from(preset)` で展開する helper を作るとよい

---

## 2. transport advance のラッピング

L-6 段階では `tot.run(ntmax)` は **TR の transport 計算のみ** を ntmax
ステップ進めます. 失敗時のハンドリングは tr モジュールの applications
ページ (`docs/sphinx/modules/tr/ja/applications.md`) の `StableTrRunner`
と同形になります.

```python
from totlib import Tot
from totlib.errors import TotlibCalculationFailedError


def transport_step(tot: Tot, *, ntmax: int = 100) -> dict:
    """tot 経由で transport を進めて主要 scalar を返す."""
    try:
        tot.run(ntmax)
        state = tot.get_state()
        return {
            "tr_present": bool(state.tr_present),
            "T":     state.scalars["T"],
            "WPT":   state.scalars["WPT"],
            "BETAN": state.scalars["BETAN"],
            "TAUE1": state.scalars["TAUE1"],
            "Q0":    state.scalars["Q0"],
        }
    except TotlibCalculationFailedError as e:
        return {"error": repr(e)}


with Tot() as tot:
    tot.set_param("tr:RR", 6.2)
    tot.set_param("tr:RA", 2.0)
    tot.set_param("tr:BB", 5.3)
    tot.set_param("tr:NSMAX", 2)
    tot.set_param("tr:DT", 0.01)
    tot.set_param("tr:NTMAX", 100)
    out = transport_step(tot, ntmax=10)
    for k, v in out.items():
        if isinstance(v, float):
            print(f"  {k} = {v:.4g}")
        else:
            print(f"  {k} = {v}")
```

期待される出力:

```text
  tr_present = True
  T = 0.1
  WPT = 10.01
  BETAN = 0.2872
  TAUE1 = 11.42
  Q0 = 2.519
```

### 拡張案

- `state.scalars` 全 14 項目 (`T, WPT, AJT, Q0, BETA0, BETAP0, BETAA,
  BETAN, TAUE1, TAUE2, ZEFF0, ALI, RQ1, AJRFT`) をすべて返すよう拡張
- 各 ntmax ごとに state.scalars をリストに蓄積して時系列分析

---

## 3. 複数モジュール coupling pipeline (L-7a)

L-7a で `TotPipeline` (Python 側オーケストレータ) が導入され,
`fp` → `tr` のスカラー coupling (driven current) が動作するように
なりました. `libtotapi.so` を経由せず, 既存の `Fplib` / `Trlib` 等の
モジュール wrapper を組み合わせて 1 つの pipeline として実行します.

```python
from totlib import TotPipeline

with TotPipeline() as tot:
    # fp 側 fixture (active drive)
    tot.set_param("fp:NSAMAX", 2)
    tot.set_param("fp:E0", 0.001)        # 誘導電場 [V/m]

    # tr 側 fixture (compute_rjt_volint が tr:RR / tr:RA を参照)
    tot.set_param("tr:RR", 6.2)
    tot.set_param("tr:RA", 2.0)
    tot.set_param("tr:BB", 5.3)
    tot.set_param("tr:NSMAX", 2)

    result = tot.run_pipeline([
        ("fp", {"ntmax": 5}),
        ("tr", {"ntmax": 1}),
    ])
    tr_scalars = result.last("tr").scalars
    print(f"AJT={tr_scalars['AJT']}, coupling={result.last('tr').coupling_applied}")
```

`run_pipeline` は隣接ステップ間で `COUPLING_RULES` を自動適用します.
L-7a では 1 件 (`fp → tr` の `compute_rjt_volint(state) → tr.PLHCD`)
だけが登録されています.

```{warning}
**L-7a スケルトン カップリング:** sink param `tr.PLHCD` は **無次元
multiplier** です (R3 outcome: `tr_param_registry.f90` に `PNBCD` 未登録
のため代替). L-7a は **API 配線の妥当性検証**が目的で, 物理的忠実度は
L-7b で `EXTERNAL_DRIVEN_I` のような専用スカラーが Fortran 側に追加
された時点で対応します. profile-level な coupling (波加熱沈着 profile,
平衡 q-profile 等) も L-7b 以降で BPSD broker 経由で実装されます.
等価性テスト (`python/totlib/tests/test_pipeline_equiv.py`) は
1e-10 の許容誤差で hand-written と pipeline-driven が一致することを
確認しています.
```

mid-pipeline で例外が発生した場合は `TotPipelineRunError` が raise され,
`partial_result` 属性に成功済ステップの snapshot が保持されます (途中まで
の解析結果を捨てずに済みます).

### MCP からの呼び出し

`tot_mcp` サーバには **`run_pipeline` MCP tool** が追加済みです
(`python/mcp-servers/tot_mcp/README.md §7.1` 参照). LLM クライアントから
は次の JSON で同じ pipeline を実行できます:

```json
{
  "steps": [
    {"module": "fp", "kwargs": {"ntmax": 5}},
    {"module": "tr", "kwargs": {"ntmax": 1}}
  ],
  "params": {"fp:NSAMAX": 2, "fp:E0": 0.001, "tr:RR": 6.2, "tr:RA": 2.0}
}
```

呼び出しごとに既存 `STATE` (legacy `Tot`) と直前の pipeline は force-close
されるため, 連続呼び出しでも各実行は独立した clean state から始まります.

---

## 組合せパターン

| 組合せ | 効果 |
|---|---|
| **namespaced setup + transport_step** | `Tot` 1 つで TR ベースの定常解析 (eq の geometry も同時に init される) |
| **transport_step + sweep** | RR × BB のような格子スキャンで, TR transport の感度を評価 |
| **TotPipeline (L-7a)** | `fp → tr` driven current のスカラー coupling を 1 PR で完結. profile coupling は L-7b 以降 |

各サブモジュール単体の応用パターンは各モジュールの `applications.md`
(例: `docs/sphinx/modules/tr/ja/applications.md`,
`docs/sphinx/modules/eq/ja/applications.md` 等) を参照. `Tot` 経由でも
同等の prefix 付きパラメータでセットアップできます.
