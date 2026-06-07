/**
 * RFC 9457 Problem Details(`application/problem+json`)の解析。
 *
 * バックエンドのエラー応答({@link ../../../docs/observability/logging-spec.md} §5.2)を
 * 安全に取り出すための汎用ヘルパ。標準形式(RFC 9457)に閉じており特定アプリに依存しない。
 * アプリ固有の安定コード集合はフロント側で型付けする(本パッケージはコードを知らない)。
 */

import { CONTENT_TYPE, HEADER } from "./constants";

/** RFC 9457 Problem Details の本文(拡張メンバ `code`/`trace_id` を含む)。 */
export interface ProblemDetails {
  /** エラー種別を識別する URI。 */
  type?: string;
  /** 人間可読の短い表題。 */
  title?: string;
  /** HTTP ステータス。 */
  status?: number;
  /** 安定エラー識別子(拡張メンバ)。 */
  code?: string;
  /** この発生事象の説明。 */
  detail?: string;
  /** 発生事象を指す URI 参照。 */
  instance?: string;
  /** 相関トレースID(拡張メンバ)。サポートでの引き戻しに用いる。 */
  trace_id?: string;
}

/** Problem Details として扱う content-type の判定に使う部分文字列。 */
const PROBLEM_CONTENT_TYPES = [CONTENT_TYPE.PROBLEM_JSON, CONTENT_TYPE.JSON];

/**
 * 応答本文を Problem Details として安全に解析する。
 *
 * 本文を読んでも呼び出し側が再度読めるよう `clone()` してから解析する。content-type が
 * JSON でない、本文が空/不正、オブジェクトでない場合は `null` を返す(失敗で例外を投げない)。
 *
 * @param response - 解析対象の応答。
 * @returns 解析できた場合は {@link ProblemDetails}、できなければ `null`。
 */
export async function parseProblemDetails(response: Response): Promise<ProblemDetails | null> {
  const contentType = response.headers.get(HEADER.CONTENT_TYPE) ?? "";
  if (!PROBLEM_CONTENT_TYPES.some((type) => contentType.includes(type))) {
    return null;
  }
  try {
    const body: unknown = await response.clone().json();
    if (typeof body !== "object" || body === null) {
      return null;
    }
    return body as ProblemDetails;
  } catch {
    // 本文が空/不正 JSON でも観測フローを止めない。
    return null;
  }
}
