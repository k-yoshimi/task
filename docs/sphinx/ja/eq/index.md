# `eq` — MHD 平衡

```{admonition} 準備中
:class: note

完全な章は後続 PR で整備します. それまでは以下を参照してください:

- Python ラッパ — `python/eqlib/README.md`
- Fortran 設計 — `docs/eq-library/architecture.md`
- MCP サーバ — `python/mcp-servers/eq_mcp/README.md`
```

## 概要

`eq` は TASK の平衡ソルバー (Grad-Shafranov 族) です. TASK パイプラインの
典型的な最初のステップで, その出力 ψ / 磁気面ジオメトリが下流モジュール
すべてに供給されます. PR #164/#165 でライブラリ版 / Python ラッパ /
`validate()` API が揃い, L-6 等価性ゲートを通過済みです.

本章の完全版は `tr` 章の構成 (quickstart → パラメータ → API リファレンス →
FAQ → Fortran 設計 → MCP → 変更履歴) を踏襲する予定です.

## パッケージ docstring (autodoc)

```{eval-rst}
.. automodule:: eqlib
   :no-members:
```
