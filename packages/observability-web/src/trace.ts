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

// ページ単位のルートトレース。ページ内の操作ログと各 fetch を同一 trace に束ねる。
let pageTrace: TraceContext | null = null;

/**
 * ページ単位のルートトレースを開始する(ページ読み込み時に呼ぶ)。
 *
 * @returns 生成したトレース文脈。
 */
export function startPageTrace(): TraceContext {
  pageTrace = newTraceContext();
  return pageTrace;
}

/**
 * 現在のページトレースを返す(未開始なら null)。
 *
 * @returns ページトレース文脈、または null。
 */
export function getPageTrace(): TraceContext | null {
  return pageTrace;
}

/**
 * 同一トレース内の新しい span 文脈を返す。
 *
 * ページトレースがあれば同じ `traceId` の新しい `spanId`、無ければ新規トレースを生成する。
 * これにより各 fetch がページトレースの子 span となり、フロント→バックが1 trace で繋がる。
 *
 * @returns 子 span の文脈。
 */
export function childTraceContext(): TraceContext {
  if (pageTrace) {
    return { traceId: pageTrace.traceId, spanId: randomHex(8) };
  }
  return newTraceContext();
}
