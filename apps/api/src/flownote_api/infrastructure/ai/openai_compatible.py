"""OpenAI 互換 API クライアント。

vLLM 等が提供する OpenAI 互換エンドポイント(``/v1/chat/completions`` 等)を呼ぶ
:class:`flownote_api.domain.ports.AIAssistant` 実装。開発時は ``apps/ai-mock`` を指す。
httpx は自動計装され、本クライアントは GenAI 計装([genai-observability])を併せて行う。
"""

from __future__ import annotations

import math

import httpx
from pydantic import BaseModel, ConfigDict

from flownote_api.domain.ai import (
    ChatMessage,
    ConsultResult,
    ProgressInsight,
    SearchDocument,
    SearchHit,
)
from flownote_api.domain.tasks import Task, TaskStatus
from flownote_observability import GenAIInstrumentation

# AI 呼び出しのタイムアウト(秒)。超過時は error.type=timeout とする。
_TIMEOUT_S = 30.0


class _Usage(BaseModel):
    """OpenAI 応答の usage 部分。"""

    model_config = ConfigDict(extra="ignore")
    prompt_tokens: int = 0
    completion_tokens: int = 0


class _Message(BaseModel):
    """chat 応答のメッセージ。"""

    model_config = ConfigDict(extra="ignore")
    content: str = ""


class _Choice(BaseModel):
    """chat 応答の choice。"""

    model_config = ConfigDict(extra="ignore")
    message: _Message = _Message()
    finish_reason: str | None = None


class _ChatResponse(BaseModel):
    """chat completions 応答。"""

    model_config = ConfigDict(extra="ignore")
    model: str = ""
    choices: list[_Choice] = []
    usage: _Usage = _Usage()


class _EmbeddingItem(BaseModel):
    """embeddings 応答の1項目。"""

    model_config = ConfigDict(extra="ignore")
    embedding: list[float] = []


class _EmbeddingResponse(BaseModel):
    """embeddings 応答。"""

    model_config = ConfigDict(extra="ignore")
    model: str = ""
    data: list[_EmbeddingItem] = []
    usage: _Usage = _Usage()


