'use client'

import { memo, useCallback, useMemo, useState } from 'react'
import {
  useListDatasetSchemasQuery,
  useListDatasetTablesQuery,
  useRefreshDatasetSnapshotMutation,
  type Dataset,
  type TableSummary,
} from '@/lib/api/datasetApi'
import { useSyncAllMutation, useSyncTableMutation } from '@/lib/api/syncApi'
import { useAuth } from '@/lib/auth/useAuth'
import { Pagination } from '@/components/common/Pagination'
import { extractApiErrorDetail } from '@/utils/apiError'
import { formatNullableDateTime } from '@/utils/datetime'
import { getSchemaDescription } from '@/constants/schemaDescriptions'

const PAGE_SIZE = 50

/** DS(資料字典)恆置最前,其餘 schema 依名稱排序 */
function orderSchemas(names: string[]): string[] {
  return [...names].sort((a, b) => {
    if (a === 'DS') return -1
    if (b === 'DS') return 1
    return a.localeCompare(b)
  })
}

/** > 1000 統一顯示 1000+;否則精確值(後端已以 LIMIT 1001 探測封頂) */
function formatRowCount(value: number): string {
  return value > 1000 ? '1000+' : value.toLocaleString()
}

interface DatasetBrowserProps {
  dataset: Dataset
  title: string
  description: string
}

export function DatasetBrowser({
  dataset,
  title,
  description,
}: DatasetBrowserProps): React.ReactNode {
  const { isAdmin } = useAuth()
  const {
    data: schemas,
    isLoading: schemasLoading,
    isError: schemasError,
  } = useListDatasetSchemasQuery(dataset)

  const [activeSchema, setActiveSchema] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [hideEmpty, setHideEmpty] = useState(true)
  const [noticeMessage, setNoticeMessage] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const [refreshSnapshot, { isLoading: isRefreshing }] =
    useRefreshDatasetSnapshotMutation()
  const [syncAll, { isLoading: isSyncingAll }] = useSyncAllMutation()

  const orderedSchemas = useMemo(
    () => orderSchemas((schemas ?? []).map((s) => s.schema)),
    [schemas],
  )

  // 尚未手動選擇時,以載入後的排序第一個(DS 優先)當預設,不在 effect 內 setState
  const effectiveSchema = activeSchema ?? orderedSchemas[0] ?? null

  const handleSchemaSelect = useCallback((schema: string): void => {
    setActiveSchema(schema)
    setPage(1)
  }, [])

  const handlePageChange = useCallback((next: number): void => {
    setPage(next)
  }, [])

  const handleHideEmptyToggle = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>): void => {
      setHideEmpty(!event.target.checked)
      setPage(1)
    },
    [],
  )

  const handleRefresh = useCallback(async (): Promise<void> => {
    setActionError(null)
    setNoticeMessage(null)
    const result = await refreshSnapshot(dataset)
    if ('error' in result) {
      setActionError(
        extractApiErrorDetail(result.error, '重整快照失敗,請稍後再試'),
      )
      return
    }
    setNoticeMessage('已重整快照')
  }, [refreshSnapshot, dataset])

  const handleSyncAll = useCallback(async (): Promise<void> => {
    setActionError(null)
    setNoticeMessage(null)
    const result = await syncAll()
    if ('error' in result) {
      setActionError(
        extractApiErrorDetail(result.error, '全量同步觸發失敗,請稍後再試'),
      )
      return
    }
    setNoticeMessage('已送出全量同步')
  }, [syncAll])

  return (
    <section className="mx-auto flex max-w-7xl flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-foreground md:text-2xl">{title}</h1>
          <p className="mt-1 text-sm text-muted-foreground md:text-base">
            {description}
          </p>
        </div>
        {isAdmin ? (
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={handleSyncAll}
              disabled={isSyncingAll}
              className="df-btn-primary-soft"
            >
              全量同步
            </button>
            <button
              type="button"
              onClick={handleRefresh}
              disabled={isRefreshing}
              className="df-btn-outline"
            >
              重整快照
            </button>
          </div>
        ) : null}
      </div>

      {actionError !== null ? (
        <p
          role="alert"
          className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger md:text-base"
        >
          {actionError}
        </p>
      ) : null}
      {noticeMessage !== null ? (
        <p className="rounded-lg bg-success/15 px-3 py-2 text-sm text-success md:text-base">
          {noticeMessage}
        </p>
      ) : null}

      {schemasError ? (
        <p
          role="alert"
          className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger md:text-base"
        >
          無法連線到資料庫或讀取結構失敗,請確認 RDS 連線設定
        </p>
      ) : null}
      {schemasLoading ? (
        <p className="text-sm text-muted-foreground md:text-base">載入中…</p>
      ) : null}

      {schemas !== undefined && schemas.length === 0 ? (
        <div className="df-card p-8 text-center text-sm text-muted-foreground md:text-base">
          此資料庫尚無任何 schema / 資料表
        </div>
      ) : null}

      {orderedSchemas.length > 0 ? (
        <>
          <div className="flex flex-wrap gap-2">
            {orderedSchemas.map((schema) => {
              const count =
                schemas?.find((s) => s.schema === schema)?.table_count ?? 0
              const active = schema === effectiveSchema
              return (
                <button
                  key={schema}
                  type="button"
                  onClick={() => handleSchemaSelect(schema)}
                  aria-pressed={active}
                  title={getSchemaDescription(schema)}
                  className={`inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-medium transition-colors md:text-base ${
                    active
                      ? 'border-primary bg-primary text-primary-foreground'
                      : 'border-border bg-card text-foreground hover:bg-muted'
                  }`}
                >
                  {schema}
                  <span
                    className={`rounded-full px-2 py-0.5 text-sm ${active ? 'bg-white/20' : 'bg-muted text-muted-foreground'}`}
                  >
                    {count}
                  </span>
                </button>
              )
            })}
          </div>

          {effectiveSchema !== null ? (
            <p className="text-sm text-muted-foreground md:text-base">
              {getSchemaDescription(effectiveSchema)}
            </p>
          ) : null}

          <label className="flex w-fit items-center gap-2 text-sm font-medium text-foreground md:text-base">
            <input
              type="checkbox"
              checked={!hideEmpty}
              onChange={handleHideEmptyToggle}
              className="h-5 w-5 accent-[rgb(var(--primary))]"
            />
            顯示 0 筆表
          </label>

          {effectiveSchema !== null ? (
            <SchemaTables
              dataset={dataset}
              schema={effectiveSchema}
              page={page}
              hideEmpty={hideEmpty}
              canSync={isAdmin}
              onPageChange={handlePageChange}
            />
          ) : null}
        </>
      ) : null}
    </section>
  )
}

