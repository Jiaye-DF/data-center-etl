'use client'

import { memo, useCallback, useId, useMemo, useState } from 'react'
import { skipToken } from '@reduxjs/toolkit/query'
import {
  TableSearchCombobox,
  type SuggestItem,
} from '@/components/common/TableSearchCombobox'
import {
  useDatasetSchemaSummaryQuery,
  useListDatasetSchemasQuery,
  useListDatasetTablesQuery,
  useRefreshDatasetSnapshotMutation,
  type Dataset,
  type TableFilters,
  type TableSummary,
} from '@/lib/api/datasetApi'
import {
  useSyncAllMutation,
  useSyncFilteredMutation,
  useSyncTableMutation,
} from '@/lib/api/syncApi'
import { useAuth } from '@/lib/auth/useAuth'
import { Pagination } from '@/components/common/Pagination'
import { ConfirmDialog } from '@/components/common/ConfirmDialog'
import { extractApiErrorDetail } from '@/utils/apiError'
import { formatNullableDateTime } from '@/utils/datetime'
import { getSchemaDescription } from '@/constants/schemaDescriptions'

const PAGE_SIZE = 50

/** 進階篩選預設值：僅顯示有資料，其餘不限 */
const DEFAULT_FILTERS: TableFilters = {
  rows: 'nonempty',
  synced: 'all',
  transformed: 'all',
  syncedBefore: '',
  transformedBefore: '',
  keyword: '',
  keywordExact: false,
  rowMin: '',
  rowMax: '',
}

interface SegmentedOption<T extends string> {
  value: T
  label: string
}

const ROWS_OPTIONS: ReadonlyArray<SegmentedOption<TableFilters['rows']>> = [
  { value: 'all', label: '全部' },
  { value: 'nonempty', label: '有資料' },
  { value: 'empty', label: '空表' },
]
const SYNCED_OPTIONS: ReadonlyArray<SegmentedOption<TableFilters['synced']>> = [
  { value: 'all', label: '全部' },
  { value: 'synced', label: '已同步' },
  { value: 'unsynced', label: '未同步' },
]
const TRANSFORMED_OPTIONS: ReadonlyArray<
  SegmentedOption<TableFilters['transformed']>
> = [
  { value: 'all', label: '全部' },
  { value: 'transformed', label: '已轉換' },
  { value: 'untransformed', label: '未轉換' },
]

/** DS（資料字典）恆置最前，其餘 schema 依名稱排序 */
function orderSchemas(names: string[]): string[] {
  return [...names].sort((a, b) => {
    if (a === 'DS') return -1
    if (b === 'DS') return 1
    return a.localeCompare(b)
  })
}

/** > 1000 統一顯示 1000+；否則精確值（後端已以 LIMIT 1001 探測封頂） */
function formatRowCount(value: number): string {
  return value > 1000 ? '1000+' : value.toLocaleString()
}

/** 通用膠囊篩選（pill；與「資料分類」同一視覺語言） */
function Segmented<T extends string>({
  options,
  value,
  onChange,
}: {
  options: ReadonlyArray<SegmentedOption<T>>
  value: T
  onChange: (value: T) => void
}): React.ReactNode {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((opt) => {
        const active = opt.value === value
        return (
          <button
            key={opt.value}
            type="button"
            onClick={() => onChange(opt.value)}
            aria-pressed={active}
            className={`rounded-full border px-4 py-1.5 text-sm font-medium transition-colors md:text-base ${
              active
                ? 'border-primary bg-primary text-primary-foreground'
                : 'border-border bg-card text-foreground hover:bg-muted'
            }`}
          >
            {opt.label}
          </button>
        )
      })}
    </div>
  )
}

/** 截止日（單一日期，YYYY-MM-DD）；搭配狀態 → 「是否在該日前（含）同步/轉換」 */
function CutoffDate({
  value,
  disabled,
  hint,
  ariaLabel,
  onChange,
}: {
  value: string
  disabled: boolean
  hint: string
  ariaLabel: string
  onChange: (value: string) => void
}): React.ReactNode {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span
        className={`text-sm ${disabled ? 'text-muted-foreground/50' : 'text-muted-foreground'}`}
      >
        截止日
      </span>
      <input
        type="date"
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        aria-label={ariaLabel}
        className="df-input min-h-[40px] w-full py-1.5 sm:w-44"
      />
      {!disabled && hint !== '' ? (
        <span className="text-sm text-muted-foreground">{hint}</span>
      ) : null}
    </div>
  )
}

