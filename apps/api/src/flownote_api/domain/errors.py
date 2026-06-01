"""ドメイン例外とエラーカタログ。

レイヤをまたいで意味のあるエラーを表現する。各例外は以下を構造的に分離して保持する
([ログ規約](../../../../docs/observability/logging-spec.md) / [マスキング規約] 参照):

- ``code``: クライアント・サポートが判別に使う**安定識別子**(例 ``RES.NOT_FOUND``)。
  メッセージやクラス名は変わりうるが、コードは公開 API の契約として固定する。
- ``http_status``: 既定の HTTP ステータス。
- ``public_title`` / ``public_detail``: **クライアントに見せてよい**文言(機密を含めない)。
- ``internal_context``: **ログにだけ出す**詳細(内部ID・原因など)。応答には載せない。

この分離により、例外メッセージへ機密(SQL・内部ID・PII)が混入してもクライアントへ漏れない。
インターフェース層はこれらを RFC 9457 Problem Details へ写像し
([interface/http/problem.py])、境界で重大度付きログを1度だけ記録する。
"""

from __future__ import annotations

from dataclasses import dataclass


class DomainError(Exception):
    """ドメイン層の基底例外。

    クラス変数 ``code`` / ``http_status`` / ``public_title`` を各サブクラスで上書きし、
    インスタンス生成時に ``public_detail`` と ``internal_context`` を与える。

    Attributes:
        code: 安定したエラー識別子(``<DOMAIN>.<NAME>``)。
        http_status: 既定 HTTP ステータス。
        public_title: クライアントに見せる短い表題(機密を含めない)。
        public_detail: クライアントに見せる詳細(機密を含めない)。``None`` 可。
        internal_context: ログにのみ出す詳細(内部IDや原因など)。
    """

    # サブクラスで上書きする既定値(基底はフォールバックの内部エラー)。
    code: str = "GEN.INTERNAL"
    http_status: int = 500
    public_title: str = "内部エラーが発生しました"

    def __init__(
        self,
        public_detail: str | None = None,
        *,
        internal_context: dict[str, object] | None = None,
    ) -> None:
        """エラーを生成する。

        Args:
            public_detail: クライアントへ返してよい詳細文言。``None`` なら表題のみ。
            internal_context: ログにのみ出す機密を含みうる詳細。
        """
        self.public_detail = public_detail
        self.internal_context: dict[str, object] = dict(internal_context or {})
        # 例外メッセージ(str(exc))は公開文言のみとし、内部文脈を混ぜない。
        super().__init__(public_detail or self.public_title)


class NotFoundError(DomainError):
    """要求された資源が存在しないことを表す。

    資源IDは推測列挙対策と情報秘匿のため公開文言に含めず、``internal_context`` にのみ残す。

    Attributes:
        entity: 資源種別(``note`` 等)。
        entity_id: 資源識別子(ログ専用)。
    """

    code = "RES.NOT_FOUND"
    http_status = 404
    public_title = "リソースが見つかりません"

    def __init__(self, entity: str, entity_id: str) -> None:
        """エラーを生成する。

        Args:
            entity: 資源種別。
            entity_id: 資源識別子(公開せずログのみ)。
        """
        self.entity = entity
        self.entity_id = entity_id
        super().__init__(
            public_detail=f"{entity} が見つかりません",
            internal_context={"flownote.entity": entity, "flownote.entity_id": entity_id},
        )


class PermissionDeniedError(DomainError):
    """要求された操作が認可されないことを表す。

    Attributes:
        permission: 要求された権限。
        resource: 対象資源(任意・ログ専用)。
    """

    code = "AUTHZ.DENIED"
    http_status = 403
    public_title = "権限がありません"

    def __init__(self, permission: str, resource: str | None = None) -> None:
        """エラーを生成する。

        Args:
            permission: 要求された権限。
            resource: 対象資源識別子(公開せずログのみ)。
        """
        self.permission = permission
        self.resource = resource
        context: dict[str, object] = {"authz.permission": permission}
        if resource is not None:
            context["authz.resource"] = resource
        super().__init__(
            public_detail="この操作を行う権限がありません",
            internal_context=context,
        )


class ValidationError(DomainError):
    """入力がドメインの不変条件に反することを表す。

    検証メッセージは利用者の修正を促す公開文言として扱う(機密を含めない前提)。
    """

    code = "VAL.INVALID"
    http_status = 422
    public_title = "入力が不正です"


class ConflictError(DomainError):
    """資源の競合(重複・不正な状態遷移など)を表す。"""

    code = "RES.CONFLICT"
    http_status = 409
    public_title = "リソースが競合しています"


@dataclass(frozen=True, slots=True)
class ErrorCatalogEntry:
    """エラーカタログの1項目。

    Attributes:
        code: 安定エラー識別子。
        http_status: 既定 HTTP ステータス。
        public_title: 公開表題。
        exception: 対応する例外クラスの完全名。
    """

    code: str
    http_status: int
    public_title: str
    exception: str


def _iter_subclasses(cls: type[DomainError]) -> list[type[DomainError]]:
    """``DomainError`` の全子孫クラスを重複なく列挙する。

    Args:
        cls: 探索の起点クラス。

    Returns:
        子孫クラスの一覧(自身は含まない)。
    """
    seen: dict[type[DomainError], None] = {}
    for sub in cls.__subclasses__():
        if sub not in seen:
            seen[sub] = None
            for descendant in _iter_subclasses(sub):
                seen.setdefault(descendant, None)
    return list(seen)


def error_catalog() -> list[ErrorCatalogEntry]:
    """既知のドメインエラーを ``code`` で安定ソートしたカタログを返す。

    OpenAPI 補足やサポート資料の生成元(コード ↔ 意味 ↔ HTTP status の対応表)に用いる。

    Note:
        列挙は ``__subclasses__()`` に基づくため、**import 済み**の :class:`DomainError`
        サブクラスのみが対象。サブクラスを別モジュールに定義する場合は、本関数の呼び出し前に
        当該モジュールが import 済みであることを保証すること(現状は本モジュールに集約)。

    Returns:
        全 :class:`DomainError` サブクラスのカタログ項目。
    """
    entries = [
        ErrorCatalogEntry(
            code=sub.code,
            http_status=sub.http_status,
            public_title=sub.public_title,
            exception=f"{sub.__module__}.{sub.__qualname__}",
        )
        for sub in _iter_subclasses(DomainError)
    ]
    return sorted(entries, key=lambda entry: entry.code)
