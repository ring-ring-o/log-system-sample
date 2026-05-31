"""observability-py テスト共通フィクスチャ。

OTel のトレース/メトリクスをインメモリで観測できるよう、テストセッションで一度だけ
プロバイダを設定する。これによりエクスポート結果(span/metric)を直接検証できる。
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

import pytest
import structlog
from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


@dataclass(slots=True)
class OtelHarness:
    """テスト用の OTel 観測ハーネス。

    Attributes:
        spans: 終了済み span を保持するインメモリエクスポータ。
        reader: メトリクスを読み出すインメモリリーダ。
    """

    spans: InMemorySpanExporter
    reader: InMemoryMetricReader


@pytest.fixture(autouse=True)
def _isolate_structlog() -> Iterator[None]:
    """各テストの前後で structlog 設定と contextvars をリセットし、相互汚染を防ぐ。

    Yields:
        テスト本体の実行。
    """
    structlog.contextvars.clear_contextvars()
    yield
    structlog.reset_defaults()
    structlog.contextvars.clear_contextvars()


@pytest.fixture(scope="session")
def otel_env() -> Iterator[OtelHarness]:
    """セッション内で一度だけ OTel プロバイダをインメモリ構成で設定する。

    Yields:
        span/metric を検証できる :class:`OtelHarness`。
    """
    span_exporter = InMemorySpanExporter()
    tracer_provider = TracerProvider()
    tracer_provider.add_span_processor(SimpleSpanProcessor(span_exporter))
    trace.set_tracer_provider(tracer_provider)

    reader = InMemoryMetricReader()
    meter_provider = MeterProvider(metric_readers=[reader])
    metrics.set_meter_provider(meter_provider)

    yield OtelHarness(spans=span_exporter, reader=reader)
