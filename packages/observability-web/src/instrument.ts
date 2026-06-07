/**
 * フェッチ計装。
 *
 * API 呼び出しに W3C `traceparent` を付与してフロント→バックを相関させ、リクエストの結果を
 * 構造化ログに記録する({@link ../../../docs/observability/frontend-logging.md} §3)。
 */

import { CLIENT_ATTR, CLIENT_EVENT, HEADER, HTTP_METHOD } from "./constants";
import type { ClientLogger } from "./logger";
import { ATTR } from "./semconv";
import { severityForHttpStatus } from "./severity";
import { buildTraceparent, childTraceContext } from "./trace";

/** `fetch` 互換のシグネチャ。 */
export type FetchFn = (input: string | URL | Request, init?: RequestInit) => Promise<Response>;

/**
 * traceparent 付与とアクセスログを行う計装済み fetch を生成する。
 *
 * @param logger - 記録に用いるロガー。
 * @param baseFetch - 元の fetch 実装(既定はグローバル `fetch`)。
 * @returns 計装済みの fetch 関数。
 */
export function createInstrumentedFetch(logger: ClientLogger, baseFetch: FetchFn = fetch): FetchFn {
  return async (input: string | URL | Request, init?: RequestInit): Promise<Response> => {
    // ページトレースの子 span として発番し、ログとバックエンドを同一 trace に束ねる。
    const trace = childTraceContext();
    const headers = new Headers(init?.headers);
    headers.set(HEADER.TRACEPARENT, buildTraceparent(trace));

    const method = (init?.method ?? HTTP_METHOD.GET).toUpperCase();
    const url = typeof input === "string" ? input : input.toString();
    const startedAt = now();

    try {
      const response = await baseFetch(input, { ...init, headers });
      logger.log(
        severityForHttpStatus(response.status),
        CLIENT_EVENT.HTTP_CLIENT_REQUEST,
        {
          [ATTR.HTTP_REQUEST_METHOD]: method,
          [ATTR.URL_PATH]: toPath(url),
          [ATTR.HTTP_RESPONSE_STATUS_CODE]: response.status,
          // OTel 準拠で単位は秒(UCUM `s`)。ミリ秒計測値を 1000 で割って秒へ。
          [CLIENT_ATTR.HTTP_CLIENT_REQUEST_DURATION]: Math.round(now() - startedAt) / 1000,
        },
        trace,
      );
      return response;
    } catch (error) {
      logger.log(
        "ERROR",
        CLIENT_EVENT.HTTP_CLIENT_ERROR,
        {
          [ATTR.HTTP_REQUEST_METHOD]: method,
          [ATTR.URL_PATH]: toPath(url),
          [ATTR.ERROR_TYPE]: error instanceof Error ? error.name : "unknown",
        },
        trace,
      );
      throw error;
    }
  };
}

/**
 * URL からパス部分のみを取り出す(クエリ等の高カーディナリティ/機密を避ける)。
 *
 * @param url - 対象URL。
 * @returns パス文字列(解析失敗時は元の文字列)。
 */
function toPath(url: string): string {
  try {
    return new URL(url, "http://placeholder").pathname;
  } catch {
    return url;
  }
}

/**
 * 高精度時刻(ミリ秒)を返す。利用不可なら `Date.now()`。
 *
 * @returns 経過計測用の時刻(ミリ秒)。
 */
function now(): number {
  return typeof performance !== "undefined" ? performance.now() : Date.now();
}
