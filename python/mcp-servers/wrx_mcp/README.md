# wrx_mcp — TASK/WRX 用 MCP サーバ

`wrx_mcp` は、TASK プロジェクトのレイトレーシングコード WRX を **Claude Desktop / Claude Code / Cursor といった LLM クライアント**から直接操作できるようにする、Model Context Protocol (MCP) 対応のサーバです。内部では `python/wrxlib` (ctypes ラッパ) を薄く被せており、`libwrxapi.so` を LLM の「道具箱」として差し出すイメージになります。

本ドキュメントは MCP や WRX が初めての方向けに書かれています。手順に沿って進めていけば、Claude のチャット欄で「WRX を初期化して、現在の状態を教えて」とお願いするだけで、WRX を動かして結果を受け取れる状態になります。

本サーバは姉妹パッケージ `tr_mcp` の設計をそのまま踏襲しており、ツール名・挙動・登録方法はほぼ共通です。大きな違いは **(A) パラメータレジストリが WRX 専用**、**(B) 状態構造体 (`get_state`) の形が WRX 専用**、**(C) `wrx_run` / `run_and_get_state` が `WRX_RUN_OK=1` 明示 opt-in ゲートで保護されている（歴史的には SEGV 対策、現在は defence-in-depth）** の 3 点です。

---

## 目次

