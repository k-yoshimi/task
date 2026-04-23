# `wr` — 波動 ray tracing

```{admonition} 準備中
:class: note

完全な章は後続 PR で整備します. それまでは以下を参照してください:

- Python ラッパ — `python/wrlib/README.md`
- Fortran 設計 — `docs/wr-library/architecture.md`
- MCP サーバ — `python/mcp-servers/wr_mcp/README.md`
```

## 概要

`wr` は RF 加熱・電流駆動のための幾何光学 ray tracing ソルバーです.
姉妹モジュール `wrx` は `wr` を拡張し beam tracing オプションを追加します.

## パッケージ docstring (autodoc)

```{eval-rst}
.. automodule:: wrlib
   :no-members:
```
