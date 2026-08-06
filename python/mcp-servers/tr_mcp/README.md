# tr_mcp — TASK/TR 用 MCP サーバ

`tr_mcp` は、TASK プロジェクトのプラズマ輸送コード TR を **Claude Desktop / Claude Code / Cursor といった LLM クライアント**から直接操作できるようにする、Model Context Protocol (MCP) 対応のサーバです。内部では `python/trlib` (ctypes ラッパ) を薄く被せており、`libtrapi.so` を LLM の「道具箱」として差し出すイメージになります。

本ドキュメントは MCP や TR が初めての方向けに書かれています。手順に沿って進めていけば、Claude のチャット欄で「TR を RR=6.5 で初期化して 10 ステップ回して結果を教えて」とお願いするだけで、TR を動かして結果を受け取れる状態になります。

---

## 目次

1. [MCP とは何か (超ざっくり)](#1-mcp-とは何か-超ざっくり)
2. [前提条件](#2-前提条件)
3. [インストール](#3-インストール)
4. [動作確認 (smoke test)](#4-動作確認-smoke-test)
5. [Claude Desktop / Claude Code への登録](#5-claude-desktop--claude-code-への登録)
6. [使い方の例](#6-使い方の例)
7. [提供ツール一覧](#7-提供ツール一覧)
8. [FAQ / トラブルシューティング](#8-faq--トラブルシューティング)
9. [参考資料](#9-参考資料)

---

## 1. MCP とは何か (超ざっくり)

MCP (Model Context Protocol) は、Anthropic が策定した **「LLM と外部ツールをつなぐ標準プロトコル」** です。ざっくり次の図のイメージになります。

```
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

ポイントは次の 3 つです。

- LLM 側は「ツール」を発見して呼び出すだけで済みます。TR の中身や Fortran を知らなくても大丈夫です。
- サーバ側は標準入出力 (stdio) で JSON-RPC を待ち受けます。特別なネットワーク設定は不要です。
- 公開するツールには型付きのスキーマが付くので、LLM が引数を誤りにくくなります。

## 2. 前提条件

以下がそろっているか確認してください。

1. **Python 3.10 以上**
2. **TR の共有ライブラリ `libtrapi.so`**  

   リポジトリルートで次を実行してビルドします:

   ```bash
   make -C tr libtrapi.so
   ```

   成功すると `tr/libtrapi.so` が生成されます (Phase L-4 で整備済みです)。

3. **`mcp` パッケージ (Python MCP SDK)**  

   `pip install 'mcp>=0.9,<2'` で入ります。後述の「インストール」手順に同梱しています。

## 3. インストール

### 3.1. リポジトリ取得とライブラリビルド

```bash
git clone <task repo> task
cd task
make -C tr libtrapi.so    # 既に実行済みならスキップで OK
```

### 3.2. MCP サーバのインストール

開発用 (editable) インストールを推奨します。

```bash
cd python/mcp-servers/tr_mcp
pip install -e .
```

これで `tr-mcp` コマンドが使えるようになります。また `python -m tr_mcp.server` でも同じ機能を呼び出せます。

> **Note:** `trlib` 自体はリポジトリ同梱の pure-Python パッケージです。`PYTHONPATH` に `<repo>/python` を通すか、`server.py` が自動で親パッケージを import できるようになっているので追加インストールは不要です。

### 3.3. 仮想環境を使いたい場合 (任意)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e python/mcp-servers/tr_mcp
```

## 4. 動作確認 (smoke test)

### 4.1. ヘルプ表示

まずコマンドが通ることを確認します。

```bash
python -m tr_mcp.server --help
```

使い方と環境変数がずらっと出れば OK です。

### 4.2. 登録ツール一覧の表示

```bash
python -m tr_mcp.server --print-tools
```

以下の 9 ツールが並びます。

```
describe_parameters
describe_state_schema
finalize
get_state
init
run
run_and_get_state
set_param
set_params
```

### 4.3. Python から直接叩く

`libtrapi.so` がビルド済みであれば、Python REPL で次のように動作確認できます。

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

`handle_*` は MCP 経由でも、テストコード内でも共通で使えるプレーンな Python 関数です。

## 5. Claude Desktop / Claude Code への登録

### 5.1. Claude Desktop の場合

設定ファイル (`claude_desktop_config.json`) に次の項目を追加します。

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Linux: `~/.config/claude-desktop/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

```jsonc
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

保存して Claude Desktop を再起動すると、ツール一覧に `task-tr` が並びます。

### 5.2. Claude Code の場合

CLI から追加できます。

```bash
claude mcp add task-tr -- python -m tr_mcp.server
```

環境変数を渡したい場合は `--env` を使います。

```bash
claude mcp add task-tr \
  --env PYTHONPATH=/absolute/path/to/task/python \
  --env TRLIB_PATH=/absolute/path/to/task/tr/libtrapi.so \
  -- python -m tr_mcp.server
```

### 5.3. Cursor / VS Code など

いずれも MCP 対応エディタであれば、`command` と `args` を同じ要領で書けば動きます。

## 6. 使い方の例

登録が済んだら、Claude にそのまま話しかけてください。以下はチャットプロンプトの例です。

### 6.1. いちばん簡単な例

```
TR を初期化して、1 ステップ走らせて、現在の時刻 T と plasma current AJT を教えて。
```

LLM は `init → run(1) → get_state` の順にツールを呼び、`scalars.T` と `scalars.AJT` の値を返してくれます。

### 6.2. パラメータを変えて実行

```
major radius RR を 6.5 にして toroidal field BB を 5.3 にしてから 10 ステップ実行して、
safety factor Q0 がどう変化したか教えて。
```

LLM は内部で

```python
run_and_get_state(params={"RR": 6.5, "BB": 5.3}, ntmax=10)
```

のような呼び出しに変換してくれます。

### 6.3. パラメータ探索 (sweep)

```
RR を 6.0, 6.5, 7.0 の 3 点で走らせて、それぞれ 20 ステップ後の BETAN を比較して。
```

### 6.4. 利用可能パラメータの確認

```
TR で設定できるパラメータを一覧にして、輸送モデルに関係するものだけ教えて。
```

LLM は `describe_parameters` を呼び、`group == "transport"` を抽出して返してくれます。

## 7. 提供ツール一覧

| ツール | 目的 | 主な引数 |
|---|---|---|
| `init` | ライブラリ初期化 | なし |
| `set_param` | 単一パラメータ設定 | `name`, `value` (配列要素は `NAME[i]`) |
| `set_params` | まとめて設定 (scalar / list / dict) | `params` |
| `run` | 時間ステップ進行 | `ntmax` (default=1) |
| `get_state` | 現在の状態取得 | なし |
| `finalize` | リソース解放 | なし |
| `describe_parameters` | パラメータ一覧・型・説明 | なし |
| `describe_state_schema` | `get_state` の JSON schema | なし |
| `run_and_get_state` | init + set + run + get_state を一括 | `params`, `ntmax` |

## 8. FAQ / トラブルシューティング

### Q1. `libtrapi.so not found` と言われます

- `make -C tr libtrapi.so` を実行したかご確認ください。
- ビルド後、`ls tr/libtrapi.so` で `.so` が存在することを確認してください。
- それでもダメなら、環境変数 `TRLIB_PATH` に絶対パスを明示してください。

```bash
export TRLIB_PATH=/absolute/path/to/task/tr/libtrapi.so
```

### Q2. `ModuleNotFoundError: No module named 'trlib'` と言われます

- `PYTHONPATH` にリポジトリの `python/` ディレクトリを追加してください。

```bash
export PYTHONPATH=/absolute/path/to/task/python:$PYTHONPATH
```

- Claude Desktop から起動する場合は、`claude_desktop_config.json` の `env` に同じ値を書いてください。

### Q3. `ModuleNotFoundError: No module named 'mcp'` と言われます

- MCP SDK が入っていません。`pip install 'mcp>=0.9,<2'` を実行してください。
- 仮想環境を使っている場合は、その環境の Python が LLM クライアント側から使われているかも確認してください。

### Q4. `invalid parameter: ...` が返ってきました

- `describe_parameters` で名前を確認してください。名前の大小は区別されます。
- 配列要素は 1-origin です。`PN[0]` は無効で、`PN[1]` から始まります。

### Q5. `calculation failed: ...` と返ってきました

- 入力値 (特に `NSMAX`, `PN`, `PT`, `DT`) の整合性が崩れていないかご確認ください。
- `finalize` してから `init` し直すとクリーンな状態に戻せます。

### Q6. 複数のサーバプロセスを同時起動できますか

TR の Fortran 側は COMMON-block 単一状態なので、1 プロセス = 1 インスタンスが原則です。どうしても同時起動したい場合はプロセス毎に別ディレクトリ / 別 Python プロセスで立ち上げてください (仮想メモリ空間が分離されます)。

### Q7. ログはどこで確認できますか

MCP サーバの標準エラー出力が LLM クライアントに渡ります。Claude Desktop なら「開発者ツール」相当のログビューア、Claude Code なら実行ターミナルで確認できます。

## 9. 参考資料

- MCP spec: <https://modelcontextprotocol.io/>
- Python MCP SDK: <https://github.com/modelcontextprotocol/python-sdk>
- trlib 本体の README: [`../../trlib/README.md`](../../trlib/README.md)
- TR ライブラリ設計書: `docs/superpowers/specs/2026-04-17-tr-library-design.md`
- MCP 共通設計計画: `docs/superpowers/plans/2026-04-18-module-mcp-servers.md`

問題・改善提案は PR / Issue でお願いします。後続の `ti_mcp` / `wr_mcp` / `wrx_mcp` / `fp_mcp` はこの実装をコピーするだけで揃う設計になっています。
