'use client'

import { useCallback, useMemo, useState } from 'react'
import {
  DEFAULT_FRIENDLY_SCHEDULE,
  describeFriendly,
  fromCron,
  toCron,
  type CronFrequency,
  type FriendlySchedule,
} from '@/utils/cron'

const FREQ_OPTIONS: ReadonlyArray<{ value: CronFrequency; label: string }> = [
  { value: 'everyMinutes', label: '每 N 分鐘' },
  { value: 'everyHours', label: '每 N 小時' },
  { value: 'daily', label: '每日' },
  { value: 'weekly', label: '每週' },
  { value: 'monthly', label: '每月' },
]

// 間隔下拉限定常用值,避免 33 分鐘這類難對齊的間隔;既有 cron 帶非清單值時動態納入
const MINUTE_STEP_OPTIONS: readonly number[] = [5, 10, 15, 20, 30]
const HOUR_STEP_OPTIONS: readonly number[] = [1, 2, 3, 4, 6, 8, 12]

function stepOptions(base: readonly number[], current: number): number[] {
  return base.includes(current) ? [...base] : [...base, current].sort((a, b) => a - b)
}

const WEEKDAY_OPTIONS: ReadonlyArray<{ value: number; label: string }> = [
  { value: 0, label: '週日' },
  { value: 1, label: '週一' },
  { value: 2, label: '週二' },
  { value: 3, label: '週三' },
  { value: 4, label: '週四' },
  { value: 5, label: '週五' },
  { value: 6, label: '週六' },
]

const HOUR_OPTIONS: readonly number[] = Array.from({ length: 24 }, (_, hour) => hour)
const MINUTE_OPTIONS: readonly number[] = Array.from({ length: 60 }, (_, minute) => minute)
const DAY_OF_MONTH_OPTIONS: readonly number[] = Array.from(
  { length: 31 },
  (_, index) => index + 1,
)

function pad2(value: number): string {
  return value.toString().padStart(2, '0')
}

/** 切換頻率下拉時,沿用原本時:分,間隔 / 週幾 / 幾號補預設值 */
function withFrequency(current: FriendlySchedule, freq: CronFrequency): FriendlySchedule {
  const hour = 'hour' in current ? current.hour : 3
  const minute = 'minute' in current ? current.minute : 0
  if (freq === 'everyMinutes') {
    return { freq, everyN: current.freq === 'everyMinutes' ? current.everyN : 30 }
  }
  if (freq === 'everyHours') {
    return { freq, everyN: current.freq === 'everyHours' ? current.everyN : 1, minute }
  }
  if (freq === 'weekly') {
    return { freq, hour, minute, weekday: current.freq === 'weekly' ? current.weekday : 0 }
  }
  if (freq === 'monthly') {
    return {
      freq,
      hour,
      minute,
      dayOfMonth: current.freq === 'monthly' ? current.dayOfMonth : 1,
    }
  }
  return { freq, hour, minute }
}

export interface CronFriendlyPickerProps {
  /** 現行 cron 字串(既有 API 契約:分 時 日 月 週) */
  value: string
  onChange: (cronExpr: string) => void
}

