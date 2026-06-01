# 可観測性アーキテクチャ（Observability Architecture）

> ログ・トレース・メトリクスをどう生成し、相関させ、収集・可視化するかの全体設計。
> 規約の細目は[ログ規約(SSOT)](./logging-spec.md)を参照。

## 1. 目的と価値

このシステムの**主目的はログ/可観測性の検証**である。題材アプリ（メモ/タスク/バージョン管理/AI/認証）は、現実的な Web サービスで生じる多様なシグナルを発生させるための器であり、本アーキテクチャはそれらを**一貫した規格(OTel)で相関可能に**集約する。

提供価値:
- **MTTR短縮**: 1つの `trace_id` でフロント操作→API→AI→DB→認証まで横断追跡できる。
- **ベンダ非依存**: アプリは OTel にのみ依存し、収集先（SigNoz）は差し替え可能。
- **コスト可制御**: レベル・サンプリング・マスキングを規約で統制。
- **学習可能性**: ローカルだけで「3本柱の相関」を観察できる。

## 2. 3本柱（Three Pillars）と相関

| 柱 | 何を答えるか | 実装 |
|---|---|---|
| ログ(Logs) | 「その瞬間、何が起きたか」 | 構造化JSON、`trace_id`/`span_id` 付与 |
| トレース(Traces) | 「どこで時間を使い、どこで失敗したか」 | OTel span、W3C伝播 |
| メトリクス(Metrics) | 「全体としてどれくらいの量/速度/失敗率か」 | RED + AI固有メトリクス |

**相関の核**は `trace_id`/`span_id`。ログとトレースは同一IDで結合し、メトリクスは exemplar / 共通属性（`service.name`, `http.route`）で関連づける。

## 3. トポロジ

```
                 ┌─────────────────────────────────────────────┐
   ブラウザ       │  apps/web (Next.js 16)                       │
  ┌────────┐     │  @opentelemetry/sdk-trace-web + client logger│
  │ ユーザー │────▶│  - fetch計装で traceparent 付与               │
  └────────┘     │  - クライアントログ/Web Vitals を OTLP/HTTP    │
                 └───────────────┬─────────────────────────────┘
                                 │ W3C traceparent + OTLP/HTTP
                                 ▼
                 ┌─────────────────────────────────────────────┐
                 │  apps/api (FastAPI, packages/observability-py)│
                 │  - ミドルウェアで span 開始/コンテキスト束縛    │
                 │  - structlog → OTel LoggingHandler            │
                 │  - 自動計装: FastAPI / SQLAlchemy / httpx      │
                 └───┬───────────────┬───────────────┬──────────┘
                     │               │               │ httpx(OpenAI互換)
                     ▼               ▼               ▼
            ┌────────────┐  ┌──────────────┐  ┌───────────────────┐
            │ PostgreSQL │  │ Keycloak     │  │ AI (vLLM/OpenAI互換) │
            │ (db.* 計装) │  │ (OIDC/JWKS)  │  │ 開発時はモック        │
            └────────────┘  └──────────────┘  └───────────────────┘

   すべてのシグナル(OTLP/gRPC or HTTP)
                     │
                     ▼
        ┌────────────────────────────┐      ┌──────────────────────────┐
        │  OpenTelemetry Collector    │─────▶│  SigNoz (ClickHouse基盤)  │
        │  receivers: otlp            │      │  Traces/Logs/Metrics/UI   │
        │  processors: batch,         │      └──────────────────────────┘
        │    memory_limiter, resource,│
        │    tail_sampling            │      ┌──────────────────────────┐
        │  exporters: clickhouse,     │─────▶│  console / file exporter  │
        │    debug, file              │      │  (ローカル確実観察用)       │
        └────────────────────────────┘      └──────────────────────────┘
```

## 4. なぜ Collector を挟むか

アプリは Collector にだけ送ればよく、**収集先の変更・追加（SigNoz→Grafana等）でアプリを変更しない**。再試行・バッチ・バックプレッシャ・属性付与（`resource`）・tail sampling(ADR 0005・エラー/高レイテンシ trace を優先保持)を Collector に集約できる（関心の分離）。

## 5. ローカルでの確実な観察

