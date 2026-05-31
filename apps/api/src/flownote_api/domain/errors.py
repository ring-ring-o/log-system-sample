"""ドメイン例外。

レイヤをまたいで意味のあるエラーを表現する。インターフェース層でこれらを HTTP 応答へ変換し、
[ログ規約](../../../../docs/observability/logging-spec.md) に従って重大度付きで記録する。
"""

from __future__ import annotations


class DomainError(Exception):
    """ドメイン層の基底例外。"""


class NotFoundError(DomainError):
    """要求された資源が存在しないことを表す。

    Attributes:
        entity: 資源種別(``note`` 等)。
        entity_id: 資源識別子。
    """

    def __init__(self, entity: str, entity_id: str) -> None:
        """エラーを生成する。

        Args:
            entity: 資源種別。
            entity_id: 資源識別子。
        """
        self.entity = entity
        self.entity_id = entity_id
        super().__init__(f"{entity} が見つかりません: {entity_id}")


class PermissionDeniedError(DomainError):
    """要求された操作が認可されないことを表す。

    Attributes:
        permission: 要求された権限。
        resource: 対象資源(任意)。
    """

    def __init__(self, permission: str, resource: str | None = None) -> None:
        """エラーを生成する。

        Args:
            permission: 要求された権限。
            resource: 対象資源識別子。
        """
        self.permission = permission
        self.resource = resource
        super().__init__(f"権限がありません: {permission}")


class ValidationError(DomainError):
    """入力がドメインの不変条件に反することを表す。"""


class ConflictError(DomainError):
    """資源の競合(重複・不正な状態遷移など)を表す。"""
