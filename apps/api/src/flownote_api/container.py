"""依存コンテナ。

合成ルート([architecture.md] §7)で構築し、各ユースケースとトークン検証器を束ねる。
インターフェース層はこのコンテナ経由で依存を受け取る。
"""

from __future__ import annotations

from dataclasses import dataclass

from flownote_api.application.usecases.ai import AIService
from flownote_api.application.usecases.notes import NoteService
from flownote_api.application.usecases.tasks import TaskService
from flownote_api.application.usecases.versions import VersionService
from flownote_api.infrastructure.security.token import TokenVerifier


@dataclass(slots=True)
class Container:
    """アプリ全体の依存を保持するコンテナ。

    Attributes:
        notes: メモのユースケース。
        tasks: タスクのユースケース。
        versions: バージョンのユースケース。
        ai: AI のユースケース。
        token_verifier: トークン検証器。
    """

    notes: NoteService
    tasks: TaskService
    versions: VersionService
    ai: AIService
    token_verifier: TokenVerifier
