# ADR 0001: 可観測性の統一規格に OpenTelemetry を採用する

- ステータス: 採用
- 日付: 2026-05-31

## 背景

本プロジェクトの主目的は、フロント/バック/AI/認証を含む現実的構成での**ログ・トレース・メトリクスの相関観察**である。複数言語(Python/TypeScript)・複数バックエンド候補(SigNoz等)をまたいで一貫させる規格が必要。

## 決定

計装(instrumentation)とデータモデルの規格として **OpenTelemetry (OTel)** を全面採用する。アプリは OTel API/SDK にのみ依存し、収集先(SigNoz)へは OTLP で送出する。重大度・属性命名は OTel Semantic Conventions に準拠する（[ログ規約](../observability/logging-spec.md)）。

## 理由

- **ベンダ非依存**: 収集先を差し替えてもアプリを変えない。
- **3本柱の相関**: `trace_id`/`span_id` でログ・トレース・メトリクスを統一的に結合できる。
- **エコシステム**: FastAPI/SQLAlchemy/httpx/ブラウザの自動計装が揃う。
- **GenAI対応**: GenAI semantic conventions があり、AI観測を規格化できる。

## 代替案

- ベンダ独自SDK(Datadog等) → ロックイン。却下。
- 自前ログのみ → トレース相関とメトリクスを失う。却下。

## 影響

- アプリは `packages/observability-*` 経由でOTelに依存。
- 収集は[OTel Collector経由](../observability/observability-architecture.md)に集約。