export function CronFriendlyPicker({
  value,
  onChange,
}: CronFriendlyPickerProps): React.ReactNode {
  const [mode, setMode] = useState<'friendly' | 'advanced'>(() =>
    value.trim() === '' || fromCron(value) !== null ? 'friendly' : 'advanced',
  )
  const [friendly, setFriendly] = useState<FriendlySchedule>(
    () => fromCron(value) ?? DEFAULT_FRIENDLY_SCHEDULE,
  )
  const [advancedValue, setAdvancedValue] = useState<string>(value)

  const parsedAdvanced = useMemo(
    (): FriendlySchedule | null => fromCron(advancedValue),
    [advancedValue],
  )

  const emitFriendly = useCallback(
    (next: FriendlySchedule): void => {
      setFriendly(next)
      onChange(toCron(next))
    },
    [onChange],
  )

  const handleFreqChange = useCallback(
    (event: React.ChangeEvent<HTMLSelectElement>): void => {
      emitFriendly(withFrequency(friendly, event.target.value as CronFrequency))
    },
    [friendly, emitFriendly],
  )
  const handleHourChange = useCallback(
    (event: React.ChangeEvent<HTMLSelectElement>): void => {
      if (friendly.freq === 'everyMinutes' || friendly.freq === 'everyHours') return
      emitFriendly({ ...friendly, hour: Number.parseInt(event.target.value, 10) })
    },
    [friendly, emitFriendly],
  )
  const handleMinuteChange = useCallback(
    (event: React.ChangeEvent<HTMLSelectElement>): void => {
      if (friendly.freq === 'everyMinutes') return
      emitFriendly({ ...friendly, minute: Number.parseInt(event.target.value, 10) })
    },
    [friendly, emitFriendly],
  )
  const handleEveryNChange = useCallback(
    (event: React.ChangeEvent<HTMLSelectElement>): void => {
      if (friendly.freq !== 'everyMinutes' && friendly.freq !== 'everyHours') return
      emitFriendly({ ...friendly, everyN: Number.parseInt(event.target.value, 10) })
    },
    [friendly, emitFriendly],
  )
  const handleWeekdayChange = useCallback(
    (event: React.ChangeEvent<HTMLSelectElement>): void => {
      if (friendly.freq !== 'weekly') return
      emitFriendly({ ...friendly, weekday: Number.parseInt(event.target.value, 10) })
    },
    [friendly, emitFriendly],
  )
  const handleDayOfMonthChange = useCallback(
    (event: React.ChangeEvent<HTMLSelectElement>): void => {
      if (friendly.freq !== 'monthly') return
      emitFriendly({ ...friendly, dayOfMonth: Number.parseInt(event.target.value, 10) })
    },
    [friendly, emitFriendly],
  )
  const handleAdvancedChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>): void => {
      setAdvancedValue(event.target.value)
      onChange(event.target.value)
    },
    [onChange],
  )
  const handleToggleMode = useCallback((): void => {
    if (mode === 'friendly') {
      setAdvancedValue(toCron(friendly))
      setMode('advanced')
      return
    }
    if (parsedAdvanced !== null) {
      setFriendly(parsedAdvanced)
      onChange(toCron(parsedAdvanced))
      setMode('friendly')
    }
  }, [mode, friendly, parsedAdvanced, onChange])

  return (
    <div className="flex flex-col gap-2">
      {mode === 'friendly' ? (
        <div className="flex flex-col gap-3 rounded-lg border border-border p-3">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <label className="flex flex-col gap-1.5 text-sm font-medium text-foreground md:text-base">
              頻率
              <select value={friendly.freq} onChange={handleFreqChange} className="df-input">
                {FREQ_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            {friendly.freq === 'everyMinutes' ? (
              <label className="flex flex-col gap-1.5 text-sm font-medium text-foreground md:text-base">
                間隔
                <select
                  value={friendly.everyN}
                  onChange={handleEveryNChange}
                  className="df-input"
                >
                  {stepOptions(MINUTE_STEP_OPTIONS, friendly.everyN).map((n) => (
                    <option key={n} value={n}>
                      每 {n} 分鐘
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
            {friendly.freq === 'everyHours' ? (
              <>
                <label className="flex flex-col gap-1.5 text-sm font-medium text-foreground md:text-base">
                  間隔
                  <select
                    value={friendly.everyN}
                    onChange={handleEveryNChange}
                    className="df-input"
                  >
                    {stepOptions(HOUR_STEP_OPTIONS, friendly.everyN).map((n) => (
                      <option key={n} value={n}>
                        每 {n} 小時
                      </option>
                    ))}
                  </select>
                </label>
                <label className="flex flex-col gap-1.5 text-sm font-medium text-foreground md:text-base">
                  第幾分執行
                  <select
                    value={friendly.minute}
                    onChange={handleMinuteChange}
                    className="df-input"
                  >
                    {MINUTE_OPTIONS.map((minute) => (
                      <option key={minute} value={minute}>
                        {pad2(minute)} 分
                      </option>
                    ))}
                  </select>
                </label>
              </>
            ) : null}
            {friendly.freq === 'weekly' ? (
              <label className="flex flex-col gap-1.5 text-sm font-medium text-foreground md:text-base">
                週幾
                <select
                  value={friendly.weekday}
                  onChange={handleWeekdayChange}
                  className="df-input"
                >
                  {WEEKDAY_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
            {friendly.freq === 'monthly' ? (
              <label className="flex flex-col gap-1.5 text-sm font-medium text-foreground md:text-base">
                幾號
                <select
                  value={friendly.dayOfMonth}
                  onChange={handleDayOfMonthChange}
                  className="df-input"
                >
                  {DAY_OF_MONTH_OPTIONS.map((day) => (
                    <option key={day} value={day}>
                      {day} 號
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
            {'hour' in friendly ? (
              <label className="flex flex-col gap-1.5 text-sm font-medium text-foreground md:text-base">
                時間
                <div className="flex items-center gap-1.5">
                  <select value={friendly.hour} onChange={handleHourChange} className="df-input">
                    {HOUR_OPTIONS.map((hour) => (
                      <option key={hour} value={hour}>
                        {pad2(hour)}
                      </option>
                    ))}
                  </select>
                  <span className="text-muted-foreground">:</span>
                  <select
                    value={friendly.minute}
                    onChange={handleMinuteChange}
                    className="df-input"
                  >
                    {MINUTE_OPTIONS.map((minute) => (
                      <option key={minute} value={minute}>
                        {pad2(minute)}
                      </option>
                    ))}
                  </select>
                </div>
              </label>
            ) : null}
          </div>
          <p className="text-sm text-muted-foreground md:text-base">
            {describeFriendly(friendly)}(UTC+8)
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-1.5">
          <input
            type="text"
            required
            maxLength={100}
            value={advancedValue}
            onChange={handleAdvancedChange}
            placeholder="分 時 日 月 週,例:0 2 * * *"
            className="df-input font-mono"
          />
          <p className="text-sm text-muted-foreground md:text-base">
            進階模式:直接輸入原始 cron 運算式(UTC+8)
          </p>
        </div>
      )}
      <button
        type="button"
        onClick={handleToggleMode}
        disabled={mode === 'advanced' && parsedAdvanced === null}
        className="df-btn-outline min-h-[36px] self-start px-3 text-sm"
      >
        {mode === 'friendly' ? '進階(原始 cron)' : '簡易模式'}
      </button>
    </div>
  )
}
