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

from flownote_observability import (
    bind_request_context,
    clear_request_context,
    get_logger,
    severity_for_http_status,
)

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
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        # クライアント指定があれば尊重し、無ければ採番する。
        request_id = request.headers.get("x-request-id") or str(uuid4())
        request.state.request_id = request_id
        bind_request_context(request_id=request_id)

        status_holder = {"code": 500}

        async def _send(message: object) -> None:
            # レスポンス開始メッセージからステータスコードを捕捉し、ヘッダに request_id を付す。
            if isinstance(message, dict) and message.get("type") == "http.response.start":
                status_holder["code"] = int(message.get("status", 500))
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode("ascii")))
                message = {**message, "headers": headers}
            await send(message)  # type: ignore[arg-type]

        start = time.perf_counter()
        try:
            await self._app(scope, receive, _send)
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 3)
            status = status_holder["code"]
            severity = severity_for_http_status(status)
            attributes = {
                "event.domain": "access",
                "http.request.method": request.method,
                "http.route": request.url.path,
                "http.response.status_code": status,
                "http.server.request.duration_ms": duration_ms,
            }
            bound = _logger.bind(**attributes)
            # 重大度に応じてレベルを選択(4xx=WARN, 5xx=ERROR, それ以外=INFO)。
            if severity.name == "ERROR":
                bound.error("http.request.completed")
            elif severity.name == "WARN":
                bound.warning("http.request.completed")
            else:
                bound.info("http.request.completed")
            clear_request_context()
