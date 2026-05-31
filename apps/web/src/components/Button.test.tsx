/**
 * Button コンポーネントのテスト。
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Button } from "@/components/Button";

describe("Button", () => {
  it("ラベルを表示する", () => {
    render(<Button>保存</Button>);
    expect(screen.getByRole("button", { name: "保存" })).toBeTruthy();
  });

  it("クリックでハンドラを呼ぶ", () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>実行</Button>);
    screen.getByRole("button", { name: "実行" }).click();
    expect(onClick).toHaveBeenCalledOnce();
  });
});
