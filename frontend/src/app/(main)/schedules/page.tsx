'use client'

import { memo, useCallback, useMemo, useState } from 'react'
import Link from 'next/link'
import {
  useCreateScheduleMutation,
  useDeleteScheduleMutation,
  useListSchedulesQuery,
  useSetScheduleEnabledMutation,
  useUpdateScheduleMutation,
  type Schedule,
  type ScheduleCreatePayload,
} from '@/lib/api/scheduleApi'
import { useTriggerRunMutation } from '@/lib/api/runApi'
import { useListEtlTablesQuery } from '@/lib/api/etlConfigApi'
import { useAuth } from '@/lib/auth/useAuth'
import { Pagination } from '@/components/common/Pagination'
import { extractApiErrorDetail } from '@/utils/apiError'
import { formatDateTime } from '@/utils/datetime'

const PAGE_SIZE = 20
// 指定表下拉選單來源(page_size 上限 100;超出者顯示 fallback 字樣)
const TABLE_OPTIONS_PAGE_SIZE = 100

interface TableOption {
  uid: string
  label: string
}

interface ScheduleFormProps {
  /** null = 新增模式 */
  initial: Schedule | null
  tableOptions: TableOption[]
  submitting: boolean
  submitError: string | null
  onSubmit: (payload: ScheduleCreatePayload) => void
  onCancel: () => void
}

