# tot_mcp — TASK/TOT 統合オーケストレータ用 MCP サーバ

`tot_mcp` は、TASK プロジェクトの統合オーケストレータ TOT を **Claude Desktop / Claude Code / Cursor といった LLM クライアント**から直接操作できるようにする、Model Context Protocol (MCP) 対応のサーバです。内部では `python/totlib` (ctypes ラッパ) を薄く被せており、`libtotapi.so` を LLM の「道具箱」として差し出すイメージになります。

TOT は eq / tr / fp / ti / wr / wrx の 6 モジュールを束ねる立場のため、パラメータ名には **必ず名前空間プレフィックス**を付けてもらう運用になります（例: `eq:RR`, `tr:DT`, `fp:NSMAX`, `ti:RR`, `wr:RFIN`, `wrx:RFIN`）。本ドキュメントはこの規約と、Claude への登録手順を初心者の方向けに案内します。

---

## 目次

1. [MCP とは何か (超ざっくり)](#1-mcp-とは何か-超ざっくり)
2. [前提条件](#2-前提条件)
3. [インストール](#3-インストール)
4. [動作確認 (smoke test)](#4-動作確認-smoke-test)
5. [Claude Desktop / Claude Code への登録](#5-claude-desktop--claude-code-への登録)
6. [使い方の例](#6-使い方の例)
7. [提供ツール一覧](#7-提供ツール一覧)
8. [名前空間プレフィックス（重要）](#8-名前空間プレフィックス重要)
9. [FAQ / トラブルシューティング](#9-faq--トラブルシューティング)
10. [参考資料](#10-参考資料)

---

## 1. MCP とは何か (超ざっくり)

MCP (Model Context Protocol) は、Anthropic が策定した **「LLM と外部ツールをつなぐ標準プロトコル」** です。ざっくり次の図のイメージになります。

```
┌────────────────┐     JSON-RPC      ┌─────────────────────┐
│  LLM client    │ ─────────────────▶│   MCP サーバ         │
│ (Claude 等)    │◀───────────────── │ (この tot_mcp)      │
└────────────────┘                   │   init/run/...      │
                                     └────────┬────────────┘
                                              │ ctypes
                                              ▼
                                     ┌─────────────────────┐
                                     │  tot/libtotapi.so   │
                                     │  (Fortran backend)  │
                                     └─────────────────────┘
```

ポイントは次の 3 つです。

- LLM 側は「ツール」を発見して呼び出すだけで済みます。TOT の中身や Fortran を知らなくても大丈夫です。
- サーバ側は標準入出力 (stdio) で JSON-RPC を待ち受けます。特別なネットワーク設定は不要です。
- 公開するツールには型付きのスキーマが付くので、LLM が引数を誤りにくくなります。

## 2. 前提条件

以下がそろっているか確認してください。

1. **Python 3.10 以上**
2. **TOT の共有ライブラリ `libtotapi.so`**

   リポジトリルートで次を実行してビルドします:

   ```bash
   make -C tot libtotapi.so
   ```

   成功すると `tot/libtotapi.so` が生成されます (Phase L-4 で整備済みです)。

3. **`mcp` パッケージ (Python MCP SDK)**

   `pip install 'mcp>=0.9,<2'` で入ります。後述の「インストール」手順に同梱しています。

## 3. インストール

### 3.1. リポジトリ取得とライブラリビルド

```bash
git clone <task repo> task
cd task
make -C tot libtotapi.so    # 既に実行済みならスキップで OK
```

### 3.2. MCP サーバのインストール

開発用 (editable) インストールを推奨します。

```bash
cd python/mcp-servers/tot_mcp
pip install -e .
```

これで `tot-mcp` コマンドが使えるようになります。また `python -m tot_mcp.server` でも同じ機能を呼び出せます。

> **Note:** `totlib` 自体はリポジトリ同梱の pure-Python パッケージです。`PYTHONPATH` に `<repo>/python` を通すか、`server.py` が自動で親パッケージを import できるようになっているので追加インストールは不要です。
>
> `describe_parameters` は per-namespace の登録情報を返すため、内部で `tr_mcp` / `ti_mcp` / `fp_mcp` / `wrx_mcp` の `PARAMETER_REGISTRY` を遅延 import します。これらは見つからなければ空辞書扱いになり、サーバ自体は問題なく動作します（モジュール毎にインストールしてもらえると、より詳しい説明が LLM に届きます）。

### 3.3. 仮想環境を使いたい場合 (任意)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e python/mcp-servers/tot_mcp
# 必要に応じて、より詳細な describe_parameters を返すために
# 兄弟 MCP サーバも入れておくと親切です。
pip install -e python/mcp-servers/tr_mcp \
            -e python/mcp-servers/ti_mcp \
            -e python/mcp-servers/fp_mcp \
            -e python/mcp-servers/wrx_mcp
```

## 4. 動作確認 (smoke test)

### 4.1. ヘルプ表示

まずコマンドが通ることを確認します。

```bash
python -m tot_mcp.server --help
```

使い方と環境変数、名前空間プレフィックスの説明が出れば OK です。

### 4.2. 登録ツール一覧の表示

```bash
python -m tot_mcp.server --print-tools
```

以下の 10 ツールが並びます。

```
describe_parameters
describe_state_schema
finalize
get_state
init
run
run_and_get_state
run_pipeline
set_param
set_params
```

### 4.3. Python から直接叩く

`libtotapi.so` がビルド済みであれば、Python REPL で次のように動作確認できます。

```python
>>> from tot_mcp.server import handle_init, handle_set_param
>>> handle_init()
'tot library initialized'
>>> handle_set_param("eq:RR", 6.2)
'set eq:RR = 6.2'
>>> handle_set_param("tr:DT", 0.01)
'set tr:DT = 0.01'
```

> L-3/L-4/L-5 時点では `tot_run` と `tot_get_state` がスタブ (`TOT_ERR_NOT_IMPL`) のため、`handle_run` / `handle_get_state` は `not implemented in this libtotapi.so build: ...` を返します。L-6 で per-module fan-out が入ると、自動的に正常終了するようになります。

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
    "task-tot": {
      "command": "python",
      "args": ["-m", "tot_mcp.server"],
      "env": {
        "PYTHONPATH": "/absolute/path/to/task/python",
        "TOTLIB_PATH": "/absolute/path/to/task/tot/libtotapi.so"
      }
    }
  }
}
```

保存して Claude Desktop を再起動すると、ツール一覧に `task-tot` が並びます。

### 5.2. Claude Code の場合

CLI から追加できます。

```bash
claude mcp add task-tot -- python -m tot_mcp.server
```

環境変数を渡したい場合は `--env` を使います。

```bash
claude mcp add task-tot \
  --env PYTHONPATH=/absolute/path/to/task/python \
  --env TOTLIB_PATH=/absolute/path/to/task/tot/libtotapi.so \
  -- python -m tot_mcp.server
```

### 5.3. Cursor / VS Code など

いずれも MCP 対応エディタであれば、`command` と `args` を同じ要領で書けば動きます。

## 6. 使い方の例

登録が済んだら、Claude にそのまま話しかけてください。以下はチャットプロンプトの例です。

### 6.1. いちばん簡単な例

```
TOT を初期化して、eq の major radius を 6.2、tr の time step を 0.01 にしてから、
1 ステップ走らせて結果を教えて。
```

LLM は `init` → `set_params({"eq:RR": 6.2, "tr:DT": 0.01})` → `run(1)` → `get_state` の順にツールを呼んでくれます（L-6 完了後）。

### 6.2. 複数モジュールに跨るパラメータ設定

```
eq の RR を 6.5、BB を 5.3、tr の RA を 2.0、fp の NSMAX を 2 に設定して。
```

LLM は内部で

```python
set_params({
    "eq:RR": 6.5,
    "eq:BB": 5.3,
    "tr:RA": 2.0,
    "fp:NSMAX": 2,
})
```

のような呼び出しに変換してくれます。

### 6.3. 配列要素の設定

```
tr の PN[1] を 0.7、PN[2] を 0.6 にしてから初期化して。
```

LLM はそれぞれ `set_param("tr:PN[1]", 0.7)` と `set_param("tr:PN[2]", 0.6)` を呼びます。リスト構文で一括指定もできます。

```python
set_params({"tr:PN": [0.7, 0.6]})
# -> 内部で tr:PN[1]=0.7, tr:PN[2]=0.6 が適用されます
```

### 6.4. 文字列パラメータの設定

```
eq の equilibrium データファイルを 'eqdata.ITER01' に設定して。
```

LLM は `set_param("eq:KNAMEQ", "eqdata.ITER01")` を呼びます（内部で `set_param_str` に振り分けられます）。文字列パラメータをサポートしているのは `tr:` と `eq:` の名前空間だけです。

### 6.5. 利用可能パラメータの確認

```
TOT で設定できる eq モジュールのパラメータを一覧にして。
```

LLM は `describe_parameters` を呼び、`parameters["eq"]` を抽出して返してくれます。

## 7. 提供ツール一覧

| ツール | 目的 | 主な引数 |
|---|---|---|
| `init` | ライブラリ初期化 | なし |
| `set_param` | 単一パラメータ設定 | `name` (必ず `<ns>:<bare>`), `value` |
| `set_params` | まとめて設定 (scalar / list / dict) | `params` (キーは必ず namespaced) |
| `run` | 時間ステップ進行 | `ntmax` (default=1) |
| `get_state` | 現在の状態取得 | なし |
| `finalize` | リソース解放 | なし |
| `describe_parameters` | 名前空間ごとのパラメータ一覧・型・説明 | なし |
| `describe_state_schema` | `get_state` の JSON schema | なし |
| `run_and_get_state` | init + set + run + get_state を一括 | `params`, `ntmax` |
| `run_pipeline` | 複数モジュールを連結したスカラーカップリング実行 (L-7a) | `steps`, `params` |

> L-3/L-4/L-5 時点では `init` / `run` / `get_state` / `finalize` の Fortran 側がスタブ (`TOT_ERR_NOT_IMPL`) です。`set_param` / `set_param_str` は端から端まで実装済みなので、パラメータ設定の挙動はいま既に確認できます。L-6 で per-module fan-out が入ると、`run` / `get_state` も自動的に正常応答に切り替わります。

### 7.1. `run_pipeline` ツール (L-7a)

`run_pipeline` は **複数モジュールにまたがるスカラーカップリング**を 1 回の MCP 呼び出しで実行するツールです。`libtotapi.so` ではなく、Python 側の `totlib.TotPipeline` (Phase 1/2 で導入) を使ってモジュール間の値伝搬を行います。

**引数:**

- `steps`: 実行するステップのリスト。各要素は `{"module": "<name>", "kwargs": {...}}` 形式の dict。`module` 名は `fp` / `tr` / `eq` / `wr` / `wrx` / `ti` のいずれか。
- `params` (省略可): 走らせる前にまとめてセットするパラメータ。`{"<module>:<param>": value, ...}` 形式 (例: `{"fp:NSAMAX": 2, "tr:RR": 6.2}`)。

**戻り値:** `dict` — モジュール名をキーに各ステップの最終 scalar が並び、`_steps` キーに全ステップ (`module` / `scalars` / `coupling_applied`) のタイムラインが入ります。

**現在登録されているカップリング規則 (L-7a):**

- `fp → tr`: `compute_rjt_volint(fp_state)` (A) を `× 1e-6` 変換して `tr.PLHCD` (無次元) にセット。

> **L-7a スケルトン カップリング注記:** `tr.PLHCD` は **無次元 multiplier** です (R3 outcome: `tr_param_registry.f90` に `PNBCD` 未登録のため代替として採用)。L-7a は **API 配線の妥当性検証**が目的で、物理的忠実度は L-7b で `EXTERNAL_DRIVEN_I` のような専用スカラーを Fortran 側に追加した時点で対応します。L-7a 等価性テスト (`python/totlib/tests/test_pipeline_equiv.py`) は 1e-10 の許容誤差で hand-written と pipeline-driven の結果が一致することを保証します。

**呼び出し例 (JSON):**

```json
{
  "steps": [
    {"module": "fp", "kwargs": {"ntmax": 5}},
    {"module": "tr", "kwargs": {"ntmax": 1}}
  ],
  "params": {"fp:NSAMAX": 2, "tr:RR": 6.2, "tr:RA": 2.0}
}
```

**force-close ゲート:** `run_pipeline` を呼ぶたびに

- 既存の legacy `STATE` (Tot シングルトン) を `STATE.close()` で閉じる
- 直前の `PIPELINE_STATE` (もしあれば) も `_force_close_pipeline()` で閉じる

ことで、毎回クリーンな状態から開始します。これは `run_and_get_state` の HIGH 監査パターン (2026-04-22) と同じ思想です。`run_pipeline` 中の例外発生時も `PIPELINE_STATE` は `None` にリセットされるので、次の呼び出しが open ハンドルを引き継ぐことはありません。

**入力検証:** `steps` の各要素は dict であり `"module"` と `"kwargs"` の両キーを持つ必要があります。欠落していると `TotPipelineCouplingError` が **state を変更する前に** raise されるため、不正ペイロードによる副作用はありません。

## 8. 名前空間プレフィックス（重要）

TOT のパラメータ空間は eq / tr / fp / ti / wr / wrx の **和集合**です。同じ名前のパラメータが複数モジュールに存在する（例: `RR` は eq / tr / ti / wrx すべてに、`DT` は tr と ti に）ため、必ず `<ns>:<bare>` 形式の名前を渡してください。

| プレフィックス | 振り分け先レジストリ | 代表例 |
|---|---|---|
| `eq:` | `eq_param_set` | `eq:RR`, `eq:BB`, `eq:RIP`, `eq:KNAMEQ` |
| `tr:` | `tr_param_set` | `tr:DT`, `tr:NTMAX`, `tr:RR`, `tr:PN[1]` |
| `fp:` | `fp_param_set` | `fp:NSMAX`, `fp:DELT` |
| `ti:` | `ti_param_set` | `ti:RR`, `ti:DT` |
| `wr:` | `wrx_param_set`（エイリアス） | `wr:RFIN` |
| `wrx:` | `wrx_param_set` | `wrx:RFIN`, `wrx:NRAY` |

> **`wr:` は `wrx:` の別名です。** TOT のリンクグラフは `wrx/libwr.a` を採用しているため、`wr:` プレフィックスも内部的に `wrx_param_set` に振り分けられます。詳細は `tot/tot_param_registry.f90` の冒頭コメントを参照してください。

未対応のプレフィックスや、プレフィックスを付け忘れた名前は、まず Python 側のガード (`totlib`) が検出して `TotlibInvalidParamError` を送出し、MCP 層では `"invalid parameter: ..."` メッセージで LLM に通知されます。

```
invalid parameter: tot parameter name 'RR' is missing a namespace prefix.
tot is the orchestrator: every name must be of the form '<ns>:<name>'
where <ns> is one of ('eq', 'tr', 'fp', 'ti', 'wr', 'wrx'). ...
```

配列要素は per-module レジストリの構文をそのまま使えます（例: `tot.set_param("tr:PN[1]", 0.7)`、`set_param("eq:PSIB[1]", 0.0)`）。

## 9. FAQ / トラブルシューティング

### Q1. `libtotapi.so not found` と言われます

- `make -C tot libtotapi.so` を実行したかご確認ください。
- ビルド後、`ls tot/libtotapi.so` で `.so` が存在することを確認してください。
- それでもダメなら、環境変数 `TOTLIB_PATH` に絶対パスを明示してください。

```bash
export TOTLIB_PATH=/absolute/path/to/task/tot/libtotapi.so
```

### Q2. `ModuleNotFoundError: No module named 'totlib'` と言われます

- `PYTHONPATH` にリポジトリの `python/` ディレクトリを追加してください。

```bash
export PYTHONPATH=/absolute/path/to/task/python:$PYTHONPATH
```

- Claude Desktop から起動する場合は、`claude_desktop_config.json` の `env` に同じ値を書いてください。

### Q3. `ModuleNotFoundError: No module named 'mcp'` と言われます

- MCP SDK が入っていません。`pip install 'mcp>=0.9,<2'` を実行してください。
- 仮想環境を使っている場合は、その環境の Python が LLM クライアント側から使われているかも確認してください。

### Q4. `invalid parameter: ... is missing a namespace prefix` と返ってきました

- 名前を `<ns>:<bare>` 形式に直してください。`<ns>` は `eq`, `tr`, `fp`, `ti`, `wr`, `wrx` のいずれかです。
- 例: `RR` → `eq:RR`、`DT` → `tr:DT`（または `ti:DT`）。
- どの名前空間に振り分けるべきか分からない場合は、`describe_parameters` を呼んで確認してください。

### Q5. `not implemented in this libtotapi.so build` と返ってきました

- `tot_run` / `tot_get_state` / `tot_init` / `tot_finalize` は L-3 〜 L-5 時点ではスタブで `TOT_ERR_NOT_IMPL` を返します。L-6 で per-module fan-out が完成すると正常応答に切り替わります。
- `set_param` / `set_param_str` は端から端まで実装済みのため、パラメータ設定の動作は今すぐ確認できます。

### Q6. `calculation failed: ...` と返ってきました

- 入力値の整合性が崩れていないかご確認ください（特に `tr:NSMAX`, `tr:PN`, `tr:PT`, `tr:DT`）。
- `finalize` してから `init` し直すとクリーンな状態に戻せます。

### Q7. 複数のサーバプロセスを同時起動できますか

TOT のバックエンドは Fortran COMMON-block を使った単一状態なので、1 プロセス = 1 インスタンスが原則です。どうしても同時起動したい場合はプロセス毎に別ディレクトリ / 別 Python プロセスで立ち上げてください (仮想メモリ空間が分離されます)。

### Q8. ログはどこで確認できますか

MCP サーバの標準エラー出力が LLM クライアントに渡ります。Claude Desktop なら「開発者ツール」相当のログビューア、Claude Code なら実行ターミナルで確認できます。

## 10. 参考資料

- MCP spec: <https://modelcontextprotocol.io/>
- Python MCP SDK: <https://github.com/modelcontextprotocol/python-sdk>
- totlib 本体の README: [`../../totlib/README.md`](../../totlib/README.md)
- TOT ライブラリ設計書: `docs/superpowers/specs/2026-04-17-tr-library-design.md`
- MCP 共通設計計画: `docs/superpowers/plans/2026-04-18-module-mcp-servers.md`
- 兄弟 MCP サーバ: `tr_mcp`, `ti_mcp`, `fp_mcp`, `wr_mcp`, `wrx_mcp`

問題・改善提案は PR / Issue でお願いします。
