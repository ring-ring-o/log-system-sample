"""ヘルスチェックルータ(認証不要)。"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """稼働確認用エンドポイント。

    Returns:
        ステータスを表す辞書。
    """
    return {"status": "ok"}
