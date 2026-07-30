'use client'

import { memo, useCallback, useEffect, useMemo, useState } from 'react'
import {
  useCreateApiClientMutation,
  useListApiClientSecretsQuery,
  useListApiClientsQuery,
  useRetireApiClientSecretMutation,
  useRotateApiClientSecretMutation,
  useUpdateApiClientMutation,
  type ApiClientListItem,
  type ApiClientSecretItem,
  type ApiClientStatus,
  type CreateApiClientPayload,
  type UpdateApiClientPayload,
} from '@/lib/api/apiClientApi'
import { ConfirmDialog } from '@/components/common/ConfirmDialog'
import { Pagination } from '@/components/common/Pagination'
import { extractApiErrorDetail } from '@/utils/apiError'
import { formatDateTime } from '@/utils/datetime'

const PAGE_SIZE = 20
const MAX_ACTIVE_SECRETS = 2

/* ---------------------------------------------------------------------- */
/* 小型顯示元件                                                             */
/* ---------------------------------------------------------------------- */

interface ApiClientStatusBadgeProps {
  status: ApiClientStatus
}

const ApiClientStatusBadge = memo(function ApiClientStatusBadge({
  status,
}: ApiClientStatusBadgeProps): React.ReactNode {
  const isEnabled = status === 'enabled'
  return (
    <span
      className={`df-badge ${isEnabled ? 'bg-success/15 text-success' : 'bg-muted text-muted-foreground'}`}
    >
      {isEnabled ? '啟用中' : '已停用'}
    </span>
  )
})

interface CopyButtonProps {
  value: string
}

const CopyButton = memo(function CopyButton({ value }: CopyButtonProps): React.ReactNode {
  const [copied, setCopied] = useState(false)

  const handleCopy = useCallback((): void => {
    void navigator.clipboard.writeText(value).then(() => {
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    })
  }, [value])

  return (
    <button
      type="button"
      onClick={handleCopy}
      className="df-btn-outline min-h-0 shrink-0 px-2 py-1 text-sm"
    >
      {copied ? '已複製' : '複製'}
    </button>
  )
})

/* ---------------------------------------------------------------------- */
/* 一次性密鑰面板(建立 / 輪替共用)                                          */
/* ---------------------------------------------------------------------- */

interface SecretRevealPanelProps {
  clientId: string
  clientSecret: string
  onRequestClose: () => void
}

