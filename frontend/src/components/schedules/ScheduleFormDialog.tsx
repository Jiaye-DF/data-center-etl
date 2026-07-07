'use client'

import { useCallback, useEffect, useState } from 'react'
import { CronFriendlyPicker } from '@/components/schedules/CronFriendlyPicker'

/** 編輯排程對話框的初始值(對應某張來源表既有排程) */
export interface ScheduleEditInitial {
  uid: string
  tableName: string
  cronExpr: string
  isEnabled: boolean
  description: string | null
}

/** 送出的更新內容(cron / 啟停 / 描述) */
export interface ScheduleEditPayload {
  cron_expr: string
  is_enabled: boolean
  description: string | null
}

interface ScheduleFormDialogProps {
  open: boolean
  /** 目前編輯中的排程;關閉時為 null */
  initial: ScheduleEditInitial | null
  submitting: boolean
  submitError: string | null
  onSubmit: (payload: ScheduleEditPayload) => void
  onCancel: () => void
}

/** 排程編輯彈窗(edit-only):改 cron / 啟停 / 描述;遮罩 + 置中卡片,Esc / 點遮罩 / 取消皆關閉。 */
export function ScheduleFormDialog({
  open,
  initial,
  submitting,
  submitError,
  onSubmit,
  onCancel,
}: ScheduleFormDialogProps): React.ReactNode {
  const [cronExpr, setCronExpr] = useState(initial?.cronExpr ?? '')
  const [description, setDescription] = useState(initial?.description ?? '')
  const [isEnabled, setIsEnabled] = useState(initial?.isEnabled ?? true)

  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent): void => {
      if (event.key === 'Escape') onCancel()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onCancel])

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
        cron_expr: cronExpr.trim(),
        is_enabled: isEnabled,
        description: description.trim() === '' ? null : description.trim(),
      })
    },
    [onSubmit, cronExpr, isEnabled, description],
  )

  if (!open || initial === null) return null

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
          編輯排程:{initial.tableName}
        </h2>

        {submitError !== null ? (
          <p
            role="alert"
            className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger md:text-base"
          >
            {submitError}
          </p>
        ) : null}

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

        <label className="flex items-center gap-2 text-sm font-medium text-foreground md:text-base">
          <input
            type="checkbox"
            checked={isEnabled}
            onChange={handleEnabledChange}
            className="h-5 w-5 accent-[rgb(var(--primary))]"
          />
          啟用此排程(停用則不派工)
        </label>

        <p className="rounded-lg bg-muted/60 px-3 py-2 text-sm text-muted-foreground md:text-base">
          此排程對該來源表執行增量同步(到點自動)。
        </p>

        <div className="mt-1 flex gap-2">
          <button type="submit" disabled={submitting} className="df-btn-primary">
            儲存
          </button>
          <button type="button" onClick={onCancel} className="df-btn-outline">
            取消
          </button>
        </div>
      </form>
    </div>
  )
}
