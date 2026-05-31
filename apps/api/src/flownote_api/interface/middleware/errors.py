"""例外 → HTTP 応答への変換とエラーログ。

ドメイン例外を適切な HTTP ステータスへ写像し、ログ規約 §3,§5 に従って重大度付きで記録する
(4xx=WARN、5xx/未捕捉=ERROR + ``exception.*``)。docs/observability/logging-spec.md を参照。
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from flownote_api.domain.errors import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from flownote_api.infrastructure.security.token import InvalidTokenError
from flownote_observability import get_logger

_logger = get_logger("flownote_api.errors")


def _problem(status: int, title: str, detail: str) -> JSONResponse:
    """RFC7807 風のエラー応答を生成する。

    Args:
        status: HTTP ステータス。
        title: エラー種別の短い名称。
        detail: 詳細メッセージ。

    Returns:
        JSON エラー応答。
    """
    return JSONResponse(status_code=status, content={"title": title, "detail": detail})


def register_exception_handlers(app: FastAPI) -> None:
    """アプリに例外ハンドラを登録する。

    Args:
        app: 対象の FastAPI アプリ。
    """

    async def _not_found(_request: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, NotFoundError)
        _logger.warning("error.not_found", **{"flownote.entity": exc.entity})
        return _problem(404, "not_found", str(exc))

    async def _permission_denied(_request: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, PermissionDeniedError)
        # 認可拒否の監査は auth 層で済んでいるため、ここでは応答変換のみ。
        return _problem(403, "permission_denied", str(exc))

    async def _validation(_request: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, ValidationError)
        _logger.warning("error.validation")
        return _problem(422, "validation_error", str(exc))

    async def _conflict(_request: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, ConflictError)
        _logger.warning("error.conflict")
        return _problem(409, "conflict", str(exc))

    async def _invalid_token(_request: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, InvalidTokenError)
        # セキュリティログは検証箇所で記録済み。ここでは 401 応答のみ。
        return _problem(401, "unauthorized", "認証が必要です")

    async def _unexpected(_request: Request, exc: Exception) -> JSONResponse:
        # 未捕捉例外は ERROR で記録(exception.* はパイプラインが付与)。
        _logger.error("error.unhandled", exc_info=exc)
        return _problem(500, "internal_error", "内部エラーが発生しました")

    app.add_exception_handler(NotFoundError, _not_found)
    app.add_exception_handler(PermissionDeniedError, _permission_denied)
    app.add_exception_handler(ValidationError, _validation)
    app.add_exception_handler(ConflictError, _conflict)
    app.add_exception_handler(InvalidTokenError, _invalid_token)
    app.add_exception_handler(Exception, _unexpected)
