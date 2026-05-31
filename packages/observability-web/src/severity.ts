/**
 * ログ重大度。
 *
 * バックエンドの {@link ../../../docs/observability/logging-spec.md} §3 と一致させ、
 * 6段階を OpenTelemetry の SeverityNumber に対応させる。
 */

/** 重大度ラベル。 */
export type SeverityText = "TRACE" | "DEBUG" | "INFO" | "WARN" | "ERROR" | "FATAL";

/** ラベル → OTel SeverityNumber の対応表。 */
export const SEVERITY_NUMBER: Record<SeverityText, number> = {
  TRACE: 1,
  DEBUG: 5,
  INFO: 9,
  WARN: 13,
  ERROR: 17,
  FATAL: 21,
};

/**
 * HTTP ステータスコードから既定の重大度を決める。
 *
 * ログ規約 §3 に従い、4xx は WARN、5xx は ERROR、その他は INFO とする。
 *
 * @param statusCode - HTTP ステータスコード。
 * @returns 対応する重大度ラベル。
 */
export function severityForHttpStatus(statusCode: number): SeverityText {
  if (statusCode >= 500) return "ERROR";
  if (statusCode >= 400) return "WARN";
  return "INFO";
}
