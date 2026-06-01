# packages/observability-web — 共有可観測性ライブラリ（ブラウザ）

`@flownote/observability-web`。**ブラウザ向けの構造化クライアントログ・トレース相関（`traceparent`）・マスキング**を提供する。
フロントエンド（[apps/web](../../apps/web/README.md)）はこのパッケージ経由でのみログ/計装を扱う（`console.log` 直出力禁止）。

> バックエンドの [ログ規約(SSOT)](../../docs/observability/logging-spec.md) とスキーマ・重大度を揃え、
> フロント操作 → API を **1 つの trace** で横断追跡できるようにする（[frontend-logging.md](../../docs/observability/frontend-logging.md)）。

## 公開 API（[`src/index.ts`](./src/index.ts)）

| 入口 | 役割 |
|---|---|
| `ClientLogger` / `createLogger` | 構造化クライアントロガー（簡易ファクトリ付き） |
| `LogSink` / `createBeaconSink` | ログ送出先（`navigator.sendBeacon` ベース・カスタム注入可） |
| `startPageTrace` / `getPageTrace` / `newTraceContext` / `childTraceContext` | ページ単位のルートトレースと子コンテキスト |
| `buildTraceparent` / `TraceContext` | `traceparent` ヘッダ生成（API への trace 伝播） |
| `createInstrumentedFetch` | `traceparent` を自動付与する fetch ラッパ |
| `reportWebVitals` | Web Vitals（LCP/CLS 等）をログへ送出 |
| `registerGlobalErrorHandlers` | 未捕捉エラー／Promise 拒否の記録（解除関数を返す） |
| `redact` | マスキング（秘匿値の削除/ハッシュ化） |
| `buildRecord` / `ClientLogRecord` / `ResourceInfo` | 共通ログレコードスキーマ |
| `severityForHttpStatus` / `SEVERITY_NUMBER` / `SeverityText` | 重大度（OTel と対応） |

## モジュール構成（[`src/`](./src/)）

```
logger.ts       ClientLogger / LogSink / beacon sink
trace.ts        TraceContext・traceparent・ページトレース
instrument.ts   traceparent を付与する fetch ラッパ
schema.ts       ClientLogRecord / ResourceInfo（共通スキーマ）
severity.ts     重大度（OTel SeverityNumber との対応）
redaction.ts    マスキング
vitals.ts       Web Vitals 収集
error.ts        グローバルエラーハンドラ
index.ts        公開エントリ + createLogger ファクトリ
```

## コマンド（リポジトリルートから / pnpm）

```bash
pnpm install
pnpm biome check --write .                       # フォーマット+リント
pnpm --filter @flownote/observability-web test       # vitest
pnpm --filter @flownote/observability-web typecheck  # tsc --noEmit
```

ビルド成果物は持たず、ソース（`./src/index.ts`）を直接 `exports` する pnpm ワークスペースパッケージ。

## テスト

[`tests/observability.test.ts`](./tests/observability.test.ts) でログ生成・マスキング・トレース相関・重大度を固定する。

## 設計メモ

- 依存は `web-vitals` のみ。OTLP エンドポイント未設定時は console フォールバックで開発を止めない。
- サーバ側の対になるパッケージは [observability-py](../observability-py/README.md)（スキーマ・重大度を揃える）。
