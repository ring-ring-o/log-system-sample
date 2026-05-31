"""GenAI(生成AI)呼び出しの計装。

[GenAI可観測性規約](../../../docs/observability/genai-observability.md) を実装する。
AI 呼び出しを ``gen_ai.*`` 属性付きの span で表し、トークン使用量・レイテンシ・概算コストを
メトリクス化する。プロンプト/補完本文は既定でログせず、有効時もマスク＋トランケートする。
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field

import structlog
from opentelemetry import metrics, trace
from opentelemetry.trace import Span, StatusCode

from flownote_observability.config import ObservabilityConfig
from flownote_observability.logging_setup import get_logger
from flownote_observability.redaction import redact

# モデル別の概算単価(1KトークンあたりのUSD)。ローカル/自前モデルは 0。
# 運用感覚を学ぶための擬似値であり、設定で上書きしてよい。
type PriceTable = Mapping[str, tuple[float, float]]
_DEFAULT_PRICING: PriceTable = {}


def _default_genai_logger() -> structlog.stdlib.BoundLogger:
    """GenAI 本文ログ用の既定ロガーを返す。

    Returns:
        モジュール用の構造化ロガー。
    """
    return get_logger("flownote_observability.genai")


def _truncate(text: str, max_chars: int) -> str:
    """本文を上限文字数でトランケートする。

    Args:
        text: 対象文字列。
        max_chars: 上限文字数。

    Returns:
        上限を超える場合は末尾に切り詰め注記を付した文字列。
    """
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars]}...[truncated {len(text) - max_chars} chars]"


@dataclass(slots=True)
class GenAIInstrumentation:
    """GenAI 計装のファサード。

    トレーサ・メータ・構成を保持し、AI 呼び出しごとに :meth:`call` で span とメトリクスを管理する。

    Attributes:
        config: 可観測性構成(本文キャプチャ可否・トランケート長を参照)。
        pricing: モデル別の概算単価表。
    """

    config: ObservabilityConfig
    pricing: PriceTable = field(default_factory=lambda: _DEFAULT_PRICING)
    logger: structlog.stdlib.BoundLogger = field(default_factory=_default_genai_logger)
    _tracer: trace.Tracer = field(init=False)
    _token_usage: metrics.Histogram = field(init=False)
    _duration: metrics.Histogram = field(init=False)
    _cost: metrics.Histogram = field(init=False)
    _count: metrics.Counter = field(init=False)

    def __post_init__(self) -> None:
        """トレーサとメトリクス計器を初期化する。"""
        self._tracer = trace.get_tracer("flownote_observability.genai")
        meter = metrics.get_meter("flownote_observability.genai")
        self._token_usage = meter.create_histogram(
            "gen_ai.client.token.usage", unit="{token}", description="AI トークン使用量"
        )
        self._duration = meter.create_histogram(
            "gen_ai.client.operation.duration", unit="s", description="AI 呼び出し時間"
        )
        self._cost = meter.create_histogram(
            "flownote.ai.cost.estimate", unit="USD", description="AI 概算コスト"
        )
        self._count = meter.create_counter(
            "flownote.ai.request.count", description="AI 呼び出し回数"
        )

    def _estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """トークン数から概算コスト(USD)を計算する。

        Args:
            model: 応答モデル名。
            input_tokens: 入力トークン数。
            output_tokens: 出力トークン数。

        Returns:
            単価表に基づく概算コスト。未登録モデルは 0.0。
        """
        rates = self.pricing.get(model)
        if rates is None:
            return 0.0
        input_rate, output_rate = rates
        return (input_tokens / 1000.0) * input_rate + (output_tokens / 1000.0) * output_rate

    @contextmanager
    def call(
        self,
        *,
        operation: str,
        system: str,
        request_model: str,
        use_case: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> Iterator[GenAICall]:
        """AI 呼び出しを計装するコンテキストマネージャ。

        ``with`` ブロック内で得た :class:`GenAICall` に使用量や応答を記録すると、退出時に
        span 属性とメトリクスへ反映する。例外送出時は span を ERROR とし ``error.type`` を付す。

        Args:
            operation: 操作種別(``chat``/``embeddings``)。
            system: プロバイダ系統(``openai``/``vllm``)。
            request_model: 要求モデル名。
            use_case: 業務ユースケース(``task_consult``/``unified_search`` 等)。
            temperature: サンプリング温度(任意)。
            max_tokens: 最大トークン(任意)。

        Yields:
            記録用の :class:`GenAICall`。
        """
        span_name = f"{operation} {request_model}"
        with self._tracer.start_as_current_span(span_name) as span:
            span.set_attribute("gen_ai.operation.name", operation)
            span.set_attribute("gen_ai.system", system)
            span.set_attribute("gen_ai.request.model", request_model)
            span.set_attribute("flownote.ai.use_case", use_case)
            if temperature is not None:
                span.set_attribute("gen_ai.request.temperature", temperature)
            if max_tokens is not None:
                span.set_attribute("gen_ai.request.max_tokens", max_tokens)

            record = GenAICall(span=span, request_model=request_model)
            error_type = "none"
            try:
                yield record
            except Exception as exc:
                # 失敗分類。呼び出し側が明示していなければ例外型名を用いる。
                error_type = record.error_type or type(exc).__qualname__
                span.set_status(StatusCode.ERROR)
                span.set_attribute("error.type", error_type)
                raise
            finally:
                self._finalize(span, record, use_case, error_type)

    def _finalize(self, span: Span, record: GenAICall, use_case: str, error_type: str) -> None:
        """span 属性とメトリクスへ記録内容を反映する。

        Args:
            span: 対象 span。
            record: 呼び出し中に蓄積された記録。
            use_case: 業務ユースケース。
            error_type: 失敗分類(``none`` なら成功)。
        """
        response_model = record.response_model or record.request_model
        span.set_attribute("gen_ai.response.model", response_model)
        span.set_attribute("gen_ai.usage.input_tokens", record.input_tokens)
        span.set_attribute("gen_ai.usage.output_tokens", record.output_tokens)
        if record.finish_reasons:
            span.set_attribute("gen_ai.response.finish_reasons", list(record.finish_reasons))

        common_attrs: dict[str, str] = {
            "gen_ai.request.model": record.request_model,
            "flownote.ai.use_case": use_case,
            "error.type": error_type,
        }
        self._count.add(1, common_attrs)
        self._token_usage.record(
            record.input_tokens, {**common_attrs, "gen_ai.token.type": "input"}
        )
        self._token_usage.record(
            record.output_tokens, {**common_attrs, "gen_ai.token.type": "output"}
        )
        cost = self._estimate_cost(response_model, record.input_tokens, record.output_tokens)
        self._cost.record(cost, common_attrs)

        # 本文キャプチャは規約で既定オフ。有効時のみマスク＋トランケートしてログする。
        if self.config.genai_capture_content and record.captured_content:
            safe = redact(
                {
                    k: _truncate(v, self.config.genai_content_max_chars)
                    for k, v in record.captured_content.items()
                }
            )
            self.logger.info(
                "gen_ai.content",
                **{"event.domain": "genai", "flownote.ai.use_case": use_case, "content": safe},
            )


@dataclass(slots=True)
class GenAICall:
    """1回の AI 呼び出しに対する記録用ハンドル。

    Attributes:
        span: 対応する OTel span。
        request_model: 要求モデル名。
        input_tokens: 入力トークン数。
        output_tokens: 出力トークン数。
        response_model: 応答モデル名(未設定なら要求モデルを使用)。
        finish_reasons: 終了理由の一覧。
        error_type: 失敗分類(任意指定)。
        captured_content: 本文キャプチャ有効時に記録する内容(role→text 等)。
    """

    span: Span
    request_model: str
    input_tokens: int = 0
    output_tokens: int = 0
    response_model: str | None = None
    finish_reasons: Sequence[str] = field(default_factory=tuple)
    error_type: str | None = None
    captured_content: dict[str, str] = field(default_factory=dict)

    def record_usage(self, *, input_tokens: int, output_tokens: int) -> None:
        """トークン使用量を記録する。

        Args:
            input_tokens: 入力トークン数。
            output_tokens: 出力トークン数。
        """
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens

    def record_response(
        self, *, model: str | None = None, finish_reasons: Sequence[str] | None = None
    ) -> None:
        """応答メタデータを記録する。

        Args:
            model: 応答モデル名。
            finish_reasons: 終了理由の一覧。
        """
        if model is not None:
            self.response_model = model
        if finish_reasons is not None:
            self.finish_reasons = tuple(finish_reasons)

    def capture(self, key: str, text: str) -> None:
        """本文(プロンプト/補完)をキャプチャ候補として記録する。

        実際にログされるかは構成 ``genai_capture_content`` に従う(既定オフ)。

        Args:
            key: 種別キー(``prompt``/``completion`` 等)。
            text: 本文。
        """
        self.captured_content[key] = text
