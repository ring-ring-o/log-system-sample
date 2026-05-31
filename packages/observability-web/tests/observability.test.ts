/**
 * observability-web のテスト。
 *
 * クライアントログのスキーマ・マスキング・相関・traceparent 付与を固定する
 * ({@link ../../../docs/observability/frontend-logging.md} §8)。
 */

import { describe, expect, it, vi } from "vitest";

import {
  type ClientLogRecord,
  ClientLogger,
  createInstrumentedFetch,
  newTraceContext,
  redact,
} from "../src/index.js";

const RESOURCE = {
  serviceName: "flownote-web",
  serviceVersion: "0.1.0",
  environment: "test",
};

/**
 * 捕捉した記録を蓄積するメモリ sink を作る。
 *
 * @returns records と sink の組。
 */
function memorySink(): { records: ClientLogRecord[]; sink: (r: ClientLogRecord) => void } {
  const records: ClientLogRecord[] = [];
  return { records, sink: (r) => records.push(r) };
}

describe("redact", () => {
  it("機密キーと機密値をマスクする", () => {
    const result = redact({
      Authorization: "Bearer abc.def",
      password: "p",
      note: "mail alice@example.com",
    }) as Record<string, unknown>;
    expect(result.Authorization).toBe("***");
    expect(result.password).toBe("***");
    expect(result.note).toContain("***@***");
  });

  it("redaction-policy §3.1 の必須キーを網羅する", () => {
    const result = redact({
      private_key: "k",
      cookie: "sid=1",
      refresh_token: "r",
      client_secret: "s",
    }) as Record<string, string>;
    expect(result.private_key).toBe("***");
    expect(result.cookie).toBe("***");
    expect(result.refresh_token).toBe("***");
    expect(result.client_secret).toBe("***");
  });

  it("ネストした構造も再帰的にマスクする", () => {
    const result = redact({ outer: { token: "t", items: ["x@y.com"] } }) as {
      outer: { token: string; items: string[] };
    };
    expect(result.outer.token).toBe("***");
    expect(result.outer.items[0]).toBe("***@***");
  });
});

describe("ClientLogger", () => {
  it("スキーマ準拠のレコードを生成する", () => {
    const { records, sink } = memorySink();
    const logger = new ClientLogger({
      resource: RESOURCE,
      sink,
      now: () => "2026-05-31T00:00:00.000Z",
    });
    logger.info("note.saved", { "flownote.note.id": "n1" });

    expect(records).toHaveLength(1);
    const record = records[0]!;
    expect(record.body).toBe("note.saved");
    expect(record.severity_text).toBe("INFO");
    expect(record.severity_number).toBe(9);
    expect(record["service.name"]).toBe("flownote-web");
    expect(record.attributes["flownote.note.id"]).toBe("n1");
  });

  it("送出前に機密属性をマスクする", () => {
    const { records, sink } = memorySink();
    const logger = new ClientLogger({ resource: RESOURCE, sink });
    logger.info("auth", { token: "secret", password: "p" });
    expect(records[0]!.attributes.token).toBe("***");
    expect(records[0]!.attributes.password).toBe("***");
  });

  it("トレース文脈を相関させる", () => {
    const { records, sink } = memorySink();
    const trace = newTraceContext();
    const logger = new ClientLogger({ resource: RESOURCE, sink, getTrace: () => trace });
    logger.info("evt");
    expect(records[0]!.trace_id).toBe(trace.traceId);
    expect(records[0]!.trace_id).toMatch(/^[0-9a-f]{32}$/);
  });
});

describe("createInstrumentedFetch", () => {
  it("traceparent を付与し結果を記録する", async () => {
    const { records, sink } = memorySink();
    const logger = new ClientLogger({ resource: RESOURCE, sink });
    let capturedHeaders: Headers | undefined;
    const fakeFetch = vi.fn(async (_input: string | URL | Request, init?: RequestInit) => {
      capturedHeaders = new Headers(init?.headers);
      return new Response("{}", { status: 200 });
    });

    const instrumented = createInstrumentedFetch(logger, fakeFetch);
    await instrumented("/api/notes", { method: "GET" });

    // traceparent が W3C 形式で付与される。
    const traceparent = capturedHeaders?.get("traceparent") ?? "";
    expect(traceparent).toMatch(/^00-[0-9a-f]{32}-[0-9a-f]{16}-01$/);
    // アクセスログが相関付きで記録される。
    const access = records.find((r) => r.body === "http.client.request");
    expect(access?.attributes["http.response.status_code"]).toBe(200);
    expect(access?.trace_id).toMatch(/^[0-9a-f]{32}$/);
  });

  it("失敗時は ERROR を記録し例外を再送する", async () => {
    const { records, sink } = memorySink();
    const logger = new ClientLogger({ resource: RESOURCE, sink });
    const failing = vi.fn(async () => {
      throw new TypeError("network down");
    });
    const instrumented = createInstrumentedFetch(logger, failing);
    await expect(instrumented("/api/notes")).rejects.toThrow("network down");
    const errorLog = records.find((r) => r.body === "http.client.error");
    expect(errorLog?.severity_text).toBe("ERROR");
    expect(errorLog?.attributes["error.type"]).toBe("TypeError");
  });
});
