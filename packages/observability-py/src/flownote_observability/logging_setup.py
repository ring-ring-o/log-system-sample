"""構造化ログのパイプライン構築。

structlog のプロセッサ列で [ログ規約](../../../docs/observability/logging-spec.md) を実装する。
出力は1行JSON(JSON Lines)で標準出力へ流す。ローカルでは `docker logs`/コンソールで観察し、
本番ではコンテナ標準出力を集約する log-shipping agent(fluentbit 等)で収集する想定
(トレース/メトリクスは OTLP で Collector へ。
[可観測性アーキテクチャ](../../../docs/observability/observability-architecture.md))。

プロセッサの責務:
    1. contextvars マージ(相関キーの継承)
    2. タイムスタンプ付与(RFC3339 ナノ秒)
    3. 重大度付与(メソッド名 → Severity)
    4. トレース文脈付与(OTel の現在 span から trace_id/span_id)
    5. 例外情報の構造化(exception.*)
    6. リソース属性付与(service.* / deployment.environment.name)
    7. スキーマ整形(予約キー以外を attributes へ集約、message → body)
    8. マスキング(機密の除去)
    9. JSON レンダリング
"""

from __future__ import annotations

import logging
import time
import traceback
from collections.abc import Callable, MutableMapping
from datetime import UTC, datetime
from types import TracebackType
from typing import cast

import structlog
from opentelemetry import trace

from flownote_observability.config import ObservabilityConfig
from flownote_observability.redaction import redact
from flownote_observability.schema import (
    DEPLOYMENT_ENVIRONMENT_KEY,
    RESERVED_TOP_LEVEL_KEYS,
    SERVICE_NAME_KEY,
    SERVICE_VERSION_KEY,
)
from flownote_observability.severity import severity_from_name

# structlog プロセッサのイベント辞書型。値は任意の Python 値になりうる。
type EventDict = MutableMapping[str, object]
type Processor = Callable[[object, str, EventDict], EventDict]

# ログレベル名 → stdlib logging レベル(structlog のフィルタ用)。
_LEVEL_NAME_TO_INT: dict[str, int] = {
    "TRACE": logging.DEBUG,
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARN": logging.WARNING,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "FATAL": logging.CRITICAL,
}


def _add_timestamp(_logger: object, _method: str, event_dict: EventDict) -> EventDict:
    """RFC3339(ナノ秒・UTC)のタイムスタンプを付与する。

    Args:
        _logger: 未使用(structlog 規約)。
        _method: 未使用。
        event_dict: 加工中のイベント辞書。

    Returns:
        ``timestamp`` を追加したイベント辞書。
    """
    ns = time.time_ns()
    seconds, nanos = divmod(ns, 1_000_000_000)
    dt = datetime.fromtimestamp(seconds, tz=UTC)
    event_dict["timestamp"] = f"{dt:%Y-%m-%dT%H:%M:%S}.{nanos:09d}Z"
    return event_dict


def _add_severity(_logger: object, method_name: str, event_dict: EventDict) -> EventDict:
    """ログメソッド名から重大度(text/number)を付与する。

    Args:
        _logger: 未使用。
        method_name: ``info``/``warning``/``exception`` などの呼び出しメソッド名。
        event_dict: 加工中のイベント辞書。

    Returns:
        ``severity_text`` と ``severity_number`` を追加したイベント辞書。
    """
    severity = severity_from_name(method_name)
    event_dict["severity_text"] = severity.text
    event_dict["severity_number"] = int(severity)
    return event_dict


def _add_trace_context(_logger: object, _method: str, event_dict: EventDict) -> EventDict:
    """OTel の現在 span から trace_id/span_id を相関付与する。

    span が無い(リクエスト外)場合は ``None`` を入れる。

    Args:
        _logger: 未使用。
        _method: 未使用。
        event_dict: 加工中のイベント辞書。

    Returns:
        ``trace_id``/``span_id`` を追加したイベント辞書。
    """
    span_context = trace.get_current_span().get_span_context()
    if span_context.is_valid:
        event_dict["trace_id"] = format(span_context.trace_id, "032x")
        event_dict["span_id"] = format(span_context.span_id, "016x")
    else:
        event_dict["trace_id"] = None
        event_dict["span_id"] = None
    return event_dict


def _format_exception(
    exc_info: bool
    | BaseException
    | tuple[type[BaseException], BaseException, TracebackType | None],
) -> tuple[str, str, str] | None:
    """exc_info を (type, message, stacktrace) に正規化する。

    Args:
        exc_info: ``True``・例外インスタンス・``sys.exc_info()`` 形式のいずれか。

    Returns:
        例外が解決できれば ``(完全型名, メッセージ, トレース文字列)``、無ければ ``None``。
    """
    if exc_info is True:
        import sys

        resolved = sys.exc_info()
        if resolved[1] is None:
            return None
        exc = resolved[1]
    elif isinstance(exc_info, BaseException):
        exc = exc_info
    elif isinstance(exc_info, tuple):
        exc = exc_info[1]
    else:
        # False など対象外はここに到達する。
        return None

    exc_type = type(exc)
    type_name = f"{exc_type.__module__}.{exc_type.__qualname__}"
    stack = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    return type_name, str(exc), stack


