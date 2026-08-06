# MCP サーバ (`tr_mcp`)

`tr_mcp` は TASK/TR を **Claude Desktop / Claude Code / Cursor などの LLM
クライアント** から直接操作できるようにする, **Model Context Protocol
(MCP)** 対応のサーバです. 内部では `python/trlib` (ctypes ラッパ) を薄く
被せた構造で, `libtrapi.so` を LLM の「道具箱」として差し出すイメージに
なります.

```{admonition} このページの位置付け
:class: note

入門者向けの完全ガイドは `python/mcp-servers/tr_mcp/README.md` にあります.
本ページはその要約 + 簡単な使い方リファレンスです.
```

## MCP とは

MCP (Model Context Protocol) は Anthropic が策定した **「LLM と外部ツール
をつなぐ標準プロトコル」** です. 簡略化した構造:

```text
┌────────────────┐     JSON-RPC      ┌─────────────────────┐
│  LLM client    │ ─────────────────▶│   MCP サーバ         │
│ (Claude 等)    │◀───────────────── │ (この tr_mcp)       │
└────────────────┘                   │   init/run/...      │
                                     └────────┬────────────┘
                                              │ ctypes
                                              ▼
                                     ┌─────────────────────┐
                                     │  tr/libtrapi.so     │
                                     │  (Fortran backend)  │
                                     └─────────────────────┘
```

ポイント:

- LLM 側はツールを発見して呼ぶだけで OK. TR や Fortran の知識不要.
- サーバ側は **stdio JSON-RPC** で待ち受け. ネットワーク設定不要.
- ツールには **型付きスキーマ** が付くので LLM が引数を誤りにくい.

## 前提条件

1. **Python 3.10 以上**
2. **`libtrapi.so` がビルド済み** (`make -C tr libtrapi.so`)
3. **`mcp` パッケージ** (`pip install 'mcp>=0.9,<2'`)

## インストール

```bash
cd python/mcp-servers/tr_mcp
pip install -e .
```

これで `tr-mcp` コマンド と `python -m tr_mcp.server` が使えるようになります.

`trlib` 本体はリポジトリ同梱の pure-Python パッケージで, `PYTHONPATH` に
`<repo>/python` を通しておけばロードされます.

## 動作確認

### コマンドが通ることの確認

```bash
python -m tr_mcp.server --help
```

### 登録ツール一覧の表示

```bash
python -m tr_mcp.server --print-tools
```

9 ツールが並びます (詳細は下記の「提供ツール一覧」参照).

### 環境ヘルスチェック

```bash
tr-mcp doctor
```

`mcp` パッケージ, `tr_mcp` / `trlib` の import 可否, `libtrapi.so` の有無,
推奨設定ファイルの場所を JSON で返します.

### Python から直接叩く

`handle_*` プレフィックスの関数は MCP 経由でもテストでも共通で使えます.

```python
>>> from tr_mcp.server import handle_init, handle_run, handle_get_state
>>> handle_init()
'tr library initialized'
>>> handle_run(0)
'advanced 0 time step(s)'
>>> state = handle_get_state()
>>> state['NT'], state['NRMAX'], state['NSMAX']
(0, 50, 2)
```

## LLM クライアントへの登録

### Claude Desktop

設定ファイル (`claude_desktop_config.json`) を編集. パスは OS 別:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Linux: `~/.config/claude-desktop/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "task-tr": {
      "command": "python",
      "args": ["-m", "tr_mcp.server"],
      "env": {
        "PYTHONPATH": "/absolute/path/to/task/python",
        "TRLIB_PATH": "/absolute/path/to/task/tr/libtrapi.so"
      }
    }
  }
}
```

保存して Claude Desktop を再起動すると, ツール一覧に `task-tr` が並びます.

### Claude Code

```bash
claude mcp add task-tr \
  --env PYTHONPATH=/absolute/path/to/task/python \
  --env TRLIB_PATH=/absolute/path/to/task/tr/libtrapi.so \
  -- python -m tr_mcp.server
```

