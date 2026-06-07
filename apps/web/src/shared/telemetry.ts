/**
 * フロント固有のテレメトリ語彙(web イベント名・アクション・属性キー・既定値)。
 *
 * FE/BE で一致が必要な属性キーは生成物 `@flownote/observability-web` の `ATTR` を参照する。
 * 本モジュールには「フロントだけが用いる値」を集約し、文字列リテラルの散在を防ぐ。
 *
 * 意図の区別(同値だが別物):
 *   - `WEB_ACTION.UNIFIED_SEARCH`(フロントのユーザー操作)は、バックエンドの
 *     `AIUseCase.UNIFIED_SEARCH`(AI ユースケース)と**意図的に同値だが別管理**。
 */

/** フロントが記録する低カーディナリティのイベント名(ログ body)。 */
export const WEB_EVENT = {
  /** API 呼び出しが安定コード付きで失敗。 */
  API_ERROR: "web.api.error",
  /** メモ一覧の読み込み失敗。 */
  NOTES_LOAD_FAILED: "web.notes.load_failed",
  /** メモ作成。 */
  NOTE_CREATED: "web.note.created",
  /** 統合検索の実行。 */
  SEARCH_EXECUTED: "web.search.executed",
  /** アプリのマウント(初期化完了)。 */
  APP_MOUNTED: "web.app.mounted",
} as const;

/** ユーザー操作の識別子(`flownote.web.action` の値)。 */
export const WEB_ACTION = {
  CREATE_NOTE: "create_note",
  UNIFIED_SEARCH: "unified_search",
} as const;

/** フロント固有の属性キー(`flownote.*`)。 */
export const WEB_ATTR = {
  /** ユーザー操作の識別子。 */
  ACTION: "flownote.web.action",
} as const;

/** 認可ヘッダ値のプレフィックス(`Authorization: Bearer <token>`)。 */
export const BEARER_PREFIX = "Bearer ";

/** リソース属性の既定値(環境)。 */
export const DEFAULT_ENV = "local";

/** フロントのサービス識別子(リソース属性 `service.name` の値)。 */
export const WEB_SERVICE_NAME = "flownote-web";
