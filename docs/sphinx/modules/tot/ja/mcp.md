# MCP サーバ (`tot_mcp`)

`tot_mcp` は TASK/TOT を **Claude Desktop / Claude Code / Cursor などの LLM
クライアント** から直接操作できるようにする, **Model Context Protocol
(MCP)** 対応のサーバです. **1 つのサーバで全サブモジュールを統合操作**
できるのが最大の強み.

```{admonition} このページの位置付け
:class: note

入門者向けの完全ガイドは `python/mcp-servers/tot_mcp/README.md` にあります.
本ページはその要約です. MCP プロトコル全般の解説は `tr` モジュールの
MCP サーバページ (`docs/sphinx/modules/tr/ja/mcp.md`) を参照.
```

## 前提条件

1. **Python 3.10 以上**
2. **`libtotapi.so` がビルド済み** (`make -C tot libtotapi.so`)
3. **`mcp` パッケージ**
4. **十分な RAM** — 全モジュールロードのため数 GB 必要な場合あり

## インストール

```bash
cd python/mcp-servers/tot_mcp
pip install -e .
```

## 動作確認

```bash
python -m tot_mcp.server --help
python -m tot_mcp.server --print-tools
tot-mcp doctor
```

## LLM クライアントへの登録

### Claude Desktop

```json
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

### Claude Code

```bash
claude mcp add task-tot \
  --env PYTHONPATH=/absolute/path/to/task/python \
  --env TOTLIB_PATH=/absolute/path/to/task/tot/libtotapi.so \
  -- python -m tot_mcp.server
```

または `tot-mcp install --client claude-code --scope project`.

## 提供ツール一覧

`tot_mcp` は **10 個** のツールを公開. パラメータ名にプレフィックスを使うのが
他モジュールとの違い.

| ツール | 目的 | 主な引数 |
|---|---|---|
| `init` | tot + 全サブモジュール初期化 | なし |
| `set_param` | プレフィックス付きパラメータ設定 | `name` (例: `"eq:RR"`), `value` |
| `set_params` | まとめて設定 | `params` (例: `{"eq:RR": 6.5, "tr:NSMAX": 2}`) |
| `run` | 統合シミュレーション実行 | `ntmax` |
| `get_state` | 統合状態取得 | なし |
| `finalize` | 全モジュール解放 | なし |
| `describe_parameters` | プレフィックス + パラメータ一覧 | なし |
| `describe_state_schema` | TotState 戻り値 schema | なし |
| `run_and_get_state` | 一括実行 | `params`, `ntmax` |
| `run_pipeline` | 複数モジュールをスカラー結合で順に実行 (`totlib.TotPipeline`). `params` の文字列値は各モジュール自身の文字列設定に渡るので `fp:KNAMEQ` もここで設定できる | `steps`, `params` |

## 使い方の例

### 例 1: 統合シミュレーションの最短形

> TOT を初期化して eq:RR=6.5, eq:BB=5.3, tr:NSMAX=2 で 10 ステップ
> 走らせて, T と BETAN を教えて.

LLM は `set_params({"eq:RR": 6.5, "eq:BB": 5.3, "tr:NSMAX": 2})`,
`run(ntmax=10)`, `state.scalars` を取得します.

### 例 2: ECRH を入れた統合解析

> ITER の EQDSK ファイル `eqdata.ITER01` を読み込んで, ECRH 170 GHz の
> レイトレース結果を反映した輸送計算を 50 ステップ走らせて, BETAN の
> 時間発展を教えて.

LLM は:

```python
{
    "eq:MODELG": 3,
    "eq:KNAMEQ": "eqdata.ITER01",
    "tr:NSMAX": 2,
    "wr:RF": 170e9,
    "wr:RPI": 8.5,
}
```

を渡し, `run(ntmax=50)` を呼び `state.scalars["BETAN"]` を返します.

### 例 3: presence フラグの確認

> 各モジュールが正しくロードされているか教えて.

LLM は `state.tr_present`, `state.fp_present`, `state.wr_present` 等を
返します. 0 のモジュールは init に失敗しています.

### 例 4: パラメータの存在チェック

> tot で使えるパラメータを一覧して, eq モジュールに関するものだけ教えて.

LLM は `describe_parameters` で全パラメータを取得し, `eq:` プレフィックスで
始まるものを抽出します.

## アーキテクチャ的な注意点

### プレフィックス必須

`set_param("RR", 6.5)` は **エラー**. `set_param("eq:RR", 6.5)` または
`set_param("tr:RR", 6.5)` などプレフィックス必須です. LLM が間違えやすい
ポイントなので, `describe_parameters` で確認してから使うのが安全.

### 大きなメモリ消費

全モジュールを抱えるため, `tot_mcp` プロセスのメモリ消費は単独より
大きい (典型的に 500MB–2GB). LLM が `fp:NPMAX` などを増やすと急激に
増えるので注意.

### サーバ多重化禁止

`tot_mcp` と `tr_mcp` などの単独 MCP は **同一プロセスで併用不可**.
独立したクライアント設定で立ち上げ直す必要があります.

## トラブルシューティング (要約)

| 症状 | 対処 |
|---|---|
| `libtotapi.so not found` | `make -C tot libtotapi.so` 後, 全サブモジュールが PIC ビルド済みか確認 |
| `<mod>_present = 0` | サブモジュールの `.so` がビルド済みか確認 |
| `Invalid parameter` (プレフィックス) | `describe_parameters` で利用可能名を確認 |
| MemoryError | `fp:NPMAX`, `fp:NTHMAX` などを抑える |

## 参考資料

- **MCP 仕様**: <https://modelcontextprotocol.io/>
- **完全ガイド**: `python/mcp-servers/tot_mcp/README.md`
- **`totlib` README**: `python/totlib/README.md`
