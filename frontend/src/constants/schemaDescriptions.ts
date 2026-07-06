/** schema → 說明文字對照;瀏覽頁 schema 分頁籤附說明用,避免只顯示裸代碼 */
const SCHEMA_DESCRIPTIONS: Record<string, string> = {
  DS: 'ERP 資料字典(表名 / 欄位中文說明,業務資料名稱由此轉譯)',
  M2201: '業務資料(ERP 交易單據明細)',
}

const DEFAULT_SCHEMA_DESCRIPTION = '此 schema 尚無說明文字,以原始代碼顯示'

/** 未知 schema 一律回預設說明,不留空 */
export function getSchemaDescription(schema: string): string {
  return SCHEMA_DESCRIPTIONS[schema] ?? DEFAULT_SCHEMA_DESCRIPTION
}
