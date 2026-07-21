'use client'

import { useGetActiveRunQuery } from '@/lib/api/runApi'
import { useAuth } from '@/lib/auth/useAuth'
import { TRIGGER_TYPE_LABELS } from '@/constants/labels'

// 視窗未聚焦不輪詢(RTK Query 內建節流,對齊 propose § 執行模型;不做 websocket)
const POLLING_INTERVAL_MS = 5_000

export function SyncProgress(): React.ReactNode {
  const { isAdmin } = useAuth()
  // non-admin 已被 (main)/layout.tsx 導向 /no-access,此處再守一層避免對 403 端點空輪詢
  const { data } = useGetActiveRunQuery(undefined, {
    pollingInterval: POLLING_INTERVAL_MS,
    skipPollingIfUnfocused: true,
    skip: !isAdmin,
  })

  if (data === null || data === undefined) {
    return null
  }

  const percent =
    data.total_tables === 0
      ? 0
      : Math.min(
          100,
          Math.round((data.processed_tables / data.total_tables) * 100),
        )
  const hasFailed = data.failed_tables > 0
  const triggerLabel = TRIGGER_TYPE_LABELS[data.trigger_type] ?? data.trigger_type

  return (
    <div
      role="status"
      aria-live="polite"
      className="sticky top-14 z-40 border-b border-border bg-card px-4 py-2 md:px-6"
    >
      <div className="mx-auto flex max-w-7xl flex-col gap-1.5">
        <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 text-sm md:text-base">
          <span className="font-medium text-foreground">
            ETL 同步中({triggerLabel})— 已完成 {data.processed_tables} / 共{' '}
            {data.total_tables} 表({percent}%)
          </span>
          <span className="flex flex-wrap items-center gap-x-2 text-muted-foreground">
            <span className="text-success">成功 {data.success_tables}</span>
            {hasFailed ? (
              <span className="text-danger">失敗 {data.failed_tables}</span>
            ) : null}
            <span>略過 {data.skipped_tables}</span>
          </span>
        </div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
          <div
            className={`h-full rounded-full transition-[width] duration-300 ${
              hasFailed ? 'bg-danger' : 'bg-primary'
            }`}
            style={{ width: `${percent}%` }}
          />
        </div>
      </div>
    </div>
  )
}
