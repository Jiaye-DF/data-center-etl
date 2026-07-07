'use client'

import { memo, useCallback, useMemo, useState } from 'react'
import {
  useGetCoverageSchemasQuery,
  useListCoverageTablesQuery,
  useSetTableExclusionMutation,
  type CoverageInclusion,
  type CoverageLastResult,
  type CoverageScheduleInfo,
  type TableCoverageItem,
} from '@/lib/api/scheduleCoverageApi'
import { useAuth } from '@/lib/auth/useAuth'
import { Pagination } from '@/components/common/Pagination'
import { extractApiErrorDetail } from '@/utils/apiError'
import { formatDateTime, formatNullableDateTime } from '@/utils/datetime'
import { describeCron, nextRunFromCron } from '@/utils/cron'

const PAGE_SIZE = 50

interface SegmentedOption<T extends string> {
  value: T
  label: string
}

const INCLUSION_OPTIONS: ReadonlyArray<SegmentedOption<CoverageInclusion>> = [
  { value: 'all', label: '全部' },
  { value: 'included', label: '已納入' },
  { value: 'excluded', label: '已排除' },
]

const LAST_RESULT_OPTIONS: ReadonlyArray<SegmentedOption<CoverageLastResult>> = [
  { value: 'all', label: '全部' },
  { value: 'success', label: '成功' },
  { value: 'failed', label: '失敗' },
  { value: 'never', label: '未跑' },
]

/** DS(資料字典)恆置最前,其餘 schema 依名稱排序 */
function orderSchemaNames(names: string[]): string[] {
  return [...names].sort((a, b) => {
    if (a === 'DS') return -1
    if (b === 'DS') return 1
    return a.localeCompare(b)
  })
}

function pad2(value: number): string {
  return value.toString().padStart(2, '0')
}

/** 下次執行:取第一個排程 cron 推算本地近似時間,轉為 formatDateTime 可讀字串 */
function nextRunDisplay(schedules: CoverageScheduleInfo[]): string {
  const first = schedules[0]
  if (first === undefined) return '—'
  const next = nextRunFromCron(first.cron_expr)
  if (next === null) return '—'
  const wall = `${next.getFullYear()}-${pad2(next.getMonth() + 1)}-${pad2(
    next.getDate(),
  )}T${pad2(next.getHours())}:${pad2(next.getMinutes())}:${pad2(next.getSeconds())}`
  return formatDateTime(wall)
}

/** 上次結果 status → 中文標籤 + badge 樣式(success/failed 以外或 null = 未跑) */
interface LastRunPresentation {
  label: string
  className: string
}

function resolveLastRun(status: string | null): LastRunPresentation {
  switch (status) {
    case 'success':
      return { label: '成功', className: 'bg-success/15 text-success' }
    case 'failed':
      return { label: '失敗', className: 'bg-danger/10 text-danger' }
    default:
      return { label: '未跑', className: 'bg-muted text-muted-foreground' }
  }
}

/** 通用膠囊篩選(與資料管理頁同一視覺語言) */
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

