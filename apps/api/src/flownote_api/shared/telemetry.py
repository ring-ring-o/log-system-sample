"""アプリ固有のテレメトリ語彙(イベント名・操作名・監査 action・属性キー)。

低カーディナリティの**イベント/操作/span 名**、**監査 action**、および FlowNote 固有の
**バックエンドローカル属性キー**を集約する。OTel 標準キーや FE と共有するキーは
:mod:`flownote_observability.semconv` を参照し、ここには「BE 内でのみ出すキー」を置く。

意図の区別(同値だが別物):
    - :class:`AuditAction.NOTE_DELETE` (監査 action ``note.delete``) と
      :class:`AppEvent.NOTE_DELETED` (業務イベント ``note.deleted``) は別綴り・別意図。
"""

from __future__ import annotations

from enum import StrEnum


class AppEvent(StrEnum):
    """業務イベント/操作の名前(ログ body・``operation`` の span 名)。

    ``operation``/``log_event``/ロガー直呼びの **body** に用いる低カーディナリティ名。
    """

    NOTE_CREATE = "note.create"
    NOTE_UPDATE = "note.update"
    NOTE_DELETED = "note.deleted"
    NOTE_VERSION_RESTORED = "note.version.restored"
    TASK_CREATED = "task.created"
    TASK_STATUS_CHANGED = "task.status.changed"
    TASK_DELETED = "task.deleted"
    AI_CONSULT_COMPLETED = "ai.consult.completed"
    AI_SEARCH_COMPLETED = "ai.search.completed"
    AI_PROGRESS_REVIEWED = "ai.progress.reviewed"
    APP_STARTED = "app.started"
    HTTP_REQUEST_COMPLETED = "http.request.completed"
    ERROR_HANDLED = "error.handled"
    ERROR_UNHANDLED = "error.unhandled"


class SpanName(StrEnum):
    """``operation`` を介さず直接張る内部 span の名前。"""

    USECASE_TASK_CREATE = "usecase.task.create"
    USECASE_AI_CONSULT = "usecase.ai.consult"
    USECASE_AI_SEARCH = "usecase.ai.search"
    USECASE_AI_REVIEW_PROGRESS = "usecase.ai.review_progress"
    USECASE_VERSION_RESTORE = "usecase.version.restore"


class AuditAction(StrEnum):
    """監査ログの action(``audit.action`` の値)。

    Attributes:
        NOTE_DELETE: メモ削除。
        TASK_DELETE: タスク削除。
        AUTHZ_DECISION: 認可判定。
        ADMIN_LOG_LEVEL_CHANGE: ログ閾値変更。
    """

    NOTE_DELETE = "note.delete"
    TASK_DELETE = "task.delete"
    AUTHZ_DECISION = "authz.decision"
    ADMIN_LOG_LEVEL_CHANGE = "admin.log_level.change"


class SecurityAction(StrEnum):
    """セキュリティログの action(``audit.action`` の値)。

    Attributes:
        AUTH_TOKEN_VERIFY: トークン検証。
    """

    AUTH_TOKEN_VERIFY = "auth.token.verify"


class AiErrorType(StrEnum):
    """上流 AI 呼び出し失敗の分類(``error.type`` の値)。

    Attributes:
        TIMEOUT: タイムアウト。
        RATE_LIMIT: レート制限(429)。
        UPSTREAM_5XX: 上流 5xx。
        UPSTREAM_4XX: 上流 4xx。
        ERROR: その他。
    """

    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    UPSTREAM_5XX = "upstream_5xx"
    UPSTREAM_4XX = "upstream_4xx"
    ERROR = "error"


# --- バックエンドローカル属性キー(FE へは生成共有しない ``flownote.*`` キー) ---
# 値は名前空間適用後の最終形(``flownote.*``)で固定し、出力の一意性を担保する。
NOTE_ID_KEY = "flownote.note.id"
VERSION_ID_KEY = "flownote.version.id"
TASK_ID_KEY = "flownote.task.id"
TASK_STATUS_KEY = "flownote.task.status"
SEARCH_HIT_COUNT_KEY = "flownote.search.hit_count"
TASK_STALLED_COUNT_KEY = "flownote.task.stalled_count"
REPO_BACKEND_KEY = "flownote.repo_backend"
AI_BACKEND_KEY = "flownote.ai_backend"
AUTH_MODE_KEY = "flownote.auth_mode"
