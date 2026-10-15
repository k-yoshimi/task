# MCP サーバ (`ti_mcp`)

`ti_mcp` は TASK/TI を **Claude Desktop / Claude Code / Cursor などの LLM
クライアント** から直接操作できるようにする, **Model Context Protocol
(MCP)** 対応のサーバです.

```{admonition} このページの位置付け
:class: note

入門者向けの完全ガイドは `python/mcp-servers/ti_mcp/README.md` にあります.
本ページはその要約です. MCP プロトコル全般の解説は `tr` モジュールの
MCP サーバページ (`docs/sphinx/modules/tr/ja/mcp.md`) も参照.
```

## 前提条件

1. **Python 3.10 以上**
2. **`libtiapi.so` がビルド済み** (`make -C ti libtiapi.so`)
3. **`mcp` パッケージ** (`pip install 'mcp>=0.9,<2'`)

## インストール

```bash
cd python/mcp-servers/ti_mcp
pip install -e .
```

## 動作確認

```bash
python -m ti_mcp.server --help
python -m ti_mcp.server --print-tools
ti-mcp doctor
```

## LLM クライアントへの登録

### Claude Desktop

```json
{
  "mcpServers": {
    "task-ti": {
      "command": "python",
      "args": ["-m", "ti_mcp.server"],
      "env": {
        "PYTHONPATH": "/absolute/path/to/task/python",
        "TILIB_PATH": "/absolute/path/to/task/ti/libtiapi.so"
      }
    }
  }
}
```

### Claude Code

```bash
claude mcp add task-ti \
  --env PYTHONPATH=/absolute/path/to/task/python \
  --env TILIB_PATH=/absolute/path/to/task/ti/libtiapi.so \
  -- python -m ti_mcp.server
```

または `ti-mcp install --client claude-code --scope project`.

### Cursor

```bash
ti-mcp install --client cursor --scope project
```

## 提供ツール一覧

`ti_mcp` は **9 個** のツールを公開します (`tr_mcp` と同じ構成. `set_param_str`
や `validate` は ti には未実装なので持ちません).

| ツール | 目的 | 主な引数 |
|---|---|---|
| `init` | ライブラリ初期化 | なし |
| `set_param` | 単一パラメータ設定 | `name`, `value` (配列は `NAME[i]`) |
| `set_params` | まとめて設定 | `params` |
| `run` | 時間ステップ進行 | `ntmax` (default=1) |
| `get_state` | 現在の状態取得 | なし |
| `finalize` | リソース解放 | なし |
| `describe_parameters` | パラメータ一覧・型・説明 | なし |
| `describe_state_schema` | `get_state` 戻り値の JSON schema | なし |
| `run_and_get_state` | `init + set + run + get_state` を一括 | `params`, `ntmax` |

## 使い方の例

### 例 1: 単純な実行

> TI を初期化して RR=6.5, BB=5.3, NSMAX=2 で 10 ステップ走らせて, T と
> 残差を教えて.

LLM は内部で `run_and_get_state(params={"RR": 6.5, "BB": 5.3, "NSMAX": 2}, ntmax=10)`
を呼び, `scalars.T` と `scalars.residual_loop_max` を返します.

### 例 2: 加熱モデル切替

> NBI を有効にして RR=6.5 で 10 ステップ走らせ, BETA プロファイルの
> 中央値を教えて.

LLM は `MODEL_NB=1` を `set_param`, `RR=6.5` を `set_params`, 走らせて
`state.BETA[0]` (軸付近) を返します.

### 例 3: 輸送モデルの比較

> MODEL_KAI を 31 (CDBM) と 140 (mBgB) で走らせて, それぞれ 50 ステップ
> 後の T と残差を比較して.

LLM は 2 回 `run_and_get_state` を呼んで結果を表組みします.

## アーキテクチャ的な注意点

### シングルトン制約 (tr/eq との衝突)

`ti` は `tr`, `eq` と共通のプラズマ状態 (`pl_*`) を握ります. 同一プロセスで
`ti_mcp` と `tr_mcp` を **両方ロードすると衝突します**. 別々のプロセスで
立ち上げてください ({doc}`faq` Q2).

### `validate` がないので慎重に

`tr_mcp` / `eq_mcp` と違って ti には事前検証 API がありません. 不正な
パラメータは `run` 時に `TilibRunError` で初めて検出します.
LLM が大量パラメータを試す場合は計算時間に注意.

## トラブルシューティング (要約)

| 症状 | 対処 |
|---|---|
| `libtiapi.so not found` | `make -C ti libtiapi.so` 後, `TILIB_PATH` を絶対パス設定 |
| `ModuleNotFoundError: tilib` | `PYTHONPATH` にリポジトリ `python/` を追加 |
| `MAXLOOP reached` | `DT` を小さくする, `MAXLOOP` を増やす ({doc}`faq` Q6) |
| 結果が `tr` と異なる | ti は補助物理を含むので tr と一致しないのは正常. ベースライン比較は `tilib_equivalence` で |

## 参考資料

- **MCP 仕様**: <https://modelcontextprotocol.io/>
- **完全ガイド**: `python/mcp-servers/ti_mcp/README.md`
- **`tilib` README**: `python/tilib/README.md`
