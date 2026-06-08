/**
 * ブラウザ計装で用いる FE ローカル定数(HTTP/プロトコル・クライアント計測・ライブラリイベント名)。
 *
 * FE/BE で一致が必要な属性キーは生成物 {@link ./semconv} の `ATTR` を参照する。本モジュールには
 * 「ブラウザ側だけが出す値」を置く。特にクライアント計測キー(`http.client.*`)はサーバ計測
 * (`http.server.*`)とは別概念のため、共有 `ATTR` には含めず分離する。
 */

/** HTTP メソッド。 */
export const HTTP_METHOD = {
  GET: "GET",
  POST: "POST",
} as const;

/** HTTP ヘッダ名(小文字正規化)。 */
export const HEADER = {
  CONTENT_TYPE: "content-type",
  AUTHORIZATION: "authorization",
  TRACEPARENT: "traceparent",
} as const;

/** メディアタイプ(MIME)。 */
export const CONTENT_TYPE = {
  JSON: "application/json",
  PROBLEM_JSON: "application/problem+json",
} as const;

/**
 * FE ローカルのテレメトリ属性キー(共有 `ATTR` に含めないブラウザ固有のもの)。
 * `HTTP_CLIENT_REQUEST_DURATION` はサーバ計測の `http.server.request.duration` とは別概念。
 */
export const CLIENT_ATTR = {
  HTTP_CLIENT_REQUEST_DURATION: "http.client.request.duration",
  EXCEPTION_TYPE: "exception.type",
  EXCEPTION_MESSAGE: "exception.message",
} as const;

/** 本ライブラリが発行する低カーディナリティのイベント名(ログ body)。 */
export const CLIENT_EVENT = {
  HTTP_CLIENT_REQUEST: "http.client.request",
  HTTP_CLIENT_ERROR: "http.client.error",
  UNHANDLED_ERROR: "client.unhandled_error",
  UNHANDLED_REJECTION: "client.unhandled_rejection",
  WEB_VITAL: "web.vital",
} as const;

/** Web Vitals(体感品質)の属性キー。 */
export const VITAL_ATTR = {
  NAME: "flownote.web.vital.name",
  VALUE: "flownote.web.vital.value",
  RATING: "flownote.web.vital.rating",
} as const;
