'use client'

import { memo, useCallback, useMemo, useState } from 'react'
import { useListRunLogsQuery, type RunLog, type RunLogStatus } from '@/lib/api/runApi'
import { formatDateTime } from '@/utils/datetime'

// 本檔除 RunLogTable 外,一併匯出 schedules / runs 頁共用的顯示單元
// (StatusBadge / Pagination / TRIGGER_TYPE_LABELS / formatNullableDateTime);
// 抽至 components/common 為後續正式化候選(affected_files 未含該路徑,見 fixed.md)。

/** run / 逐表 log 狀態顯示字樣(聯集兩層狀態值) */
const STATUS_LABELS: Record<string, string> = {
  pending: '等待中',
  running: '執行中',
  success: '成功',
  partial: '部分失敗',
  failed: '失敗',
  skipped: '略過',
}

const STATUS_CLASSES: Record<string, string> = {
  pending: 'bg-gray-100 text-gray-700',
  running: 'bg-blue-50 text-blue-700',
  success: 'bg-green-50 text-green-700',
  partial: 'bg-orange-50 text-orange-700',
  failed: 'bg-red-50 text-red-700',
  skipped: 'bg-yellow-50 text-yellow-700',
}

export const TRIGGER_TYPE_LABELS: Record<string, string> = {
  schedule: '排程',
  manual: '手動',
}

/** 可為 null 的時間顯示(started_at / finished_at 等) */
export function formatNullableDateTime(iso: string | null): string {
  return iso === null ? '—' : formatDateTime(iso)
}

function formatDurationMs(ms: number | null): string {
  if (ms === null) {
    return '—'
  }
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`
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

export interface PaginationProps {
  page: number
  pageSize: number
  total: number
  onPageChange: (page: number) => void
}

export const Pagination = memo(function Pagination({
  page,
  pageSize,
  total,
  onPageChange,
}: PaginationProps): React.ReactNode {
  const totalPages = useMemo(
    (): number => Math.max(1, Math.ceil(total / pageSize)),
    [total, pageSize],
  )

  const handlePrev = useCallback((): void => {
    onPageChange(page - 1)
  }, [onPageChange, page])

  const handleNext = useCallback((): void => {
    onPageChange(page + 1)
  }, [onPageChange, page])

  return (
    <div className="flex items-center justify-between gap-2">
      <p className="text-sm text-gray-600 md:text-base">
        共 {total} 筆,第 {page} / {totalPages} 頁
      </p>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={handlePrev}
          disabled={page <= 1}
          className="min-h-[44px] rounded border border-gray-300 px-4 text-sm font-medium text-gray-700 hover:bg-gray-100 disabled:opacity-50 md:text-base"
        >
          上一頁
        </button>
        <button
          type="button"
          onClick={handleNext}
          disabled={page >= totalPages}
          className="min-h-[44px] rounded border border-gray-300 px-4 text-sm font-medium text-gray-700 hover:bg-gray-100 disabled:opacity-50 md:text-base"
        >
          下一頁
        </button>
      </div>
    </div>
  )
})

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
      ? 'border-b border-red-100 bg-red-50/60 last:border-b-0'
      : 'border-b border-gray-100 last:border-b-0 hover:bg-gray-50'

  return (
    <>
      <tr className={rowClass}>
        <td className="px-3 py-3 text-sm font-medium text-gray-900 md:text-base">
          {log.source_schema}.{log.source_table}
        </td>
        <td className="px-3 py-3">
          <StatusBadge status={log.status} />
        </td>
        <td className="px-3 py-3 text-sm text-gray-700 md:text-base">
          {log.row_count ?? '—'}
        </td>
        <td className="px-3 py-3 text-sm text-gray-700 md:text-base">
          {formatDurationMs(log.duration_ms)}
        </td>
        <td className="px-3 py-3 text-sm text-gray-700 md:text-base">
          {formatNullableDateTime(log.started_at)}
        </td>
        <td className="px-3 py-3 text-sm text-gray-700 md:text-base">
          {formatNullableDateTime(log.finished_at)}
        </td>
        <td className="px-3 py-3">
          {log.error_message !== null && log.error_message !== '' ? (
            <p className="text-sm text-red-700 md:text-base">
              {log.error_message}
            </p>
          ) : (
            <span className="text-sm text-gray-400 md:text-base">—</span>
          )}
          {log.error_stack !== null && log.error_stack !== '' ? (
            <button
              type="button"
              onClick={handleToggle}
              aria-expanded={expanded}
              className="mt-1 min-h-[44px] rounded border border-red-200 px-2 text-sm font-medium text-red-700 hover:bg-red-100 md:min-h-[28px]"
            >
              {expanded ? '收合 stack trace' : '展開 stack trace'}
            </button>
          ) : null}
        </td>
      </tr>
      {expanded && log.error_stack !== null ? (
        <tr className="border-b border-red-100 bg-red-50/40 last:border-b-0">
          <td colSpan={7} className="px-3 py-3">
            {/* monospace code 允許 text-xs(00-overview 字級下限例外) */}
            <pre className="max-h-96 overflow-auto rounded bg-gray-900 p-3 font-mono text-xs whitespace-pre-wrap text-red-200">
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
          className="text-sm font-medium text-gray-700 md:text-base"
        >
          逐表狀態
        </label>
        <select
          id="run-log-status-filter"
          value={statusFilter}
          onChange={handleStatusChange}
          className="min-h-[44px] rounded border border-gray-300 bg-white px-2 text-sm text-gray-700 md:text-base"
        >
          {LOG_STATUS_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      {isLoading ? (
        <p className="text-sm text-gray-500 md:text-base">載入中…</p>
      ) : null}
      {isError ? (
        <p
          role="alert"
          className="rounded bg-red-50 px-3 py-2 text-sm text-red-700 md:text-base"
        >
          載入逐表詳細 log 失敗,請稍後再試
        </p>
      ) : null}

      {data !== undefined ? (
        <>
          <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white shadow-sm">
            <table className="w-full min-w-[880px] text-left">
              <thead>
                <tr className="border-b border-gray-200 bg-gray-50">
                  <th className="px-3 py-2 text-sm font-semibold text-gray-700 md:text-base">
                    來源表
                  </th>
                  <th className="px-3 py-2 text-sm font-semibold text-gray-700 md:text-base">
                    狀態
                  </th>
                  <th className="px-3 py-2 text-sm font-semibold text-gray-700 md:text-base">
                    讀寫筆數
                  </th>
                  <th className="px-3 py-2 text-sm font-semibold text-gray-700 md:text-base">
                    耗時
                  </th>
                  <th className="px-3 py-2 text-sm font-semibold text-gray-700 md:text-base">
                    開始時間
                  </th>
                  <th className="px-3 py-2 text-sm font-semibold text-gray-700 md:text-base">
                    結束時間
                  </th>
                  <th className="px-3 py-2 text-sm font-semibold text-gray-700 md:text-base">
                    錯誤明細
                  </th>
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
              <p className="px-3 py-8 text-center text-sm text-gray-500 md:text-base">
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
