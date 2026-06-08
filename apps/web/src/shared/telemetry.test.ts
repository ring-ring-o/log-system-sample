/**
 * フロント固有テレメトリ語彙(web イベント名・アクション・ルート)の契約テスト。
 *
 * 値をピン留めし、BE と「意図的に同値だが別管理」の関係を明示する。
 */

import { describe, expect, it } from "vitest";

import { API_ROUTES } from "./routes.generated";
import { BEARER_PREFIX, DEFAULT_ENV, WEB_ACTION, WEB_ATTR, WEB_EVENT } from "./telemetry";

describe("web テレメトリ語彙", () => {
  it("web イベント名を固定", () => {
    expect(WEB_EVENT.API_ERROR).toBe("web.api.error");
    expect(WEB_EVENT.NOTE_CREATED).toBe("web.note.created");
    expect(WEB_EVENT.SEARCH_EXECUTED).toBe("web.search.executed");
  });

  it("アクション識別子と属性キーを固定", () => {
    expect(WEB_ACTION.CREATE_NOTE).toBe("create_note");
    expect(WEB_ATTR.ACTION).toBe("flownote.web.action");
  });

  it("WEB_ACTION.UNIFIED_SEARCH は BE の AIUseCase と意図的に同値(別管理)", () => {
    // FE のユーザー操作と BE の AI ユースケースは値こそ一致するが、別の意図・別の SSOT。
    expect(WEB_ACTION.UNIFIED_SEARCH).toBe("unified_search");
  });

  it("認可プレフィックスと環境既定を固定", () => {
    expect(BEARER_PREFIX).toBe("Bearer ");
    expect(DEFAULT_ENV).toBe("local");
  });
});

describe("生成ルート(BE SSOT と一致)", () => {
  it("フロントが叩くフルパスを固定", () => {
    expect(API_ROUTES.NOTES).toBe("/api/notes");
    expect(API_ROUTES.AI_SEARCH).toBe("/api/ai/search");
  });
});
