# Module MCP Servers — 共通設計 + tr リファレンス実装

**Date:** 2026-04-18
**Status:** Draft (tr reference implementation in-flight; ti/wr/wrx/fp は follow-up)
**Applies to:** tr, ti, wr, wrx, fp (+ 後続 tot composer)

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:executing-plans`. 本計画は「共通設計」+「tr リファレンス実装」を 1 PR で着地させ、ti/wr/wrx/fp の MCP 実装は tr をコピーするだけで済むようにする。

---

## 1. Goal

TASK プロジェクトの各 Phase-L モジュール（現時点で `trlib`, `tilib`, `wrlib`, `wrxlib`, `fplib`）を LLM (Claude Desktop / Claude Code 等) から直接呼び出せるよう、[Model Context Protocol (MCP)](https://modelcontextprotocol.io/) に準拠した Python サーバをモジュール毎に 1 本用意する。

- **Phase 1 (this PR):** `tr` をリファレンス実装として完成させる。
- **Phase 2 (follow-up PRs):** tr をテンプレートに ti / wr / wrx / fp の 4 サーバを複製。
- **Phase 3 (deferred):** `tot` composer MCP — 複数モジュールを跨ぐオーケストレーションは別設計。

## 2. Why MCP

1. LLM は標準 JSON-RPC (over stdio) で MCP サーバと会話できる。Claude Desktop / Claude Code / Cursor などが既に対応。
2. Python MCP SDK (`pip install mcp`) の FastMCP デコレータ API はほぼボイラープレート無しでツール公開できる。
3. `python/<mod>lib/` は既に ctypes ラッパとして仕上がっており、MCP サーバはそれを薄く被せるだけ。Fortran にも Makefile にも手を入れない。

## 3. ディレクトリレイアウト

```
python/
├── <mod>lib/                # 既存: ctypes wrapper (L-5 成果物)
└── mcp-servers/
    ├── __init__.py          # (empty, namespace package marker)
    ├── tr_mcp/              # ← this PR のリファレンス実装
    │   ├── __init__.py
    │   ├── server.py        # FastMCP server (9 tools)
    │   ├── pyproject.toml   # mcp>=0.9,<2 + path dep on trlib
    │   ├── README.md        # 初心者向け使い方 (です・ます調)
    │   └── tests/
    │       ├── __init__.py
    │       └── test_server.py
    ├── ti_mcp/              # follow-up PR
    ├── wr_mcp/              # follow-up PR
    ├── wrx_mcp/             # follow-up PR
    └── fp_mcp/              # follow-up PR
