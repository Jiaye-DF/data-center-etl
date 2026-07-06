'use client'

import { useEffect } from 'react'

interface ConfirmDialogProps {
  open: boolean
  title: string
  confirmLabel: string
  confirmDisabled?: boolean
  tone?: 'primary' | 'danger'
  onConfirm: () => void
  onCancel: () => void
  children: React.ReactNode
}

/** 通用確認對話框:遮罩 + 置中卡片;Esc / 點遮罩 / 取消皆關閉。 */
export function ConfirmDialog({
  open,
  title,
  confirmLabel,
  confirmDisabled = false,
  tone = 'primary',
  onConfirm,
  onCancel,
  children,
}: ConfirmDialogProps): React.ReactNode {
  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent): void => {
      if (event.key === 'Escape') onCancel()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onCancel])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        aria-label="關閉對話框"
        onClick={onCancel}
        className="absolute inset-0 cursor-default bg-black/40"
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        className="df-card relative z-10 flex w-full max-w-xl flex-col gap-5 p-6 md:p-8"
      >
        <h2
          id="confirm-dialog-title"
          className="text-lg font-bold text-foreground md:text-2xl"
        >
          {title}
        </h2>
        <div className="flex flex-col gap-3 text-base text-muted-foreground md:text-lg">
          {children}
        </div>
        <div className="mt-1 flex gap-3">
          <button
            type="button"
            onClick={onCancel}
            className="df-btn-outline min-h-[52px] flex-1 border-2 text-base font-semibold md:text-lg"
          >
            取消
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={confirmDisabled}
            className={`min-h-[52px] flex-1 text-base font-semibold md:text-lg ${
              tone === 'danger' ? 'df-btn-danger' : 'df-btn-primary'
            }`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
