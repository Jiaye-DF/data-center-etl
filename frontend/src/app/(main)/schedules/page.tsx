'use client'

import { memo, useCallback, useState } from 'react'
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
import { useAuth } from '@/lib/auth/useAuth'
import { Pagination } from '@/components/common/Pagination'
import { ScheduleFormDialog } from '@/components/schedules/ScheduleFormDialog'
import { extractApiErrorDetail } from '@/utils/apiError'
import { formatDateTime } from '@/utils/datetime'

const PAGE_SIZE = 20

/** 上次執行結果 status → 中文標籤 + badge 樣式(null / 未知 = 未跑) */
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
    case 'partial':
      return { label: '部分成功', className: 'bg-warning/15 text-warning' }
    case 'running':
      return { label: '執行中', className: 'bg-info/15 text-info' }
    case 'pending':
      return { label: '等待中', className: 'bg-muted text-muted-foreground' }
    default:
      return { label: '未跑', className: 'bg-muted text-muted-foreground' }
  }
}

interface ScheduleRowProps {
  schedule: Schedule
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
  const lastRun = resolveLastRun(schedule.last_run_status)
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
      <td className="df-td text-muted-foreground">{schedule.job_desc}</td>
      <td className="px-3 py-3">
        <span className={`df-badge ${lastRun.className}`}>{lastRun.label}</span>
        {schedule.last_run_finished_at !== null ? (
          <p className="mt-0.5 text-xs text-muted-foreground">
            {formatDateTime(schedule.last_run_finished_at)}
          </p>
        ) : null}
      </td>
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

  const [createSchedule, { isLoading: isCreating }] =
    useCreateScheduleMutation()
  const [updateSchedule, { isLoading: isUpdating }] =
    useUpdateScheduleMutation()
  const [deleteSchedule] = useDeleteScheduleMutation()
  const [setEnabled] = useSetScheduleEnabledMutation()
  const [triggerRun] = useTriggerRunMutation()

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
      const result = await triggerRun({ etlTableUid: null })
      if ('error' in result) {
        setActionError(
          extractApiErrorDetail(result.error, '手動觸發失敗,請稍後再試'),
        )
      } else {
        setTriggerNotice(`已送出手動觸發(${schedule.name})`)
      }
      setBusyUid(null)
    },
    [triggerRun],
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
        {isAdmin ? (
          <button
            type="button"
            onClick={openCreate}
            className="df-btn-primary"
          >
            新增排程
          </button>
        ) : null}
      </div>

      {isAdmin ? (
        <ScheduleFormDialog
          key={formState.mode === 'edit' ? formState.schedule.uid : 'create'}
          open={formState.mode !== 'closed'}
          initial={formState.mode === 'edit' ? formState.schedule : null}
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
                  <th className="df-th">做什麼</th>
                  <th className="df-th">上次結果</th>
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