export function ScheduleCoverageBrowser(): React.ReactNode {
  const { isAdmin } = useAuth()
  const {
    data: schemasData,
    isLoading: schemasLoading,
    isError: schemasError,
  } = useGetCoverageSchemasQuery()

  const [activeSchema, setActiveSchema] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [inclusion, setInclusion] = useState<CoverageInclusion>('all')
  const [lastResult, setLastResult] = useState<CoverageLastResult>('all')
  const [keyword, setKeyword] = useState('')

  const orderedSchemas = useMemo(() => {
    const items = schemasData?.items ?? []
    const order = orderSchemaNames(items.map((s) => s.schema_name))
    return order
      .map((name) => items.find((s) => s.schema_name === name))
      .filter((s): s is NonNullable<typeof s> => s !== undefined)
  }, [schemasData])

  const effectiveSchema = activeSchema ?? orderedSchemas[0]?.schema_name ?? null
  const schedules = useMemo(
    () => schemasData?.schedules ?? [],
    [schemasData],
  )
  const hasEnabledSchedule = schemasData?.has_enabled_schedule ?? false

  const scheduleSummary = useMemo(
    () => schedules.map((s) => describeCron(s.cron_expr)).join('、'),
    [schedules],
  )

  const handleSchemaSelect = useCallback((schema: string): void => {
    setActiveSchema(schema)
    setPage(1)
  }, [])

  const handleInclusionChange = useCallback((value: CoverageInclusion): void => {
    setInclusion(value)
    setPage(1)
  }, [])

  const handleLastResultChange = useCallback(
    (value: CoverageLastResult): void => {
      setLastResult(value)
      setPage(1)
    },
    [],
  )

  const handleKeywordChange = useCallback((value: string): void => {
    setKeyword(value)
    setPage(1)
  }, [])

  const handlePageChange = useCallback((next: number): void => {
    setPage(next)
  }, [])

  const showUncovered = useCallback((): void => {
    setInclusion('excluded')
    setPage(1)
  }, [])

  return (
    <section className="mx-auto flex max-w-7xl flex-col gap-6">
      <div>
        <h1 className="text-xl font-bold text-foreground md:text-2xl">
          排程涵蓋(依表檢視)
        </h1>
        <p className="mt-1 text-sm text-muted-foreground md:text-base">
          依 schema 檢視每張資料表是否被排程涵蓋,可逐表排除,並查看上次結果與下次執行時間
        </p>
      </div>

      {hasEnabledSchedule ? (
        <div className="rounded-lg bg-info/10 px-3 py-2 text-sm text-info md:text-base">
          目前啟用排程:{scheduleSummary}
        </div>
      ) : (
        <div
          role="alert"
          className="rounded-lg bg-warning/15 px-3 py-2 text-sm text-warning md:text-base"
        >
          目前無啟用排程,所有表未被涵蓋
        </div>
      )}

      {schemasError ? (
        <p
          role="alert"
          className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger md:text-base"
        >
          載入排程涵蓋資料失敗,請稍後再試
        </p>
      ) : null}
      {schemasLoading ? (
        <p className="text-sm text-muted-foreground md:text-base">載入中…</p>
      ) : null}

      {schemasData !== undefined && orderedSchemas.length === 0 ? (
        <div className="df-card p-8 text-center text-sm text-muted-foreground md:text-base">
          目前沒有可檢視的資料表
        </div>
      ) : null}

      {orderedSchemas.length > 0 ? (
        <>
          <div className="df-card p-4 md:p-5">
            <p className="mb-3 text-sm font-semibold text-foreground md:text-base">
              資料分類
            </p>
            <div className="flex flex-wrap gap-2">
              {orderedSchemas.map((s) => {
                const active = s.schema_name === effectiveSchema
                return (
                  <button
                    key={s.schema_name}
                    type="button"
                    onClick={() => handleSchemaSelect(s.schema_name)}
                    aria-pressed={active}
                    className={`inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-medium transition-colors md:text-base ${
                      active
                        ? 'border-primary bg-primary text-primary-foreground'
                        : 'border-border bg-card text-foreground hover:bg-muted'
                    }`}
                  >
                    {s.schema_name}
                    <span
                      className={`rounded-full px-2 py-0.5 text-sm ${active ? 'bg-white/20' : 'bg-muted text-muted-foreground'}`}
                    >
                      {s.table_count}
                    </span>
                    {s.excluded_count > 0 ? (
                      <span
                        className={`rounded-full px-2 py-0.5 text-sm ${active ? 'bg-white/20' : 'bg-warning/15 text-warning'}`}
                        title="已排除的資料表數"
                      >
                        排除 {s.excluded_count}
                      </span>
                    ) : null}
                  </button>
                )
              })}
            </div>
          </div>

          <div className="df-card flex flex-col gap-4 p-4 md:p-5">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
              <span className="w-24 shrink-0 text-sm font-medium text-foreground md:text-base">
                納入狀態
              </span>
              <Segmented
                options={INCLUSION_OPTIONS}
                value={inclusion}
                onChange={handleInclusionChange}
              />
              <button
                type="button"
                onClick={showUncovered}
                className="df-btn-outline min-h-[36px] px-3"
              >
                找未被涵蓋的表
              </button>
            </div>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
              <span className="w-24 shrink-0 text-sm font-medium text-foreground md:text-base">
                上次結果
              </span>
              <Segmented
                options={LAST_RESULT_OPTIONS}
                value={lastResult}
                onChange={handleLastResultChange}
              />
            </div>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
              <span className="w-24 shrink-0 text-sm font-medium text-foreground md:text-base">
                關鍵字
              </span>
              <input
                type="search"
                value={keyword}
                onChange={(e) => handleKeywordChange(e.target.value)}
                placeholder="資料表名稱或業務名稱"
                aria-label="資料表 / 業務名稱搜尋"
                className="df-input w-full sm:w-96"
              />
            </div>
          </div>

          <h2 className="text-sm font-semibold text-foreground md:text-base">
            {effectiveSchema !== null ? `${effectiveSchema} 資料表` : '資料表'}
          </h2>

          {effectiveSchema !== null ? (
            <CoverageTables
              schema={effectiveSchema}
              page={page}
              inclusion={inclusion}
              lastResult={lastResult}
              keyword={keyword}
              schedules={schedules}
              canEdit={isAdmin}
              onPageChange={handlePageChange}
            />
          ) : null}
        </>
      ) : null}
    </section>
  )
}

interface CoverageTablesProps {
  schema: string
  page: number
  inclusion: CoverageInclusion
  lastResult: CoverageLastResult
  keyword: string
  schedules: CoverageScheduleInfo[]
  canEdit: boolean
  onPageChange: (page: number) => void
}

