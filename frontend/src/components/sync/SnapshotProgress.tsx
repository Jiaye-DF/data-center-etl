'use client'

import {
  useSnapshotRefreshProgressQuery,
  type Dataset,
  type SnapshotRefreshProgress as SnapshotRefreshProgressData,
} from '@/lib/api/datasetApi'
import { useAuth } from '@/lib/auth/useAuth'

// 對齊 SyncProgress 全局輪詢慣例:5s、視窗未聚焦暫停、僅 admin
const POLLING_INTERVAL_MS = 5_000

/** 快照 refresh 各階段顯示名稱(對齊後端 SnapshotRefreshProgress.phase) */
const PHASE_LABELS: Record<string, string> = {
  introspect: '讀取資料表結構',
  dictionary: '查詢字典業務名稱',
  persist: '寫入快照',
  schedules: '維護逐表排程',
}

const DATASET_LABELS: Record<Dataset, string> = {
  source: '原始資料',
  target: 'ETL 資料',
}

function SnapshotBar({
  dataset,
  progress,
}: {
  dataset: Dataset
  progress: SnapshotRefreshProgressData
}): React.ReactNode {
  const determinate = progress.total > 0
  const percent = determinate
    ? Math.min(100, Math.round((progress.done / progress.total) * 100))
    : 0
  const phaseLabel = PHASE_LABELS[progress.phase] ?? progress.phase
  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-1.5">
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 text-sm md:text-base">
        <span className="font-medium text-foreground">
          快照同步中({DATASET_LABELS[dataset]})— {phaseLabel}
          {determinate
            ? `(${progress.done.toLocaleString()} / ${progress.total.toLocaleString()} 表,${percent}%)`
            : '…'}
        </span>
      </div>
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
  )
}

/** 全局快照同步進度條:掛 (main) layout,與 ETL 同步進度條(SyncProgress)並列;
 *  source / target 各自輪詢,誰在跑就顯示誰(標示資料集以資區分)。 */
export function SnapshotProgress(): React.ReactNode {
  const { isAdmin } = useAuth()
  const queryOptions = {
    pollingInterval: POLLING_INTERVAL_MS,
    skipPollingIfUnfocused: true,
    skip: !isAdmin,
  }
  const { data: sourceProgress } = useSnapshotRefreshProgressQuery('source', queryOptions)
  const { data: targetProgress } = useSnapshotRefreshProgressQuery('target', queryOptions)

  const active: Array<{ dataset: Dataset; progress: SnapshotRefreshProgressData }> = []
  if (sourceProgress?.active === true) {
    active.push({ dataset: 'source', progress: sourceProgress })
  }
  if (targetProgress?.active === true) {
    active.push({ dataset: 'target', progress: targetProgress })
  }
  if (active.length === 0) {
    return null
  }

  return (
    <div
      role="status"
      aria-live="polite"
      className="sticky top-14 z-40 flex flex-col gap-2 border-b border-border bg-card px-4 py-2 md:px-6"
    >
      {active.map(({ dataset, progress }) => (
        <SnapshotBar key={dataset} dataset={dataset} progress={progress} />
      ))}
    </div>
  )
}
