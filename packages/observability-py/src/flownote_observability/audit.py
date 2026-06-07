"""監査ログ/セキュリティログのヘルパ。

[監査ログ規約](../../../docs/observability/audit-logging.md) を実装する。
認証認可・機微操作を ``event.domain`` で業務ログと分離して記録する。
"""

from __future__ import annotations

from enum import StrEnum

import structlog

from flownote_observability.conventions import EventDomain
from flownote_observability.logging_setup import get_logger
from flownote_observability.semconv import (
    AUDIT_ACTION_KEY,
    AUDIT_OUTCOME_KEY,
    AUTHZ_DECISION_KEY,
    AUTHZ_PERMISSION_KEY,
    AUTHZ_RESOURCE_KEY,
    CLIENT_ADDRESS_KEY,
    EVENT_DOMAIN_KEY,
    SECURITY_REASON_KEY,
    USER_ID_KEY,
    USER_ROLES_KEY,
)

_logger = get_logger("flownote_observability.audit")


class AuditOutcome(StrEnum):
    """監査結果。

    Attributes:
        SUCCESS: 成功。
        FAILURE: 失敗(認証失敗など)。
        DENIED: 認可拒否。
    """

    SUCCESS = "success"
    FAILURE = "failure"
    DENIED = "denied"


class AuthzDecision(StrEnum):
    """認可判定。

    Attributes:
        ALLOW: 許可。
        DENY: 拒否。
    """

    ALLOW = "allow"
    DENY = "deny"


def emit_audit(
    *,
    action: str,
    outcome: AuditOutcome,
    user_id: str | None = None,
    roles: list[str] | None = None,
    resource: str | None = None,
    permission: str | None = None,
    decision: AuthzDecision | None = None,
    client_address: str | None = None,
) -> None:
    """監査イベントを記録する。

    成功は INFO、失敗/拒否は WARN で出力する([監査ログ規約] §2,§4)。
    ``event.domain="audit"`` を付与し、業務ログと判別可能にする。機密(パスワード/トークン)は
    引数に渡さない方針とし、混入してもマスキングプロセッサが除去する。

    Args:
        action: 動詞.対象(``auth.login``/``authz.decision``/``note.delete`` 等)。
        outcome: 監査結果。
        user_id: 認証主体の不透明ID。未認証なら ``None``。
        roles: 判定時点のロール一覧。
        resource: 対象リソース識別子(``note:{id}`` 等)。
        permission: 要求権限(``note:read`` 等)。
        decision: 認可判定(``allow``/``deny``)。
        client_address: 送信元アドレス。
    """
    attributes: dict[str, object] = {
        EVENT_DOMAIN_KEY: EventDomain.AUDIT,
        AUDIT_ACTION_KEY: action,
        AUDIT_OUTCOME_KEY: outcome.value,
    }
    if user_id is not None:
        attributes[USER_ID_KEY] = user_id
    if roles is not None:
        attributes[USER_ROLES_KEY] = roles
    if resource is not None:
        attributes[AUTHZ_RESOURCE_KEY] = resource
    if permission is not None:
        attributes[AUTHZ_PERMISSION_KEY] = permission
    if decision is not None:
        attributes[AUTHZ_DECISION_KEY] = decision.value
    if client_address is not None:
        attributes[CLIENT_ADDRESS_KEY] = client_address

    _emit(outcome, action, attributes)


def emit_security(
    *,
    action: str,
    outcome: AuditOutcome = AuditOutcome.FAILURE,
    client_address: str | None = None,
    reason: str | None = None,
) -> None:
    """セキュリティイベント(攻撃/異常検知)を記録する。

    ``event.domain="security"`` を付与する。主体不明でも記録する([監査ログ規約] §6)。

    Args:
        action: 事象(``auth.token.verify``/``cors.violation`` 等)。
        outcome: 監査結果(既定は失敗)。
        client_address: 送信元アドレス。
        reason: 失敗理由の分類(``expired``/``invalid_signature`` 等)。
    """
    attributes: dict[str, object] = {
        EVENT_DOMAIN_KEY: EventDomain.SECURITY,
        AUDIT_ACTION_KEY: action,
        AUDIT_OUTCOME_KEY: outcome.value,
    }
    if client_address is not None:
        attributes[CLIENT_ADDRESS_KEY] = client_address
    if reason is not None:
        attributes[SECURITY_REASON_KEY] = reason
    _emit(outcome, action, attributes)


def _emit(outcome: AuditOutcome, action: str, attributes: dict[str, object]) -> None:
    """結果に応じた重大度で監査/セキュリティイベントを出力する。

    Args:
        outcome: 監査結果。
        action: 事象名(ログの body)。
        attributes: 付与する属性。
    """
    bound: structlog.stdlib.BoundLogger = _logger.bind(**attributes)
    if outcome is AuditOutcome.SUCCESS:
        bound.info(action)
    else:
        # 失敗・拒否は注意喚起のため WARN とする。
        bound.warning(action)
