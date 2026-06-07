# フロントエンドログ（Frontend / Browser Observability）

> ブラウザ（Next.js 16）側のログ・トレース収集規約。基本規約は[ログ規約(SSOT)](./logging-spec.md)。

## 1. 目的

フロントの可観測性は「ユーザーが実際に体験した品質」を捉える。サーバ側だけでは見えない**クライアントエラー・体感速度(Web Vitals)・主要ユーザー操作**を収集し、**同一 `trace_id` でバックエンドと相関**させる。

## 2. 何を収集するか

| 種別 | 内容 | severity |
|---|---|---|
| クライアントエラー | 未捕捉例外、`unhandledrejection`、React Error Boundary | ERROR |
| ネットワーク | `fetch` の失敗/遅延（自動計装） | WARN/ERROR |
| API エラー | 4xx/5xx の Problem Details（安定コード `flownote.error.code`・`trace_id`） | ERROR |
| Web Vitals | LCP / INP / CLS / TTFB | INFO |
| ユーザー操作 | 主要アクション（メモ保存、AI検索実行 等の低カーディナリティイベント） | INFO |
| ルーティング | ページ遷移 | INFO/DEBUG |

**収集しないもの**: フォーム入力値、メモ本文、検索クエリ本文（[マスキング規約](./redaction-policy.md)）。操作イベントは「種別」のみ記録し、本文は記録しない。

## 3. トレース相関（最重要）

- API 呼び出し(`fetch`)に **W3C `traceparent`** を付与し、ブラウザ → FastAPI の server span → DB/AI span を**1つの trace** に繋ぐ。
- **ページ単位のルートトレース**を持ち、ページ内の各 `fetch` はその子 span(同一 `trace_id`・新しい `span_id`)として発番する。クライアントログにも同じ `trace_id`/`span_id` を載せ、ログ↔トレースを相関させる。
- **実装方針**: 依存を最小化するため、現状は OTel Web SDK を使わず W3C 準拠の `traceparent` を自前生成する軽量実装(`packages/observability-web`)。本番では `@opentelemetry/sdk-trace-web` + fetch 自動計装へ差し替え可能(span のネスト・サンプリング・OTLP トレース送出を SDK に委ねる)。

## 3.1 API エラーの扱い（RFC 9457 Problem Details）

バックエンドのエラー応答は [Problem Details](./logging-spec.md)（§5.2）。フロントは**メッセージ文字列ではなく安定コードで分岐**する。

- `shared/api-client.ts` は失敗応答を `parseProblemDetails()`（`@flownote/observability-web`）で解析し、`code` / `title` / `detail` / `trace_id` を `ApiError` に載せる。
- 同時に `web.api.error` を **ERROR で1件記録**し、`flownote.error.code` と（あれば）`flownote.error.trace_id` を付与する。`trace_id` でバックエンドのトレースへ引き戻せる。
  - **アラート注意**: `web.api.error` は 4xx でも ERROR（§2）。バックエンドは 4xx=WARN（[logging-spec §3](./logging-spec.md)）のため severity が非対称になる。アラートは `web.api.error` の severity を素朴に critical 扱いせず、`flownote.error.code` / status で 5xx・想定外のみを対象に絞る（404 等の Expected で誤発報しない）。
- **コードの型は手書きしない**。バックエンドの SSOT から `flownote-error-catalog --format ts` で `shared/error-catalog.generated.ts`（`ErrorCode` union / `ERROR_CATALOG`）を生成し、`ApiErrorCode` がそれを既知値として参照する。再生成は `pnpm --filter web gen:errors`、CI 追従チェックは `pnpm --filter web check:errors`。

```ts
try {
  await api.createNote(input);
} catch (e) {
  if (e instanceof ApiError && e.code === "VAL.REQUEST") {
    // コードで分岐(可変メッセージに依存しない)
  }
}
```

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
- トレースは `deployment.environment.name` 別比率（[ログ規約 §8](./logging-spec.md)）に従う。`ERROR` は常時送出。
- 開発(`local`)は 100%。

## 7. 実装の置き場所

- 共有実装: `packages/observability-web`
  - `trace.ts`: W3C `traceparent` 生成、ページトレース・子 span 発番。
  - `instrument.ts`: `fetch` 計装(`traceparent` 付与 + アクセスログ)。
  - `logger.ts` / `schema.ts` / `severity.ts`: 構造化クライアントロガー(スキーマ整形・相関・送出 sink)。
  - `redaction.ts`: 送出前マスキング。
  - `problem.ts`: RFC 9457 Problem Details の安全な解析（`parseProblemDetails`。アプリ固有コードには非依存）。
  - `vitals.ts`: Web Vitals 収集。 `error.ts`: グローバルエラー/Promise ハンドラ。
  - `index.ts`: 公開 API と `createLogger` ファクトリ。
- `apps/web` は `components/Providers.tsx`(`"use client"`)で `startPageTrace()`・Web Vitals・エラーハンドラを初期化し、各コンポーネントは `shared/observability.ts` の `getClientLogger()` と `shared/api-client.ts`(計装 fetch)のみ参照する。
- `apps/web/src/shared/error-catalog.generated.ts` はバックエンド SSOT からの**生成物**（手編集禁止）。エラーコードの追加時は `pnpm --filter web gen:errors` で再生成してコミットする。

## 8. テストで固定する事項（vitest）

- ロガー出力がスキーマに準拠し相関IDを含む。
- 送出ペイロードに機密キー/値が含まれない（マスク適用）。
- fetch 計装で `traceparent` ヘッダが付与される。
- エラーハンドラが未捕捉例外を `ERROR` で記録する。
- Problem Details を解析して `ApiError` に `code`/`trace_id` を反映し、`web.api.error` を `flownote.error.code` 付きで記録する。