SigNoz は ClickHouse を含み重い。学習を止めないため、**多重エクスポート**を採る:

1. **既定**: アプリ → OTel Collector(OTLP) → SigNoz。
2. **常時併用**: アプリ/Collector の `console` および `file` exporter。`docker compose` を立てなくても、ターミナルとログファイルで「`trace_id` 相関した構造化ログ・span」を観察できる。

環境変数で切替:
- `OTEL_EXPORTER_OTLP_ENDPOINT`（未設定なら console exporter のみ）
- `FLOWNOTE_OTEL_CONSOLE=1`（常にコンソールにも出す）

## 6. リソース属性（Resource）

全シグナルに付与する識別属性（OTel Resource）:

- `service.name`（`flownote-api` / `flownote-web` / `flownote-ai-mock`）
- `service.version`、`service.instance.id`（採番元は環境別。[ADR 0006](../adr/0006-service-instance-id.md)）
- `deployment.environment.name`（`local`/`dev`/`staging`/`prod`）

Collector の `resource` processor で、収集経路や Collector バージョン等の運用属性を追加する。

## 7. 自動計装 vs 手動計装

- **自動計装**（OTel instrumentation）: FastAPI(HTTP server span)、SQLAlchemy(db span)、httpx(client span)。横断関心を低コストで網羅。
- **手動計装**: ドメインのユースケース境界（例: 「メモ作成→AI検索→タスク化」の各ステップ）に明示 span を張り、業務的に意味のある単位で観察できるようにする。GenAI 呼び出しは手動 span + GenAI属性（[GenAI可観測性](./genai-observability.md)）。

## 8. データフローの責務分担

| 層 | 責務 |
|---|---|
| `packages/observability-py` | OTel初期化、structlogプロセッサ、コンテキスト束縛、マスキング、GenAI計測ヘルパ。**アプリはここだけに依存**。 |
| `apps/api` ミドルウェア | span開始、`request_id`/`user`束縛、RED計測、アクセスログ。 |
| `packages/observability-web` | ブラウザSDK初期化、fetch計装、クライアントロガー、OTLP送出。 |
| OTel Collector | 受信・整形・バッチ・配送。 |
| SigNoz | 保存・可視化・アラート。 |

> **シグナル別の送出経路**: バックエンドの**トレース/メトリクスは OTLP** で Collector へ送る。
> **ログは標準出力(JSON)** に出し、ローカルは `docker logs`/コンソール、本番はコンテナ標準出力を
> 集約する log-shipping agent(fluentbit 等)で収集する(12-factor)。Collector のログ・パイプラインは
> OTLP ログ(将来アプリが送る場合)を受ける口として用意している。フロントは OTLP/HTTP(またはプロキシ)で送出する。

## 9. ローカル起動手順（概要）

```bash
# 観測スタック（ベストエフォート。SigNozは重い）
docker compose -f infra/compose.yaml up -d otel-collector postgres keycloak ai-mock
# SigNoz を含める場合
docker compose -f infra/compose.yaml --profile signoz up -d

# アプリ（開発時はローカルコマンド優先）
uv run --package flownote-api uvicorn flownote_api.main:app --reload   # API
pnpm --filter web dev                                                  # Web
```

`docker compose` を使わずとも、API 単体起動 + console exporter で相関ログ/トレースを観察可能。詳細は `infra/README.md` と [CLAUDE.md](../../CLAUDE.md)。

## 10. 導入済み / 将来拡張

- ✅ Collector に **tail-based sampling**（エラー/高レイテンシ trace を優先保持）を導入済み（`infra/otel-collector/config.yaml`・[ADR 0005](../adr/0005-log-transport.md)）。ヘッドサンプリングと併用時の注意は [logging-spec §8](./logging-spec.md)。
- ログ送出は stdout JSON が一次経路。OTLP Logs Bridge への一本化は条件付きの将来オプション（[ADR 0005](../adr/0005-log-transport.md)）。
- MCP/エージェントのツール呼び出し計装は `gen_ai.*` の延長として規約化（[ADR 0007](../adr/0007-mcp-agent-instrumentation.md)）。
- ログ→トレース→メトリクスの **exemplar** リンク強化。
- SLO/アラート定義を SigNoz に IaC 化。
