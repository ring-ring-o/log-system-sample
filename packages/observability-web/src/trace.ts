/**
 * W3C Trace Context の生成。
 *
 * フロント→バックの相関のため、フェッチに `traceparent` ヘッダを付与する。ここでは依存を増やさず
 * W3C 準拠の ID とヘッダを自前生成する(本番では完全な OpenTelemetry Web SDK へ差し替え可能。
 * {@link ../../../docs/observability/frontend-logging.md} 参照)。
 */

/** トレース文脈(現在の trace_id/span_id)。 */
export interface TraceContext {
  /** 32桁16進のトレースID。 */
  traceId: string;
  /** 16桁16進のスパンID。 */
  spanId: string;
}

/**
 * 指定バイト長のランダム16進文字列を生成する。
 *
 * @param bytes - バイト数。
 * @returns 16進文字列(長さ = bytes * 2)。
 */
function randomHex(bytes: number): string {
  const buffer = new Uint8Array(bytes);
  crypto.getRandomValues(buffer);
  return Array.from(buffer, (b) => b.toString(16).padStart(2, "0")).join("");
}

/**
 * 新しいトレース文脈を生成する。
 *
 * @returns 新規の {@link TraceContext}。
 */
export function newTraceContext(): TraceContext {
  return { traceId: randomHex(16), spanId: randomHex(8) };
}

/**
 * トレース文脈から W3C `traceparent` ヘッダ値を作る。
 *
 * @param context - トレース文脈。
 * @returns `00-<trace_id>-<span_id>-01` 形式の文字列。
 */
export function buildTraceparent(context: TraceContext): string {
  return `00-${context.traceId}-${context.spanId}-01`;
}
