/**
 * 共有テレメトリ語彙(生成物 ATTR)と FE ローカル定数の契約テスト。
 *
 * 「一意の意図と意味をテストで固定する」方針に従い、属性キーをピン留めする。特に
 * ドリフトを起こしていた `deployment.environment` の回帰防止と、サーバ計測キーとの区別を固定する。
 */

import { describe, expect, it } from "vitest";

import { ATTR, CLIENT_ATTR, CLIENT_EVENT, CONTENT_TYPE, HEADER } from "../src/index";

describe("共有属性キー(ATTR・BE 生成)", () => {
  it("リソース環境キーは OTel Stable rename 後の値で固定(ドリフト回帰防止)", () => {
    expect(ATTR.DEPLOYMENT_ENVIRONMENT).toBe("deployment.environment.name");
    expect(ATTR.SERVICE_NAME).toBe("service.name");
  });

  it("HTTP/エラー属性キーを固定", () => {
    expect(ATTR.HTTP_REQUEST_METHOD).toBe("http.request.method");
    expect(ATTR.HTTP_RESPONSE_STATUS_CODE).toBe("http.response.status_code");
    expect(ATTR.URL_PATH).toBe("url.path");
    expect(ATTR.FLOWNOTE_ERROR_CODE).toBe("flownote.error.code");
  });
});

describe("FE ローカル定数(client.* 等)", () => {
  it("クライアント計測キーはサーバ計測とは別概念であること", () => {
    // FE は client、BE は server。両者を同一にしない(意図の区別)。
    expect(CLIENT_ATTR.HTTP_CLIENT_REQUEST_DURATION).toBe("http.client.request.duration");
    expect(CLIENT_ATTR.HTTP_CLIENT_REQUEST_DURATION).not.toBe("http.server.request.duration");
  });

  it("ライブラリのイベント名・ヘッダ・MIME を固定", () => {
    expect(CLIENT_EVENT.HTTP_CLIENT_REQUEST).toBe("http.client.request");
    expect(HEADER.CONTENT_TYPE).toBe("content-type");
    expect(CONTENT_TYPE.PROBLEM_JSON).toBe("application/problem+json");
  });
});
