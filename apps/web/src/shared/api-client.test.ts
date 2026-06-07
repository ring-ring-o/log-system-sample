/**
 * API クライアントのテスト。
 *
 * Problem Details の解析(安定コード・trace_id の例外への反映)と、エラー時の
 * クライアントログ付与({@link ../../../../docs/observability/logging-spec.md} §5.2)を固定する。
 */

import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, createApiClient } from "./api-client";

// クライアントロガーをモックし、エラー記録の属性を検証する。
const { loggerMock } = vi.hoisted(() => ({
  loggerMock: {
    error: vi.fn(),
    warn: vi.fn(),
    info: vi.fn(),
    debug: vi.fn(),
    log: vi.fn(),
  },
}));

vi.mock("./observability", () => ({
  getClientLogger: () => loggerMock,
}));

/**
 * 指定の応答を返す global fetch を仕込む。
 *
 * @param response - 返す応答。
 */
function stubFetch(response: Response): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => response),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

describe("createApiClient", () => {
  it("エラー応答(Problem Details)を ApiError に反映する", async () => {
    stubFetch(
      new Response(
        JSON.stringify({
          code: "RES.NOT_FOUND",
          title: "リソースが見つかりません",
          detail: "note が見つかりません",
          trace_id: "trace-123",
        }),
        { status: 404, headers: { "content-type": "application/problem+json" } },
      ),
    );
    const api = createApiClient(() => "token");

    const error = await api.listNotes().catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    const apiError = error as ApiError;
    expect(apiError.status).toBe(404);
    expect(apiError.code).toBe("RES.NOT_FOUND");
    expect(apiError.title).toBe("リソースが見つかりません");
    expect(apiError.traceId).toBe("trace-123");
  });

  it("エラーを安定コード・trace_id 付きでクライアントログに記録する", async () => {
    stubFetch(
      new Response(JSON.stringify({ code: "AUTH.UNAUTHORIZED", trace_id: "t-9" }), {
        status: 401,
        headers: { "content-type": "application/problem+json" },
      }),
    );
    const api = createApiClient(() => undefined);

    await api.listNotes().catch(() => undefined);

    expect(loggerMock.error).toHaveBeenCalledWith(
      "web.api.error",
      expect.objectContaining({
        "flownote.error.code": "AUTH.UNAUTHORIZED",
        "http.response.status_code": 401,
        "url.path": "/api/notes",
        "flownote.error.trace_id": "t-9",
      }),
    );
  });

  it("Problem Details が無い応答でも status だけで ApiError を投げる", async () => {
    stubFetch(new Response("oops", { status: 500, headers: { "content-type": "text/plain" } }));
    const api = createApiClient(() => "token");

    const error = await api.listNotes().catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    const apiError = error as ApiError;
    expect(apiError.status).toBe(500);
    expect(apiError.code).toBeNull();
  });
});