function SecretRevealPanel({
  clientId,
  clientSecret,
  onRequestClose,
}: SecretRevealPanelProps): React.ReactNode {
  const [confirmingClose, setConfirmingClose] = useState(false)

  useEffect(() => {
    const onKey = (event: KeyboardEvent): void => {
      if (event.key === 'Escape') setConfirmingClose(true)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const handleCloseClick = useCallback((): void => setConfirmingClose(true), [])
  const handleCancelClose = useCallback((): void => setConfirmingClose(false), [])
  const handleConfirmClose = useCallback((): void => {
    setConfirmingClose(false)
    onRequestClose()
  }, [onRequestClose])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/40" />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="secret-reveal-title"
        className="df-card relative z-10 flex w-full max-w-xl flex-col gap-4 p-6 md:p-8"
      >
        <h2 id="secret-reveal-title" className="text-lg font-bold text-foreground md:text-xl">
          密鑰核發成功
        </h2>
        <p className="rounded-lg bg-warning/15 px-3 py-2 text-sm text-warning md:text-base">
          關閉後將不再顯示此密鑰明文,請立即複製並妥善保存。
        </p>
        <div className="flex flex-col gap-1.5">
          <span className="text-sm font-medium text-foreground md:text-base">Client ID</span>
          <div className="flex items-center gap-2">
            <code className="df-input flex-1 overflow-x-auto font-mono text-sm">{clientId}</code>
            <CopyButton value={clientId} />
          </div>
        </div>
        <div className="flex flex-col gap-1.5">
          <span className="text-sm font-medium text-foreground md:text-base">Client Secret</span>
          <div className="flex items-center gap-2">
            <code className="df-input flex-1 overflow-x-auto font-mono text-sm">
              {clientSecret}
            </code>
            <CopyButton value={clientSecret} />
          </div>
        </div>
        <div className="mt-1 flex gap-2">
          <button type="button" onClick={handleCloseClick} className="df-btn-primary">
            關閉
          </button>
        </div>
      </div>
      <ConfirmDialog
        open={confirmingClose}
        title="確認關閉"
        confirmLabel="確認關閉"
        tone="danger"
        onConfirm={handleConfirmClose}
        onCancel={handleCancelClose}
      >
        <p>關閉後將不再顯示此密鑰明文,請確認已複製保存。</p>
      </ConfirmDialog>
    </div>
  )
}

/* ---------------------------------------------------------------------- */
/* 建立 Client 對話框                                                       */
/* ---------------------------------------------------------------------- */

interface CreateClientDialogProps {
  open: boolean
  submitting: boolean
  submitError: string | null
  onSubmit: (payload: CreateApiClientPayload) => void
  onCancel: () => void
}

function CreateClientDialog({
  open,
  submitting,
  submitError,
  onSubmit,
  onCancel,
}: CreateClientDialogProps): React.ReactNode {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')

  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent): void => {
      if (event.key === 'Escape') onCancel()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onCancel])

  const handleNameChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>): void => setName(event.target.value),
    [],
  )
  const handleDescriptionChange = useCallback(
    (event: React.ChangeEvent<HTMLTextAreaElement>): void =>
      setDescription(event.target.value),
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

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        aria-label="關閉對話框"
        onClick={onCancel}
        className="absolute inset-0 cursor-default bg-black/40"
      />
      <form
        onSubmit={handleSubmit}
        role="dialog"
        aria-modal="true"
        aria-labelledby="create-client-dialog-title"
        className="df-card relative z-10 flex w-full max-w-xl flex-col gap-4 p-6 md:p-8"
      >
        <h2
          id="create-client-dialog-title"
          className="text-lg font-bold text-foreground md:text-xl"
        >
          建立 API Client
        </h2>
        {submitError !== null ? (
          <p
            role="alert"
            className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger md:text-base"
          >
            {submitError}
          </p>
        ) : null}
        <label className="flex flex-col gap-1.5 text-sm font-medium text-foreground md:text-base">
          應用系統名稱
          <input
            type="text"
            value={name}
            onChange={handleNameChange}
            required
            className="df-input"
          />
        </label>
        <label className="flex flex-col gap-1.5 text-sm font-medium text-foreground md:text-base">
          用途說明(選填)
          <textarea
            value={description}
            onChange={handleDescriptionChange}
            rows={2}
            className="df-input min-h-[44px] py-2"
          />
        </label>
        <div className="mt-1 flex gap-2">
          <button
            type="submit"
            disabled={submitting || name.trim() === ''}
            className="df-btn-primary"
          >
            建立
          </button>
          <button type="button" onClick={onCancel} className="df-btn-outline">
            取消
          </button>
        </div>
      </form>
    </div>
  )
}

/* ---------------------------------------------------------------------- */
/* 編輯 Client 對話框(含停用二次確認)                                       */
/* ---------------------------------------------------------------------- */

interface EditClientDialogProps {
  client: ApiClientListItem | null
  submitting: boolean
  submitError: string | null
  onSubmit: (payload: UpdateApiClientPayload) => void
  onCancel: () => void
}

