# MCP サーバ (`fp_mcp`)

`fp_mcp` は TASK/FP を **Claude Desktop / Claude Code / Cursor などの LLM
クライアント** から直接操作できるようにする, **Model Context Protocol
(MCP)** 対応のサーバです.

```{admonition} このページの位置付け
:class: note

入門者向けの完全ガイドは `python/mcp-servers/fp_mcp/README.md` にあります.
本ページはその要約です. MCP プロトコル全般の解説は `tr` モジュールの
MCP サーバページ (`docs/sphinx/modules/tr/ja/mcp.md`) を参照.
```

## 前提条件

1. **Python 3.10 以上**
2. **`libfpapi.so` がビルド済み** (`make -C fp libfpapi.so`)
3. **`mcp` パッケージ** (`pip install 'mcp>=0.9,<2'`)
4. **十分な RAM** — 5D グリッドのため数百 MB〜数 GB 必要

## インストール

```bash
cd python/mcp-servers/fp_mcp
pip install -e .
```

## 動作確認

```bash
python -m fp_mcp.server --help
python -m fp_mcp.server --print-tools
fp-mcp doctor
```

## LLM クライアントへの登録

### Claude Desktop

```json
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

### Claude Code

```bash
claude mcp add task-fp \
  --env PYTHONPATH=/absolute/path/to/task/python \
  --env FPLIB_PATH=/absolute/path/to/task/fp/libfpapi.so \
  -- python -m fp_mcp.server
```

または `fp-mcp install --client claude-code --scope project`.

## 提供ツール一覧

`fp_mcp` は **9 個** のツールを公開します. C ABI レベルでは
`fp_set_param_str` がありますが MCP には現時点で公開されていません
(`KNAMEQ` を変更したい場合は MCP 経由ではなく事前に環境を整えて
ください).

| ツール | 目的 | 主な引数 |
|---|---|---|
| `init` | ライブラリ初期化 | なし |
| `set_param` | パラメータ設定 | `name`, `value` |
| `set_params` | まとめて設定 | `params` |
| `run` | 時間ステップ進行 | `ntmax` |
| `get_state` | 現在の状態取得 | なし |
| `finalize` | リソース解放 | なし |
| `describe_parameters` | パラメータ一覧 | なし |
| `describe_state_schema` | 戻り値 schema | なし |
| `run_and_get_state` | 一括実行 | `params`, `ntmax` |

## 使い方の例

### 例 1: NBI 高速イオンの分布計算

> FP を初期化して, NSAMAX=2 で MODEL_NBI=1 を有効にして 10 ステップ走らせ,
> 1 番目 active species の RTT (温度プロファイル) を返して.

LLM は `MODEL_NBI=1`, `NSAMAX=2` を `set_params` で設定し, `run(ntmax=10)`
の後 `state.RTT[0]` を取得します.

### 例 2: LH 駆動電流

> LH 波の吸収パワー PABS_LH=2.0 で MODEL_WAVE=1 を有効にして 5 ステップ
> 走らせ, RJT (電流密度) の体積積分を計算して.

LLM は `set_params(PABS_LH=2.0, MODEL_WAVE=1)`, `run(ntmax=5)`,
`state.RJT[0]` を `state.nrmax` 個の半径点で積分.

### 例 3: グリッド解像度の比較

> NPMAX を 50 と 100 で走らせて, 結果の精度がどう違うか教えて.

LLM は 2 回 `run_and_get_state` を呼び, RTT の差分を比較します.

## アーキテクチャ的な注意点

### メモリ消費の見積もり

5D グリッドのため, MCP サーバプロセスのメモリ消費が大きい:

```
RAM ≈ NRMAX × NPMAX × NTHMAX × NSAMAX × 800 bytes
```

LLM が `NPMAX=200` などを試すと簡単に GB 単位になります. **`describe_parameters`
で範囲を確認してから動かす** のが安全です.

### シングルトン制約

`fp` は `pl_*` 状態を `tr`, `eq`, `ti` と共有. 同一プロセスで他の `*_mcp`
と同時起動できません.

### `validate` がない

`fp` は `validate` API を実装していません. パラメータエラーは `run` 時の
`FplibCalcFailedError` で初めて検出されます. LLM が試行錯誤するときの
リトライコストに注意.

## トラブルシューティング (要約)

| 症状 | 対処 |
|---|---|
| `libfpapi.so not found` | `make -C fp libfpapi.so` 後, `FPLIB_PATH` を絶対パス設定 |
| `MemoryError` | `NPMAX`/`NTHMAX` を下げる |
| 結果が `fpx2` と異なる | `fplib_equivalence` で確認 |
| 計算が遅い | `LMAXFP`/`EPSFP` を緩めるか, グリッド解像度を下げる |

## 参考資料

- **MCP 仕様**: <https://modelcontextprotocol.io/>
- **完全ガイド**: `python/mcp-servers/fp_mcp/README.md`
- **`fplib` README**: `python/fplib/README.md`
