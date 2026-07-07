'use client'

import { memo, useCallback, useId, useMemo, useState } from 'react'
import {
  useBatchSetEnabledMutation,
  useGetScheduleSchemasQuery,
  useListScheduleTablesQuery,
  useSetScheduleEnabledMutation,
  useUpdateScheduleMutation,
  type EnabledFilter,
  type LastResultFilter,
  type ScheduleTableView,
} from '@/lib/api/scheduleApi'
import { useAuth } from '@/lib/auth/useAuth'
import { Pagination } from '@/components/common/Pagination'
import { ConfirmDialog } from '@/components/common/ConfirmDialog'
import { StatusBadge } from '@/components/common/StatusBadge'
import {
  ScheduleFormDialog,
  type ScheduleEditInitial,
  type ScheduleEditPayload,
} from '@/components/schedules/ScheduleFormDialog'
import { extractApiErrorDetail } from '@/utils/apiError'
import { formatNullableDateTime } from '@/utils/datetime'
import { describeCron, nextRunFromCron } from '@/utils/cron'
import { getSchemaDescription } from '@/constants/schemaDescriptions'

const PAGE_SIZE = 20

/** 逐表視角進階篩選狀態 */
interface ScheduleFilters {
  enabled: EnabledFilter
  lastResult: LastResultFilter
  keyword: string
}

const DEFAULT_FILTERS: ScheduleFilters = {
  enabled: 'all',
  lastResult: 'all',
  keyword: '',
}

interface SegmentedOption<T extends string> {
  value: T
  label: string
}

const ENABLED_OPTIONS: ReadonlyArray<SegmentedOption<EnabledFilter>> = [
  { value: 'all', label: '全部' },
  { value: 'enabled', label: '已啟用' },
  { value: 'disabled', label: '已停用' },
]
const LAST_RESULT_OPTIONS: ReadonlyArray<SegmentedOption<LastResultFilter>> = [
  { value: 'all', label: '全部' },
  { value: 'success', label: '成功' },
  { value: 'failed', label: '失敗' },
  { value: 'never', label: '未跑' },
]

/** DS(資料字典)恆置最前,其餘 schema 依名稱排序 */
function orderSchemas(names: string[]): string[] {
  return [...names].sort((a, b) => {
    if (a === 'DS') return -1
    if (b === 'DS') return 1
    return a.localeCompare(b)
  })
}

function pad2(value: number): string {
  return value.toString().padStart(2, '0')
}

/** 依 cron 推算下次執行(Date → YYYY/MM/DD HH:mm);停用或無法解析回「—」 */
function formatNextRun(cronExpr: string | null, isEnabled: boolean | null): string {
  if (cronExpr === null || isEnabled !== true) return '—'
  const next = nextRunFromCron(cronExpr)
  if (next === null) return '—'
  return `${next.getFullYear()}/${pad2(next.getMonth() + 1)}/${pad2(next.getDate())} ${pad2(next.getHours())}:${pad2(next.getMinutes())}`
}

/** 上次結果 badge:null → 灰「未跑」;其餘走通用 StatusBadge(success 綠 / failed 紅) */
function LastResultBadge({ status }: { status: string | null }): React.ReactNode {
  if (status === null) {
    return <span className="df-badge bg-muted text-muted-foreground">未跑</span>
  }
  return <StatusBadge status={status} />
}

/** 通用膠囊篩選(pill;與資料管理頁同一視覺語言) */
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

/** 可摺疊卡片:標題列(accent bar + 標題 + 收合摘要 + chevron),內容可收合 */
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

