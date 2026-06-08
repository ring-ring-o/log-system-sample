"""リクエスト文脈の束縛。

[ログ規約](../../../docs/observability/logging-spec.md) §6 に対応。
``contextvars`` ベースで ``request_id``/``user.id``/``session_id`` を束縛し、
以降のログが自動的にこれらを継承できるようにする。structlog の contextvars と統合する。
"""

from __future__ import annotations

import hashlib

import structlog

from flownote_observability.semconv import USER_ID_KEY

# セッションIDをそのまま出さないためのハッシュ短縮桁数([マスキング規約] §3.3)。
_SESSION_HASH_LEN = 16


def hash_session_id(session_id: str) -> str:
    """セッションIDを不可逆ハッシュに短縮する。

    Args:
        session_id: 生のセッション識別子。

    Returns:
        SHA-256 の先頭16桁(突合は可能・値は秘匿)。
    """
    digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()
    return digest[:_SESSION_HASH_LEN]


def bind_request_context(
    *,
    request_id: str,
    user_id: str | None = None,
    session_id: str | None = None,
) -> None:
    """リクエスト単位の相関キーを文脈に束縛する。

    束縛後に生成される全ログへ自動的に付与される。``user_id`` は不透明ID(Keycloak ``sub``)
    を想定し、PII は渡さない。``session_id`` はハッシュ化して束縛する。

    Args:
        request_id: リクエスト識別子。
        user_id: 認証主体の不透明ID。未認証なら ``None``。
        session_id: セッション識別子(ハッシュ化して保持)。
    """
    structlog.contextvars.bind_contextvars(request_id=request_id)
    if user_id is not None:
        # OTel セマンティック規約のキー名 ``user.id`` で束縛する。
        structlog.contextvars.bind_contextvars(**{USER_ID_KEY: user_id})
    if session_id is not None:
        structlog.contextvars.bind_contextvars(session_id=hash_session_id(session_id))


def clear_request_context() -> None:
    """束縛済みのリクエスト文脈をすべて解除する。

    リクエスト処理の終了時(ミドルウェアの finally)に呼び出す。
    """
    structlog.contextvars.clear_contextvars()
