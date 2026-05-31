"use client";

/**
 * クライアント共通プロバイダ。
 *
 * 認証セッションを供給し、可観測性(Web Vitals 収集・グローバルエラーハンドラ)を初期化する
 * ([frontend-logging](../../../../docs/observability/frontend-logging.md))。
 */

import {
  registerGlobalErrorHandlers,
  reportWebVitals,
  startPageTrace,
} from "@flownote/observability-web";
import { SessionProvider } from "next-auth/react";
import { type ReactNode, useEffect } from "react";

import { getClientLogger } from "@/shared/observability";

/**
 * アプリ全体を包むプロバイダ。
 *
 * @param props - 子要素。
 * @returns プロバイダ要素。
 */
export function Providers({ children }: { children: ReactNode }) {
  useEffect(() => {
    // ページ単位のルートトレースを開始し、以降のログ・fetch を同一 trace に束ねる。
    startPageTrace();
    const logger = getClientLogger();
    reportWebVitals(logger);
    logger.info("web.app.mounted");
    // 未捕捉エラーを記録し、アンマウント時に解除する。
    return registerGlobalErrorHandlers(logger);
  }, []);

  return <SessionProvider>{children}</SessionProvider>;
}
