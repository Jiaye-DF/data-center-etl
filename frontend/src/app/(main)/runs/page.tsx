'use client'

import { memo, useCallback, useState } from 'react'
import Link from 'next/link'
import {
  useListRunsQuery,
  useTriggerRunMutation,
  type RunStatus,
  type RunSummary,
  type TriggerType,
} from '@/lib/api/runApi'
import { useAuth } from '@/lib/auth/useAuth'
import { Pagination } from '@/components/common/Pagination'
import { StatusBadge } from '@/components/common/StatusBadge'
import { TRIGGER_TYPE_LABELS } from '@/constants/labels'
import { extractApiErrorDetail } from '@/utils/apiError'
import { formatNullableDateTime } from '@/utils/datetime'

const PAGE_SIZE = 20
// 佇列模式下 run 由 worker 非同步建立,輪詢讓觸發後的新 run / 進行中狀態自動更新
const POLLING_INTERVAL_MS = 10_000

const STATUS_OPTIONS: { value: '' | RunStatus; label: string }[] = [
  { value: '', label: '全部狀態' },
  { value: 'pending', label: '等待中' },
  { value: 'running', label: '執行中' },
  { value: 'success', label: '成功' },
  { value: 'failed', label: '失敗' },
]

const TRIGGER_OPTIONS: { value: '' | TriggerType; label: string }[] = [
  { value: '', label: '全部觸發方式' },
  { value: 'schedule', label: '排程' },
  { value: 'manual', label: '手動' },
]

interface RunRowProps {
  run: RunSummary
}

const RunRow = memo(function RunRow({ run }: RunRowProps): React.ReactNode {
  return (
    <tr className="border-b border-border transition-colors last:border-b-0 hover:bg-muted/50">
      <td className="df-td text-muted-foreground">
        {TRIGGER_TYPE_LABELS[run.trigger_type] ?? run.trigger_type}
      </td>
      <td className="df-td text-muted-foreground">
        {run.schedule_name ?? '—'}
      </td>
      <td className="px-3 py-3">
        <StatusBadge status={run.status} />
      </td>
      <td className="df-td text-muted-foreground">
        {formatNullableDateTime(run.started_at)}
      </td>
      <td className="df-td text-muted-foreground">
        {formatNullableDateTime(run.finished_at)}
      </td>
      <td className="df-td text-muted-foreground">
        <span className="text-success">{run.success_tables} 成功</span>
        {run.failed_tables > 0 ? (
          <span className="text-danger"> / {run.failed_tables} 失敗</span>
        ) : null}
        <span> / 共 {run.total_tables}</span>
      </td>
      <td className="px-3 py-3">
        <Link
          href={`/runs/${run.uid}`}
          className="text-sm font-medium text-primary underline-offset-2 hover:underline md:text-base"
        >
          查看明細
        </Link>
      </td>
    </tr>
  )
})

export default function RunsPage(): React.ReactNode {
  const { isAdmin } = useAuth()
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState<'' | RunStatus>('')
  const [triggerFilter, setTriggerFilter] = useState<'' | TriggerType>('')
  const [triggerError, setTriggerError] = useState<string | null>(null)
  const [triggerNotice, setTriggerNotice] = useState<string | null>(null)

  const { data, isLoading, isError } = useListRunsQuery(
    {
      page,
      pageSize: PAGE_SIZE,
      status: statusFilter === '' ? undefined : statusFilter,
      triggerType: triggerFilter === '' ? undefined : triggerFilter,
    },
    { pollingInterval: POLLING_INTERVAL_MS },
  )
  const [triggerRun, { isLoading: isTriggering }] = useTriggerRunMutation()

  const handleStatusChange = useCallback(
    (event: React.ChangeEvent<HTMLSelectElement>): void => {
      setStatusFilter(event.target.value as '' | RunStatus)
      setPage(1)
    },
    [],
  )

  const handleTriggerFilterChange = useCallback(
    (event: React.ChangeEvent<HTMLSelectElement>): void => {
      setTriggerFilter(event.target.value as '' | TriggerType)
      setPage(1)
    },
    [],
  )

  const handlePageChange = useCallback((nextPage: number): void => {
    setPage(nextPage)
  }, [])

  const handleTrigger = useCallback(async (): Promise<void> => {
    setTriggerError(null)
    setTriggerNotice(null)
    const result = await triggerRun({ etlTableUid: null })
    if ('error' in result) {
      setTriggerError(
        extractApiErrorDetail(result.error, '手動觸發失敗,請稍後再試'),
      )
    } else {
      setTriggerNotice('已送出手動觸發(全部啟用表),新 run 稍後出現在清單最上方')
    }
  }, [triggerRun])

  return (
    <section className="mx-auto flex max-w-7xl flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-foreground md:text-2xl">
            執行紀錄
          </h1>
          <p className="mt-1 text-sm text-muted-foreground md:text-base">
            ETL 執行 run 清單:狀態 / 觸發方式過濾,點入查看逐表詳細 log
          </p>
        </div>
        {isAdmin ? (
          <button
            type="button"
            onClick={handleTrigger}
            disabled={isTriggering}
            className="df-btn-primary"
          >
            手動觸發(全部啟用表)
          </button>
        ) : null}
      </div>

      {triggerError !== null ? (
        <p
          role="alert"
          className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger md:text-base"
        >
          {triggerError}
        </p>
      ) : null}
      {triggerNotice !== null ? (
        <p className="rounded-lg bg-success/15 px-3 py-2 text-sm text-success md:text-base">
          {triggerNotice}
        </p>
      ) : null}

      <div className="flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2">
          <label
            htmlFor="run-status-filter"
            className="text-sm font-medium text-foreground md:text-base"
          >
            狀態
          </label>
          <select
            id="run-status-filter"
            value={statusFilter}
            onChange={handleStatusChange}
            className="df-input w-auto min-w-[8rem]"
          >
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-2">
          <label
            htmlFor="run-trigger-filter"
            className="text-sm font-medium text-foreground md:text-base"
          >
            觸發方式
          </label>
          <select
            id="run-trigger-filter"
            value={triggerFilter}
            onChange={handleTriggerFilterChange}
            className="df-input w-auto min-w-[8rem]"
          >
            {TRIGGER_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {isLoading ? (
        <p className="text-sm text-muted-foreground md:text-base">載入中…</p>
      ) : null}
      {isError ? (
        <p
          role="alert"
          className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger md:text-base"
        >
          載入執行紀錄失敗,請稍後再試
        </p>
      ) : null}

      {data !== undefined ? (
        <div className="flex flex-col gap-3">
          <div className="df-card overflow-x-auto">
            <table className="df-table min-w-[880px]">
              <thead>
                <tr className="border-b border-border bg-muted/50">
                  <th className="df-th">觸發方式</th>
                  <th className="df-th">排程名稱</th>
                  <th className="df-th">狀態</th>
                  <th className="df-th">開始時間</th>
                  <th className="df-th">結束時間</th>
                  <th className="df-th">表數統計</th>
                  <th className="df-th">明細</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((run) => (
                  <RunRow key={run.uid} run={run} />
                ))}
              </tbody>
            </table>
            {data.items.length === 0 ? (
              <p className="px-3 py-8 text-center text-sm text-muted-foreground md:text-base">
                無符合條件的執行紀錄
              </p>
            ) : null}
          </div>
          <Pagination
            page={data.page}
            pageSize={data.page_size}
            total={data.total}
            onPageChange={handlePageChange}
          />
        </div>
      ) : null}
    </section>
  )
}
