'use client'

import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  useCreateApiClientMutation,
  useListApiClientSecretsQuery,
  useListApiClientsQuery,
  useRevealApiClientSecretMutation,
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
const SECRET_MASK = '••••••••'

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

type CopyResult = 'idle' | 'copied' | 'failed'

const COPY_LABEL: Record<CopyResult, string> = {
  idle: '複製',
  copied: '已複製',
  failed: '複製失敗',
}

const CopyButton = memo(function CopyButton({ value }: CopyButtonProps): React.ReactNode {
  const [copyResult, setCopyResult] = useState<CopyResult>('idle')
  const resetTimerRef = useRef<number | null>(null)

  useEffect(() => {
    return () => {
      if (resetTimerRef.current !== null) window.clearTimeout(resetTimerRef.current)
    }
  }, [])

  const showResult = useCallback((result: CopyResult): void => {
    setCopyResult(result)
    if (resetTimerRef.current !== null) window.clearTimeout(resetTimerRef.current)
    resetTimerRef.current = window.setTimeout(() => setCopyResult('idle'), 1500)
  }, [])

  const handleCopy = useCallback((): void => {
    // 非 secure context(如 http 內網)沒有 clipboard API,直接顯示失敗
    if (navigator.clipboard === undefined) {
      showResult('failed')
      return
    }
    navigator.clipboard
      .writeText(value)
      .then(() => showResult('copied'))
      .catch(() => showResult('failed'))
  }, [value, showResult])

  return (
    <button
      type="button"
      onClick={handleCopy}
      className="df-btn-outline min-h-0 shrink-0 px-2 py-1 text-sm"
    >
      {COPY_LABEL[copyResult]}
    </button>
  )
})

/* ---------------------------------------------------------------------- */
/* 密鑰明文檢視(遮罩 → reveal → 可再遮回;明文只留元件 state)                */
/* ---------------------------------------------------------------------- */

interface SecretRevealControlProps {
  clientUid: string
  secret: ApiClientSecretItem
}

const SecretRevealControl = memo(function SecretRevealControl({
  clientUid,
  secret,
}: SecretRevealControlProps): React.ReactNode {
  const [plainSecret, setPlainSecret] = useState<string | null>(null)
  const [revealError, setRevealError] = useState<string | null>(null)
  const [revealApiClientSecret, { isLoading, reset }] = useRevealApiClientSecretMutation()

  const handleReveal = useCallback(async (): Promise<void> => {
    setRevealError(null)
    const result = await revealApiClientSecret({ uid: clientUid, secretUid: secret.uid })
    // 明文只留在本元件 state:讀完立刻清掉 mutation 結果,避免長駐 redux store
    reset()
    if ('error' in result) {
      setRevealError(extractApiErrorDetail(result.error, '檢視密鑰明文失敗,請稍後再試'))
      return
    }
    setPlainSecret(result.data.client_secret)
  }, [revealApiClientSecret, reset, clientUid, secret.uid])

  const handleRevealClick = useCallback((): void => {
    void handleReveal()
  }, [handleReveal])

  const handleMask = useCallback((): void => {
    setPlainSecret(null)
    setRevealError(null)
  }, [])

  if (!secret.revealable) {
    return (
      <span className="text-sm text-muted-foreground md:text-base">
        舊密鑰,輪替後可檢視
      </span>
    )
  }

  return (
    <div className="flex flex-col gap-1">
      <div className="flex flex-nowrap items-center gap-2">
        <code className="font-mono text-sm text-foreground md:text-base">
          {plainSecret ?? SECRET_MASK}
        </code>
        {plainSecret === null ? (
          <button
            type="button"
            onClick={handleRevealClick}
            disabled={isLoading}
            className="df-btn-outline min-h-0 shrink-0 px-2 py-1 text-sm"
          >
            {isLoading ? '讀取中…' : '顯示'}
          </button>
        ) : (
          <>
            <CopyButton value={plainSecret} />
            <button
              type="button"
              onClick={handleMask}
              className="df-btn-outline min-h-0 shrink-0 px-2 py-1 text-sm"
            >
              遮蔽
            </button>
          </>
        )}
      </div>
      {revealError !== null ? (
        <span role="alert" className="text-sm text-danger">
          {revealError}
        </span>
      ) : null}
    </div>
  )
})

interface LatestSecretCellProps {
  client: ApiClientListItem
}

