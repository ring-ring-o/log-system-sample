"""ログパイプライン(構造化/相関/マスキング/重大度)のテスト。

[ログ規約](../../docs/observability/logging-spec.md) §11 の固定。``build_processors`` で得た
プロセッサ列に1イベントを流し、最終スキーマ辞書を検証する。
"""

from __future__ import annotations

from collections.abc import MutableMapping

from opentelemetry import trace

from flownote_observability.config import ObservabilityConfig
from flownote_observability.logging_setup import build_processors
from flownote_observability.schema import LogRecord

_CONFIG = ObservabilityConfig(service_name="flownote-test", console_export=False)


def _run_pipeline(method: str, event: dict[str, object]) -> dict[str, object]:
    """プロセッサ列に1イベントを通し、整形後の辞書を返す。

    Args:
        method: 呼び出しメソッド名(重大度の決定に使う)。
        event: 入力イベント(``event`` キーが message)。

    Returns:
        スキーマ整形・マスキング済みの辞書。
    """
    processed: MutableMapping[str, object] = dict(event)
    for processor in build_processors(_CONFIG):
        processed = processor(None, method, processed)
    return dict(processed)


def test_log_conforms_to_schema() -> None:
    record = _run_pipeline("info", {"event": "note.created", "flownote.note.id": "n1"})
    # 規約スキーマ(LogRecord)に適合する。
    parsed = LogRecord.model_validate(record)
    assert parsed.body == "note.created"
    assert parsed.severity_text == "INFO"
    assert parsed.severity_number == 9
    assert parsed.service_name == "flownote-test"
    # 業務属性は attributes に集約される。
    assert record["attributes"] == {"flownote.note.id": "n1"}


def test_message_is_not_interpolated() -> None:
    # body は固定イベント名であり、可変値は attributes 側にある。
    record = _run_pipeline("info", {"event": "http.request.completed", "request_id": "r-123"})
    assert record["body"] == "http.request.completed"
    attributes = record["attributes"]
    assert isinstance(attributes, dict)
    assert attributes["request_id"] == "r-123"


def test_severity_mapping() -> None:
    # 4xx 相当のログは WARN、未捕捉相当は ERROR(メソッド名で表現)。
    assert _run_pipeline("warning", {"event": "x"})["severity_number"] == 13
    assert _run_pipeline("error", {"event": "x"})["severity_number"] == 17


def test_correlation_inside_span(otel_env: object) -> None:
    # span 内で生成したログは trace_id/span_id を相関する。
    tracer = trace.get_tracer("test")
    with tracer.start_as_current_span("unit"):
        record = _run_pipeline("info", {"event": "in.span"})
    assert isinstance(record["trace_id"], str)
    assert isinstance(record["span_id"], str)
    assert len(record["trace_id"]) == 32


def test_no_correlation_outside_span() -> None:
    # span 外では相関IDは None(スキーマ上許容)。
    record = _run_pipeline("info", {"event": "out.span"})
    assert record["trace_id"] is None
    assert record["span_id"] is None


def test_secrets_are_masked_in_pipeline() -> None:
    # パイプライン経由でも機密属性がマスクされる。
    record = _run_pipeline(
        "info",
        {"event": "auth", "Authorization": "Bearer secret", "password": "p"},
    )
    attributes = record["attributes"]
    assert isinstance(attributes, dict)
    assert attributes["Authorization"] == "***"
    assert attributes["password"] == "***"


def test_exception_is_structured() -> None:
    # exc_info から exception.* 属性が生成される。
    try:
        raise ValueError("boom")
    except ValueError as exc:
        record = _run_pipeline("error", {"event": "failure", "exc_info": exc})
    attributes = record["attributes"]
    assert isinstance(attributes, dict)
    assert attributes["exception.type"] == "builtins.ValueError"
    assert attributes["exception.message"] == "boom"
    assert "ValueError" in str(attributes["exception.stacktrace"])
