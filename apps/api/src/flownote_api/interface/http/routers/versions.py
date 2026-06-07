"""バージョン管理のルータ。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from flownote_api.container import Container
from flownote_api.domain.identity import Permission, User
from flownote_api.interface.http.schemas import DiffOut, VersionOut
from flownote_api.interface.security.auth import get_container, require_permission
from flownote_api.shared.routes import (
    ROOT,
    VERSION_DIFF,
    VERSION_RESTORE,
    VERSIONS_PREFIX,
    RouterTag,
)

router = APIRouter(prefix=VERSIONS_PREFIX, tags=[RouterTag.VERSIONS])


@router.get(ROOT)
async def list_versions(
    note_id: str,
    user: User = Depends(require_permission(Permission.NOTE_READ)),
    container: Container = Depends(get_container),
) -> list[VersionOut]:
    """メモのバージョン履歴を取得する。

    Args:
        note_id: メモ識別子。
        user: 認可済みユーザー。
        container: 依存コンテナ。

    Returns:
        バージョン一覧。
    """
    versions = await container.versions.list(owner_id=user.id, note_id=note_id)
    return [VersionOut.from_domain(v) for v in versions]


@router.get(VERSION_DIFF)
async def diff_versions(
    note_id: str,
    from_version: str,
    to_version: str,
    user: User = Depends(require_permission(Permission.NOTE_READ)),
    container: Container = Depends(get_container),
) -> DiffOut:
    """2バージョン間の差分を取得する。

    Args:
        note_id: メモ識別子。
        from_version: 比較元バージョンID。
        to_version: 比較先バージョンID。
        user: 認可済みユーザー。
        container: 依存コンテナ。

    Returns:
        unified diff を含む応答。
    """
    diff = await container.versions.diff(
        owner_id=user.id,
        note_id=note_id,
        from_version_id=from_version,
        to_version_id=to_version,
    )
    return DiffOut(diff=diff)


@router.post(VERSION_RESTORE, status_code=201)
async def restore_version(
    note_id: str,
    version_id: str,
    user: User = Depends(require_permission(Permission.NOTE_WRITE)),
    container: Container = Depends(get_container),
) -> VersionOut:
    """指定バージョンへ復元する(復元内容の新バージョンを生成)。

    Args:
        note_id: メモ識別子。
        version_id: 復元元バージョンID。
        user: 認可済みユーザー。
        container: 依存コンテナ。

    Returns:
        生成された復元バージョン。
    """
    restored = await container.versions.restore(
        owner_id=user.id, note_id=note_id, version_id=version_id
    )
    return VersionOut.from_domain(restored)
