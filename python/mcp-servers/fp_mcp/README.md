# fp_mcp — TASK/FP 用 MCP サーバ

`fp_mcp` は、TASK プロジェクトの Fokker-Planck コード FP を **Claude Desktop / Claude Code / Cursor といった LLM クライアント**から直接操作できるようにする、Model Context Protocol (MCP) 対応のサーバです。内部では `python/fplib` (ctypes ラッパ) を薄く被せており、`libfpapi.so` を LLM の「道具箱」として差し出すイメージになります。

本ドキュメントは MCP や FP が初めての方向けに書かれています。手順に沿って進めていけば、Claude のチャット欄で「FP を iter01 設定で初期化して 2 ステップ回して温度プロファイルを教えて」とお願いするだけで、FP を動かして結果を受け取れる状態になります。

設計は `tr_mcp` のリファレンス実装を踏襲しており、ツール名・引数・レスポンス形式は共通化されています。

---

## 目次

1. [MCP とは何か (超ざっくり)](#1-mcp-とは何か-超ざっくり)
2. [前提条件](#2-前提条件)
3. [インストール](#3-インストール)
4. [動作確認 (smoke test)](#4-動作確認-smoke-test)
5. [Claude Desktop / Claude Code への登録](#5-claude-desktop--claude-code-への登録)
6. [使い方の例](#6-使い方の例)
7. [提供ツール一覧](#7-提供ツール一覧)
8. [FP 固有の注意点](#8-fp-固有の注意点)
9. [FAQ / トラブルシューティング](#9-faq--トラブルシューティング)
10. [参考資料](#10-参考資料)

---

## 1. MCP とは何か (超ざっくり)

MCP (Model Context Protocol) は、Anthropic が策定した **「LLM と外部ツールをつなぐ標準プロトコル」** です。ざっくり次の図のイメージになります。

```
┌────────────────┐     JSON-RPC      ┌─────────────────────┐
│  LLM client    │ ─────────────────▶│   MCP サーバ         │
│ (Claude 等)    │◀───────────────── │ (この fp_mcp)       │
└────────────────┘                   │   init/run/...      │
                                     └────────┬────────────┘
                                              │ ctypes
                                              ▼
                                     ┌─────────────────────┐
                                     │  fp/libfpapi.so     │
                                     │  (Fortran backend)  │
                                     └─────────────────────┘
```

ポイントは次の 3 つです。

- LLM 側は「ツール」を発見して呼び出すだけで済みます。FP の中身や Fortran を知らなくても大丈夫です。
- サーバ側は標準入出力 (stdio) で JSON-RPC を待ち受けます。特別なネットワーク設定は不要です。
- 公開するツールには型付きのスキーマが付くので、LLM が引数を誤りにくくなります。

## 2. 前提条件

以下がそろっているか確認してください。

1. **Python 3.10 以上**
2. **FP の共有ライブラリ `libfpapi.so`**

   リポジトリルートで次を実行してビルドします:

   ```bash
   make -C fp libs_pic
   make -C fp libfpapi.so
   ```

   成功すると `fp/libfpapi.so` が生成されます (Phase L-4 で整備済みです)。エクスポートされる C ABI シンボルは 6 つ (`fp_init`, `fp_run`, `fp_set_param`, `fp_set_param_str`, `fp_get_state`, `fp_finalize`) です。

3. **`mcp` パッケージ (Python MCP SDK)**

   `pip install 'mcp>=0.9'` で入ります。後述の「インストール」手順に同梱しています。

## 3. インストール

### 3.1. リポジトリ取得とライブラリビルド

```bash
git clone <task repo> task
cd task
make -C fp libs_pic
make -C fp libfpapi.so
```

### 3.2. MCP サーバのインストール

開発用 (editable) インストールを推奨します。

```bash
cd python/mcp-servers/fp_mcp
pip install -e .
```

これで `fp-mcp` コマンドが使えるようになります。また `python -m fp_mcp.server` でも同じ機能を呼び出せます。

> **Note:** `fplib` 自体はリポジトリ同梱の pure-Python パッケージです。`PYTHONPATH` に `<repo>/python` を通すか、`server.py` が自動で親パッケージを import できるようになっているので追加インストールは不要です。

### 3.3. 仮想環境を使いたい場合 (任意)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e python/mcp-servers/fp_mcp
```

## 4. 動作確認 (smoke test)

### 4.1. ヘルプ表示

まずコマンドが通ることを確認します。

```bash
python -m fp_mcp.server --help
```

使い方と環境変数がずらっと出れば OK です。

### 4.2. 登録ツール一覧の表示

```bash
python -m fp_mcp.server --print-tools
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
set_param
set_param_str
set_params
```

### 4.3. Python から直接叩く

`libfpapi.so` がビルド済みであれば、Python REPL で次のように動作確認できます。

```python
>>> from fp_mcp.server import handle_init, handle_run, handle_get_state
>>> handle_init()
'fp library initialized'
>>> handle_run(0)
'advanced 0 time step(s)'
>>> state = handle_get_state()
>>> state['NRMAX'], state['NSAMAX'], state['TIMEFP']
(50, 2, 0.0)
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
    "task-fp": {
      "command": "python",
      "args": ["-m", "fp_mcp.server"],
      "env": {
        "PYTHONPATH": "/absolute/path/to/task/python",
        "FPLIB_PATH": "/absolute/path/to/task/fp/libfpapi.so"
      }
    }
  }
}
```

保存して Claude Desktop を再起動すると、ツール一覧に `task-fp` が並びます。

### 5.2. Claude Code の場合

CLI から追加できます。

```bash
claude mcp add task-fp -- python -m fp_mcp.server
```

環境変数を渡したい場合は `--env` を使います。

```bash
claude mcp add task-fp \
  --env PYTHONPATH=/absolute/path/to/task/python \
  --env FPLIB_PATH=/absolute/path/to/task/fp/libfpapi.so \
  -- python -m fp_mcp.server
```

### 5.3. Cursor / VS Code など

いずれも MCP 対応エディタであれば、`command` と `args` を同じ要領で書けば動きます。

## 6. 使い方の例

登録が済んだら、Claude にそのまま話しかけてください。以下はチャットプロンプトの例です。

### 6.1. いちばん簡単な例

```
FP を初期化して、1 ステップ走らせて、現在の TIMEFP と NSAMAX を教えて。
```

LLM は `init → run(1) → get_state` の順にツールを呼び、`TIMEFP` と `NSAMAX` の値を返してくれます。

### 6.2. iter01 相当のパラメータ設定

```
FP を MODELG=3、NSMAX=3、NRMAX=40、NPMAX=50、NTHMAX=50、DELT=1.0e-3
で初期化して 2 ステップ走らせて、NSA=1 の RTT プロファイルを教えて。
```

LLM は内部で

```python
run_and_get_state(
    params={
        "MODELG": 3, "NSMAX": 3,
        "NRMAX": 40, "NPMAX": 50, "NTHMAX": 50,
        "DELT": 1.0e-3,
    },
    ntmax=2,
)
```

のような呼び出しに変換し、`profile[0]["RTT"]` を読み取って返してくれます。

### 6.3. 種族ごとのパラメータ設定 (配列)

```
PA を [1.0, 2.0, 12.0]、PZ を [-1, 1, 6] に設定してから 1 ステップ走らせて、
RNT の NSA=2 プロファイルを教えて。
```

LLM は `set_params(params={"PA": [1.0, 2.0, 12.0], "PZ": [-1, 1, 6]})` のように展開します (1-origin で `PA[1], PA[2], PA[3]` に割り当てられます)。

### 6.4. 利用可能パラメータの確認

```
FP で設定できるパラメータを一覧にして、波加熱関係のものだけ教えて。
```

LLM は `describe_parameters` を呼び、`group == "wave"` を抽出して返してくれます。

## 7. 提供ツール一覧

| ツール | 目的 | 主な引数 |
|---|---|---|
| `init` | ライブラリ初期化 | なし |
| `set_param` | 単一パラメータ設定 (数値) | `name`, `value` (配列要素は `NAME[i]`) |
| `set_param_str` | 文字列パラメータ設定 (`KNAMEQ`) | `name`, `value` |
| `set_params` | まとめて設定 (scalar / list / dict / str) | `params` |
| `run` | 時間ステップ進行 | `ntmax` (default=1) |
| `get_state` | 現在の状態取得 | なし |
| `finalize` | リソース解放 | なし |
| `describe_parameters` | パラメータ一覧・型・説明 + mesh caps | なし |
| `describe_state_schema` | `get_state` の JSON schema | なし |
| `run_and_get_state` | init + set + run + get_state を一括 | `params`, `ntmax` |

## 8. FP 固有の注意点

### 8.1. メッシュの上限 (コンパイル時定数)

`fp/fp_api.h` で以下が定義されています。`fp_state_t` の 2D プロファイル配列はここから派生し、超過する大きさでは動作しません。

| 定数 | 値 | 意味 |
|---|---|---|
| `FP_MAX_NRMAX` | 100 | 径方向メッシュの最大点数 |
| `FP_MAX_NSAMAX` | 8 | kinetic 種族の最大数 |

これを超えたいときは `fp/fp_api.h` を書き換えて `libfpapi.so` を再ビルドする必要があります。

プロファイル配列 (`RNT`, `RWT`, `RTT`, `RJT`, `RPCT`, `RPWT`) は C 側で `[FP_MAX_NSAMAX][FP_MAX_NRMAX]` として確保されますが、`get_state` の応答は実際に使われている `[0:NSAMAX][0:NRMAX]` 部分のみ返します (pure-Python の入れ子リスト)。

### 8.2. `fp_finalize` の非対称性 (既知の制限)

FP バックエンドには `fp_allocate` / `fp_deallocate` 非対称があります。すなわち、

- `fp_init` は FPCOMM 配列を確保する (1 回目のみ)。
- `fp_finalize` はライフサイクルフラグをクリアするだけで、配列の deallocate は行わない。

そのため、**1 プロセス内で `init → run → finalize → init → run → ...` を繰り返すと期待通りの初期状態に戻らない** ことがあります。サーバをクリーンに再起動したいときは、プロセスごと再起動してください。

これは `python/fplib/README.md` にも「Known limitations」として記載されている制限事項です。

### 8.3. `MODELG=3` は iter01 fixture の典型値

`test_run/inputs/fp_iter01.in` で使われている設定を踏襲する場合、`MODELG=3` が既定的な選択になります。ただし `MODELG=3` は**解析的平衡ではなく、平衡データファイルを読み込むパス**です。必ず `set_param_str("KNAMEQ", <file>)` で実在するファイルを指してください (8.4 参照)。`MODELG` を設定しなければ `pl_init` 既定の `MODELG=2` (解析的平衡) で動き、外部ファイルは不要です。他のモデル (`MODELG=0, 1, 5, 8, ...`) を選ぶと `fp_init` / `fp_prep` が `FP_ERR_CALC_FAILED` を返すこともあるので、`libfpapi.so` 側の対応状況を確認してください。

### 8.4. 文字列パラメータ (`KNAMEQ`) と EQ→FP 連携

`fp_set_param(const char* name, double value)` は `double` 値しか受け付けないため、文字列パラメータ用には別の C ABI エントリ `fp_set_param_str(const char* name, const char* value)` (`fp/fp_api.f90`) を使います。MCP からは `set_param_str` ツール、または `set_params` に `str` 値を渡す形で叩けます。

現在レジストリ (`fp/fp_param_registry.f90::fp_param_set_str`) が受け付ける名前は `KNAMEQ` のみです。これは `MODELG=3` のときに `eq_load` が読む平衡データファイル名で、EQ が書き出したファイルを FP に食わせる (EQ→FP 連携) ための入口になります。

```python
# eq_mcp 側で平衡を保存
eq.save(path="eq.bin")

# 同じ作業ディレクトリで fp_mcp を起動して読み込む
fp.set_param(name="MODELG", value=3)
fp.set_param_str(name="KNAMEQ", value="eq.bin")
fp.run(ntmax=2)
```

パスはサーバプロセスの cwd 基準で解決されます。`MODELG=3` を指定しつつ `KNAMEQ` が存在しないファイルを指していると、`eq_load` が失敗し、下流の `BESEKNX` が `NCALC=-2` を出して NaN が伝播します (`fp_param_registry.f90` のコメント参照)。`MODELG` を設定しない場合は `pl_init` 既定の `MODELG=2` (解析的平衡) で動くので、`KNAMEQ` は不要です。

なお `KNAMFP` など他の文字列パラメータはまだレジストリに CASE エントリがなく、`invalid parameter` になります。

### 8.5. `NSMAX` と `NSAMAX` の違い

- `NSMAX`: namelist で宣言されている種族の総数 (`PA`, `PZ` などの配列長を規定)。
- `NSAMAX`: kinetic に時間発展させる種族の数 (`FP_MAX_NSAMAX=8` が上限)。
- `NSBMAX`: 背景種族の数。

通常は `NSAMAX + NSBMAX <= NSMAX` を満たすよう設定します。

## 9. FAQ / トラブルシューティング

### Q1. `libfpapi.so not found` と言われます

- `make -C fp libs_pic && make -C fp libfpapi.so` を実行したかご確認ください。
- ビルド後、`ls fp/libfpapi.so` で `.so` が存在することを確認してください。
- それでもダメなら、環境変数 `FPLIB_PATH` に絶対パスを明示してください。

```bash
export FPLIB_PATH=/absolute/path/to/task/fp/libfpapi.so
```

### Q2. `ModuleNotFoundError: No module named 'fplib'` と言われます

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
- `NSMAX` の範囲内 (通常 `1..NSM=8`) に収まる index を使ってください。

### Q5. `calculation failed: ...` と返ってきました

- 入力値 (特に `NSMAX`, `NSAMAX`, `PA`, `PN`, `PT`, `DELT`) の整合性が崩れていないかご確認ください。
- `MODELG` 等のモデル選択が `libfpapi.so` でサポートされているか確認してください。
- いったんサーバをプロセスごと再起動してクリーンな状態にするのも有効です (`fp_finalize` の非対称性の影響を避けるため、§8.2 参照)。

### Q6. 複数のサーバプロセスを同時起動できますか

FP の Fortran 側は FPCOMM 単一状態なので、1 プロセス = 1 インスタンスが原則です。どうしても同時起動したい場合はプロセス毎に別ディレクトリ / 別 Python プロセスで立ち上げてください (仮想メモリ空間が分離されます)。

### Q7. `finalize` → `init` でリセットしたら結果が変です

§8.2 の通り `fp_finalize` は配列を deallocate しません。クリーンに再実行したい場合は MCP サーバ自体を再起動してください (Claude Desktop の場合は設定画面から停止 → 起動が楽です)。

### Q8. ログはどこで確認できますか

MCP サーバの標準エラー出力が LLM クライアントに渡ります。Claude Desktop なら「開発者ツール」相当のログビューア、Claude Code なら実行ターミナルで確認できます。

## 10. 参考資料

- MCP spec: <https://modelcontextprotocol.io/>
- Python MCP SDK: <https://github.com/modelcontextprotocol/python-sdk>
- fplib 本体の README: [`../../fplib/README.md`](../../fplib/README.md)
- FP C ABI ヘッダ: [`../../../fp/fp_api.h`](../../../fp/fp_api.h)
- FP パラメータ registry: [`../../../fp/fp_param_registry.f90`](../../../fp/fp_param_registry.f90)
- MCP 共通設計計画: `docs/superpowers/plans/2026-04-18-module-mcp-servers.md`
- リファレンス実装: [`../tr_mcp/README.md`](../tr_mcp/README.md)

問題・改善提案は PR / Issue でお願いします。
