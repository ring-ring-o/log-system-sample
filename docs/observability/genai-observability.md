# GenAI 可観測性（AI呼び出しのログ・トレース・メトリクス）

> 生成AI（OpenAI互換 / vLLM上の qwen・gemma を想定、開発時はモック）呼び出しの観測規約。
> 基本規約は[ログ規約(SSOT)](./logging-spec.md)、機密の扱いは[マスキング規約](./redaction-policy.md)に従う。

## 1. なぜ AI を特別扱いするか

AI 呼び出しは通常のHTTPと異なり、**コスト（トークン）・レイテンシ・品質・プロンプト機密性**という固有の観測軸を持つ。これらを規格化しないと、コスト超過・遅延・プロンプト漏洩・品質劣化を検知できない。OTel の **GenAI Semantic Conventions** に準拠する。

## 2. span 設計

AI 呼び出しは1つの span（`gen_ai.*` 属性付き）で表す。span 名は `{operation} {model}`（例: `chat qwen2.5`）。

| 属性 | 必須 | 説明 | 例 |
|---|---|---|---|
| `gen_ai.operation.name` | ✅ | 操作種別 | `chat` / `embeddings` |
| `gen_ai.system` | ✅ | プロバイダ系統 | `openai`（互換）/ `vllm` |
| `gen_ai.request.model` | ✅ | 要求モデル | `qwen2.5-7b-instruct` |
| `gen_ai.response.model` | ✅ | 応答モデル | `qwen2.5-7b-instruct` |
| `gen_ai.request.temperature` | 任意 | サンプリング温度 | `0.2` |
| `gen_ai.request.max_tokens` | 任意 | 最大トークン | `512` |
| `gen_ai.usage.input_tokens` | ✅ | 入力トークン数 | `1024` |
| `gen_ai.usage.output_tokens` | ✅ | 出力トークン数 | `256` |
| `gen_ai.response.finish_reasons` | 任意 | 終了理由 | `["stop"]` |
| `gen_ai.response.id` | 任意 | 応答ID | `chatcmpl-...` |
| `flownote.ai.use_case` | ✅ | 業務ユースケース | `task_consult` / `unified_search` / `progress_review` |
| `error.type` | エラー時 | 失敗分類 | `timeout` / `rate_limit` / `upstream_5xx` |

## 3. プロンプト・補完のログ方針（最重要）

プロンプト/補完には**ユーザーの機密・PII が混入しうる**。原則:

| 環境 | プロンプト/補完本文 | メタデータ(トークン数/モデル/レイテンシ) |
|---|---|---|
| `local` | 既定オフ。`FLOWNOTE_GENAI_CAPTURE_CONTENT=1` 明示時のみ、**マスク＋トランケート**して記録 | 常時 |
| `dev`/`staging` | オフ | 常時 |
| `prod` | **禁止** | 常時 |

- 記録する場合も:
  - [マスキング規約](./redaction-policy.md)を適用（メール/トークン/秘密鍵パターンを除去）。
  - 1メッセージあたり既定 **2,048 文字でトランケート**（`...[truncated N chars]`）。
  - OTel の方針に従い、本文は span の **event/log** として別管理（メトリクス・主要属性とは分離）。`event.domain="genai"`。
- 本文をログしない場合でも、**プロンプトのハッシュ**（`flownote.ai.prompt_hash`）と**文字数**は記録してよい（再現性・重複検知のため、内容は復元不可）。

## 4. メトリクス

| メトリクス | 種別 | 単位 | 属性 |
|---|---|---|---|
| `gen_ai.client.token.usage` | Histogram | token | `gen_ai.token.type`(input/output), `gen_ai.request.model`, `flownote.ai.use_case` |
| `gen_ai.client.operation.duration` | Histogram | s | `gen_ai.request.model`, `error.type` |
| `flownote.ai.cost.estimate` | Histogram | USD(概算) | `gen_ai.request.model` |
| `flownote.ai.request.count` | Counter | 1 | `flownote.ai.use_case`, `error.type` |

**概算コスト**: ローカル/自前モデルは実費0だが、運用感覚を学ぶため `input/output トークン × 単価表(`flownote.ai.pricing`)` で概算を計上する（単価は設定ファイルで管理。0でも可）。

## 5. エラー・リトライ・タイムアウト

- AI 呼び出し失敗は span status=ERROR、`error.type` を必須付与（`timeout`/`rate_limit`/`upstream_5xx`/`invalid_response`）。
- リトライは `WARN` ログ＋ `flownote.ai.retry.count` 属性。バックオフ秒も記録。
- タイムアウトは明示閾値（既定 30s）で打ち切り、`error.type="timeout"`。

## 6. ストリーミング

ストリーミング応答では、span はストリーム完了で終了し、`gen_ai.usage.output_tokens` は最終的な合計を記録。最初のトークンまでの時間（TTFT）を `flownote.ai.ttft_ms` に記録する（体感品質の指標）。

## 7. 実装の置き場所

- 計測ヘルパ: `packages/observability-py/.../genai.py`（`@instrument_genai` デコレータ / context manager）。
- AIクライアント実装: `apps/api/.../infrastructure/ai/openai_compatible_client.py`（このヘルパで必ず計装）。
- モック: `apps/ai-mock`（OpenAI互換 `/v1/chat/completions`, `/v1/embeddings` を返し、usage も模擬）。

## 8. テストで固定する事項

- AI 呼び出しが `gen_ai.*` 必須属性を持つ span を生成する。
- 既定設定でプロンプト本文が**ログに出ない**こと（capture オフ）。
- capture 有効時にマスキング＆トランケートが適用されること。
- 失敗時に `error.type` と span status=ERROR が付くこと。
- トークン使用量メトリクスが記録されること。
