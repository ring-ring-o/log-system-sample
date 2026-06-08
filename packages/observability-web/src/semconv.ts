// 自動生成: `flownote-telemetry-catalog --target semconv`。手で編集しない。
// 生成元はバックエンドの SSOT (flownote_api.interface.telemetry_catalog)。

/** FE/BE が共有するテレメトリ属性/リソースキー(OTel/FlowNote)。 */
export const ATTR = {
  /** リソース: 環境。 */
  DEPLOYMENT_ENVIRONMENT: "deployment.environment.name",
  /** 失敗分類(OTel 共通)。 */
  ERROR_TYPE: "error.type",
  /** 安定エラーコード。 */
  FLOWNOTE_ERROR_CODE: "flownote.error.code",
  /** エラー相関トレース。 */
  FLOWNOTE_ERROR_TRACE_ID: "flownote.error.trace_id",
  /** HTTP メソッド。 */
  HTTP_REQUEST_METHOD: "http.request.method",
  /** HTTP ステータス。 */
  HTTP_RESPONSE_STATUS_CODE: "http.response.status_code",
  /** ログスキーマ世代。 */
  LOG_SCHEMA_VERSION: "flownote.log.schema_version",
  /** リソース: サービス名。 */
  SERVICE_NAME: "service.name",
  /** リソース: バージョン。 */
  SERVICE_VERSION: "service.version",
  /** リクエストパス。 */
  URL_PATH: "url.path",
} as const;

/** 共有属性キー名の union 型。 */
export type AttrName = keyof typeof ATTR;
