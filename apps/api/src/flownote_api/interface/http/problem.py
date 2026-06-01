"""RFC 9457 Problem Details(``application/problem+json``)。

API がクライアントへ返すエラー本文の形式を1つに固定する。安定識別子 ``code`` と相関用
``trace_id`` を含めることで、(1) クライアントは文字列メッセージではなくコードで分岐でき、
(2) エンドユーザーが ``trace_id`` をサポートへ伝えれば SigNoz 等でトレースを引き戻せる。

公開してよい文言のみを載せる。機密を含みうる詳細はドメイン例外の ``internal_context`` に留め、
ログ側にのみ出す([domain/errors.py])。
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

# ``type`` に用いるドキュメント URI の基底。コードを連結して安定 URI を作る。
PROBLEM_TYPE_BASE = "https://errors.flownote.example/"


class ProblemDetail(BaseModel):
    """RFC 9457 準拠のエラー応答本文。

    Attributes:
        type: エラー種別を識別する URI(``code`` から導出)。
        title: 人間可読の短い表題(公開可)。
        status: HTTP ステータス。
        code: 安定エラー識別子(``RES.NOT_FOUND`` 等)。RFC 9457 の拡張メンバ。
        detail: この発生事象の説明(公開可)。``None`` 可。
        instance: 発生事象を指す URI 参照(通常はリクエストパス)。
        trace_id: 相関トレースID。サポートでの引き戻しに用いる。拡張メンバ。
    """

    # 拡張メンバ(code/trace_id)を許容しつつ未知キーは禁止する。
    model_config = ConfigDict(extra="forbid")

    type: str
    title: str
    status: int
    code: str
    detail: str | None = None
    instance: str | None = None
    trace_id: str | None = None
    # 入力検証エラー等で、フィールド単位の詳細を載せるための任意拡張。
    errors: list[dict[str, object]] | None = Field(default=None)


def build_problem(
    *,
    code: str,
    status: int,
    title: str,
    detail: str | None,
    instance: str | None,
    trace_id: str | None,
    errors: list[dict[str, object]] | None = None,
) -> ProblemDetail:
    """Problem Details を組み立てる。

    Args:
        code: 安定エラー識別子。
        status: HTTP ステータス。
        title: 公開表題。
        detail: 公開詳細(任意)。
        instance: 発生事象 URI(通常はリクエストパス)。
        trace_id: 相関トレースID(任意)。
        errors: フィールド単位の詳細(入力検証エラー等、任意)。

    Returns:
        構築済み :class:`ProblemDetail`。
    """
    return ProblemDetail(
        type=f"{PROBLEM_TYPE_BASE}{code}",
        title=title,
        status=status,
        code=code,
        detail=detail,
        instance=instance,
        trace_id=trace_id,
        errors=errors,
    )
