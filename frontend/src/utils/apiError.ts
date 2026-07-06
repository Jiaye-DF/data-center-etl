/** 從 RTK Query 錯誤物件取後端 detail(400 業務訊息等;禁 any,逐層型別守衛) */
export function extractApiErrorDetail(error: unknown, fallback: string): string {
  if (typeof error === 'object' && error !== null && 'data' in error) {
    const data = (error as { data?: unknown }).data
    if (typeof data === 'object' && data !== null && 'detail' in data) {
      const detail = (data as { detail?: unknown }).detail
      if (typeof detail === 'string' && detail !== '') {
        return detail
      }
    }
  }
  return fallback
}
