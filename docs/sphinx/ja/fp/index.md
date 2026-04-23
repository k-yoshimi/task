# `fp` — Fokker-Planck

```{admonition} 準備中
:class: note

完全な章は後続 PR で整備します. それまでは以下を参照してください:

- Python ラッパ — `python/fplib/README.md`
- Fortran 設計 — `docs/fp-library/architecture.md`
- MCP サーバ — `python/mcp-servers/fp_mcp/README.md`
```

## 概要

`fp` は高速イオン・高エネルギー粒子の分布関数を解く TASK の Fokker-Planck
ソルバーです. `eq` から平衡・磁気面データを受け取り, 単独でも, `tot` に
組み込まれた結合計算の一部としても走ります.

## パッケージ docstring (autodoc)

```{eval-rst}
.. automodule:: fplib
   :no-members:
```
