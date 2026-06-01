# ADR 0005: ログ送出経路（stdout JSON を一次、OTLP Logs Bridge は将来オプション）

- ステータス: 採用
- 日付: 2026-06-01

## 背景

トレース/メトリクスは OTLP で Collector へ送る（[ADR 0001](./0001-opentelemetry.md)）。一方ログの送出経路には2系統がある:

1. **stdout JSON**（12-factor「logs as event streams」）+ コンテナログを tail する agent（filelog/fluentbit）で集約。
2. **OTLP Logs**（Python の OTel Logs Bridge API。2025 に Stable 化）で `structlog → LoggingHandler → OTLP` とし、3シグナルを Collector に一本化。

当初アーキテクチャ文書は「ログは stdout、Collector のログパイプラインは将来口」と書いていたが、判断理由が曖昧だった（本 ADR で明文化する）。

## 決定

**一次経路は stdout JSON（JSON Lines）を維持する。** OTLP Logs Bridge は「将来オプション」として口を開けておき、採用条件を本 ADR に明記する。Collector のログパイプライン（receivers: otlp → ... → debug/file）は OTLP 経由でログを送る構成に切り替えたときの受け口として残す。

## 理由

- **バックプレッシャ/障害分離**: Collector 障害時、トレース/メトリクスは SDK の BatchSpanProcessor がメモリに溜め、やがて**ドロップ**する。stdout ログはプロセス外（コンテナランタイム/agent）が運ぶため Collector 障害の影響を受けず、**監査・障害解析に最も必要なログを失わない**。これは stdout 経路の明確な利点。
- **単純さ**: アプリは標準出力に書くだけでよく、ローカルは `docker logs`/コンソールで即観察できる（SigNoz 等の起動に依存しない）。
- **相関は確保済み**: stdout でも `trace_id`/`span_id` を全ログに付与しており（[logging-spec §6](../observability/logging-spec.md)）、収集後に SigNoz 側でトレースと相関できる。

## OTLP Logs Bridge へ切り替える条件（将来）

- ログ・トレース・メトリクスの**同一パイプライン整形/サンプリング**を Collector 側で統一したくなったとき。
- agent（filelog/fluentbit）の運用コストが OTLP 直送より高くつくとき。
- 切替時は Collector 障害時のログ欠落を **persistent queue（file_storage extension）** で緩和する。

## 留意 / リスク

- 2経路を併存させると二重集約になりうる → 切替は**排他**（どちらか一方）とする。
- stdout 経路は**行サイズ上限**に注意（巨大スタックトレースは `exception.stacktrace` に1行格納するため、ランタイムのログ行上限に収まるか確認する）。

## 代替案

- 最初から OTLP Logs に一本化 → Collector 障害時のログ欠落リスクを負う。当環境（ローカル確実観察重視・SigNoz 起動が不確実）では stdout の堅牢性を優先した。
