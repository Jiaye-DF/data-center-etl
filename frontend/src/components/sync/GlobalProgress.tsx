'use client'

import { useGlobalProgressQuery } from '@/lib/api/progressApi'
import type { Dataset, SnapshotRefreshProgress } from '@/lib/api/datasetApi'
import type { ActiveRunData } from '@/lib/api/runApi'
import { useAuth } from '@/lib/auth/useAuth'
import { TRIGGER_TYPE_LABELS } from '@/constants/labels'

// 視窗未聚焦不輪詢(RTK Query 內建節流,對齊 propose § 執行模型;不做 websocket)
const POLLING_INTERVAL_MS = 5_000

/** 快照 refresh 各階段顯示名稱(對齊後端 SnapshotRefreshProgress.phase) */
const SNAPSHOT_PHASE_LABELS: Record<string, string> = {
  introspect: '讀取資料表結構',
  dictionary: '查詢字典業務名稱',
  persist: '寫入快照',
  schedules: '維護逐表排程',
}

const DATASET_LABELS: Record<Dataset, string> = {
  source: '原始資料',
  target: 'ETL 資料',
}

/** 套用各階段顯示名稱(對齊後端 apply progress phase) */
const APPLY_PHASE_LABELS: Record<string, string> = {
  copy: '更新名稱對照',
  views: '重建英文資料檢視',
}

function SyncRow({ run }: { run: ActiveRunData }): React.ReactNode {
  const percent =
    run.total_tables === 0
      ? 0
      : Math.min(
          100,
          Math.round((run.processed_tables / run.total_tables) * 100),
        )
  const hasFailed = run.failed_tables > 0
  const triggerLabel = TRIGGER_TYPE_LABELS[run.trigger_type] ?? run.trigger_type

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-1.5">
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 text-sm md:text-base">
        <span className="font-medium text-foreground">
          ETL 同步中({triggerLabel})— 已完成 {run.processed_tables} / 共{' '}
          {run.total_tables} 表({percent}%)
        </span>
        <span className="flex flex-wrap items-center gap-x-2 text-muted-foreground">
          <span className="text-success">成功 {run.success_tables}</span>
          {hasFailed ? (
            <span className="text-danger">失敗 {run.failed_tables}</span>
          ) : null}
          <span>略過 {run.skipped_tables}</span>
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
  )
}

/** 快照 / 套用共用進度列:total=0 顯示不定進度動畫 */
function PhaseRow({
  title,
  phaseLabel,
  progress,
}: {
  title: string
  phaseLabel: string
  progress: SnapshotRefreshProgress
}): React.ReactNode {
  const determinate = progress.total > 0
  const percent = determinate
    ? Math.min(100, Math.round((progress.done / progress.total) * 100))
    : 0
  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-1.5">
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 text-sm md:text-base">
        <span className="font-medium text-foreground">
          {title} — {phaseLabel}
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

/** 全局進度條:掛 (main) layout,單一聚合輪詢(AD-121)取回 ETL 同步 / 快照(source、target)/
 *  套用四種狀態,於同一個 sticky 容器內垂直堆疊(AD-124);全部閒置時不渲染。 */
export function GlobalProgress(): React.ReactNode {
  const { isAdmin } = useAuth()
  // non-admin 已被 (main)/layout.tsx 導向 /no-access,此處再守一層避免對 403 端點空輪詢
  const { data } = useGlobalProgressQuery(undefined, {
    pollingInterval: POLLING_INTERVAL_MS,
    skipPollingIfUnfocused: true,
    skip: !isAdmin,
  })

  if (data === undefined) {
    return null
  }

  const rows: React.ReactNode[] = []
  if (data.sync !== null) {
    rows.push(<SyncRow key="sync" run={data.sync} />)
  }
  for (const dataset of ['source', 'target'] as const) {
    const progress =
      dataset === 'source' ? data.snapshot_source : data.snapshot_target
    if (progress.active) {
      rows.push(
        <PhaseRow
          key={`snapshot-${dataset}`}
          title={`快照同步中(${DATASET_LABELS[dataset]})`}
          phaseLabel={SNAPSHOT_PHASE_LABELS[progress.phase] ?? progress.phase}
          progress={progress}
        />,
      )
    }
  }
  if (data.apply.active) {
    rows.push(
      <PhaseRow
        key="apply"
        title="套用名稱對照中"
        phaseLabel={APPLY_PHASE_LABELS[data.apply.phase] ?? data.apply.phase}
        progress={data.apply}
      />,
    )
  }

  if (rows.length === 0) {
    return null
  }

  return (
    <div
      role="status"
      aria-live="polite"
      className="sticky top-14 z-40 flex flex-col gap-2 border-b border-border bg-card px-4 py-2 md:px-6"
    >
      {rows}
    </div>
  )
}
