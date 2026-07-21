'use client'

import { memo, useCallback, useMemo, useState } from 'react'
import { skipToken } from '@reduxjs/toolkit/query'
import { ConfirmDialog } from '@/components/common/ConfirmDialog'
import { CollapsibleSection } from '@/components/common/CollapsibleSection'
import { Pagination } from '@/components/common/Pagination'
import {
  TableSearchCombobox,
  type SuggestItem,
} from '@/components/common/TableSearchCombobox'
import {
  useConfirmSemanticTableMutation,
  useListSemanticMappingsQuery,
  useListSemanticTablesQuery,
  useSyncSemanticViewsMutation,
  useUpdateSemanticMappingMutation,
  type MappingStatus,
  type MappingStatusFilter,
  type SemanticMappingItem,
} from '@/lib/api/semanticMappingApi'
import { useGlobalProgressQuery } from '@/lib/api/progressApi'
import { extractApiErrorDetail } from '@/utils/apiError'
import { formatNullableDateTime } from '@/utils/datetime'

const PAGE_SIZE = 50

/** 英文名白名單(對齊後端 ENGLISH_NAME_PATTERN):小寫開頭,僅小寫英數與底線 */
const ENGLISH_NAME_RE = /^[a-z][a-z0-9_]*$/

const STATUS_OPTIONS: ReadonlyArray<{ value: MappingStatusFilter; label: string }> = [
  { value: 'all', label: '全部' },
  { value: 'draft', label: '草稿' },
  { value: 'confirmed', label: '已確認' },
]

const STATUS_LABELS: Record<MappingStatus, string> = {
  draft: '草稿',
  confirmed: '已確認',
}

interface EditingState {
  tableName: string
  columnName: string
  englishName: string
  zhName: string
}

/** 狀態膠囊(對齊 pill 視覺語言) */
function StatusBadge({ status }: { status: MappingStatus }): React.ReactNode {
  const cls =
    status === 'confirmed'
      ? 'bg-success/15 text-success'
      : 'bg-muted text-muted-foreground'
  return <span className={`df-badge ${cls}`}>{STATUS_LABELS[status]}</span>
}

