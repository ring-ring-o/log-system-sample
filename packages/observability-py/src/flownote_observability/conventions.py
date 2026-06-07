"""テレメトリで用いる「閉じた値域」の列挙(規約値の SSOT)。

属性の **キー** は :mod:`flownote_observability.semconv` に、ここでは属性の **値** のうち
取りうる集合が閉じているもの(列挙)を :class:`enum.StrEnum` で固定する。文字列リテラルを
各所に散らさず、綴り・大小・別名の揺れをコンパイラ/型検査で防ぐ。

意図の区別(同値でも別意図は別 enum):
    - GenAI メッセージの役割 ``system`` (ドメインの ``ChatRole``) と
      :class:`GenAiSystem` (プロバイダ系統) は別意図。ドメイン概念の ``ChatRole`` は
      外向き依存ゼロの ``domain`` 層に置き、ここ(観測ライブラリ)には持たない。
"""

from __future__ import annotations

from enum import StrEnum


class EventDomain(StrEnum):
    """``event.domain`` の値(ログの分類軸)。

    Attributes:
        APP: 業務イベント(既定)。
        ACCESS: HTTP アクセスログ。
        AUDIT: 監査イベント(認証認可・機微操作)。
        SECURITY: セキュリティイベント(攻撃/異常検知)。
        GENAI: GenAI 本文/結果イベント。
    """

    APP = "app"
    ACCESS = "access"
    AUDIT = "audit"
    SECURITY = "security"
    GENAI = "genai"


class GenAiOperation(StrEnum):
    """``gen_ai.operation.name`` の値(AI 操作種別)。

    Attributes:
        CHAT: チャット補完。
        EMBEDDINGS: 埋め込み生成。
    """

    CHAT = "chat"
    EMBEDDINGS = "embeddings"


class GenAiSystem(StrEnum):
    """``gen_ai.system`` の値(プロバイダ系統)。

    Attributes:
        STUB: 開発用スタブ。
        OPENAI: OpenAI 互換。
        VLLM: vLLM。
    """

    STUB = "stub"
    OPENAI = "openai"
    VLLM = "vllm"


class GenAiTokenType(StrEnum):
    """``gen_ai.token.type`` の値(トークン種別・メトリクス次元)。

    Attributes:
        INPUT: 入力トークン。
        OUTPUT: 出力トークン。
    """

    INPUT = "input"
    OUTPUT = "output"


class GenAiContentKind(StrEnum):
    """GenAI 本文キャプチャの種別キー(``GenAICall.capture`` の key)。

    Attributes:
        PROMPT: 入力プロンプト。
        COMPLETION: 生成された補完。
    """

    PROMPT = "prompt"
    COMPLETION = "completion"


class FinishReason(StrEnum):
    """``gen_ai.response.finish_reasons`` の値。

    Attributes:
        STOP: 正常終了(停止トークン到達)。
    """

    STOP = "stop"
