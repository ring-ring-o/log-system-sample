"""ドメインのエンティティ種別。

メモ/タスク/バージョンといった資源の種別を表す列挙。``NotFoundError`` の対象種別、統合検索の
``SearchDocument.kind``、監査ログの資源識別子(``note:{id}`` 等)で同一の語彙を用い、
文字列リテラルの散在と綴りの揺れを防ぐ。
"""

from __future__ import annotations

from enum import StrEnum


class EntityType(StrEnum):
    """資源の種別。

    Attributes:
        NOTE: メモ。
        TASK: タスク。
        VERSION: メモのバージョン。
    """

    NOTE = "note"
    TASK = "task"
    VERSION = "version"

    def resource_id(self, identifier: str) -> str:
        """監査ログ用の資源識別子(``<種別>:<id>``)を組み立てる。

        Args:
            identifier: 資源の識別子。

        Returns:
            ``note:abc`` のような資源識別子。
        """
        return f"{self.value}:{identifier}"
