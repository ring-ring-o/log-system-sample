"""アプリ固有テレメトリ定数の契約テスト。

イベント名・監査 action・属性キー・エンティティ種別の値を固定し、「同値だが別意図」の定数が
**別物として共存**することを明示する(綴りの一意性 = 規約契約の固定)。
"""

from __future__ import annotations

from flownote_api.domain.ai import AIUseCase, ChatRole
from flownote_api.domain.errors import (
    AUTHZ_PERMISSION_KEY,
    AUTHZ_RESOURCE_KEY,
    ENTITY_ID_KEY,
    ENTITY_KEY,
)
from flownote_api.domain.kinds import EntityType
from flownote_api.shared import telemetry as tel
from flownote_observability import conventions, semconv


def test_app_event_names_are_pinned() -> None:
    assert tel.AppEvent.NOTE_CREATE == "note.create"
    assert tel.AppEvent.NOTE_DELETED == "note.deleted"
    assert tel.AppEvent.HTTP_REQUEST_COMPLETED == "http.request.completed"
    assert tel.AppEvent.ERROR_HANDLED == "error.handled"
    assert tel.AppEvent.ERROR_UNHANDLED == "error.unhandled"


def test_audit_action_delete_differs_from_business_event() -> None:
    # 監査 action ``note.delete`` と業務イベント ``note.deleted`` は別綴り・別意図。
    assert tel.AuditAction.NOTE_DELETE == "note.delete"
    assert tel.AppEvent.NOTE_DELETED == "note.deleted"
    assert tel.AuditAction.NOTE_DELETE != tel.AppEvent.NOTE_DELETED


def test_backend_attribute_keys_are_namespaced() -> None:
    # BE ローカル属性キーは名前空間適用後の最終形(``flownote.*``)で固定する。
    assert tel.NOTE_ID_KEY == "flownote.note.id"
    assert tel.TASK_ID_KEY == "flownote.task.id"
    assert tel.TASK_STATUS_KEY == "flownote.task.status"


def test_ai_use_case_matches_web_action_intentionally() -> None:
    # AIUseCase.UNIFIED_SEARCH(AI ユースケース)は FE の WEB_ACTION.UNIFIED_SEARCH
    # (ユーザー操作)と**意図的に同値**だが、別の意図・別の管理単位である。
    assert AIUseCase.UNIFIED_SEARCH == "unified_search"
    assert AIUseCase.TASK_CONSULT == "task_consult"
    assert AIUseCase.PROGRESS_REVIEW == "progress_review"


def test_chat_role_and_genai_system_are_distinct() -> None:
    # ChatRole.SYSTEM(メッセージ役割)と GenAiSystem(プロバイダ系統)は別意図の別 enum。
    assert ChatRole.SYSTEM == "system"
    assert conventions.GenAiSystem.STUB == "stub"
    assert ChatRole.SYSTEM not in set(conventions.GenAiSystem)


def test_entity_type_values_and_resource_id() -> None:
    assert EntityType.NOTE == "note"
    assert EntityType.TASK == "task"
    assert EntityType.VERSION == "version"
    # 監査ログの資源識別子は ``<種別>:<id>`` 形式。
    assert EntityType.NOTE.resource_id("42") == "note:42"


def test_domain_error_keys_match_semconv() -> None:
    # ドメインは obs-py を import しないが、キー値は semconv と一致する(ドリフト防止)。
    assert AUTHZ_PERMISSION_KEY == semconv.AUTHZ_PERMISSION_KEY
    assert AUTHZ_RESOURCE_KEY == semconv.AUTHZ_RESOURCE_KEY
    # エラー文脈の業務キーは ``flownote.*`` 名前空間。
    assert ENTITY_KEY == "flownote.entity"
    assert ENTITY_ID_KEY == "flownote.entity_id"