/** 可摺疊卡片：標題列（accent bar + 標題 + 收合摘要 + chevron），內容可收合 */
function CollapsibleSection({
  title,
  summary,
  defaultOpen = true,
  children,
}: {
  title: string
  summary?: string
  defaultOpen?: boolean
  children: React.ReactNode
}): React.ReactNode {
  const [open, setOpen] = useState(defaultOpen)
  const contentId = useId()
  const toggle = useCallback((): void => setOpen((prev) => !prev), [])
  const hasSummary = summary !== undefined && summary !== ''

  return (
    <div className="df-card p-4 md:p-5">
      <h2 className="m-0">
        <button
          type="button"
          onClick={toggle}
          aria-expanded={open}
          aria-controls={contentId}
          className="flex w-full items-center gap-2 text-left"
        >
          <span aria-hidden className="h-4 w-1 rounded-full bg-primary" />
          <span className="text-sm font-semibold text-foreground md:text-base">
            {title}
          </span>
          {hasSummary ? (
            <span className="ml-auto truncate text-sm font-normal text-muted-foreground">
              {summary}
            </span>
          ) : null}
          <svg
            aria-hidden
            viewBox="0 0 20 20"
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
            className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform ${
              hasSummary ? 'ml-2' : 'ml-auto'
            } ${open ? 'rotate-180' : ''}`}
          >
            <path
              d="M5 7.5 10 12.5 15 7.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      </h2>
      {open ? (
        <div id={contentId} className="mt-4">
          {children}
        </div>
      ) : null}
    </div>
  )
}

/** 進階篩選內容：項目垂直排列，每列（項目名 + 水平選項 + 截止日）+ 清除 */
function AdvancedFilters({
  filters,
  suggestions,
  onChange,
  onReset,
  activeCount,
}: {
  filters: TableFilters
  suggestions: readonly SuggestItem[]
  onChange: (patch: Partial<TableFilters>) => void
  onReset: () => void
  activeCount: number
}): React.ReactNode {
  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <span className="w-32 shrink-0 text-sm font-medium text-foreground md:text-base">
          資料表搜尋
        </span>
        <TableSearchCombobox
          value={filters.keyword}
          suggestions={suggestions}
          onCommit={(keyword, exact) =>
            onChange({ keyword, keywordExact: exact })
          }
        />
      </div>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <span className="w-32 shrink-0 text-sm font-medium text-foreground md:text-base">
          資料總筆數
        </span>
        <Segmented
          options={ROWS_OPTIONS}
          value={filters.rows}
          onChange={(rows) => onChange({ rows })}
        />
      </div>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <span className="w-32 shrink-0 text-sm font-medium text-foreground md:text-base">
          筆數區間
        </span>
        <input
          type="number"
          min={0}
          max={1000}
          value={filters.rowMin}
          onChange={(e) => onChange({ rowMin: e.target.value })}
          aria-label="資料總筆數下限"
          placeholder="下限"
          className="df-input min-h-[40px] w-full py-1.5 sm:w-28"
        />
        <span className="text-sm text-muted-foreground">至</span>
        <input
          type="number"
          min={0}
          max={1000}
          value={filters.rowMax}
          onChange={(e) => onChange({ rowMax: e.target.value })}
          aria-label="資料總筆數上限"
          placeholder="上限"
          className="df-input min-h-[40px] w-full py-1.5 sm:w-28"
        />
        <span className="text-sm text-muted-foreground">
          (含端點;超過 1000 一律視為 1000+)
        </span>
      </div>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <span className="w-32 shrink-0 text-sm font-medium text-foreground md:text-base">
          RDS 同步時間
        </span>
        <Segmented
          options={SYNCED_OPTIONS}
          value={filters.synced}
          onChange={(synced) =>
            onChange(synced === 'all' ? { synced, syncedBefore: '' } : { synced })
          }
        />
        <CutoffDate
          value={filters.syncedBefore}
          disabled={filters.synced === 'all'}
          hint={filters.synced === 'unsynced' ? '（到該日仍未同步）' : '（該日前已同步）'}
          ariaLabel="RDS 同步截止日"
          onChange={(syncedBefore) => onChange({ syncedBefore })}
        />
      </div>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <span className="w-32 shrink-0 text-sm font-medium text-foreground md:text-base">
          ETL 轉換時間
        </span>
        <Segmented
          options={TRANSFORMED_OPTIONS}
          value={filters.transformed}
          onChange={(transformed) =>
            onChange(
              transformed === 'all'
                ? { transformed, transformedBefore: '' }
                : { transformed },
            )
          }
        />
        <CutoffDate
          value={filters.transformedBefore}
          disabled={filters.transformed === 'all'}
          hint={
            filters.transformed === 'untransformed'
              ? '（到該日仍未轉換）'
              : '（該日前已轉換）'
          }
          ariaLabel="ETL 轉換截止日"
          onChange={(transformedBefore) => onChange({ transformedBefore })}
        />
      </div>

      <div className="flex items-center justify-end">
        <button
          type="button"
          onClick={onReset}
          disabled={activeCount === 0}
          className="df-btn-outline min-h-[36px] px-3"
        >
          清除篩選
        </button>
      </div>
    </div>
  )
}

/** 資料總筆數分布概覽:總表數 / 有資料 / 空表 / 1000+(依當前 schema;不做筆數加總) */
function SchemaSummaryBar({
  dataset,
  schema,
}: {
  dataset: Dataset
  schema: string
}): React.ReactNode {
  const { data, isFetching } = useDatasetSchemaSummaryQuery({ dataset, schema })
  const stats: ReadonlyArray<{ label: string; value: number | null }> = [
    { label: '總表數', value: data?.table_count ?? null },
    { label: '有資料', value: data?.nonempty_count ?? null },
    { label: '空表', value: data?.empty_count ?? null },
    { label: '1000+', value: data?.capped_count ?? null },
  ]
  return (
    <div
      className={`df-card flex flex-wrap gap-6 p-4 md:p-5 transition-opacity ${
        isFetching ? 'opacity-60' : ''
      }`}
    >
      {stats.map((s) => (
        <div key={s.label} className="flex min-w-[80px] flex-col gap-1">
          <span className="text-sm text-muted-foreground">{s.label}</span>
          <span className="text-lg font-semibold text-foreground md:text-xl">
            {s.value === null ? '—' : s.value.toLocaleString()}
          </span>
        </div>
      ))}
    </div>
  )
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
  const [filters, setFilters] = useState<TableFilters>(DEFAULT_FILTERS)
  const [noticeMessage, setNoticeMessage] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [openDialog, setOpenDialog] = useState<
    'sync' | 'snapshot' | 'filtered' | null
  >(null)

  const closeDialog = useCallback((): void => setOpenDialog(null), [])

  const [refreshSnapshot, { isLoading: isRefreshing }] =
    useRefreshDatasetSnapshotMutation()
  const [syncAll, { isLoading: isSyncingAll }] = useSyncAllMutation()
  const [syncFiltered, { isLoading: isSyncingFiltered }] =
    useSyncFilteredMutation()

  const orderedSchemas = useMemo(
    () => orderSchemas((schemas ?? []).map((s) => s.schema)),
    [schemas],
  )

  // 尚未手動選擇時，以載入後的排序第一個（DS 優先）當預設，不在 effect 內 setState
  const effectiveSchema = activeSchema ?? orderedSchemas[0] ?? null

  // combobox 建議：取當前 schema + 其他篩選（不含關鍵字）的表名 / 業務名
  const { data: suggestData } = useListDatasetTablesQuery(
    effectiveSchema !== null
      ? {
          dataset,
          schema: effectiveSchema,
          page: 1,
          pageSize: PAGE_SIZE,
          ...filters,
          keyword: '',
        }
      : skipToken,
  )
  const nameSuggestions = useMemo((): SuggestItem[] => {
    const seen = new Set<string>()
    const out: SuggestItem[] = []
    for (const item of suggestData?.items ?? []) {
      if (seen.has(item.name)) continue
      seen.add(item.name)
      out.push({ name: item.name, business_name: item.business_name })
    }
    return out
  }, [suggestData])

  const activeFilterCount = useMemo((): number => {
    let count = 0
    if (filters.rows !== DEFAULT_FILTERS.rows) count += 1
    if (filters.synced !== 'all') count += 1
    if (filters.transformed !== 'all') count += 1
    if (filters.syncedBefore !== '') count += 1
    if (filters.transformedBefore !== '') count += 1
    if (filters.keyword !== '') count += 1
    if (filters.rowMin !== '' || filters.rowMax !== '') count += 1
    return count
  }, [filters])

  const handleSchemaSelect = useCallback((schema: string): void => {
    setActiveSchema(schema)
    setPage(1)
  }, [])

  const handlePageChange = useCallback((next: number): void => {
    setPage(next)
  }, [])

  const updateFilters = useCallback((patch: Partial<TableFilters>): void => {
    setFilters((prev) => ({ ...prev, ...patch }))
    setPage(1)
  }, [])

  const resetFilters = useCallback((): void => {
    setFilters(DEFAULT_FILTERS)
    setPage(1)
  }, [])

  const handleRefresh = useCallback(async (): Promise<void> => {
    setOpenDialog(null)
    setActionError(null)
    setNoticeMessage(null)
    const result = await refreshSnapshot(dataset)
    if ('error' in result) {
      setActionError(
        extractApiErrorDetail(result.error, '從 RDS 同步快照資料失敗，請稍後再試'),
      )
      return
    }
    setNoticeMessage('已從 RDS 同步快照資料')
  }, [refreshSnapshot, dataset])

  const handleSyncAll = useCallback(async (): Promise<void> => {
    setOpenDialog(null)
    setActionError(null)
    setNoticeMessage(null)
    const result = await syncAll()
    if ('error' in result) {
      setActionError(
        extractApiErrorDetail(result.error, '全量同步觸發失敗，請稍後再試'),
      )
      return
    }
    setNoticeMessage('已送出全量同步，由背景 worker 執行')
  }, [syncAll])

  const handleSyncFiltered = useCallback(async (): Promise<void> => {
    setOpenDialog(null)
    setActionError(null)
    setNoticeMessage(null)
    if (effectiveSchema === null) return
    const result = await syncFiltered({ schema: effectiveSchema, ...filters })
    if ('error' in result) {
      setActionError(
        extractApiErrorDetail(result.error, '篩選同步觸發失敗，請稍後再試'),
      )
      return
    }
    const matched = result.data.matched ?? 0
    setNoticeMessage(
      matched === 0
        ? '目前篩選條件沒有符合的資料表，未觸發同步'
        : `已送出篩選同步（${effectiveSchema}，符合 ${matched} 張表），由背景 worker 執行`,
    )
  }, [syncFiltered, effectiveSchema, filters])

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
            {dataset === 'source' ? (
              <button
                type="button"
                onClick={() => setOpenDialog('sync')}
                disabled={isSyncingAll}
                className="df-btn-primary-soft"
              >
                {isSyncingAll ? '同步中…' : '全量同步'}
              </button>
            ) : null}
            <button
              type="button"
              onClick={() => setOpenDialog('snapshot')}
              disabled={isRefreshing}
              className="df-btn-outline"
            >
              {isRefreshing
                ? '同步中…'
                : dataset === 'target'
                  ? 'ETL 快照同步'
                  : '快照同步'}
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

      <ConfirmDialog
        open={openDialog === 'sync'}
        title="全量同步"
        confirmLabel="開始全量同步"
        confirmDisabled={isSyncingAll}
        tone="danger"
        onConfirm={handleSyncAll}
        onCancel={closeDialog}
      >
        <p className="text-foreground">
          把 RDS 裡所有資料表，整批做 ETL 同步到資料中心。
        </p>
        <div className="rounded-lg border border-danger/30 bg-danger/10 p-4 text-danger">
          會用來源最新內容整批覆蓋資料中心的資料（資料量大、可能要跑一段時間）。確定現在要執行嗎？
        </div>
      </ConfirmDialog>

      <ConfirmDialog
        open={openDialog === 'snapshot'}
        title={dataset === 'target' ? 'ETL 快照同步' : '快照同步'}
        confirmLabel="開始更新"
        confirmDisabled={isRefreshing}
        onConfirm={handleRefresh}
        onCancel={closeDialog}
      >
        <p className="text-foreground">
          重新從 RDS 讀取最新的資料表清單，更新這個頁面的顯示。
        </p>
        <p>動作很快，只更新清單，不會更動或搬移任何資料。</p>
      </ConfirmDialog>

      <ConfirmDialog
        open={openDialog === 'filtered'}
        title="僅同步篩選資料表"
        confirmLabel="開始同步"
        confirmDisabled={isSyncingFiltered}
        tone="danger"
        onConfirm={handleSyncFiltered}
        onCancel={closeDialog}
      >
        <p className="text-foreground">
          只把「{effectiveSchema ?? '—'}」目前
          <strong className="text-danger">符合進階篩選條件</strong>
          的資料表，鏡像同步到資料中心。
        </p>
        <div className="rounded-lg border border-danger/30 bg-danger/10 p-4 text-danger">
          會用來源最新內容覆蓋這些表在資料中心的資料。確定要同步目前篩選出的資料表嗎？
        </div>
      </ConfirmDialog>

      {schemasError ? (
        <p
          role="alert"
          className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger md:text-base"
        >
          無法連線到資料庫或讀取結構失敗，請確認 RDS 連線設定
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
          <CollapsibleSection
            title="資料分類"
            summary={effectiveSchema !== null ? `目前：${effectiveSchema}` : undefined}
          >
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
          </CollapsibleSection>

          {effectiveSchema !== null ? (
            <SchemaSummaryBar dataset={dataset} schema={effectiveSchema} />
          ) : null}

          <CollapsibleSection
            title="進階篩選"
            defaultOpen={false}
            summary={
              activeFilterCount === 0 ? '未套用' : `${activeFilterCount} 項條件`
            }
          >
            <AdvancedFilters
              filters={filters}
              suggestions={nameSuggestions}
              onChange={updateFilters}
              onReset={resetFilters}
              activeCount={activeFilterCount}
            />
          </CollapsibleSection>

          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-sm font-semibold text-foreground md:text-base">
              {effectiveSchema !== null ? `${effectiveSchema} 資料表` : '資料表'}
            </h2>
            {isAdmin && dataset === 'source' ? (
              <button
                type="button"
                onClick={() => setOpenDialog('filtered')}
                disabled={isSyncingFiltered}
                className="df-btn-primary-soft min-h-[36px] px-3"
              >
                {isSyncingFiltered ? '同步中…' : '僅同步篩選資料表'}
              </button>
            ) : null}
          </div>

          {effectiveSchema !== null ? (
            <SchemaTables
              dataset={dataset}
              schema={effectiveSchema}
              page={page}
              filters={filters}
              hasActiveFilter={activeFilterCount > 0}
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
  filters: TableFilters
  hasActiveFilter: boolean
  canSync: boolean
  onPageChange: (page: number) => void
}

function SchemaTables({
  dataset,
  schema,
  page,
  filters,
  hasActiveFilter,
  canSync,
  onPageChange,
}: SchemaTablesProps): React.ReactNode {
  const { data, isLoading, isError, isFetching } = useListDatasetTablesQuery({
    dataset,
    schema,
    page,
    pageSize: PAGE_SIZE,
    ...filters,
  })
  // target 已是 ETL 產物,不記同步/轉換生命週期(那兩欄恆空)→ 改顯示快照擷取時間
  const isTarget = dataset === 'target'
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
          extractApiErrorDetail(result.error, `同步 ${table} 失敗，請稍後再試`),
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
        載入 {schema} 的資料表失敗，請稍後再試
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
        <table className="df-table min-w-[760px]">
          <thead>
            <tr className="border-b border-border bg-muted/50">
              <th className="df-th">資料表</th>
              <th className="df-th">業務資料表名稱</th>
              <th className="df-th">資料總筆數</th>
              {isTarget ? (
                <th className="df-th">快照時間</th>
              ) : (
                <>
                  <th className="df-th">RDS 同步時間</th>
                  <th className="df-th">ETL 轉換時間</th>
                </>
              )}
              {canSync ? <th className="df-th">操作</th> : null}
            </tr>
          </thead>
          <tbody>
            {data.items.map((table) => (
              <TableRow
                key={table.name}
                table={table}
                isTarget={isTarget}
                canSync={canSync}
                busy={busyTable === table.name}
                onSync={handleSync}
              />
            ))}
          </tbody>
        </table>
        {data.items.length === 0 ? (
          <p className="px-3 py-8 text-center text-sm text-muted-foreground md:text-base">
            {hasActiveFilter
              ? '查無符合篩選條件的資料表（可調整或清除進階篩選）'
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
  isTarget: boolean
  canSync: boolean
  busy: boolean
  onSync: (table: string) => void
}

const TableRow = memo(function TableRow({
  table,
  isTarget,
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
      <td className="df-td text-muted-foreground">
        {formatRowCount(table.row_count)}
      </td>
      {isTarget ? (
        <td className="df-td text-muted-foreground">
          {formatNullableDateTime(table.snapshot_at)}
        </td>
      ) : (
        <>
          <td className="df-td text-muted-foreground">
            {formatNullableDateTime(table.last_synced_at)}
          </td>
          <td className="df-td text-muted-foreground">
            {formatNullableDateTime(table.last_transformed_at)}
          </td>
        </>
      )}
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