または `tr-mcp install` で `.mcp.json` を自動生成:

```bash
tr-mcp install --client claude-code --scope project
```

### Cursor / VS Code

Cursor のプロジェクト設定は `.cursor/mcp.json`, グローバル設定は
`~/.cursor/mcp.json`. `tr-mcp install` で自動更新できます.

```bash
tr-mcp install --client cursor --scope project
tr-mcp install --client cursor --scope user
```

### スニペット印字のみ (手で貼りたい場合)

```bash
tr-mcp print-config --client cursor --scope project
```

設定ファイルを変更せず, 標準出力に JSON スニペットだけ表示します.

## 提供ツール一覧

`tr_mcp` は 9 個のツールを公開します.

| ツール | 目的 | 主な引数 |
|---|---|---|
| `init` | ライブラリ初期化 (`tr_init`) | なし |
| `set_param` | 単一パラメータ設定 | `name`, `value` (配列は `NAME[i]`) |
| `set_params` | まとめて設定 (scalar / list / dict) | `params` |
| `run` | 時間ステップ進行 (`tr_run`) | `ntmax` (default=1) |
| `get_state` | 現在の状態取得 (`tr_get_state`) | なし |
| `finalize` | リソース解放 (`tr_finalize`) | なし |
| `describe_parameters` | パラメータ一覧・型・説明 (LLM 向けのインスペクション) | なし |
| `describe_state_schema` | `get_state` 戻り値の JSON schema | なし |
| `run_and_get_state` | `init + set + run + get_state` を一括実行 | `params`, `ntmax` |

`describe_parameters` と `describe_state_schema` の 2 つは **LLM が
パラメータ名を間違えないため** に存在します. LLM はまずこれを呼んで
名前と型を確認してから, `set_params` などを呼ぶ流れになります.

## 使い方の例

LLM クライアントに登録したら, 自然言語で対話できます.

### 例 1: 最短

> TR を初期化して, 1 ステップ走らせて, 現在の時刻 T と plasma current AJT
> を教えて.

LLM は内部で `init → run(1) → get_state` の順にツールを呼び, `scalars.T`
と `scalars.AJT` を返します.

### 例 2: パラメータを変えて実行

> major radius RR を 6.5 にして toroidal field BB を 5.3 にしてから
> 10 ステップ実行して, safety factor Q0 がどう変化したか教えて.

内部呼び出しは:

```python
run_and_get_state(params={"RR": 6.5, "BB": 5.3}, ntmax=10)
```

### 例 3: パラメータスキャン (sweep)

> RR を 6.0, 6.5, 7.0 の 3 点で走らせて, それぞれ 20 ステップ後の
> BETAN を比較して.

LLM は 3 回の `run_and_get_state` を呼んで結果を表組みします.

### 例 4: パラメータの絞り込み

> TR で設定できるパラメータを一覧にして, 輸送モデルに関係するものだけ教えて.

LLM は `describe_parameters` を呼び, `group == "transport"` を抽出して
返します.

## 使用シナリオ — もう少し深い使い方

「ツール一覧」だけでは MCP の実用イメージが掴みにくいので, 典型的な
解析フローを 2 つ詳しく見ます.

### シナリオ A: 装置パラメータを変えてエネルギーバランスを見る

ユーザのプロンプト:

> ITER 想定 (RR=6.2, BB=5.3, RIP=15) で 100 ステップ走らせて, 蓄積エネルギー
> WPT と規格化 β (BETAN) を教えて. それから RIP を 12 と 18 でも比較して.

LLM が内部で行うツール呼び出し:

