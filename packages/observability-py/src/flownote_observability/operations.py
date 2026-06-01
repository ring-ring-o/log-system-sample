"""業務操作を1行で計装する高レベルファサード(開発者DX)。

ログ規約の全体像を理解していなくても、**直感的に正しく**計装できることを目的とする。
``operation`` は1つの業務単位について以下を自動で行う:

1. その名前で OTel span を開始する(トレース相関は自動)。
2. 渡した属性を span とログの両方へ付与する。名前空間の無いキーは ``flownote.*`` に寄せる
   (規約 §4.2 のカーディナリティ/衝突回避を初心者でも踏み外しにくくする)。
3. 正常終了時に、その名前の業務イベントを **INFO で1度だけ**記録する(``event.domain="app"``)。
4. 例外送出時は span を ERROR にして **再送出するだけ**(ログは出さない)。
   エラーログは interface 層の境界に集約する規約([logging-spec] §5.3)を、使う側が
   意識しなくても守れる。

使用例::

    from flownote_observability import operation

    async def create_note(...) -> Note:
        with operation("note.create", note_id=note.id) as op:
            await repo.add(note)
            op.set(version_id=version.id)  # 後から判明した属性を足す
        return note

これだけで「span 開始 → 属性付与 → 業務ログ → 失敗時 span=ERROR」が規約準拠で揃う。
個別に ``get_tracer``/``get_logger`` を組み合わせる必要はない。
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field

import structlog
from opentelemetry import trace
from opentelemetry.trace import Span, StatusCode

from flownote_observability.logging_setup import get_logger

# span 属性として設定できる OTel の値型。これ以外(None/dict 等)は span には載せずログのみへ。
type SpanAttributeValue = str | bool | int | float | Sequence[str]

# 既知の(=既に名前空間が付いている)属性ルート。これらで始まるキーはそのまま尊重する。
# それ以外(業務固有のキー)は衝突回避のため ``flownote.*`` に寄せる(規約 §4.2)。
_KNOWN_NAMESPACES: frozenset[str] = frozenset(
    {
        "flownote",
        "http",
        "db",
        "gen_ai",
        "exception",
        "code",
        "user",
        "service",
        "deployment",
        "event",
        "network",
        "client",
        "server",
        "url",
        "error",
        "audit",
        "authz",
        "security",
        "session",
        "rpc",
        "messaging",
        "mcp",
    }
)


def _namespaced(key: str) -> str:
    """業務固有キーを ``flownote.*`` に寄せる(既知の名前空間はそのまま)。

    ``note_id`` → ``flownote.note_id``、``note.id`` → ``flownote.note.id``。
    一方 ``http.route`` や ``flownote.note.id`` のように既知ルートのキーは尊重する。

    Args:
        key: 属性キー。

    Returns:
        名前空間付きの属性キー。
    """
    root = key.split(".", 1)[0]
    if root in _KNOWN_NAMESPACES:
        return key
    return f"flownote.{key}"


def _span_safe(value: object) -> SpanAttributeValue | None:
    """値を span 属性に設定可能な型へ落とし込む(不可なら ``None``)。

    Args:
        value: 元の属性値。

    Returns:
        span に設定できる値、設定できなければ ``None``(ログ側にのみ残す)。
    """
    if isinstance(value, str | bool | int | float):
        return value
    # 文字列シーケンスのみ許可(混在は避ける)。
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        items = list(value)
        if all(isinstance(item, str) for item in items):
            return [str(item) for item in items]
    return None


@dataclass(slots=True)
class Operation:
    """計装中の業務操作ハンドル。

    Attributes:
        span: 対応する OTel span。
        attributes: ログ/span に付与済みの属性(名前空間適用後)。
    """

    span: Span
    attributes: dict[str, object] = field(default_factory=dict)

    def set(self, **attributes: object) -> None:
        """属性を追加する(span とログの両方へ反映)。

        キーは ``_namespaced`` で正規化する。span に載らない型はログ側にのみ残す。

        Args:
            **attributes: 追加する属性(``note_id=...`` のように渡す)。
        """
        for raw_key, value in attributes.items():
            key = _namespaced(raw_key)
            self.attributes[key] = value
            safe = _span_safe(value)
            if safe is not None:
                self.span.set_attribute(key, safe)


@contextmanager
def operation(
    name: str,
    *,
    domain: str = "app",
    emit: bool = True,
    logger: structlog.stdlib.BoundLogger | None = None,
    tracer: trace.Tracer | None = None,
    **attributes: object,
) -> Iterator[Operation]:
    """業務操作を span + 業務ログとして計装するコンテキストマネージャ。

    Args:
        name: 低カーディナリティの操作名(span 名 / ログ body)。例 ``note.create``。
        domain: ``event.domain``(既定 ``app``)。
        emit: 正常終了時に業務イベントログを出すか(既定 True)。span のみ欲しい時は False。
        logger: 使用するロガー(未指定なら共有ロガー)。
        tracer: 使用するトレーサ(未指定ならグローバルプロバイダ。テストで明示注入できる)。
        **attributes: 初期属性(名前空間の無いキーは ``flownote.*`` に寄せる)。

    Yields:
        属性を追記できる :class:`Operation`。

    Raises:
        Exception: ブロック内の例外は span を ERROR にして**そのまま再送出**する
            (ログは境界に集約する規約のため、ここでは出さない)。
    """
    log = logger or get_logger("flownote_observability.operations")
    active_tracer = tracer or trace.get_tracer("flownote_observability.operations")
    with active_tracer.start_as_current_span(name) as span:
        op = Operation(span=span)
        op.set(**attributes)
        try:
            yield op
        except Exception:
            # 失敗の事実は span に残し、ログは出さず再送出(境界で1度だけログる)。
            span.set_status(StatusCode.ERROR)
            raise
        else:
            if emit:
                bound = log.bind(**{"event.domain": domain, **op.attributes})
                bound.info(name)


def log_event(name: str, *, domain: str = "app", **attributes: object) -> None:
    """span を張るほどでもない業務イベントを INFO で1件記録する。

    名前空間の正規化と ``event.domain`` 付与を肩代わりする薄いヘルパ。

    Args:
        name: 低カーディナリティのイベント名(ログ body)。
        domain: ``event.domain``(既定 ``app``)。
        **attributes: 付与する属性(名前空間の無いキーは ``flownote.*`` に寄せる)。
    """
    normalized = {_namespaced(key): value for key, value in attributes.items()}
    logger = get_logger("flownote_observability.operations")
    logger.bind(**{"event.domain": domain, **normalized}).info(name)
