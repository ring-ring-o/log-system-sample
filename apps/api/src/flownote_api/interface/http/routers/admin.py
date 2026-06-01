"""運用管理ルータ(ADMIN 限定)。

本番事故時にプロセス再起動なしでログ閾値を変更するための ``/admin/log-level`` を提供する
([ログ規約] §7)。再起動は状態リセット等の副作用を伴うため、運用中の一時的な詳細化
(INFO → DEBUG)を API で行えるようにする。変更操作は監査ログに残す。

注意(マルチワーカー): 閾値はプロセスグローバルのため、本エンドポイントは**リクエストを
処理したワーカーのみ**に作用する。``--workers N`` 構成では全ワーカーへ反映するには各ワーカーへ
配信する仕組み(共有設定の監視・シグナル・オーケストレータ経由のローリング適用)が別途必要。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from flownote_api.domain.identity import Permission, User
from flownote_api.interface.security.auth import require_permission
from flownote_observability import AuditOutcome, emit_audit, get_log_level, set_log_level

router = APIRouter(prefix="/admin", tags=["admin"])


class LogLevelOut(BaseModel):
    """現在のログ閾値応答。"""

    level: str


class LogLevelUpdate(BaseModel):
    """ログ閾値変更リクエスト。"""

    level: str


@router.get("/log-level")
async def read_log_level(
    _user: User = Depends(require_permission(Permission.ADMIN_MANAGE)),
) -> LogLevelOut:
    """現在のログ閾値を返す。

    Args:
        _user: 管理権限を持つ認可済みユーザー。

    Returns:
        現在の閾値ラベル。
    """
    return LogLevelOut(level=get_log_level())


@router.put("/log-level")
async def update_log_level(
    payload: LogLevelUpdate,
    user: User = Depends(require_permission(Permission.ADMIN_MANAGE)),
) -> LogLevelOut:
    """ログ閾値をプロセス再起動なしで変更する(機微操作のため監査記録)。

    Args:
        payload: 変更後のレベル。
        user: 管理権限を持つ認可済みユーザー。

    Returns:
        反映後の閾値ラベル。
    """
    set_log_level(payload.level)
    applied = get_log_level()
    emit_audit(
        action="admin.log_level.change",
        outcome=AuditOutcome.SUCCESS,
        user_id=user.id,
        resource=f"log_level:{applied}",
    )
    return LogLevelOut(level=applied)
