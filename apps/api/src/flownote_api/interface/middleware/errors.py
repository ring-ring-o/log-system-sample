"""例外 → RFC 9457 Problem Details 応答への変換と境界エラーログ。

[ログ規約](../../../../docs/observability/logging-spec.md) の「**エラーは境界で1度だけログる**」
原則を実装する。ドメイン/アプリケーション層は例外を ``raise`` するだけで、ログは出さない
(log-and-rethrow 禁止)。本ハンドラ(interface 層の最外郭)が:

1. 例外を :class:`ProblemDetail` へ写像し ``application/problem+json`` で返す。
2. ``flownote.error.code`` 付きで重大度ログを **1件だけ** 記録する(4xx/5xx の段階に従う)。
3. 例外の ``internal_context``(機密含む)はログ側にのみ出し、応答へは載せない。

認証/認可の失敗(401/403)は auth 層で監査/セキュリティログ済みのため、ここでは二重に
ログしない(``event.domain`` が異なる別ストリーム)。
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from opentelemetry import trace

from flownote_api.domain.errors import DomainError, PermissionDeniedError
from flownote_api.infrastructure.security.token import InvalidTokenError
from flownote_api.interface.http.error_catalog import AUTH_UNAUTHORIZED, VAL_REQUEST
from flownote_api.interface.http.problem import ProblemDetail, build_problem
from flownote_api.shared.http_constants import MediaType
from flownote_api.shared.telemetry import AppEvent
from flownote_observability import get_logger, severity_for_http_status
from flownote_observability.conventions import EventDomain
from flownote_observability.semconv import EVENT_DOMAIN_KEY, FLOWNOTE_ERROR_CODE_KEY
from flownote_observability.severity import Severity

_logger = get_logger("flownote_api.errors")


def _current_trace_id() -> str | None:
    """実行中 span の trace_id(hex32)を返す。span 外なら ``None``。

    Returns:
        相関トレースID、無ければ ``None``。
    """
    context = trace.get_current_span().get_span_context()
    return format(context.trace_id, "032x") if context.is_valid else None


def _response(problem: ProblemDetail) -> JSONResponse:
    """Problem Details を ``application/problem+json`` 応答にする。

    Args:
        problem: 応答本文。

    Returns:
        JSON エラー応答(未設定フィールドは省く)。
    """
    return JSONResponse(
        status_code=problem.status,
        content=problem.model_dump(exclude_none=True),
        media_type=MediaType.PROBLEM_JSON,
    )


def _log_boundary(
    body: str,
    *,
    code: str,
    status: int,
    internal_context: dict[str, object],
    exc: BaseException | None = None,
) -> None:
    """境界で重大度ログを1件だけ記録する。

    重大度は HTTP ステータスの段階に従う(5xx=ERROR、4xx は §3 の2段階)。``exception.*`` は
    ``exc_info`` からパイプラインが付与する。``internal_context`` はマスキング後に出力される。

    Args:
        body: 低カーディナリティのイベント名。
        code: 安定エラーコード(``flownote.error.code`` として記録)。
        status: HTTP ステータス(重大度決定に使う)。
        internal_context: ログにのみ出す詳細。
        exc: 5xx 等でスタックトレースを残す対象例外(任意)。
    """
    severity = severity_for_http_status(status)
    bound = _logger.bind(
        **{EVENT_DOMAIN_KEY: EventDomain.APP, FLOWNOTE_ERROR_CODE_KEY: code, **internal_context}
    )
    if severity is Severity.ERROR:
        bound.error(body, exc_info=exc)
    elif severity is Severity.WARN:
        bound.warning(body)
    else:
        bound.info(body)


def register_exception_handlers(app: FastAPI) -> None:
    """アプリに例外ハンドラを登録する。

    Args:
        app: 対象の FastAPI アプリ。
    """

    async def _domain_error(request: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, DomainError)
        # 認可拒否は auth 層で監査済み。二重ログを避ける。
        if not isinstance(exc, PermissionDeniedError):
            _log_boundary(
                AppEvent.ERROR_HANDLED,
                code=exc.code,
                status=exc.http_status,
                internal_context=exc.internal_context,
                exc=exc if exc.http_status >= 500 else None,
            )
        problem = build_problem(
            code=exc.code,
            status=exc.http_status,
            title=exc.public_title,
            detail=exc.public_detail,
            instance=request.url.path,
            trace_id=_current_trace_id(),
        )
        return _response(problem)

    async def _invalid_token(request: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, InvalidTokenError)
        # セキュリティログは検証箇所で記録済み。ここでは 401 応答のみ(コードは境界 SSOT を参照)。
        problem = build_problem(
            code=AUTH_UNAUTHORIZED.code,
            status=AUTH_UNAUTHORIZED.http_status,
            title=AUTH_UNAUTHORIZED.public_title,
            detail=AUTH_UNAUTHORIZED.public_detail,
            instance=request.url.path,
            trace_id=_current_trace_id(),
        )
        return _response(problem)

    async def _request_validation(request: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, RequestValidationError)
        # 入力検証の失敗は仕様内のクライアント挙動(期待される失敗)。INFO で1件記録。
        _log_boundary(
            AppEvent.ERROR_HANDLED,
            code=VAL_REQUEST.code,
            status=VAL_REQUEST.http_status,
            internal_context={},
        )
        # フィールド単位の指摘は利用者の修正に必要なため公開する(機密は含めない前提)。
        errors = [
            {"loc": list(err.get("loc", ())), "msg": err.get("msg"), "type": err.get("type")}
            for err in exc.errors()
        ]
        problem = build_problem(
            code=VAL_REQUEST.code,
            status=VAL_REQUEST.http_status,
            title=VAL_REQUEST.public_title,
            detail=VAL_REQUEST.public_detail,
            instance=request.url.path,
            trace_id=_current_trace_id(),
            errors=errors,
        )
        return _response(problem)

    async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
        # 未捕捉例外は基底 DomainError(GEN.INTERNAL)へフォールバックする。コード/表題は
        # ドメインの基底定義を参照し、リテラルの二重管理を避ける(exception.* はパイプライン付与)。
        _log_boundary(
            AppEvent.ERROR_UNHANDLED,
            code=DomainError.code,
            status=DomainError.http_status,
            internal_context={},
            exc=exc,
        )
        problem = build_problem(
            code=DomainError.code,
            status=DomainError.http_status,
            title=DomainError.public_title,
            detail="しばらくしてから再度お試しください",
            instance=request.url.path,
            trace_id=_current_trace_id(),
        )
        return _response(problem)

    app.add_exception_handler(DomainError, _domain_error)
    app.add_exception_handler(InvalidTokenError, _invalid_token)
    app.add_exception_handler(RequestValidationError, _request_validation)
    app.add_exception_handler(Exception, _unexpected)
