'use client'

import { memo } from 'react'

/** run / 逐表 log 狀態顯示字樣(聯集兩層狀態值) */
const STATUS_LABELS: Record<string, string> = {
  pending: '等待中',
  running: '執行中',
  success: '成功',
  failed: '失敗',
  skipped: '略過',
}

const STATUS_CLASSES: Record<string, string> = {
  pending: 'bg-muted text-muted-foreground',
  running: 'bg-info/15 text-info',
  success: 'bg-success/15 text-success',
  failed: 'bg-danger/15 text-danger',
  skipped: 'bg-warning/15 text-warning',
}

interface StatusBadgeProps {
  status: string
}

export const StatusBadge = memo(function StatusBadge({
  status,
}: StatusBadgeProps): React.ReactNode {
  const label = STATUS_LABELS[status] ?? status
  const badgeClass = STATUS_CLASSES[status] ?? 'bg-muted text-muted-foreground'
  return <span className={`df-badge ${badgeClass}`}>{label}</span>
})