function EditClientDialog({
  client,
  submitting,
  submitError,
  onSubmit,
  onCancel,
}: EditClientDialogProps): React.ReactNode {
  const [name, setName] = useState(client?.name ?? '')
  const [description, setDescription] = useState(client?.description ?? '')
  const [rateLimitPerMinute, setRateLimitPerMinute] = useState(
    client?.rate_limit_per_minute ?? 1,
  )
  const [rateLimitPer10Min, setRateLimitPer10Min] = useState(
    client?.rate_limit_per_10min ?? 1,
  )
  const [enabled, setEnabled] = useState(client?.status === 'enabled')
  const [confirmingDisable, setConfirmingDisable] = useState(false)

  useEffect(() => {
    if (client === null) return
    const onKey = (event: KeyboardEvent): void => {
      if (event.key === 'Escape') onCancel()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [client, onCancel])

  const handleNameChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>): void => setName(event.target.value),
    [],
  )
  const handleDescriptionChange = useCallback(
    (event: React.ChangeEvent<HTMLTextAreaElement>): void =>
      setDescription(event.target.value),
    [],
  )
  const handleRateMinuteChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>): void => {
      const value = Number(event.target.value)
      setRateLimitPerMinute(Number.isNaN(value) || value < 1 ? 1 : value)
    },
    [],
  )
  const handleRate10MinChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>): void => {
      const value = Number(event.target.value)
      setRateLimitPer10Min(Number.isNaN(value) || value < 1 ? 1 : value)
    },
    [],
  )
  const handleEnabledChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>): void => setEnabled(event.target.checked),
    [],
  )

  const buildPayload = useCallback(
    (statusOverride?: ApiClientStatus): UpdateApiClientPayload => {
      if (client === null) throw new Error('client is null')
      return {
        uid: client.uid,
        name: name.trim(),
        description: description.trim() === '' ? null : description.trim(),
        status: statusOverride ?? (enabled ? 'enabled' : 'disabled'),
        rate_limit_per_minute: rateLimitPerMinute,
        rate_limit_per_10min: rateLimitPer10Min,
      }
    },
    [client, name, description, enabled, rateLimitPerMinute, rateLimitPer10Min],
  )

  const handleSubmit = useCallback(
    (event: React.FormEvent<HTMLFormElement>): void => {
      event.preventDefault()
      if (client === null || name.trim() === '') return
      const turningOff = client.status === 'enabled' && !enabled
      if (turningOff) {
        setConfirmingDisable(true)
        return
      }
      onSubmit(buildPayload())
    },
    [client, name, enabled, buildPayload, onSubmit],
  )

  const handleConfirmDisable = useCallback((): void => {
    setConfirmingDisable(false)
    onSubmit(buildPayload('disabled'))
  }, [buildPayload, onSubmit])

  const handleCancelDisable = useCallback((): void => {
    setConfirmingDisable(false)
    setEnabled(true)
  }, [])

  if (client === null) return null

  return (
    <>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <button
          type="button"
          aria-label="關閉對話框"
          onClick={onCancel}
          className="absolute inset-0 cursor-default bg-black/40"
        />
        <form
          onSubmit={handleSubmit}
          role="dialog"
          aria-modal="true"
          aria-labelledby="edit-client-dialog-title"
          className="df-card relative z-10 flex max-h-[90vh] w-full max-w-xl flex-col gap-4 overflow-y-auto p-6 md:p-8"
        >
          <h2
            id="edit-client-dialog-title"
            className="text-lg font-bold text-foreground md:text-xl"
          >
            編輯 API Client:{client.name}
          </h2>
          {submitError !== null ? (
            <p
              role="alert"
              className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger md:text-base"
            >
              {submitError}
            </p>
          ) : null}
          <label className="flex flex-col gap-1.5 text-sm font-medium text-foreground md:text-base">
            應用系統名稱
            <input
              type="text"
              value={name}
              onChange={handleNameChange}
              required
              className="df-input"
            />
          </label>
          <label className="flex flex-col gap-1.5 text-sm font-medium text-foreground md:text-base">
            用途說明(選填)
            <textarea
              value={description}
              onChange={handleDescriptionChange}
              rows={2}
              className="df-input min-h-[44px] py-2"
            />
          </label>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <label className="flex flex-col gap-1.5 text-sm font-medium text-foreground md:text-base">
              每分鐘請求上限
              <input
                type="number"
                min={1}
                value={rateLimitPerMinute}
                onChange={handleRateMinuteChange}
                className="df-input"
              />
            </label>
            <label className="flex flex-col gap-1.5 text-sm font-medium text-foreground md:text-base">
              每 10 分鐘請求上限
              <input
                type="number"
                min={1}
                value={rateLimitPer10Min}
                onChange={handleRate10MinChange}
                className="df-input"
              />
            </label>
          </div>
          <label className="flex items-center gap-2 text-sm font-medium text-foreground md:text-base">
            <input
              type="checkbox"
              checked={enabled}
              onChange={handleEnabledChange}
              className="h-5 w-5 accent-[rgb(var(--primary))]"
            />
            啟用此 API Client(停用將立即無法取得 token)
          </label>
          <div className="mt-1 flex gap-2">
            <button
              type="submit"
              disabled={submitting || name.trim() === ''}
              className="df-btn-primary"
            >
              儲存
            </button>
            <button type="button" onClick={onCancel} className="df-btn-outline">
              取消
            </button>
          </div>
        </form>
      </div>
      <ConfirmDialog
        open={confirmingDisable}
        title="停用 API Client"
        confirmLabel="確認停用"
        tone="danger"
        confirmDisabled={submitting}
        onConfirm={handleConfirmDisable}
        onCancel={handleCancelDisable}
      >
        <p>
          停用「{client.name}」後,該系統將<strong>立即無法取得 token</strong>。
        </p>
        <p>請確認已通知相關系統負責人再停用。</p>
      </ConfirmDialog>
    </>
  )
}

