/**
 * クライアント可観測性のシングルトン。
 *
 * 共有パッケージ @flownote/observability-web を初期化する。OTLP エンドポイント未設定時は
 * コンソールへ出力するフォールバック sink を用い、開発を止めない。
 */

import {
  type ClientLogRecord,
  ClientLogger,
  createBeaconSink,
  getPageTrace,
} from "@flownote/observability-web";

let cached: ClientLogger | null = null;

/**
 * コンソール出力のフォールバック sink。
 *
 * @param record - 整形済みログレコード。
 */
function consoleSink(record: ClientLogRecord): void {
  // 開発時の確認用。構造化レコードをそのまま出す(収集先が無い場合のフォールバック)。
  // biome-ignore lint/suspicious/noConsole: 収集先未設定時の開発用フォールバック sink
  console.debug(JSON.stringify(record));
}

/**
 * クライアントロガー(シングルトン)を取得する。
 *
 * @returns 構成済みの {@link ClientLogger}。
 */
export function getClientLogger(): ClientLogger {
  if (cached) return cached;
  const endpoint = process.env.NEXT_PUBLIC_OTLP_ENDPOINT;
  cached = new ClientLogger({
    resource: {
      serviceName: "flownote-web",
      serviceVersion: "0.1.0",
      environment: process.env.NEXT_PUBLIC_DEPLOYMENT_ENV ?? "local",
    },
    // 収集先があれば OTLP(ログ)へ、無ければコンソールへ。
    sink: endpoint ? createBeaconSink(`${endpoint}/v1/logs`) : consoleSink,
    // ページトレースに相関させ、ログ↔トレースを結びつける([frontend-logging] §3)。
    getTrace: () => getPageTrace(),
  });
  return cached;
}
