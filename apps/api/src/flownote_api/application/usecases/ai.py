"""AI のユースケース(相談 / 統合検索 / 進捗レビュー)。

メモ・タスクを文脈に AI ポートを呼び出す。垂直導線
「メモ作成 → AI統合検索 → タスク化 → AI相談」の中核であり、ログ観察の主動線
([concept.md] §5)。
"""

from __future__ import annotations

from dataclasses import dataclass

from flownote_api.domain.ai import (
    AIUseCase,
    ChatMessage,
    ChatRole,
    ConsultResult,
    ProgressInsight,
    SearchDocument,
    SearchHit,
)
from flownote_api.domain.errors import NotFoundError
from flownote_api.domain.kinds import EntityType
from flownote_api.domain.ports import AIAssistant, NoteRepository, TaskRepository
from flownote_api.shared.telemetry import (
    SEARCH_HIT_COUNT_KEY,
    TASK_STALLED_COUNT_KEY,
    AppEvent,
    SpanName,
)
from flownote_observability import get_logger, get_tracer
from flownote_observability.semconv import FLOWNOTE_AI_USE_CASE_KEY

_logger = get_logger("flownote_api.usecases.ai")
_tracer = get_tracer("flownote_api.usecases.ai")

# 相談時にメモ本文を文脈へ載せる際の最大文字数(プロンプト肥大とコストの抑制)。
_CONTEXT_BODY_MAX = 2000


@dataclass(slots=True)
class AIService:
    """AI 相談・統合検索・進捗レビューを司るユースケース群。

    Attributes:
        assistant: AI ポート(OpenAI互換/スタブ)。
        notes: メモ永続化ポート。
        tasks: タスク永続化ポート。
    """

    assistant: AIAssistant
    notes: NoteRepository
    tasks: TaskRepository

    async def consult(
        self, *, owner_id: str, question: str, note_id: str | None = None
    ) -> ConsultResult:
        """メモを文脈に相談へ応答する。

        Args:
            owner_id: 要求者の不透明ID。
            question: 相談内容。
            note_id: 文脈にするメモ(任意)。

        Returns:
            AI の応答。

        Raises:
            NotFoundError: 指定メモが存在しない/所有者が異なる場合。
        """
        with _tracer.start_as_current_span(SpanName.USECASE_AI_CONSULT):
            messages: list[ChatMessage] = [
                ChatMessage(
                    role=ChatRole.SYSTEM, content="あなたは作業管理を支援するアシスタントです。"
                )
            ]
            if note_id is not None:
                note = await self.notes.get(note_id)
                if note is None or note.owner_id != owner_id:
                    raise NotFoundError(EntityType.NOTE, note_id)
                context = note.body[:_CONTEXT_BODY_MAX]
                messages.append(
                    ChatMessage(role=ChatRole.USER, content=f"次のメモを参考にして:\n{context}")
                )
            messages.append(ChatMessage(role=ChatRole.USER, content=question))
            result = await self.assistant.consult(messages)
            _logger.info(
                AppEvent.AI_CONSULT_COMPLETED,
                **{FLOWNOTE_AI_USE_CASE_KEY: AIUseCase.TASK_CONSULT},
            )
            return result

    async def search(self, *, owner_id: str, query: str) -> list[SearchHit]:
        """メモ・タスク横断の統合検索を行う。

        Args:
            owner_id: 要求者の不透明ID。
            query: 検索クエリ。

        Returns:
            関連度順のヒット一覧。
        """
        with _tracer.start_as_current_span(SpanName.USECASE_AI_SEARCH):
            notes = await self.notes.list_by_owner(owner_id)
            tasks = await self.tasks.list_by_owner(owner_id)
            documents: list[SearchDocument] = [
                SearchDocument(kind=EntityType.NOTE, id=n.id, title=n.title, text=n.body)
                for n in notes
            ]
            documents += [
                SearchDocument(kind=EntityType.TASK, id=t.id, title=t.title, text=t.title)
                for t in tasks
            ]
            hits = await self.assistant.search(query, documents)
            _logger.info(
                AppEvent.AI_SEARCH_COMPLETED,
                **{
                    FLOWNOTE_AI_USE_CASE_KEY: AIUseCase.UNIFIED_SEARCH,
                    SEARCH_HIT_COUNT_KEY: len(hits),
                },
            )
            return hits

    async def review_progress(self, *, owner_id: str) -> ProgressInsight:
        """所有者のタスク進捗をレビューする。

        Args:
            owner_id: 要求者の不透明ID。

        Returns:
            進捗の洞察。
        """
        with _tracer.start_as_current_span(SpanName.USECASE_AI_REVIEW_PROGRESS):
            tasks = await self.tasks.list_by_owner(owner_id)
            insight = await self.assistant.review_progress(tasks)
            _logger.info(
                AppEvent.AI_PROGRESS_REVIEWED,
                **{
                    FLOWNOTE_AI_USE_CASE_KEY: AIUseCase.PROGRESS_REVIEW,
                    TASK_STALLED_COUNT_KEY: len(insight.stalled_task_ids),
                },
            )
            return insight
