"""HTTP / プロトコル関連の定数(アプリ境界の語彙)。

HTTP メソッド・ヘッダ名・メディアタイプ・ASGI のメッセージ語彙・認可スキームなど、外部標準や
プロトコルに由来する文字列を意図ごとに名前付き定数へ集約する。各所の文字列リテラルを排し、
綴りの揺れ(``content-type`` の大小やタイポ)を型/定数で防ぐ。
"""

from __future__ import annotations

from enum import StrEnum


class HttpMethod(StrEnum):
    """HTTP メソッド。

    Attributes:
        GET: 取得。
        POST: 作成。
        PUT: 置換更新。
        PATCH: 部分更新。
        DELETE: 削除。
    """

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


class HeaderName(StrEnum):
    """HTTP ヘッダ名(小文字正規化)。

    Attributes:
        AUTHORIZATION: 認可ヘッダ。
        CONTENT_TYPE: コンテンツ種別。
        REQUEST_ID: リクエスト相関ID。
        TRACEPARENT: W3C Trace Context。
    """

    AUTHORIZATION = "authorization"
    CONTENT_TYPE = "content-type"
    REQUEST_ID = "x-request-id"
    TRACEPARENT = "traceparent"


class MediaType(StrEnum):
    """メディアタイプ(MIME)。

    Attributes:
        JSON: 通常の JSON。
        PROBLEM_JSON: RFC 9457 Problem Details。
    """

    JSON = "application/json"
    PROBLEM_JSON = "application/problem+json"


class AuthScheme(StrEnum):
    """``Authorization`` ヘッダの認可スキーム(小文字比較用)。

    Attributes:
        BEARER: Bearer トークン。
    """

    BEARER = "bearer"


# 送信時の ``Authorization`` 値のプレフィックス(``Bearer <token>``)。
# 受信時の小文字比較に使う :class:`AuthScheme.BEARER` とは用途が異なる(別定数)。
BEARER_PREFIX = "Bearer "


class TokenFailureReason(StrEnum):
    """トークン検証失敗の分類(``security.reason`` の値)。

    Attributes:
        MISSING: ``Authorization: Bearer`` が無い/形式不正。
        EMPTY: トークンが空。
        EXPIRED: 期限切れ。
        INVALID_SIGNATURE: 署名不正。
        INVALID_AUDIENCE: aud 不一致。
        INVALID_ISSUER: iss 不一致。
        MISSING_SUBJECT: ``sub`` 欠落。
        INVALID: その他の検証失敗。
    """

    MISSING = "missing_bearer"
    EMPTY = "empty"
    EXPIRED = "expired"
    INVALID_SIGNATURE = "invalid_signature"
    INVALID_AUDIENCE = "invalid_audience"
    INVALID_ISSUER = "invalid_issuer"
    MISSING_SUBJECT = "missing_subject"
    INVALID = "invalid"


class AsgiScopeType(StrEnum):
    """ASGI スコープ種別(``scope["type"]``)。

    Attributes:
        HTTP: HTTP リクエスト。
    """

    HTTP = "http"


class AsgiMessageType(StrEnum):
    """ASGI 送信メッセージ種別(``message["type"]``)。

    Attributes:
        RESPONSE_START: 応答開始(ステータス/ヘッダを含む)。
    """

    RESPONSE_START = "http.response.start"


# ASGI スコープ/メッセージ辞書のフィールドキー(プロトコル語彙)。
ASGI_TYPE_KEY = "type"
ASGI_STATUS_KEY = "status"
ASGI_HEADERS_KEY = "headers"


class UpstreamPath(StrEnum):
    """上流 OpenAI 互換 API のパス(FlowNote 自身のルートではない)。

    Attributes:
        CHAT_COMPLETIONS: chat completions。
        EMBEDDINGS: embeddings。
    """

    CHAT_COMPLETIONS = "/v1/chat/completions"
    EMBEDDINGS = "/v1/embeddings"


# CORS の最小許可セット(実際に用いる method/header に限定する)。
CORS_ALLOW_METHODS: tuple[str, ...] = (
    HttpMethod.GET,
    HttpMethod.POST,
    HttpMethod.PUT,
    HttpMethod.PATCH,
    HttpMethod.DELETE,
)
CORS_ALLOW_HEADERS: tuple[str, ...] = (
    HeaderName.AUTHORIZATION,
    HeaderName.CONTENT_TYPE,
    HeaderName.REQUEST_ID,
    HeaderName.TRACEPARENT,
)
