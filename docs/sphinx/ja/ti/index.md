# `ti` — 統合輸送

```{admonition} 準備中
:class: note

完全な章は後続 PR で整備します. それまでは以下を参照してください:

- Python ラッパ — `python/tilib/README.md`
- Fortran 設計 — `docs/ti-library/architecture.md`
- MCP サーバ — `python/mcp-servers/ti_mcp/README.md`
```

## 概要

`ti` は輸送ソルバー (`tr`) と補助物理モデルを結合する統合輸送インタ
フェースです. {doc}`../common/architecture` 章で説明する 5 関数 C ABI
に従います.

## パッケージ docstring (autodoc)

```{eval-rst}
.. automodule:: tilib
   :no-members:
```
