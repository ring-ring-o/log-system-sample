"""高レベルファサード ``operation`` / ``log_event`` の契約テスト(開発者DX)。

「1行で規約準拠の計装ができる」ことと、その際に規約(名前空間・相関・境界ログ・
span ステータス)が自動で守られることを固定する。
"""

from __future__ import annotations

import json
from typing import Protocol

import pytest
from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from flownote_observability import log_event, operation
from flownote_observability.config import ObservabilityConfig
from flownote_observability.logging_setup import configure_logging

_CONFIG = ObservabilityConfig(service_name="dx-test", console_export=False)


class OtelHarness(Protocol):
    """conftest の ``otel_env`` が返す観測ハーネスの構造的型。"""

    spans: InMemorySpanExporter
    reader: InMemoryMetricReader
    tracer: trace.Tracer
    meter: metrics.Meter


def _logs(text: str) -> list[dict[str, object]]:
    """標準出力から JSON ログ行を抽出する。

    Args:
        text: 捕捉した標準出力。

    Returns:
        パースできた JSON ログの一覧。
    """
    out: list[dict[str, object]] = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def _attrs(record: dict[str, object]) -> dict[str, object]:
    attrs = record.get("attributes")
    return attrs if isinstance(attrs, dict) else {}


def test_operation_emits_namespaced_correlated_business_event(
    otel_env: OtelHarness, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_logging(_CONFIG)
    with operation("note.create", tracer=otel_env.tracer, note_id="n1") as op:
        # 後から判明した属性を足せる。
        op.set(version_id="v1")

    records = _logs(capsys.readouterr().out)
    events = [r for r in records if r.get("body") == "note.create"]
    assert events, "業務イベントログが出ていない"
    record = events[-1]
    attrs = _attrs(record)
    # event.domain が自動付与される。
    assert attrs["event.domain"] == "app"
    # 名前空間の無いキーは flownote.* に寄せられる(規約 §4.2 を踏み外しにくくする)。
    assert attrs["flownote.note_id"] == "n1"
    assert attrs["flownote.version_id"] == "v1"
    # span 内で出力されトレース相関する。
    assert isinstance(record["trace_id"], str)


def test_operation_preserves_already_namespaced_keys(
    otel_env: OtelHarness, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_logging(_CONFIG)
    with operation(
        "ai.search",
        tracer=otel_env.tracer,
        **{"flownote.search.query_hash": "abc", "http.route": "/x"},
    ):
        pass
    record = [r for r in _logs(capsys.readouterr().out) if r.get("body") == "ai.search"][-1]
    attrs = _attrs(record)
    # 既にドット区切りのキーはそのまま尊重する(二重 flownote. を付けない)。
    assert attrs["flownote.search.query_hash"] == "abc"
    assert attrs["http.route"] == "/x"


def test_operation_on_error_marks_span_and_does_not_log(
    otel_env: OtelHarness, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_logging(_CONFIG)
    with pytest.raises(ValueError), operation("note.fail", tracer=otel_env.tracer, note_id="n2"):
        raise ValueError("boom")

    # 失敗時は業務ログを出さない(エラーログは境界に集約する規約)。
    records = _logs(capsys.readouterr().out)
    assert not [r for r in records if r.get("body") == "note.fail"]
    # span は ERROR ステータスで残る。
    spans = [s for s in otel_env.spans.get_finished_spans() if s.name == "note.fail"]
    assert spans and spans[-1].status.status_code is StatusCode.ERROR


def test_log_event_namespaces_and_tags_domain(
    otel_env: OtelHarness, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_logging(_CONFIG)
    log_event("search.performed", query_hash="abc")
    record = [r for r in _logs(capsys.readouterr().out) if r.get("body") == "search.performed"][-1]
    attrs = _attrs(record)
    assert attrs["flownote.query_hash"] == "abc"
    assert attrs["event.domain"] == "app"
