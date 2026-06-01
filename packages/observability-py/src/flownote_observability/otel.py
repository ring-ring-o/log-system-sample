"""OpenTelemetry のトレース/メトリクス初期化。

[ADR 0001](../../../docs/adr/0001-opentelemetry.md) に基づき、トレースとメトリクスを
OTLP/HTTP で OTel Collector に送出する。ローカル観察用に Console exporter も併用できる
([可観測性アーキテクチャ](../../../docs/observability/observability-architecture.md) §5)。

ログは structlog による標準出力JSON([logging_setup])が一次経路であり、本モジュールは
トレース/メトリクスを担当する(責務分離)。
"""

from __future__ import annotations

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    ConsoleMetricExporter,
    MetricReader,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SpanExporter,
)
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased

from flownote_observability.config import ObservabilityConfig


def _build_resource(config: ObservabilityConfig) -> Resource:
    """全シグナル共通のリソース属性を構築する。

    Args:
        config: 可観測性構成。

    Returns:
        ``service.name``/``service.version``/``deployment.environment.name`` を持つ Resource。
    """
    return Resource.create(
        {
            "service.name": config.service_name,
            "service.version": config.service_version,
            # OTel Stable: `deployment.environment` は `deployment.environment.name` に rename。
            "deployment.environment.name": config.environment,
        }
    )


def configure_otel(config: ObservabilityConfig) -> None:
    """トレースとメトリクスのプロバイダをプロセス全体に設定する。

    OTLP エンドポイントが設定されていれば OTLP exporter を、``console_export`` が真なら
    Console exporter を登録する。両方無効ならトレースは生成されるが送出されない。

    Args:
        config: 可観測性構成。
    """
    resource = _build_resource(config)

    # --- トレース ---------------------------------------------------------
    # 親の決定を尊重しつつ比率サンプリングする(ローカルは 1.0)。
    sampler = ParentBased(root=TraceIdRatioBased(config.trace_sample_ratio))
    tracer_provider = TracerProvider(resource=resource, sampler=sampler)
    span_exporters: list[SpanExporter] = []
    if config.otlp_endpoint is not None:
        span_exporters.append(OTLPSpanExporter())
    if config.console_export:
        span_exporters.append(ConsoleSpanExporter())
    for exporter in span_exporters:
        tracer_provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(tracer_provider)

    # --- メトリクス -------------------------------------------------------
    metric_readers: list[MetricReader] = []
    if config.otlp_endpoint is not None:
        metric_readers.append(PeriodicExportingMetricReader(OTLPMetricExporter()))
    if config.console_export:
        metric_readers.append(PeriodicExportingMetricReader(ConsoleMetricExporter()))
    meter_provider = MeterProvider(resource=resource, metric_readers=metric_readers)
    metrics.set_meter_provider(meter_provider)


def get_tracer(name: str) -> trace.Tracer:
    """設定済みプロバイダからトレーサを取得する。

    Args:
        name: 計装スコープ名(通常はモジュール名)。

    Returns:
        OTel トレーサ。
    """
    return trace.get_tracer(name)


def get_meter(name: str) -> metrics.Meter:
    """設定済みプロバイダからメータを取得する。

    Args:
        name: 計装スコープ名。

    Returns:
        OTel メータ。
    """
    return metrics.get_meter(name)
