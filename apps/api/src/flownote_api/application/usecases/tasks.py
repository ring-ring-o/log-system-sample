"""タスクのユースケース。"""

from __future__ import annotations

from dataclasses import dataclass

from flownote_api.domain.errors import NotFoundError
from flownote_api.domain.kinds import EntityType
from flownote_api.domain.ports import Clock, IdGenerator, TaskRepository
from flownote_api.domain.tasks import Task, TaskStatus
from flownote_api.shared.telemetry import (
    TASK_ID_KEY,
    TASK_STATUS_KEY,
    AppEvent,
    SpanName,
)
from flownote_observability import get_logger, get_tracer

_logger = get_logger("flownote_api.usecases.tasks")
_tracer = get_tracer("flownote_api.usecases.tasks")


@dataclass(slots=True)
class TaskService:
    """タスクの作成・取得・状態変更・削除を司るユースケース群。

    Attributes:
        tasks: タスク永続化ポート。
        clock: 時刻供給ポート。
        ids: 識別子生成ポート。
    """

    tasks: TaskRepository
    clock: Clock
    ids: IdGenerator

    async def create(self, *, owner_id: str, title: str, note_id: str | None = None) -> Task:
        """タスクを新規作成する(メモ由来も可)。

        Args:
            owner_id: 所有ユーザーの不透明ID。
            title: タイトル。
            note_id: 由来メモの識別子(任意)。

        Returns:
            作成されたタスク。
        """
        with _tracer.start_as_current_span(SpanName.USECASE_TASK_CREATE):
            now = self.clock.now()
            task = Task(
                id=self.ids.new_id(),
                owner_id=owner_id,
                title=title,
                status=TaskStatus.TODO,
                note_id=note_id,
                created_at=now,
                updated_at=now,
            )
            await self.tasks.add(task)
            _logger.info(
                AppEvent.TASK_CREATED,
                **{TASK_ID_KEY: task.id, TASK_STATUS_KEY: task.status.value},
            )
            return task

    async def get(self, *, owner_id: str, task_id: str) -> Task:
        """所有者のタスクを取得する。

        Args:
            owner_id: 要求者の不透明ID。
            task_id: タスク識別子。

        Returns:
            該当タスク。

        Raises:
            NotFoundError: 存在しない、または所有者が異なる場合。
        """
        task = await self.tasks.get(task_id)
        if task is None or task.owner_id != owner_id:
            raise NotFoundError(EntityType.TASK, task_id)
        return task

    async def list(self, *, owner_id: str) -> list[Task]:
        """所有者のタスク一覧を返す。

        Args:
            owner_id: 所有ユーザーの不透明ID。

        Returns:
            タスク一覧。
        """
        return await self.tasks.list_by_owner(owner_id)

    async def change_status(self, *, owner_id: str, task_id: str, status: TaskStatus) -> Task:
        """タスクの状態を変更する。

        Args:
            owner_id: 要求者の不透明ID。
            task_id: タスク識別子。
            status: 新しい状態。

        Returns:
            状態変更後のタスク。

        Raises:
            NotFoundError: 存在しない、または所有者が異なる場合。
        """
        current = await self.get(owner_id=owner_id, task_id=task_id)
        updated = current.with_status(status, now=self.clock.now())
        await self.tasks.update(updated)
        _logger.info(
            AppEvent.TASK_STATUS_CHANGED,
            **{
                TASK_ID_KEY: task_id,
                TASK_STATUS_KEY: status.value,
            },
        )
        return updated

    async def delete(self, *, owner_id: str, task_id: str) -> None:
        """タスクを削除する。

        Args:
            owner_id: 要求者の不透明ID。
            task_id: タスク識別子。

        Raises:
            NotFoundError: 存在しない、または所有者が異なる場合。
        """
        await self.get(owner_id=owner_id, task_id=task_id)
        await self.tasks.delete(task_id)
        _logger.info(AppEvent.TASK_DELETED, **{TASK_ID_KEY: task_id})
