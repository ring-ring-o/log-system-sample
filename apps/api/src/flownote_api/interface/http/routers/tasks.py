"""タスクのルータ。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from flownote_api.container import Container
from flownote_api.domain.identity import Permission, User
from flownote_api.interface.http.schemas import TaskCreate, TaskOut, TaskStatusUpdate
from flownote_api.interface.security.auth import get_container, require_permission
from flownote_observability import AuditOutcome, emit_audit

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.post("", status_code=201)
async def create_task(
    payload: TaskCreate,
    user: User = Depends(require_permission(Permission.TASK_WRITE)),
    container: Container = Depends(get_container),
) -> TaskOut:
    """タスクを作成する。

    Args:
        payload: 作成リクエスト。
        user: 認可済みユーザー。
        container: 依存コンテナ。

    Returns:
        作成されたタスク。
    """
    task = await container.tasks.create(
        owner_id=user.id, title=payload.title, note_id=payload.note_id
    )
    return TaskOut.from_domain(task)


@router.get("")
async def list_tasks(
    user: User = Depends(require_permission(Permission.TASK_READ)),
    container: Container = Depends(get_container),
) -> list[TaskOut]:
    """タスク一覧を取得する。

    Args:
        user: 認可済みユーザー。
        container: 依存コンテナ。

    Returns:
        タスク一覧。
    """
    tasks = await container.tasks.list(owner_id=user.id)
    return [TaskOut.from_domain(t) for t in tasks]


@router.patch("/{task_id}/status")
async def change_task_status(
    task_id: str,
    payload: TaskStatusUpdate,
    user: User = Depends(require_permission(Permission.TASK_WRITE)),
    container: Container = Depends(get_container),
) -> TaskOut:
    """タスクの状態を変更する。

    Args:
        task_id: タスク識別子。
        payload: 状態変更リクエスト。
        user: 認可済みユーザー。
        container: 依存コンテナ。

    Returns:
        状態変更後のタスク。
    """
    task = await container.tasks.change_status(
        owner_id=user.id, task_id=task_id, status=payload.status
    )
    return TaskOut.from_domain(task)


@router.delete("/{task_id}", status_code=204)
async def delete_task(
    task_id: str,
    user: User = Depends(require_permission(Permission.TASK_DELETE)),
    container: Container = Depends(get_container),
) -> None:
    """タスクを削除する。

    Args:
        task_id: タスク識別子。
        user: 認可済みユーザー(削除権限)。
        container: 依存コンテナ。
    """
    await container.tasks.delete(owner_id=user.id, task_id=task_id)
    # 機微操作(削除)は監査ログへ([audit-logging] §3)。
    emit_audit(
        action="task.delete",
        outcome=AuditOutcome.SUCCESS,
        user_id=user.id,
        resource=f"task:{task_id}",
    )