/** 表格 Secret 欄:取該使用者最新一把 active 密鑰(清單依核發時間升冪)。 */
const LatestSecretCell = memo(function LatestSecretCell({
  client,
}: LatestSecretCellProps): React.ReactNode {
  const { data, isLoading, isError } = useListApiClientSecretsQuery(client.uid)

  const latestActive = useMemo((): ApiClientSecretItem | null => {
    const actives = (data?.items ?? []).filter((item) => item.status === 'active')
    return actives.length === 0 ? null : (actives[actives.length - 1] ?? null)
  }, [data])

  if (isLoading) {
    return <span className="text-sm text-muted-foreground md:text-base">載入中…</span>
  }
  if (isError) {
    return (
      <span role="alert" className="text-sm text-danger md:text-base">
        載入失敗
      </span>
    )
  }
  if (latestActive === null) {
    return <span className="text-sm text-muted-foreground md:text-base">無有效密鑰</span>
  }
  // key 綁密鑰 uid:輪替換代時重掛元件,回到遮罩態並清掉殘留的舊密鑰明文 state
  return <SecretRevealControl key={latestActive.uid} clientUid={client.uid} secret={latestActive} />
})

/* ---------------------------------------------------------------------- */
/* 核發完成面板(建立 / 輪替共用;明文即時顯示,關閉後仍可於表格檢視)          */
/* ---------------------------------------------------------------------- */

interface IssuedSecretPanelProps {
  clientId: string
  clientSecret: string
  onRequestClose: () => void
}

function IssuedSecretPanel({
  clientId,
  clientSecret,
  onRequestClose,
}: IssuedSecretPanelProps): React.ReactNode {
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
        aria-labelledby="issued-secret-title"
        className="df-card relative z-10 flex w-full max-w-xl flex-col gap-4 p-6 md:p-8"
      >
        <h2 id="issued-secret-title" className="text-lg font-bold text-foreground md:text-xl">
          密鑰核發成功
        </h2>
        <p className="rounded-lg bg-warning/15 px-3 py-2 text-sm text-warning md:text-base">
          請立即複製並交付該使用者
          <br />
          關閉後仍可在清單「ClientID-Secret」欄重新檢視明文
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
        <p>請確認已複製此密鑰明文</p>
        <p>關閉後可在清單「ClientID-Secret」欄重新檢視</p>
      </ConfirmDialog>
    </div>
  )
}

/* ---------------------------------------------------------------------- */
/* 建立使用者對話框                                                          */
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
          建立使用者 API 憑證
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
          使用者名稱
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

/** 解析流量上限輸入:僅接受正整數,其餘(空值 / 非數字 / 0)回 null。 */
function parseRateLimit(raw: string): number | null {
  if (!/^\d+$/.test(raw)) return null
  const value = Number(raw)
  return value >= 1 ? value : null
}

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
  // 以字串保存輸入,避免打字途中被強制轉成 1(空值 / 非法值於提交時驗證)
  const [rateLimitPerMinute, setRateLimitPerMinute] = useState(
    String(client?.rate_limit_per_minute ?? 1),
  )
  const [rateLimitPer10Min, setRateLimitPer10Min] = useState(
    String(client?.rate_limit_per_10min ?? 1),
  )
  const [rateLimitError, setRateLimitError] = useState<string | null>(null)
  const [enabled, setEnabled] = useState(client?.status === 'enabled')
  const [confirmingDisable, setConfirmingDisable] = useState(false)

  useEffect(() => {
    if (client === null) return
    const onKey = (event: KeyboardEvent): void => {
      // 停用二次確認開啟時,Esc 只該關閉 ConfirmDialog,不連鎖關閉編輯對話框
      if (event.key === 'Escape' && !confirmingDisable) onCancel()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [client, onCancel, confirmingDisable])

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
      setRateLimitPerMinute(event.target.value.replace(/\D/g, ''))
      setRateLimitError(null)
    },
    [],
  )
  const handleRate10MinChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>): void => {
      setRateLimitPer10Min(event.target.value.replace(/\D/g, ''))
      setRateLimitError(null)
    },
    [],
  )
  const handleEnabledChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>): void => setEnabled(event.target.checked),
    [],
  )

  const buildPayload = useCallback(
    (statusOverride?: ApiClientStatus): UpdateApiClientPayload | null => {
      if (client === null) throw new Error('client is null')
      const perMinute = parseRateLimit(rateLimitPerMinute)
      const per10Min = parseRateLimit(rateLimitPer10Min)
      if (perMinute === null || per10Min === null) return null
      return {
        uid: client.uid,
        name: name.trim(),
        description: description.trim() === '' ? null : description.trim(),
        status: statusOverride ?? (enabled ? 'enabled' : 'disabled'),
        rate_limit_per_minute: perMinute,
        rate_limit_per_10min: per10Min,
      }
    },
    [client, name, description, enabled, rateLimitPerMinute, rateLimitPer10Min],
  )

  const handleSubmit = useCallback(
    (event: React.FormEvent<HTMLFormElement>): void => {
      event.preventDefault()
      if (client === null || name.trim() === '') return
      const payload = buildPayload()
      if (payload === null) {
        setRateLimitError('流量上限須為正整數,不可空白')
        return
      }
      setRateLimitError(null)
      const turningOff = client.status === 'enabled' && !enabled
      if (turningOff) {
        setConfirmingDisable(true)
        return
      }
      onSubmit(payload)
    },
    [client, name, enabled, buildPayload, onSubmit],
  )

  const handleConfirmDisable = useCallback((): void => {
    setConfirmingDisable(false)
    const payload = buildPayload('disabled')
    if (payload === null) {
      setRateLimitError('流量上限須為正整數,不可空白')
      return
    }
    onSubmit(payload)
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
            編輯使用者 API 憑證:{client.name}
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
            使用者名稱
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
          {rateLimitError !== null ? (
            <span role="alert" className="text-sm text-danger">
              {rateLimitError}
            </span>
          ) : null}
          <label className="flex items-center gap-2 text-sm font-medium text-foreground md:text-base">
            <input
              type="checkbox"
              checked={enabled}
              onChange={handleEnabledChange}
              className="h-5 w-5 accent-[rgb(var(--primary))]"
            />
            啟用此使用者(停用將立即無法取得 token)
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
        title="停用使用者"
        confirmLabel="確認停用"
        tone="danger"
        confirmDisabled={submitting}
        onConfirm={handleConfirmDisable}
        onCancel={handleCancelDisable}
      >
        <p>
          停用「{client.name}」後,該使用者將<strong>立即無法取得 token</strong>。
        </p>
        <p>請確認已通知該使用者再停用。</p>
      </ConfirmDialog>
    </>
  )
}

