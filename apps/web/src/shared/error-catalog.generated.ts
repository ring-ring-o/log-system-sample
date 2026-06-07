// 自動生成: `flownote-error-catalog --format ts`。手で編集しない。
// 生成元はバックエンドの SSOT (domain/errors.py + interface/http/error_catalog.py)。

/** クライアントに返りうる安定エラーコード(ドメイン＋境界)。 */
export const ERROR_CODES = [
  "AUTH.UNAUTHORIZED",
  "AUTHZ.DENIED",
  "GEN.INTERNAL",
  "RES.CONFLICT",
  "RES.NOT_FOUND",
  "VAL.INVALID",
  "VAL.REQUEST",
] as const;

/** 安定エラーコードの union 型。 */
export type ErrorCode = (typeof ERROR_CODES)[number];

/** エラーカタログの1項目。 */
export interface ErrorCatalogEntry {
  /** HTTP ステータス。 */
  httpStatus: number;
  /** 発行レイヤ(domain=ドメイン例外 / interface=境界発行)。 */
  origin: "domain" | "interface";
  /** 公開表題。 */
  title: string;
}

/** コード → 定義の対応表。 */
export const ERROR_CATALOG: Record<ErrorCode, ErrorCatalogEntry> = {
  "AUTH.UNAUTHORIZED": { httpStatus: 401, origin: "interface", title: "認証が必要です" },
  "AUTHZ.DENIED": { httpStatus: 403, origin: "domain", title: "権限がありません" },
  "GEN.INTERNAL": { httpStatus: 500, origin: "domain", title: "内部エラーが発生しました" },
  "RES.CONFLICT": { httpStatus: 409, origin: "domain", title: "リソースが競合しています" },
  "RES.NOT_FOUND": { httpStatus: 404, origin: "domain", title: "リソースが見つかりません" },
  "VAL.INVALID": { httpStatus: 422, origin: "domain", title: "入力が不正です" },
  "VAL.REQUEST": { httpStatus: 422, origin: "interface", title: "入力が不正です" },
};
