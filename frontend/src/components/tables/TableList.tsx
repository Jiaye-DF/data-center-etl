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
    return (
      <span className="text-sm text-muted-foreground md:text-base">
        尚未執行
      </span>
    )
  }
  return (
    <span className="flex flex-col gap-0.5">
      <StatusBadge status={status} />
      {runAt !== null ? (
        <span className="text-sm text-muted-foreground">
          {formatDateTime(runAt)}
        </span>
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
    ? 'bg-success/15 text-success'
    : 'bg-muted text-muted-foreground'

  return (
    <tr className="border-b border-border transition-colors last:border-b-0 hover:bg-muted/50">
      <td className="px-3 py-3">
        <Link
          href={`/tables/${item.uid}`}
          className="text-sm font-medium text-primary underline-offset-2 hover:underline md:text-base"
        >
          {item.source_schema}.{item.source_table}
        </Link>
        {item.description !== null && item.description !== '' ? (
          <p className="mt-0.5 text-sm text-muted-foreground">
            {item.description}
          </p>
        ) : null}
      </td>
      <td className="df-td text-muted-foreground">
        {item.target_schema}.{item.target_table}
      </td>
      <td className="df-td text-muted-foreground">{item.mapping_count}</td>
      <td className="px-3 py-3">
        <span className={`df-badge ${enabledClass}`}>
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
            className="df-btn-warning-soft min-h-[36px] px-3"
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
          className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger md:text-base"
        >
          {toggleError}
        </p>
      ) : null}

      <div className="df-card overflow-x-auto">
        <table className="df-table min-w-[720px]">
          <thead>
            <tr className="border-b border-border bg-muted/50">
              <th className="df-th">來源表</th>
              <th className="df-th">目標表</th>
              <th className="df-th">欄位數</th>
              <th className="df-th">啟用狀態</th>
              <th className="df-th">最近執行</th>
              {canEdit ? <th className="df-th">操作</th> : null}
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
          <p className="px-3 py-8 text-center text-sm text-muted-foreground md:text-base">
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
