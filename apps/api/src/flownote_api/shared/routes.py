"""API ルートの定義(SSOT)。

FastAPI ルータの ``prefix`` とデコレータの ``path`` に渡す文字列を一点に集約する。フロントが
叩くフルパスは本モジュールから合成し、テレメトリカタログ経由で TypeScript へ生成する
([interface/telemetry_catalog.py])。これにより FE/BE のパス不一致(タイポ)を構造的に防ぐ。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class RouterTag(StrEnum):
    """OpenAPI のルータタグ。

    Attributes:
        NOTES: メモ。
        TASKS: タスク。
        AI: AI。
        VERSIONS: バージョン管理。
        HEALTH: ヘルスチェック。
        ADMIN: 運用管理。
    """

    NOTES = "notes"
    TASKS = "tasks"
    AI = "ai"
    VERSIONS = "versions"
    HEALTH = "health"
    ADMIN = "admin"


# --- ルータ prefix(``APIRouter(prefix=...)``) ---
NOTES_PREFIX = "/api/notes"
TASKS_PREFIX = "/api/tasks"
AI_PREFIX = "/api/ai"
VERSIONS_PREFIX = "/api/notes/{note_id}/versions"
ADMIN_PREFIX = "/admin"

# --- サブパス(デコレータの ``path``) ---
# 空文字は prefix 直下(コレクション)を表す。
ROOT = ""
BY_NOTE_ID = "/{note_id}"
BY_TASK_ID = "/{task_id}"
TASK_STATUS = "/{task_id}/status"
AI_CONSULT = "/consult"
AI_SEARCH = "/search"
AI_PROGRESS = "/progress"
VERSION_DIFF = "/diff"
VERSION_RESTORE = "/{version_id}/restore"
HEALTH = "/health"
LOG_LEVEL = "/log-level"


@dataclass(frozen=True, slots=True)
class FrontendRoute:
    """フロントが呼び出す API のフルパス(生成共有の単位)。

    Attributes:
        name: TypeScript 側の定数名(``API_ROUTES.<name>``)。
        path: フルパス(prefix + サブパス)。
    """

    name: str
    path: str


# フロントが実際に叩くエンドポイントのフルパス(BE prefix + サブパスから合成)。
# 生成対象はこの集合に限定し、テンプレート(``/{id}`` 等)や FE 未使用ルートは含めない。
FRONTEND_ROUTES: tuple[FrontendRoute, ...] = (
    FrontendRoute(name="NOTES", path=NOTES_PREFIX + ROOT),
    FrontendRoute(name="TASKS", path=TASKS_PREFIX + ROOT),
    FrontendRoute(name="AI_CONSULT", path=AI_PREFIX + AI_CONSULT),
    FrontendRoute(name="AI_SEARCH", path=AI_PREFIX + AI_SEARCH),
    FrontendRoute(name="AI_PROGRESS", path=AI_PREFIX + AI_PROGRESS),
)
