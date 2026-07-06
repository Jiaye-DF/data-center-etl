'use client'

import { memo, useCallback, useState } from 'react'
import { useListRunLogsQuery, type RunLog, type RunLogStatus } from '@/lib/api/runApi'
import { formatNullableDateTime } from '@/utils/datetime'
import { Pagination } from '@/components/common/Pagination'
import { StatusBadge } from '@/components/common/StatusBadge'

function formatDurationMs(ms: number | null): string {
  if (ms === null) {
    return '—'
  }
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`
}

const LOG_PAGE_SIZE = 20

/** 逐表 log 狀態過濾選項('' = 全部) */
const LOG_STATUS_OPTIONS: { value: '' | RunLogStatus; label: string }[] = [
  { value: '', label: '全部狀態' },
  { value: 'pending', label: '等待中' },
  { value: 'running', label: '執行中' },
  { value: 'success', label: '成功' },
  { value: 'failed', label: '失敗' },
  { value: 'skipped', label: '略過' },
]

interface RunLogRowProps {
  log: RunLog
  expanded: boolean
  onToggleStack: (uid: string) => void
}

const RunLogRow = memo(function RunLogRow({
  log,
  expanded,
  onToggleStack,
}: RunLogRowProps): React.ReactNode {
  const handleToggle = useCallback((): void => {
    onToggleStack(log.uid)
  }, [onToggleStack, log.uid])

  // 失敗表列醒目標示
  const rowClass =
    log.status === 'failed'
      ? 'border-b border-danger/20 bg-danger/5 last:border-b-0'
      : 'border-b border-border transition-colors last:border-b-0 hover:bg-muted/50'

  return (
    <>
      <tr className={rowClass}>
        <td className="px-3 py-3 text-sm font-medium text-foreground md:text-base">
          {log.source_schema}.{log.source_table}
        </td>
        <td className="px-3 py-3">
          <StatusBadge status={log.status} />
        </td>
        <td className="df-td text-muted-foreground">{log.row_count ?? '—'}</td>
        <td className="df-td text-muted-foreground">
          {formatDurationMs(log.duration_ms)}
        </td>
        <td className="df-td text-muted-foreground">
          {formatNullableDateTime(log.started_at)}
        </td>
        <td className="df-td text-muted-foreground">
          {formatNullableDateTime(log.finished_at)}
        </td>
        <td className="px-3 py-3">
          {log.error_message !== null && log.error_message !== '' ? (
            <p className="text-sm text-danger md:text-base">
              {log.error_message}
            </p>
          ) : (
            <span className="text-sm text-muted-foreground md:text-base">—</span>
          )}
          {log.error_stack !== null && log.error_stack !== '' ? (
            <button
              type="button"
              onClick={handleToggle}
              aria-expanded={expanded}
              className="df-btn-danger-soft mt-1 min-h-[32px] px-2"
            >
              {expanded ? '收合 stack trace' : '展開 stack trace'}
            </button>
          ) : null}
        </td>
      </tr>
      {expanded && log.error_stack !== null ? (
        <tr className="border-b border-danger/20 bg-danger/5 last:border-b-0">
          <td colSpan={7} className="px-3 py-3">
            {/* monospace code 允許 text-xs(00-overview 字級下限例外) */}
            <pre className="max-h-96 overflow-auto rounded-lg bg-zinc-900 p-3 font-mono text-xs whitespace-pre-wrap text-red-200">
              {log.error_stack}
            </pre>
          </td>
        </tr>
      ) : null}
    </>
  )
})

export interface RunLogTableProps {
  runUid: string
}

/** 單次執行的逐表詳細 log(狀態過濾 + 分頁;stack trace 預設收合) */
export function RunLogTable({ runUid }: RunLogTableProps): React.ReactNode {
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState<'' | RunLogStatus>('')
  const [expandedUids, setExpandedUids] = useState<ReadonlySet<string>>(
    new Set<string>(),
  )

  const { data, isLoading, isError } = useListRunLogsQuery({
    runUid,
    page,
    pageSize: LOG_PAGE_SIZE,
    status: statusFilter === '' ? undefined : statusFilter,
  })

  const handleStatusChange = useCallback(
    (event: React.ChangeEvent<HTMLSelectElement>): void => {
      setStatusFilter(event.target.value as '' | RunLogStatus)
      setPage(1)
    },
    [],
  )

  const handlePageChange = useCallback((nextPage: number): void => {
    setPage(nextPage)
  }, [])

  const handleToggleStack = useCallback((uid: string): void => {
    setExpandedUids((prev) => {
      const next = new Set(prev)
      if (next.has(uid)) {
        next.delete(uid)
      } else {
        next.add(uid)
      }
      return next
    })
  }, [])

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <label
          htmlFor="run-log-status-filter"
          className="text-sm font-medium text-foreground md:text-base"
        >
          逐表狀態
        </label>
        <select
          id="run-log-status-filter"
          value={statusFilter}
          onChange={handleStatusChange}
          className="df-input w-auto min-w-[8rem]"
        >
          {LOG_STATUS_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      {isLoading ? (
        <p className="text-sm text-muted-foreground md:text-base">載入中…</p>
      ) : null}
      {isError ? (
        <p
          role="alert"
          className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger md:text-base"
        >
          載入逐表詳細 log 失敗,請稍後再試
        </p>
      ) : null}

      {data !== undefined ? (
        <>
          <div className="df-card overflow-x-auto">
            <table className="df-table min-w-[880px]">
              <thead>
                <tr className="border-b border-border bg-muted/50">
                  <th className="df-th">來源表</th>
                  <th className="df-th">狀態</th>
                  <th className="df-th">讀寫筆數</th>
                  <th className="df-th">耗時</th>
                  <th className="df-th">開始時間</th>
                  <th className="df-th">結束時間</th>
                  <th className="df-th">錯誤明細</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((log) => (
                  <RunLogRow
                    key={log.uid}
                    log={log}
                    expanded={expandedUids.has(log.uid)}
                    onToggleStack={handleToggleStack}
                  />
                ))}
              </tbody>
            </table>
            {data.items.length === 0 ? (
              <p className="px-3 py-8 text-center text-sm text-muted-foreground md:text-base">
                無符合條件的逐表 log
              </p>
            ) : null}
          </div>
          <Pagination
            page={data.page}
            pageSize={data.page_size}
            total={data.total}
            onPageChange={handlePageChange}
          />
        </>
      ) : null}
    </div>
  )
}
