/**
 * グローバルエラーハンドラ。
 *
 * 未捕捉例外・未処理 Promise 拒否を ERROR で記録する
 * ({@link ../../../docs/observability/frontend-logging.md} §2)。
 */

import type { ClientLogger } from "./logger";

/**
 * ブラウザのグローバルエラーハンドラを登録する。
 *
 * @param logger - 記録に用いるロガー。
 * @returns 登録解除する関数。
 */
export function registerGlobalErrorHandlers(logger: ClientLogger): () => void {
  const onError = (event: ErrorEvent): void => {
    logger.error("client.unhandled_error", {
      "exception.type": event.error instanceof Error ? event.error.name : "Error",
      "exception.message": event.message,
    });
  };
  const onRejection = (event: PromiseRejectionEvent): void => {
    const reason = event.reason;
    logger.error("client.unhandled_rejection", {
      "exception.type": reason instanceof Error ? reason.name : "UnhandledRejection",
      "exception.message": reason instanceof Error ? reason.message : String(reason),
    });
  };

  window.addEventListener("error", onError);
  window.addEventListener("unhandledrejection", onRejection);
  return () => {
    window.removeEventListener("error", onError);
    window.removeEventListener("unhandledrejection", onRejection);
  };
}
