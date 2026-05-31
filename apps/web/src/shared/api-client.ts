/**
 * バックエンド API クライアント。
 *
 * 計装済み fetch(traceparent 付与 + アクセスログ)を用い、認証トークンを付与する。
 * これによりフロント操作からバックエンドまで同一 `trace_id` で追跡できる。
 */

import { createInstrumentedFetch } from "@flownote/observability-web";

import { getClientLogger } from "./observability";

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

/** API エラー。 */
export class ApiError extends Error {
  /**
   * @param status - HTTP ステータスコード。
   */
  constructor(public readonly status: number) {
    super(`API エラー: ${status}`);
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
    if (!response.ok) throw new ApiError(response.status);
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
