"""識別子生成アダプタ。"""

from __future__ import annotations

from uuid import uuid4


class UuidGenerator:
    """UUID4 に基づく :class:`flownote_api.domain.ports.IdGenerator` 実装。"""

    def new_id(self) -> str:
        """新しい UUID4 文字列を返す。

        Returns:
            一意な識別子。
        """
        return str(uuid4())