def _add_exception(_logger: object, _method: str, event_dict: EventDict) -> EventDict:
    """``exc_info`` を OTel の ``exception.*`` 属性へ構造化する。

    Args:
        _logger: 未使用。
        _method: 未使用。
        event_dict: 加工中のイベント辞書。

    Returns:
        例外があれば ``exception.type``/``exception.message``/``exception.stacktrace`` を
        付与したイベント辞書。
    """
    raw = event_dict.pop("exc_info", None)
    if raw is None or raw is False:
        return event_dict
    # 型を満たす値のみ処理する(それ以外は無視)。
    if raw is True or isinstance(raw, BaseException | tuple):
        formatted = _format_exception(raw)
        if formatted is not None:
            type_name, message, stack = formatted
            event_dict["exception.type"] = type_name
            event_dict["exception.message"] = message
            event_dict["exception.stacktrace"] = stack
    return event_dict


def _make_resource_processor(config: ObservabilityConfig) -> Processor:
    """リソース属性(service.* / deployment.environment.name)を付与するプロセッサを作る。

    Args:
        config: 可観測性構成。

    Returns:
        structlog プロセッサ。
    """

    def _add_resource(_logger: object, _method: str, event_dict: EventDict) -> EventDict:
        event_dict[SERVICE_NAME_KEY] = config.service_name
        event_dict[SERVICE_VERSION_KEY] = config.service_version
        event_dict[DEPLOYMENT_ENVIRONMENT_KEY] = config.environment
        return event_dict

    return _add_resource


def _to_schema(_logger: object, _method: str, event_dict: EventDict) -> EventDict:
    """予約キー以外を ``attributes`` に集約し、message を ``body`` に移す。

    [ログ規約](../../../docs/observability/logging-spec.md) §2 のスキーマ形へ整形する。

    Args:
        _logger: 未使用。
        _method: 未使用。
        event_dict: 加工中のイベント辞書。

    Returns:
        スキーマに整形したイベント辞書。
    """
    # structlog はメッセージを "event" キーに入れる。これを body にする。
    body = event_dict.pop("event", "")
    attributes: dict[str, object] = {}
    reserved: dict[str, object] = {}
    for key, value in event_dict.items():
        if key in RESERVED_TOP_LEVEL_KEYS:
            reserved[key] = value
        else:
            # 相関キーや業務属性はすべて attributes へ集約する。
            attributes[key] = value
    reserved["body"] = body if isinstance(body, str) else str(body)
    reserved["attributes"] = attributes
    return reserved


def _redact_processor(_logger: object, _method: str, event_dict: EventDict) -> EventDict:
    """イベント辞書全体にマスキングを適用する。

    Args:
        _logger: 未使用。
        _method: 未使用。
        event_dict: 加工中のイベント辞書(スキーマ整形済み)。

    Returns:
        機密をマスクしたイベント辞書。
    """
    redacted = redact(dict(event_dict))
    # redact は Mapping を dict で返すため、型を保証しつつ詰め替える。
    if isinstance(redacted, dict):
        event_dict.clear()
        event_dict.update(redacted)
    return event_dict


def build_processors(config: ObservabilityConfig) -> list[Processor]:
    """規約準拠の structlog プロセッサ列(レンダラ手前まで)を構築する。

    テストはこの列を用いて1イベントを手動で流し、スキーマ/相関/マスキングを検証できる。

    Args:
        config: 可観測性構成。

    Returns:
        contextvars マージから整形・マスキングまでのプロセッサ列。
    """
    return [
        structlog.contextvars.merge_contextvars,
        _add_timestamp,
        _add_severity,
        _add_trace_context,
        _add_exception,
        _make_resource_processor(config),
        _to_schema,
        _redact_processor,
    ]


def configure_logging(config: ObservabilityConfig) -> None:
    """structlog をプロセス全体に対して構成する。

    1行JSON を標準出力へ出力し、``config.log_level`` 未満のレベルを抑止する。

    Args:
        config: 可観測性構成。
    """
    min_level = _LEVEL_NAME_TO_INT.get(config.log_level.upper(), logging.INFO)
    processors: list[Processor] = build_processors(config)
    structlog.configure(
        processors=[*processors, structlog.processors.JSONRenderer(ensure_ascii=False)],
        wrapper_class=structlog.make_filtering_bound_logger(min_level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """設定済みの構造化ロガーを取得する。

    Args:
        name: ロガー名(``code.namespace`` 相当)。

    Returns:
        structlog の束縛ロガー。
    """
    # structlog.get_logger は Any を返すため、公開境界で具体型へ明示変換する。
    return cast("structlog.stdlib.BoundLogger", structlog.get_logger(name))
