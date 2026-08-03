'use client'

import {
  createContext,
  Fragment,
  memo,
  useCallback,
  useContext,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from 'react'
import { skipToken } from '@reduxjs/toolkit/query'
import {
  useCreateClientSettingRoleMutation,
  useCreateExceptionSetMutation,
  useCreateOperationMutation,
  useCreatePermissionProfileMutation,
  useCreateServiceMutation,
  useDeleteClientSettingRoleMutation,
  useDeleteExceptionSetMutation,
  useDeleteOperationMutation,
  useDeletePermissionProfileMutation,
  useDeleteServiceMutation,
  useListClientSettingRolesQuery,
  useListExceptionItemsQuery,
  useListExceptionOperationsQuery,
  useListExceptionSetsQuery,
  useListOperationItemsQuery,
  useListOperationsQuery,
  useListPermissionProfilesQuery,
  useListProfileItemsQuery,
  useListProfileOperationsQuery,
  useListServicesQuery,
  useReplaceExceptionItemsMutation,
  useReplaceExceptionOperationsMutation,
  useReplaceOperationItemsMutation,
  useReplaceProfileItemsMutation,
  useReplaceProfileOperationsMutation,
  useUpdateClientSettingRoleMutation,
  type ClientSettingOperation,
  type ClientSettingRole,
  type ClientSettingService,
  type CreateClientSettingOperationPayload,
  type CreateClientSettingRolePayload,
  type CreateClientSettingServicePayload,
  type CreateExceptionSetPayload,
  type CreatePermissionProfilePayload,
  type ExceptionSet,
  type ListExceptionItemsParams,
  type ListProfileItemsParams,
  type PermissionAction,
  type PermissionItem,
  type PermissionProfile,
  type ScopeItem,
} from '@/lib/api/clientSettingApi'
import {
  useListSemanticMappingsQuery,
  useListSemanticTablesQuery,
  type ListSemanticMappingsParams,
  type SemanticTableSummary,
} from '@/lib/api/semanticMappingApi'
import { ConfirmDialog } from '@/components/common/ConfirmDialog'
import { Segmented, type SegmentedOption } from '@/components/common/Segmented'
import { extractApiErrorDetail } from '@/utils/apiError'
import { formatDateTime } from '@/utils/datetime'

/** 表 / 欄位授權設定前提;各 tab 空狀態與作業建立區共用同一提示語意 */
const CONFIRMED_MAPPING_HINT =
  '設定作業範圍 / 授權矩陣前,請先於「語意映射管理」將欲開放的表 / 欄位標記為「已確認」,否則後端會拒絕(422)'

/** 後端 `ALL_COLUMNS`:該表全欄位(只驗表存在,不逐欄驗) */
const ALL_COLUMNS = '*'
/** 複合鍵分隔字元(不可能出現在表 / 欄位英文名內) */
const KEY_SEP = '::'
/** 單表欄位選項一次撈完的上限;**必**對齊後端 `page_size` 的 `le=200`(超出即 422) */
const COLUMN_PAGE_SIZE = 200

/** 服務代碼白名單(對齊後端 `SERVICE_CODE_PATTERN`):小寫字母開頭,僅小寫英文與底線 */
const SERVICE_CODE_RE = /^[a-z][a-z_]*$/
const SERVICE_CODE_HINT = '僅限英文小寫與底線、小寫字母開頭(URL 允許格式),建立後不可改'
const SERVICE_CODE_ERROR = `服務代碼格式不符:${SERVICE_CODE_HINT}`

const CHECKBOX_CLASS = 'h-5 w-5 accent-[rgb(var(--primary))]'

const ACTIONS: readonly PermissionAction[] = ['read', 'edit']
const ACTION_LABELS: Record<PermissionAction, string> = {
  read: '讀取',
  edit: '編輯',
}

type TabKey = 'services' | 'profiles' | 'roles' | 'exceptions'

const TAB_OPTIONS: ReadonlyArray<SegmentedOption<TabKey>> = [
  { value: 'services', label: '服務 / 作業' },
  { value: 'profiles', label: '角色權限設定檔' },
  { value: 'roles', label: '角色' },
  { value: 'exceptions', label: '臨時權限' },
]

/** 角色權限設定檔 / 臨時權限組共用同一組授權 UI,差別僅在打哪組端點 */
type PermissionSetKind = 'profile' | 'exception'

/* ---------------------------------------------------------------------- */
/* 純函式 helper                                                            */
/* ---------------------------------------------------------------------- */

function scopeKey(tableName: string, columnName: string): string {
  return `${tableName}${KEY_SEP}${columnName}`
}

function parseScopeKey(key: string): ScopeItem | null {
  const [tableName, columnName] = key.split(KEY_SEP)
  if (tableName === undefined || columnName === undefined) return null
  return { table_name: tableName, column_name: columnName }
}

function grantKey(tableName: string, columnName: string, action: PermissionAction): string {
  return `${tableName}${KEY_SEP}${columnName}${KEY_SEP}${action}`
}

function isPermissionAction(value: string): value is PermissionAction {
  return value === 'read' || value === 'edit'
}

function parseGrantKey(key: string): PermissionItem | null {
  const [tableName, columnName, action] = key.split(KEY_SEP)
  if (tableName === undefined || columnName === undefined || action === undefined) return null
  if (!isPermissionAction(action)) return null
  return { table_name: tableName, column_name: columnName, action }
}

function columnLabel(columnName: string): string {
  return columnName === ALL_COLUMNS ? '全欄位(*)' : columnName
}

/** `*` 永遠排最前(表級快捷),其餘依英文名 */
function compareColumn(a: string, b: string): number {
  if (a === b) return 0
  if (a === ALL_COLUMNS) return -1
  if (b === ALL_COLUMNS) return 1
  return a.localeCompare(b)
}

interface TableGroup {
  tableName: string
  columns: string[]
}

function groupByTable(items: readonly ScopeItem[]): TableGroup[] {
  const columnsByTable = new Map<string, string[]>()
  for (const item of items) {
    const existing = columnsByTable.get(item.table_name)
    if (existing === undefined) columnsByTable.set(item.table_name, [item.column_name])
    else existing.push(item.column_name)
  }
  const groups: TableGroup[] = []
  for (const [tableName, columns] of columnsByTable) {
    groups.push({ tableName, columns: [...columns].sort(compareColumn) })
  }
  groups.sort((a, b) => a.tableName.localeCompare(b.tableName))
  return groups
}

/** 排序後的鍵陣列比對(草稿 vs 伺服器)*/
function sameKeys(a: readonly string[], b: readonly string[]): boolean {
  return a.length === b.length && a.every((key, index) => key === b[index])
}

/** 表英文語意名 → 中文名(範圍編輯與授權矩陣共用同一份顯示對照) */
function buildTableZhMap(tables: readonly SemanticTableSummary[] | undefined): Map<string, string> {
  const map = new Map<string, string>()
  for (const table of tables ?? []) {
    if (table.english_name === null || table.english_name === '') continue
    if (table.zh_name === null || table.zh_name === '') continue
    map.set(table.english_name, table.zh_name)
  }
  return map
}

/* ---------------------------------------------------------------------- */
/* 未儲存草稿守衛(切分頁 / 換列前攔一次)                                     */
/* ---------------------------------------------------------------------- */

interface DirtyGuardValue {
  /** 編輯器上報自身 dirty 狀態(以 instance id 為鍵) */
  setDirty: (id: string, dirty: boolean) => void
  /** 有未儲存草稿時先確認再執行;乾淨則直接執行 */
  guard: (action: () => void) => void
}

/** 預設值供未包 Provider 的情境(直接執行,不攔) */
const DirtyGuardContext = createContext<DirtyGuardValue>({
  setDirty: (): void => undefined,
  guard: (action: () => void): void => action(),
})

/**
 * 把編輯器的 dirty 狀態上報給頁面層守衛;卸載時自動註銷。
 *
 * 註冊表放 ref 不放 state:守衛只在使用者操作當下讀取,不需要因 dirty 變動重繪整頁。
 */
function useReportDirty(dirty: boolean): void {
  const id = useId()
  const { setDirty } = useContext(DirtyGuardContext)
  useEffect(() => {
    setDirty(id, dirty)
    return () => setDirty(id, false)
  }, [id, dirty, setDirty])
}

interface DirtyGuardProviderProps {
  children: React.ReactNode
}

function DirtyGuardProvider({ children }: DirtyGuardProviderProps): React.ReactNode {
  const dirtyIds = useRef<Set<string>>(new Set())
  const [pendingAction, setPendingAction] = useState<(() => void) | null>(null)

  const setDirty = useCallback((id: string, dirty: boolean): void => {
    if (dirty) dirtyIds.current.add(id)
    else dirtyIds.current.delete(id)
  }, [])

  const guard = useCallback((action: () => void): void => {
    if (dirtyIds.current.size === 0) {
      action()
      return
    }
    setPendingAction(() => action)
  }, [])

  const value = useMemo((): DirtyGuardValue => ({ setDirty, guard }), [setDirty, guard])

  const confirmLeave = useCallback((): void => {
    const action = pendingAction
    setPendingAction(null)
    if (action !== null) action()
  }, [pendingAction])
  const cancelLeave = useCallback((): void => setPendingAction(null), [])

  return (
    <DirtyGuardContext.Provider value={value}>
      {children}
      <ConfirmDialog
        open={pendingAction !== null}
        title="尚有未儲存的變更"
        confirmLabel="離開並捨棄"
        tone="danger"
        onConfirm={confirmLeave}
        onCancel={cancelLeave}
      >
        <p>目前的勾選尚未儲存,離開後將直接捨棄。確定要離開?</p>
        <p>若要保留,請先取消並按下編輯區的儲存按鈕。</p>
      </ConfirmDialog>
    </DirtyGuardContext.Provider>
  )
}

/* ---------------------------------------------------------------------- */
/* 共用小元件                                                                */
/* ---------------------------------------------------------------------- */

interface InlineErrorProps {
  message: string | null
}

function InlineError({ message }: InlineErrorProps): React.ReactNode {
  if (message === null) return null
  return (
    <p role="alert" className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger md:text-base">
      {message}
    </p>
  )
}

interface InlineNoticeProps {
  message: string | null
}

function InlineNotice({ message }: InlineNoticeProps): React.ReactNode {
  if (message === null) return null
  return (
    <p className="rounded-lg bg-success/15 px-3 py-2 text-sm text-success md:text-base">
      {message}
    </p>
  )
}

interface EmptyStateProps {
  message: string
}

function EmptyState({ message }: EmptyStateProps): React.ReactNode {
  return (
    <p className="px-3 py-8 text-center text-sm text-muted-foreground md:text-base">{message}</p>
  )
}

/**
 * 讀取失敗提示 + 重試;整批置換類編輯器共用。
 *
 * 這三個編輯器的儲存都是「整批置換」,沒讀到伺服器現況就編輯等於拿空草稿覆蓋既有設定,
 * 故失敗時一律以本元件取代編輯區,不給編輯入口。
 */
interface LoadFailedNoticeProps {
  message: string
  onRetry: () => void
}

function LoadFailedNotice({ message, onRetry }: LoadFailedNoticeProps): React.ReactNode {
  return (
    <div className="flex flex-col items-start gap-3">
      <InlineError message={message} />
      <button type="button" onClick={onRetry} className="df-btn-outline min-h-[44px] px-4">
        重新載入
      </button>
    </div>
  )
}

/** 整批存檔列(作業範圍 / 勾選作業 / 授權矩陣三處共用) */
interface EditorActionsProps {
  dirty: boolean
  saving: boolean
  saveLabel: string
  onSave: () => void
  onReset: () => void
}

function EditorActions({
  dirty,
  saving,
  saveLabel,
  onSave,
  onReset,
}: EditorActionsProps): React.ReactNode {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <button
        type="button"
        onClick={onSave}
        disabled={!dirty || saving}
        className="df-btn-primary"
      >
        {saving ? '儲存中…' : saveLabel}
      </button>
      <button
        type="button"
        onClick={onReset}
        disabled={!dirty || saving}
        className="df-btn-outline min-h-[44px] px-4"
      >
        還原
      </button>
      <span className="text-sm text-muted-foreground md:text-base">
        {dirty ? '有未儲存的變更' : '已與伺服器一致'}
      </span>
    </div>
  )
}