/* ---------------------------------------------------------------------- */
/* 密鑰紀錄(伺服器資料)                                                     */
/* ---------------------------------------------------------------------- */

interface SecretItemProps {
  client: ApiClientListItem
  secret: ApiClientSecretItem
  retiring: boolean
  onRequestRetire: (client: ApiClientListItem, secret: ApiClientSecretItem) => void
}

const SecretItem = memo(function SecretItem({
  client,
  secret,
  retiring,
  onRequestRetire,
}: SecretItemProps): React.ReactNode {
  const handleClick = useCallback(
    (): void => onRequestRetire(client, secret),
    [onRequestRetire, client, secret],
  )

  return (
    <li className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-card px-3 py-2">
      <span className="text-sm text-foreground md:text-base">
        核發於 {formatDateTime(secret.created_at)} ·{' '}
        {secret.status === 'active' ? (
          <span className="text-success">有效</span>
        ) : (
          <span className="text-muted-foreground">已汰換</span>
        )}
      </span>
      <button
        type="button"
        disabled={secret.status === 'retired' || retiring}
        onClick={handleClick}
        className="df-btn-danger-soft px-3 py-1.5 text-sm"
      >
        汰換
      </button>
    </li>
  )
})

interface SecretHistoryPanelProps {
  client: ApiClientListItem
  retiringSecretUid: string | null
  onRequestRetire: (client: ApiClientListItem, secret: ApiClientSecretItem) => void
}

function SecretHistoryPanel({
  client,
  retiringSecretUid,
  onRequestRetire,
}: SecretHistoryPanelProps): React.ReactNode {
  const { data, isLoading, isError } = useListApiClientSecretsQuery(client.uid)

  if (isLoading) {
    return <p className="text-sm text-muted-foreground md:text-base">載入密鑰紀錄中…</p>
  }
  if (isError || data === undefined) {
    return (
      <p role="alert" className="text-sm text-danger md:text-base">
        載入密鑰紀錄失敗,請稍後再試
      </p>
    )
  }
  if (data.items.length === 0) {
    return <p className="text-sm text-muted-foreground md:text-base">尚無密鑰紀錄</p>
  }

  return (
    <>
      <p className="mb-2 text-sm text-muted-foreground md:text-base">
        密鑰明文僅在核發當次顯示一次,此處只列出核發時間與狀態。
      </p>
      <ul className="flex flex-col gap-2">
        {data.items.map((secret) => (
          <SecretItem
            key={secret.uid}
            client={client}
            secret={secret}
            retiring={retiringSecretUid === secret.uid}
            onRequestRetire={onRequestRetire}
          />
        ))}
      </ul>
    </>
  )
}

