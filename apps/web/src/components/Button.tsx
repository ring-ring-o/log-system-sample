/**
 * ボタン(UIプリミティブ)。
 *
 * 生値を直書きせず、デザイントークン(semantic 層)のみを参照する
 * (規約: .claude/skills/design-tokens/SKILL.md)。
 */

import type { ButtonHTMLAttributes, CSSProperties } from "react";

import { color, font, radius, space } from "@/tokens/tokens";

/** ボタンの意図(見た目の役割)。 */
export type ButtonIntent = "primary" | "secondary";

/** ボタンの props。 */
export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** 見た目の役割(既定 primary)。 */
  intent?: ButtonIntent;
}

/**
 * トークンに基づくスタイルを組み立てる。
 *
 * @param intent - ボタンの意図。
 * @returns インラインスタイル。
 */
function styleFor(intent: ButtonIntent): CSSProperties {
  const base: CSSProperties = {
    padding: `${space[2]} ${space[4]}`,
    borderRadius: radius.sm,
    fontSize: font.sizeBody,
    fontWeight: font.weightBold,
    cursor: "pointer",
    border: `1px solid ${color.borderDefault}`,
  };
  if (intent === "primary") {
    return {
      ...base,
      background: color.primaryBg,
      color: color.primaryFg,
      borderColor: color.primaryBg,
    };
  }
  return { ...base, background: color.bgDefault, color: color.textDefault };
}

/**
 * ボタン。
 *
 * @param props - ボタン props。
 * @returns ボタン要素。
 */
export function Button({ intent = "primary", style, ...rest }: ButtonProps) {
  return <button type="button" style={{ ...styleFor(intent), ...style }} {...rest} />;
}