/* ---------------------------------------------------------------------- */
/* 清單列                                                                   */
/* ---------------------------------------------------------------------- */

interface ApiClientRowProps {
  client: ApiClientListItem
  rotating: boolean
  onEdit: (client: ApiClientListItem) => void
  onRotate: (client: ApiClientListItem) => void
}

const ApiClientRow = memo(function ApiClientRow({
  client,
  rotating,
  onEdit,
  onRotate,
}: ApiClientRowProps): React.ReactNode {
  const handleEdit = useCallback((): void => onEdit(client), [onEdit, client])
  const handleRotate = useCallback((): void => onRotate(client), [onRotate, client])

  return (
    <tr className="border-b border-border transition-colors last:border-b-0 hover:bg-muted/50">
      <td className="px-3 py-3">
        <div className="flex flex-nowrap gap-2">
          <button
            type="button"
            onClick={handleEdit}
            className="df-btn-outline min-h-0 shrink-0 whitespace-nowrap rounded-full px-3 py-1 text-sm"
          >
            編輯
          </button>
          <button
            type="button"
            onClick={handleRotate}
            disabled={rotating}
            className="df-btn-outline min-h-0 shrink-0 whitespace-nowrap rounded-full px-3 py-1 text-sm"
          >
            輪替密鑰
          </button>
        </div>
      </td>
      <td className="whitespace-nowrap px-3 py-3 text-sm font-medium text-foreground md:text-base">
        {client.name}
      </td>
      <td className="whitespace-nowrap px-3 py-3">
        <div className="flex flex-col gap-1.5">
          <div className="flex flex-nowrap items-center gap-2">
            <span className="w-16 shrink-0 text-xs font-medium text-muted-foreground">
              Client ID
            </span>
            <code className="text-sm font-mono text-muted-foreground md:text-base">
              {client.client_id}
            </code>
            <CopyButton value={client.client_id} />
          </div>
          <div className="flex flex-nowrap items-center gap-2">
            <span className="w-16 shrink-0 text-xs font-medium text-muted-foreground">
              Secret
            </span>
            <LatestSecretCell client={client} />
          </div>
        </div>
      </td>
      <td className="df-td">
        <ApiClientStatusBadge status={client.status} />
      </td>
      <td className="df-td whitespace-nowrap">
        <div className="flex flex-col gap-0.5">
          <span>{client.rate_limit_per_minute} 次 / 分</span>
          <span>{client.rate_limit_per_10min} 次 / 10 分</span>
        </div>
      </td>
      <td className="df-td text-muted-foreground">{formatDateTime(client.created_at)}</td>
    </tr>
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
  const [issuedSecret, setIssuedSecret] = useState<{
    clientId: string
    secret: string
  } | null>(null)
  const [rotateTarget, setRotateTarget] = useState<ApiClientListItem | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const { data, isLoading, isError, isFetching } = useListApiClientsQuery({
    page,
    pageSize: PAGE_SIZE,
  })
  const [createApiClient, { isLoading: isCreating, reset: resetCreate }] =
    useCreateApiClientMutation()
  const [updateApiClient, { isLoading: isUpdating }] = useUpdateApiClientMutation()
  const [rotateApiClientSecret, { isLoading: isRotating, reset: resetRotate }] =
    useRotateApiClientSecretMutation()

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
      // 明文只交給元件 state:讀完立刻清掉 mutation 結果,避免長駐 redux store
      resetCreate()
      if ('error' in result) {
        setCreateError(
          extractApiErrorDetail(result.error, '建立使用者 API 憑證失敗,請稍後再試'),
        )
        return
      }
      setCreateOpen(false)
      setIssuedSecret({
        clientId: result.data.client.client_id,
        secret: result.data.client_secret,
      })
    },
    [createApiClient, resetCreate],
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
        setEditError(
          extractApiErrorDetail(result.error, '更新使用者 API 憑證失敗,請稍後再試'),
        )
        return
      }
      setEditingClient(null)
    },
    [updateApiClient],
  )

  const handleRequestRotate = useCallback((client: ApiClientListItem): void => {
    setActionError(null)
    setRotateTarget(client)
  }, [])
  const cancelRotate = useCallback((): void => setRotateTarget(null), [])

  const handleConfirmRotate = useCallback(async (): Promise<void> => {
    if (rotateTarget === null) return
    setActionError(null)
    const target = rotateTarget
    const result = await rotateApiClientSecret(target.uid)
    // 明文只交給元件 state:讀完立刻清掉 mutation 結果,避免長駐 redux store
    resetRotate()
    setRotateTarget(null)
    if ('error' in result) {
      setActionError(extractApiErrorDetail(result.error, '輪替密鑰失敗,請稍後再試'))
      return
    }
    setIssuedSecret({ clientId: target.client_id, secret: result.data.client_secret })
  }, [rotateTarget, rotateApiClientSecret, resetRotate])

  const closeIssued = useCallback((): void => setIssuedSecret(null), [])

  const items = useMemo((): ApiClientListItem[] => data?.items ?? [], [data])

  return (
    <section className="mx-auto flex max-w-7xl flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-foreground md:text-2xl">API Client 設定</h1>
          <p className="mt-1 text-sm text-muted-foreground md:text-base">
            管理使用者的 API 存取憑證
          </p>
        </div>
        <button type="button" onClick={openCreate} className="df-btn-primary">
          建立使用者 API 憑證
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
          載入使用者清單失敗,請稍後再試
        </p>
      ) : null}

      {data !== undefined ? (
        <>
          <div
            className={`df-card overflow-x-auto transition-opacity ${isFetching ? 'opacity-60' : ''}`}
          >
            <table className="df-table min-w-[1080px]">
              <thead>
                <tr className="border-b border-border bg-muted/50">
                  <th className="df-th">操作</th>
                  <th className="df-th">使用者</th>
                  <th className="df-th">ClientID-Secret</th>
                  <th className="df-th">狀態</th>
                  <th className="df-th">流量上限</th>
                  <th className="df-th">建立時間</th>
                </tr>
              </thead>
              <tbody>
                {items.map((client) => (
                  <ApiClientRow
                    key={client.uid}
                    client={client}
                    rotating={isRotating}
                    onEdit={openEdit}
                    onRotate={handleRequestRotate}
                  />
                ))}
              </tbody>
            </table>
            {items.length === 0 ? (
              <p className="px-3 py-8 text-center text-sm text-muted-foreground md:text-base">
                尚無使用者
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

      {issuedSecret !== null ? (
        <IssuedSecretPanel
          clientId={issuedSecret.clientId}
          clientSecret={issuedSecret.secret}
          onRequestClose={closeIssued}
        />
      ) : null}

      <ConfirmDialog
        open={rotateTarget !== null}
        title="輪替密鑰"
        confirmLabel="確認輪替"
        tone="danger"
        confirmDisabled={isRotating}
        onConfirm={handleConfirmRotate}
        onCancel={cancelRotate}
      >
        {rotateTarget !== null ? (
          <p>確定要為「{rotateTarget.name}」輪替密鑰?</p>
        ) : null}
        <p>
          輪替後將核發一把新密鑰,<strong>舊密鑰將立即失效</strong>
          ,使用中的系統須改用新密鑰。
        </p>
      </ConfirmDialog>
    </section>
  )
}
