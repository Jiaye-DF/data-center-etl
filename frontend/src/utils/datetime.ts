// 後端序列化為 naive UTC+8 wall-clock 字串(無 offset),依 02-frontend/04-datetime.md
// 一律純字串切割顯示;禁 new Date(...) / Intl timeZone(非 +8 瀏覽器會雙偏移)
const DATETIME_RE = /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})/

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const m = iso.match(DATETIME_RE)
  return m ? `${m[1]}/${m[2]}/${m[3]} ${m[4]}:${m[5]}:${m[6]}` : iso
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})/)
  return m ? `${m[1]}/${m[2]}/${m[3]}` : iso
}

export function formatTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const m = iso.match(DATETIME_RE)
  return m ? `${m[4]}:${m[5]}:${m[6]}` : iso
}

/** 可為 null 的時間顯示(started_at / finished_at 等) */
export function formatNullableDateTime(iso: string | null): string {
  return iso === null ? '—' : formatDateTime(iso)
}
