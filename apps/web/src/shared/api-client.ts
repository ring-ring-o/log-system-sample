/**
 * バックエンド API クライアント。
 *
 * 計装済み fetch(traceparent 付与 + アクセスログ)を用い、認証トークンを付与する。
 * これによりフロント操作からバックエンドまで同一 `trace_id` で追跡できる。
 */

import { createInstrumentedFetch, parseProblemDetails } from "@flownote/observability-web";

import type { ErrorCode } from "./error-catalog.generated";
import { getClientLogger } from "./observability";

/**
 * API エラーの安定コード。バックエンド SSOT から生成した {@link ErrorCode} を既知値とし、
 * 未知のコード(将来の追加・想定外)も受けられるよう任意文字列も許容する。
 */
export type ApiErrorCode = ErrorCode | (string & {});

/** メモの DTO。 */
export interface Note {
  id: string;
  title: string;
  body: string;
  created_at: string;
  updated_at: string;
}

/** 統合検索のヒット。 */
export interface SearchHit {
  kind: string;
  id: string;
  title: string;
  score: number;
  snippet: string;
}

/**
 * API エラー。RFC 9457 Problem Details の公開フィールドを保持する。
 *
 * 呼び出し側は可変メッセージではなく安定 `code` で分岐し、`traceId` をサポート連携に使える
 * ({@link ../../../../docs/observability/logging-spec.md} §5.2)。
 */
export class ApiError extends Error {
  /**
   * @param status - HTTP ステータスコード。
   * @param code - 安定エラーコード(応答に含まれない場合は `null`)。
   * @param title - 公開表題(応答に含まれない場合は `null`)。
   * @param detail - 公開詳細(応答に含まれない場合は `null`)。
   * @param traceId - 相関トレースID(応答に含まれない場合は `null`)。
   */
  constructor(
    public readonly status: number,
    public readonly code: ApiErrorCode | null = null,
    public readonly title: string | null = null,
    public readonly detail: string | null = null,
    public readonly traceId: string | null = null,
  ) {
    super(title ?? `API エラー: ${status}`);
    this.name = "ApiError";
  }
}

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

/**
 * 認証トークンを供給する関数を受け取り、API クライアントを生成する。
 *
 * @param getToken - アクセストークンを返す関数(未認証なら undefined)。
 * @returns 各エンドポイントを呼ぶメソッド群。
 */
export function createApiClient(getToken: () => string | undefined) {
  const instrumentedFetch = createInstrumentedFetch(getClientLogger());

  /**
   * 認証ヘッダと計装付きで API を呼ぶ。
   *
   * @param path - API パス。
   * @param init - fetch オプション。
   * @returns 応答。
   * @throws ApiError 4xx/5xx 応答時。
   */
  async function request(path: string, init?: RequestInit): Promise<Response> {
    const token = getToken();
    const headers = new Headers(init?.headers);
    headers.set("content-type", "application/json");
    if (token) headers.set("authorization", `Bearer ${token}`);
    const response = await instrumentedFetch(`${BASE_URL}${path}`, { ...init, headers });
    if (!response.ok) {
      // エラー応答(Problem Details)から安定コード・trace_id を取り出して例外へ載せる。
      const problem = await parseProblemDetails(response);
      const error = new ApiError(
        response.status,
        problem?.code ?? null,
        problem?.title ?? null,
        problem?.detail ?? null,
        problem?.trace_id ?? null,
      );
      // クライアント側でもエラーを安定コードで識別・相関できるよう1件記録する。
      // span 粒度の相関は http.client.request(計装 fetch)が担保するため、ここは
      // ページトレースの trace_id 相関で足りる。属性は値があるときだけ付与する。
      const attributes: Record<string, unknown> = {
        "http.response.status_code": error.status,
        "url.path": path,
      };
      if (error.code) attributes["flownote.error.code"] = error.code;
      if (error.traceId) attributes["flownote.error.trace_id"] = error.traceId;
      getClientLogger().error("web.api.error", attributes);
      throw error;
    }
    return response;
  }

  return {
    /**
     * メモ一覧を取得する。
     * @returns メモ配列。
     */
    async listNotes(): Promise<Note[]> {
      const response = await request("/api/notes");
      return (await response.json()) as Note[];
    },
    /**
     * メモを作成する。
     * @param input - タイトルと本文。
     * @returns 作成されたメモ。
     */
    async createNote(input: { title: string; body: string }): Promise<Note> {
      const response = await request("/api/notes", {
        method: "POST",
        body: JSON.stringify(input),
      });
      return (await response.json()) as Note;
    },
    /**
     * 統合検索を行う。
     * @param query - 検索クエリ。
     * @returns ヒット配列。
     */
    async search(query: string): Promise<SearchHit[]> {
      const response = await request("/api/ai/search", {
        method: "POST",
        body: JSON.stringify({ query }),
      });
      const data = (await response.json()) as { hits: SearchHit[] };
      return data.hits;
    },
  };
}
