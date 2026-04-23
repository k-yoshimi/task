# TASK プラズマ輸送ライブラリ化プロジェクト マニュアル (日本語, 凍結アーカイブ)

> **⚠️ このマニュアルは凍結アーカイブです.**
>
> 正本のマニュアルは Sphinx 版 (`docs/sphinx/`, 英日バイリンガル) に
> 移行しました. 以後の変更は Sphinx 側へ反映し, 本 `docs/manual/` は
> **2026-04 時点のスナップショット** として凍結します.
>
> - 新しいマニュアル: `docs/sphinx/{en,ja}/`
>   (ビルド方法は `docs/sphinx/README.md` を参照)
> - 本 LaTeX 版は参照用アーカイブとして残置 (PDF も同梱)
> - 新規の章追加・修正は **Sphinx 側のみ** に行なってください
>
> 凍結日: 2026-04-23.

本ディレクトリには, tr / ti / wr / wrx / fp 5 モジュールの
ライブラリ化 (Phase L-0 〜 L-7) をまとめた日本語マニュアル兼報告書が
含まれる.

## 成果物

| ファイル | 内容 |
|----------|------|
| `task-library-manual.tex` | 正本の LaTeX ソース (xeCJK + tcolorbox + TikZ) |
| `task-library-manual.pdf` | 同梱の生成済み PDF (A4, 52 ページ) |

**注意:** 同梱の PDF は xelatex が利用できない環境で matplotlib ベースの
簡易レンダラで生成したため、章タイトルや表レイアウトの整形精度が劣ります
(章タイトルは "はじめに" のように素直に表示、表は崩れる可能性あり)。
本番利用時は下記の推奨ビルドで xelatex から再生成してください。

## 推奨ビルド (TeX Live 利用可能時)

```bash
cd docs/manual
xelatex -interaction=nonstopmode task-library-manual.tex
xelatex -interaction=nonstopmode task-library-manual.tex   # 相互参照
```

TeX Live のインストールは:

```bash
sudo apt-get install -y texlive-xetex texlive-lang-japanese \
     texlive-latex-extra fonts-noto-cjk fonts-noto-cjk-extra \
     fonts-dejavu-core
```

## 使用フォント

- 本文 (和文): Noto Serif CJK JP (Regular / Bold)
- 見出し: Noto Sans CJK JP (Bold)
- コード: Noto Sans Mono CJK JP (TeX 版), Noto Sans CJK JP (matplotlib 版)
- 欧文モノスペース: DejaVu Sans Mono

## 生成物の配置

相互参照などで生成される中間ファイル (`*.aux`, `*.log`, `*.toc`,
`*.out`, `*.fls`, `*.fdb_latexmk`, `*.synctex.gz`) は
リポジトリ root の `.gitignore` で除外する.