/** 進階篩選內容:啟用狀態 / 上次結果 / 關鍵字 + 清除 */
function AdvancedFilters({
  filters,
  onChange,
  onReset,
  activeCount,
}: {
  filters: ScheduleFilters
  onChange: (patch: Partial<ScheduleFilters>) => void
  onReset: () => void
  activeCount: number
}): React.ReactNode {
  const handleKeywordChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>): void => {
      onChange({ keyword: event.target.value })
    },
    [onChange],
  )

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <span className="w-24 shrink-0 text-sm font-medium text-foreground md:text-base">
          資料表搜尋
        </span>
        <input
          type="search"
          value={filters.keyword}
          onChange={handleKeywordChange}
          placeholder="輸入業務名稱或資料表名稱搜尋"
          aria-label="業務名稱 / 資料表名稱搜尋"
          className="df-input w-full sm:w-96"
        />
      </div>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <span className="w-24 shrink-0 text-sm font-medium text-foreground md:text-base">
          啟用狀態
        </span>
        <Segmented
          options={ENABLED_OPTIONS}
          value={filters.enabled}
          onChange={(enabled) => onChange({ enabled })}
        />
      </div>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <span className="w-24 shrink-0 text-sm font-medium text-foreground md:text-base">
          上次結果
        </span>
        <Segmented
          options={LAST_RESULT_OPTIONS}
          value={filters.lastResult}
          onChange={(lastResult) => onChange({ lastResult })}
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

interface ScheduleRowProps {
  row: ScheduleTableView
  canEdit: boolean
  busy: boolean
  onToggle: (row: ScheduleTableView) => void
  onEdit: (row: ScheduleTableView) => void
}

const ScheduleRow = memo(function ScheduleRow({
  row,
  canEdit,
  busy,
  onToggle,
  onEdit,
}: ScheduleRowProps): React.ReactNode {
  const handleToggle = useCallback((): void => {
    onToggle(row)
  }, [onToggle, row])
  const handleEdit = useCallback((): void => {
    onEdit(row)
  }, [onEdit, row])

  const hasSchedule = row.schedule_uid !== null

  return (
    <tr className="border-b border-border transition-colors last:border-b-0 hover:bg-muted/50">
      <td className="px-3 py-3 font-mono text-sm font-medium text-foreground md:text-base">
        {row.table_name}
      </td>
      <td className="df-td text-muted-foreground">{row.business_name ?? '—'}</td>
      <td className="px-3 py-3">
        {!hasSchedule ? (
          <span className="text-muted-foreground">—</span>
        ) : canEdit ? (
          <button
            type="button"
            onClick={handleToggle}
            disabled={busy}
            aria-pressed={row.is_enabled === true}
            className={`rounded-full border px-3 py-1 text-sm font-medium transition-colors ${
              row.is_enabled === true
                ? 'border-success bg-success/15 text-success hover:bg-success/25'
                : 'border-border bg-muted text-muted-foreground hover:bg-muted/70'
            }`}
          >
            {row.is_enabled === true ? '啟用' : '停用'}
          </button>
        ) : (
          <span
            className={`df-badge ${
              row.is_enabled === true
                ? 'bg-success/15 text-success'
                : 'bg-muted text-muted-foreground'
            }`}
          >
            {row.is_enabled === true ? '啟用' : '停用'}
          </span>
        )}
      </td>
      <td className="px-3 py-3">
        {row.cron_expr === null ? (
          <span className="text-muted-foreground">—</span>
        ) : canEdit ? (
          <button
            type="button"
            onClick={handleEdit}
            disabled={busy}
            className="df-btn-info-soft min-h-[36px] px-3"
          >
            {describeCron(row.cron_expr)}
          </button>
        ) : (
          <span className="text-foreground">{describeCron(row.cron_expr)}</span>
        )}
      </td>
      <td className="df-td text-muted-foreground">
        {formatNullableDateTime(row.last_synced_at)}
      </td>
      <td className="px-3 py-3">
        <LastResultBadge status={row.last_run_status} />
      </td>
      <td className="df-td text-muted-foreground">
        {formatNextRun(row.cron_expr, row.is_enabled)}
      </td>
    </tr>
  )
})

interface SchemaTablesProps {
  schema: string
  page: number
  filters: ScheduleFilters
  hasActiveFilter: boolean
  canEdit: boolean
  busyUid: string | null
  onToggle: (row: ScheduleTableView) => void
  onEdit: (row: ScheduleTableView) => void
  onPageChange: (page: number) => void
}

