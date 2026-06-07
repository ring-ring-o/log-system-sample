"""境界(interface 層)が直接発行する公開エラーコードの単一源泉(SSOT)と統合カタログ。

ドメイン例外([domain/errors.py])に加え、interface 層の例外ハンドラが
``DomainError`` 派生**でない**事象から直接発行する公開コードが存在する
(認証失敗 ``AUTH.UNAUTHORIZED``・リクエスト検証失敗 ``VAL.REQUEST``)。これらを文字列
リテラルでハンドラに散らさず本モジュールに集約し、ハンドラ
([interface/middleware/errors.py])とカタログ抽出の双方が同じ定義を参照する。

これにより「クライアントに実際に返る全コード」を一点から列挙でき、抽出コマンド
([interface/cli/error_catalog.py])が**ドメイン＋境界の完全なカタログ**を出力できる。
"""

from __future__ import annotations

from dataclasses import dataclass

from flownote_api.domain.errors import ErrorCatalogEntry, error_catalog


@dataclass(frozen=True, slots=True)
class BoundaryError:
    """境界が直接発行する公開エラー(``DomainError`` 派生でないもの)の定義。

    Attributes:
        code: 安定エラー識別子(``<DOMAIN>.<NAME>``)。
        http_status: HTTP ステータス。
        public_title: クライアントに見せる表題。
        public_detail: クライアントに見せる詳細(境界では静的に定まる)。
        source: 発行契機となる例外の完全名。
    """

    code: str
    http_status: int
    public_title: str
    public_detail: str
    source: str


# 認証情報が無効/欠落のときに interface 層が返す(infrastructure の InvalidTokenError 由来)。
AUTH_UNAUTHORIZED = BoundaryError(
    code="AUTH.UNAUTHORIZED",
    http_status=401,
    public_title="認証が必要です",
    public_detail="有効な認証情報が必要です",
    source="flownote_api.infrastructure.security.token.InvalidTokenError",
)

# FastAPI のリクエスト検証(スキーマ違反)で返す。フィールド単位の詳細は応答に同梱する。
VAL_REQUEST = BoundaryError(
    code="VAL.REQUEST",
    http_status=422,
    public_title="入力が不正です",
    public_detail="リクエストの内容を確認してください",
    source="fastapi.exceptions.RequestValidationError",
)

# 境界が直接発行する公開コードの一覧(SSOT)。
BOUNDARY_ERRORS: tuple[BoundaryError, ...] = (AUTH_UNAUTHORIZED, VAL_REQUEST)


def boundary_catalog() -> list[ErrorCatalogEntry]:
    """境界が直接発行するコードを :class:`ErrorCatalogEntry` に正規化して返す。

    Returns:
        ``origin="interface"`` のカタログ項目(コード昇順)。
    """
    entries = [
        ErrorCatalogEntry(
            code=err.code,
            http_status=err.http_status,
            public_title=err.public_title,
            public_detail=err.public_detail,
            origin="interface",
            source=err.source,
        )
        for err in BOUNDARY_ERRORS
    ]
    return sorted(entries, key=lambda entry: entry.code)


def full_error_catalog() -> list[ErrorCatalogEntry]:
    """ドメイン＋境界を統合した、クライアントに返る全公開コードのカタログを返す。

    抽出コマンドやドキュメント生成の唯一の入口。``(code, origin)`` で安定ソートするため、
    生成物(Markdown/JSON/CSV)の差分を小さく保てる。

    Returns:
        ドメイン例外と境界エラーを合わせたカタログ項目(``(code, origin)`` 昇順)。
    """
    entries = [*error_catalog(), *boundary_catalog()]
    return sorted(entries, key=lambda entry: (entry.code, entry.origin))