```text
1. run_and_get_state(params={RR=6.2, BB=5.3, RIP=15.0, NSMAX=2}, ntmax=100)
   → state.scalars["WPT"], state.scalars["BETAN"] を取得
2. run_and_get_state(params={RR=6.2, BB=5.3, RIP=12.0, NSMAX=2}, ntmax=100)
   (各 run の前に init/finalize は MCP サーバ側で自動)
3. run_and_get_state(params={RR=6.2, BB=5.3, RIP=18.0, NSMAX=2}, ntmax=100)
4. 結果を表組みで返す:
     | RIP   | WPT   | BETAN |
     |-------|-------|-------|
     | 12 MA | ...   | ...   |
     | 15 MA | ...   | ...   |
     | 18 MA | ...   | ...   |
```

ポイント:

- LLM は `describe_parameters` で名前を確認してから `run_and_get_state` を
  発行するので, パラメータ名のタイポが起こりにくい
- 結果がプロセス間で残らないため, 各 `run_and_get_state` は独立した
  クリーン状態でスタート
- 物理的考察 ({doc}`appendix-sensitivity` 参照: `RIP↑` で `BETAN↓` の傾向)
  まで合わせて書いてもらうと解析レポートに近い形になる

### シナリオ B: validate でエラーを LLM に直してもらう

ユーザのプロンプト:

> MODELG=3 で `eqdata.MISSING` を読ませて 10 ステップ走らせて. エラーが
> 出たら適切なファイルを推測して直して.

LLM の動作:

```text
1. run_and_get_state(params={MODELG: 3, ...}, string_params={KNAMEQ: "eqdata.MISSING"})
   → エラー (FILE_MISSING)
2. validate を呼び diag を確認
3. 既知の eqdata ファイル名 (eqdata.ITER01, eqdata.JET, ...) を提案
4. ユーザに確認を取るか, 自動的に最有力候補で再実行
```

LLM が「自動修正をどこまで踏み込むか」は LLM の指示次第:

- **安全寄り**: `validate` だけ呼んで結果報告 → ユーザに任せる
- **攻め寄り**: 推測で再実行も可能

このパターンは Python ラッパー側 ({doc}`applications` の §3 validate 駆動
セットアップ) を LLM に呼んでもらう形にも展開できます.

## アーキテクチャ的な注意点

### シングルトン制約

TR の Fortran 側は COMMON ブロックで状態を持つので, **1 MCP プロセス =
1 TR インスタンス** が原則です. 複数同時に走らせたい場合は別プロセス
(別 Python プロセス) で立ち上げてください ({doc}`faq` Q4 と同じ理由).

### `eqdata` ファイルへの依存

`MODELG=3` で `KNAMEQ` を指定する場合, MCP サーバの **カレントディレクトリ**
にそのファイルがある必要があります. Claude Desktop から起動するときは
`cwd` を環境変数で固定するか, 絶対パスでファイルを指定してください.

### ログ・デバッグ

MCP サーバの標準エラー出力が LLM クライアントに渡ります.

- Claude Desktop: 開発者ツール相当のログビューア
- Claude Code: 実行ターミナル

エラーが出たら `tr-mcp doctor` で環境を再確認するのが第一歩です.

## トラブルシューティング (要約)

| 症状 | 対処 |
|---|---|
| `libtrapi.so not found` | `make -C tr libtrapi.so` 後, `TRLIB_PATH` を絶対パスで設定 |
| `ModuleNotFoundError: trlib` | `PYTHONPATH` にリポジトリ `python/` を追加 |
| `ModuleNotFoundError: mcp` | `pip install 'mcp>=0.9,<2'`. 仮想環境を確認 |
| `invalid parameter` | `describe_parameters` で名前を確認 (大小区別あり, 1-origin) |
| `calculation failed` | `NSMAX`, `PN`, `PT`, `DT` の整合性. `finalize` → `init` でリセット |

詳細は `python/mcp-servers/tr_mcp/README.md` の §8 FAQ を参照してください.

## 参考資料

- **MCP 仕様**: <https://modelcontextprotocol.io/>
- **Python MCP SDK**: <https://github.com/modelcontextprotocol/python-sdk>
- **完全ガイド**: `python/mcp-servers/tr_mcp/README.md` (本ページの 5 倍ほど詳細)
- **`trlib` README**: `python/trlib/README.md`
