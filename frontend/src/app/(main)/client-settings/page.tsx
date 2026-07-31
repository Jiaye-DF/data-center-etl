'use client'

import { memo, useCallback, useMemo, useState } from 'react'
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
  useListExceptionSetsQuery,
  useListOperationsQuery,
  useListPermissionProfilesQuery,
  useListServicesQuery,
  type ClientSettingOperation,
  type ClientSettingRole,
  type ClientSettingService,
  type CreateClientSettingOperationPayload,
  type CreateClientSettingRolePayload,
  type CreateClientSettingServicePayload,
  type CreateExceptionSetPayload,
  type CreatePermissionProfilePayload,
  type ExceptionSet,
  type PermissionProfile,
} from '@/lib/api/clientSettingApi'
import { ConfirmDialog } from '@/components/common/ConfirmDialog'
import { Segmented, type SegmentedOption } from '@/components/common/Segmented'
import { extractApiErrorDetail } from '@/utils/apiError'
import { formatDateTime } from '@/utils/datetime'

/** 表 / 欄位授權設定前提;各 tab 空狀態與作業建立區共用同一提示語意 */
const CONFIRMED_MAPPING_HINT =
  '設定作業範圍 / 授權矩陣前,請先於「語意映射管理」將欲開放的表 / 欄位標記為「已確認」,否則後端會拒絕(422)'

type TabKey = 'services' | 'profiles' | 'roles' | 'exceptions'

const TAB_OPTIONS: ReadonlyArray<SegmentedOption<TabKey>> = [
  { value: 'services', label: '系統別 / 作業' },
  { value: 'profiles', label: '設定檔' },
  { value: 'roles', label: 'Role' },
  { value: 'exceptions', label: '特例' },
]

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

interface EmptyStateProps {
  message: string
}

function EmptyState({ message }: EmptyStateProps): React.ReactNode {
  return (
    <p className="px-3 py-8 text-center text-sm text-muted-foreground md:text-base">{message}</p>
  )
}

/** 名稱 + 說明(選填)建立表單;設定檔 / 特例組共用同一形狀 */
interface NameDescriptionCreateFormProps {
  submitting: boolean
  submitLabel: string
  nameLabel: string
  onSubmit: (payload: { name: string; description: string | null }) => void
}

function NameDescriptionCreateForm({
  submitting,
  submitLabel,
  nameLabel,
  onSubmit,
}: NameDescriptionCreateFormProps): React.ReactNode {
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
    <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-3">
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
      <button
        type="submit"
        disabled={submitting || name.trim() === ''}
        className="df-btn-primary"
      >
        {submitLabel}
      </button>
    </form>
  )
}

/** 名稱 / 說明 / 建立時間 / 操作 的清單表格;設定檔 / 特例組共用同一欄位形狀 */
interface SimpleNamedEntity {
  uid: string
  name: string
  description: string | null
  created_at: string
}

interface SimpleEntityTableProps<T extends SimpleNamedEntity> {
  items: T[]
  emptyMessage: string
  deletingUid: string | null
  onDelete: (item: T) => void
}

