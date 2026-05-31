"""アイデンティティと認可(RBAC)のドメインモデル。

[ADR 0004](../../../../docs/adr/0004-auth-keycloak.md) と
[監査ログ規約](../../../../docs/observability/audit-logging.md) §4 のロール定義に対応する。
認可はフレームワーク非依存の純粋ロジックとしてここに置き、アプリ層が呼び出す。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Role(StrEnum):
    """ユーザーのロール。

    Attributes:
        VIEWER: 閲覧・検索のみ。
        EDITOR: VIEWER + 作成・更新・AI利用。
        ADMIN: EDITOR + 削除・管理。
    """

    VIEWER = "viewer"
    EDITOR = "editor"
    ADMIN = "admin"


class Permission(StrEnum):
    """きめ細かな権限。

    Attributes:
        NOTE_READ: メモ閲覧。
        NOTE_WRITE: メモ作成・更新。
        NOTE_DELETE: メモ削除。
        TASK_READ: タスク閲覧。
        TASK_WRITE: タスク作成・更新。
        TASK_DELETE: タスク削除。
        AI_USE: AI 機能の利用。
    """

    NOTE_READ = "note:read"
    NOTE_WRITE = "note:write"
    NOTE_DELETE = "note:delete"
    TASK_READ = "task:read"
    TASK_WRITE = "task:write"
    TASK_DELETE = "task:delete"
    AI_USE = "ai:use"


# ロール → 権限集合。上位ロールは下位の権限を包含する。
_VIEWER_PERMS: frozenset[Permission] = frozenset({Permission.NOTE_READ, Permission.TASK_READ})
_EDITOR_PERMS: frozenset[Permission] = _VIEWER_PERMS | {
    Permission.NOTE_WRITE,
    Permission.TASK_WRITE,
    Permission.AI_USE,
}
_ADMIN_PERMS: frozenset[Permission] = _EDITOR_PERMS | {
    Permission.NOTE_DELETE,
    Permission.TASK_DELETE,
}

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.VIEWER: _VIEWER_PERMS,
    Role.EDITOR: _EDITOR_PERMS,
    Role.ADMIN: _ADMIN_PERMS,
}


@dataclass(frozen=True, slots=True)
class User:
    """認証済みユーザー。

    Attributes:
        id: 不透明な主体ID(Keycloak ``sub``)。PII は含めない。
        roles: 付与されたロール集合。
    """

    id: str
    roles: frozenset[Role]

    def permissions(self) -> frozenset[Permission]:
        """保有ロールから導かれる権限の和集合を返す。

        Returns:
            ユーザーが持つ全権限。
        """
        result: frozenset[Permission] = frozenset()
        for role in self.roles:
            result |= ROLE_PERMISSIONS.get(role, frozenset())
        return result

    def has_permission(self, permission: Permission) -> bool:
        """指定権限を保有するか判定する。

        Args:
            permission: 判定する権限。

        Returns:
            保有していれば ``True``。
        """
        return permission in self.permissions()
