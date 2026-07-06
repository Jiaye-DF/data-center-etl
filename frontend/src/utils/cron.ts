// 排程友善設定 ↔ cron 字串雙向轉換(時間一律 UTC+8,對齊 00-overview/05-timezone.md)
// cron 欄位順序:分 時 日 月 週;本專案僅支援 每日 / 每週 / 每月 三型,月份欄一律 *

export type CronFrequency = 'daily' | 'weekly' | 'monthly'

export type FriendlySchedule =
  | { freq: 'daily'; hour: number; minute: number }
  | { freq: 'weekly'; hour: number; minute: number; weekday: number }
  | { freq: 'monthly'; hour: number; minute: number; dayOfMonth: number }

export const DEFAULT_FRIENDLY_SCHEDULE: FriendlySchedule = {
  freq: 'daily',
  hour: 3,
  minute: 0,
}

function pad2(value: number): string {
  return value.toString().padStart(2, '0')
}

export function toCron(friendly: FriendlySchedule): string {
  const { hour, minute } = friendly
  switch (friendly.freq) {
    case 'daily':
      return `${minute} ${hour} * * *`
    case 'weekly':
      return `${minute} ${hour} * * ${friendly.weekday}`
    case 'monthly':
      return `${minute} ${hour} ${friendly.dayOfMonth} * *`
  }
}

export const DEFAULT_CRON_EXPR = toCron(DEFAULT_FRIENDLY_SCHEDULE)

function parseField(raw: string, min: number, max: number): number | null {
  if (!/^\d+$/.test(raw)) return null
  const value = Number.parseInt(raw, 10)
  return value >= min && value <= max ? value : null
}

/** 無法解析(自訂 cron,如每 5 分鐘一次)回傳 null,呼叫端落「進階」原始欄 */
export function fromCron(cronExpr: string): FriendlySchedule | null {
  const parts = cronExpr.trim().split(/\s+/)
  if (parts.length !== 5) return null

  const minutePart = parts[0]
  const hourPart = parts[1]
  const dayPart = parts[2]
  const monthPart = parts[3]
  const weekdayPart = parts[4]
  if (
    minutePart === undefined ||
    hourPart === undefined ||
    dayPart === undefined ||
    monthPart === undefined ||
    weekdayPart === undefined
  ) {
    return null
  }
  if (monthPart !== '*') return null

  const minute = parseField(minutePart, 0, 59)
  const hour = parseField(hourPart, 0, 23)
  if (minute === null || hour === null) return null

  if (dayPart === '*' && weekdayPart === '*') {
    return { freq: 'daily', hour, minute }
  }
  if (dayPart === '*' && weekdayPart !== '*') {
    const weekday = parseField(weekdayPart, 0, 6)
    if (weekday === null) return null
    return { freq: 'weekly', hour, minute, weekday }
  }
  if (dayPart !== '*' && weekdayPart === '*') {
    const dayOfMonth = parseField(dayPart, 1, 31)
    if (dayOfMonth === null) return null
    return { freq: 'monthly', hour, minute, dayOfMonth }
  }
  return null
}

const WEEKDAY_LABELS: Record<number, string> = {
  0: '週日',
  1: '週一',
  2: '週二',
  3: '週三',
  4: '週四',
  5: '週五',
  6: '週六',
}

/** 人類可讀摘要,如「每天 03:30」/「每週一 09:00」/「每月 1 號 00:00」 */
export function describeFriendly(friendly: FriendlySchedule): string {
  const time = `${pad2(friendly.hour)}:${pad2(friendly.minute)}`
  switch (friendly.freq) {
    case 'daily':
      return `每天 ${time}`
    case 'weekly':
      return `每${WEEKDAY_LABELS[friendly.weekday] ?? '週'} ${time}`
    case 'monthly':
      return `每月 ${friendly.dayOfMonth} 號 ${time}`
  }
}
