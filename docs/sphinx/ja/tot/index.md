# `tot` — オーケストレータ

```{admonition} 準備中
:class: note

完全な章は後続 PR で整備します. それまでは以下を参照してください:

- Python ラッパ — `python/totlib/README.md`
- Fortran 設計 — `docs/tot-library/architecture.md`
- MCP サーバ — `python/mcp-servers/tot_mcp/README.md`
```

## 概要

`tot` は `eq` → `tr` / `ti` / `fp` / `wr` / `wrx` をまたぐ実行を構成する
オーケストレータです. 名前空間プレフィックス付きパラメータ辞書 (例:
`eq:BB`, `tr:NSMAX`) を用いることで, 全モジュールのパラメータを一つの
Python dict や TOML ファイルから設定できます.

## パッケージ docstring (autodoc)

```{eval-rst}
.. automodule:: totlib
   :no-members:
```
