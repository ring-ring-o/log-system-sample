"""認証・認可(RBAC)のインターフェース層実装。

トークン検証で認証し、ロールに基づき認可する。認可判定(特に拒否)は必ず監査ログへ記録する
([監査ログ規約](../../../../../docs/observability/audit-logging.md))。ドメイン層は権限を意識しない。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import cast

from fastapi import Depends, Request

from flownote_api.container import Container
from flownote_api.domain.errors import PermissionDeniedError
from flownote_api.domain.identity import Permission, User
from flownote_api.infrastructure.security.token import InvalidTokenError
from flownote_observability import (
    AuditOutcome,
    AuthzDecision,
    bind_request_context,
    emit_audit,
    emit_security,
)

# 許可(allow)を監査する機微権限。これ以外の allow は監査せず量を抑える([audit-logging] §3)。
_SENSITIVE_PERMISSIONS: frozenset[Permission] = frozenset(
    {Permission.NOTE_DELETE, Permission.TASK_DELETE}
)


def get_container(request: Request) -> Container:
    """リクエストからアプリの依存コンテナを取り出す。

    Args:
        request: 現在のリクエスト。

    Returns:
        合成ルートで設定された :class:`Container`。
    """
    return cast("Container", request.app.state.container)


def _bearer_token(request: Request) -> str:
    """``Authorization: Bearer`` ヘッダからトークンを取り出す。

    Args:
        request: 現在のリクエスト。

    Returns:
        トークン文字列。

    Raises:
        InvalidTokenError: ヘッダが無い/形式不正の場合。
    """
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise InvalidTokenError("missing_bearer")
    return token


async def get_current_user(request: Request, container: Container = Depends(get_container)) -> User:
    """トークンを検証し認証済みユーザーを返す。

    認証主体を実行文脈に束縛し、以降のログへ ``user.id`` を相関させる。検証失敗は
    セキュリティログに記録する。

    Args:
        request: 現在のリクエスト。
        container: 依存コンテナ。

    Returns:
        認証済み :class:`User`。

    Raises:
        InvalidTokenError: 認証に失敗した場合(401 へ変換される)。
    """
    client_address = request.client.host if request.client else None
    try:
        token = _bearer_token(request)
        verified = await container.token_verifier.verify(token)
    except InvalidTokenError as exc:
        # 攻撃検知のためセキュリティログへ(主体不明でも記録)。
        emit_security(action="auth.token.verify", reason=exc.reason, client_address=client_address)
        raise
    user = User(id=verified.subject, roles=verified.roles)
    # 認証主体を文脈束縛し、以降のログに user.id を相関させる。
    bind_request_context(request_id=_request_id(request), user_id=user.id)
    return user


def _request_id(request: Request) -> str:
    """ミドルウェアが付与した request_id を取り出す(無ければ空)。

    Args:
        request: 現在のリクエスト。

    Returns:
        request_id 文字列。
    """
    value = request.headers.get("x-request-id")
    return value if value else cast("str", getattr(request.state, "request_id", ""))


def require_permission(
    permission: Permission,
) -> Callable[[Request, User], Awaitable[User]]:
    """指定権限を要求する FastAPI 依存を生成する。

    Args:
        permission: 必要な権限。

    Returns:
        認可済みユーザーを返す依存関数。許可時は監査(成功)、拒否時は監査(拒否)を記録する。
    """

    async def _dependency(request: Request, user: User = Depends(get_current_user)) -> User:
        client_address = request.client.host if request.client else None
        if not user.has_permission(permission):
            emit_audit(
                action="authz.decision",
                outcome=AuditOutcome.DENIED,
                user_id=user.id,
                roles=[r.value for r in user.roles],
                permission=permission.value,
                decision=AuthzDecision.DENY,
                client_address=client_address,
            )
            raise PermissionDeniedError(permission.value)
        # 量制御([audit-logging] §3): 許可は機微操作(削除)のみ記録。通常の read/write は
        # access ログに委ね、監査ログの膨張を避ける。拒否は上で必ず記録済み。
        if permission in _SENSITIVE_PERMISSIONS:
            emit_audit(
                action="authz.decision",
                outcome=AuditOutcome.SUCCESS,
                user_id=user.id,
                roles=[r.value for r in user.roles],
                permission=permission.value,
                decision=AuthzDecision.ALLOW,
            )
        return user

    return _dependency
