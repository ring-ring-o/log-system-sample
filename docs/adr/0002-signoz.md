# ADR 0002: 収集・可視化基盤に SigNoz を採用する

- ステータス: 採用
- 日付: 2026-05-31

## 背景

ユーザー要件は「SigNoz などの Datadog 的挙動」。3本柱を1つのUIで相関閲覧でき、ローカルで動く OSS が必要。

## 決定

可視化・保存基盤に **SigNoz**（ClickHouse基盤）を採用する。アプリ→**OTel Collector**→SigNoz の経路とし、Collector を緩衝層に置く。

## 理由

- ログ/トレース/メトリクスを単一UIで相関でき、Datadog的な体験をローカルで得られる。
- OTLPネイティブで [ADR 0001](./0001-opentelemetry.md) と整合。
- OSS・セルフホスト可能でローカル完結要件を満たす。

## 留意 / リスク

- SigNoz は ClickHouse を含み**重い**。当環境での完全起動は不確実。
- → 緩和策: アプリ/Collector に **console / file exporter** を常時併用し、SigNoz が無くても相関ログ・トレースを観察可能にする（[アーキテクチャ §5](../observability/observability-architecture.md)）。`docker compose --profile signoz` で任意起動。

## 代替案

- Grafana LGTM(Loki/Tempo/Mimir) → 構成要素が多い。将来の差し替え候補として OTel 経由で開放。
- Jaeger単体 → トレースのみでログ/メトリクス相関に不足。
