/**
 * クライアントログのスキーマ。
 *
 * バックエンドの {@link ../../../docs/observability/logging-spec.md} §2 と整合する形に整形する。
 */

import type { SeverityText } from "./severity";
import { SEVERITY_NUMBER } from "./severity";

/** 構造化クライアントログ1件。 */
export interface ClientLogRecord {
  /** RFC3339(ミリ秒)・UTC の発生時刻。 */
  timestamp: string;
  /** 重大度ラベル。 */
  severity_text: SeverityText;
  /** OTel SeverityNumber。 */
  severity_number: number;
  /** 低カーディナリティのイベント名。 */
  body: string;
  /** 発生元サービス(常に flownote-web)。 */
  "service.name": string;
  /** バージョン。 */
  "service.version": string;
  /** 環境。 */
  "deployment.environment": string;
  /** 相関トレースID。 */
  trace_id: string | null;
  /** 相関スパンID。 */
  span_id: string | null;
  /** 構造化属性。 */
  attributes: Record<string, unknown>;
}

/** ログ整形に必要なリソース情報。 */
export interface ResourceInfo {
  serviceName: string;
  serviceVersion: string;
  environment: string;
}

/**
 * スキーマ準拠のログレコードを組み立てる。
 *
 * @param params - レコード生成のパラメータ。
 * @param params.severity - 重大度ラベル。
 * @param params.body - イベント名。
 * @param params.attributes - 構造化属性。
 * @param params.resource - リソース情報。
 * @param params.trace - 相関トレース文脈(無ければ null)。
 * @param params.nowIso - 生成時刻の ISO 文字列(テスト容易性のため注入可能)。
 * @returns 整形済みの {@link ClientLogRecord}。
 */
export function buildRecord(params: {
  severity: SeverityText;
  body: string;
  attributes: Record<string, unknown>;
  resource: ResourceInfo;
  trace: { traceId: string; spanId: string } | null;
  nowIso: string;
}): ClientLogRecord {
  return {
    timestamp: params.nowIso,
    severity_text: params.severity,
    severity_number: SEVERITY_NUMBER[params.severity],
    body: params.body,
    "service.name": params.resource.serviceName,
    "service.version": params.resource.serviceVersion,
    "deployment.environment": params.resource.environment,
    trace_id: params.trace?.traceId ?? null,
    span_id: params.trace?.spanId ?? null,
    attributes: params.attributes,
  };
}
