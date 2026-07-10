// 排程友善設定 ↔ cron 字串雙向轉換(時間一律 UTC+8,對齊 00-overview/05-timezone.md)
// cron 欄位順序:分 時 日 月 週;支援 每N分鐘 / 每N小時 / 每日 / 每週 / 每月 五型,月份欄一律 *

export type CronFrequency = 'everyMinutes' | 'everyHours' | 'daily' | 'weekly' | 'monthly'

export type FriendlySchedule =
  | { freq: 'everyMinutes'; everyN: number }
  | { freq: 'everyHours'; everyN: number; minute: number }
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
  switch (friendly.freq) {
    case 'everyMinutes':
      return `${friendly.everyN === 1 ? '*' : `*/${friendly.everyN}`} * * * *`
    case 'everyHours':
      return `${friendly.minute} ${friendly.everyN === 1 ? '*' : `*/${friendly.everyN}`} * * *`
    case 'daily':
      return `${friendly.minute} ${friendly.hour} * * *`
    case 'weekly':
      return `${friendly.minute} ${friendly.hour} * * ${friendly.weekday}`
    case 'monthly':
      return `${friendly.minute} ${friendly.hour} ${friendly.dayOfMonth} * *`
  }
}

export const DEFAULT_CRON_EXPR = toCron(DEFAULT_FRIENDLY_SCHEDULE)

function parseField(raw: string, min: number, max: number): number | null {
  if (!/^\d+$/.test(raw)) return null
  const value = Number.parseInt(raw, 10)
  return value >= min && value <= max ? value : null
}

// 解析步進欄位:`*` 回 1、星號斜線 N 回 N(超界回 null),其餘(固定值 / 清單 / 範圍)回 null
function parseStep(raw: string, max: number): number | null {
  if (raw === '*') return 1
  const match = /^\*\/(\d+)$/.exec(raw)
  if (match === null || match[1] === undefined) return null
  const value = Number.parseInt(match[1], 10)
  return value >= 1 && value <= max ? value : null
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

  // 週期式(日 / 月 / 週皆 * 才成立):分欄步進 → 每N分鐘;分固定 + 時欄步進 → 每N小時
  if (dayPart === '*' && weekdayPart === '*') {
    const minuteStep = parseStep(minutePart, 59)
    if (minuteStep !== null && hourPart === '*') {
      return { freq: 'everyMinutes', everyN: minuteStep }
    }
    const fixedMinute = parseField(minutePart, 0, 59)
    const hourStep = parseStep(hourPart, 23)
    if (fixedMinute !== null && hourStep !== null) {
      return { freq: 'everyHours', everyN: hourStep, minute: fixedMinute }
    }
  }

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

/** 人類可讀摘要,如「每 30 分鐘」/「每 2 小時的第 15 分」/「每天 03:30」/「每週一 09:00」 */
export function describeFriendly(friendly: FriendlySchedule): string {
  switch (friendly.freq) {
    case 'everyMinutes':
      return friendly.everyN === 1 ? '每分鐘' : `每 ${friendly.everyN} 分鐘`
    case 'everyHours':
      return friendly.everyN === 1
        ? `每小時的第 ${friendly.minute} 分`
        : `每 ${friendly.everyN} 小時的第 ${friendly.minute} 分`
    case 'daily':
      return `每天 ${pad2(friendly.hour)}:${pad2(friendly.minute)}`
    case 'weekly':
      return `每${WEEKDAY_LABELS[friendly.weekday] ?? '週'} ${pad2(friendly.hour)}:${pad2(friendly.minute)}`
    case 'monthly':
      return `每月 ${friendly.dayOfMonth} 號 ${pad2(friendly.hour)}:${pad2(friendly.minute)}`
  }
}

/** 排程摘要:可解析 → describeFriendly;自訂 cron → 回原始字串 */
export function describeCron(cronExpr: string): string {
  const friendly = fromCron(cronExpr)
  return friendly === null ? cronExpr : describeFriendly(friendly)
}

/** 該年月(0-based month)的天數 */
function daysInMonth(year: number, monthIndex: number): number {
  return new Date(year, monthIndex + 1, 0).getDate()
}

/**
 * 推算 from 之後最近一次執行(使用者本地時間近似;UTC+8 語意由後端 cron 定義)。
 * 無法解析的自訂 cron 回 null。
 */
export function nextRunFromCron(
  cronExpr: string,
  from: Date = new Date(),
): Date | null {
  const friendly = fromCron(cronExpr)
  if (friendly === null) return null

  switch (friendly.freq) {
    case 'everyMinutes': {
      // cron `*/N` = 每小時第 0, N, 2N… 分;自下一分鐘起找最近符合者(跨時自然歸 0)
      const candidate = new Date(from)
      candidate.setSeconds(0, 0)
      do {
        candidate.setMinutes(candidate.getMinutes() + 1)
      } while (candidate.getMinutes() % friendly.everyN !== 0)
      return candidate
    }
    case 'everyHours': {
      // cron `M */N` = 第 0, N, 2N… 點的第 M 分
      const candidate = new Date(from)
      candidate.setMinutes(friendly.minute, 0, 0)
      while (
        candidate.getTime() <= from.getTime() ||
        candidate.getHours() % friendly.everyN !== 0
      ) {
        candidate.setHours(candidate.getHours() + 1)
      }
      return candidate
    }
    case 'daily': {
      const candidate = new Date(
        from.getFullYear(),
        from.getMonth(),
        from.getDate(),
        friendly.hour,
        friendly.minute,
        0,
        0,
      )
      if (candidate.getTime() <= from.getTime()) {
        candidate.setDate(candidate.getDate() + 1)
      }
      return candidate
    }
    case 'weekly': {
      const diff = (friendly.weekday - from.getDay() + 7) % 7
      const candidate = new Date(
        from.getFullYear(),
        from.getMonth(),
        from.getDate() + diff,
        friendly.hour,
        friendly.minute,
        0,
        0,
      )
      if (candidate.getTime() <= from.getTime()) {
        candidate.setDate(candidate.getDate() + 7)
      }
      return candidate
    }
    case 'monthly': {
      // 本月起最多找兩個月:超出當月天數 clamp 到最後一天,已過則跳下月
      let year = from.getFullYear()
      let month = from.getMonth()
      for (let i = 0; i < 2; i += 1) {
        const day = Math.min(friendly.dayOfMonth, daysInMonth(year, month))
        const candidate = new Date(year, month, day, friendly.hour, friendly.minute, 0, 0)
        if (candidate.getTime() > from.getTime()) return candidate
        month += 1
        if (month > 11) {
          month = 0
          year += 1
        }
      }
      return null
    }
  }
}