interface SchemaTablesProps {
  dataset: Dataset
  schema: string
  page: number
  hideEmpty: boolean
  canSync: boolean
  onPageChange: (page: number) => void
}

function SchemaTables({
  dataset,
  schema,
  page,
  hideEmpty,
  canSync,
  onPageChange,
}: SchemaTablesProps): React.ReactNode {
  const { data, isLoading, isError, isFetching } = useListDatasetTablesQuery({
    dataset,
    schema,
    page,
    pageSize: PAGE_SIZE,
    hideEmpty,
  })
  const [syncTable] = useSyncTableMutation()
  const [busyTable, setBusyTable] = useState<string | null>(null)
  const [syncError, setSyncError] = useState<string | null>(null)
  const [syncNotice, setSyncNotice] = useState<string | null>(null)

  const handleSync = useCallback(
    async (table: string): Promise<void> => {
      setSyncError(null)
      setSyncNotice(null)
      setBusyTable(table)
      const result = await syncTable({ schema, table })
      if ('error' in result) {
        setSyncError(
          extractApiErrorDetail(result.error, `同步 ${table} 失敗,請稍後再試`),
        )
      } else {
        setSyncNotice(`已送出 ${schema}.${table} 同步`)
      }
      setBusyTable(null)
    },
    [syncTable, schema],
  )

  if (isLoading) {
    return <p className="text-sm text-muted-foreground md:text-base">載入中…</p>
  }
  if (isError || data === undefined) {
    return (
      <p
        role="alert"
        className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger md:text-base"
      >
        載入 {schema} 的資料表失敗,請稍後再試
      </p>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      {syncError !== null ? (
        <p
          role="alert"
          className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger md:text-base"
        >
          {syncError}
        </p>
      ) : null}
      {syncNotice !== null ? (
        <p className="rounded-lg bg-success/15 px-3 py-2 text-sm text-success md:text-base">
          {syncNotice}
        </p>
      ) : null}
      <div
        className={`df-card overflow-x-auto transition-opacity ${isFetching ? 'opacity-60' : ''}`}
      >
        <table className="df-table min-w-[880px]">
          <thead>
            <tr className="border-b border-border bg-muted/50">
              <th className="df-th">資料表</th>
              <th className="df-th">業務資料名稱</th>
              <th className="df-th">欄位數</th>
              <th className="df-th">資料筆數</th>
              <th className="df-th">RDS 同步時間</th>
              <th className="df-th">ETL 轉換時間</th>
              {canSync ? <th className="df-th">操作</th> : null}
            </tr>
          </thead>
          <tbody>
            {data.items.map((table) => (
              <TableRow
                key={table.name}
                table={table}
                canSync={canSync}
                busy={busyTable === table.name}
                onSync={handleSync}
              />
            ))}
          </tbody>
        </table>
        {data.items.length === 0 ? (
          <p className="px-3 py-8 text-center text-sm text-muted-foreground md:text-base">
            {hideEmpty
              ? '此 schema 尚無資料表(或皆為 0 筆已隱藏,可切換「顯示 0 筆表」)'
              : '此 schema 尚無資料表'}
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

interface TableRowProps {
  table: TableSummary
  canSync: boolean
  busy: boolean
  onSync: (table: string) => void
}

const TableRow = memo(function TableRow({
  table,
  canSync,
  busy,
  onSync,
}: TableRowProps): React.ReactNode {
  const handleSync = useCallback((): void => {
    onSync(table.name)
  }, [onSync, table.name])

  return (
    <tr className="border-b border-border transition-colors last:border-b-0 hover:bg-muted/50">
      <td className="px-3 py-3 font-mono text-sm font-medium text-foreground md:text-base">
        {table.name}
      </td>
      <td className="df-td text-muted-foreground">
        {table.business_name ?? '—'}
      </td>
      <td className="df-td text-muted-foreground">{table.column_count}</td>
      <td className="df-td text-muted-foreground">
        {formatRowCount(table.row_count)}
      </td>
      <td className="df-td text-muted-foreground">
        {formatNullableDateTime(table.last_synced_at)}
      </td>
      <td className="df-td text-muted-foreground">
        {formatNullableDateTime(table.last_transformed_at)}
      </td>
      {canSync ? (
        <td className="px-3 py-3">
          <button
            type="button"
            onClick={handleSync}
            disabled={busy}
            className="df-btn-primary-soft min-h-[36px] px-3"
          >
            同步
          </button>
        </td>
      ) : null}
    </tr>
  )
})