/** 「新增」按鈕(各 section 卡片標題列右側,開啟對應建立對話框) */
interface CreateButtonProps {
  label: string
  disabled?: boolean
  onClick: () => void
}

function CreateButton({ label, disabled = false, onClick }: CreateButtonProps): React.ReactNode {
  return (
    <button type="button" onClick={onClick} disabled={disabled} className="df-btn-primary">
      {label}
    </button>
  )
}

/**
 * 建立對話框外殼(遮罩 + df-card + Esc / 點遮罩關閉);沿用 api-clients 頁建立對話框版式。
 *
 * 只在開啟時掛載(由父層條件 render),故欄位 state 每次開啟都是乾淨的。
 */
interface FormDialogProps {
  title: string
  submitLabel: string
  submitDisabled: boolean
  errorMessage: string | null
  onSubmit: (event: React.FormEvent<HTMLFormElement>) => void
  onCancel: () => void
  children: React.ReactNode
}

function FormDialog({
  title,
  submitLabel,
  submitDisabled,
  errorMessage,
  onSubmit,
  onCancel,
  children,
}: FormDialogProps): React.ReactNode {
  useEffect(() => {
    const onKey = (event: KeyboardEvent): void => {
      if (event.key === 'Escape') onCancel()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onCancel])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        aria-label="關閉對話框"
        onClick={onCancel}
        className="absolute inset-0 cursor-default bg-black/40"
      />
      <form
        onSubmit={onSubmit}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="df-card relative z-10 flex max-h-[90vh] w-full max-w-xl flex-col gap-4 overflow-y-auto p-6 md:p-8"
      >
        <h2 className="text-lg font-bold text-foreground md:text-xl">{title}</h2>
        <InlineError message={errorMessage} />
        {children}
        <div className="mt-1 flex gap-3">
          <button
            type="button"
            onClick={onCancel}
            className="df-btn-outline min-h-[52px] flex-1 border-2 text-base font-semibold md:text-lg"
          >
            取消
          </button>
          <button
            type="submit"
            disabled={submitDisabled}
            className="df-btn-primary min-h-[52px] flex-1 text-base font-semibold md:text-lg"
          >
            {submitLabel}
          </button>
        </div>
      </form>
    </div>
  )
}

/** 名稱 + 說明(選填)建立對話框;作業 / 角色權限設定檔 / 臨時權限組共用同一形狀 */
interface NameDescriptionCreateDialogProps {
  title: string
  nameLabel: string
  submitLabel: string
  submitting: boolean
  submitError: string | null
  onSubmit: (payload: { name: string; description: string | null }) => void
  onCancel: () => void
}

function NameDescriptionCreateDialog({
  title,
  nameLabel,
  submitLabel,
  submitting,
  submitError,
  onSubmit,
  onCancel,
}: NameDescriptionCreateDialogProps): React.ReactNode {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')

  const handleNameChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>): void => setName(event.target.value),
    [],
  )
  const handleDescriptionChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>): void => setDescription(event.target.value),
    [],
  )
  const handleSubmit = useCallback(
    (event: React.FormEvent<HTMLFormElement>): void => {
      event.preventDefault()
      const trimmedName = name.trim()
      if (trimmedName === '') return
      onSubmit({
        name: trimmedName,
        description: description.trim() === '' ? null : description.trim(),
      })
    },
    [name, description, onSubmit],
  )

  return (
    <FormDialog
      title={title}
      submitLabel={submitting ? '建立中…' : submitLabel}
      submitDisabled={submitting || name.trim() === ''}
      errorMessage={submitError}
      onSubmit={handleSubmit}
      onCancel={onCancel}
    >
      <label className="flex flex-col gap-1.5 text-sm font-medium text-foreground md:text-base">
        {nameLabel}
        <input
          type="text"
          value={name}
          onChange={handleNameChange}
          required
          className="df-input"
        />
      </label>
      <label className="flex flex-col gap-1.5 text-sm font-medium text-foreground md:text-base">
        說明(選填)
        <input
          type="text"
          value={description}
          onChange={handleDescriptionChange}
          className="df-input"
        />
      </label>
    </FormDialog>
  )
}

/** 名稱 / 說明 / 建立時間 / 操作 的清單表格;角色權限設定檔 / 臨時權限組共用同一欄位形狀 */
interface SimpleNamedEntity {
  uid: string
  name: string
  description: string | null
  created_at: string
}

interface SimpleEntityTableProps<T extends SimpleNamedEntity> {
  items: T[]
  emptyMessage: string
  selectedUid: string | null
  deletingUid: string | null
  onSelect: (item: T) => void
  onDelete: (item: T) => void
}

