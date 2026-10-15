# MCP サーバ (`eq_mcp`)

`eq_mcp` は TASK/EQ を **Claude Desktop / Claude Code / Cursor などの LLM
クライアント** から直接操作できるようにする, **Model Context Protocol
(MCP)** 対応のサーバです (PR #167). 内部では `python/eqlib` (ctypes ラッパ)
を薄く被せた構造で, `libeqapi.so` を LLM の「道具箱」として差し出す
イメージになります.

```{admonition} このページの位置付け
:class: note

入門者向けの完全ガイドは `python/mcp-servers/eq_mcp/README.md` にあります.
本ページはその要約 + 簡単な使い方リファレンスです. MCP プロトコル全般の
解説は `tr` モジュールの MCP サーバページ
(`docs/sphinx/modules/tr/ja/mcp.md`) も参照.
```

## アーキテクチャ

```text
┌────────────────┐     JSON-RPC      ┌─────────────────────┐
│  LLM client    │ ─────────────────▶│   MCP サーバ         │
│ (Claude 等)    │◀───────────────── │ (この eq_mcp)       │
└────────────────┘                   │   init/run/...      │
                                     └────────┬────────────┘
                                              │ ctypes
                                              ▼
                                     ┌─────────────────────┐
                                     │  eq/libeqapi.so     │
                                     │  (Fortran backend)  │
                                     └─────────────────────┘
```

`tr_mcp` との違い:

- **`set_param_str`** ツールが追加 — `KNAMEQ` (EQDSK ファイル名) などの
  文字列パラメータ用. `tr` も最近対応しましたが eq では設計初期から必須.
- **`validate`** ツールが独立 — 事前検証 (PR #164) を専用エンドポイントで
  公開. LLM が EQDSK ファイル不在などを `run` 前に検出できる.
- ツール総数 **11 個** (tr は 9 個).

## 前提条件

1. **Python 3.10 以上**
2. **`libeqapi.so` がビルド済み** (`make -C eq libeqapi.so`)
3. **`mcp` パッケージ** (`pip install 'mcp>=0.9,<2'`)

## インストール

```bash
cd python/mcp-servers/eq_mcp
pip install -e .
```

これで `eq-mcp` コマンド と `python -m eq_mcp.server` が使えるようになります.

## 動作確認

### コマンドが通ることの確認

```bash
python -m eq_mcp.server --help
```

### 登録ツール一覧の表示

```bash
python -m eq_mcp.server --print-tools
```

11 ツールが並びます (詳細は下記の「提供ツール一覧」参照).

### 環境ヘルスチェック

```bash
eq-mcp doctor
```

`mcp` パッケージ, `eq_mcp` / `eqlib` の import 可否, `libeqapi.so` の有無,
推奨設定ファイルの場所を JSON で返します.

### Python から直接叩く

```python
>>> from eq_mcp.server import handle_init, handle_run, handle_get_state
>>> handle_init()
'eq library initialized'
>>> # set_param_str("KNAMEQ", "eqdata.ITER01") ... の後
>>> handle_run(1)   # mode=1 (KNAMEQ 読み込み)
'equilibrium loaded with mode=1'
>>> state = handle_get_state()
>>> state['scalars']['raxis'], state['scalars']['qaxis']
(6.4321, 0.9876)
```

## LLM クライアントへの登録

### Claude Desktop

設定ファイル (`claude_desktop_config.json`) に追加:

```json
{
  "mcpServers": {
    "task-eq": {
      "command": "python",
      "args": ["-m", "eq_mcp.server"],
      "env": {
        "PYTHONPATH": "/absolute/path/to/task/python",
        "EQLIB_PATH": "/absolute/path/to/task/eq/libeqapi.so"
      }
    }
  }
}
```

`KNAMEQ` で読み込む EQDSK ファイルもアクセス可能なディレクトリに配置
(または絶対パス指定) してください.

### Claude Code

```bash
claude mcp add task-eq \
  --env PYTHONPATH=/absolute/path/to/task/python \
  --env EQLIB_PATH=/absolute/path/to/task/eq/libeqapi.so \
  -- python -m eq_mcp.server
```

または `eq-mcp install`:

```bash
eq-mcp install --client claude-code --scope project
```

### Cursor / VS Code

```bash
eq-mcp install --client cursor --scope project
eq-mcp install --client cursor --scope user
```

## 提供ツール一覧

`eq_mcp` は **11 個** のツールを公開します.

| ツール | 目的 | 主な引数 |
|---|---|---|
| `init` | ライブラリ初期化 (`eq_init`) | なし |
| `set_param` | 数値パラメータ設定 | `name`, `value` (配列は `NAME[i]`) |
| `set_param_str` | **文字列パラメータ設定 (EQ 固有)** | `name`, `value` (`KNAMEQ` 等 7 種) |
| `set_params` | まとめて設定 (dict) | `params` |
| `run` | 平衡計算実行 (`eq_run`) | `mode` (default=1) |
| `get_state` | 現在の状態取得 (`eq_get_state`) | なし |
| `validate` | **事前検証 (EQ 強み)** | なし |
| `finalize` | リソース解放 (`eq_finalize`) | なし |
| `describe_parameters` | パラメータ一覧・型・グループ | なし |
| `describe_state_schema` | `get_state` 戻り値の JSON schema | なし |
| `run_and_get_state` | `init + set + validate + run + get_state` を一括 | `params`, `string_params`, `mode` |

`set_param_str` と `validate` の 2 つが eq の特徴です. `tr_mcp` には
`set_param_str` がなく, `validate` も後発の追加機能でした.

## 使い方の例

### 例 1: 解析的トロイダル幾何 (KNAMEQ 不要)

> EQ を初期化して, RR=6.5, BB=5.3, RIP=1.5 で平衡を解いて, 磁気軸位置と
> qaxis を教えて.

LLM は内部で `run_and_get_state(params={"RR": 6.5, "BB": 5.3, "RIP": 1.5}, mode=1)`
を呼び, `scalars.raxis` と `scalars.qaxis` を返します. `MODELG=2` 既定なので
`KNAMEQ` 不要.

### 例 2: EQDSK ファイルから読み込み

> ITER の EQDSK ファイル `eqdata.ITER01` を読み込んで平衡を構築し,
> beta_t と pvol を教えて.

LLM は `MODELG=3` を `set_param`, `KNAMEQ="eqdata.ITER01"` を
`set_param_str`, そして `validate` でファイル存在を確認してから `run`.

### 例 3: 事前検証

> 今のパラメータ設定で run できる状態か事前検査して.

LLM は `validate` を呼び, 診断 (FILE_MISSING, OUT_OF_RANGE 等) のリストを
表示します. EQDSK ファイル探しなどでループに陥るのを防げます.

### 例 4: パラメータスキャン

> RR を 5.0, 6.0, 7.0 の 3 点で走らせて, それぞれ raxis, qaxis, betat を
> 比較して.

LLM は 3 回の `run_and_get_state` を呼んで結果を表組みします.

## アーキテクチャ的な注意点

### シングルトン制約

EQ も `tr` 同様 1 プロセス 1 インスタンスです ({doc}`faq` Q6). 複数同時に
走らせたい場合は別プロセスで立ち上げてください.

### `eqdata` ファイルへの依存

`MODELG=3,5,8` で `KNAMEQ` を指定する場合, MCP サーバの **カレント
ディレクトリ** にそのファイルがある必要があります. Claude Desktop から
起動するときは `cwd` を環境変数で固定するか, 絶対パスでファイルを
指定してください.

### `validate` の積極利用

`tr_mcp` にもありますが, `eq` では特に効果的です. EQDSK ファイルの存在,
グリッド寸法 (`NRGMAX`, `NPSMAX` 等の 10 個) のコンパイル時最大値超過を
**`run` を呼ばずに** 検出できます. パラメータを大量に振る LLM ワーク
フローではトークンとリトライの節約に直結します.

## トラブルシューティング (要約)

| 症状 | 対処 |
|---|---|
| `libeqapi.so not found` | `make -C eq libeqapi.so` 後, `EQLIB_PATH` を絶対パスで設定 |
| `ModuleNotFoundError: eqlib` | `PYTHONPATH` にリポジトリ `python/` を追加 |
| `ModuleNotFoundError: mcp` | `pip install 'mcp>=0.9,<2'`. 仮想環境を確認 |
| `EQDSK file missing` | `KNAMEQ` のファイルがカレントディレクトリにあるか確認 |
| `EqlibCalculationFailedError: ierr=3` | 入力パラメータの物理整合性, EPSEQ や NLPMAX を緩める |

## 参考資料

- **MCP 仕様**: <https://modelcontextprotocol.io/>
- **Python MCP SDK**: <https://github.com/modelcontextprotocol/python-sdk>
- **完全ガイド**: `python/mcp-servers/eq_mcp/README.md`
- **`eqlib` README**: `python/eqlib/README.md`
