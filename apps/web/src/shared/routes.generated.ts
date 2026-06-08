// 自動生成: `flownote-telemetry-catalog --target routes`。手で編集しない。
// 生成元はバックエンドの SSOT (flownote_api.interface.telemetry_catalog)。

/** フロントが呼び出す API ルートのフルパス(バックエンド SSOT と一致)。 */
export const API_ROUTES = {
  AI_CONSULT: "/api/ai/consult",
  AI_PROGRESS: "/api/ai/progress",
  AI_SEARCH: "/api/ai/search",
  NOTES: "/api/notes",
  TASKS: "/api/tasks",
} as const;

/** ルート名の union 型。 */
export type ApiRouteName = keyof typeof API_ROUTES;
