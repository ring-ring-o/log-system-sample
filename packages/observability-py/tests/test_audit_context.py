"""監査ログとコンテキスト束縛のテスト([audit-logging] の固定)。"""

from __future__ import annotations

from dataclasses import dataclass, field

import structlog

from flownote_observability.audit import (
    AuditOutcome,
    AuthzDecision,
    emit_audit,
    emit_security,
)
from flownote_observability.context import (
    bind_request_context,
    clear_request_context,
    hash_session_id,
)


@dataclass(slots=True)
class _Captured:
    """structlog の出力を捕捉するための保持器。"""

    records: list[dict[str, object]] = field(default_factory=list)


def _capture() -> _Captured:
    """structlog を捕捉モードに設定し、捕捉器を返す。

    Returns:
        以後のログを蓄積する :class:`_Captured`。
    """
    captured = _Captured()

    def _sink(_logger: object, _method: str, event_dict: dict[str, object]) -> str:
        # 終端プロセッサとして event_dict を捕捉し、ロガーには空文字を渡す。
        captured.records.append(dict(event_dict))
        return ""

    structlog.configure(
        processors=[structlog.contextvars.merge_contextvars, _sink],
        wrapper_class=structlog.make_filtering_bound_logger(0),
        logger_factory=structlog.ReturnLoggerFactory(),
        cache_logger_on_first_use=False,
    )
    return captured


def test_audit_login_success_is_info_and_separated() -> None:
    captured = _capture()
    emit_audit(action="auth.login", outcome=AuditOutcome.SUCCESS, user_id="u1")
    record = captured.records[-1]
    assert record["event.domain"] == "audit"
    assert record["audit.action"] == "auth.login"
    assert record["audit.outcome"] == "success"
    assert record["user.id"] == "u1"


def test_authz_denied_is_recorded() -> None:
    captured = _capture()
    emit_audit(
        action="authz.decision",
        outcome=AuditOutcome.DENIED,
        user_id="u1",
        resource="note:42",
        permission="note:delete",
        decision=AuthzDecision.DENY,
    )
    record = captured.records[-1]
    assert record["event.domain"] == "audit"
    assert record["authz.decision"] == "deny"
    assert record["authz.resource"] == "note:42"


def test_security_event_records_without_user() -> None:
    captured = _capture()
    emit_security(action="auth.token.verify", reason="expired", client_address="10.0.0.1")
    record = captured.records[-1]
    assert record["event.domain"] == "security"
    assert record["security.reason"] == "expired"
    assert record["client.address"] == "10.0.0.1"


def test_context_binding_and_session_hash() -> None:
    captured = _capture()
    clear_request_context()
    bind_request_context(request_id="req-1", user_id="u9", session_id="raw-session")
    logger = structlog.get_logger("ctx")
    logger.info("some.event")
    record = captured.records[-1]
    # 束縛キーが自動継承される。
    assert record["request_id"] == "req-1"
    assert record["user.id"] == "u9"
    # session_id は生値ではなくハッシュで束縛される。
    assert record["session_id"] == hash_session_id("raw-session")
    assert record["session_id"] != "raw-session"
    clear_request_context()
