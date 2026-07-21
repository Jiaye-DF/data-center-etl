'use client'

import { useApplyProgressQuery } from '@/lib/api/semanticMappingApi'
import { useAuth } from '@/lib/auth/useAuth'

// 對齊 SyncProgress / SnapshotProgress 全局輪詢慣例:5s、視窗未聚焦暫停、僅 admin
const POLLING_INTERVAL_MS = 5_000

/** 套用各階段顯示名稱(對齊後端 apply progress phase) */
const PHASE_LABELS: Record<string, string> = {
  copy: '更新名稱對照',
  views: '重建英文資料檢視',
}

/** 全局「套用變更」進度條:掛 (main) layout,與 ETL 同步 / 快照同步進度條並列;
 *  手動套用與 ETL 同步收尾的自動套用都會顯示。 */
export function ApplyProgress(): React.ReactNode {
  const { isAdmin } = useAuth()
  const { data } = useApplyProgressQuery(undefined, {
    pollingInterval: POLLING_INTERVAL_MS,
    skipPollingIfUnfocused: true,
    skip: !isAdmin,
  })

  if (data === undefined || !data.active) {
    return null
  }

  const determinate = data.total > 0
  const percent = determinate
    ? Math.min(100, Math.round((data.done / data.total) * 100))
    : 0
  const phaseLabel = PHASE_LABELS[data.phase] ?? data.phase

  return (
    <div
      role="status"
      aria-live="polite"
      className="sticky top-14 z-40 border-b border-border bg-card px-4 py-2 md:px-6"
    >
      <div className="mx-auto flex max-w-7xl flex-col gap-1.5">
        <span className="text-sm font-medium text-foreground md:text-base">
          套用名稱對照中 — {phaseLabel}
          {determinate
            ? `(${data.done.toLocaleString()} / ${data.total.toLocaleString()} 表,${percent}%)`
            : '…'}
        </span>
        <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
          <div
            className={
              determinate
                ? 'h-full rounded-full bg-primary transition-[width] duration-300'
                : 'h-full w-1/3 animate-pulse rounded-full bg-primary'
            }
            style={determinate ? { width: `${percent}%` } : undefined}
          />
        </div>
      </div>
    </div>
  )
}
