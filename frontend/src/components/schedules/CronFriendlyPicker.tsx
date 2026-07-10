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

// 間隔可自由輸入,前端限定有效範圍(cron 步進語意:分 1–59、時 1–23)
const MINUTE_STEP_MAX = 59
const HOUR_STEP_MAX = 23

function parseStepInput(raw: string, max: number): number | null {
  if (!/^\d+$/.test(raw.trim())) return null
  const value = Number.parseInt(raw, 10)
  return value >= 1 && value <= max ? value : null
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
  // 間隔輸入框:保留原始輸入字串,僅有效值外流;無效時顯示提示、blur 還原上次有效值
  const [everyNText, setEveryNText] = useState<string>(
    'everyN' in friendly ? String(friendly.everyN) : '',
  )
  // 外部有效值變動(切頻率 / 自進階同步回簡易)時同步輸入框:render 期間依差異更新 state
  const currentEveryN = 'everyN' in friendly ? friendly.everyN : null
  const [prevEveryN, setPrevEveryN] = useState<number | null>(currentEveryN)
  if (currentEveryN !== prevEveryN) {
    setPrevEveryN(currentEveryN)
    if (currentEveryN !== null) {
      setEveryNText(String(currentEveryN))
    }
  }
  const everyNMax = friendly.freq === 'everyHours' ? HOUR_STEP_MAX : MINUTE_STEP_MAX
  const everyNInvalid =
    (friendly.freq === 'everyMinutes' || friendly.freq === 'everyHours') &&
    parseStepInput(everyNText, everyNMax) === null

  const handleEveryNChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>): void => {
      if (friendly.freq !== 'everyMinutes' && friendly.freq !== 'everyHours') return
      const raw = event.target.value
      setEveryNText(raw)
      const max = friendly.freq === 'everyHours' ? HOUR_STEP_MAX : MINUTE_STEP_MAX
      const parsed = parseStepInput(raw, max)
      if (parsed !== null) emitFriendly({ ...friendly, everyN: parsed })
    },
    [friendly, emitFriendly],
  )
  const handleEveryNBlur = useCallback((): void => {
    if (friendly.freq !== 'everyMinutes' && friendly.freq !== 'everyHours') return
    const max = friendly.freq === 'everyHours' ? HOUR_STEP_MAX : MINUTE_STEP_MAX
    if (parseStepInput(everyNText, max) === null) {
      setEveryNText(String(friendly.everyN))
    }
  }, [friendly, everyNText])
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
                間隔(分鐘)
                <input
                  type="number"
                  inputMode="numeric"
                  min={1}
                  max={MINUTE_STEP_MAX}
                  step={1}
                  value={everyNText}
                  onChange={handleEveryNChange}
                  onBlur={handleEveryNBlur}
                  aria-invalid={everyNInvalid}
                  className="df-input"
                />
              </label>
            ) : null}
            {friendly.freq === 'everyHours' ? (
              <>
                <label className="flex flex-col gap-1.5 text-sm font-medium text-foreground md:text-base">
                  間隔(小時)
                  <input
                    type="number"
                    inputMode="numeric"
                    min={1}
                    max={HOUR_STEP_MAX}
                    step={1}
                    value={everyNText}
                    onChange={handleEveryNChange}
                    onBlur={handleEveryNBlur}
                    aria-invalid={everyNInvalid}
                    className="df-input"
                  />
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
          {everyNInvalid ? (
            <p className="text-sm text-danger md:text-base">
              間隔需為 1–{everyNMax} 的整數(
              {friendly.freq === 'everyHours' ? '小時' : '分鐘'})
            </p>
          ) : null}
          {!everyNInvalid && friendly.freq === 'everyMinutes' && 60 % friendly.everyN !== 0 ? (
            <p className="text-sm text-muted-foreground md:text-base">
              注意:60 無法被 {friendly.everyN} 整除,每小時整點會重新對齊起算
            </p>
          ) : null}
          {!everyNInvalid && friendly.freq === 'everyHours' && 24 % friendly.everyN !== 0 ? (
            <p className="text-sm text-muted-foreground md:text-base">
              注意:24 無法被 {friendly.everyN} 整除,每日 0 點會重新對齊起算
            </p>
          ) : null}
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
