"""FlowNote 共有可観測性ライブラリ。

ログ/トレース/メトリクスを OpenTelemetry 準拠で扱うための公開 API を集約する。
アプリ(``apps/api`` 等)はこのパッケージのみに依存し、特定ベンダに固定されない。

主な入口:
    - :func:`bootstrap`: ログとトレース/メトリクスを一括初期化する。
    - :func:`get_logger`: 構造化ロガーを取得する。
    - :class:`GenAIInstrumentation`: AI 呼び出しを計装する。
    - :func:`emit_audit` / :func:`emit_security`: 監査/セキュリティログを記録する。
"""

from __future__ import annotations

from flownote_observability.audit import (
    AuditOutcome,
    AuthzDecision,
    emit_audit,
    emit_security,
)
from flownote_observability.config import ObservabilityConfig
from flownote_observability.context import (
    bind_request_context,
    clear_request_context,
    hash_session_id,
)
from flownote_observability.conventions import (
    EventDomain,
    FinishReason,
    GenAiContentKind,
    GenAiOperation,
    GenAiSystem,
    GenAiTokenType,
)
from flownote_observability.genai import GenAICall, GenAIInstrumentation
from flownote_observability.logging_setup import (
    configure_logging,
    get_log_level,
    get_logger,
    set_log_level,
)
from flownote_observability.operations import Operation, log_event, operation
from flownote_observability.otel import configure_otel, get_meter, get_tracer
from flownote_observability.schema import LogRecord
from flownote_observability.severity import (
    Severity,
    severity_for_http_status,
    severity_from_name,
)


def bootstrap(config: ObservabilityConfig) -> None:
    """可観測性スタック(ログ + トレース/メトリクス)を一括初期化する。

    アプリ起動時(合成ルート)で一度だけ呼び出す。

    Args:
        config: 可観測性構成。
    """
    configure_logging(config)
    configure_otel(config)


__all__ = [
    "AuditOutcome",
    "AuthzDecision",
    "EventDomain",
    "FinishReason",
    "GenAICall",
    "GenAIInstrumentation",
    "GenAiContentKind",
    "GenAiOperation",
    "GenAiSystem",
    "GenAiTokenType",
    "LogRecord",
    "ObservabilityConfig",
    "Operation",
    "Severity",
    "bind_request_context",
    "bootstrap",
    "clear_request_context",
    "configure_logging",
    "configure_otel",
    "emit_audit",
    "emit_security",
    "get_log_level",
    "get_logger",
    "get_meter",
    "get_tracer",
    "hash_session_id",
    "log_event",
    "operation",
    "set_log_level",
    "severity_for_http_status",
    "severity_from_name",
]
