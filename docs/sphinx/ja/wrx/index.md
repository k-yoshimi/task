# `wrx` — 波動 ray tracing (拡張版)

```{admonition} 準備中
:class: note

完全な章は後続 PR で整備します. それまでは以下を参照してください:

- Python ラッパ — `python/wrxlib/README.md`
- Fortran 設計 — `docs/wrx-library/architecture.md`
- MCP サーバ — `python/mcp-servers/wrx_mcp/README.md`
```

## 概要

`wrx` は `wr` の ray tracing ソルバーに beam tracing オプションを加えた
拡張モジュールです. {doc}`../common/architecture` の 5 関数 C ABI に
従い, Python ラッパ (`wrxlib`) が主要な入口となります.

## パッケージ docstring (autodoc)

```{eval-rst}
.. automodule:: wrxlib
   :no-members:
```
