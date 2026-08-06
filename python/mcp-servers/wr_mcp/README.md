# wr_mcp — TASK/WR 用 MCP サーバ

`wr_mcp` は、TASK プロジェクトのレイトレーシングコード WR を **Claude Desktop / Claude Code / Cursor といった LLM クライアント**から直接操作できるようにする、Model Context Protocol (MCP) 対応のサーバです。内部では `python/wrlib` (ctypes ラッパ) を薄く被せており、`libwrapi.so` を LLM の「道具箱」として差し出すイメージになります。

本ドキュメントは MCP や WR が初めての方向けに書かれています。手順に沿って進めていけば、Claude のチャット欄で「WR を RR=3.0, BB=3.5 で初期化して 1 本レイを飛ばして結果を教えて」とお願いするだけで、WR を動かして結果を受け取れる状態になります。

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
10. [設計メモ: finalize リセット不変条件](#10-設計メモ-finalize-リセット不変条件)

---

## 1. MCP とは何か (超ざっくり)

MCP (Model Context Protocol) は、Anthropic が策定した **「LLM と外部ツールをつなぐ標準プロトコル」** です。ざっくり次の図のイメージになります。

```
┌────────────────┐     JSON-RPC      ┌─────────────────────┐
│  LLM client    │ ─────────────────▶│   MCP サーバ         │
│ (Claude 等)    │◀───────────────── │ (この wr_mcp)       │
└────────────────┘                   │   init/run/...      │
                                     └────────┬────────────┘
                                              │ ctypes
                                              ▼
                                     ┌─────────────────────┐
                                     │  wr/libwrapi.so     │
                                     │  (Fortran backend)  │
                                     └─────────────────────┘
```

ポイントは次の 3 つです。

- LLM 側は「ツール」を発見して呼び出すだけで済みます。WR の中身や Fortran を知らなくても大丈夫です。
- サーバ側は標準入出力 (stdio) で JSON-RPC を待ち受けます。特別なネットワーク設定は不要です。
- 公開するツールには型付きのスキーマが付くので、LLM が引数を誤りにくくなります。

## 2. 前提条件

以下がそろっているか確認してください。

1. **Python 3.10 以上**
2. **WR の共有ライブラリ `libwrapi.so`**

   リポジトリルートで次を実行してビルドします。

   ```bash
   make -C wr libwrapi.so
   ```

   成功すると `wr/libwrapi.so` が生成されます (Phase L-4 で整備済みです)。

3. **`mcp` パッケージ (Python MCP SDK)**

   `pip install 'mcp>=0.9,<2'` で入ります。後述の「インストール」手順に同梱しています。

## 3. インストール

### 3.1. リポジトリ取得とライブラリビルド

```bash
git clone <task repo> task
cd task
make -C wr libwrapi.so    # 既に実行済みならスキップで OK
```

### 3.2. MCP サーバのインストール

開発用 (editable) インストールを推奨します。

```bash
cd python/mcp-servers/wr_mcp
pip install -e .
```

これで `wr-mcp` コマンドが使えるようになります。また `python -m wr_mcp.server` でも同じ機能を呼び出せます。

> **Note:** `wrlib` 自体はリポジトリ同梱の pure-Python パッケージです。`PYTHONPATH` に `<repo>/python` を通すか、`server.py` が自動で親パッケージを import できるようになっているので追加インストールは不要です。

### 3.3. 仮想環境を使いたい場合 (任意)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e python/mcp-servers/wr_mcp
```

## 4. 動作確認 (smoke test)

### 4.1. ヘルプ表示

まずコマンドが通ることを確認します。

```bash
python -m wr_mcp.server --help
```

使い方と環境変数がずらっと出れば OK です。

### 4.2. 登録ツール一覧の表示

```bash
python -m wr_mcp.server --print-tools
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

`libwrapi.so` がビルド済みであれば、Python REPL で次のように動作確認できます。

```python
>>> from wr_mcp.server import handle_init, handle_run, handle_get_state
>>> handle_init()
'wr library initialized'
>>> handle_run(0)          # namelist の NRAYMAX を維持
'ran ray tracing (nray_request=0)'
>>> state = handle_get_state()
>>> state['NRAYMAX'], state['NRSMAX'], state['NRLMAX']
(1, 50, 100)               # デフォルト入力に依存します
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
    "task-wr": {
      "command": "python",
      "args": ["-m", "wr_mcp.server"],
      "env": {
        "PYTHONPATH": "/absolute/path/to/task/python",
        "WRLIB_PATH": "/absolute/path/to/task/wr/libwrapi.so"
      }
    }
  }
}
```

保存して Claude Desktop を再起動すると、ツール一覧に `task-wr` が並びます。

### 5.2. Claude Code の場合

CLI から追加できます。

```bash
claude mcp add task-wr -- python -m wr_mcp.server
```

環境変数を渡したい場合は `--env` を使います。

```bash
claude mcp add task-wr \
  --env PYTHONPATH=/absolute/path/to/task/python \
  --env WRLIB_PATH=/absolute/path/to/task/wr/libwrapi.so \
  -- python -m wr_mcp.server
```

### 5.3. Cursor / VS Code など

いずれも MCP 対応エディタであれば、`command` と `args` を同じ要領で書けば動きます。

## 6. 使い方の例

登録が済んだら、Claude にそのまま話しかけてください。以下はチャットプロンプトの例です。

### 6.1. いちばん簡単な例

```
WR を初期化して、デフォルトパラメータのまま 1 回レイトレーシングを実行し、
pwrmax_rs と pwrmax_rl を教えて。
```

LLM は `init → run → get_state` の順にツールを呼び、`scalars.pwrmax_rs` と `scalars.pwrmax_rl` の値を返してくれます。

### 6.2. パラメータを変えて実行

```
major radius RR を 3.0 にして、toroidal field BB を 3.5 にして、
入射周波数 RF を 170 GHz、初期 n_parallel RNZI を 0.4 にしてから
1 本レイを飛ばして、pwrmax_rs の位置を教えて。
```

LLM は内部で

```python
run_and_get_state(
    params={"RR": 3.0, "BB": 3.5, "RF": 170.0, "RNZI": 0.4},
    nray_request=1,
)
```

のような呼び出しに変換してくれます。

### 6.3. 複数レイを投入

```
NRAYMAX を 4 にして、RFIN を [170, 170, 170, 170]、
UUIN を [1.0, 1.0, 1.0, 1.0] にして run_and_get_state。
それぞれのレイの pwrmax_rs を表にして。
```

`RFIN` / `UUIN` を list で渡すと、LLM は `RFIN[1]..RFIN[4]` / `UUIN[1]..UUIN[4]` として 1-origin で展開します。

### 6.4. 利用可能パラメータの確認

```
WR で設定できるパラメータを一覧にして、ray/beam に関係するものだけ教えて。
```

LLM は `describe_parameters` を呼び、`group == "ray"` や `group == "beam"` を抽出して返してくれます。

## 7. 提供ツール一覧

| ツール | 目的 | 主な引数 |
|---|---|---|
| `init` | ライブラリ初期化 | なし |
| `set_param` | 単一パラメータ設定 | `name`, `value` (配列要素は `NAME[i]`) |
| `set_params` | まとめて設定 (scalar / list / dict) | `params` |
| `run` | レイトレーシング実行 | `nray_request` (default=0: namelist の NRAYMAX を維持) |
| `get_state` | 現在の状態取得 | なし |
| `finalize` | リソース解放 | なし |
| `describe_parameters` | パラメータ一覧・型・説明 | なし |
| `describe_state_schema` | `get_state` の JSON schema | なし |
| `run_and_get_state` | init + set + run + get_state を一括 | `params`, `nray_request` |

## 8. FAQ / トラブルシューティング

### Q1. `libwrapi.so not found` と言われます

- `make -C wr libwrapi.so` を実行したかご確認ください。
- ビルド後、`ls wr/libwrapi.so` で `.so` が存在することを確認してください。
- それでもダメなら、環境変数 `WRLIB_PATH` に絶対パスを明示してください。

```bash
export WRLIB_PATH=/absolute/path/to/task/wr/libwrapi.so
```

### Q2. `ModuleNotFoundError: No module named 'wrlib'` と言われます

- `PYTHONPATH` にリポジトリの `python/` ディレクトリを追加してください。

```bash
export PYTHONPATH=/absolute/path/to/task/python:$PYTHONPATH
```

- Claude Desktop から起動する場合は、`claude_desktop_config.json` の `env` に同じ値を書いてください。

### Q3. `ModuleNotFoundError: No module named 'mcp'` と言われます

- MCP SDK が入っていません。`pip install 'mcp>=0.9,<2'` を実行してください。
- 仮想環境を使っている場合は、その環境の Python が LLM クライアント側から使われているかも確認してください。

### Q4. `invalid parameter: ...` が返ってきました

- `describe_parameters` で名前を確認してください。名前の大小は区別されます (例: `mode_beam` は小文字、`MODEW` は大文字です)。
- 配列要素は 1-origin です。`RFIN[0]` は無効で、`RFIN[1]` から始まります。
- `NRAYMAX` は上限 100 (`WR_MAX_NRAYMAX`)、`NRSMAX` は 200、`NRLMAX` は 400 です。

### Q5. `calculation failed: ...` と返ってきました

- 入力値 (特に `RR`, `BB`, `NRAYMAX`, `RFIN`, `RNZI`) の整合性が崩れていないかご確認ください。
- プラズマ境界外や `pne_threshold` 未満の領域にレイ始点を置くと失敗します。
- `finalize` してから `init` し直すとクリーンな状態に戻せます (次節を参照)。

### Q6. 複数のサーバプロセスを同時起動できますか

WR の Fortran 側は COMMON-block 単一状態なので、1 プロセス = 1 インスタンスが原則です。どうしても同時起動したい場合はプロセス毎に別ディレクトリ / 別 Python プロセスで立ち上げてください (仮想メモリ空間が分離されます)。

### Q7. ログはどこで確認できますか

MCP サーバの標準エラー出力が LLM クライアントに渡ります。Claude Desktop なら「開発者ツール」相当のログビューア、Claude Code なら実行ターミナルで確認できます。

## 9. 参考資料

- MCP spec: <https://modelcontextprotocol.io/>
- Python MCP SDK: <https://github.com/modelcontextprotocol/python-sdk>
- wrlib 本体の README: [`../../wrlib/README.md`](../../wrlib/README.md)
- WR ライブラリ設計 (Phase L-0〜L-7): `docs/superpowers/plans/2026-04-18-wr-library-L*.md`
- 兄弟実装 (参考元): [`../tr_mcp/README.md`](../tr_mcp/README.md)

問題・改善提案は PR / Issue でお願いします。後続の `ti_mcp` / `wrx_mcp` / `fp_mcp` もこの実装をコピーすれば揃う設計になっています。

## 10. 設計メモ: finalize リセット不変条件

> この節は PR #36 で Bugbot に HIGH 指摘された「finalize 後の状態」について、LLM および利用者が踏み込むと事故りやすいポイントを明文化するためのメモです。

### 10.1. 不変条件

**`finalize` を呼んだ後、次にデータを返すツール (`run` / `get_state` / `run_and_get_state` / `set_param` / `set_params`) を呼ぶと、ライブラリは「デフォルト値で」自動的に再初期化されます。** 前の `run` の状態は一切引き継がれません。

```
init → set_params(A=1) → run → get_state   ← 状態 S1
finalize                                    ← 内部の Wrlib を close()
run → get_state                             ← 自動 init され、S1 は消滅
                                              set_params(A=1) を再度やり直す必要あり
```

### 10.2. 推奨フロー (1 シミュレーション 1 サイクル)

信頼できる結果を得るために、**1 組のパラメータで 1 つの結果を取る単位**として次のフローを守ってください。

```python
init()
set_params({"RR": 3.0, "BB": 3.5, "RFIN": [170.0, 170.0]})
run(nray_request=2)
state = get_state()
finalize()          # 次のシミュレーションに備えて確実にリセット
```

LLM プロンプトでも 1 問い合わせにつき 1 サイクルをお願いする形が安全です。

### 10.3. スイープ (パラメータ探索) のやり方

同じプロセス内で複数ケースを回したい場合、`finalize` の前に結果を必ず取り出してから次の `init` に進んでください。

```python
results = []
for rr in (3.0, 3.2, 3.4):
    init()
    set_param("RR", rr)
    run(nray_request=1)
    results.append(get_state())
    finalize()      # 次のループに状態を漏らさない
```

`run_and_get_state` は init/set/run/get_state を 1 回で行うので、スイープで使う場合も**ループ末尾で `finalize` を呼ぶ**のが推奨です。

### 10.4. ハマりどころ

- `finalize` 後に `set_param` だけ呼ぶと、新しく開かれた初期状態に書き込まれます。前の `run` の状態ではありません。
- `get_state` を 2 回連続で呼んでも、2 回目は 1 回目と同じ状態です (自動 re-init は `close()` 済みの時だけ発動します)。
- `wrlib.Wrlib` は 1 プロセス 1 インスタンスが原則です。別セッションでも結果を比べたいときは、`state.to_dict()` を JSON 化して保存してから次のサイクルに進んでください。