/* ---------------------------------------------------------------------- */
/* 清單列                                                                   */
/* ---------------------------------------------------------------------- */

interface ApiClientRowProps {
  client: ApiClientListItem
  expanded: boolean
  rotating: boolean
  retiringSecretUid: string | null
  onToggleExpand: (uid: string) => void
  onEdit: (client: ApiClientListItem) => void
  onRotate: (client: ApiClientListItem) => void
  onRequestRetire: (client: ApiClientListItem, secret: ApiClientSecretItem) => void
}

const ApiClientRow = memo(function ApiClientRow({
  client,
  expanded,
  rotating,
  retiringSecretUid,
  onToggleExpand,
  onEdit,
  onRotate,
  onRequestRetire,
}: ApiClientRowProps): React.ReactNode {
  const handleToggle = useCallback((): void => onToggleExpand(client.uid), [
    onToggleExpand,
    client.uid,
  ])
  const handleEdit = useCallback((): void => onEdit(client), [onEdit, client])
  const handleRotate = useCallback((): void => onRotate(client), [onRotate, client])

  const rotateDisabled = rotating || client.active_secret_count >= MAX_ACTIVE_SECRETS

  return (
    <>
      <tr className="border-b border-border transition-colors last:border-b-0 hover:bg-muted/50">
        <td className="px-3 py-3 text-sm font-medium text-foreground md:text-base">
          {client.name}
        </td>
        <td className="px-3 py-3">
          <div className="flex items-center gap-2">
            <code className="text-sm font-mono text-muted-foreground md:text-base">
              {client.client_id}
            </code>
            <CopyButton value={client.client_id} />
          </div>
        </td>
        <td className="df-td">
          <ApiClientStatusBadge status={client.status} />
        </td>
        <td className="df-td">{client.rate_limit_per_minute}</td>
        <td className="df-td">{client.rate_limit_per_10min}</td>
        <td className="df-td">{client.active_secret_count}</td>
        <td className="df-td text-muted-foreground">{formatDateTime(client.created_at)}</td>
        <td className="px-3 py-3">
          <div className="flex flex-wrap gap-2">
            <button type="button" onClick={handleEdit} className="df-btn-outline px-3 py-1.5 text-sm">
              編輯
            </button>
            <button
              type="button"
              onClick={handleRotate}
              disabled={rotateDisabled}
              title={
                client.active_secret_count >= MAX_ACTIVE_SECRETS
                  ? '已有 2 把有效密鑰,請先汰換舊密鑰'
                  : undefined
              }
              className="df-btn-outline px-3 py-1.5 text-sm"
            >
              核發新密鑰
            </button>
            <button
              type="button"
              onClick={handleToggle}
              className="df-btn-outline px-3 py-1.5 text-sm"
            >
              {expanded ? '收合密鑰' : '密鑰紀錄'}
            </button>
          </div>
        </td>
      </tr>
      {expanded ? (
        <tr className="border-b border-border bg-muted/30 last:border-b-0">
          <td colSpan={8} className="px-3 py-3">
            <SecretHistoryPanel
              client={client}
              retiringSecretUid={retiringSecretUid}
              onRequestRetire={onRequestRetire}
            />
          </td>
        </tr>
      ) : null}
    </>
  )
})

