"""可観測性ミドルウェア。

リクエストごとに ``request_id`` を採番・束縛し、終了時にアクセスログ(RED の Duration を含む)を
出力する。HTTP server span とメトリクスは OTel FastAPI 自動計装が担うため、本ミドルウェアは
相関キーの束縛とアクセスログに専念する([logging-spec] §6, [observability-architecture] §8)。
"""

from __future__ import annotations

import time
from uuid import uuid4

from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from flownote_api.shared.http_constants import (
    ASGI_HEADERS_KEY,
    ASGI_STATUS_KEY,
    ASGI_TYPE_KEY,
    AsgiMessageType,
    AsgiScopeType,
    HeaderName,
)
from flownote_api.shared.telemetry import AppEvent
from flownote_observability import (
    bind_request_context,
    clear_request_context,
    get_logger,
    severity_for_http_status,
)
from flownote_observability.conventions import EventDomain
from flownote_observability.semconv import (
    EVENT_DOMAIN_KEY,
    HTTP_REQUEST_METHOD_KEY,
    HTTP_RESPONSE_STATUS_CODE_KEY,
    HTTP_ROUTE_KEY,
    HTTP_SERVER_REQUEST_DURATION_KEY,
)
from flownote_observability.severity import Severity

_logger = get_logger("flownote_api.access")


class ObservabilityMiddleware:
    """request_id 束縛とアクセスログを行う ASGI ミドルウェア。"""

    def __init__(self, app: ASGIApp) -> None:
        """ミドルウェアを初期化する。

        Args:
            app: ラップする ASGI アプリ。
        """
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """HTTP リクエストを処理し、アクセスログを記録する。

        Args:
            scope: ASGI スコープ。
            receive: ASGI 受信関数。
            send: ASGI 送信関数。
        """
        if scope[ASGI_TYPE_KEY] != AsgiScopeType.HTTP:
            await self._app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        # クライアント指定があれば尊重し、無ければ採番する。
        request_id = request.headers.get(HeaderName.REQUEST_ID) or str(uuid4())
        request.state.request_id = request_id
        bind_request_context(request_id=request_id)

        status_holder = {"code": 500}

        async def _send(message: object) -> None:
            # レスポンス開始メッセージからステータスコードを捕捉し、ヘッダに request_id を付す。
            if (
                isinstance(message, dict)
                and message.get(ASGI_TYPE_KEY) == AsgiMessageType.RESPONSE_START
            ):
                status_holder["code"] = int(message.get(ASGI_STATUS_KEY, 500))
                headers = list(message.get(ASGI_HEADERS_KEY, []))
                headers.append((HeaderName.REQUEST_ID.encode("ascii"), request_id.encode("ascii")))
                message = {**message, ASGI_HEADERS_KEY: headers}
            await send(message)  # type: ignore[arg-type]

        start = time.perf_counter()
        try:
            await self._app(scope, receive, _send)
        finally:
            # OTel Semantic Conventions に合わせ単位は秒(UCUM `s`)。`*_ms` は採用しない。
            duration_s = round(time.perf_counter() - start, 6)
            status = status_holder["code"]
            severity = severity_for_http_status(status)
            attributes = {
                EVENT_DOMAIN_KEY: EventDomain.ACCESS,
                HTTP_REQUEST_METHOD_KEY: request.method,
                # 実IDを含む生パスではなくルートテンプレート(例 /api/notes/{note_id})を用いる
                # (logging-spec §4.2/§4.3 のカーディナリティ規約)。
                HTTP_ROUTE_KEY: _route_template(scope, request.url.path),
                HTTP_RESPONSE_STATUS_CODE_KEY: status,
                HTTP_SERVER_REQUEST_DURATION_KEY: duration_s,
            }
            bound = _logger.bind(**attributes)
            # 重大度に応じてレベルを選択(5xx=ERROR、4xx は §3 の2段階で WARN/INFO、
            # 2xx/3xx=INFO)。判定は severity_for_http_status を唯一の源泉とする。
            if severity is Severity.ERROR:
                bound.error(AppEvent.HTTP_REQUEST_COMPLETED)
            elif severity is Severity.WARN:
                bound.warning(AppEvent.HTTP_REQUEST_COMPLETED)
            else:
                bound.info(AppEvent.HTTP_REQUEST_COMPLETED)
            clear_request_context()


def _route_template(scope: Scope, fallback: str) -> str:
    """マッチしたルートのテンプレートパスを返す。

    Starlette はルーティング後に ``scope["route"]`` を設定する。APIRoute の ``path`` は
    ``/api/notes/{note_id}`` のようなテンプレートで、実IDを含まない。

    Args:
        scope: ASGI スコープ(ルーティング後)。
        fallback: ルート未解決時(404 等)に用いる値。

    Returns:
        ルートテンプレート、解決できなければ ``fallback``。
    """
    route = scope.get("route")
    template = getattr(route, "path", None)
    return template if isinstance(template, str) else fallback
