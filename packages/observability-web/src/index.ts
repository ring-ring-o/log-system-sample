/**
 * FlowNote 共有可観測性ライブラリ(ブラウザ)。
 *
 * 構造化クライアントログ・トレース相関(traceparent)・マスキングを提供する。バックエンドの
 * ログ規約({@link ../../../docs/observability/logging-spec.md})とスキーマ・重大度を揃える。
 */

export { redact } from "./redaction";
export { type AttrName, ATTR } from "./semconv";
export {
  CLIENT_ATTR,
  CLIENT_EVENT,
  CONTENT_TYPE,
  HEADER,
  HTTP_METHOD,
  VITAL_ATTR,
} from "./constants";
export { type SeverityText, SEVERITY_NUMBER, severityForHttpStatus } from "./severity";
export { type ClientLogRecord, type ResourceInfo, buildRecord } from "./schema";
export {
  type TraceContext,
  buildTraceparent,
  childTraceContext,
  getPageTrace,
  newTraceContext,
  startPageTrace,
} from "./trace";
export { type LogSink, type LoggerOptions, ClientLogger, createBeaconSink } from "./logger";
export { type FetchFn, createInstrumentedFetch } from "./instrument";
export { type ProblemDetails, parseProblemDetails } from "./problem";
export { reportWebVitals } from "./vitals";
export { registerGlobalErrorHandlers } from "./error";

import { ClientLogger, type LogSink, createBeaconSink } from "./logger";
import type { ResourceInfo } from "./schema";

/** 可観測性の初期化オプション。 */
export interface ObservabilityInit {
  /** リソース情報。 */
  resource: ResourceInfo;
  /** ログ送出先 URL(OTLP/HTTP または内部プロキシ)。`sink` 指定時は無視。 */
  endpoint?: string;
  /** 送出先を直接注入(テスト/カスタム用)。 */
  sink?: LogSink;
}

/**
 * クライアントロガーを生成する簡易ファクトリ。
 *
 * @param init - 初期化オプション。
 * @returns 構成済みの {@link ClientLogger}。
 * @throws endpoint も sink も指定が無い場合。
 */
export function createLogger(init: ObservabilityInit): ClientLogger {
  const sink = init.sink ?? (init.endpoint ? createBeaconSink(init.endpoint) : undefined);
  if (!sink) {
    throw new Error("createLogger には endpoint か sink のいずれかが必要です");
  }
  return new ClientLogger({ resource: init.resource, sink });
}
