"""GenAI 計装のテスト([genai-observability] の固定)。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import pytest
from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from flownote_observability.config import ObservabilityConfig
from flownote_observability.genai import GenAIInstrumentation


class OtelHarness(Protocol):
    """conftest の ``otel_env`` フィクスチャが返す観測ハーネスの構造的型。

    Attributes:
        spans: 終了済み span を保持するエクスポータ。
        reader: メトリクスを読み出すリーダ。
        tracer: ローカルプロバイダ由来のトレーサ。
        meter: ローカルプロバイダ由来のメータ。
    """

    spans: InMemorySpanExporter
    reader: InMemoryMetricReader
    tracer: trace.Tracer
    meter: metrics.Meter


def _make_instrumentation(otel_env: OtelHarness, **config_kwargs: object) -> GenAIInstrumentation:
    """ハーネスのローカル tracer/meter を注入した計装を生成する。

    Args:
        otel_env: OTel ハーネス。
        **config_kwargs: :class:`ObservabilityConfig` への追加引数。

    Returns:
        テスト用に構成した計装。
    """
    config = ObservabilityConfig(service_name="t", console_export=False, **config_kwargs)  # type: ignore[arg-type]
    return GenAIInstrumentation(config=config, tracer=otel_env.tracer, meter=otel_env.meter)


@dataclass(slots=True)
class _FakeLogger:
    """本文ログを記録するだけのフェイクロガー。"""

    events: list[tuple[str, dict[str, object]]] = field(default_factory=list)

    def info(self, event: str, **kwargs: object) -> None:
        self.events.append((event, kwargs))


def _find_span(harness: OtelHarness, name: str) -> ReadableSpan:
    """名前で終了済み span を1件取得する。

    Args:
        harness: OTel ハーネス。
        name: span 名。

    Returns:
        最初に一致した span。
    """
    matches = [s for s in harness.spans.get_finished_spans() if s.name == name]
    assert matches, f"span {name!r} not found"
    return matches[-1]


def test_genai_span_has_required_attributes(otel_env: OtelHarness) -> None:
    inst = _make_instrumentation(otel_env)
    with inst.call(
        operation="chat", system="openai", request_model="qwen2.5", use_case="task_consult"
    ) as call:
        call.record_usage(input_tokens=120, output_tokens=34)
        call.record_response(model="qwen2.5", finish_reasons=["stop"])

    span = _find_span(otel_env, "chat qwen2.5")
    attrs = span.attributes or {}
    # gen_ai.* 必須属性が揃う。
    assert attrs["gen_ai.operation.name"] == "chat"
    assert attrs["gen_ai.system"] == "openai"
    assert attrs["gen_ai.request.model"] == "qwen2.5"
    assert attrs["gen_ai.usage.input_tokens"] == 120
    assert attrs["gen_ai.usage.output_tokens"] == 34
    assert attrs["flownote.ai.use_case"] == "task_consult"


def test_genai_records_token_metrics(otel_env: OtelHarness) -> None:
    inst = _make_instrumentation(otel_env)
    with inst.call(
        operation="chat", system="openai", request_model="m", use_case="unified_search"
    ) as call:
        call.record_usage(input_tokens=10, output_tokens=5)

    data = otel_env.reader.get_metrics_data()
    names = {
        metric.name
        for rm in (data.resource_metrics if data else [])
        for sm in rm.scope_metrics
        for metric in sm.metrics
    }
    assert "gen_ai.client.token.usage" in names
    assert "flownote.ai.request.count" in names


def test_genai_error_sets_status_and_type(otel_env: OtelHarness) -> None:
    inst = _make_instrumentation(otel_env)
    with (
        pytest.raises(ValueError),
        inst.call(
            operation="chat", system="openai", request_model="err-model", use_case="uc"
        ) as call,
    ):
        call.record_usage(input_tokens=1, output_tokens=0)
        raise ValueError("boom")

    span = _find_span(otel_env, "chat err-model")
    assert span.status.status_code is StatusCode.ERROR
    attrs = span.attributes or {}
    assert attrs["error.type"] == "ValueError"


def test_prompt_content_not_logged_by_default(otel_env: OtelHarness) -> None:
    fake = _FakeLogger()
    inst = GenAIInstrumentation(
        config=ObservabilityConfig(service_name="t", console_export=False),
        logger=fake,  # type: ignore[arg-type]
        tracer=otel_env.tracer,
        meter=otel_env.meter,
    )
    with inst.call(operation="chat", system="openai", request_model="m", use_case="uc") as call:
        call.capture("prompt", "secret content sk-abcdef1234567890")
    # 既定では本文をログしない。
    assert fake.events == []


def test_prompt_content_masked_when_enabled(otel_env: OtelHarness) -> None:
    fake = _FakeLogger()
    inst = GenAIInstrumentation(
        config=ObservabilityConfig(
            service_name="t",
            console_export=False,
            genai_capture_content=True,
            genai_content_max_chars=500,
        ),
        logger=fake,  # type: ignore[arg-type]
        tracer=otel_env.tracer,
        meter=otel_env.meter,
    )
    with inst.call(operation="chat", system="openai", request_model="m", use_case="uc") as call:
        call.capture("prompt", "contact alice@example.com now")

    assert len(fake.events) == 1
    _event, kwargs = fake.events[0]
    # 本文はマスクされ、生のメールは出ない。
    rendered = str(kwargs)
    assert "alice@example.com" not in rendered
    assert "***@***" in rendered