function SimpleEntityTable<T extends SimpleNamedEntity>({
  items,
  emptyMessage,
  deletingUid,
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
        {items.map((item) => (
          <tr
            key={item.uid}
            className="border-b border-border transition-colors last:border-b-0 hover:bg-muted/50"
          >
            <td className="df-td font-medium text-foreground">{item.name}</td>
            <td className="df-td text-muted-foreground">{item.description ?? '—'}</td>
            <td className="df-td text-muted-foreground">{formatDateTime(item.created_at)}</td>
            <td className="df-td">
              <button
                type="button"
                onClick={() => onDelete(item)}
                disabled={deletingUid === item.uid}
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
}

/* ---------------------------------------------------------------------- */
/* 系統別 / 作業                                                            */
/* ---------------------------------------------------------------------- */

interface ServiceCreateFormProps {
  submitting: boolean
  onSubmit: (payload: CreateClientSettingServicePayload) => void
}

function ServiceCreateForm({ submitting, onSubmit }: ServiceCreateFormProps): React.ReactNode {
  const [code, setCode] = useState('')
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')

  const handleCodeChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>): void => setCode(event.target.value),
    [],
  )
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
      onSubmit({
        code: trimmedCode,
        name: trimmedName,
        description: description.trim() === '' ? null : description.trim(),
      })
    },
    [code, name, description, onSubmit],
  )

  return (
    <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-3">
      <label className="flex flex-col gap-1.5 text-sm font-medium text-foreground md:text-base">
        代碼(erp / crm…;建立後不可改)
        <input
          type="text"
          value={code}
          onChange={handleCodeChange}
          required
          className="df-input font-mono"
        />
      </label>
      <label className="flex flex-col gap-1.5 text-sm font-medium text-foreground md:text-base">
        名稱
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
      <button
        type="submit"
        disabled={submitting || code.trim() === '' || name.trim() === ''}
        className="df-btn-primary"
      >
        新增系統別
      </button>
    </form>
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
  if (items.length === 0) return <EmptyState message="尚無系統別" />
  return (
    <table className="df-table min-w-[720px]">
      <thead>
        <tr className="border-b border-border bg-muted/50">
          <th className="df-th">代碼</th>
          <th className="df-th">名稱</th>
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
  deletingUid: string | null
  onDelete: (operation: ClientSettingOperation) => void
}

const OperationTable = memo(function OperationTable({
  items,
  deletingUid,
  onDelete,
}: OperationTableProps): React.ReactNode {
  if (items.length === 0) {
    return <EmptyState message="尚無作業(範圍設定 / 授權矩陣見 task-009)" />
  }
  return (
    <table className="df-table min-w-[560px]">
      <thead>
        <tr className="border-b border-border bg-muted/50">
          <th className="df-th">名稱</th>
          <th className="df-th">說明</th>
          <th className="df-th">操作</th>
        </tr>
      </thead>
      <tbody>
        {items.map((operation) => (
          <tr
            key={operation.uid}
            className="border-b border-border transition-colors last:border-b-0 hover:bg-muted/50"
          >
            <td className="df-td font-medium text-foreground">{operation.name}</td>
            <td className="df-td text-muted-foreground">{operation.description ?? '—'}</td>
            <td className="df-td">
              <button
                type="button"
                onClick={() => onDelete(operation)}
                disabled={deletingUid === operation.uid}
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

function ServicesOperationsSection(): React.ReactNode {
  const [selectedService, setSelectedService] = useState<ClientSettingService | null>(null)
  const [serviceCreateError, setServiceCreateError] = useState<string | null>(null)
  const [serviceDeleteTarget, setServiceDeleteTarget] = useState<ClientSettingService | null>(
    null,
  )
  const [serviceDeleteError, setServiceDeleteError] = useState<string | null>(null)
  const [operationCreateError, setOperationCreateError] = useState<string | null>(null)
  const [operationDeleteTarget, setOperationDeleteTarget] =
    useState<ClientSettingOperation | null>(null)
  const [operationDeleteError, setOperationDeleteError] = useState<string | null>(null)
  const [operationName, setOperationName] = useState('')
  const [operationDescription, setOperationDescription] = useState('')

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

  const handleCreateService = useCallback(
    async (payload: CreateClientSettingServicePayload): Promise<void> => {
      setServiceCreateError(null)
      const result = await createService(payload)
      if ('error' in result) {
        setServiceCreateError(extractApiErrorDetail(result.error, '建立系統別失敗,請稍後再試'))
      }
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
      setServiceDeleteError(extractApiErrorDetail(result.error, '刪除系統別失敗,請稍後再試'))
      return
    }
    if (selectedService?.uid === target.uid) setSelectedService(null)
  }, [serviceDeleteTarget, deleteService, selectedService])

  const handleCreateOperation = useCallback(
    async (event: React.FormEvent<HTMLFormElement>): Promise<void> => {
      event.preventDefault()
      if (selectedService === null) return
      const trimmedName = operationName.trim()
      if (trimmedName === '') return
      setOperationCreateError(null)
      const payload: CreateClientSettingOperationPayload = {
        service_uid: selectedService.uid,
        name: trimmedName,
        description: operationDescription.trim() === '' ? null : operationDescription.trim(),
      }
      const result = await createOperation(payload)
      if ('error' in result) {
        setOperationCreateError(extractApiErrorDetail(result.error, '建立作業失敗,請稍後再試'))
        return
      }
      setOperationName('')
      setOperationDescription('')
    },
    [selectedService, operationName, operationDescription, createOperation],
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
        <h2 className="text-base font-semibold text-foreground md:text-lg">系統別</h2>
        <ServiceCreateForm submitting={isCreatingService} onSubmit={handleCreateService} />
        <InlineError message={serviceCreateError} />
        {isServicesLoading ? (
          <p className="text-sm text-muted-foreground md:text-base">載入中…</p>
        ) : null}
        {isServicesError ? <InlineError message="載入系統別清單失敗,請稍後再試" /> : null}
        {serviceData !== undefined ? (
          <div className="overflow-x-auto">
            <ServiceTable
              items={services}
              selectedUid={selectedService?.uid ?? null}
              deletingUid={isDeletingService ? (serviceDeleteTarget?.uid ?? null) : null}
              onSelect={setSelectedService}
              onDelete={requestDeleteService}
            />
          </div>
        ) : null}
      </div>

      <div className="df-card flex flex-col gap-4 p-4 md:p-5">
        <h2 className="text-base font-semibold text-foreground md:text-lg">
          作業{selectedService !== null ? `(${selectedService.name})` : ''}
        </h2>
        <p className="text-sm text-muted-foreground md:text-base">{CONFIRMED_MAPPING_HINT}</p>
        {selectedService === null ? (
          <EmptyState message="請先於上方選取一個系統別" />
        ) : (
          <>
            <form onSubmit={handleCreateOperation} className="flex flex-wrap items-end gap-3">
              <label className="flex flex-col gap-1.5 text-sm font-medium text-foreground md:text-base">
                作業名稱
                <input
                  type="text"
                  value={operationName}
                  onChange={(event) => setOperationName(event.target.value)}
                  required
                  className="df-input"
                />
              </label>
              <label className="flex flex-col gap-1.5 text-sm font-medium text-foreground md:text-base">
                說明(選填)
                <input
                  type="text"
                  value={operationDescription}
                  onChange={(event) => setOperationDescription(event.target.value)}
                  className="df-input"
                />
              </label>
              <button
                type="submit"
                disabled={isCreatingOperation || operationName.trim() === ''}
                className="df-btn-primary"
              >
                新增作業
              </button>
            </form>
            <InlineError message={operationCreateError} />
            {isOperationsLoading ? (
              <p className="text-sm text-muted-foreground md:text-base">載入中…</p>
            ) : null}
            {isOperationsError ? <InlineError message="載入作業清單失敗,請稍後再試" /> : null}
            {operationData !== undefined ? (
              <div className="overflow-x-auto">
                <OperationTable
                  items={operations}
                  deletingUid={
                    isDeletingOperation ? (operationDeleteTarget?.uid ?? null) : null
                  }
                  onDelete={requestDeleteOperation}
                />
              </div>
            ) : null}
          </>
        )}
      </div>

      <ConfirmDialog
        open={serviceDeleteTarget !== null}
        title="刪除系統別"
        confirmLabel="確認刪除"
        tone="danger"
        confirmDisabled={isDeletingService}
        onConfirm={confirmDeleteService}
        onCancel={cancelDeleteService}
      >
        {serviceDeleteTarget !== null ? <p>確定要刪除系統別「{serviceDeleteTarget.name}」?</p> : null}
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
        <p>仍被設定檔 / 特例組引用時後端將拒絕刪除(409)。</p>
        <InlineError message={operationDeleteError} />
      </ConfirmDialog>
    </div>
  )
}

/* ---------------------------------------------------------------------- */
/* 設定檔                                                                   */
/* ---------------------------------------------------------------------- */

function ProfilesSection(): React.ReactNode {
  const [createError, setCreateError] = useState<string | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<PermissionProfile | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  const { data, isLoading, isError } = useListPermissionProfilesQuery()
  const [createPermissionProfile, { isLoading: isCreating }] = useCreatePermissionProfileMutation()
  const [deletePermissionProfile, { isLoading: isDeleting }] = useDeletePermissionProfileMutation()

  const items = useMemo((): PermissionProfile[] => data?.items ?? [], [data])

  const handleCreate = useCallback(
    async (payload: CreatePermissionProfilePayload): Promise<void> => {
      setCreateError(null)
      const result = await createPermissionProfile(payload)
      if ('error' in result) {
        setCreateError(extractApiErrorDetail(result.error, '建立設定檔失敗,請稍後再試'))
      }
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
      setDeleteError(extractApiErrorDetail(result.error, '刪除設定檔失敗,請稍後再試'))
    }
  }, [deleteTarget, deletePermissionProfile])

  return (
    <div className="df-card flex flex-col gap-4 p-4 md:p-5">
      <h2 className="text-base font-semibold text-foreground md:text-lg">權限設定檔</h2>
      <p className="text-sm text-muted-foreground md:text-base">
        勾選可讀作業 + 逐表逐欄授權矩陣(read / edit)見 task-009
      </p>
      <NameDescriptionCreateForm
        submitting={isCreating}
        submitLabel="新增設定檔"
        nameLabel="設定檔名稱"
        onSubmit={handleCreate}
      />
      <InlineError message={createError} />
      {isLoading ? <p className="text-sm text-muted-foreground md:text-base">載入中…</p> : null}
      {isError ? <InlineError message="載入設定檔清單失敗,請稍後再試" /> : null}
      {data !== undefined ? (
        <div className="overflow-x-auto">
          <SimpleEntityTable
            items={items}
            emptyMessage="尚無設定檔"
            deletingUid={isDeleting ? (deleteTarget?.uid ?? null) : null}
            onDelete={requestDelete}
          />
        </div>
      ) : null}
      <ConfirmDialog
        open={deleteTarget !== null}
        title="刪除設定檔"
        confirmLabel="確認刪除"
        tone="danger"
        confirmDisabled={isDeleting}
        onConfirm={confirmDelete}
        onCancel={cancelDelete}
      >
        {deleteTarget !== null ? <p>確定要刪除設定檔「{deleteTarget.name}」?</p> : null}
        <p>仍被 Role 綁定時後端將拒絕刪除(409)。</p>
        <InlineError message={deleteError} />
      </ConfirmDialog>
    </div>
  )
}

/* ---------------------------------------------------------------------- */
/* Role                                                                     */
/* ---------------------------------------------------------------------- */

interface RoleCreateFormProps {
  submitting: boolean
  profiles: PermissionProfile[]
  onSubmit: (payload: CreateClientSettingRolePayload) => void
}

function RoleCreateForm({ submitting, profiles, onSubmit }: RoleCreateFormProps): React.ReactNode {
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
    <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-3">
      <label className="flex flex-col gap-1.5 text-sm font-medium text-foreground md:text-base">
        綁定設定檔(必選)
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
        Role 名稱
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
      <button
        type="submit"
        disabled={submitting || name.trim() === '' || profileUid === ''}
        className="df-btn-primary"
      >
        新增 Role
      </button>
    </form>
  )
}

interface RoleTableProps {
  items: ClientSettingRole[]
  profileNameByUid: Record<string, string>
  deletingUid: string | null
  onDelete: (role: ClientSettingRole) => void
}

const RoleTable = memo(function RoleTable({
  items,
  profileNameByUid,
  deletingUid,
  onDelete,
}: RoleTableProps): React.ReactNode {
  if (items.length === 0) return <EmptyState message="尚無 Role" />
  return (
    <table className="df-table min-w-[720px]">
      <thead>
        <tr className="border-b border-border bg-muted/50">
          <th className="df-th">名稱</th>
          <th className="df-th">綁定設定檔</th>
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
            <td className="df-td text-muted-foreground">
              {profileNameByUid[role.permission_profile_uid] ?? '—'}
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
  const [createError, setCreateError] = useState<string | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<ClientSettingRole | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  const { data: profileData } = useListPermissionProfilesQuery()
  const { data, isLoading, isError } = useListClientSettingRolesQuery()
  const [createClientSettingRole, { isLoading: isCreating }] = useCreateClientSettingRoleMutation()
  const [deleteClientSettingRole, { isLoading: isDeleting }] = useDeleteClientSettingRoleMutation()

  const profiles = useMemo((): PermissionProfile[] => profileData?.items ?? [], [profileData])
  const profileNameByUid = useMemo((): Record<string, string> => {
    const map: Record<string, string> = {}
    for (const profile of profiles) map[profile.uid] = profile.name
    return map
  }, [profiles])
  const items = useMemo((): ClientSettingRole[] => data?.items ?? [], [data])

  const handleCreate = useCallback(
    async (payload: CreateClientSettingRolePayload): Promise<void> => {
      setCreateError(null)
      const result = await createClientSettingRole(payload)
      if ('error' in result) {
        setCreateError(extractApiErrorDetail(result.error, '建立 Role 失敗,請稍後再試'))
      }
    },
    [createClientSettingRole],
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
      setDeleteError(extractApiErrorDetail(result.error, '刪除 Role 失敗,請稍後再試'))
    }
  }, [deleteTarget, deleteClientSettingRole])

  return (
    <div className="df-card flex flex-col gap-4 p-4 md:p-5">
      <h2 className="text-base font-semibold text-foreground md:text-lg">Role</h2>
      <p className="text-sm text-muted-foreground md:text-base">
        每個 Role 必綁 1 個權限設定檔;指派給 API Client 見「API Client 設定」頁
      </p>
      <RoleCreateForm submitting={isCreating} profiles={profiles} onSubmit={handleCreate} />
      <InlineError message={createError} />
      {isLoading ? <p className="text-sm text-muted-foreground md:text-base">載入中…</p> : null}
      {isError ? <InlineError message="載入 Role 清單失敗,請稍後再試" /> : null}
      {data !== undefined ? (
        <div className="overflow-x-auto">
          <RoleTable
            items={items}
            profileNameByUid={profileNameByUid}
            deletingUid={isDeleting ? (deleteTarget?.uid ?? null) : null}
            onDelete={requestDelete}
          />
        </div>
      ) : null}
      <ConfirmDialog
        open={deleteTarget !== null}
        title="刪除 Role"
        confirmLabel="確認刪除"
        tone="danger"
        confirmDisabled={isDeleting}
        onConfirm={confirmDelete}
        onCancel={cancelDelete}
      >
        {deleteTarget !== null ? <p>確定要刪除 Role「{deleteTarget.name}」?</p> : null}
        <p>仍被 API Client 指派時後端將拒絕刪除(409)。</p>
        <InlineError message={deleteError} />
      </ConfirmDialog>
    </div>
  )
}

/* ---------------------------------------------------------------------- */
/* 特例                                                                     */
/* ---------------------------------------------------------------------- */

function ExceptionSetsSection(): React.ReactNode {
  const [createError, setCreateError] = useState<string | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<ExceptionSet | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  const { data, isLoading, isError } = useListExceptionSetsQuery()
  const [createExceptionSet, { isLoading: isCreating }] = useCreateExceptionSetMutation()
  const [deleteExceptionSet, { isLoading: isDeleting }] = useDeleteExceptionSetMutation()

  const items = useMemo((): ExceptionSet[] => data?.items ?? [], [data])

  const handleCreate = useCallback(
    async (payload: CreateExceptionSetPayload): Promise<void> => {
      setCreateError(null)
      const result = await createExceptionSet(payload)
      if ('error' in result) {
        setCreateError(extractApiErrorDetail(result.error, '建立特例權限組失敗,請稍後再試'))
      }
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
      setDeleteError(extractApiErrorDetail(result.error, '刪除特例權限組失敗,請稍後再試'))
    }
  }, [deleteTarget, deleteExceptionSet])

  return (
    <div className="df-card flex flex-col gap-4 p-4 md:p-5">
      <h2 className="text-base font-semibold text-foreground md:text-lg">特例權限組</h2>
      <p className="text-sm text-muted-foreground md:text-base">
        結構同設定檔,可重用、可綁多個 API Client(含效期);矩陣設定見 task-009,綁定 API
        Client 見「API Client 設定」頁
      </p>
      <NameDescriptionCreateForm
        submitting={isCreating}
        submitLabel="新增特例權限組"
        nameLabel="特例權限組名稱"
        onSubmit={handleCreate}
      />
      <InlineError message={createError} />
      {isLoading ? <p className="text-sm text-muted-foreground md:text-base">載入中…</p> : null}
      {isError ? <InlineError message="載入特例權限組清單失敗,請稍後再試" /> : null}
      {data !== undefined ? (
        <div className="overflow-x-auto">
          <SimpleEntityTable
            items={items}
            emptyMessage="尚無特例權限組"
            deletingUid={isDeleting ? (deleteTarget?.uid ?? null) : null}
            onDelete={requestDelete}
          />
        </div>
      ) : null}
      <ConfirmDialog
        open={deleteTarget !== null}
        title="刪除特例權限組"
        confirmLabel="確認刪除"
        tone="danger"
        confirmDisabled={isDeleting}
        onConfirm={confirmDelete}
        onCancel={cancelDelete}
      >
        {deleteTarget !== null ? <p>確定要刪除特例權限組「{deleteTarget.name}」?</p> : null}
        <p>仍被未過期綁定引用時後端將拒絕刪除(409)。</p>
        <InlineError message={deleteError} />
      </ConfirmDialog>
    </div>
  )
}

/* ---------------------------------------------------------------------- */
/* 主頁面                                                                   */
/* ---------------------------------------------------------------------- */

export default function ClientSettingsPage(): React.ReactNode {
  const [tab, setTab] = useState<TabKey>('services')

  return (
    <section className="mx-auto flex max-w-7xl flex-col gap-6">
      <div>
        <h1 className="text-xl font-bold text-foreground md:text-2xl">組織權限管理</h1>
        <p className="mt-1 text-sm text-muted-foreground md:text-base">
          系統別 / 作業範圍 → 權限設定檔矩陣 → Role;特例權限組另可臨時綁定 API Client
        </p>
      </div>

      <Segmented options={TAB_OPTIONS} value={tab} onChange={setTab} />

      {tab === 'services' ? <ServicesOperationsSection /> : null}
      {tab === 'profiles' ? <ProfilesSection /> : null}
      {tab === 'roles' ? <RolesSection /> : null}
      {tab === 'exceptions' ? <ExceptionSetsSection /> : null}
    </section>
  )
}