function ScheduleForm({
  initial,
  tableOptions,
  submitting,
  submitError,
  onSubmit,
  onCancel,
}: ScheduleFormProps): React.ReactNode {
  const [name, setName] = useState(initial?.name ?? '')
  const [cronExpr, setCronExpr] = useState(initial?.cron_expr ?? '')
  const [etlTableUid, setEtlTableUid] = useState(initial?.etl_table_uid ?? '')
  const [description, setDescription] = useState(initial?.description ?? '')
  const [isEnabled, setIsEnabled] = useState(initial?.is_enabled ?? true)

  const handleNameChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>): void => {
      setName(event.target.value)
    },
    [],
  )
  const handleCronChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>): void => {
      setCronExpr(event.target.value)
    },
    [],
  )
  const handleTableChange = useCallback(
    (event: React.ChangeEvent<HTMLSelectElement>): void => {
      setEtlTableUid(event.target.value)
    },
    [],
  )
  const handleDescriptionChange = useCallback(
    (event: React.ChangeEvent<HTMLTextAreaElement>): void => {
      setDescription(event.target.value)
    },
    [],
  )
  const handleEnabledChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>): void => {
      setIsEnabled(event.target.checked)
    },
    [],
  )

  const handleSubmit = useCallback(
    (event: React.FormEvent<HTMLFormElement>): void => {
      event.preventDefault()
      onSubmit({
        name: name.trim(),
        cron_expr: cronExpr.trim(),
        is_enabled: isEnabled,
        etl_table_uid: etlTableUid === '' ? null : etlTableUid,
        description: description.trim() === '' ? null : description.trim(),
      })
    },
    [onSubmit, name, cronExpr, isEnabled, etlTableUid, description],
  )

  return (
    <form
      onSubmit={handleSubmit}
      className="df-card flex flex-col gap-4 p-5 md:p-6"
    >
      <h2 className="text-lg font-bold text-foreground md:text-xl">
        {initial === null ? '新增排程' : `編輯排程:${initial.name}`}
      </h2>

      {submitError !== null ? (
        <p
          role="alert"
          className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger md:text-base"
        >
          {submitError}
        </p>
      ) : null}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <label className="flex flex-col gap-1.5 text-sm font-medium text-foreground md:text-base">
          名稱
          <input
            type="text"
            required
            maxLength={200}
            value={name}
            onChange={handleNameChange}
            className="df-input"
          />
        </label>
        <label className="flex flex-col gap-1.5 text-sm font-medium text-foreground md:text-base">
          cron 運算式(UTC+8)
          <input
            type="text"
            required
            maxLength={100}
            value={cronExpr}
            onChange={handleCronChange}
            placeholder="分 時 日 月 週,例:0 2 * * *"
            className="df-input"
          />
        </label>
        <label className="flex flex-col gap-1.5 text-sm font-medium text-foreground md:text-base">
          執行範圍
          <select
            value={etlTableUid}
            onChange={handleTableChange}
            className="df-input"
          >
            <option value="">全部啟用表</option>
            {tableOptions.map((option) => (
              <option key={option.uid} value={option.uid}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1.5 text-sm font-medium text-foreground md:text-base">
          描述
          <textarea
            value={description}
            onChange={handleDescriptionChange}
            rows={2}
            className="df-input min-h-[44px] py-2"
          />
        </label>
      </div>

      {initial === null ? (
        <label className="flex items-center gap-2 text-sm font-medium text-foreground md:text-base">
          <input
            type="checkbox"
            checked={isEnabled}
            onChange={handleEnabledChange}
            className="h-5 w-5 accent-[rgb(var(--primary))]"
          />
          建立後立即啟用
        </label>
      ) : null}

      <div className="flex gap-2">
        <button type="submit" disabled={submitting} className="df-btn-primary">
          {initial === null ? '建立' : '儲存'}
        </button>
        <button type="button" onClick={onCancel} className="df-btn-outline">
          取消
        </button>
      </div>
    </form>
  )
}

interface ScheduleRowProps {
  schedule: Schedule
  /** 執行範圍顯示字樣(全部啟用表 / 表名) */
  scopeLabel: string
  canEdit: boolean
  busy: boolean
  confirmingDelete: boolean
  onEdit: (schedule: Schedule) => void
  onToggle: (schedule: Schedule) => void
  onTrigger: (schedule: Schedule) => void
  onRequestDelete: (uid: string) => void
  onConfirmDelete: (uid: string) => void
  onCancelDelete: () => void
}

const ScheduleRow = memo(function ScheduleRow({
  schedule,
  scopeLabel,
  canEdit,
  busy,
  confirmingDelete,
  onEdit,
  onToggle,
  onTrigger,
  onRequestDelete,
  onConfirmDelete,
  onCancelDelete,
}: ScheduleRowProps): React.ReactNode {
  const handleEdit = useCallback((): void => {
    onEdit(schedule)
  }, [onEdit, schedule])
  const handleToggle = useCallback((): void => {
    onToggle(schedule)
  }, [onToggle, schedule])
  const handleTrigger = useCallback((): void => {
    onTrigger(schedule)
  }, [onTrigger, schedule])
  const handleRequestDelete = useCallback((): void => {
    onRequestDelete(schedule.uid)
  }, [onRequestDelete, schedule.uid])
  const handleConfirmDelete = useCallback((): void => {
    onConfirmDelete(schedule.uid)
  }, [onConfirmDelete, schedule.uid])

  const enabledClass = schedule.is_enabled
    ? 'bg-success/15 text-success'
    : 'bg-muted text-muted-foreground'
  const actionSize = 'min-h-[36px] px-3'

  return (
    <tr className="border-b border-border transition-colors last:border-b-0 hover:bg-muted/50">
      <td className="px-3 py-3">
        <p className="text-sm font-medium text-foreground md:text-base">
          {schedule.name}
        </p>
        {schedule.description !== null && schedule.description !== '' ? (
          <p className="mt-0.5 text-sm text-muted-foreground">
            {schedule.description}
          </p>
        ) : null}
      </td>
      <td className="df-td font-mono text-muted-foreground">
        {schedule.cron_expr}
      </td>
      <td className="df-td text-muted-foreground">{scopeLabel}</td>
      <td className="px-3 py-3">
        <span className={`df-badge ${enabledClass}`}>
          {schedule.is_enabled ? '啟用' : '停用'}
        </span>
      </td>
      <td className="df-td text-muted-foreground">
        {formatDateTime(schedule.updated_at)}
      </td>
      {canEdit ? (
        <td className="px-3 py-3">
          <div className="flex flex-nowrap gap-2">
            <button
              type="button"
              onClick={handleEdit}
              disabled={busy}
              className={`df-btn-info-soft ${actionSize}`}
            >
              編輯
            </button>
            <button
              type="button"
              onClick={handleToggle}
              disabled={busy}
              className={`df-btn-warning-soft ${actionSize}`}
            >
              {schedule.is_enabled ? '停用' : '啟用'}
            </button>
            <button
              type="button"
              onClick={handleTrigger}
              disabled={busy}
              className={`df-btn-primary-soft ${actionSize}`}
            >
              手動觸發
            </button>
            {confirmingDelete ? (
              <>
                <button
                  type="button"
                  onClick={handleConfirmDelete}
                  disabled={busy}
                  className={`df-btn-danger ${actionSize}`}
                >
                  確認刪除
                </button>
                <button
                  type="button"
                  onClick={onCancelDelete}
                  disabled={busy}
                  className={`df-btn-outline ${actionSize}`}
                >
                  取消
                </button>
              </>
            ) : (
              <button
                type="button"
                onClick={handleRequestDelete}
                disabled={busy}
                className={`df-btn-danger-soft ${actionSize}`}
              >
                刪除
              </button>
            )}
          </div>
        </td>
      ) : null}
    </tr>
  )
})

type FormState =
  | { mode: 'closed' }
  | { mode: 'create' }
  | { mode: 'edit'; schedule: Schedule }

export default function SchedulesPage(): React.ReactNode {
  const { isAdmin } = useAuth()
  const [page, setPage] = useState(1)
  const [formState, setFormState] = useState<FormState>({ mode: 'closed' })
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [triggerNotice, setTriggerNotice] = useState<string | null>(null)
  const [confirmDeleteUid, setConfirmDeleteUid] = useState<string | null>(null)
  const [busyUid, setBusyUid] = useState<string | null>(null)

  const { data, isLoading, isError } = useListSchedulesQuery({
    page,
    pageSize: PAGE_SIZE,
  })
  const { data: tablesData } = useListEtlTablesQuery({
    page: 1,
    pageSize: TABLE_OPTIONS_PAGE_SIZE,
  })

  const [createSchedule, { isLoading: isCreating }] =
    useCreateScheduleMutation()
  const [updateSchedule, { isLoading: isUpdating }] =
    useUpdateScheduleMutation()
  const [deleteSchedule] = useDeleteScheduleMutation()
  const [setEnabled] = useSetScheduleEnabledMutation()
  const [triggerRun] = useTriggerRunMutation()

  const tableOptions = useMemo(
    (): TableOption[] =>
      (tablesData?.items ?? []).map((item) => ({
        uid: item.uid,
        label: `${item.source_schema}.${item.source_table}`,
      })),
    [tablesData],
  )

  const tableLabelMap = useMemo((): ReadonlyMap<string, string> => {
    return new Map(tableOptions.map((option) => [option.uid, option.label]))
  }, [tableOptions])

  const resolveScopeLabel = useCallback(
    (etlTableUid: string | null): string => {
      if (etlTableUid === null) {
        return '全部啟用表'
      }
      return tableLabelMap.get(etlTableUid) ?? '指定單表'
    },
    [tableLabelMap],
  )

  const handlePageChange = useCallback((nextPage: number): void => {
    setPage(nextPage)
  }, [])

  const openCreate = useCallback((): void => {
    setSubmitError(null)
    setFormState({ mode: 'create' })
  }, [])

  const openEdit = useCallback((schedule: Schedule): void => {
    setSubmitError(null)
    setFormState({ mode: 'edit', schedule })
  }, [])

  const closeForm = useCallback((): void => {
    setSubmitError(null)
    setFormState({ mode: 'closed' })
  }, [])

  const handleSubmit = useCallback(
    async (payload: ScheduleCreatePayload): Promise<void> => {
      setSubmitError(null)
      const result =
        formState.mode === 'edit'
          ? await updateSchedule({
              uid: formState.schedule.uid,
              name: payload.name,
              cron_expr: payload.cron_expr,
              etl_table_uid: payload.etl_table_uid,
              description: payload.description,
            })
          : await createSchedule(payload)
      if ('error' in result) {
        setSubmitError(
          extractApiErrorDetail(result.error, '儲存排程失敗,請稍後再試'),
        )
        return
      }
      setFormState({ mode: 'closed' })
    },
    [formState, createSchedule, updateSchedule],
  )

  const handleToggle = useCallback(
    async (schedule: Schedule): Promise<void> => {
      setActionError(null)
      setBusyUid(schedule.uid)
      const result = await setEnabled({
        uid: schedule.uid,
        enabled: !schedule.is_enabled,
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

  const handleTrigger = useCallback(
    async (schedule: Schedule): Promise<void> => {
      setActionError(null)
      setTriggerNotice(null)
      setBusyUid(schedule.uid)
      const result = await triggerRun({ etlTableUid: schedule.etl_table_uid })
      if ('error' in result) {
        setActionError(
          extractApiErrorDetail(result.error, '手動觸發失敗,請稍後再試'),
        )
      } else {
        setTriggerNotice(
          `已送出手動觸發(${schedule.name},範圍:${resolveScopeLabel(schedule.etl_table_uid)})`,
        )
      }
      setBusyUid(null)
    },
    [triggerRun, resolveScopeLabel],
  )

  const handleRequestDelete = useCallback((uid: string): void => {
    setConfirmDeleteUid(uid)
  }, [])

  const handleCancelDelete = useCallback((): void => {
    setConfirmDeleteUid(null)
  }, [])

  const handleConfirmDelete = useCallback(
    async (uid: string): Promise<void> => {
      setActionError(null)
      setBusyUid(uid)
      const result = await deleteSchedule(uid)
      if ('error' in result) {
        setActionError(
          extractApiErrorDetail(result.error, '刪除排程失敗,請稍後再試'),
        )
      }
      setConfirmDeleteUid(null)
      setBusyUid(null)
    },
    [deleteSchedule],
  )

  return (
    <section className="mx-auto flex max-w-7xl flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-foreground md:text-2xl">
            排程管理
          </h1>
          <p className="mt-1 text-sm text-muted-foreground md:text-base">
            cron 排程 CRUD、啟停與手動觸發(時間一律 UTC+8)
          </p>
        </div>
        {isAdmin && formState.mode === 'closed' ? (
          <button
            type="button"
            onClick={openCreate}
            className="df-btn-primary"
          >
            新增排程
          </button>
        ) : null}
      </div>

      {isAdmin && formState.mode !== 'closed' ? (
        <ScheduleForm
          key={formState.mode === 'edit' ? formState.schedule.uid : 'create'}
          initial={formState.mode === 'edit' ? formState.schedule : null}
          tableOptions={tableOptions}
          submitting={isCreating || isUpdating}
          submitError={submitError}
          onSubmit={handleSubmit}
          onCancel={closeForm}
        />
      ) : null}

      {actionError !== null ? (
        <p
          role="alert"
          className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger md:text-base"
        >
          {actionError}
        </p>
      ) : null}
      {triggerNotice !== null ? (
        <p className="rounded-lg bg-success/15 px-3 py-2 text-sm text-success md:text-base">
          {triggerNotice},
          <Link
            href="/runs"
            className="ml-1 font-medium underline underline-offset-2"
          >
            前往執行紀錄
          </Link>
        </p>
      ) : null}

      {isLoading ? (
        <p className="text-sm text-muted-foreground md:text-base">載入中…</p>
      ) : null}
      {isError ? (
        <p
          role="alert"
          className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger md:text-base"
        >
          載入排程清單失敗,請稍後再試
        </p>
      ) : null}

      {data !== undefined ? (
        <div className="flex flex-col gap-3">
          <div className="df-card overflow-x-auto">
            <table className="df-table min-w-[880px]">
              <thead>
                <tr className="border-b border-border bg-muted/50">
                  <th className="df-th">名稱</th>
                  <th className="df-th">cron</th>
                  <th className="df-th">執行範圍</th>
                  <th className="df-th">狀態</th>
                  <th className="df-th">更新時間</th>
                  {isAdmin ? <th className="df-th">操作</th> : null}
                </tr>
              </thead>
              <tbody>
                {data.items.map((schedule) => (
                  <ScheduleRow
                    key={schedule.uid}
                    schedule={schedule}
                    scopeLabel={resolveScopeLabel(schedule.etl_table_uid)}
                    canEdit={isAdmin}
                    busy={busyUid === schedule.uid}
                    confirmingDelete={confirmDeleteUid === schedule.uid}
                    onEdit={openEdit}
                    onToggle={handleToggle}
                    onTrigger={handleTrigger}
                    onRequestDelete={handleRequestDelete}
                    onConfirmDelete={handleConfirmDelete}
                    onCancelDelete={handleCancelDelete}
                  />
                ))}
              </tbody>
            </table>
            {data.items.length === 0 ? (
              <p className="px-3 py-8 text-center text-sm text-muted-foreground md:text-base">
                尚無排程
              </p>
            ) : null}
          </div>
          <Pagination
            page={data.page}
            pageSize={data.page_size}
            total={data.total}
            onPageChange={handlePageChange}
          />
        </div>
      ) : null}
    </section>
  )
}
