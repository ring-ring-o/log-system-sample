/**
 * 構造化クライアントロガー。
 *
 * スキーマ整形・マスキング・相関付与を行い、注入された sink へ送る。送出先(OTLP/内部ルート)は
 * sink で差し替え可能にし、テストではメモリ sink を使う。
 * {@link ../../../docs/observability/frontend-logging.md} 参照。
 */

import { CONTENT_TYPE, HEADER, HTTP_METHOD } from "./constants";
import { redact } from "./redaction";
import type { ClientLogRecord, ResourceInfo } from "./schema";
import { buildRecord } from "./schema";
import type { SeverityText } from "./severity";
import type { TraceContext } from "./trace";

/** ログ送出先。整形済みレコードを受け取る。 */
export type LogSink = (record: ClientLogRecord) => void;

/** ロガーの構成。 */
export interface LoggerOptions {
  /** リソース情報。 */
  resource: ResourceInfo;
  /** 送出先。 */
  sink: LogSink;
  /** 現在のトレース文脈を返す関数(相関用、任意)。 */
  getTrace?: () => TraceContext | null;
  /** 現在時刻の ISO 文字列を返す関数(テスト容易性のため、任意)。 */
  now?: () => string;
}

/** 構造化クライアントロガー。 */
export class ClientLogger {
  private readonly resource: ResourceInfo;
  private readonly sink: LogSink;
  private readonly getTrace: () => TraceContext | null;
  private readonly now: () => string;

  /**
   * ロガーを生成する。
   *
   * @param options - ロガー構成。
   */
  constructor(options: LoggerOptions) {
    this.resource = options.resource;
    this.sink = options.sink;
    this.getTrace = options.getTrace ?? (() => null);
    this.now = options.now ?? (() => new Date().toISOString());
  }

  /**
   * 任意重大度のイベントを記録する。
   *
   * @param severity - 重大度ラベル。
   * @param body - 低カーディナリティのイベント名。
   * @param attributes - 構造化属性(送出前にマスクされる)。
   */
  log(
    severity: SeverityText,
    body: string,
    attributes: Record<string, unknown> = {},
    trace?: TraceContext | null,
  ): void {
    const record = buildRecord({
      severity,
      body,
      attributes: redact(attributes) as Record<string, unknown>,
      resource: this.resource,
      // 明示指定があればそれを、無ければ現在の文脈を相関に用いる。
      trace: trace !== undefined ? trace : this.getTrace(),
      nowIso: this.now(),
    });
    this.sink(record);
  }

  /** DEBUG ログ。 @param body イベント名。 @param attributes 属性。 */
  debug(body: string, attributes: Record<string, unknown> = {}): void {
    this.log("DEBUG", body, attributes);
  }

  /** INFO ログ。 @param body イベント名。 @param attributes 属性。 */
  info(body: string, attributes: Record<string, unknown> = {}): void {
    this.log("INFO", body, attributes);
  }

  /** WARN ログ。 @param body イベント名。 @param attributes 属性。 */
  warn(body: string, attributes: Record<string, unknown> = {}): void {
    this.log("WARN", body, attributes);
  }

  /** ERROR ログ。 @param body イベント名。 @param attributes 属性。 */
  error(body: string, attributes: Record<string, unknown> = {}): void {
    this.log("ERROR", body, attributes);
  }
}

/**
 * OTLP/HTTP(または内部プロキシ)へ送る sink を生成する。
 *
 * 離脱時の取りこぼしを抑えるため `sendBeacon` を優先し、無ければ `fetch` で送る。
 *
 * @param endpoint - 送出先URL。
 * @returns ログ sink。
 */
export function createBeaconSink(endpoint: string): LogSink {
  return (record: ClientLogRecord): void => {
    const payload = JSON.stringify(record);
    if (typeof navigator !== "undefined" && typeof navigator.sendBeacon === "function") {
      navigator.sendBeacon(endpoint, payload);
      return;
    }
    void fetch(endpoint, {
      method: HTTP_METHOD.POST,
      body: payload,
      headers: { [HEADER.CONTENT_TYPE]: CONTENT_TYPE.JSON },
      keepalive: true,
    });
  };
}