```

- 各 `<mod>_mcp/` はインストール可能な Python パッケージとして自律的に動く (`pip install -e python/mcp-servers/<mod>_mcp`)。
- 既存 `python/<mod>lib/` を **path dependency** で参照し、`<mod>lib` 自体は編集しない。
- `python/mcp-servers/__init__.py` を置くことで `python/` を `PYTHONPATH` に通している既存ユーザも自然に発見できる。

## 4. 共通ツール API (9 tools per module)

| # | Tool | 引数 | 戻り値 | 役割 |
|---|---|---|---|---|
| 1 | `init` | — | `str` | ライブラリ初期化 (tr_init など) |
| 2 | `set_param` | `name: str, value: float` | `str` | 単一パラメータ設定 (配列要素は `NAME[i]`) |
| 3 | `set_params` | `params: dict[str, scalar \| list \| dict[int, value]]` | `str` | 複数パラメータ一括設定 |
| 4 | `run` | `ntmax: int = 1` | `str` | 時刻ステップ進行 |
| 5 | `get_state` | — | `dict` | 現在の状態を JSON-serializable dict で返却 |
| 6 | `finalize` | — | `str` | リソース解放 |
| 7 | `describe_parameters` | — | `dict` | サポートパラメータ一覧 (name, group, 型, description) |
| 8 | `describe_state_schema` | — | `dict` | `get_state` の JSON schema |
| 9 | `run_and_get_state` | `params: dict = None, ntmax: int = 1` | `dict` | init → set_params → run → get_state を 1 コールで |

### 設計判断のポイント

- **FastMCP vs low-level Server**: FastMCP デコレータ API を採用。型ヒントから JSON Schema を自動生成でき、後続モジュールへのコピーコストが最小化できる。low-level `mcp.server.Server` は async I/O を細かく触りたいケース専用で、今回は過剰。
- **Single instance per server**: TR/TI/… いずれも libxxxapi.so 内部に Fortran COMMON-block singleton を持つため、1 サーバプロセス＝ 1 ライブラリインスタンス方針。`init` は冪等にし、既に open ならそのまま ok を返す。
- **パラメータ Bulk API**: `set_params` の `dict` 値に対し、`scalar` / `list[float]`（1-origin で要素展開） / `dict[int, float]`（疎な index→value 指定）の 3 形態をサポート。LLM が「PN[1], PN[2] を設定して」のような自然言語で来ても対応しやすい。
- **Error mapping**: 各モジュールの `<Mod>libError` 階層をそのまま `mcp.server.fastmcp.exceptions.ToolError` に変換。`ierr=1 → "invalid parameter"` のようなメッセージで LLM 側にも復帰可能な情報を返す。
- **`describe_parameters` のデータソース**: `tr_param_registry.f90` を正とする（60+ エントリ）。本 PR ではハードコード dict で出す（将来、Fortran からの自動抽出に差し替え可）。`describe_state_schema` は `trlib.state.TrState` の dataclass から生成。

## 5. Dependencies

- `mcp>=0.9,<2` （Python MCP SDK, [GitHub](https://github.com/modelcontextprotocol/python-sdk)）。
- Path dep on `python/<mod>lib/` （例: `trlib`）。`pip install -e .` で local 開発インストール。
- Python 3.10+ を要求 (MCP SDK の最低ライン)。trlib 自体は 3.8+ だが MCP 側で 3.10+ に引き上げる。
- 追加の外部依存なし（numpy なども不要）。

## 6. エラー処理

| trlib 例外 | MCP 応答 | LLM への hint |
|---|---|---|
| `TrlibParamError` | `ToolError("invalid parameter: …")` | 名前/添字を直すよう誘導 |
| `TrlibStateError` | `ToolError("library not initialized: call init first")` | `init` ツール呼び出しを促す |
| `TrlibRunError` | `ToolError("calculation failed: …")` | 入力値の妥当性を確認 |
| `TrlibNotImplementedError` | `ToolError("feature not implemented: rebuild libtrapi.so")` | ライブラリ再ビルド |
| `FileNotFoundError (libtrapi.so)` | `ToolError("libtrapi.so not found: run 'make -C tr libtrapi.so'")` | ビルド手順案内 |

## 7. テスト戦略

各サーバ `tests/test_server.py` で以下を網羅:

1. **Pure-Python tests** — `mcp` / `<mod>lib` どちらも import 可能なら unconditional に通す:
   - `describe_parameters` / `describe_state_schema` 形状検証
   - ツール一覧 (9 つ) の登録確認
   - エラーマッピング検証（モック `<Mod>lib` でエラーを投げさせる）
2. **Integration tests** — `libtrapi.so` 存在時のみ実行（`unittest.skipIf(not Path(...).exists())`）:
   - 実 `Trlib` を使って `init → set_param(RR=6.5) → run(1) → get_state` のラウンドトリップ
   - `run_and_get_state` one-shot
3. MCP SDK には `mcp.testing` ユーティリティがあり、stdio を張らずに tool 呼び出しをテストできる（想定: `client.call_tool("init")` 風）。`mcp` 未インストール時は全テスト skip。

## 8. インストール & Claude Code / Desktop 登録

```jsonc
// ~/.config/claude-desktop/claude_desktop_config.json (macOS: ~/Library/Application Support/Claude/claude_desktop_config.json)
{
  "mcpServers": {
    "task-tr": {
      "command": "python",
      "args": ["-m", "tr_mcp.server"],
      "env": {
        "TRLIB_PATH": "/path/to/task/tr/libtrapi.so",
        "PYTHONPATH": "/path/to/task/python"
      }
    }
  }
}
```

Claude Code からは `claude mcp add task-tr -- python -m tr_mcp.server` で追加可能（詳細は README に）。

## 9. 検収基準 (tr リファレンス実装)

- [ ] `python3 -c "import ast; ast.parse(open('python/mcp-servers/tr_mcp/server.py').read())"` が通る
- [ ] `python3 -m py_compile python/mcp-servers/tr_mcp/server.py` が通る（`mcp` 未導入時は ImportError 扱いで OK）
- [ ] `pytest python/mcp-servers/tr_mcp/tests/` が緑。`mcp` / `libtrapi.so` の有無により skipIf で適切にスキップされる
- [ ] README に beginner-friendly な導入、登録手順、使用例、FAQ を含む
- [ ] Fortran / Makefile / 既存 Python ライブラリに差分なし

## 10. Follow-up (別 PR)

- `ti_mcp`, `wr_mcp`, `wrx_mcp`, `fp_mcp`: tr_mcp をコピーし、import と registry を差し替えるだけ。各 4 時間以内の見込み。
- `tot_mcp`: 複数モジュール横断オーケストレータ。`tot` library (設計検討中) と連携する想定で現段階では deferred。
- `describe_parameters` の自動生成: `tr_param_registry.f90` をパースして dict を build-time 生成する。
- MCP server 側でのロギング: `mcp.server.fastmcp.FastMCP(logger=...)` に task 標準 logger を差す。

## 11. 非スコープ

- Fortran / C ABI / Makefile 変更は一切しない。
- 複数インスタンス同時実行 (multi-tenant) は非対応。singleton 前提。
- 非同期 I/O (async run) は非対応。`run` は同期ブロッキング。
- グラフィクス / ファイル出力は公開しない（`tr2` CLI 専用のまま）。

## 12. References

- MCP spec: https://modelcontextprotocol.io/
- Python SDK: https://github.com/modelcontextprotocol/python-sdk
- trlib design: `docs/superpowers/specs/2026-04-17-tr-library-design.md`
- trlib arch: `docs/tr-library/architecture.md`
- trlib README: `python/trlib/README.md`
