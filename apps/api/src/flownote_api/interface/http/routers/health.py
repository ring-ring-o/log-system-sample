"""ヘルスチェックルータ(認証不要)。"""

from __future__ import annotations

from fastapi import APIRouter

from flownote_api.shared.routes import HEALTH, RouterTag

# ヘルス応答の本文キーと値(運用監視が参照する契約)。
_STATUS_KEY = "status"
_STATUS_OK = "ok"

router = APIRouter(tags=[RouterTag.HEALTH])


@router.get(HEALTH)
async def health() -> dict[str, str]:
    """稼働確認用エンドポイント。

    Returns:
        ステータスを表す辞書。
    """
    return {_STATUS_KEY: _STATUS_OK}
