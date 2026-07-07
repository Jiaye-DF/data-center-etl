'use client'

import { useCallback, useEffect, useState } from 'react'
import { CronFriendlyPicker } from '@/components/schedules/CronFriendlyPicker'
import { DEFAULT_CRON_EXPR } from '@/utils/cron'
import type { Schedule, ScheduleCreatePayload } from '@/lib/api/scheduleApi'

interface ScheduleFormDialogProps {
  open: boolean
  /** null = 新增模式 */
  initial: Schedule | null
  submitting: boolean
  submitError: string | null
  onSubmit: (payload: ScheduleCreatePayload) => void
  onCancel: () => void
}

/** 排程新增 / 編輯彈窗:遮罩 + 置中卡片;Esc / 點遮罩 / 取消皆關閉。 */
export function ScheduleFormDialog({
  open,
  initial,
  submitting,
  submitError,
  onSubmit,
  onCancel,
}: ScheduleFormDialogProps): React.ReactNode {
  const [name, setName] = useState(initial?.name ?? '')
  const [cronExpr, setCronExpr] = useState(initial?.cron_expr ?? DEFAULT_CRON_EXPR)
  const [description, setDescription] = useState(initial?.description ?? '')
  const [isEnabled, setIsEnabled] = useState(initial?.is_enabled ?? true)

  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent): void => {
      if (event.key === 'Escape') onCancel()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onCancel])

  const handleNameChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>): void => {
      setName(event.target.value)
    },
    [],
  )
  const handleDescriptionChange = useCallback(
    (event: React.ChangeEvent<HTMLTextAreaElement>): void => {
      setDescription(event.target.value)
    },
    [],
  )
  const handleEnabledChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>): void => {
      setIsEnabled(event.target.checked)
    },
    [],
  )

  const handleSubmit = useCallback(
    (event: React.FormEvent<HTMLFormElement>): void => {
      event.preventDefault()
      onSubmit({
        name: name.trim(),
        cron_expr: cronExpr.trim(),
        is_enabled: isEnabled,
        description: description.trim() === '' ? null : description.trim(),
      })
    },
    [onSubmit, name, cronExpr, isEnabled, description],
  )

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        aria-label="關閉對話框"
        onClick={onCancel}
        className="absolute inset-0 cursor-default bg-black/40"
      />
      <form
        onSubmit={handleSubmit}
        role="dialog"
        aria-modal="true"
        aria-labelledby="schedule-form-dialog-title"
        className="df-card relative z-10 flex max-h-[90vh] w-full max-w-xl flex-col gap-4 overflow-y-auto p-6 md:p-8"
      >
        <h2
          id="schedule-form-dialog-title"
          className="text-lg font-bold text-foreground md:text-xl"
        >
          {initial === null ? '新增排程' : `編輯排程:${initial.name}`}
        </h2>

        {submitError !== null ? (
          <p
            role="alert"
            className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger md:text-base"
          >
            {submitError}
          </p>
        ) : null}

        <label className="flex flex-col gap-1.5 text-sm font-medium text-foreground md:text-base">
          名稱
          <input
            type="text"
            required
            maxLength={200}
            value={name}
            onChange={handleNameChange}
            className="df-input"
          />
        </label>

        <div className="flex flex-col gap-1.5 text-sm font-medium text-foreground md:text-base">
          執行時間(UTC+8)
          <CronFriendlyPicker value={cronExpr} onChange={setCronExpr} />
        </div>

        <label className="flex flex-col gap-1.5 text-sm font-medium text-foreground md:text-base">
          描述
          <textarea
            value={description}
            onChange={handleDescriptionChange}
            rows={2}
            className="df-input min-h-[44px] py-2"
          />
        </label>

        <p className="rounded-lg bg-muted/60 px-3 py-2 text-sm text-muted-foreground md:text-base">
          此排程將對全部來源表執行增量同步(半夜到點自動)。
        </p>

        {initial === null ? (
          <label className="flex items-center gap-2 text-sm font-medium text-foreground md:text-base">
            <input
              type="checkbox"
              checked={isEnabled}
              onChange={handleEnabledChange}
              className="h-5 w-5 accent-[rgb(var(--primary))]"
            />
            建立後立即啟用
          </label>
        ) : null}

        <div className="mt-1 flex gap-2">
          <button type="submit" disabled={submitting} className="df-btn-primary">
            {initial === null ? '建立' : '儲存'}
          </button>
          <button type="button" onClick={onCancel} className="df-btn-outline">
            取消
          </button>
        </div>
      </form>
    </div>
  )
}