/** 狀態篩選膠囊(與資料集頁 Segmented 同一視覺語言) */
function StatusSegmented({
  value,
  onChange,
}: {
  value: MappingStatusFilter
  onChange: (value: MappingStatusFilter) => void
}): React.ReactNode {
  return (
    <div className="flex flex-wrap gap-2">
      {STATUS_OPTIONS.map((opt) => {
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
                : 'border-border bg-card text-muted-foreground hover:bg-muted hover:text-foreground'
            }`}
          >
            {opt.label}
          </button>
        )
      })}
    </div>
  )
}

interface MappingRowProps {
  item: SemanticMappingItem
  busy: boolean
  onStartEdit: (item: SemanticMappingItem) => void
  onToggleStatus: (item: SemanticMappingItem) => void
}

const MappingRow = memo(function MappingRow({
  item,
  busy,
  onStartEdit,
  onToggleStatus,
}: MappingRowProps): React.ReactNode {
  return (
    <tr className="border-b border-border transition-colors last:border-b-0 hover:bg-muted/50">
      <td className="px-3 py-3 font-mono text-sm font-medium whitespace-nowrap text-foreground md:text-base">
        {item.table_name}
      </td>
      <td className="df-td font-mono">
        {item.column_name === '' ? (
          <span className="font-sans text-muted-foreground">(表層級)</span>
        ) : (
          item.column_name
        )}
      </td>
      <td className="df-td font-mono">{item.english_name}</td>
      <td className="df-td text-muted-foreground">{item.zh_name ?? '—'}</td>
      <td className="df-td">
        <StatusBadge status={item.status} />
      </td>
      <td className="df-td text-muted-foreground">
        {formatNullableDateTime(item.updated_at)}
      </td>
      <td className="px-3 py-3 whitespace-nowrap">
        <span className="flex gap-2">
          <button
            type="button"
            onClick={() => onStartEdit(item)}
            className="df-btn-outline min-h-[36px] px-3"
          >
            編輯
          </button>
          <button
            type="button"
            onClick={() => onToggleStatus(item)}
            disabled={busy}
            className="df-btn-outline min-h-[36px] px-3"
          >
            {item.status === 'draft' ? '轉已確認' : '退回草稿'}
          </button>
        </span>
      </td>
    </tr>
  )
})

export function SemanticMappingManager(): React.ReactNode {
  const [activeTable, setActiveTable] = useState('')
  const [statusFilter, setStatusFilter] = useState<MappingStatusFilter>('all')
  const [keyword, setKeyword] = useState('')
  const [page, setPage] = useState(1)
  const [editing, setEditing] = useState<EditingState | null>(null)
  // 編輯 dialog 內的錯誤訊息(顯示在 dialog 裡,不用頁面層 actionError 以免被遮罩擋住)
  const [editError, setEditError] = useState<string | null>(null)
  const [openDialog, setOpenDialog] = useState<
    'edit' | 'confirm-table' | 'sync-views' | null
  >(null)
  const [noticeMessage, setNoticeMessage] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const { data: tables, isError: isTablesError } = useListSemanticTablesQuery()
  // 與 layout 的全局進度條共用 RTK Query 快取(不多打 API):套用進行中時擋「套用變更」
  const { data: globalProgress } = useGlobalProgressQuery()
  const isApplyRunning = globalProgress?.apply.active === true
  const { data, isLoading, isError, isFetching } = useListSemanticMappingsQuery({
    table: activeTable,
    status: statusFilter,
    keyword,
    page,
    pageSize: PAGE_SIZE,
  })

  // 逐筆轉態使 total 縮水後 page 可能超出末頁而停在空頁(AD-131):資料回來後夾回末頁
  // (React「渲染期間調整 state」模式:條件成立時立即重渲染,不進 effect)
  const totalPages = Math.max(1, Math.ceil((data?.total ?? 0) / PAGE_SIZE))
  if (!isFetching && data !== undefined && page > totalPages) {
    setPage(totalPages)
  }

  // combobox 建議池:不受表 / 狀態篩選影響,依當前關鍵字取前 20 筆(表 / 欄 / 中 / 英皆可命中)
  const { data: suggestData } = useListSemanticMappingsQuery(
    keyword !== ''
      ? { table: '', status: 'all', keyword, page: 1, pageSize: 20 }
      : skipToken,
  )
  const nameSuggestions = useMemo((): SuggestItem[] => {
    const seen = new Set<string>()
    const out: SuggestItem[] = []
    for (const item of suggestData?.items ?? []) {
      // 表層級列以表名為建議;欄層級列以欄名為建議,顯示字樣帶中英語意名
      const name = item.column_name === '' ? item.table_name : item.column_name
      if (seen.has(name)) continue
      seen.add(name)
      const semantic = [item.zh_name, item.english_name]
        .filter((v): v is string => v !== null && v !== '')
        .join(' / ')
      out.push({ name, business_name: semantic === '' ? null : semantic })
    }
    return out
  }, [suggestData])

  const [updateMapping, { isLoading: isUpdating }] = useUpdateSemanticMappingMutation()
  const [confirmTable, { isLoading: isConfirming }] = useConfirmSemanticTableMutation()
  const [syncViews, { isLoading: isSyncing }] = useSyncSemanticViewsMutation()

  const activeTableSummary = useMemo(
    () => (tables ?? []).find((t) => t.table_name === activeTable) ?? null,
    [tables, activeTable],
  )

  // 表名 combobox 建議池:全部表(表名 + 表層級中英文名,中英皆可搜)
  const tableSuggestions = useMemo((): SuggestItem[] => {
    return (tables ?? []).map((t) => {
      const semantic = [t.zh_name, t.english_name]
        .filter((v): v is string => v !== null && v !== '')
        .join(' / ')
      return {
        name: t.table_name,
        business_name: semantic === '' ? null : semantic,
      }
    })
  }, [tables])

  const activeFilterCount = useMemo((): number => {
    let count = 0
    if (activeTable !== '') count += 1
    if (statusFilter !== 'all') count += 1
    if (keyword !== '') count += 1
    return count
  }, [activeTable, statusFilter, keyword])

  const resetMessages = useCallback((): void => {
    setNoticeMessage(null)
    setActionError(null)
  }, [])

  // 表名 combobox:選定建議(exact)直接套用;自由打字僅在完全等於某表名時套用,
  // 清空輸入則解除表篩選(模糊探索交給下拉建議與「名稱搜尋」)
  const handleTableCommit = useCallback(
    (value: string, exact: boolean): void => {
      if (value === '') {
        setActiveTable('')
        setPage(1)
        return
      }
      const matched = exact
        ? value
        : ((tables ?? []).find(
            (t) => t.table_name.toLowerCase() === value.toLowerCase(),
          )?.table_name ?? null)
      if (matched !== null && matched !== activeTable) {
        setActiveTable(matched)
        setPage(1)
      } else if (matched === null && activeTable !== '') {
        // 打不中就不套表篩選:解除既有表篩選,避免顯示文字與實際篩選脫鉤(AD-126)
        setActiveTable('')
        setPage(1)
      }
    },
    [tables, activeTable],
  )

  const handleStatusChange = useCallback((value: MappingStatusFilter): void => {
    setStatusFilter(value)
    setPage(1)
  }, [])

  const handleKeywordCommit = useCallback((value: string): void => {
    setKeyword(value)
    setPage(1)
  }, [])

  const resetFilters = useCallback((): void => {
    setActiveTable('')
    setStatusFilter('all')
    setKeyword('')
    setPage(1)
  }, [])

  const startEdit = useCallback((item: SemanticMappingItem): void => {
    setEditing({
      tableName: item.table_name,
      columnName: item.column_name,
      englishName: item.english_name,
      zhName: item.zh_name ?? '',
    })
    setEditError(null)
    setOpenDialog('edit')
  }, [])

  const patchEditing = useCallback((patch: Partial<EditingState>): void => {
    setEditing((prev) => (prev === null ? prev : { ...prev, ...patch }))
  }, [])

  const cancelEdit = useCallback((): void => {
    setOpenDialog(null)
    setEditing(null)
    setEditError(null)
  }, [])

  const saveEdit = useCallback(async (): Promise<void> => {
    if (editing === null) return
    setEditError(null)
    const english = editing.englishName.trim()
    if (!ENGLISH_NAME_RE.test(english)) {
      setEditError('英文名格式不符:小寫開頭,僅允許小寫英數與底線(例 part_number)')
      return
    }
    const zh = editing.zhName.trim()
    const result = await updateMapping({
      table_name: editing.tableName,
      column_name: editing.columnName,
      english_name: english,
      zh_name: zh === '' ? null : zh,
    })
    if ('error' in result) {
      setEditError(extractApiErrorDetail(result.error, '更新映射失敗,請稍後再試'))
      return
    }
    resetMessages()
    setOpenDialog(null)
    setEditing(null)
    setNoticeMessage('已儲存;點右上「套用變更」立即生效,或等系統排程自動套用')
  }, [editing, updateMapping, resetMessages])

  const toggleStatus = useCallback(
    async (item: SemanticMappingItem): Promise<void> => {
      resetMessages()
      const next: MappingStatus = item.status === 'draft' ? 'confirmed' : 'draft'
      const result = await updateMapping({
        table_name: item.table_name,
        column_name: item.column_name,
        status: next,
      })
      if ('error' in result) {
        setActionError(extractApiErrorDetail(result.error, '狀態切換失敗,請稍後再試'))
        return
      }
      setNoticeMessage(
        `已將 ${item.table_name}.${item.column_name === '' ? '(表層級)' : item.column_name} 轉為「${STATUS_LABELS[next]}」`,
      )
    },
    [updateMapping, resetMessages],
  )

  const handleConfirmTable = useCallback(async (): Promise<void> => {
    setOpenDialog(null)
    resetMessages()
    if (activeTable === '') return
    const result = await confirmTable(activeTable)
    if ('error' in result) {
      setActionError(extractApiErrorDetail(result.error, '整表轉態失敗,請稍後再試'))
      return
    }
    setNoticeMessage(
      `${activeTable} 整表轉「已確認」完成(${result.data.affected} 筆);點右上「套用變更」立即生效`,
    )
  }, [activeTable, confirmTable, resetMessages])

  const handleSyncViews = useCallback(async (): Promise<void> => {
    setOpenDialog(null)
    resetMessages()
    const result = await syncViews()
    if ('error' in result) {
      // 409(套用進行中)等錯誤同走此路徑,detail 由後端提供
      setActionError(extractApiErrorDetail(result.error, '套用變更失敗,請稍後再試'))
      return
    }
    // 202 受理:實際執行進度由全局進度條(apply)呈現
    setNoticeMessage('已開始套用,進度顯示於上方進度條')
  }, [syncViews, resetMessages])

  return (
    <section className="mx-auto flex max-w-7xl flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-foreground md:text-2xl">語意映射管理</h1>
          <p className="mt-1 text-sm text-muted-foreground md:text-base">
            管理 ERP 表 / 欄位的英文名稱對照;確認後套用,資料查詢與英文資料檢視即使用新名稱
          </p>
        </div>
        <button
          type="button"
          onClick={() => setOpenDialog('sync-views')}
          disabled={isSyncing || isApplyRunning}
          className="df-btn-primary-soft"
        >
          {isApplyRunning ? '套用進行中…' : isSyncing ? '套用中…' : '套用變更'}
        </button>
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

      <CollapsibleSection
        title="篩選條件"
        summary={activeFilterCount === 0 ? '未套用' : `${activeFilterCount} 項條件`}
      >
        <div className="flex flex-col gap-5">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <span className="w-32 shrink-0 text-sm font-medium text-foreground md:text-base">
              名稱搜尋
            </span>
            <TableSearchCombobox
              value={keyword}
              suggestions={nameSuggestions}
              onCommit={handleKeywordCommit}
            />
            <span className="text-sm text-muted-foreground">
              (資料表 / 欄位 / 英文語意名 / 中文名,中英皆可)
            </span>
          </div>

          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <span className="w-32 shrink-0 text-sm font-medium text-foreground md:text-base">
              資料表
            </span>
            <TableSearchCombobox
              value={activeTable}
              suggestions={tableSuggestions}
              onCommit={handleTableCommit}
            />
            {isTablesError ? (
              <span className="text-sm text-danger md:text-base">
                表清單載入失敗
              </span>
            ) : null}
            {activeTable !== '' && activeTableSummary !== null ? (
              <span className="text-sm text-muted-foreground">
                (草稿 {activeTableSummary.draft_count} / 已確認{' '}
                {activeTableSummary.confirmed_count})
              </span>
            ) : null}
            {activeTable !== '' ? (
              <button
                type="button"
                onClick={() => setOpenDialog('confirm-table')}
                disabled={isConfirming || (activeTableSummary?.draft_count ?? 0) === 0}
                className="df-btn-outline min-h-[36px] px-3"
              >
                整表轉已確認
              </button>
            ) : null}
          </div>

          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <span className="w-32 shrink-0 text-sm font-medium text-foreground md:text-base">
              狀態
            </span>
            <StatusSegmented value={statusFilter} onChange={handleStatusChange} />
          </div>

          <div className="flex items-center justify-end">
            <button
              type="button"
              onClick={resetFilters}
              disabled={activeFilterCount === 0}
              className="df-btn-outline min-h-[36px] px-3"
            >
              清除篩選
            </button>
          </div>
        </div>
      </CollapsibleSection>

      {isLoading ? (
        <p className="text-sm text-muted-foreground md:text-base">載入中…</p>
      ) : isError ? (
        <p
          role="alert"
          className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger md:text-base"
        >
          載入語意映射失敗,請稍後再試
        </p>
      ) : (
        <div className="flex flex-col gap-3">
          <div
            className={`df-card overflow-x-auto transition-opacity ${
              isFetching ? 'opacity-60' : ''
            }`}
          >
            <table className="df-table min-w-[960px]">
              <thead>
                <tr className="border-b border-border bg-muted/50">
                  <th className="df-th">資料表</th>
                  <th className="df-th">欄位</th>
                  <th className="df-th">英文語意名</th>
                  <th className="df-th">中文名</th>
                  <th className="df-th">狀態</th>
                  <th className="df-th">更新時間</th>
                  <th className="df-th">操作</th>
                </tr>
              </thead>
              <tbody>
                {(data?.items ?? []).map((item) => (
                  <MappingRow
                    key={`${item.table_name}::${item.column_name}`}
                    item={item}
                    busy={isUpdating}
                    onStartEdit={startEdit}
                    onToggleStatus={toggleStatus}
                  />
                ))}
              </tbody>
            </table>
            {(data?.items.length ?? 0) === 0 ? (
              <p className="px-3 py-8 text-center text-sm text-muted-foreground md:text-base">
                {activeFilterCount > 0
                  ? '查無符合篩選條件的映射(可調整或清除篩選)'
                  : '尚無語意映射資料(請先執行 seed 或同步)'}
              </p>
            ) : null}
          </div>
          <Pagination
            page={page}
            pageSize={PAGE_SIZE}
            total={data?.total ?? 0}
            onPageChange={setPage}
          />
        </div>
      )}

      <ConfirmDialog
        open={openDialog === 'edit' && editing !== null}
        title="編輯映射"
        confirmLabel={isUpdating ? '儲存中…' : '儲存'}
        confirmDisabled={isUpdating}
        onConfirm={saveEdit}
        onCancel={cancelEdit}
      >
        {editing !== null ? (
          <div className="flex flex-col gap-4">
            <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm md:text-base">
              <span>
                資料表:
                <span className="ml-1 font-mono text-foreground">
                  {editing.tableName}
                </span>
              </span>
              <span>
                欄位:
                <span className="ml-1 font-mono text-foreground">
                  {editing.columnName === '' ? '(表層級)' : editing.columnName}
                </span>
              </span>
            </div>
            <label className="flex flex-col gap-1.5">
              <span className="text-sm font-medium text-foreground md:text-base">
                英文語意名
              </span>
              <input
                type="text"
                value={editing.englishName}
                onChange={(e) => patchEditing({ englishName: e.target.value })}
                placeholder="例 part_number"
                className="df-input font-mono"
              />
              <span className="text-sm text-muted-foreground">
                小寫開頭,僅允許小寫英數與底線;將作為對外顯示的英文欄位名
              </span>
            </label>
            <label className="flex flex-col gap-1.5">
              <span className="text-sm font-medium text-foreground md:text-base">
                中文名
              </span>
              <input
                type="text"
                value={editing.zhName}
                onChange={(e) => patchEditing({ zhName: e.target.value })}
                placeholder="例 品號(留空代表清除)"
                className="df-input"
              />
            </label>
            {editError !== null ? (
              <p
                role="alert"
                className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger md:text-base"
              >
                {editError}
              </p>
            ) : null}
          </div>
        ) : null}
      </ConfirmDialog>

      <ConfirmDialog
        open={openDialog === 'confirm-table'}
        title="整表轉已確認"
        confirmLabel="確定轉態"
        confirmDisabled={isConfirming}
        tone="danger"
        onConfirm={handleConfirmTable}
        onCancel={() => setOpenDialog(null)}
      >
        <p className="text-foreground">
          把「{activeTable}」全部草稿映射轉為「已確認」
          {activeTableSummary !== null ? `(約 ${activeTableSummary.draft_count} 筆)` : ''}。
        </p>
        <p>轉「已確認」後,這些英文名稱會在套用變更(或系統排程)時正式生效,確定要執行嗎?</p>
      </ConfirmDialog>

      <ConfirmDialog
        open={openDialog === 'sync-views'}
        title="套用變更"
        confirmLabel="開始套用"
        confirmDisabled={isSyncing || isApplyRunning}
        onConfirm={handleSyncViews}
        onCancel={() => setOpenDialog(null)}
      >
        <p className="text-foreground">
          把「已確認」的名稱對照套用到系統:資料查詢的英文欄位名與各帳套的英文資料檢視會同步更新。
        </p>
        <p>於背景執行,進度顯示於上方進度條;只更新名稱對照,不會更動任何 ERP 資料。</p>
      </ConfirmDialog>
    </section>
  )
}
