# TASK プラズマライブラリ マニュアル

TASK 系プラズマ物理モジュール群 (`lib{eq,tr,ti,fp,wr,wrx,tot}api.so`) と,
それらを呼び出す薄い `ctypes` ベース Python ラッパ
(`python/{eq,tr,ti,fp,wr,wrx,tot}lib`) のユーザマニュアルです.

このマニュアルは英語・日本語の 2 ツリーで並行して提供されます. 本ツリーは
日本語版で, 英語版は `../en/` 以下にあります. 両ツリーの同期は reviewer
ディスシプリンで維持します — 詳しくは `docs/sphinx/README.md` を参照.

```{note}
本 Sphinx マニュアルは `docs/manual/task-library-manual.tex` の LaTeX 文書を
正本の座から置き換えるものです. LaTeX 版は 2026-04 時点で凍結し, 以降の
変更は本 Sphinx 側に反映します.
```

## 読者対象

本マニュアルは, Python または C ABI を通じて TASK モジュール群を
プログラムから呼び出したい研究者・エンジニアを対象とします. Python と
プラズマ物理用語に慣れていれば十分で, 旧来の `tr2` や対話メニューの
経験は不要です.

## 目次

```{toctree}
:maxdepth: 2
:caption: 基礎

common/architecture
```

```{toctree}
:maxdepth: 2
:caption: 各モジュール

tr/index
eq/index
ti/index
fp/index
wr/index
wrx/index
tot/index
```

## 現在の整備状況

| 章 | 状態 |
|---|---|
| 共通アーキテクチャ | LaTeX Ch.2 から完全移植 |
| `tr` | 完全移植 + autodoc + クイックスタート notebook |
| `eq` / `ti` / `fp` / `wr` / `wrx` / `tot` | placeholder (後続 PR で内容を充実) |

## 索引

* {ref}`genindex`
* {ref}`modindex`
