"""インメモリの AI スタブ実装。

外部サーバなしで動く決定的な :class:`flownote_api.domain.ports.AIAssistant` 実装。
ローカル既定 AI バックエンドとして用い、外部依存なしでも GenAI 計装(span/メトリクス)を
観察できるようにする([genai-observability])。
"""

from __future__ import annotations

from datetime import UTC, datetime

from flownote_api.domain.ai import (
    AIUseCase,
    ChatMessage,
    ChatRole,
    ConsultResult,
    ProgressInsight,
    SearchDocument,
    SearchHit,
)
from flownote_api.domain.tasks import Task, TaskStatus
from flownote_observability import GenAIInstrumentation
from flownote_observability.conventions import (
    FinishReason,
    GenAiContentKind,
    GenAiOperation,
    GenAiSystem,
)

# トークン数の粗い見積り係数(おおよそ4文字=1トークン)。
_CHARS_PER_TOKEN = 4


def _estimate_tokens(text: str) -> int:
    """文字列から概算トークン数を見積もる。

    Args:
        text: 対象文字列。

    Returns:
        概算トークン数(最低1)。
    """
    return max(1, len(text) // _CHARS_PER_TOKEN)


class StubAIAssistant:
    """決定的に応答する AI スタブ。

    Attributes:
        model: 応答に用いるモデル名(観測用ラベル)。
    """

    def __init__(self, instrumentation: GenAIInstrumentation, *, model: str = "stub-qwen") -> None:
        """計装を注入して初期化する。

        Args:
            instrumentation: GenAI 計装ファサード。
            model: モデル名。
        """
        self._genai = instrumentation
        self.model = model

    async def consult(self, messages: list[ChatMessage]) -> ConsultResult:
        """最後のユーザー発話に定型応答する(計装あり)。

        Args:
            messages: 会話メッセージ列。

        Returns:
            定型の応答。
        """
        prompt = "\n".join(m.content for m in messages)
        last_user = next((m.content for m in reversed(messages) if m.role == ChatRole.USER), "")
        with self._genai.call(
            operation=GenAiOperation.CHAT,
            system=GenAiSystem.STUB,
            request_model=self.model,
            use_case=AIUseCase.TASK_CONSULT,
        ) as call:
            answer = f"ご相談の件「{last_user[:50]}」について、まず小さな次の一歩に分解しましょう。"
            call.capture(GenAiContentKind.PROMPT, prompt)
            call.capture(GenAiContentKind.COMPLETION, answer)
            call.record_usage(
                input_tokens=_estimate_tokens(prompt),
                output_tokens=_estimate_tokens(answer),
            )
            call.record_response(model=self.model, finish_reasons=[FinishReason.STOP])
            return ConsultResult(message=answer, model=self.model)

    async def search(self, query: str, documents: list[SearchDocument]) -> list[SearchHit]:
        """語の重なりに基づく素朴な統合検索(計装あり)。

        Args:
            query: 検索クエリ。
            documents: 検索対象。

        Returns:
            関連度降順の上位ヒット。
        """
        with self._genai.call(
            operation=GenAiOperation.EMBEDDINGS,
            system=GenAiSystem.STUB,
            request_model=self.model,
            use_case=AIUseCase.UNIFIED_SEARCH,
        ) as call:
            terms = {t for t in query.lower().split() if t}
            hits: list[SearchHit] = []
            for doc in documents:
                haystack = f"{doc.title}\n{doc.text}".lower()
                matched = sum(1 for t in terms if t in haystack)
                if matched == 0:
                    continue
                score = matched / max(1, len(terms))
                hits.append(
                    SearchHit(
                        kind=doc.kind,
                        id=doc.id,
                        title=doc.title,
                        score=round(score, 3),
                        snippet=doc.text[:120],
                    )
                )
            hits.sort(key=lambda h: h.score, reverse=True)
            total_chars = len(query) + sum(len(d.text) for d in documents)
            call.record_usage(input_tokens=_estimate_tokens(str(total_chars)), output_tokens=0)
            call.record_response(model=self.model)
            return hits[:10]

    async def review_progress(self, tasks: list[Task]) -> ProgressInsight:
        """滞留タスクを抽出し進捗を要約する(計装あり)。

        Args:
            tasks: レビュー対象のタスク一覧。

        Returns:
            進捗の洞察。
        """
        now = datetime.now(UTC)
        with self._genai.call(
            operation=GenAiOperation.CHAT,
            system=GenAiSystem.STUB,
            request_model=self.model,
            use_case=AIUseCase.PROGRESS_REVIEW,
        ) as call:
            stalled = tuple(t.id for t in tasks if t.is_stalled(now=now))
            done = sum(1 for t in tasks if t.status is TaskStatus.DONE)
            summary = f"全{len(tasks)}件中 完了{done}件、滞留{len(stalled)}件です。"
            suggestions = (
                "滞留中のタスクを15分で着手できる粒度に分割しましょう。",
                "今日完了できる1件を選びましょう。",
            )
            call.record_usage(
                input_tokens=_estimate_tokens(summary), output_tokens=_estimate_tokens(summary)
            )
            call.record_response(model=self.model, finish_reasons=[FinishReason.STOP])
            return ProgressInsight(
                summary=summary, stalled_task_ids=stalled, suggestions=suggestions
            )
