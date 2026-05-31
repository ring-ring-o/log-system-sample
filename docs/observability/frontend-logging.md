# フロントエンドログ（Frontend / Browser Observability）

> ブラウザ（Next.js 16）側のログ・トレース収集規約。基本規約は[ログ規約(SSOT)](./logging-spec.md)。

## 1. 目的

フロントの可観測性は「ユーザーが実際に体験した品質」を捉える。サーバ側だけでは見えない**クライアントエラー・体感速度(Web Vitals)・主要ユーザー操作**を収集し、**同一 `trace_id` でバックエンドと相関**させる。

## 2. 何を収集するか

| 種別 | 内容 | severity |
|---|---|---|
| クライアントエラー | 未捕捉例外、`unhandledrejection`、React Error Boundary | ERROR |
| ネットワーク | `fetch` の失敗/遅延（自動計装） | WARN/ERROR |
| Web Vitals | LCP / INP / CLS / TTFB | INFO |
| ユーザー操作 | 主要アクション（メモ保存、AI検索実行 等の低カーディナリティイベント） | INFO |
| ルーティング | ページ遷移 | INFO/DEBUG |

**収集しないもの**: フォーム入力値、メモ本文、検索クエリ本文（[マスキング規約](./redaction-policy.md)）。操作イベントは「種別」のみ記録し、本文は記録しない。

## 3. トレース相関（最重要）

- API 呼び出し(`fetch`)に **W3C `traceparent`** を付与し、ブラウザ → FastAPI の server span → DB/AI span を**1つの trace** に繋ぐ。
- **ページ単位のルートトレース**を持ち、ページ内の各 `fetch` はその子 span(同一 `trace_id`・新しい `span_id`)として発番する。クライアントログにも同じ `trace_id`/`span_id` を載せ、ログ↔トレースを相関させる。
- **実装方針**: 依存を最小化するため、現状は OTel Web SDK を使わず W3C 準拠の `traceparent` を自前生成する軽量実装(`packages/observability-web`)。本番では `@opentelemetry/sdk-trace-web` + fetch 自動計装へ差し替え可能(span のネスト・サンプリング・OTLP トレース送出を SDK に委ねる)。

## 4. 送出経路

```
ブラウザ → (OTLP/HTTP) → OTel Collector → SigNoz
                         （CORS許可した収集エンドポイント or Next.js の Route Handler 経由でプロキシ）
```

- 開発時は Collector の OTLP/HTTP(:4318) に直接、または Next.js の Route Handler (`/api/otel`) でプロキシして CORS とトークンを制御する。
- バッチ送出（`BatchSpanProcessor`）でリクエスト数を抑制。ページ離脱時は `sendBeacon` でフラッシュ。

## 5. 構造化とスキーマ整合

- クライアントログも[ログ規約](./logging-spec.md)のスキーマ（`timestamp`/`severity_*`/`body`/`attributes`/相関ID）に準拠した JSON とする。
- `service.name="flownote-web"`、`attributes` に `browser.*`（OTel）、`flownote.web.route`、`flownote.web.action` を付与。
- 送出前に[マスキング規約](./redaction-policy.md)のキー/パターンマスクを適用。

## 6. サンプリング・量制御

- Web Vitals/操作ログは**ページビュー単位**でまとめ、過剰送出を避ける。
- トレースは `deployment.environment` 別比率（[ログ規約 §8](./logging-spec.md)）に従う。`ERROR` は常時送出。
- 開発(`local`)は 100%。

## 7. 実装の置き場所

- 共有実装: `packages/observability-web`
  - `trace.ts`: W3C `traceparent` 生成、ページトレース・子 span 発番。
  - `instrument.ts`: `fetch` 計装(`traceparent` 付与 + アクセスログ)。
  - `logger.ts` / `schema.ts` / `severity.ts`: 構造化クライアントロガー(スキーマ整形・相関・送出 sink)。
  - `redaction.ts`: 送出前マスキング。
  - `vitals.ts`: Web Vitals 収集。 `error.ts`: グローバルエラー/Promise ハンドラ。
  - `index.ts`: 公開 API と `createLogger` ファクトリ。
- `apps/web` は `components/Providers.tsx`(`"use client"`)で `startPageTrace()`・Web Vitals・エラーハンドラを初期化し、各コンポーネントは `shared/observability.ts` の `getClientLogger()` と `shared/api-client.ts`(計装 fetch)のみ参照する。

## 8. テストで固定する事項（vitest）

- ロガー出力がスキーマに準拠し相関IDを含む。
- 送出ペイロードに機密キー/値が含まれない（マスク適用）。
- fetch 計装で `traceparent` ヘッダが付与される。
- エラーハンドラが未捕捉例外を `ERROR` で記録する。
