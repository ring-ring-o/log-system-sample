"""時刻供給アダプタ。"""

from __future__ import annotations

from datetime import UTC, datetime


class SystemClock:
    """システム時計に基づく :class:`flownote_api.domain.ports.Clock` 実装。"""

    def now(self) -> datetime:
        """現在時刻(UTC)を返す。

        Returns:
            タイムゾーン付き現在時刻。
        """
        return datetime.now(UTC)
