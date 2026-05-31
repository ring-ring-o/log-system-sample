"""AI 関連のドメイン値オブジェクト。

AI の入出力を表す不変の値オブジェクト。実装(OpenAI互換クライアント/スタブ)はインフラ層、
これを利用するユースケースはアプリ層に置く。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AIUseCase(StrEnum):
    """AI のユースケース分類([genai-observability] の ``flownote.ai.use_case``)。

    Attributes:
        TASK_CONSULT: タスク/メモを文脈にした相談。
        UNIFIED_SEARCH: メモ・タスク横断の統合検索。
        PROGRESS_REVIEW: 進捗レビューと次の一手の提案。
    """

    TASK_CONSULT = "task_consult"
    UNIFIED_SEARCH = "unified_search"
    PROGRESS_REVIEW = "progress_review"


@dataclass(frozen=True, slots=True)
class ChatMessage:
    """会話メッセージ。

    Attributes:
        role: 役割(``system``/``user``/``assistant``)。
        content: 本文。
    """

    role: str
    content: str


@dataclass(frozen=True, slots=True)
class ConsultResult:
    """AI 相談の結果。

    Attributes:
        message: AI からの応答テキスト。
        model: 応答に用いたモデル名。
    """

    message: str
    model: str


@dataclass(frozen=True, slots=True)
class SearchDocument:
    """検索対象のドキュメント(メモ/タスクを正規化したもの)。

    Attributes:
        kind: 種別(``note``/``task``)。
        id: 識別子。
        title: タイトル。
        text: 本文(検索対象テキスト)。
    """

    kind: str
    id: str
    title: str
    text: str


@dataclass(frozen=True, slots=True)
class SearchHit:
    """統合検索のヒット結果。

    Attributes:
        kind: 種別(``note``/``task``)。
        id: 識別子。
        title: タイトル。
        score: 関連度スコア(0.0-1.0)。
        snippet: 該当箇所の抜粋。
    """

    kind: str
    id: str
    title: str
    score: float
    snippet: str


@dataclass(frozen=True, slots=True)
class ProgressInsight:
    """進捗レビューの洞察。

    Attributes:
        summary: 全体の要約。
        stalled_task_ids: 滞留しているタスクの識別子一覧。
        suggestions: 次の一手の提案。
    """

    summary: str
    stalled_task_ids: tuple[str, ...]
    suggestions: tuple[str, ...]
