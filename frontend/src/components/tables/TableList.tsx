'use client'

import { memo, useCallback, useState } from 'react'
import Link from 'next/link'
import {
  useSetEtlTableEnabledMutation,
  type EtlTableListData,
  type EtlTableSummary,
} from '@/lib/api/etlConfigApi'
import { Pagination } from '@/components/common/Pagination'
import { StatusBadge } from '@/components/common/StatusBadge'
import { extractApiErrorDetail } from '@/utils/apiError'
import { formatDateTime } from '@/utils/datetime'

interface RunStatusBadgeProps {
  status: string | null
  runAt: string | null
}

/** 最近執行狀態:共用 StatusBadge + 本頁特有的執行時間副行 */
const RunStatusBadge = memo(function RunStatusBadge({
  status,
  runAt,
}: RunStatusBadgeProps): React.ReactNode {
  if (status === null) {
    return <span className="text-sm text-gray-400 md:text-base">尚未執行</span>
  }
  return (
    <span className="flex flex-col gap-0.5">
      <StatusBadge status={status} />
      {runAt !== null ? (
        <span className="text-sm text-gray-500">{formatDateTime(runAt)}</span>
      ) : null}
    </span>
  )
})

interface TableRowProps {
  item: EtlTableSummary
  canEdit: boolean
  toggling: boolean
  onToggle: (uid: string, enabled: boolean) => void
}

const TableRow = memo(function TableRow({
  item,
  canEdit,
  toggling,
  onToggle,
}: TableRowProps): React.ReactNode {
  const handleToggle = useCallback((): void => {
    onToggle(item.uid, !item.is_enabled)
  }, [onToggle, item.uid, item.is_enabled])

  const enabledClass = item.is_enabled
    ? 'bg-green-50 text-green-700'
    : 'bg-gray-100 text-gray-500'

  return (
    <tr className="border-b border-gray-100 last:border-b-0 hover:bg-gray-50">
      <td className="px-3 py-3">
        <Link
          href={`/tables/${item.uid}`}
          className="text-sm font-medium text-gray-900 underline-offset-2 hover:underline md:text-base"
        >
          {item.source_schema}.{item.source_table}
        </Link>
        {item.description !== null && item.description !== '' ? (
          <p className="mt-0.5 text-sm text-gray-500">{item.description}</p>
        ) : null}
      </td>
      <td className="px-3 py-3 text-sm text-gray-700 md:text-base">
        {item.target_schema}.{item.target_table}
      </td>
      <td className="px-3 py-3 text-sm text-gray-700 md:text-base">
        {item.mapping_count}
      </td>
      <td className="px-3 py-3">
        <span
          className={`rounded px-2 py-0.5 text-sm font-medium md:text-base ${enabledClass}`}
        >
          {item.is_enabled ? '啟用' : '停用'}
        </span>
      </td>
      <td className="px-3 py-3">
        <RunStatusBadge status={item.last_run_status} runAt={item.last_run_at} />
      </td>
      {canEdit ? (
        <td className="px-3 py-3">
          <button
            type="button"
            onClick={handleToggle}
            disabled={toggling}
            className="min-h-[44px] rounded border border-gray-300 px-3 text-sm font-medium text-gray-700 hover:bg-gray-100 disabled:opacity-50 md:min-h-[32px] md:text-base"
          >
            {item.is_enabled ? '停用' : '啟用'}
          </button>
        </td>
      ) : null}
    </tr>
  )
})

export interface TableListProps {
  data: EtlTableListData
  /** viewer 角色為 false:隱藏啟停操作欄 */
  canEdit: boolean
  onPageChange: (page: number) => void
}

export function TableList({
  data,
  canEdit,
  onPageChange,
}: TableListProps): React.ReactNode {
  const [setEnabled, { isLoading: isToggling }] =
    useSetEtlTableEnabledMutation()
  const [togglingUid, setTogglingUid] = useState<string | null>(null)
  const [toggleError, setToggleError] = useState<string | null>(null)

  const handleToggle = useCallback(
    async (uid: string, enabled: boolean): Promise<void> => {
      setTogglingUid(uid)
      setToggleError(null)
      const result = await setEnabled({ uid, enabled })
      if ('error' in result) {
        setToggleError(
          extractApiErrorDetail(result.error, '切換啟用狀態失敗,請稍後再試'),
        )
      }
      setTogglingUid(null)
    },
    [setEnabled],
  )

  return (
    <div className="flex flex-col gap-3">
      {toggleError !== null ? (
        <p
          role="alert"
          className="rounded bg-red-50 px-3 py-2 text-sm text-red-700 md:text-base"
        >
          {toggleError}
        </p>
      ) : null}

      <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white shadow-sm">
        <table className="w-full min-w-[720px] text-left">
          <thead>
            <tr className="border-b border-gray-200 bg-gray-50">
              <th className="px-3 py-2 text-sm font-semibold text-gray-700 md:text-base">
                來源表
              </th>
              <th className="px-3 py-2 text-sm font-semibold text-gray-700 md:text-base">
                目標表
              </th>
              <th className="px-3 py-2 text-sm font-semibold text-gray-700 md:text-base">
                欄位數
              </th>
              <th className="px-3 py-2 text-sm font-semibold text-gray-700 md:text-base">
                啟用狀態
              </th>
              <th className="px-3 py-2 text-sm font-semibold text-gray-700 md:text-base">
                最近執行
              </th>
              {canEdit ? (
                <th className="px-3 py-2 text-sm font-semibold text-gray-700 md:text-base">
                  操作
                </th>
              ) : null}
            </tr>
          </thead>
          <tbody>
            {data.items.map((item) => (
              <TableRow
                key={item.uid}
                item={item}
                canEdit={canEdit}
                toggling={isToggling && togglingUid === item.uid}
                onToggle={handleToggle}
              />
            ))}
          </tbody>
        </table>
        {data.items.length === 0 ? (
          <p className="px-3 py-8 text-center text-sm text-gray-500 md:text-base">
            尚無納管的資料表
          </p>
        ) : null}
      </div>

      <Pagination
        page={data.page}
        pageSize={data.page_size}
        total={data.total}
        onPageChange={onPageChange}
      />
    </div>
  )
}