function CoverageTables({
  schema,
  page,
  inclusion,
  lastResult,
  keyword,
  schedules,
  canEdit,
  onPageChange,
}: CoverageTablesProps): React.ReactNode {
  const { data, isLoading, isError, isFetching } = useListCoverageTablesQuery({
    schema,
    page,
    pageSize: PAGE_SIZE,
    inclusion,
    lastResult,
    keyword,
  })
  const [setExclusion] = useSetTableExclusionMutation()
  const [busyUid, setBusyUid] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const scheduleLabel = useMemo(
    () => schedules.map((s) => describeCron(s.cron_expr)).join('、'),
    [schedules],
  )
  const nextRun = useMemo(() => nextRunDisplay(schedules), [schedules])

  const handleToggle = useCallback(
    async (item: TableCoverageItem): Promise<void> => {
      setActionError(null)
      setBusyUid(item.uid)
      const result = await setExclusion({
        uid: item.uid,
        excluded: !item.sync_excluded,
      })
      if ('error' in result) {
        setActionError(
          extractApiErrorDetail(
            result.error,
            `更新 ${item.table_name} 的排除狀態失敗,請稍後再試`,
          ),
        )
      }
      setBusyUid(null)
    },
    [setExclusion],
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
      {actionError !== null ? (
        <p
          role="alert"
          className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger md:text-base"
        >
          {actionError}
        </p>
      ) : null}
      <div
        className={`df-card overflow-x-auto transition-opacity ${isFetching ? 'opacity-60' : ''}`}
      >
        <table className="df-table min-w-[960px]">
          <thead>
            <tr className="border-b border-border bg-muted/50">
              <th className="df-th">資料表</th>
              <th className="df-th">業務資料表名稱</th>
              <th className="df-th">納入排程</th>
              <th className="df-th">套用排程</th>
              <th className="df-th">上次同步時間</th>
              <th className="df-th">上次結果</th>
              <th className="df-th">下次執行</th>
              {canEdit ? <th className="df-th">操作</th> : null}
            </tr>
          </thead>
          <tbody>
            {data.items.map((item) => (
              <CoverageRow
                key={item.uid}
                item={item}
                scheduleLabel={scheduleLabel}
                nextRun={nextRun}
                canEdit={canEdit}
                busy={busyUid === item.uid}
                onToggle={handleToggle}
              />
            ))}
          </tbody>
        </table>
        {data.items.length === 0 ? (
          <p className="px-3 py-8 text-center text-sm text-muted-foreground md:text-base">
            查無符合條件的資料表(可調整篩選)
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

interface CoverageRowProps {
  item: TableCoverageItem
  scheduleLabel: string
  nextRun: string
  canEdit: boolean
  busy: boolean
  onToggle: (item: TableCoverageItem) => void
}

const CoverageRow = memo(function CoverageRow({
  item,
  scheduleLabel,
  nextRun,
  canEdit,
  busy,
  onToggle,
}: CoverageRowProps): React.ReactNode {
  const handleToggle = useCallback((): void => {
    onToggle(item)
  }, [onToggle, item])

  const lastRun = resolveLastRun(item.last_run_status)
  const covered = item.included && !item.sync_excluded

  return (
    <tr className="border-b border-border transition-colors last:border-b-0 hover:bg-muted/50">
      <td className="px-3 py-3">
        <p className="font-mono text-sm font-medium text-foreground md:text-base">
          {item.table_name}
        </p>
        <p className="mt-0.5 text-xs text-muted-foreground">{item.schema_name}</p>
      </td>
      <td className="df-td text-muted-foreground">
        {item.business_name ?? '—'}
      </td>
      <td className="px-3 py-3">
        {item.sync_excluded ? (
          <span className="df-badge bg-muted text-muted-foreground">已排除</span>
        ) : (
          <span className="df-badge bg-success/15 text-success">已納入</span>
        )}
      </td>
      <td className="df-td text-muted-foreground">
        {covered ? scheduleLabel : '—'}
      </td>
      <td className="df-td text-muted-foreground">
        {formatNullableDateTime(item.last_synced_at)}
      </td>
      <td className="px-3 py-3">
        <span className={`df-badge ${lastRun.className}`}>{lastRun.label}</span>
      </td>
      <td className="df-td text-muted-foreground">{covered ? nextRun : '—'}</td>
      {canEdit ? (
        <td className="px-3 py-3">
          <button
            type="button"
            onClick={handleToggle}
            disabled={busy}
            className={`min-h-[36px] px-3 ${
              item.sync_excluded ? 'df-btn-primary-soft' : 'df-btn-warning-soft'
            }`}
          >
            {item.sync_excluded ? '納入' : '排除'}
          </button>
        </td>
      ) : null}
    </tr>
  )
})
