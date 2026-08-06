# MCP サーバ (`wr_mcp`)

`wr_mcp` は TASK/WR を **Claude Desktop / Claude Code / Cursor などの LLM
クライアント** から直接操作できるようにする, **Model Context Protocol
(MCP)** 対応のサーバです.

```{admonition} このページの位置付け
:class: note

入門者向けの完全ガイドは `python/mcp-servers/wr_mcp/README.md` にあります.
本ページはその要約です. MCP プロトコル全般の解説は `tr` モジュールの
MCP サーバページ (`docs/sphinx/modules/tr/ja/mcp.md`) を参照.
```

## 前提条件

1. **Python 3.10 以上**
2. **`libwrapi.so` がビルド済み** (`make -C wr libwrapi.so`)
3. **`mcp` パッケージ** (`pip install 'mcp>=0.9,<2'`)

## インストール

```bash
cd python/mcp-servers/wr_mcp
pip install -e .
```

## 動作確認

```bash
python -m wr_mcp.server --help
python -m wr_mcp.server --print-tools
wr-mcp doctor
```

## LLM クライアントへの登録

### Claude Desktop

```json
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

### Claude Code

```bash
claude mcp add task-wr \
  --env PYTHONPATH=/absolute/path/to/task/python \
  --env WRLIB_PATH=/absolute/path/to/task/wr/libwrapi.so \
  -- python -m wr_mcp.server
```

または `wr-mcp install --client claude-code --scope project`.

## 提供ツール一覧

`wr_mcp` は **9 個** のツールを公開します.

| ツール | 目的 | 主な引数 |
|---|---|---|
| `init` | ライブラリ初期化 | なし |
| `set_param` | パラメータ設定 | `name`, `value` |
| `set_params` | まとめて設定 | `params` |
| `run` | レイトレース実行 | `nray_request` (default=0) |
| `get_state` | 現在の状態取得 | なし |
| `finalize` | リソース解放 | なし |
| `describe_parameters` | パラメータ一覧 (103 個) | なし |
| `describe_state_schema` | 戻り値 schema | なし |
| `run_and_get_state` | 一括実行 | `params`, `nray_request` |

## 使い方の例

### 例 1: ECRH パワー堆積位置の確認

> WR を初期化して RR=6.2, BB=5.3, RF=170e9, RPI=8.0, ZPI=0.0 で 1 本の
> レイをトレースして, ピーク堆積位置 (pos_pwrmax_rs) を教えて.

LLM は `run_and_get_state(params={"RR": 6.2, "BB": 5.3, "RF": 170e9,
"RPI": 8.0, "ZPI": 0.0}, nray_request=1)` を呼び, `scalars.pos_pwrmax_rs` を返します.

### 例 2: 周波数スキャン

> RF を 100, 140, 170, 200 GHz で走らせて, それぞれのピーク堆積位置を比較して.

LLM は 4 回 `run_and_get_state` を呼び表組みします. ECRH の周波数調整に
使えます.

### 例 3: ビーム近似

> NRAYMAX=5 でレイを Z 方向に -0.1 から 0.1 まで分散させて, 5 本の合計
> 吸収プロファイルを返して.

LLM は `set_param("ZPIN[1]", -0.1)`, `ZPIN[2]=-0.05`, ... と設定して
`run(nray_request=5)`, `state.pwr_nrs` を返します.

## アーキテクチャ的な注意点

### `run` の引数

`tr`/`ti`/`fp` の `run(ntmax)` と違って **`run(nray_request)` はレイ本数**
です. `nray_request=0` だと `NRAYMAX` の値を使います.

### シングルトン制約

`wr` は `pl_*` 状態を `tr`, `eq`, `ti`, `fp` と共有. 同一プロセスで他の
`*_mcp` と同時起動できません.

### `wr` vs `wrx`

LLM が選択するときの目安:

- 高速簡易解析 → `wr_mcp`
- ビーム形状の精密モデル → `wrx_mcp`

## トラブルシューティング (要約)

| 症状 | 対処 |
|---|---|
| `libwrapi.so not found` | `make -C wr libwrapi.so` 後, `WRLIB_PATH` を絶対パス |
| レイが途中で止まる | `NSTPMAX`, `UUMIN` を調整 ({doc}`faq` Q4) |
| ピークパワーが 0 | 周波数 `RF` と入射条件を確認 ({doc}`faq` Q5) |
| 結果が `wrx2` と異なる | `wrlib_equivalence` で確認 |

## 参考資料

- **MCP 仕様**: <https://modelcontextprotocol.io/>
- **完全ガイド**: `python/mcp-servers/wr_mcp/README.md`
- **`wrlib` README**: `python/wrlib/README.md`
