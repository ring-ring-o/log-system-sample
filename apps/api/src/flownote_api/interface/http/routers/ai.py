"""AI のルータ(相談 / 統合検索 / 進捗レビュー)。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from flownote_api.container import Container
from flownote_api.domain.identity import Permission, User
from flownote_api.interface.http.schemas import (
    ConsultOut,
    ConsultRequest,
    ProgressOut,
    SearchHitOut,
    SearchOut,
    SearchRequest,
)
from flownote_api.interface.security.auth import get_container, require_permission

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.post("/consult")
async def consult(
    payload: ConsultRequest,
    user: User = Depends(require_permission(Permission.AI_USE)),
    container: Container = Depends(get_container),
) -> ConsultOut:
    """AI に相談する。

    Args:
        payload: 相談リクエスト。
        user: 認可済みユーザー。
        container: 依存コンテナ。

    Returns:
        AI の応答。
    """
    result = await container.ai.consult(
        owner_id=user.id, question=payload.question, note_id=payload.note_id
    )
    return ConsultOut(message=result.message, model=result.model)


@router.post("/search")
async def search(
    payload: SearchRequest,
    user: User = Depends(require_permission(Permission.AI_USE)),
    container: Container = Depends(get_container),
) -> SearchOut:
    """メモ・タスク横断の統合検索を行う。

    Args:
        payload: 検索リクエスト。
        user: 認可済みユーザー。
        container: 依存コンテナ。

    Returns:
        ヒット一覧。
    """
    hits = await container.ai.search(owner_id=user.id, query=payload.query)
    return SearchOut(
        hits=[
            SearchHitOut(kind=h.kind, id=h.id, title=h.title, score=h.score, snippet=h.snippet)
            for h in hits
        ]
    )


@router.get("/progress")
async def review_progress(
    user: User = Depends(require_permission(Permission.AI_USE)),
    container: Container = Depends(get_container),
) -> ProgressOut:
    """タスク進捗をレビューする。

    Args:
        user: 認可済みユーザー。
        container: 依存コンテナ。

    Returns:
        進捗の洞察。
    """
    insight = await container.ai.review_progress(owner_id=user.id)
    return ProgressOut(
        summary=insight.summary,
        stalled_task_ids=list(insight.stalled_task_ids),
        suggestions=list(insight.suggestions),
    )
