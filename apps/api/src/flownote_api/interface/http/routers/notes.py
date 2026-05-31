"""メモのルータ。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from flownote_api.container import Container
from flownote_api.domain.identity import Permission, User
from flownote_api.interface.http.schemas import NoteCreate, NoteOut, NoteUpdate
from flownote_api.interface.security.auth import get_container, require_permission
from flownote_observability import AuditOutcome, emit_audit

router = APIRouter(prefix="/api/notes", tags=["notes"])


@router.post("", status_code=201)
async def create_note(
    payload: NoteCreate,
    user: User = Depends(require_permission(Permission.NOTE_WRITE)),
    container: Container = Depends(get_container),
) -> NoteOut:
    """メモを作成する。

    Args:
        payload: 作成リクエスト。
        user: 認可済みユーザー。
        container: 依存コンテナ。

    Returns:
        作成されたメモ。
    """
    note = await container.notes.create(owner_id=user.id, title=payload.title, body=payload.body)
    return NoteOut.from_domain(note)


@router.get("")
async def list_notes(
    user: User = Depends(require_permission(Permission.NOTE_READ)),
    container: Container = Depends(get_container),
) -> list[NoteOut]:
    """メモ一覧を取得する。

    Args:
        user: 認可済みユーザー。
        container: 依存コンテナ。

    Returns:
        メモ一覧。
    """
    notes = await container.notes.list(owner_id=user.id)
    return [NoteOut.from_domain(n) for n in notes]


@router.get("/{note_id}")
async def get_note(
    note_id: str,
    user: User = Depends(require_permission(Permission.NOTE_READ)),
    container: Container = Depends(get_container),
) -> NoteOut:
    """メモを取得する。

    Args:
        note_id: メモ識別子。
        user: 認可済みユーザー。
        container: 依存コンテナ。

    Returns:
        該当メモ。
    """
    note = await container.notes.get(owner_id=user.id, note_id=note_id)
    return NoteOut.from_domain(note)


@router.put("/{note_id}")
async def update_note(
    note_id: str,
    payload: NoteUpdate,
    user: User = Depends(require_permission(Permission.NOTE_WRITE)),
    container: Container = Depends(get_container),
) -> NoteOut:
    """メモを更新する(バージョンを追記)。

    Args:
        note_id: メモ識別子。
        payload: 更新リクエスト。
        user: 認可済みユーザー。
        container: 依存コンテナ。

    Returns:
        更新後のメモ。
    """
    note = await container.notes.update(
        owner_id=user.id, note_id=note_id, title=payload.title, body=payload.body
    )
    return NoteOut.from_domain(note)


@router.delete("/{note_id}", status_code=204)
async def delete_note(
    note_id: str,
    user: User = Depends(require_permission(Permission.NOTE_DELETE)),
    container: Container = Depends(get_container),
) -> None:
    """メモを削除する。

    Args:
        note_id: メモ識別子。
        user: 認可済みユーザー(削除権限)。
        container: 依存コンテナ。
    """
    await container.notes.delete(owner_id=user.id, note_id=note_id)
    # 機微操作(削除)は監査ログへ([audit-logging] §3)。
    emit_audit(
        action="note.delete",
        outcome=AuditOutcome.SUCCESS,
        user_id=user.id,
        resource=f"note:{note_id}",
    )
