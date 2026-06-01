# ADR 0007: MCP / エージェント・ツール呼び出しの計装（`gen_ai.*` の延長）

- ステータス: 採用（FlowNote では未使用・将来/転用向けの規約）
- 日付: 2026-06-01

## 背景

FlowNote 本体は MCP（Model Context Protocol）を使わないが、本リポジトリの真の成果物は「ログ/可観測性の規約」であり、エージェント（incident management agent 等）への転用が想定される。エージェントは **LLM 呼び出し + ツール（MCP tool）呼び出し**のループで動くため、ツール呼び出しを観測する規約が要る。既存の GenAI 計装（[genai-observability.md](../observability/genai-observability.md)・`flownote.ai.use_case`）は良い基盤になる。

## 決定

MCP/エージェントのツール呼び出しは **`gen_ai.*` の延長として span 化**し、以下の属性を付与する（OTel GenAI semconv の MCP/tool 拡張に整合させる）:

| 属性 | 内容 |
|---|---|
| `gen_ai.operation.name` | `execute_tool`（ツール実行 span の操作名） |
| `gen_ai.tool.name` / `mcp.tool.name` | ツール名（低カーディナリティ） |
| `mcp.server.name` | 接続先 MCP サーバ識別 |
| `mcp.tool.duration` | ツール実行時間（**秒**・UCUM `s`。[logging-spec §4.1](../observability/logging-spec.md) の単位規約に従う） |
| `error.type` | 失敗分類（`none` なら成功） |
| `flownote.ai.use_case` | 業務ユースケース（既存枠を流用） |

LLM 呼び出し span（`chat`）の子として tool span をぶら下げ、1エージェント・ターンを1トレースに束ねる。ツール入出力の本文は GenAI 同様に**既定オフ＋マスク＋トランケート**（[redaction-policy](../observability/redaction-policy.md)）。

## 理由

- 既存 `GenAIInstrumentation.call(...)` と同じ計装スタイルで統一でき、SigNoz 等で LLM とツールを1トレースで相関閲覧できる。
- OTel GenAI semconv が MCP/tool 方向に拡張されており、独自属性を最小化できる（`mcp.*` は補助）。

## 留意 / リスク

- ツール名は低カーディナリティに保つ（引数値は span 属性にせず、必要ならハッシュ/要約）。
- 本実装は転用時に `packages/observability-py` 側へ `gen_ai.operation.name="execute_tool"` を扱う薄いヘルパとして追加する（FlowNote には現状不要）。

## 代替案

- 独自 `tool.*` 名前空間で計装 → GenAI トレースと相関しづらい。`gen_ai.*` 延長を優先。