function SimpleEntityTable<T extends SimpleNamedEntity>({
  items,
  emptyMessage,
  selectedUid,
  deletingUid,
  onSelect,
  onDelete,
}: SimpleEntityTableProps<T>): React.ReactNode {
  if (items.length === 0) return <EmptyState message={emptyMessage} />
  return (
    <table className="df-table min-w-[720px]">
      <thead>
        <tr className="border-b border-border bg-muted/50">
          <th className="df-th">名稱</th>
          <th className="df-th">說明</th>
          <th className="df-th">建立時間</th>
          <th className="df-th">操作</th>
        </tr>
      </thead>
      <tbody>
        {items.map((item) => {
          const active = item.uid === selectedUid
          return (
            <tr
              key={item.uid}
              className={`cursor-pointer border-b border-border transition-colors last:border-b-0 hover:bg-muted/50 ${active ? 'bg-primary/10' : ''}`}
              onClick={() => onSelect(item)}
            >
              <td className="df-td font-medium text-foreground">{item.name}</td>
              <td className="df-td text-muted-foreground">{item.description ?? '—'}</td>
              <td className="df-td text-muted-foreground">{formatDateTime(item.created_at)}</td>
              <td className="df-td">
                <span className="flex gap-2">
                  <button
                    type="button"
                    onClick={(event) => {
                      event.stopPropagation()
                      onSelect(item)
                    }}
                    className="df-btn-outline min-h-[36px] whitespace-nowrap px-3"
                  >
                    設定授權
                  </button>
                  <button
                    type="button"
                    onClick={(event) => {
                      event.stopPropagation()
                      onDelete(item)
                    }}
                    disabled={deletingUid === item.uid}
                    className="df-btn-danger-soft min-h-0 whitespace-nowrap rounded-full px-3 py-1 text-sm"
                  >
                    刪除
                  </button>
                </span>
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

/* ---------------------------------------------------------------------- */
/* 作業範圍(表 × 欄位)編輯                                                 */
/* ---------------------------------------------------------------------- */

/** 可授權的表:須有 confirmed 表層級英文名(對齊後端 `_load_confirmed_semantic`) */
interface AuthorizableTable {
  rawName: string
  englishName: string
  zhName: string | null
}

interface ColumnOption {
  englishName: string
  zhName: string | null
}

interface ScopeChipProps {
  tableName: string
  columnName: string
  onRemove: (tableName: string, columnName: string) => void
}

const ScopeChip = memo(function ScopeChip({
  tableName,
  columnName,
  onRemove,
}: ScopeChipProps): React.ReactNode {
  return (
    <button
      type="button"
      onClick={() => onRemove(tableName, columnName)}
      aria-label={`移除 ${tableName}.${columnLabel(columnName)}`}
      className="inline-flex min-h-[36px] items-center gap-2 rounded-full border border-border bg-card px-3 py-1 font-mono text-sm text-foreground transition-colors hover:border-danger hover:text-danger"
    >
      {columnLabel(columnName)}
      <span aria-hidden="true">×</span>
    </button>
  )
})

interface OperationScopeEditorProps {
  operation: ClientSettingOperation
}

/**
 * 作業範圍編輯:選表 → 勾欄位(含「全欄位(*)」表級快捷)→ 整批 PUT 置換。
 *
 * 選項來源為 confirmed 語意映射(英文語意名);後端以同一份資料再驗一次,
 * 超出者一次列明回 422 並直接顯示於下方。
 */
function OperationScopeEditor({ operation }: OperationScopeEditorProps): React.ReactNode {
  const { data, isLoading, isError, refetch } = useListOperationItemsQuery(operation.uid)
  const [replaceOperationItems, { isLoading: isSaving }] = useReplaceOperationItemsMutation()
  const { data: semanticTables, isError: isTablesError } = useListSemanticTablesQuery()

  const [draftKeys, setDraftKeys] = useState<readonly string[]>([])
  const [syncedSignature, setSyncedSignature] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [rawTable, setRawTable] = useState('')

  const serverKeys = useMemo(
    (): string[] =>
      (data?.items ?? []).map((item) => scopeKey(item.table_name, item.column_name)).sort(),
    [data],
  )
  // 伺服器資料變動(首次載入 / 儲存成功)時才重置草稿;編輯中的重繪不覆寫
  const signature = data === undefined ? null : serverKeys.join('|')
  if (signature !== null && signature !== syncedSignature) {
    setSyncedSignature(signature)
    setDraftKeys(serverKeys)
    setSaveError(null)
  }

  const authorizableTables = useMemo((): AuthorizableTable[] => {
    const out: AuthorizableTable[] = []
    for (const table of semanticTables ?? []) {
      if (table.english_name === null || table.english_name === '') continue
      if (table.confirmed_count === 0) continue
      out.push({
        rawName: table.table_name,
        englishName: table.english_name,
        zhName: table.zh_name,
      })
    }
    out.sort((a, b) => a.englishName.localeCompare(b.englishName))
    return out
  }, [semanticTables])

  const zhNameByEnglishTable = useMemo(
    (): Map<string, string> => buildTableZhMap(semanticTables),
    [semanticTables],
  )

  const selectedTable = useMemo(
    (): AuthorizableTable | null =>
      authorizableTables.find((table) => table.rawName === rawTable) ?? null,
    [authorizableTables, rawTable],
  )

  const columnQueryArg = useMemo(
    (): ListSemanticMappingsParams | typeof skipToken =>
      selectedTable === null
        ? skipToken
        : {
            table: selectedTable.rawName,
            status: 'confirmed',
            keyword: '',
            page: 1,
            pageSize: COLUMN_PAGE_SIZE,
          },
    [selectedTable],
  )
  const {
    data: columnData,
    isFetching: isColumnsFetching,
    isError: isColumnsError,
  } = useListSemanticMappingsQuery(columnQueryArg)

  // 表層級列(column_name = '')未 confirmed 的表沒有可用英文表名 → 後端一律視為不可授權。
  // 僅在「確實取得資料」時才成立;載入失敗不得被誤判為「尚未確認映射」
  const tableLevelConfirmed = useMemo(
    (): boolean => (columnData?.items ?? []).some((item) => item.column_name === ''),
    [columnData],
  )
  const columnsLoaded = columnData !== undefined && !isColumnsError

  const columnOptions = useMemo((): ColumnOption[] => {
    const seen = new Set<string>()
    const out: ColumnOption[] = []
    for (const item of columnData?.items ?? []) {
      // 表層級列(column_name = '')只提供表英文名,不是可授權欄位
      if (item.column_name === '' || item.english_name === '') continue
      if (seen.has(item.english_name)) continue
      seen.add(item.english_name)
      out.push({ englishName: item.english_name, zhName: item.zh_name })
    }
    out.sort((a, b) => a.englishName.localeCompare(b.englishName))
    return out
  }, [columnData])

  const draftSet = useMemo((): Set<string> => new Set(draftKeys), [draftKeys])
  const draftGroups = useMemo((): TableGroup[] => {
    const items: ScopeItem[] = []
    for (const key of draftKeys) {
      const parsed = parseScopeKey(key)
      if (parsed !== null) items.push(parsed)
    }
    return groupByTable(items)
  }, [draftKeys])

  // 讀不到伺服器現況就不准整批覆蓋:草稿與 serverKeys 都會算成空,存檔即把既有範圍洗掉
  const loadFailed = isError || data === undefined
  const dirty = !loadFailed && !sameKeys(draftKeys, serverKeys)
  useReportDirty(dirty)

  const toggleScope = useCallback((tableName: string, columnName: string): void => {
    const key = scopeKey(tableName, columnName)
    setNotice(null)
    setDraftKeys((prev) =>
      prev.includes(key) ? prev.filter((item) => item !== key) : [...prev, key].sort(),
    )
  }, [])

  const handleRemove = useCallback(
    (tableName: string, columnName: string): void => toggleScope(tableName, columnName),
    [toggleScope],
  )

  const handleReset = useCallback((): void => {
    setDraftKeys(serverKeys)
    setSaveError(null)
    setNotice(null)
  }, [serverKeys])

  const handleSave = useCallback(async (): Promise<void> => {
    setSaveError(null)
    setNotice(null)
    const items: ScopeItem[] = []
    for (const key of draftKeys) {
      const parsed = parseScopeKey(key)
      if (parsed !== null) items.push(parsed)
    }
    const result = await replaceOperationItems({ uid: operation.uid, items })
    if ('error' in result) {
      setSaveError(extractApiErrorDetail(result.error, '儲存作業範圍失敗,請稍後再試'))
      return
    }
    setNotice(`已儲存作業範圍(${items.length} 項)`)
  }, [draftKeys, operation.uid, replaceOperationItems])

  const handleTableChange = useCallback(
    (event: React.ChangeEvent<HTMLSelectElement>): void => setRawTable(event.target.value),
    [],
  )

  const handleRetry = useCallback((): void => {
    void refetch()
  }, [refetch])

  if (isLoading || loadFailed) {
    return (
      <div className="df-card flex flex-col gap-4 p-4 md:p-5">
        <h2 className="text-base font-semibold text-foreground md:text-lg">
          作業範圍({operation.name})
        </h2>
        {isLoading ? (
          <p className="text-sm text-muted-foreground md:text-base">載入中…</p>
        ) : (
          <LoadFailedNotice
            message="載入作業範圍失敗;讀不到目前設定前不開放編輯(整批儲存會覆蓋既有範圍)"
            onRetry={handleRetry}
          />
        )}
      </div>
    )
  }

  return (
    <div className="df-card flex flex-col gap-4 p-4 md:p-5">
      <h2 className="text-base font-semibold text-foreground md:text-lg">
        作業範圍({operation.name})
      </h2>
      <p className="text-sm text-muted-foreground md:text-base">
        設定此作業最多可碰到的表 × 欄位;角色權限設定檔 / 臨時權限組的授權矩陣以此為上限(給不出範圍外的欄位)
      </p>

      {isTablesError ? <InlineError message="載入語意映射表清單失敗,請稍後再試" /> : null}

      {authorizableTables.length === 0 && !isTablesError ? (
        <EmptyState message={`尚無可授權的資料表。${CONFIRMED_MAPPING_HINT}`} />
      ) : (
        <>
          <label className="flex flex-col gap-1.5 text-sm font-medium text-foreground md:text-base">
            資料表(僅列已確認語意映射)
            <select value={rawTable} onChange={handleTableChange} className="df-input">
              <option value="">請選擇資料表</option>
              {authorizableTables.map((table) => (
                <option key={table.rawName} value={table.rawName}>
                  {table.zhName !== null && table.zhName !== ''
                    ? `${table.zhName}(${table.englishName})`
                    : table.englishName}
                </option>
              ))}
            </select>
          </label>

          {selectedTable !== null && isColumnsError ? (
            <InlineError message="載入欄位選項失敗,請稍後再試" />
          ) : null}

          {selectedTable !== null && columnsLoaded && !isColumnsFetching && !tableLevelConfirmed ? (
            <EmptyState
              message={`此表尚未確認「表層級」語意映射(表名英文對照),後端不接受授權。${CONFIRMED_MAPPING_HINT}`}
            />
          ) : null}

          {selectedTable !== null && !isColumnsError && (tableLevelConfirmed || isColumnsFetching) ? (
            <div className="flex flex-col gap-3 rounded-lg border border-border p-3 md:p-4">
              <p className="text-sm font-medium text-foreground md:text-base">
                欄位(勾選即加入範圍)
              </p>
              {isColumnsFetching ? (
                <p className="text-sm text-muted-foreground md:text-base">載入欄位中…</p>
              ) : null}
              <label className="flex min-h-[44px] items-center gap-2 text-sm text-foreground md:text-base">
                <input
                  type="checkbox"
                  checked={draftSet.has(scopeKey(selectedTable.englishName, ALL_COLUMNS))}
                  onChange={() => toggleScope(selectedTable.englishName, ALL_COLUMNS)}
                  className={CHECKBOX_CLASS}
                />
                <span className="font-medium">全欄位(*)</span>
                <span className="text-muted-foreground">— 該表所有欄位一次開放</span>
              </label>
              {columnOptions.length === 0 && columnsLoaded && !isColumnsFetching ? (
                <EmptyState message={`此表尚無已確認的欄位映射。${CONFIRMED_MAPPING_HINT}`} />
              ) : (
                <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {columnOptions.map((column) => (
                    <label
                      key={column.englishName}
                      className="flex min-h-[44px] items-center gap-2 text-sm text-foreground md:text-base"
                    >
                      <input
                        type="checkbox"
                        checked={draftSet.has(
                          scopeKey(selectedTable.englishName, column.englishName),
                        )}
                        onChange={() =>
                          toggleScope(selectedTable.englishName, column.englishName)
                        }
                        className={CHECKBOX_CLASS}
                      />
                      <span className="font-mono">{column.englishName}</span>
                      {column.zhName !== null && column.zhName !== '' ? (
                        <span className="text-muted-foreground">{column.zhName}</span>
                      ) : null}
                    </label>
                  ))}
                </div>
              )}
            </div>
          ) : null}
        </>
      )}

      <div className="flex flex-col gap-3">
        <p className="text-sm font-medium text-foreground md:text-base">
          目前範圍({draftKeys.length} 項)
        </p>
        {draftGroups.length === 0 ? (
          <EmptyState message="尚未選擇任何表 / 欄位(範圍為空 = 此作業給不出任何資料)" />
        ) : (
          draftGroups.map((group) => {
            const tableZh = zhNameByEnglishTable.get(group.tableName)
            return (
              <div key={group.tableName} className="flex flex-col gap-2">
                <p className="text-sm text-muted-foreground md:text-base">
                  <span className="font-mono text-foreground">{group.tableName}</span>
                  {tableZh !== undefined ? `(${tableZh})` : ''}
                </p>
                <div className="flex flex-wrap gap-2">
                  {group.columns.map((column) => (
                    <ScopeChip
                      key={column}
                      tableName={group.tableName}
                      columnName={column}
                      onRemove={handleRemove}
                    />
                  ))}
                </div>
              </div>
            )
          })
        )}
      </div>

      <EditorActions
        dirty={dirty}
        saving={isSaving}
        saveLabel="儲存作業範圍"
        onSave={handleSave}
        onReset={handleReset}
      />

      <InlineError message={saveError} />
      <InlineNotice message={notice} />
    </div>
  )
}

/* ---------------------------------------------------------------------- */
/* 服務 / 作業                                                              */
/* ---------------------------------------------------------------------- */

interface ServiceCreateDialogProps {
  submitting: boolean
  submitError: string | null
  onSubmit: (payload: CreateClientSettingServicePayload) => void
  onCancel: () => void
}

function ServiceCreateDialog({
  submitting,
  submitError,
  onSubmit,
  onCancel,
}: ServiceCreateDialogProps): React.ReactNode {
  const [code, setCode] = useState('')
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [codeError, setCodeError] = useState<string | null>(null)

  const handleCodeChange = useCallback((event: React.ChangeEvent<HTMLInputElement>): void => {
    setCode(event.target.value)
    setCodeError(null)
  }, [])
  const handleNameChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>): void => setName(event.target.value),
    [],
  )
  const handleDescriptionChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>): void => setDescription(event.target.value),
    [],
  )
  const handleSubmit = useCallback(
    (event: React.FormEvent<HTMLFormElement>): void => {
      event.preventDefault()
      const trimmedCode = code.trim()
      const trimmedName = name.trim()
      if (trimmedCode === '' || trimmedName === '') return
      if (!SERVICE_CODE_RE.test(trimmedCode)) {
        setCodeError(SERVICE_CODE_ERROR)
        return
      }
      setCodeError(null)
      onSubmit({
        code: trimmedCode,
        name: trimmedName,
        description: description.trim() === '' ? null : description.trim(),
      })
    },
    [code, name, description, onSubmit],
  )

  return (
    <FormDialog
      title="新增服務"
      submitLabel={submitting ? '建立中…' : '建立服務'}
      submitDisabled={submitting || code.trim() === '' || name.trim() === ''}
      errorMessage={submitError}
      onSubmit={handleSubmit}
      onCancel={onCancel}
    >
      <label className="flex flex-col gap-1.5 text-sm font-medium text-foreground md:text-base">
        服務代碼
        <input
          type="text"
          value={code}
          onChange={handleCodeChange}
          placeholder="例 erp / crm / hrm"
          required
          aria-invalid={codeError !== null}
          className="df-input font-mono"
        />
        <span className="text-sm font-normal text-muted-foreground">{SERVICE_CODE_HINT}</span>
      </label>
      <InlineError message={codeError} />
      <label className="flex flex-col gap-1.5 text-sm font-medium text-foreground md:text-base">
        顯示名稱
        <input
          type="text"
          value={name}
          onChange={handleNameChange}
          required
          className="df-input"
        />
      </label>
      <label className="flex flex-col gap-1.5 text-sm font-medium text-foreground md:text-base">
        說明(選填)
        <input
          type="text"
          value={description}
          onChange={handleDescriptionChange}
          className="df-input"
        />
      </label>
    </FormDialog>
  )
}

interface ServiceTableProps {
  items: ClientSettingService[]
  selectedUid: string | null
  deletingUid: string | null
  onSelect: (service: ClientSettingService) => void
  onDelete: (service: ClientSettingService) => void
}

const ServiceTable = memo(function ServiceTable({
  items,
  selectedUid,
  deletingUid,
  onSelect,
  onDelete,
}: ServiceTableProps): React.ReactNode {
  if (items.length === 0) return <EmptyState message="尚無服務" />
  return (
    <table className="df-table min-w-[720px]">
      <thead>
        <tr className="border-b border-border bg-muted/50">
          <th className="df-th">代碼</th>
          <th className="df-th">顯示名稱</th>
          <th className="df-th">說明</th>
          <th className="df-th">操作</th>
        </tr>
      </thead>
      <tbody>
        {items.map((service) => {
          const active = service.uid === selectedUid
          return (
            <tr
              key={service.uid}
              className={`cursor-pointer border-b border-border transition-colors last:border-b-0 hover:bg-muted/50 ${active ? 'bg-primary/10' : ''}`}
              onClick={() => onSelect(service)}
            >
              <td className="df-td font-mono text-sm">{service.code}</td>
              <td className="df-td font-medium text-foreground">{service.name}</td>
              <td className="df-td text-muted-foreground">{service.description ?? '—'}</td>
              <td className="df-td">
                <button
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation()
                    onDelete(service)
                  }}
                  disabled={deletingUid === service.uid}
                  className="df-btn-danger-soft min-h-0 whitespace-nowrap rounded-full px-3 py-1 text-sm"
                >
                  刪除
                </button>
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
})

interface OperationTableProps {
  items: ClientSettingOperation[]
  selectedUid: string | null
  deletingUid: string | null
  onSelect: (operation: ClientSettingOperation) => void
  onDelete: (operation: ClientSettingOperation) => void
}

const OperationTable = memo(function OperationTable({
  items,
  selectedUid,
  deletingUid,
  onSelect,
  onDelete,
}: OperationTableProps): React.ReactNode {
  if (items.length === 0) return <EmptyState message="尚無作業" />
  return (
    <table className="df-table min-w-[640px]">
      <thead>
        <tr className="border-b border-border bg-muted/50">
          <th className="df-th">名稱</th>
          <th className="df-th">說明</th>
          <th className="df-th">操作</th>
        </tr>
      </thead>
      <tbody>
        {items.map((operation) => {
          const active = operation.uid === selectedUid
          return (
            <tr
              key={operation.uid}
              className={`cursor-pointer border-b border-border transition-colors last:border-b-0 hover:bg-muted/50 ${active ? 'bg-primary/10' : ''}`}
              onClick={() => onSelect(operation)}
            >
              <td className="df-td font-medium text-foreground">{operation.name}</td>
              <td className="df-td text-muted-foreground">{operation.description ?? '—'}</td>
              <td className="df-td">
                <span className="flex gap-2">
                  <button
                    type="button"
                    onClick={(event) => {
                      event.stopPropagation()
                      onSelect(operation)
                    }}
                    className="df-btn-outline min-h-[36px] whitespace-nowrap px-3"
                  >
                    設定範圍
                  </button>
                  <button
                    type="button"
                    onClick={(event) => {
                      event.stopPropagation()
                      onDelete(operation)
                    }}
                    disabled={deletingUid === operation.uid}
                    className="df-btn-danger-soft min-h-0 whitespace-nowrap rounded-full px-3 py-1 text-sm"
                  >
                    刪除
                  </button>
                </span>
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
})

function ServicesOperationsSection(): React.ReactNode {
  const [selectedService, setSelectedService] = useState<ClientSettingService | null>(null)
  const [selectedOperation, setSelectedOperation] = useState<ClientSettingOperation | null>(null)
  const [serviceCreateOpen, setServiceCreateOpen] = useState(false)
  const [serviceCreateError, setServiceCreateError] = useState<string | null>(null)
  const [serviceDeleteTarget, setServiceDeleteTarget] = useState<ClientSettingService | null>(
    null,
  )
  const [serviceDeleteError, setServiceDeleteError] = useState<string | null>(null)
  const [operationCreateOpen, setOperationCreateOpen] = useState(false)
  const [operationCreateError, setOperationCreateError] = useState<string | null>(null)
  const [operationDeleteTarget, setOperationDeleteTarget] =
    useState<ClientSettingOperation | null>(null)
  const [operationDeleteError, setOperationDeleteError] = useState<string | null>(null)

  const {
    data: serviceData,
    isLoading: isServicesLoading,
    isError: isServicesError,
  } = useListServicesQuery()
  const [createService, { isLoading: isCreatingService }] = useCreateServiceMutation()
  const [deleteService, { isLoading: isDeletingService }] = useDeleteServiceMutation()

  const {
    data: operationData,
    isLoading: isOperationsLoading,
    isError: isOperationsError,
  } = useListOperationsQuery(selectedService?.uid ?? undefined, { skip: selectedService === null })
  const [createOperation, { isLoading: isCreatingOperation }] = useCreateOperationMutation()
  const [deleteOperation, { isLoading: isDeletingOperation }] = useDeleteOperationMutation()

  const services = useMemo((): ClientSettingService[] => serviceData?.items ?? [], [serviceData])
  const operations = useMemo(
    (): ClientSettingOperation[] => operationData?.items ?? [],
    [operationData],
  )

  // 作業清單換了(切服務 / 刪除)後,已選作業可能不在清單內 → 收起範圍編輯區
  if (
    selectedOperation !== null &&
    operationData !== undefined &&
    !operations.some((operation) => operation.uid === selectedOperation.uid)
  ) {
    setSelectedOperation(null)
  }

  const { guard } = useContext(DirtyGuardContext)

  const handleSelectService = useCallback(
    (service: ClientSettingService): void =>
      guard(() => {
        setSelectedService(service)
        setSelectedOperation(null)
      }),
    [guard],
  )

  const handleSelectOperation = useCallback(
    (operation: ClientSettingOperation): void => guard(() => setSelectedOperation(operation)),
    [guard],
  )

  const openServiceCreate = useCallback((): void => {
    setServiceCreateError(null)
    setServiceCreateOpen(true)
  }, [])
  const cancelServiceCreate = useCallback((): void => setServiceCreateOpen(false), [])
  const handleCreateService = useCallback(
    async (payload: CreateClientSettingServicePayload): Promise<void> => {
      setServiceCreateError(null)
      const result = await createService(payload)
      if ('error' in result) {
        setServiceCreateError(extractApiErrorDetail(result.error, '建立服務失敗,請稍後再試'))
        return
      }
      setServiceCreateOpen(false)
    },
    [createService],
  )

  const requestDeleteService = useCallback((service: ClientSettingService): void => {
    setServiceDeleteError(null)
    setServiceDeleteTarget(service)
  }, [])
  const cancelDeleteService = useCallback((): void => setServiceDeleteTarget(null), [])
  const confirmDeleteService = useCallback(async (): Promise<void> => {
    if (serviceDeleteTarget === null) return
    setServiceDeleteError(null)
    const target = serviceDeleteTarget
    const result = await deleteService(target.uid)
    setServiceDeleteTarget(null)
    if ('error' in result) {
      setServiceDeleteError(extractApiErrorDetail(result.error, '刪除服務失敗,請稍後再試'))
      return
    }
    if (selectedService?.uid === target.uid) {
      setSelectedService(null)
      setSelectedOperation(null)
    }
  }, [serviceDeleteTarget, deleteService, selectedService])

  const openOperationCreate = useCallback((): void => {
    setOperationCreateError(null)
    setOperationCreateOpen(true)
  }, [])
  const cancelOperationCreate = useCallback((): void => setOperationCreateOpen(false), [])
  const handleCreateOperation = useCallback(
    async (payload: { name: string; description: string | null }): Promise<void> => {
      if (selectedService === null) return
      setOperationCreateError(null)
      const body: CreateClientSettingOperationPayload = {
        service_uid: selectedService.uid,
        name: payload.name,
        description: payload.description,
      }
      const result = await createOperation(body)
      if ('error' in result) {
        setOperationCreateError(extractApiErrorDetail(result.error, '建立作業失敗,請稍後再試'))
        return
      }
      setOperationCreateOpen(false)
    },
    [selectedService, createOperation],
  )

  const requestDeleteOperation = useCallback((operation: ClientSettingOperation): void => {
    setOperationDeleteError(null)
    setOperationDeleteTarget(operation)
  }, [])
  const cancelDeleteOperation = useCallback((): void => setOperationDeleteTarget(null), [])
  const confirmDeleteOperation = useCallback(async (): Promise<void> => {
    if (operationDeleteTarget === null) return
    setOperationDeleteError(null)
    const result = await deleteOperation(operationDeleteTarget.uid)
    setOperationDeleteTarget(null)
    if ('error' in result) {
      setOperationDeleteError(extractApiErrorDetail(result.error, '刪除作業失敗,請稍後再試'))
    }
  }, [operationDeleteTarget, deleteOperation])

  return (
    <div className="flex flex-col gap-6">
      <div className="df-card flex flex-col gap-4 p-4 md:p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-base font-semibold text-foreground md:text-lg">服務名稱</h2>
          <CreateButton label="新增服務" onClick={openServiceCreate} />
        </div>
        {isServicesLoading ? (
          <p className="text-sm text-muted-foreground md:text-base">載入中…</p>
        ) : null}
        {isServicesError ? <InlineError message="載入服務清單失敗,請稍後再試" /> : null}
        {serviceData !== undefined ? (
          <div className="overflow-x-auto">
            <ServiceTable
              items={services}
              selectedUid={selectedService?.uid ?? null}
              deletingUid={isDeletingService ? (serviceDeleteTarget?.uid ?? null) : null}
              onSelect={handleSelectService}
              onDelete={requestDeleteService}
            />
          </div>
        ) : null}
      </div>

      <div className="df-card flex flex-col gap-4 p-4 md:p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-base font-semibold text-foreground md:text-lg">
            作業{selectedService !== null ? `(${selectedService.name})` : ''}
          </h2>
          <CreateButton
            label="新增作業"
            disabled={selectedService === null}
            onClick={openOperationCreate}
          />
        </div>
        <p className="text-sm text-muted-foreground md:text-base">{CONFIRMED_MAPPING_HINT}</p>
        {selectedService === null ? (
          <EmptyState message="請先於上方選取一個服務" />
        ) : (
          <>
            {isOperationsLoading ? (
              <p className="text-sm text-muted-foreground md:text-base">載入中…</p>
            ) : null}
            {isOperationsError ? <InlineError message="載入作業清單失敗,請稍後再試" /> : null}
            {operationData !== undefined ? (
              <div className="overflow-x-auto">
                <OperationTable
                  items={operations}
                  selectedUid={selectedOperation?.uid ?? null}
                  deletingUid={
                    isDeletingOperation ? (operationDeleteTarget?.uid ?? null) : null
                  }
                  onSelect={handleSelectOperation}
                  onDelete={requestDeleteOperation}
                />
              </div>
            ) : null}
          </>
        )}
      </div>

      {selectedOperation !== null ? (
        <OperationScopeEditor key={selectedOperation.uid} operation={selectedOperation} />
      ) : null}

      {serviceCreateOpen ? (
        <ServiceCreateDialog
          submitting={isCreatingService}
          submitError={serviceCreateError}
          onSubmit={handleCreateService}
          onCancel={cancelServiceCreate}
        />
      ) : null}

      {operationCreateOpen && selectedService !== null ? (
        <NameDescriptionCreateDialog
          title={`新增作業(${selectedService.name})`}
          nameLabel="作業名稱"
          submitLabel="建立作業"
          submitting={isCreatingOperation}
          submitError={operationCreateError}
          onSubmit={handleCreateOperation}
          onCancel={cancelOperationCreate}
        />
      ) : null}

      <ConfirmDialog
        open={serviceDeleteTarget !== null}
        title="刪除服務"
        confirmLabel="確認刪除"
        tone="danger"
        confirmDisabled={isDeletingService}
        onConfirm={confirmDeleteService}
        onCancel={cancelDeleteService}
      >
        {serviceDeleteTarget !== null ? <p>確定要刪除服務「{serviceDeleteTarget.name}」?</p> : null}
        <p>底下仍有作業時後端將拒絕刪除(409)。</p>
        <InlineError message={serviceDeleteError} />
      </ConfirmDialog>

      <ConfirmDialog
        open={operationDeleteTarget !== null}
        title="刪除作業"
        confirmLabel="確認刪除"
        tone="danger"
        confirmDisabled={isDeletingOperation}
        onConfirm={confirmDeleteOperation}
        onCancel={cancelDeleteOperation}
      >
        {operationDeleteTarget !== null ? (
          <p>確定要刪除作業「{operationDeleteTarget.name}」?</p>
        ) : null}
        <p>仍被角色權限設定檔 / 臨時權限組引用時後端將拒絕刪除(409)。</p>
        <InlineError message={operationDeleteError} />
      </ConfirmDialog>
    </div>
  )
}

/* ---------------------------------------------------------------------- */
/* 授權矩陣(角色權限設定檔 / 臨時權限組共用)                                 */
/* ---------------------------------------------------------------------- */

interface MatrixGroupHeaderProps {
  tableName: string
  tableLabel: string
  allRead: boolean
  allEdit: boolean
  onToggleAll: (tableName: string, action: PermissionAction, enabled: boolean) => void
}

const MatrixGroupHeader = memo(function MatrixGroupHeader({
  tableName,
  tableLabel,
  allRead,
  allEdit,
  onToggleAll,
}: MatrixGroupHeaderProps): React.ReactNode {
  return (
    <tr className="border-b border-border bg-muted/40">
      <th scope="row" className="df-th text-left">
        <span className="font-mono text-foreground">{tableName}</span>
        {tableLabel !== '' ? (
          <span className="ml-2 font-sans font-normal text-muted-foreground">{tableLabel}</span>
        ) : null}
      </th>
      {ACTIONS.map((action) => (
        <td key={action} className="df-td">
          <label className="flex min-h-[36px] items-center gap-2 text-sm text-muted-foreground md:text-base">
            <input
              type="checkbox"
              checked={action === 'read' ? allRead : allEdit}
              onChange={(event) => onToggleAll(tableName, action, event.target.checked)}
              aria-label={`${tableName} 全表${ACTION_LABELS[action]}`}
              className={CHECKBOX_CLASS}
            />
            全選
          </label>
        </td>
      ))}
    </tr>
  )
})

interface MatrixRowProps {
  tableName: string
  columnName: string
  read: boolean
  edit: boolean
  onToggle: (tableName: string, columnName: string, action: PermissionAction) => void
}

const MatrixRow = memo(function MatrixRow({
  tableName,
  columnName,
  read,
  edit,
  onToggle,
}: MatrixRowProps): React.ReactNode {
  return (
    <tr className="border-b border-border transition-colors last:border-b-0 hover:bg-muted/50">
      <td className="df-td pl-8 font-mono">{columnLabel(columnName)}</td>
      {ACTIONS.map((action) => (
        <td key={action} className="df-td">
          <input
            type="checkbox"
            checked={action === 'read' ? read : edit}
            onChange={() => onToggle(tableName, columnName, action)}
            aria-label={`${tableName}.${columnLabel(columnName)} ${ACTION_LABELS[action]}`}
            className={CHECKBOX_CLASS}
          />
        </td>
      ))}
    </tr>
  )
})

interface PermissionMatrixEditorProps {
  kind: PermissionSetKind
  targetUid: string
  operationUid: string
  operationName: string
}

/**
 * 單一作業的授權矩陣:列 = 該作業範圍項(表 × 欄位),欄 = read / edit;整批 PUT 置換。
 *
 * 可選全集刻意鎖在作業範圍內(後端以 ∩ 範圍上限把守,超出回 422),
 * 表級「全欄位(*)」隨範圍呈現為一列。
 */
function PermissionMatrixEditor({
  kind,
  targetUid,
  operationUid,
  operationName,
}: PermissionMatrixEditorProps): React.ReactNode {
  const isProfile = kind === 'profile'

  const {
    data: scopeData,
    isLoading: isScopeLoading,
    isError: isScopeError,
    refetch: refetchScope,
  } = useListOperationItemsQuery(operationUid)
  const { data: semanticTables } = useListSemanticTablesQuery()

  const profileItemsArg = useMemo(
    (): ListProfileItemsParams | typeof skipToken =>
      isProfile ? { uid: targetUid, operationUid } : skipToken,
    [isProfile, targetUid, operationUid],
  )
  const exceptionItemsArg = useMemo(
    (): ListExceptionItemsParams | typeof skipToken =>
      isProfile ? skipToken : { uid: targetUid, operationUid },
    [isProfile, targetUid, operationUid],
  )
  const profileItems = useListProfileItemsQuery(profileItemsArg)
  const exceptionItems = useListExceptionItemsQuery(exceptionItemsArg)
  const itemsData = isProfile ? profileItems.data : exceptionItems.data
  const isItemsError = isProfile ? profileItems.isError : exceptionItems.isError
  const isItemsLoading = isProfile ? profileItems.isLoading : exceptionItems.isLoading
  const refetchItems = isProfile ? profileItems.refetch : exceptionItems.refetch

  const [replaceProfileItems, { isLoading: isSavingProfile }] = useReplaceProfileItemsMutation()
  const [replaceExceptionItems, { isLoading: isSavingException }] =
    useReplaceExceptionItemsMutation()
  const isSaving = isProfile ? isSavingProfile : isSavingException

  const [draftKeys, setDraftKeys] = useState<readonly string[]>([])
  const [syncedSignature, setSyncedSignature] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const serverKeys = useMemo(
    (): string[] =>
      (itemsData?.items ?? [])
        .map((item) => grantKey(item.table_name, item.column_name, item.action))
        .sort(),
    [itemsData],
  )
  const signature = itemsData === undefined ? null : serverKeys.join('|')
  if (signature !== null && signature !== syncedSignature) {
    setSyncedSignature(signature)
    setDraftKeys(serverKeys)
    setSaveError(null)
  }

  const scopeItems = useMemo((): ScopeItem[] => scopeData?.items ?? [], [scopeData])
  const groups = useMemo((): TableGroup[] => groupByTable(scopeItems), [scopeItems])
  const columnsByTable = useMemo((): Map<string, string[]> => {
    const map = new Map<string, string[]>()
    for (const group of groups) map.set(group.tableName, group.columns)
    return map
  }, [groups])
  const zhNameByEnglishTable = useMemo(
    (): Map<string, string> => buildTableZhMap(semanticTables),
    [semanticTables],
  )

  const draftSet = useMemo((): Set<string> => new Set(draftKeys), [draftKeys])

  // 作業範圍事後縮小時,既有授權可能已落在範圍外(後端不連動清理)——這些項在矩陣上
  // 無列可呈現,若原樣送出必被 422 擋死,故列明後於儲存時一併移除
  const staleKeys = useMemo((): string[] => {
    const columnsByTableSet = new Map<string, Set<string>>()
    for (const group of groups) columnsByTableSet.set(group.tableName, new Set(group.columns))
    return draftKeys.filter((key) => {
      const parsed = parseGrantKey(key)
      if (parsed === null) return true
      const columns = columnsByTableSet.get(parsed.table_name)
      if (columns === undefined) return true
      // 範圍含 `*` = 全欄位開放,任何欄位都在上限內(對齊後端 `_within_scope`)
      if (columns.has(ALL_COLUMNS)) return false
      return parsed.column_name === ALL_COLUMNS || !columns.has(parsed.column_name)
    })
  }, [draftKeys, groups])

  // 範圍或既有授權任一讀不到,就不准整批覆蓋(見 LoadFailedNotice)
  const loadFailed =
    isScopeError || scopeData === undefined || isItemsError || itemsData === undefined
  const dirty = !loadFailed && (!sameKeys(draftKeys, serverKeys) || staleKeys.length > 0)
  useReportDirty(dirty)

  const handleToggle = useCallback(
    (tableName: string, columnName: string, action: PermissionAction): void => {
      const key = grantKey(tableName, columnName, action)
      setNotice(null)
      setDraftKeys((prev) =>
        prev.includes(key) ? prev.filter((item) => item !== key) : [...prev, key].sort(),
      )
    },
    [],
  )

  const handleToggleAll = useCallback(
    (tableName: string, action: PermissionAction, enabled: boolean): void => {
      const columns = columnsByTable.get(tableName) ?? []
      setNotice(null)
      setDraftKeys((prev) => {
        const next = new Set(prev)
        for (const column of columns) {
          const key = grantKey(tableName, column, action)
          if (enabled) next.add(key)
          else next.delete(key)
        }
        return [...next].sort()
      })
    },
    [columnsByTable],
  )

  const handleReset = useCallback((): void => {
    setDraftKeys(serverKeys)
    setSaveError(null)
    setNotice(null)
  }, [serverKeys])

  const handleSave = useCallback(async (): Promise<void> => {
    setSaveError(null)
    setNotice(null)
    const staleSet = new Set(staleKeys)
    const items: PermissionItem[] = []
    for (const key of draftKeys) {
      if (staleSet.has(key)) continue
      const parsed = parseGrantKey(key)
      if (parsed !== null) items.push(parsed)
    }
    const result = isProfile
      ? await replaceProfileItems({ uid: targetUid, operationUid, items })
      : await replaceExceptionItems({ uid: targetUid, operationUid, items })
    if ('error' in result) {
      setSaveError(extractApiErrorDetail(result.error, '儲存授權矩陣失敗,請稍後再試'))
      return
    }
    setNotice(`已儲存「${operationName}」授權(${items.length} 項)`)
  }, [
    draftKeys,
    isProfile,
    operationName,
    operationUid,
    replaceExceptionItems,
    replaceProfileItems,
    staleKeys,
    targetUid,
  ])

  const handleRetry = useCallback((): void => {
    void refetchScope()
    void refetchItems()
  }, [refetchScope, refetchItems])

  if (isScopeLoading || isItemsLoading) {
    return <p className="text-sm text-muted-foreground md:text-base">載入授權矩陣中…</p>
  }
  if (loadFailed) {
    return (
      <LoadFailedNotice
        message={
          isScopeError || scopeData === undefined
            ? '載入作業範圍失敗;讀不到範圍上限前不開放編輯授權矩陣'
            : '載入既有授權失敗;讀不到目前授權前不開放編輯(整批儲存會覆蓋既有授權)'
        }
        onRetry={handleRetry}
      />
    )
  }
  if (groups.length === 0) {
    return (
      <EmptyState message="此作業尚未設定範圍,請先至「服務 / 作業」分頁設定表 × 欄位範圍" />
    )
  }

  return (
    <div className="flex flex-col gap-4">
      {staleKeys.length > 0 ? (
        <InlineError
          message={`下列既有授權已超出目前作業範圍,儲存時將一併移除:${staleKeys
            .map((key) => key.split(KEY_SEP).join('.'))
            .join('、')}`}
        />
      ) : null}
      <div className="overflow-x-auto">
        <table className="df-table min-w-[560px]">
          <thead>
            <tr className="border-b border-border bg-muted/50">
              <th className="df-th">資料表 / 欄位</th>
              {ACTIONS.map((action) => (
                <th key={action} className="df-th w-24">
                  {ACTION_LABELS[action]}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {groups.map((group) => (
              <Fragment key={group.tableName}>
                <MatrixGroupHeader
                  tableName={group.tableName}
                  tableLabel={zhNameByEnglishTable.get(group.tableName) ?? ''}
                  allRead={group.columns.every((column) =>
                    draftSet.has(grantKey(group.tableName, column, 'read')),
                  )}
                  allEdit={group.columns.every((column) =>
                    draftSet.has(grantKey(group.tableName, column, 'edit')),
                  )}
                  onToggleAll={handleToggleAll}
                />
                {group.columns.map((column) => (
                  <MatrixRow
                    key={column}
                    tableName={group.tableName}
                    columnName={column}
                    read={draftSet.has(grantKey(group.tableName, column, 'read'))}
                    edit={draftSet.has(grantKey(group.tableName, column, 'edit'))}
                    onToggle={handleToggle}
                  />
                ))}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
      <EditorActions
        dirty={dirty}
        saving={isSaving}
        saveLabel="儲存授權矩陣"
        onSave={handleSave}
        onReset={handleReset}
      />
      <InlineError message={saveError} />
      <InlineNotice message={notice} />
    </div>
  )
}

interface ServiceOperationGroup {
  serviceUid: string
  serviceName: string
  operations: ClientSettingOperation[]
}

interface OperationPickerProps {
  groups: ServiceOperationGroup[]
  selectedUids: Set<string>
  onToggle: (operationUid: string) => void
}

const OperationPicker = memo(function OperationPicker({
  groups,
  selectedUids,
  onToggle,
}: OperationPickerProps): React.ReactNode {
  if (groups.length === 0) {
    return <EmptyState message="尚無作業,請先於「服務 / 作業」分頁建立" />
  }
  return (
    <div className="flex flex-col gap-4">
      {groups.map((group) => (
        <div key={group.serviceUid} className="flex flex-col gap-2">
          <p className="text-sm font-medium text-foreground md:text-base">{group.serviceName}</p>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {group.operations.map((operation) => (
              <label
                key={operation.uid}
                className="flex min-h-[44px] items-center gap-2 text-sm text-foreground md:text-base"
              >
                <input
                  type="checkbox"
                  checked={selectedUids.has(operation.uid)}
                  onChange={() => onToggle(operation.uid)}
                  className={CHECKBOX_CLASS}
                />
                {operation.name}
              </label>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
})

interface PermissionSetEditorProps {
  kind: PermissionSetKind
  targetUid: string
  targetName: string
}

/**
 * 角色權限設定檔 / 臨時權限組的授權編輯:先勾作業(整批置換),再逐作業設授權矩陣。
 *
 * 兩者端點對稱,故以 `kind` 分流:未選用的那一組 query 走 `skipToken` 不發請求。
 */
function PermissionSetEditor({
  kind,
  targetUid,
  targetName,
}: PermissionSetEditorProps): React.ReactNode {
  const isProfile = kind === 'profile'
  const kindLabel = isProfile ? '角色權限設定檔' : '臨時權限組'

  const { data: serviceData, isError: isServicesError } = useListServicesQuery()
  const {
    data: operationData,
    isError: isOperationsError,
    isLoading: isOperationsLoading,
    refetch: refetchOperations,
  } = useListOperationsQuery(undefined)

  const profileOperations = useListProfileOperationsQuery(isProfile ? targetUid : skipToken)
  const exceptionOperations = useListExceptionOperationsQuery(isProfile ? skipToken : targetUid)
  const grantedData = isProfile ? profileOperations.data : exceptionOperations.data
  const isGrantedError = isProfile ? profileOperations.isError : exceptionOperations.isError
  const isGrantedLoading = isProfile ? profileOperations.isLoading : exceptionOperations.isLoading
  const refetchGranted = isProfile ? profileOperations.refetch : exceptionOperations.refetch

  const [replaceProfileOperations, { isLoading: isSavingProfileOps }] =
    useReplaceProfileOperationsMutation()
  const [replaceExceptionOperations, { isLoading: isSavingExceptionOps }] =
    useReplaceExceptionOperationsMutation()
  const isSavingOperations = isProfile ? isSavingProfileOps : isSavingExceptionOps

  const [draftUids, setDraftUids] = useState<readonly string[]>([])
  const [syncedSignature, setSyncedSignature] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [matrixOperationUid, setMatrixOperationUid] = useState('')

  const serverUids = useMemo(
    (): string[] => (grantedData?.items ?? []).map((item) => item.operation_uid).sort(),
    [grantedData],
  )
  const signature = grantedData === undefined ? null : serverUids.join('|')
  if (signature !== null && signature !== syncedSignature) {
    setSyncedSignature(signature)
    setDraftUids(serverUids)
    setSaveError(null)
  }

  const operations = useMemo(
    (): ClientSettingOperation[] => operationData?.items ?? [],
    [operationData],
  )

  const groups = useMemo((): ServiceOperationGroup[] => {
    const serviceNameByUid = new Map<string, string>()
    for (const service of serviceData?.items ?? []) serviceNameByUid.set(service.uid, service.name)
    const operationsByService = new Map<string, ClientSettingOperation[]>()
    for (const operation of operations) {
      const existing = operationsByService.get(operation.service_uid)
      if (existing === undefined) operationsByService.set(operation.service_uid, [operation])
      else existing.push(operation)
    }
    const out: ServiceOperationGroup[] = []
    for (const [serviceUid, groupOperations] of operationsByService) {
      out.push({
        serviceUid,
        serviceName: serviceNameByUid.get(serviceUid) ?? '(未知服務)',
        operations: [...groupOperations].sort((a, b) => a.name.localeCompare(b.name)),
      })
    }
    out.sort((a, b) => a.serviceName.localeCompare(b.serviceName))
    return out
  }, [serviceData, operations])

  const draftSet = useMemo((): Set<string> => new Set(draftUids), [draftUids])
  // 已勾作業或作業母清單任一讀不到,就不准整批覆蓋
  const operationsLoadFailed = isOperationsError || operationData === undefined
  const loadFailed = isGrantedError || grantedData === undefined || operationsLoadFailed
  const dirty = !loadFailed && !sameKeys(draftUids, serverUids)
  useReportDirty(dirty)

  // 授權矩陣只能設「已存檔勾選」的作業(未勾作業後端回 409),故以伺服器狀態為準
  const grantedOperations = useMemo(
    (): ClientSettingOperation[] =>
      operations
        .filter((operation) => serverUids.includes(operation.uid))
        .sort((a, b) => a.name.localeCompare(b.name)),
    [operations, serverUids],
  )
  const matrixOperation = useMemo(
    (): ClientSettingOperation | null =>
      grantedOperations.find((operation) => operation.uid === matrixOperationUid) ?? null,
    [grantedOperations, matrixOperationUid],
  )
  // 取消勾選某作業後,矩陣選取可能失效 → 清掉
  if (matrixOperationUid !== '' && grantedData !== undefined && matrixOperation === null) {
    setMatrixOperationUid('')
  }

  const handleToggleOperation = useCallback((operationUid: string): void => {
    setNotice(null)
    setDraftUids((prev) =>
      prev.includes(operationUid)
        ? prev.filter((item) => item !== operationUid)
        : [...prev, operationUid].sort(),
    )
  }, [])

  const handleResetOperations = useCallback((): void => {
    setDraftUids(serverUids)
    setSaveError(null)
    setNotice(null)
  }, [serverUids])

  const handleSaveOperations = useCallback(async (): Promise<void> => {
    setSaveError(null)
    setNotice(null)
    const operationUids = [...draftUids]
    const result = isProfile
      ? await replaceProfileOperations({ uid: targetUid, operation_uids: operationUids })
      : await replaceExceptionOperations({ uid: targetUid, operation_uids: operationUids })
    if ('error' in result) {
      setSaveError(extractApiErrorDetail(result.error, '儲存勾選作業失敗,請稍後再試'))
      return
    }
    setNotice(`已儲存勾選作業(${operationUids.length} 項)`)
  }, [
    draftUids,
    isProfile,
    replaceExceptionOperations,
    replaceProfileOperations,
    targetUid,
  ])

  const handleMatrixOperationChange = useCallback(
    (event: React.ChangeEvent<HTMLSelectElement>): void =>
      setMatrixOperationUid(event.target.value),
    [],
  )

  const handleRetry = useCallback((): void => {
    void refetchGranted()
    void refetchOperations()
  }, [refetchGranted, refetchOperations])

  return (
    <div className="flex flex-col gap-6">
      <div className="df-card flex flex-col gap-4 p-4 md:p-5">
        <h2 className="text-base font-semibold text-foreground md:text-lg">
          勾選作業({targetName})
        </h2>
        <p className="text-sm text-muted-foreground md:text-base">
          先決定此{kindLabel}開哪些作業的門;取消勾選會一併清掉該作業下已設的授權
        </p>
        {isServicesError ? <InlineError message="載入服務清單失敗,請稍後再試" /> : null}
        {isGrantedLoading || isOperationsLoading ? (
          <p className="text-sm text-muted-foreground md:text-base">載入中…</p>
        ) : loadFailed ? (
          <LoadFailedNotice
            message={
              operationsLoadFailed
                ? '載入作業清單失敗;讀不到作業母清單前不開放編輯'
                : '載入勾選作業失敗;讀不到目前勾選前不開放編輯(整批儲存會覆蓋既有勾選)'
            }
            onRetry={handleRetry}
          />
        ) : (
          <>
            <OperationPicker
              groups={groups}
              selectedUids={draftSet}
              onToggle={handleToggleOperation}
            />
            <EditorActions
              dirty={dirty}
              saving={isSavingOperations}
              saveLabel="儲存勾選作業"
              onSave={handleSaveOperations}
              onReset={handleResetOperations}
            />
          </>
        )}
        <InlineError message={saveError} />
        <InlineNotice message={notice} />
      </div>

      <div className="df-card flex flex-col gap-4 p-4 md:p-5">
        <h2 className="text-base font-semibold text-foreground md:text-lg">授權矩陣</h2>
        <p className="text-sm text-muted-foreground md:text-base">
          逐表逐欄勾讀取 / 編輯;可選範圍上限為該作業的表 × 欄位範圍(給不出範圍外的欄位),
          未勾任何欄位 = 該作業不給資料(default-closed)
        </p>
        {loadFailed ? (
          <InlineError message="讀取失敗,無法顯示已勾選作業;請先於上方重新載入" />
        ) : grantedOperations.length === 0 ? (
          <EmptyState message="尚未儲存任何勾選作業;請先於上方勾選並儲存" />
        ) : (
          <>
            <label className="flex flex-col gap-1.5 text-sm font-medium text-foreground md:text-base">
              作業
              <select
                value={matrixOperationUid}
                onChange={handleMatrixOperationChange}
                className="df-input"
              >
                <option value="">請選擇作業</option>
                {grantedOperations.map((operation) => (
                  <option key={operation.uid} value={operation.uid}>
                    {operation.name}
                  </option>
                ))}
              </select>
            </label>
            {matrixOperation !== null ? (
              <PermissionMatrixEditor
                key={`${kind}-${targetUid}-${matrixOperation.uid}`}
                kind={kind}
                targetUid={targetUid}
                operationUid={matrixOperation.uid}
                operationName={matrixOperation.name}
              />
            ) : (
              <EmptyState message="請先選擇要設定授權的作業" />
            )}
          </>
        )}
      </div>
    </div>
  )
}

/* ---------------------------------------------------------------------- */
/* 角色權限設定檔                                                            */
/* ---------------------------------------------------------------------- */

function ProfilesSection(): React.ReactNode {
  const [createOpen, setCreateOpen] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<PermissionProfile | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [selected, setSelected] = useState<PermissionProfile | null>(null)

  const { data, isLoading, isError } = useListPermissionProfilesQuery()
  const [createPermissionProfile, { isLoading: isCreating }] = useCreatePermissionProfileMutation()
  const [deletePermissionProfile, { isLoading: isDeleting }] = useDeletePermissionProfileMutation()

  const items = useMemo((): PermissionProfile[] => data?.items ?? [], [data])

  // 設定檔被刪除 / 清單更新後仍指向不存在的項目 → 收起授權編輯區
  if (
    selected !== null &&
    data !== undefined &&
    !items.some((item) => item.uid === selected.uid)
  ) {
    setSelected(null)
  }

  const { guard } = useContext(DirtyGuardContext)
  const handleSelect = useCallback(
    (item: PermissionProfile): void => guard(() => setSelected(item)),
    [guard],
  )

  const openCreate = useCallback((): void => {
    setCreateError(null)
    setCreateOpen(true)
  }, [])
  const cancelCreate = useCallback((): void => setCreateOpen(false), [])
  const handleCreate = useCallback(
    async (payload: CreatePermissionProfilePayload): Promise<void> => {
      setCreateError(null)
      const result = await createPermissionProfile(payload)
      if ('error' in result) {
        setCreateError(extractApiErrorDetail(result.error, '建立角色權限設定檔失敗,請稍後再試'))
        return
      }
      setCreateOpen(false)
    },
    [createPermissionProfile],
  )

  const requestDelete = useCallback((item: PermissionProfile): void => {
    setDeleteError(null)
    setDeleteTarget(item)
  }, [])
  const cancelDelete = useCallback((): void => setDeleteTarget(null), [])
  const confirmDelete = useCallback(async (): Promise<void> => {
    if (deleteTarget === null) return
    setDeleteError(null)
    const result = await deletePermissionProfile(deleteTarget.uid)
    setDeleteTarget(null)
    if ('error' in result) {
      setDeleteError(extractApiErrorDetail(result.error, '刪除角色權限設定檔失敗,請稍後再試'))
    }
  }, [deleteTarget, deletePermissionProfile])

  return (
    <div className="flex flex-col gap-6">
      <div className="df-card flex flex-col gap-4 p-4 md:p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-base font-semibold text-foreground md:text-lg">角色權限設定檔</h2>
          <CreateButton label="新增設定檔" onClick={openCreate} />
        </div>
        <p className="text-sm text-muted-foreground md:text-base">
          選一列(或按「設定授權」)即可於下方勾選作業與設定逐表逐欄授權矩陣
        </p>
        {isLoading ? <p className="text-sm text-muted-foreground md:text-base">載入中…</p> : null}
        {isError ? <InlineError message="載入角色權限設定檔清單失敗,請稍後再試" /> : null}
        {data !== undefined ? (
          <div className="overflow-x-auto">
            <SimpleEntityTable
              items={items}
              emptyMessage="尚無角色權限設定檔"
              selectedUid={selected?.uid ?? null}
              deletingUid={isDeleting ? (deleteTarget?.uid ?? null) : null}
              onSelect={handleSelect}
              onDelete={requestDelete}
            />
          </div>
        ) : null}
        <ConfirmDialog
          open={deleteTarget !== null}
          title="刪除角色權限設定檔"
          confirmLabel="確認刪除"
          tone="danger"
          confirmDisabled={isDeleting}
          onConfirm={confirmDelete}
          onCancel={cancelDelete}
        >
          {deleteTarget !== null ? <p>確定要刪除角色權限設定檔「{deleteTarget.name}」?</p> : null}
          <p>仍被角色綁定時後端將拒絕刪除(409)。</p>
          <InlineError message={deleteError} />
        </ConfirmDialog>
      </div>

      {createOpen ? (
        <NameDescriptionCreateDialog
          title="新增角色權限設定檔"
          nameLabel="設定檔名稱"
          submitLabel="建立設定檔"
          submitting={isCreating}
          submitError={createError}
          onSubmit={handleCreate}
          onCancel={cancelCreate}
        />
      ) : null}

      {selected !== null ? (
        <PermissionSetEditor
          key={`profile-${selected.uid}`}
          kind="profile"
          targetUid={selected.uid}
          targetName={selected.name}
        />
      ) : null}
    </div>
  )
}

/* ---------------------------------------------------------------------- */
/* 角色                                                                     */
/* ---------------------------------------------------------------------- */

interface RoleCreateDialogProps {
  submitting: boolean
  submitError: string | null
  profiles: PermissionProfile[]
  onSubmit: (payload: CreateClientSettingRolePayload) => void
  onCancel: () => void
}

function RoleCreateDialog({
  submitting,
  submitError,
  profiles,
  onSubmit,
  onCancel,
}: RoleCreateDialogProps): React.ReactNode {
  const [profileUid, setProfileUid] = useState('')
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')

  const handleSubmit = useCallback(
    (event: React.FormEvent<HTMLFormElement>): void => {
      event.preventDefault()
      const trimmedName = name.trim()
      if (trimmedName === '' || profileUid === '') return
      onSubmit({
        permission_profile_uid: profileUid,
        name: trimmedName,
        description: description.trim() === '' ? null : description.trim(),
      })
    },
    [profileUid, name, description, onSubmit],
  )

  return (
    <FormDialog
      title="新增角色"
      submitLabel={submitting ? '建立中…' : '建立角色'}
      submitDisabled={submitting || name.trim() === '' || profileUid === ''}
      errorMessage={submitError}
      onSubmit={handleSubmit}
      onCancel={onCancel}
    >
      <label className="flex flex-col gap-1.5 text-sm font-medium text-foreground md:text-base">
        綁定角色權限設定檔(必選)
        <select
          value={profileUid}
          onChange={(event) => setProfileUid(event.target.value)}
          required
          className="df-input"
        >
          <option value="">請選擇</option>
          {profiles.map((profile) => (
            <option key={profile.uid} value={profile.uid}>
              {profile.name}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1.5 text-sm font-medium text-foreground md:text-base">
        角色名稱
        <input
          type="text"
          value={name}
          onChange={(event) => setName(event.target.value)}
          required
          className="df-input"
        />
      </label>
      <label className="flex flex-col gap-1.5 text-sm font-medium text-foreground md:text-base">
        說明(選填)
        <input
          type="text"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          className="df-input"
        />
      </label>
    </FormDialog>
  )
}

interface RoleTableProps {
  items: ClientSettingRole[]
  profiles: PermissionProfile[]
  /** 角色權限設定檔清單讀取失敗:下拉選項不完整,禁止改綁以免誤送 */
  profilesUnavailable: boolean
  deletingUid: string | null
  rebindingUid: string | null
  onRebind: (role: ClientSettingRole, profileUid: string) => void
  onDelete: (role: ClientSettingRole) => void
}

const RoleTable = memo(function RoleTable({
  items,
  profiles,
  profilesUnavailable,
  deletingUid,
  rebindingUid,
  onRebind,
  onDelete,
}: RoleTableProps): React.ReactNode {
  if (items.length === 0) return <EmptyState message="尚無角色" />
  return (
    <table className="df-table min-w-[760px]">
      <thead>
        <tr className="border-b border-border bg-muted/50">
          <th className="df-th">名稱</th>
          <th className="df-th">綁定角色權限設定檔</th>
          <th className="df-th">說明</th>
          <th className="df-th">操作</th>
        </tr>
      </thead>
      <tbody>
        {items.map((role) => (
          <tr
            key={role.uid}
            className="border-b border-border transition-colors last:border-b-0 hover:bg-muted/50"
          >
            <td className="df-td font-medium text-foreground">{role.name}</td>
            <td className="df-td">
              {profilesUnavailable ? (
                <span className="text-muted-foreground">—(角色權限設定檔清單讀取失敗)</span>
              ) : (
                <select
                  value={role.permission_profile_uid}
                  onChange={(event) => onRebind(role, event.target.value)}
                  disabled={rebindingUid === role.uid}
                  aria-label={`${role.name} 綁定角色權限設定檔`}
                  className="df-input min-w-[12rem]"
                >
                  {profiles.map((profile) => (
                    <option key={profile.uid} value={profile.uid}>
                      {profile.name}
                    </option>
                  ))}
                </select>
              )}
            </td>
            <td className="df-td text-muted-foreground">{role.description ?? '—'}</td>
            <td className="df-td">
              <button
                type="button"
                onClick={() => onDelete(role)}
                disabled={deletingUid === role.uid}
                className="df-btn-danger-soft min-h-0 whitespace-nowrap rounded-full px-3 py-1 text-sm"
              >
                刪除
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
})

function RolesSection(): React.ReactNode {
  const [createOpen, setCreateOpen] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<ClientSettingRole | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [rebindError, setRebindError] = useState<string | null>(null)
  const [rebindNotice, setRebindNotice] = useState<string | null>(null)
  const [rebindingUid, setRebindingUid] = useState<string | null>(null)

  const { data: profileData, isError: isProfilesError } = useListPermissionProfilesQuery()
  const { data, isLoading, isError } = useListClientSettingRolesQuery()
  const [createClientSettingRole, { isLoading: isCreating }] = useCreateClientSettingRoleMutation()
  const [updateClientSettingRole] = useUpdateClientSettingRoleMutation()
  const [deleteClientSettingRole, { isLoading: isDeleting }] = useDeleteClientSettingRoleMutation()

  const profiles = useMemo((): PermissionProfile[] => profileData?.items ?? [], [profileData])
  const items = useMemo((): ClientSettingRole[] => data?.items ?? [], [data])

  const openCreate = useCallback((): void => {
    setCreateError(null)
    setCreateOpen(true)
  }, [])
  const cancelCreate = useCallback((): void => setCreateOpen(false), [])
  const handleCreate = useCallback(
    async (payload: CreateClientSettingRolePayload): Promise<void> => {
      setCreateError(null)
      const result = await createClientSettingRole(payload)
      if ('error' in result) {
        setCreateError(extractApiErrorDetail(result.error, '建立角色失敗,請稍後再試'))
        return
      }
      setCreateOpen(false)
    },
    [createClientSettingRole],
  )

  const handleRebind = useCallback(
    async (role: ClientSettingRole, profileUid: string): Promise<void> => {
      setRebindError(null)
      setRebindNotice(null)
      // 後端不允許清空綁定;下拉無空選項,仍防呆一次
      if (profileUid === '' || profileUid === role.permission_profile_uid) return
      setRebindingUid(role.uid)
      const result = await updateClientSettingRole({
        uid: role.uid,
        permission_profile_uid: profileUid,
      })
      setRebindingUid(null)
      if ('error' in result) {
        setRebindError(extractApiErrorDetail(result.error, '改綁角色權限設定檔失敗,請稍後再試'))
        return
      }
      setRebindNotice(`已將角色「${role.name}」改綁角色權限設定檔`)
    },
    [updateClientSettingRole],
  )

  const requestDelete = useCallback((item: ClientSettingRole): void => {
    setDeleteError(null)
    setDeleteTarget(item)
  }, [])
  const cancelDelete = useCallback((): void => setDeleteTarget(null), [])
  const confirmDelete = useCallback(async (): Promise<void> => {
    if (deleteTarget === null) return
    setDeleteError(null)
    const result = await deleteClientSettingRole(deleteTarget.uid)
    setDeleteTarget(null)
    if ('error' in result) {
      setDeleteError(extractApiErrorDetail(result.error, '刪除角色失敗,請稍後再試'))
    }
  }, [deleteTarget, deleteClientSettingRole])

  return (
    <div className="df-card flex flex-col gap-4 p-4 md:p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-base font-semibold text-foreground md:text-lg">角色</h2>
        <CreateButton
          label="新增角色"
          disabled={profiles.length === 0 || isProfilesError}
          onClick={openCreate}
        />
      </div>
      <p className="text-sm text-muted-foreground md:text-base">
        每個角色必綁 1 個角色權限設定檔(可改綁、不可清空);指派給使用者見「API Client 設定」頁
      </p>
      {/* 讀不到設定檔 ≠ 沒有設定檔:失敗時給故障訊息,不可叫使用者去重建已存在的資料 */}
      {isProfilesError ? (
        <InlineError message="載入角色權限設定檔清單失敗,請稍後再試;改綁下拉與新增角色暫不可用" />
      ) : profileData !== undefined && profiles.length === 0 ? (
        <InlineError message="尚無角色權限設定檔,請先於「角色權限設定檔」分頁建立後再建角色" />
      ) : null}
      {isLoading ? <p className="text-sm text-muted-foreground md:text-base">載入中…</p> : null}
      {isError ? <InlineError message="載入角色清單失敗,請稍後再試" /> : null}
      {data !== undefined ? (
        <div className="overflow-x-auto">
          <RoleTable
            items={items}
            profiles={profiles}
            profilesUnavailable={isProfilesError}
            deletingUid={isDeleting ? (deleteTarget?.uid ?? null) : null}
            rebindingUid={rebindingUid}
            onRebind={handleRebind}
            onDelete={requestDelete}
          />
        </div>
      ) : null}
      <InlineError message={rebindError} />
      <InlineNotice message={rebindNotice} />
      <ConfirmDialog
        open={deleteTarget !== null}
        title="刪除角色"
        confirmLabel="確認刪除"
        tone="danger"
        confirmDisabled={isDeleting}
        onConfirm={confirmDelete}
        onCancel={cancelDelete}
      >
        {deleteTarget !== null ? <p>確定要刪除角色「{deleteTarget.name}」?</p> : null}
        <p>仍被使用者指派時後端將拒絕刪除(409)。</p>
        <InlineError message={deleteError} />
      </ConfirmDialog>
      {createOpen ? (
        <RoleCreateDialog
          submitting={isCreating}
          submitError={createError}
          profiles={profiles}
          onSubmit={handleCreate}
          onCancel={cancelCreate}
        />
      ) : null}
    </div>
  )
}

/* ---------------------------------------------------------------------- */
/* 臨時權限                                                                  */
/* ---------------------------------------------------------------------- */

function ExceptionSetsSection(): React.ReactNode {
  const [createOpen, setCreateOpen] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<ExceptionSet | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [selected, setSelected] = useState<ExceptionSet | null>(null)

  const { data, isLoading, isError } = useListExceptionSetsQuery()
  const [createExceptionSet, { isLoading: isCreating }] = useCreateExceptionSetMutation()
  const [deleteExceptionSet, { isLoading: isDeleting }] = useDeleteExceptionSetMutation()

  const items = useMemo((): ExceptionSet[] => data?.items ?? [], [data])

  if (
    selected !== null &&
    data !== undefined &&
    !items.some((item) => item.uid === selected.uid)
  ) {
    setSelected(null)
  }

  const { guard } = useContext(DirtyGuardContext)
  const handleSelect = useCallback(
    (item: ExceptionSet): void => guard(() => setSelected(item)),
    [guard],
  )

  const openCreate = useCallback((): void => {
    setCreateError(null)
    setCreateOpen(true)
  }, [])
  const cancelCreate = useCallback((): void => setCreateOpen(false), [])
  const handleCreate = useCallback(
    async (payload: CreateExceptionSetPayload): Promise<void> => {
      setCreateError(null)
      const result = await createExceptionSet(payload)
      if ('error' in result) {
        setCreateError(extractApiErrorDetail(result.error, '建立臨時權限組失敗,請稍後再試'))
        return
      }
      setCreateOpen(false)
    },
    [createExceptionSet],
  )

  const requestDelete = useCallback((item: ExceptionSet): void => {
    setDeleteError(null)
    setDeleteTarget(item)
  }, [])
  const cancelDelete = useCallback((): void => setDeleteTarget(null), [])
  const confirmDelete = useCallback(async (): Promise<void> => {
    if (deleteTarget === null) return
    setDeleteError(null)
    const result = await deleteExceptionSet(deleteTarget.uid)
    setDeleteTarget(null)
    if ('error' in result) {
      setDeleteError(extractApiErrorDetail(result.error, '刪除臨時權限組失敗,請稍後再試'))
    }
  }, [deleteTarget, deleteExceptionSet])

  return (
    <div className="flex flex-col gap-6">
      <div className="df-card flex flex-col gap-4 p-4 md:p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-base font-semibold text-foreground md:text-lg">臨時權限組</h2>
          <CreateButton label="新增臨時權限組" onClick={openCreate} />
        </div>
        <p className="text-sm text-muted-foreground md:text-base">
          結構同角色權限設定檔(勾作業 + 授權矩陣),可重用、可綁多個使用者;綁定與效期(到期自動失效)
          於「API Client 設定」頁設定
        </p>
        {isLoading ? <p className="text-sm text-muted-foreground md:text-base">載入中…</p> : null}
        {isError ? <InlineError message="載入臨時權限組清單失敗,請稍後再試" /> : null}
        {data !== undefined ? (
          <div className="overflow-x-auto">
            <SimpleEntityTable
              items={items}
              emptyMessage="尚無臨時權限組"
              selectedUid={selected?.uid ?? null}
              deletingUid={isDeleting ? (deleteTarget?.uid ?? null) : null}
              onSelect={handleSelect}
              onDelete={requestDelete}
            />
          </div>
        ) : null}
        <ConfirmDialog
          open={deleteTarget !== null}
          title="刪除臨時權限組"
          confirmLabel="確認刪除"
          tone="danger"
          confirmDisabled={isDeleting}
          onConfirm={confirmDelete}
          onCancel={cancelDelete}
        >
          {deleteTarget !== null ? <p>確定要刪除臨時權限組「{deleteTarget.name}」?</p> : null}
          <p>仍被未過期綁定引用時後端將拒絕刪除(409)。</p>
          <InlineError message={deleteError} />
        </ConfirmDialog>
      </div>

      {createOpen ? (
        <NameDescriptionCreateDialog
          title="新增臨時權限組"
          nameLabel="臨時權限組名稱"
          submitLabel="建立臨時權限組"
          submitting={isCreating}
          submitError={createError}
          onSubmit={handleCreate}
          onCancel={cancelCreate}
        />
      ) : null}

      {selected !== null ? (
        <PermissionSetEditor
          key={`exception-${selected.uid}`}
          kind="exception"
          targetUid={selected.uid}
          targetName={selected.name}
        />
      ) : null}
    </div>
  )
}

/* ---------------------------------------------------------------------- */
/* 主頁面                                                                   */
/* ---------------------------------------------------------------------- */

/** 分頁切換需經守衛,故與 Provider 分層(useContext 必須在 Provider 之下) */
function ClientSettingsTabs(): React.ReactNode {
  const [tab, setTab] = useState<TabKey>('services')
  const { guard } = useContext(DirtyGuardContext)

  const handleTabChange = useCallback(
    (next: TabKey): void => guard(() => setTab(next)),
    [guard],
  )

  return (
    <>
      <Segmented options={TAB_OPTIONS} value={tab} onChange={handleTabChange} />

      {tab === 'services' ? <ServicesOperationsSection /> : null}
      {tab === 'profiles' ? <ProfilesSection /> : null}
      {tab === 'roles' ? <RolesSection /> : null}
      {tab === 'exceptions' ? <ExceptionSetsSection /> : null}
    </>
  )
}

export default function ClientSettingsPage(): React.ReactNode {
  return (
    <section className="mx-auto flex max-w-7xl flex-col gap-6">
      <div>
        <h1 className="text-xl font-bold text-foreground md:text-2xl">組織權限管理</h1>
        <p className="mt-1 text-sm text-muted-foreground md:text-base">
          服務 / 作業範圍 → 角色權限設定檔矩陣 → 角色;臨時權限組可限期綁定使用者
        </p>
      </div>

      <DirtyGuardProvider>
        <ClientSettingsTabs />
      </DirtyGuardProvider>
    </section>
  )
}
