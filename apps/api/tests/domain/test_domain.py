"""ドメイン層のテスト(不変条件・認可・差分・滞留判定)。

ドメインに紐づく振る舞いを固定する([architecture.md] §6)。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from flownote_api.domain.errors import ValidationError
from flownote_api.domain.identity import Permission, Role, User
from flownote_api.domain.notes import Note
from flownote_api.domain.tasks import Task, TaskStatus
from flownote_api.domain.versions import compute_unified_diff

_NOW = datetime(2026, 5, 31, tzinfo=UTC)


def test_role_permission_hierarchy() -> None:
    viewer = User(id="u", roles=frozenset({Role.VIEWER}))
    editor = User(id="u", roles=frozenset({Role.EDITOR}))
    admin = User(id="u", roles=frozenset({Role.ADMIN}))

    # viewer は読みのみ。
    assert viewer.has_permission(Permission.NOTE_READ)
    assert not viewer.has_permission(Permission.NOTE_WRITE)
    # editor は書き込み・AI 可、削除不可。
    assert editor.has_permission(Permission.NOTE_WRITE)
    assert editor.has_permission(Permission.AI_USE)
    assert not editor.has_permission(Permission.NOTE_DELETE)
    # admin は削除も可。
    assert admin.has_permission(Permission.NOTE_DELETE)
    assert admin.has_permission(Permission.TASK_DELETE)
    # 運用管理(動的ログレベル変更等)は admin のみ。
    assert admin.has_permission(Permission.ADMIN_MANAGE)
    assert not editor.has_permission(Permission.ADMIN_MANAGE)
    assert not viewer.has_permission(Permission.ADMIN_MANAGE)


def test_note_title_validation() -> None:
    with pytest.raises(ValidationError):
        Note(id="n", owner_id="u", title="  ", body="", created_at=_NOW, updated_at=_NOW)


def test_note_edited_updates_timestamp() -> None:
    note = Note(id="n", owner_id="u", title="t", body="b", created_at=_NOW, updated_at=_NOW)
    later = _NOW + timedelta(hours=1)
    edited = note.edited(title="t2", body="b2", now=later)
    assert edited.title == "t2"
    assert edited.updated_at == later
    # 元のインスタンスは不変。
    assert note.title == "t"


def test_task_stalled_detection() -> None:
    old = _NOW - timedelta(days=10)
    doing = Task(
        id="t",
        owner_id="u",
        title="x",
        status=TaskStatus.DOING,
        note_id=None,
        created_at=old,
        updated_at=old,
    )
    todo = doing.with_status(TaskStatus.TODO, now=old)
    assert doing.is_stalled(now=_NOW)
    # TODO は滞留扱いにしない。
    assert not todo.is_stalled(now=_NOW)


def test_unified_diff() -> None:
    diff = compute_unified_diff("a\nb\n", "a\nc\n")
    assert "-b" in diff
    assert "+c" in diff
    # 同一内容は空。
    assert compute_unified_diff("same\n", "same\n") == ""
