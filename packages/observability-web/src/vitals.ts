/**
 * Web Vitals 収集。
 *
 * 体感品質(LCP/INP/CLS/TTFB/FCP)を構造化ログに記録する
 * ({@link ../../../docs/observability/frontend-logging.md} §2)。
 */

import type { Metric } from "web-vitals";
import { onCLS, onFCP, onINP, onLCP, onTTFB } from "web-vitals";

import { CLIENT_EVENT, VITAL_ATTR } from "./constants";
import type { ClientLogger } from "./logger";

/**
 * Web Vitals の計測を開始し、各指標をロガーに送る。
 *
 * @param logger - 記録に用いるロガー。
 */
export function reportWebVitals(logger: ClientLogger): void {
  const handler = (metric: Metric): void => {
    logger.info(CLIENT_EVENT.WEB_VITAL, {
      [VITAL_ATTR.NAME]: metric.name,
      [VITAL_ATTR.VALUE]: Math.round(metric.value * 1000) / 1000,
      [VITAL_ATTR.RATING]: metric.rating,
    });
  };
  onCLS(handler);
  onFCP(handler);
  onINP(handler);
  onLCP(handler);
  onTTFB(handler);
}