def _cosine(a: list[float], b: list[float]) -> float:
    """2ベクトルのコサイン類似度を返す。

    Args:
        a: ベクトル1。
        b: ベクトル2。

    Returns:
        コサイン類似度(0除算時は 0.0)。
    """
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class OpenAICompatibleAssistant:
    """OpenAI 互換サーバを用いる AI 実装。"""

    def __init__(
        self,
        instrumentation: GenAIInstrumentation,
        *,
        base_url: str,
        chat_model: str,
        embedding_model: str,
        api_key: str | None = None,
        system: str = "vllm",
    ) -> None:
        """接続情報と計装を注入して初期化する。

        Args:
            instrumentation: GenAI 計装ファサード。
            base_url: OpenAI 互換 API のベースURL。
            chat_model: chat に用いるモデル名。
            embedding_model: embeddings に用いるモデル名。
            api_key: API キー(任意。ローカルは不要)。
            system: ``gen_ai.system`` のラベル。
        """
        self._genai = instrumentation
        self._base_url = base_url.rstrip("/")
        self._chat_model = chat_model
        self._embedding_model = embedding_model
        self._headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._system = system

    async def _post(self, path: str, payload: dict[str, object]) -> httpx.Response:
        """OpenAI 互換 API に POST する。

        Args:
            path: パス(``/v1/chat/completions`` 等)。
            payload: リクエストボディ。

        Returns:
            HTTP 応答。

        Raises:
            httpx.HTTPStatusError: 4xx/5xx 応答時。
            httpx.TimeoutException: タイムアウト時。
        """
        async with httpx.AsyncClient(timeout=_TIMEOUT_S, headers=self._headers) as client:
            response = await client.post(f"{self._base_url}{path}", json=payload)
            response.raise_for_status()
            return response

    @staticmethod
    def _classify_error(exc: Exception) -> str:
        """例外を ``error.type`` 用の分類へ変換する。

        Args:
            exc: 捕捉した例外。

        Returns:
            ``timeout``/``rate_limit``/``upstream_5xx``/``upstream_4xx``/``error`` のいずれか。
        """
        if isinstance(exc, httpx.TimeoutException):
            return "timeout"
        if isinstance(exc, httpx.HTTPStatusError):
            status = exc.response.status_code
            if status == 429:
                return "rate_limit"
            return "upstream_5xx" if status >= 500 else "upstream_4xx"
        return "error"

    async def consult(self, messages: list[ChatMessage]) -> ConsultResult:
        """chat completions で相談へ応答する。

        Args:
            messages: 会話メッセージ列。

        Returns:
            AI の応答。
        """
        with self._genai.call(
            operation="chat",
            system=self._system,
            request_model=self._chat_model,
            use_case="task_consult",
        ) as call:
            try:
                response = await self._post(
                    "/v1/chat/completions",
                    {
                        "model": self._chat_model,
                        "messages": [{"role": m.role, "content": m.content} for m in messages],
                    },
                )
            except Exception as exc:
                call.error_type = self._classify_error(exc)
                raise
            parsed = _ChatResponse.model_validate(response.json())
            content = parsed.choices[0].message.content if parsed.choices else ""
            finish = parsed.choices[0].finish_reason if parsed.choices else None
            call.record_usage(
                input_tokens=parsed.usage.prompt_tokens,
                output_tokens=parsed.usage.completion_tokens,
            )
            call.record_response(
                model=parsed.model or self._chat_model,
                finish_reasons=[finish] if finish else None,
            )
            return ConsultResult(message=content, model=parsed.model or self._chat_model)

    async def search(self, query: str, documents: list[SearchDocument]) -> list[SearchHit]:
        """embeddings によるベクトル類似度で統合検索する。

        Args:
            query: 検索クエリ。
            documents: 検索対象。

        Returns:
            類似度降順の上位ヒット。
        """
        if not documents:
            return []
        with self._genai.call(
            operation="embeddings",
            system=self._system,
            request_model=self._embedding_model,
            use_case="unified_search",
        ) as call:
            inputs = [query] + [f"{d.title}\n{d.text}" for d in documents]
            try:
                response = await self._post(
                    "/v1/embeddings", {"model": self._embedding_model, "input": inputs}
                )
            except Exception as exc:
                call.error_type = self._classify_error(exc)
                raise
            parsed = _EmbeddingResponse.model_validate(response.json())
            call.record_usage(input_tokens=parsed.usage.prompt_tokens, output_tokens=0)
            call.record_response(model=parsed.model or self._embedding_model)
            if len(parsed.data) != len(inputs):
                return []
            query_vec = parsed.data[0].embedding
            hits: list[SearchHit] = []
            for doc, item in zip(documents, parsed.data[1:], strict=True):
                score = _cosine(query_vec, item.embedding)
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
            return hits[:10]

    async def review_progress(self, tasks: list[Task]) -> ProgressInsight:
        """chat で進捗を要約し、滞留はローカル判定する。

        Args:
            tasks: レビュー対象のタスク一覧。

        Returns:
            進捗の洞察。
        """
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        stalled = tuple(t.id for t in tasks if t.is_stalled(now=now))
        done = sum(1 for t in tasks if t.status is TaskStatus.DONE)
        prompt = (
            f"タスク総数{len(tasks)}、完了{done}、滞留{len(stalled)}。"
            "進捗の要約と次の一手を簡潔に述べてください。"
        )
        with self._genai.call(
            operation="chat",
            system=self._system,
            request_model=self._chat_model,
            use_case="progress_review",
        ) as call:
            try:
                response = await self._post(
                    "/v1/chat/completions",
                    {"model": self._chat_model, "messages": [{"role": "user", "content": prompt}]},
                )
            except Exception as exc:
                call.error_type = self._classify_error(exc)
                raise
            parsed = _ChatResponse.model_validate(response.json())
            summary = parsed.choices[0].message.content if parsed.choices else ""
            call.record_usage(
                input_tokens=parsed.usage.prompt_tokens,
                output_tokens=parsed.usage.completion_tokens,
            )
            call.record_response(model=parsed.model or self._chat_model, finish_reasons=["stop"])
            return ProgressInsight(
                summary=summary or "進捗を確認しました。",
                stalled_task_ids=stalled,
                suggestions=("滞留タスクを分割しましょう。",),
            )
