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
  pending: 'bg-gray-100 text-gray-700',
  running: 'bg-blue-50 text-blue-700',
  success: 'bg-green-50 text-green-700',
  failed: 'bg-red-50 text-red-700',
  skipped: 'bg-yellow-50 text-yellow-700',
}

interface StatusBadgeProps {
  status: string
}

export const StatusBadge = memo(function StatusBadge({
  status,
}: StatusBadgeProps): React.ReactNode {
  const label = STATUS_LABELS[status] ?? status
  const badgeClass = STATUS_CLASSES[status] ?? 'bg-gray-100 text-gray-700'
  return (
    <span
      className={`w-fit rounded px-2 py-0.5 text-sm font-medium md:text-base ${badgeClass}`}
    >
      {label}
    </span>
  )
})