1. [MCP とは何か (超ざっくり)](#1-mcp-とは何か-超ざっくり)
2. [前提条件](#2-前提条件)
3. [インストール](#3-インストール)
4. [動作確認 (smoke test)](#4-動作確認-smoke-test)
5. [Claude Desktop / Claude Code への登録](#5-claude-desktop--claude-code-への登録)
6. [使い方の例](#6-使い方の例)
7. [提供ツール一覧](#7-提供ツール一覧)
8. [`WRX_RUN_OK` ゲートについて](#8-wrx_run_ok-ゲートについて)
9. [FAQ / トラブルシューティング](#9-faq--トラブルシューティング)
10. [参考資料](#10-参考資料)

---

## 1. MCP とは何か (超ざっくり)

MCP (Model Context Protocol) は、Anthropic が策定した **「LLM と外部ツールをつなぐ標準プロトコル」** です。ざっくり次の図のイメージになります。

```
┌────────────────┐     JSON-RPC      ┌─────────────────────┐
│  LLM client    │ ─────────────────▶│   MCP サーバ         │
│ (Claude 等)    │◀───────────────── │ (この wrx_mcp)      │
└────────────────┘                   │   init/run/...      │
                                     └────────┬────────────┘
                                              │ ctypes
                                              ▼
                                     ┌─────────────────────┐
                                     │  wrx/libwrxapi.so   │
                                     │  (Fortran backend)  │
                                     └─────────────────────┘
```

ポイントは次の 3 つです。

- LLM 側は「ツール」を発見して呼び出すだけで済みます。WRX の中身や Fortran を知らなくても大丈夫です。
- サーバ側は標準入出力 (stdio) で JSON-RPC を待ち受けます。特別なネットワーク設定は不要です。
- 公開するツールには型付きのスキーマが付くので、LLM が引数を誤りにくくなります。

## 2. 前提条件

以下がそろっているか確認してください。

1. **Python 3.10 以上**
2. **WRX の共有ライブラリ `libwrxapi.so`**

   リポジトリルートで次を実行してビルドします:

   ```bash
   make -C wrx libwrxapi.so
   ```

   成功すると `wrx/libwrxapi.so` が生成されます (Phase L-4 で整備済みです)。

3. **`mcp` パッケージ (Python MCP SDK)**

   `pip install 'mcp>=0.9'` で入ります。後述の「インストール」手順に同梱しています。

## 3. インストール

### 3.1. リポジトリ取得とライブラリビルド

```bash
git clone <task repo> task
cd task
make -C wrx libwrxapi.so    # 既に実行済みならスキップで OK
```

### 3.2. MCP サーバのインストール

開発用 (editable) インストールを推奨します。

```bash
cd python/mcp-servers/wrx_mcp
pip install -e .
```

これで `wrx-mcp` コマンドが使えるようになります。また `python -m wrx_mcp.server` でも同じ機能を呼び出せます。

> **Note:** `wrxlib` 自体はリポジトリ同梱の pure-Python パッケージです。`PYTHONPATH` に `<repo>/python` を通すか、`server.py` が自動で親パッケージを import できるようになっているので追加インストールは不要です。

### 3.3. 仮想環境を使いたい場合 (任意)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e python/mcp-servers/wrx_mcp
```

## 4. 動作確認 (smoke test)

### 4.1. ヘルプ表示

まずコマンドが通ることを確認します。

```bash
python -m wrx_mcp.server --help
```

使い方と環境変数がずらっと出れば OK です。

### 4.2. 登録ツール一覧の表示

```bash
python -m wrx_mcp.server --print-tools
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

### 4.3. Python から直接叩く (run なし)

`libwrxapi.so` がビルド済みであれば、Python REPL で次のように動作確認できます。`run` を呼ばなければ segfault リスクはありません。

```python
>>> from wrx_mcp.server import handle_init, handle_get_state, handle_finalize
>>> handle_init()
'wrx library initialized'
>>> state = handle_get_state()
>>> state['NRAYMAX'], state['NSAMAX'], state['MODELG']
(...)
>>> handle_finalize()
'wrx library finalized'
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
    "task-wrx": {
      "command": "python",
      "args": ["-m", "wrx_mcp.server"],
      "env": {
        "PYTHONPATH": "/absolute/path/to/task/python",
        "WRXLIB_PATH": "/absolute/path/to/task/wrx/libwrxapi.so"
        // "WRX_RUN_OK": "1"   // run を使いたい時だけ。8 節の注意事項を必ず確認
      }
    }
  }
}
```

保存して Claude Desktop を再起動すると、ツール一覧に `task-wrx` が並びます。

### 5.2. Claude Code の場合

CLI から追加できます。

```bash
claude mcp add task-wrx -- python -m wrx_mcp.server
```

環境変数を渡したい場合は `--env` を使います。

```bash
claude mcp add task-wrx \
  --env PYTHONPATH=/absolute/path/to/task/python \
  --env WRXLIB_PATH=/absolute/path/to/task/wrx/libwrxapi.so \
  -- python -m wrx_mcp.server
```

### 5.3. Cursor / VS Code など

いずれも MCP 対応エディタであれば、`command` と `args` を同じ要領で書けば動きます。

## 6. 使い方の例

登録が済んだら、Claude にそのまま話しかけてください。以下はチャットプロンプトの例です。

### 6.1. いちばん簡単な例 (run 不要)

```
WRX を初期化して、現在の NRAYMAX と NSAMAX を教えて。
```

LLM は `init → get_state` の順にツールを呼び、値を返してくれます。`run` は呼ばれないので安全です。

### 6.2. パラメータを変えて状態を確認

```
RR を 6.2、BB を 5.3 に設定して、現在のパラメータを get_state で確認して。
```

LLM は内部で

```python
init()
set_params({"RR": 6.2, "BB": 5.3})
get_state()
```

のような呼び出しに変換してくれます。

### 6.3. 配列要素の設定

```
1 本目のレイの周波数 RFIN[1] を 170 GHz (170.0e3) に設定して。
```

LLM は `set_param("RFIN[1]", 170000.0)` (または `set_params({"RFIN": [170000.0]})`) を呼びます。

### 6.4. 利用可能パラメータの確認

```
WRX で設定できるパラメータのうち、ray_init グループのものだけ一覧にして。
```

LLM は `describe_parameters` を呼び、`group == "ray_init"` を抽出して返してくれます。

### 6.5. 実際に実行する (`WRX_RUN_OK=1` で opt-in)

```
RR=6.2, BB=5.3, NRAYMAX=1 に設定して run して、pwr_tot を教えて。
```

`run` / `run_and_get_state` 系のツールは **環境変数 `WRX_RUN_OK=1` を明示的に設定することで opt-in** する方式になっています。歴史的には `wrx_run` が dlopen 経由で SEGV する問題の防衛ゲートでしたが、根本原因は PR #123 (`WRX_NO_GRAPHICS` 自動設定) および PR #163 (`EQFINI` rearm) で既に解消済みです。現在はレイトレの実行コストを LLM に誤って消費させない保険として残しています。詳しくは次節を参照してください。

## 7. 提供ツール一覧

| ツール | 目的 | 主な引数 | 備考 |
|---|---|---|---|
| `init` | ライブラリ初期化 | なし | |
| `set_param` | 単一パラメータ設定 | `name`, `value` (配列要素は `NAME[i]`) | |
| `set_params` | まとめて設定 (scalar / list / dict) | `params` | 文字列パラメータは WRX には無し |
| `run` | レイトレ実行 | `nray_request` (default=0) | **`WRX_RUN_OK=1` opt-in** (8 節参照) |
| `get_state` | 現在の状態取得 | なし | |
| `finalize` | リソース解放 | なし | |
| `describe_parameters` | パラメータ一覧・型・説明 | なし | |
| `describe_state_schema` | `get_state` の JSON schema | なし | |
| `run_and_get_state` | init + set + run + get_state を一括 | `params`, `nray_request` | **`WRX_RUN_OK=1` opt-in** (8 節参照) |

## 8. `WRX_RUN_OK` ゲートについて

`run` と `run_and_get_state` は **環境変数 `WRX_RUN_OK` が `"1"` に設定されていないと実行を拒否** します。

```text
wrx_run is disabled because WRX_RUN_OK is not set to '1'. ...
```

### 歴史的経緯 (resolved)

元々このゲートは、`wrx/libwrxapi.so` を `dlopen` 経由で呼ぶと `wrcalpwr.f90 → libgrf::grd1d` の関係で SEGV する既知問題から MCP サーバを守るためのものでした。ただしこの根本原因は既に次の 2 つの PR で解消しています:

- **PR #123**: `wrx_api_init` が `setenv("WRX_NO_GRAPHICS", "1")` を発行することで、`libwrxapi.so` 起動時に `wrcalpwr` 内のグラフィクス経路が無効化される (SEGV 消滅)。
- **PR #163**: `EQFINI` が `eq_bpsd_init_flag` などの SAVE 変数を rearm するので、`finalize → init` cycle での SEGV も解消。

テスト側の `WRX_RUN_OK` ゲートも PR #166 で default-on (opt-out via `=0`) に flip されており、CI 上で `run` 経路は常時 exercise されています。

### 現在の役割

このゲートは **defence-in-depth / explicit opt-in** として残されています:

- LLM が誤ってレイトレ計算を大量に発行することを防ぐ安全弁 (`init` / `set_param` / `get_state` 系は計算コスト数ミリ秒、`run` は数十秒〜数分)。
- カスタムビルドや実験的ブランチで再発した SEGV を踏んだ場合にサーバごと巻き込まれにくくする保険。

将来的に完全撤去する場合はこの節と `server.py` の gate コードを同時に削除する follow-up PR を想定しています (現時点では保留)。

### 有効化の方法

- シェルから:
  ```bash
  export WRX_RUN_OK=1
  python -m wrx_mcp.server
  ```
- Claude Desktop の `env` に追記:
  ```jsonc
  "env": {
    "PYTHONPATH": "...",
    "WRXLIB_PATH": "...",
    "WRX_RUN_OK": "1"
  }
  ```

ゲートを開いていない状態でも、`init / set_param / set_params / get_state / finalize / describe_parameters / describe_state_schema` は安全に使えます。`run` を必要としないパラメータ検証や形状確認は、ゲートを閉じたままで十分に機能します。

## 9. FAQ / トラブルシューティング

### Q1. `libwrxapi.so not found` と言われます

- `make -C wrx libwrxapi.so` を実行したかご確認ください。
- ビルド後、`ls wrx/libwrxapi.so` で `.so` が存在することを確認してください。
- それでもダメなら、環境変数 `WRXLIB_PATH` に絶対パスを明示してください。

```bash
export WRXLIB_PATH=/absolute/path/to/task/wrx/libwrxapi.so
```

### Q2. `ModuleNotFoundError: No module named 'wrxlib'` と言われます

- `PYTHONPATH` にリポジトリの `python/` ディレクトリを追加してください。

```bash
export PYTHONPATH=/absolute/path/to/task/python:$PYTHONPATH
```

- Claude Desktop から起動する場合は、`claude_desktop_config.json` の `env` に同じ値を書いてください。

### Q3. `ModuleNotFoundError: No module named 'mcp'` と言われます

- MCP SDK が入っていません。`pip install 'mcp>=0.9'` を実行してください。
- 仮想環境を使っている場合は、その環境の Python が LLM クライアント側から使われているかも確認してください。

### Q4. `invalid parameter: ...` が返ってきました

- `describe_parameters` で名前を確認してください。名前の大小は区別されます。
- 配列要素は 1-origin です。`PN[0]` は無効で、`PN[1]` から始まります。

### Q5. `wrx_run is disabled because WRX_RUN_OK ...` と返ってきました

- 8 節「`WRX_RUN_OK` ゲートについて」を参照してください。意図的にブロックしています。

### Q6. `calculation failed: ...` と返ってきました

- 入力値 (特に `NRAYMAX`, `NSMAX`, `RFIN`, `RPIN`, `MODELG`) の整合性が崩れていないかご確認ください。
- `finalize` してから `init` し直すとクリーンな状態に戻せます。

### Q7. 複数のサーバプロセスを同時起動できますか

WRX の Fortran 側は COMMON-block 単一状態なので、1 プロセス = 1 インスタンスが原則です。どうしても同時起動したい場合はプロセス毎に別ディレクトリ / 別 Python プロセスで立ち上げてください (仮想メモリ空間が分離されます)。

### Q8. ログはどこで確認できますか

MCP サーバの標準エラー出力が LLM クライアントに渡ります。Claude Desktop なら「開発者ツール」相当のログビューア、Claude Code なら実行ターミナルで確認できます。

## 10. 参考資料

- MCP spec: <https://modelcontextprotocol.io/>
- Python MCP SDK: <https://github.com/modelcontextprotocol/python-sdk>
- wrxlib 本体の README: [`../../wrxlib/README.md`](../../wrxlib/README.md) (ライブラリ層のテストゲート履歴あり)
- tr_mcp リファレンス実装: [`../tr_mcp/README.md`](../tr_mcp/README.md)
- MCP 共通設計計画: `docs/superpowers/plans/2026-04-18-module-mcp-servers.md`

問題・改善提案は PR / Issue でお願いします。姉妹サーバ (`tr_mcp` / 今後の `ti_mcp` / `wr_mcp` / `fp_mcp`) も同じ構成です。
