/**
 * 機密情報のマスキング(ブラウザ側)。
 *
 * バックエンドの {@link ../../../docs/observability/redaction-policy.md} と同じ方針で、
 * 送出前に機密キー・機密値パターンを不可逆にマスクする。
 */

const MASK = "***";

/** 値ごとマスクするキー(小文字・部分一致)。 */
const SENSITIVE_KEY_PARTS: readonly string[] = [
  "password",
  "passwd",
  "secret",
  "token",
  "authorization",
  "api_key",
  "apikey",
  "client_secret",
  "cookie",
  "private_key",
  "credential",
  "session",
  "otp",
];

/** 値の中身に対するマスクパターン。 */
const VALUE_PATTERNS: readonly { pattern: RegExp; replacement: string }[] = [
  { pattern: /eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g, replacement: "***JWT***" },
  { pattern: /bearer\s+[A-Za-z0-9._-]+/gi, replacement: "Bearer ***" },
  { pattern: /sk-[A-Za-z0-9]{16,}/g, replacement: MASK },
  { pattern: /[\w.+-]+@[\w-]+\.[\w.-]+/g, replacement: "***@***" },
];

/** 再帰の暴走を防ぐ深さ上限。 */
const MAX_DEPTH = 12;

/**
 * キー名が機密語を含むか判定する。
 *
 * @param key - 属性キー名。
 * @returns 機密語を部分一致で含めば true。
 */
function isSensitiveKey(key: string): boolean {
  const lowered = key.toLowerCase();
  return SENSITIVE_KEY_PARTS.some((part) => lowered.includes(part));
}

/**
 * 文字列値に含まれる機密パターンをマスクする。
 *
 * @param value - 元の文字列。
 * @returns マスク適用後の文字列。
 */
function redactString(value: string): string {
  let result = value;
  for (const { pattern, replacement } of VALUE_PATTERNS) {
    result = result.replace(pattern, replacement);
  }
  return result;
}

/**
 * 任意の値を再帰的にマスクする。
 *
 * @param value - マスク対象の値。
 * @param depth - 内部用の再帰深さ(呼び出し側は指定しない)。
 * @returns マスク適用後の同型の値。
 */
export function redact(value: unknown, depth = 0): unknown {
  if (depth > MAX_DEPTH) return MASK;
  if (typeof value === "string") return redactString(value);
  if (Array.isArray(value)) return value.map((item) => redact(item, depth + 1));
  if (value !== null && typeof value === "object") {
    const result: Record<string, unknown> = {};
    for (const [key, item] of Object.entries(value as Record<string, unknown>)) {
      result[key] = isSensitiveKey(key) ? MASK : redact(item, depth + 1);
    }
    return result;
  }
  return value;
}
