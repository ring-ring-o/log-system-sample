"""AI のユースケース(相談 / 統合検索 / 進捗レビュー)。

メモ・タスクを文脈に AI ポートを呼び出す。垂直導線
「メモ作成 → AI統合検索 → タスク化 → AI相談」の中核であり、ログ観察の主動線
([concept.md] §5)。
"""

from __future__ import annotations

from dataclasses import dataclass

from flownote_api.domain.ai import (
    ChatMessage,
    ConsultResult,
    ProgressInsight,
    SearchDocument,
    SearchHit,
)
from flownote_api.domain.errors import NotFoundError
from flownote_api.domain.ports import AIAssistant, NoteRepository, TaskRepository
from flownote_observability import get_logger, get_tracer

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
        with _tracer.start_as_current_span("usecase.ai.consult"):
            messages: list[ChatMessage] = [
                ChatMessage(role="system", content="あなたは作業管理を支援するアシスタントです。")
            ]
            if note_id is not None:
                note = await self.notes.get(note_id)
                if note is None or note.owner_id != owner_id:
                    raise NotFoundError("note", note_id)
                context = note.body[:_CONTEXT_BODY_MAX]
                messages.append(
                    ChatMessage(role="user", content=f"次のメモを参考にして:\n{context}")
                )
            messages.append(ChatMessage(role="user", content=question))
            result = await self.assistant.consult(messages)
            _logger.info("ai.consult.completed", **{"flownote.ai.use_case": "task_consult"})
            return result

    async def search(self, *, owner_id: str, query: str) -> list[SearchHit]:
        """メモ・タスク横断の統合検索を行う。

        Args:
            owner_id: 要求者の不透明ID。
            query: 検索クエリ。

        Returns:
            関連度順のヒット一覧。
        """
        with _tracer.start_as_current_span("usecase.ai.search"):
            notes = await self.notes.list_by_owner(owner_id)
            tasks = await self.tasks.list_by_owner(owner_id)
            documents: list[SearchDocument] = [
                SearchDocument(kind="note", id=n.id, title=n.title, text=n.body) for n in notes
            ]
            documents += [
                SearchDocument(kind="task", id=t.id, title=t.title, text=t.title) for t in tasks
            ]
            hits = await self.assistant.search(query, documents)
            _logger.info(
                "ai.search.completed",
                **{
                    "flownote.ai.use_case": "unified_search",
                    "flownote.search.hit_count": len(hits),
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
        with _tracer.start_as_current_span("usecase.ai.review_progress"):
            tasks = await self.tasks.list_by_owner(owner_id)
            insight = await self.assistant.review_progress(tasks)
            _logger.info(
                "ai.progress.reviewed",
                **{
                    "flownote.ai.use_case": "progress_review",
                    "flownote.task.stalled_count": len(insight.stalled_task_ids),
                },
            )
            return insight