/* ---------------------------------------------------------------------- */
/* 主頁面                                                                   */
/* ---------------------------------------------------------------------- */

export default function ApiClientsPage(): React.ReactNode {
  const [page, setPage] = useState(1)
  const [createOpen, setCreateOpen] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)
  const [editingClient, setEditingClient] = useState<ApiClientListItem | null>(null)
  const [editError, setEditError] = useState<string | null>(null)
  const [revealSecret, setRevealSecret] = useState<{ clientId: string; secret: string } | null>(
    null,
  )
  const [expandedUid, setExpandedUid] = useState<string | null>(null)
  const [retireTarget, setRetireTarget] = useState<{
    client: ApiClientListItem
    secret: ApiClientSecretItem
  } | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const { data, isLoading, isError, isFetching } = useListApiClientsQuery({
    page,
    pageSize: PAGE_SIZE,
  })
  const [createApiClient, { isLoading: isCreating }] = useCreateApiClientMutation()
  const [updateApiClient, { isLoading: isUpdating }] = useUpdateApiClientMutation()
  const [rotateApiClientSecret, { isLoading: isRotating }] = useRotateApiClientSecretMutation()
  const [retireApiClientSecret, { isLoading: isRetiring }] = useRetireApiClientSecretMutation()

  const handlePageChange = useCallback((next: number): void => setPage(next), [])

  const openCreate = useCallback((): void => {
    setCreateError(null)
    setCreateOpen(true)
  }, [])
  const closeCreate = useCallback((): void => setCreateOpen(false), [])

  const handleCreateSubmit = useCallback(
    async (payload: CreateApiClientPayload): Promise<void> => {
      setCreateError(null)
      const result = await createApiClient(payload)
      if ('error' in result) {
        setCreateError(extractApiErrorDetail(result.error, '建立 API Client 失敗,請稍後再試'))
        return
      }
      setCreateOpen(false)
      setRevealSecret({
        clientId: result.data.client.client_id,
        secret: result.data.client_secret,
      })
    },
    [createApiClient],
  )

  const openEdit = useCallback((client: ApiClientListItem): void => {
    setEditError(null)
    setEditingClient(client)
  }, [])
  const closeEdit = useCallback((): void => setEditingClient(null), [])

  const handleEditSubmit = useCallback(
    async (payload: UpdateApiClientPayload): Promise<void> => {
      setEditError(null)
      const result = await updateApiClient(payload)
      if ('error' in result) {
        setEditError(extractApiErrorDetail(result.error, '更新 API Client 失敗,請稍後再試'))
        return
      }
      setEditingClient(null)
    },
    [updateApiClient],
  )

  const handleToggleExpand = useCallback((uid: string): void => {
    setExpandedUid((prev) => (prev === uid ? null : uid))
  }, [])

  const handleRotate = useCallback(
    async (client: ApiClientListItem): Promise<void> => {
      setActionError(null)
      const result = await rotateApiClientSecret(client.uid)
      if ('error' in result) {
        setActionError(extractApiErrorDetail(result.error, '核發新密鑰失敗,請稍後再試'))
        return
      }
      setExpandedUid(client.uid)
      setRevealSecret({ clientId: client.client_id, secret: result.data.client_secret })
    },
    [rotateApiClientSecret],
  )

  const handleRequestRetire = useCallback(
    (client: ApiClientListItem, secret: ApiClientSecretItem): void => {
      setActionError(null)
      setRetireTarget({ client, secret })
    },
    [],
  )
  const cancelRetire = useCallback((): void => setRetireTarget(null), [])

  const handleConfirmRetire = useCallback(async (): Promise<void> => {
    if (retireTarget === null) return
    setActionError(null)
    const { client, secret } = retireTarget
    const result = await retireApiClientSecret({ uid: client.uid, secretUid: secret.uid })
    setRetireTarget(null)
    if ('error' in result) {
      setActionError(extractApiErrorDetail(result.error, '汰換密鑰失敗,請稍後再試'))
    }
  }, [retireTarget, retireApiClientSecret])

  const closeReveal = useCallback((): void => setRevealSecret(null), [])

  const items = useMemo((): ApiClientListItem[] => data?.items ?? [], [data])

  return (
    <section className="mx-auto flex max-w-7xl flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-foreground md:text-2xl">API Client 設定</h1>
          <p className="mt-1 text-sm text-muted-foreground md:text-base">
            管理可呼叫資料供應 API 的應用系統(admin 專用)
          </p>
        </div>
        <button type="button" onClick={openCreate} className="df-btn-primary">
          建立 API Client
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

      {isLoading ? (
        <p className="text-sm text-muted-foreground md:text-base">載入中…</p>
      ) : null}
      {isError ? (
        <p
          role="alert"
          className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger md:text-base"
        >
          載入 API Client 清單失敗,請稍後再試
        </p>
      ) : null}

      {data !== undefined ? (
        <>
          <div
            className={`df-card overflow-x-auto transition-opacity ${isFetching ? 'opacity-60' : ''}`}
          >
            <table className="df-table min-w-[960px]">
              <thead>
                <tr className="border-b border-border bg-muted/50">
                  <th className="df-th">名稱</th>
                  <th className="df-th">Client ID</th>
                  <th className="df-th">狀態</th>
                  <th className="df-th">每分鐘上限</th>
                  <th className="df-th">每 10 分鐘上限</th>
                  <th className="df-th">有效密鑰數</th>
                  <th className="df-th">建立時間</th>
                  <th className="df-th">操作</th>
                </tr>
              </thead>
              <tbody>
                {items.map((client) => (
                  <ApiClientRow
                    key={client.uid}
                    client={client}
                    expanded={expandedUid === client.uid}
                    rotating={isRotating}
                    retiringSecretUid={isRetiring ? (retireTarget?.secret.uid ?? null) : null}
                    onToggleExpand={handleToggleExpand}
                    onEdit={openEdit}
                    onRotate={handleRotate}
                    onRequestRetire={handleRequestRetire}
                  />
                ))}
              </tbody>
            </table>
            {items.length === 0 ? (
              <p className="px-3 py-8 text-center text-sm text-muted-foreground md:text-base">
                尚無 API Client
              </p>
            ) : null}
          </div>
          <Pagination
            page={data.page}
            pageSize={data.page_size}
            total={data.total}
            onPageChange={handlePageChange}
          />
        </>
      ) : null}

      <CreateClientDialog
        key={createOpen ? 'open' : 'closed'}
        open={createOpen}
        submitting={isCreating}
        submitError={createError}
        onSubmit={handleCreateSubmit}
        onCancel={closeCreate}
      />

      <EditClientDialog
        key={editingClient?.uid ?? 'closed'}
        client={editingClient}
        submitting={isUpdating}
        submitError={editError}
        onSubmit={handleEditSubmit}
        onCancel={closeEdit}
      />

      {revealSecret !== null ? (
        <SecretRevealPanel
          clientId={revealSecret.clientId}
          clientSecret={revealSecret.secret}
          onRequestClose={closeReveal}
        />
      ) : null}

      <ConfirmDialog
        open={retireTarget !== null}
        title="汰換密鑰"
        confirmLabel="確認汰換"
        tone="danger"
        confirmDisabled={isRetiring}
        onConfirm={handleConfirmRetire}
        onCancel={cancelRetire}
      >
        {retireTarget !== null ? (
          <p>
            確定要汰換「{retireTarget.client.name}」於{' '}
            {formatDateTime(retireTarget.secret.created_at)} 核發的密鑰?
          </p>
        ) : null}
        <p>汰換後該密鑰立即失效,持有該密鑰的呼叫端須改用其他有效密鑰。</p>
      </ConfirmDialog>
    </section>
  )
}
