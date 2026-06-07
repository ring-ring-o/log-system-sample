"""ドメインエラーの契約テスト(エラーコード・内部/外部メッセージ分離・カタログ)。

[ログ規約](../../../../docs/observability/logging-spec.md) のエラー設計を固定する。
ここで固定するのは「安定識別子(code)を持つ」「公開文言と内部文脈が構造的に分かれる」
「カタログが一意なコードで列挙できる」の3点。
"""

from __future__ import annotations

from flownote_api.domain.errors import (
    ConflictError,
    DomainError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
    error_catalog,
)


def test_each_error_has_stable_code_and_status() -> None:
    # 各例外は安定したエラーコードと既定 HTTP ステータスを持つ。
    assert (NotFoundError.code, NotFoundError.http_status) == ("RES.NOT_FOUND", 404)
    assert (PermissionDeniedError.code, PermissionDeniedError.http_status) == ("AUTHZ.DENIED", 403)
    assert (ValidationError.code, ValidationError.http_status) == ("VAL.INVALID", 422)
    assert (ConflictError.code, ConflictError.http_status) == ("RES.CONFLICT", 409)


def test_not_found_separates_internal_id_from_public_message() -> None:
    exc = NotFoundError("note", "secret-internal-id-123")
    # 公開文言(str/ public_detail)には内部IDを含めない(情報秘匿・推測列挙対策)。
    assert "secret-internal-id-123" not in str(exc)
    assert exc.public_detail is not None
    assert "secret-internal-id-123" not in exc.public_detail
    # 内部IDは internal_context にのみ残り、ログ側で利用できる。
    assert exc.internal_context["flownote.entity_id"] == "secret-internal-id-123"
    assert exc.internal_context["flownote.entity"] == "note"


def test_permission_denied_keeps_resource_internal() -> None:
    exc = PermissionDeniedError("note:delete", resource="note:n-42")
    assert "n-42" not in str(exc)
    assert exc.internal_context["authz.permission"] == "note:delete"
    assert exc.internal_context["authz.resource"] == "note:n-42"


def test_validation_message_is_public() -> None:
    # 検証メッセージは利用者向けの公開文言として保持する。
    exc = ValidationError("タイトルは空にできません")
    assert exc.public_detail == "タイトルは空にできません"
    assert str(exc) == "タイトルは空にできません"
    assert exc.code == "VAL.INVALID"


def test_base_domain_error_defaults_to_internal() -> None:
    # 識別されない基底エラーは 500 / 内部エラーへフォールバックする。
    exc = DomainError()
    assert exc.http_status == 500
    assert exc.code == "GEN.INTERNAL"
    assert exc.internal_context == {}


def test_error_catalog_codes_are_unique_and_cover_subclasses() -> None:
    catalog = error_catalog()
    codes = [entry.code for entry in catalog]
    # コードは一意(クライアントの判別キーとして衝突してはならない)。
    assert len(codes) == len(set(codes))
    # 既知の主要エラーがカタログに含まれる。
    assert {"RES.NOT_FOUND", "AUTHZ.DENIED", "VAL.INVALID", "RES.CONFLICT"} <= set(codes)
    # カタログはコード昇順で安定している(生成物の差分を小さく保つ)。
    assert codes == sorted(codes)


def test_error_catalog_includes_base_internal_fallback() -> None:
    # 基底 DomainError(GEN.INTERNAL)も未識別例外の公開コードとして列挙される。
    catalog = error_catalog()
    internal = next(entry for entry in catalog if entry.code == "GEN.INTERNAL")
    assert internal.http_status == 500
    assert internal.source.endswith("DomainError")


def test_error_catalog_entries_are_tagged_as_domain() -> None:
    # ドメイン抽出の全項目は origin=domain で、発行元クラス名を保持する。
    catalog = error_catalog()
    assert {entry.origin for entry in catalog} == {"domain"}
    assert all(entry.source for entry in catalog)