function SchemaTables({
  schema,
  page,
  filters,
  hasActiveFilter,
  canEdit,
  busyUid,
  onToggle,
  onEdit,
  onPageChange,
}: SchemaTablesProps): React.ReactNode {
  const { data, isLoading, isError, isFetching } = useListScheduleTablesQuery({
    schema,
    page,
    pageSize: PAGE_SIZE,
    enabled: filters.enabled,
    lastResult: filters.lastResult,
    keyword: filters.keyword,
  })

  if (isLoading) {
    return <p className="text-sm text-muted-foreground md:text-base">載入中…</p>
  }
  if (isError || data === undefined) {
    return (
      <p
        role="alert"
        className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger md:text-base"
      >
        載入 {schema} 的排程失敗,請稍後再試
      </p>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <div
        className={`df-card overflow-x-auto transition-opacity ${isFetching ? 'opacity-60' : ''}`}
      >
        <table className="df-table min-w-[880px]">
          <thead>
            <tr className="border-b border-border bg-muted/50">
              <th className="df-th">資料表</th>
              <th className="df-th">業務名</th>
              <th className="df-th">啟用</th>
              <th className="df-th">排程時間</th>
              <th className="df-th">上次同步</th>
              <th className="df-th">上次結果</th>
              <th className="df-th">下次執行</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((row) => (
              <ScheduleRow
                key={row.table_name}
                row={row}
                canEdit={canEdit}
                busy={busyUid === row.schedule_uid}
                onToggle={onToggle}
                onEdit={onEdit}
              />
            ))}
          </tbody>
        </table>
        {data.items.length === 0 ? (
          <p className="px-3 py-8 text-center text-sm text-muted-foreground md:text-base">
            {hasActiveFilter
              ? '查無符合篩選條件的資料表(可調整或清除進階篩選)'
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

/** 批次啟停確認的目標(scope=all → 全部 schema;scope=schema → 當前 schema) */
type BatchTarget = { enabled: boolean; scope: 'all' | 'schema' }

export function ScheduleTableBrowser(): React.ReactNode {
  const { isAdmin } = useAuth()
  const {
    data: schemas,
    isLoading: schemasLoading,
    isError: schemasError,
  } = useGetScheduleSchemasQuery()

  const [activeSchema, setActiveSchema] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [filters, setFilters] = useState<ScheduleFilters>(DEFAULT_FILTERS)
  const [noticeMessage, setNoticeMessage] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [busyUid, setBusyUid] = useState<string | null>(null)
  const [editTarget, setEditTarget] = useState<ScheduleEditInitial | null>(null)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [batchTarget, setBatchTarget] = useState<BatchTarget | null>(null)

  const [updateSchedule, { isLoading: isUpdating }] = useUpdateScheduleMutation()
  const [setEnabled] = useSetScheduleEnabledMutation()
  const [batchSetEnabled, { isLoading: isBatching }] =
    useBatchSetEnabledMutation()

  const orderedSchemas = useMemo(
    () => orderSchemas((schemas ?? []).map((s) => s.schema_name)),
    [schemas],
  )
  const effectiveSchema = activeSchema ?? orderedSchemas[0] ?? null

  const activeSummary = useMemo(
    () => schemas?.find((s) => s.schema_name === effectiveSchema) ?? null,
    [schemas, effectiveSchema],
  )
  const totals = useMemo(() => {
    let tableCount = 0
    let enabledCount = 0
    for (const s of schemas ?? []) {
      tableCount += s.table_count
      enabledCount += s.enabled_count
    }
    return { tableCount, enabledCount }
  }, [schemas])

  const activeFilterCount = useMemo((): number => {
    let count = 0
    if (filters.enabled !== 'all') count += 1
    if (filters.lastResult !== 'all') count += 1
    if (filters.keyword !== '') count += 1
    return count
  }, [filters])

  const handleSchemaSelect = useCallback((schema: string): void => {
    setActiveSchema(schema)
    setPage(1)
  }, [])

  const handlePageChange = useCallback((next: number): void => {
    setPage(next)
  }, [])

  const updateFilters = useCallback((patch: Partial<ScheduleFilters>): void => {
    setFilters((prev) => ({ ...prev, ...patch }))
    setPage(1)
  }, [])

  const resetFilters = useCallback((): void => {
    setFilters(DEFAULT_FILTERS)
    setPage(1)
  }, [])

  const handleToggle = useCallback(
    async (row: ScheduleTableView): Promise<void> => {
      if (row.schedule_uid === null) return
      setActionError(null)
      setNoticeMessage(null)
      setBusyUid(row.schedule_uid)
      const result = await setEnabled({
        uid: row.schedule_uid,
        enabled: row.is_enabled !== true,
      })
      if ('error' in result) {
        setActionError(
          extractApiErrorDetail(result.error, '切換排程狀態失敗,請稍後再試'),
        )
      }
      setBusyUid(null)
    },
    [setEnabled],
  )

  const handleOpenEdit = useCallback((row: ScheduleTableView): void => {
    if (row.schedule_uid === null || row.cron_expr === null) return
    setSubmitError(null)
    setEditTarget({
      uid: row.schedule_uid,
      tableName: row.table_name,
      cronExpr: row.cron_expr,
      isEnabled: row.is_enabled === true,
      description: row.description,
    })
  }, [])

  const closeEdit = useCallback((): void => {
    setSubmitError(null)
    setEditTarget(null)
  }, [])

  const handleSubmitEdit = useCallback(
    async (payload: ScheduleEditPayload): Promise<void> => {
      if (editTarget === null) return
      setSubmitError(null)
      const result = await updateSchedule({
        uid: editTarget.uid,
        cron_expr: payload.cron_expr,
        is_enabled: payload.is_enabled,
        description: payload.description,
      })
      if ('error' in result) {
        setSubmitError(
          extractApiErrorDetail(result.error, '儲存排程失敗,請稍後再試'),
        )
        return
      }
      setEditTarget(null)
    },
    [editTarget, updateSchedule],
  )

  const closeBatch = useCallback((): void => setBatchTarget(null), [])

  const handleConfirmBatch = useCallback(async (): Promise<void> => {
    if (batchTarget === null) return
    setActionError(null)
    setNoticeMessage(null)
    const scoped =
      batchTarget.scope === 'schema' && effectiveSchema !== null
        ? { enabled: batchTarget.enabled, schema: effectiveSchema }
        : { enabled: batchTarget.enabled }
    const result = await batchSetEnabled(scoped)
    setBatchTarget(null)
    if ('error' in result) {
      setActionError(
        extractApiErrorDetail(result.error, '批次啟停失敗,請稍後再試'),
      )
      return
    }
    setNoticeMessage(
      `已${batchTarget.enabled ? '啟用' : '停用'} ${result.data.affected} 筆排程`,
    )
  }, [batchTarget, effectiveSchema, batchSetEnabled])

  return (
    <section className="mx-auto flex max-w-7xl flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-foreground md:text-2xl">
            排程管理
          </h1>
          <p className="mt-1 text-sm text-muted-foreground md:text-base">
            逐表檢視排程啟停、執行時間與上次同步結果(時間一律 UTC+8;排程由系統自動建立)
          </p>
        </div>
        {isAdmin ? (
          <button
            type="button"
            onClick={() => setBatchTarget({ enabled: true, scope: 'all' })}
            disabled={isBatching}
            className="df-btn-primary-soft"
          >
            全部啟用
          </button>
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

      {isAdmin ? (
        <ScheduleFormDialog
          key={editTarget?.uid ?? 'closed'}
          open={editTarget !== null}
          initial={editTarget}
          submitting={isUpdating}
          submitError={submitError}
          onSubmit={handleSubmitEdit}
          onCancel={closeEdit}
        />
      ) : null}

      <ConfirmDialog
        open={batchTarget !== null}
        title={batchTarget?.enabled === true ? '批次啟用排程' : '批次停用排程'}
        confirmLabel={batchTarget?.enabled === true ? '開始啟用' : '開始停用'}
        confirmDisabled={isBatching}
        tone={batchTarget?.enabled === true ? 'primary' : 'danger'}
        onConfirm={handleConfirmBatch}
        onCancel={closeBatch}
      >
        {batchTarget !== null && batchTarget.scope === 'all' ? (
          <p className="text-foreground">
            將{batchTarget.enabled ? '啟用' : '停用'}
            <strong>全部 schema</strong>的來源表排程(共 {totals.tableCount} 張表,目前已啟用{' '}
            {totals.enabledCount} 筆)。
          </p>
        ) : batchTarget !== null ? (
          <p className="text-foreground">
            將{batchTarget.enabled ? '啟用' : '停用'}「
            {effectiveSchema ?? '—'}」分類下的所有來源表排程(共{' '}
            {activeSummary?.table_count ?? 0} 張表,目前已啟用{' '}
            {activeSummary?.enabled_count ?? 0} 筆)。
          </p>
        ) : null}
        <p>停用的排程不會派工;可隨時再切回啟用。</p>
      </ConfirmDialog>

      {schemasError ? (
        <p
          role="alert"
          className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger md:text-base"
        >
          載入排程 schema 清單失敗,請稍後再試
        </p>
      ) : null}
      {schemasLoading ? (
        <p className="text-sm text-muted-foreground md:text-base">載入中…</p>
      ) : null}

      {schemas !== undefined && schemas.length === 0 ? (
        <div className="df-card p-8 text-center text-sm text-muted-foreground md:text-base">
          尚無任何來源表 / 排程
        </div>
      ) : null}

      {orderedSchemas.length > 0 ? (
        <>
          <CollapsibleSection
            title="資料分類"
            summary={
              effectiveSchema !== null ? `目前:${effectiveSchema}` : undefined
            }
          >
            <div className="flex flex-wrap gap-2">
              {orderedSchemas.map((schema) => {
                const summary = schemas?.find((s) => s.schema_name === schema)
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
                      {summary?.enabled_count ?? 0}/{summary?.table_count ?? 0}
                    </span>
                  </button>
                )
              })}
            </div>
          </CollapsibleSection>

          <CollapsibleSection
            title="進階篩選"
            defaultOpen={false}
            summary={
              activeFilterCount === 0 ? '未套用' : `${activeFilterCount} 項條件`
            }
          >
            <AdvancedFilters
              filters={filters}
              onChange={updateFilters}
              onReset={resetFilters}
              activeCount={activeFilterCount}
            />
          </CollapsibleSection>

          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-sm font-semibold text-foreground md:text-base">
              {effectiveSchema !== null ? `${effectiveSchema} 排程` : '排程'}
            </h2>
            {isAdmin ? (
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() =>
                    setBatchTarget({ enabled: true, scope: 'schema' })
                  }
                  disabled={isBatching}
                  className="df-btn-primary-soft min-h-[36px] px-3"
                >
                  本分類全部啟用
                </button>
                <button
                  type="button"
                  onClick={() =>
                    setBatchTarget({ enabled: false, scope: 'schema' })
                  }
                  disabled={isBatching}
                  className="df-btn-warning-soft min-h-[36px] px-3"
                >
                  本分類全部停用
                </button>
              </div>
            ) : null}
          </div>

          {effectiveSchema !== null ? (
            <SchemaTables
              schema={effectiveSchema}
              page={page}
              filters={filters}
              hasActiveFilter={activeFilterCount > 0}
              canEdit={isAdmin}
              busyUid={busyUid}
              onToggle={handleToggle}
              onEdit={handleOpenEdit}
              onPageChange={handlePageChange}
            />
          ) : null}
        </>
      ) : null}
    </section>
  )
}
