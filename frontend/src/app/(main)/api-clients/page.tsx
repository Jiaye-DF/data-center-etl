'use client'

import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  useAssignClientRoleMutation,
  useBindClientExceptionSetMutation,
  useCreateApiClientMutation,
  useDeleteApiClientMutation,
  useGetEffectivePermissionsQuery,
  useListApiClientSecretsQuery,
  useListApiClientsQuery,
  useListClientExceptionSetsQuery,
  useRemoveClientRoleMutation,
  useRevealApiClientSecretMutation,
  useRotateApiClientSecretMutation,
  useUnbindClientExceptionSetMutation,
  useUpdateApiClientMutation,
  type ApiClientListItem,
  type ApiClientSecretItem,
  type ApiClientStatus,
  type ClientExceptionSetBinding,
  type CreateApiClientPayload,
  type EffectivePermissionAction,
  type UpdateApiClientPayload,
} from '@/lib/api/apiClientApi'
import {
  useListClientSettingRolesQuery,
  useListExceptionSetsQuery,
} from '@/lib/api/clientSettingApi'
import { ConfirmDialog } from '@/components/common/ConfirmDialog'
import { Pagination } from '@/components/common/Pagination'
import { extractApiErrorDetail } from '@/utils/apiError'
import { formatDateTime } from '@/utils/datetime'

const PAGE_SIZE = 20
const SECRET_MASK = '••••••••••••••••'

/** Credentials 風格共用樣式:值框(淡色圓角 + mono)與 icon 按鈕 */
const CODE_BOX_ID =
  'break-all rounded-lg bg-primary/10 px-2.5 py-1.5 font-mono text-sm text-primary'
const CODE_BOX_NEUTRAL =
  'break-all rounded-lg bg-muted px-2.5 py-1.5 font-mono text-sm text-foreground'
const ICON_BTN =
  'inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50'

/* ---------------------------------------------------------------------- */
/* Icons(inline SVG,無外部依賴)                                          */
/* ---------------------------------------------------------------------- */

interface IconProps {
  className?: string
}

function CopyIcon({ className = 'h-4 w-4' }: IconProps): React.ReactNode {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      <rect x="9" y="9" width="13" height="13" rx="2" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </svg>
  )
}

function CheckIcon({ className = 'h-4 w-4' }: IconProps): React.ReactNode {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      <path d="M20 6 9 17l-5-5" />
    </svg>
  )
}

function XIcon({ className = 'h-4 w-4' }: IconProps): React.ReactNode {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      <path d="M18 6 6 18M6 6l12 12" />
    </svg>
  )
}

function EyeIcon({ className = 'h-4 w-4' }: IconProps): React.ReactNode {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  )
}

function EyeOffIcon({ className = 'h-4 w-4' }: IconProps): React.ReactNode {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      <path d="M10.7 5.1A10.9 10.9 0 0 1 12 5c6.5 0 10 7 10 7a17.6 17.6 0 0 1-2.2 3.1M6.6 6.6C3.7 8.5 2 12 2 12s3.5 7 10 7c1.6 0 3-.4 4.3-1M3 3l18 18" />
      <path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" />
    </svg>
  )
}

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
      aria-label={COPY_LABEL[copyResult]}
      title={COPY_LABEL[copyResult]}
      className={`${ICON_BTN} ${
        copyResult === 'copied' ? 'text-success' : copyResult === 'failed' ? 'text-danger' : ''
      }`}
    >
      {copyResult === 'copied' ? (
        <CheckIcon />
      ) : copyResult === 'failed' ? (
        <XIcon />
      ) : (
        <CopyIcon />
      )}
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
      <div className="flex flex-nowrap items-center gap-1.5">
        {plainSecret === null ? (
          <>
            <span className="select-none font-mono text-sm tracking-widest text-muted-foreground">
              {SECRET_MASK}
            </span>
            <button
              type="button"
              onClick={handleRevealClick}
              disabled={isLoading}
              aria-label="顯示密鑰明文"
              title={isLoading ? '讀取中…' : '顯示'}
              className={ICON_BTN}
            >
              <EyeIcon />
            </button>
          </>
        ) : (
          <>
            <code className={CODE_BOX_NEUTRAL}>{plainSecret}</code>
            <CopyButton value={plainSecret} />
            <button
              type="button"
              onClick={handleMask}
              aria-label="遮蔽密鑰"
              title="遮蔽"
              className={ICON_BTN}
            >
              <EyeOffIcon />
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
          關閉後仍可在清單「Credentials」欄重新檢視明文
        </p>
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-3">
            <span className="w-28 shrink-0 text-sm font-medium text-muted-foreground md:text-base">
              Client ID
            </span>
            <code className={`min-w-0 ${CODE_BOX_ID}`}>{clientId}</code>
            <CopyButton value={clientId} />
          </div>
          <div className="flex items-center gap-3">
            <span className="w-28 shrink-0 text-sm font-medium text-muted-foreground md:text-base">
              Client Secret
            </span>
            <code className={`min-w-0 ${CODE_BOX_NEUTRAL}`}>{clientSecret}</code>
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
        <p>關閉後可在清單「Credentials」欄重新檢視</p>
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
/* 權限面板(Role 指派 + 特例綁定 + 最終可見欄位頁內檢視;task-010)             */
/* ---------------------------------------------------------------------- */

const EFFECTIVE_ACTION_LABEL: Record<EffectivePermissionAction, string> = {
  read: '唯讀',
  edit: '可編輯',
}

const EFFECTIVE_ACTION_BADGE: Record<EffectivePermissionAction, string> = {
  read: 'df-badge bg-muted text-muted-foreground',
  edit: 'df-badge bg-primary/15 text-primary',
}

/** Role 指派區:下拉選取後二次確認才指派;已指派時顯示解除鈕(同樣走 ConfirmDialog)。 */
interface RoleAssignmentSectionProps {
  clientUid: string
  currentRoleUid: string | null
  /** 子層 ConfirmDialog 開闔上報,供外層權限對話框的 Esc 分流 */
  onNestedDialogChange: (open: boolean) => void
}

function RoleAssignmentSection({
  clientUid,
  currentRoleUid,
  onNestedDialogChange,
}: RoleAssignmentSectionProps): React.ReactNode {
  const {
    data: roleData,
    isLoading: isLoadingRoles,
    isError: isRolesError,
  } = useListClientSettingRolesQuery()
  const [assignClientRole, { isLoading: isAssigning }] = useAssignClientRoleMutation()
  const [removeClientRole, { isLoading: isRemoving }] = useRemoveClientRoleMutation()
  const [assignError, setAssignError] = useState<string | null>(null)
  const [confirmingRemove, setConfirmingRemove] = useState(false)
  // 指派 = 把整組表 × 欄位授權放行給對外使用者,與「解除指派」同樣走二次確認
  const [pendingRoleUid, setPendingRoleUid] = useState<string | null>(null)

  const roles = useMemo(
    (): { uid: string; name: string }[] => roleData?.items ?? [],
    [roleData],
  )
  const pendingRoleName = useMemo(
    (): string =>
      roles.find((role) => role.uid === pendingRoleUid)?.name ?? '(未知 Role)',
    [roles, pendingRoleUid],
  )

  const nestedOpen = confirmingRemove || pendingRoleUid !== null
  useEffect(() => {
    onNestedDialogChange(nestedOpen)
    // 對話框關閉時本區塊隨之卸載,須歸零否則下次開啟會殘留「有子對話框」而擋掉 Esc
    return () => onNestedDialogChange(false)
  }, [nestedOpen, onNestedDialogChange])

  const handleRoleChange = useCallback(
    (event: React.ChangeEvent<HTMLSelectElement>): void => {
      const roleUid = event.target.value
      if (roleUid === '' || roleUid === currentRoleUid) return
      setAssignError(null)
      setPendingRoleUid(roleUid)
    },
    [currentRoleUid],
  )

  // 取消:清掉暫存選取,下拉即回到目前指派值(select 值由 currentRoleUid 決定)
  const cancelAssign = useCallback((): void => setPendingRoleUid(null), [])
  const handleConfirmAssign = useCallback(async (): Promise<void> => {
    if (pendingRoleUid === null) return
    const roleUid = pendingRoleUid
    setPendingRoleUid(null)
    setAssignError(null)
    const result = await assignClientRole({ clientUid, role_uid: roleUid })
    if ('error' in result) {
      setAssignError(extractApiErrorDetail(result.error, '指派 Role 失敗,請稍後再試'))
    }
  }, [assignClientRole, clientUid, pendingRoleUid])

  const openConfirmRemove = useCallback((): void => setConfirmingRemove(true), [])
  const cancelConfirmRemove = useCallback((): void => setConfirmingRemove(false), [])
  const handleConfirmRemove = useCallback(async (): Promise<void> => {
    setConfirmingRemove(false)
    setAssignError(null)
    const result = await removeClientRole(clientUid)
    if ('error' in result) {
      setAssignError(extractApiErrorDetail(result.error, '解除 Role 指派失敗,請稍後再試'))
    }
  }, [removeClientRole, clientUid])

  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-sm font-semibold text-foreground md:text-base">目前 Role</h3>
      <div className="flex flex-wrap items-center gap-2">
        <select
          value={pendingRoleUid ?? currentRoleUid ?? ''}
          onChange={handleRoleChange}
          disabled={isLoadingRoles || isAssigning || isRolesError}
          className="df-input w-auto min-w-[180px]"
        >
          <option value="" disabled>
            {currentRoleUid === null ? '未指派' : '請選擇'}
          </option>
          {roles.map((role) => (
            <option key={role.uid} value={role.uid}>
              {role.name}
            </option>
          ))}
        </select>
        {currentRoleUid !== null ? (
          <button
            type="button"
            onClick={openConfirmRemove}
            disabled={isRemoving}
            className="df-btn-danger-soft min-h-0 whitespace-nowrap rounded-full px-3 py-1 text-sm"
          >
            解除指派
          </button>
        ) : null}
      </div>
      {/* 讀不到 Role 清單 ≠ 沒有 Role:失敗時給故障訊息並停用下拉,不讓空選單誤導 */}
      {isRolesError ? (
        <p role="alert" className="text-sm text-danger">
          載入 Role 清單失敗,請稍後再試;指派功能暫不可用
        </p>
      ) : null}
      {assignError !== null ? (
        <p role="alert" className="text-sm text-danger">
          {assignError}
        </p>
      ) : null}
      <ConfirmDialog
        open={pendingRoleUid !== null}
        title="指派 Role"
        confirmLabel="確認指派"
        confirmDisabled={isAssigning}
        onConfirm={handleConfirmAssign}
        onCancel={cancelAssign}
      >
        <p>
          確定要指派 Role「<strong>{pendingRoleName}</strong>」?
        </p>
        <p>此使用者將<strong>立即取得</strong>該 Role 設定檔授予的可見欄位。</p>
      </ConfirmDialog>
      <ConfirmDialog
        open={confirmingRemove}
        title="解除 Role 指派"
        confirmLabel="確認解除"
        tone="danger"
        confirmDisabled={isRemoving}
        onConfirm={handleConfirmRemove}
        onCancel={cancelConfirmRemove}
      >
        <p>確定要解除目前指派的 Role?</p>
        <p>解除後該使用者將失去此 Role 授予的可見欄位。</p>
      </ConfirmDialog>
    </div>
  )
}

/** 特例組綁定區:選組 + 選填效期綁定;清單顯示過期標示與解除。 */
interface ExceptionSetSectionProps {
  clientUid: string
  /** 子層 ConfirmDialog 開闔上報,供外層權限對話框的 Esc 分流 */
  onNestedDialogChange: (open: boolean) => void
}

function ExceptionSetSection({
  clientUid,
  onNestedDialogChange,
}: ExceptionSetSectionProps): React.ReactNode {
  const {
    data: bindingData,
    isLoading: isLoadingBindings,
    isError: isBindingsError,
  } = useListClientExceptionSetsQuery(clientUid)
  const {
    data: setData,
    isLoading: isLoadingSets,
    isError: isSetsError,
  } = useListExceptionSetsQuery()
  const [bindClientExceptionSet, { isLoading: isBinding }] = useBindClientExceptionSetMutation()
  const [unbindClientExceptionSet, { isLoading: isUnbinding }] =
    useUnbindClientExceptionSetMutation()

  const [exceptionSetUid, setExceptionSetUid] = useState('')
  const [expiresAtLocal, setExpiresAtLocal] = useState('')
  const [bindError, setBindError] = useState<string | null>(null)
  const [unbindError, setUnbindError] = useState<string | null>(null)
  const [unbindTarget, setUnbindTarget] = useState<ClientExceptionSetBinding | null>(null)

  const bindings = useMemo(
    (): ClientExceptionSetBinding[] => bindingData?.items ?? [],
    [bindingData],
  )

  // 排除目前已生效綁定,避免選了就直接撞後端 409(過期綁定可再重綁,不排除)
  const availableSets = useMemo((): { uid: string; name: string }[] => {
    const activeBoundUids = new Set(
      bindings.filter((binding) => !binding.is_expired).map((binding) => binding.exception_set_uid),
    )
    return (setData?.items ?? []).filter((set) => !activeBoundUids.has(set.uid))
  }, [setData, bindings])

  const handleSetChange = useCallback(
    (event: React.ChangeEvent<HTMLSelectElement>): void => setExceptionSetUid(event.target.value),
    [],
  )
  const handleExpiresAtChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>): void =>
      setExpiresAtLocal(event.target.value),
    [],
  )

  const handleBindSubmit = useCallback(
    async (event: React.FormEvent<HTMLFormElement>): Promise<void> => {
      event.preventDefault()
      if (exceptionSetUid === '') return
      setBindError(null)
      // datetime-local 只給到分鐘,補秒對齊後端 `YYYY-MM-DDTHH:mm:ss`(台北 wall-clock,不轉 UTC)
      const result = await bindClientExceptionSet({
        clientUid,
        exception_set_uid: exceptionSetUid,
        expires_at: expiresAtLocal === '' ? undefined : `${expiresAtLocal}:00`,
      })
      if ('error' in result) {
        setBindError(extractApiErrorDetail(result.error, '綁定特例權限組失敗,請稍後再試'))
        return
      }
      setExceptionSetUid('')
      setExpiresAtLocal('')
    },
    [bindClientExceptionSet, clientUid, exceptionSetUid, expiresAtLocal],
  )

  useEffect(() => {
    onNestedDialogChange(unbindTarget !== null)
    return () => onNestedDialogChange(false)
  }, [unbindTarget, onNestedDialogChange])

  const requestUnbind = useCallback((binding: ClientExceptionSetBinding): void => {
    setUnbindError(null)
    setUnbindTarget(binding)
  }, [])
  const cancelUnbind = useCallback((): void => setUnbindTarget(null), [])
  const handleConfirmUnbind = useCallback(async (): Promise<void> => {
    if (unbindTarget === null) return
    const target = unbindTarget
    setUnbindTarget(null)
    const result = await unbindClientExceptionSet({ clientUid, bindingUid: target.uid })
    if ('error' in result) {
      setUnbindError(extractApiErrorDetail(result.error, '解除特例綁定失敗,請稍後再試'))
    }
  }, [unbindClientExceptionSet, clientUid, unbindTarget])

  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-sm font-semibold text-foreground md:text-base">特例權限組綁定</h3>
      <form onSubmit={handleBindSubmit} className="flex flex-wrap items-end gap-2">
        <label className="flex flex-col gap-1 text-xs font-medium text-muted-foreground">
          特例權限組
          <select
            value={exceptionSetUid}
            onChange={handleSetChange}
            disabled={isLoadingSets || isSetsError}
            className="df-input w-auto min-w-[180px]"
          >
            <option value="">請選擇</option>
            {availableSets.map((set) => (
              <option key={set.uid} value={set.uid}>
                {set.name}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-muted-foreground">
          效期(選填,不設限留空)
          <input
            type="datetime-local"
            value={expiresAtLocal}
            onChange={handleExpiresAtChange}
            className="df-input w-auto"
          />
        </label>
        <button
          type="submit"
          disabled={isBinding || exceptionSetUid === ''}
          className="df-btn-primary min-h-0 rounded-full px-4 py-1.5 text-sm"
        >
          綁定
        </button>
      </form>
      {/* 讀不到特例組清單 ≠ 沒有特例組:失敗時給故障訊息並停用下拉 */}
      {isSetsError ? (
        <p role="alert" className="text-sm text-danger">
          載入特例權限組清單失敗,請稍後再試;綁定功能暫不可用
        </p>
      ) : null}
      {bindError !== null ? (
        <p role="alert" className="text-sm text-danger">
          {bindError}
        </p>
      ) : null}
      {unbindError !== null ? (
        <p role="alert" className="text-sm text-danger">
          {unbindError}
        </p>
      ) : null}
      {isLoadingBindings ? (
        <p className="text-sm text-muted-foreground">載入中…</p>
      ) : isBindingsError || bindingData === undefined ? (
        // 「讀不到」不可退化成「尚無綁定」:admin 會誤判特例權限已被清空
        <p role="alert" className="text-sm text-danger">
          載入已綁定特例權限組失敗,請稍後再試
        </p>
      ) : bindings.length === 0 ? (
        <p className="text-sm text-muted-foreground">尚無綁定的特例權限組</p>
      ) : (
        <ul className="flex flex-col gap-1.5">
          {bindings.map((binding) => (
            <li
              key={binding.uid}
              className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-muted/50 px-3 py-2"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-medium text-foreground">
                  {binding.exception_set_name}
                </span>
                <span className="text-sm text-muted-foreground">
                  效期:{formatDateTime(binding.expires_at)}
                </span>
                {binding.is_expired ? (
                  <span className="df-badge bg-danger/10 text-danger">已過期</span>
                ) : null}
              </div>
              <button
                type="button"
                onClick={() => requestUnbind(binding)}
                disabled={isUnbinding}
                className="df-btn-danger-soft min-h-0 whitespace-nowrap rounded-full px-3 py-1 text-sm"
              >
                解除
              </button>
            </li>
          ))}
        </ul>
      )}
      <ConfirmDialog
        open={unbindTarget !== null}
        title="解除特例綁定"
        confirmLabel="確認解除"
        tone="danger"
        confirmDisabled={isUnbinding}
        onConfirm={handleConfirmUnbind}
        onCancel={cancelUnbind}
      >
        {unbindTarget !== null ? (
          <p>確定要解除「{unbindTarget.exception_set_name}」的綁定?</p>
        ) : null}
        <p>如需續期,解除後可重新綁定並設定新效期。</p>
      </ConfirmDialog>
    </div>
  )
}

/** 最終可見欄位頁內檢視:`{作業: {表: {欄位: read/edit}}}` 分組呈現;空結構顯示 default-closed 提示。 */
interface EffectivePermissionPreviewProps {
  clientUid: string
}

function EffectivePermissionPreview({
  clientUid,
}: EffectivePermissionPreviewProps): React.ReactNode {
  const { data, isLoading, isError } = useGetEffectivePermissionsQuery(clientUid)

  if (isLoading) {
    return <p className="text-sm text-muted-foreground">載入中…</p>
  }
  if (isError || data === undefined) {
    return (
      <p role="alert" className="text-sm text-danger">
        載入最終可見欄位失敗,請稍後再試
      </p>
    )
  }
  if (data.operations.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        尚未指派任何權限(無 Role 或有效特例),無可見欄位
      </p>
    )
  }

  return (
    <div className="flex flex-col gap-2.5">
      {data.operations.map((operation) => {
        const tableEntries = Object.entries(operation.tables)
        return (
          <div key={operation.operation_uid} className="rounded-lg border border-border p-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="df-badge bg-muted text-muted-foreground">
                {operation.service_code}
              </span>
              <span className="text-sm font-medium text-foreground md:text-base">
                {operation.operation_name}
              </span>
            </div>
            {tableEntries.length === 0 ? (
              <p className="mt-2 text-sm text-muted-foreground">
                此作業無可見欄位(default-closed)
              </p>
            ) : (
              <div className="mt-2 flex flex-col gap-1.5">
                {tableEntries.map(([tableName, columns]) => (
                  <div key={tableName} className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
                    <span className="w-32 shrink-0 text-sm font-medium text-foreground">
                      {tableName}
                    </span>
                    <div className="flex flex-wrap gap-1.5">
                      {Object.entries(columns).map(([columnName, action]) => (
                        <span
                          key={columnName}
                          className={EFFECTIVE_ACTION_BADGE[action]}
                          title={EFFECTIVE_ACTION_LABEL[action]}
                        >
                          {columnName === '*' ? '全部欄位' : columnName}
                          <span className="ml-1 text-[0.7em] opacity-80">
                            {EFFECTIVE_ACTION_LABEL[action]}
                          </span>
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

interface ClientPermissionDialogProps {
  client: ApiClientListItem | null
  onClose: () => void
}

function ClientPermissionDialog({
  client,
  onClose,
}: ClientPermissionDialogProps): React.ReactNode {
  // 子層 ConfirmDialog 也監聽 Esc:未分流時一次 Esc 會連本對話框一起關,
  // 連帶清掉已選特例組與已填效期(AD-142 同型)
  const [roleNestedOpen, setRoleNestedOpen] = useState(false)
  const [exceptionNestedOpen, setExceptionNestedOpen] = useState(false)
  const hasNestedDialog = roleNestedOpen || exceptionNestedOpen

  useEffect(() => {
    if (client === null) return
    const onKey = (event: KeyboardEvent): void => {
      if (event.key === 'Escape' && !hasNestedDialog) onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [client, onClose, hasNestedDialog])

  // effective-permissions 提供目前 Role 摘要,免另開一支查詢
  const { data: effectiveData } = useGetEffectivePermissionsQuery(client?.uid ?? '', {
    skip: client === null,
  })

  if (client === null) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        aria-label="關閉對話框"
        onClick={onClose}
        className="absolute inset-0 cursor-default bg-black/40"
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="client-permission-dialog-title"
        className="df-card relative z-10 flex max-h-[90vh] w-full max-w-3xl flex-col gap-5 overflow-y-auto p-6 md:p-8"
      >
        <div className="flex items-start justify-between gap-3">
          <h2
            id="client-permission-dialog-title"
            className="text-lg font-bold text-foreground md:text-xl"
          >
            權限管理:{client.name}
          </h2>
          <button type="button" onClick={onClose} className="df-btn-outline min-h-0 px-3 py-1.5">
            關閉
          </button>
        </div>

        <RoleAssignmentSection
          clientUid={client.uid}
          currentRoleUid={effectiveData?.role?.uid ?? null}
          onNestedDialogChange={setRoleNestedOpen}
        />

        <hr className="border-border" />

        <ExceptionSetSection
          clientUid={client.uid}
          onNestedDialogChange={setExceptionNestedOpen}
        />

        <hr className="border-border" />

        <div className="flex flex-col gap-2">
          <h3 className="text-sm font-semibold text-foreground md:text-base">
            最終可見欄位(檢視)
          </h3>
          <EffectivePermissionPreview clientUid={client.uid} />
        </div>
      </div>
    </div>
  )
}

/* ---------------------------------------------------------------------- */
/* 清單列                                                                   */
/* ---------------------------------------------------------------------- */

interface ApiClientRowProps {
  client: ApiClientListItem
  rotating: boolean
  deleting: boolean
  onEdit: (client: ApiClientListItem) => void
  onRotate: (client: ApiClientListItem) => void
  onDelete: (client: ApiClientListItem) => void
  onViewPermissions: (client: ApiClientListItem) => void
}

const ApiClientRow = memo(function ApiClientRow({
  client,
  rotating,
  deleting,
  onEdit,
  onRotate,
  onDelete,
  onViewPermissions,
}: ApiClientRowProps): React.ReactNode {
  const handleEdit = useCallback((): void => onEdit(client), [onEdit, client])
  const handleRotate = useCallback((): void => onRotate(client), [onRotate, client])
  const handleDelete = useCallback((): void => onDelete(client), [onDelete, client])
  const handleViewPermissions = useCallback(
    (): void => onViewPermissions(client),
    [onViewPermissions, client],
  )

  return (
    <tr className="border-b border-border transition-colors last:border-b-0 hover:bg-muted/50">
      <td className="px-3 py-3">
        <div className="flex flex-col gap-1.5">
          <button
            type="button"
            onClick={handleEdit}
            className="df-btn-outline min-h-0 whitespace-nowrap rounded-full px-3 py-1 text-sm"
          >
            編輯
          </button>
          <button
            type="button"
            onClick={handleViewPermissions}
            className="df-btn-outline min-h-0 whitespace-nowrap rounded-full px-3 py-1 text-sm"
          >
            權限
          </button>
          <button
            type="button"
            onClick={handleRotate}
            disabled={rotating}
            className="df-btn-outline min-h-0 whitespace-nowrap rounded-full px-3 py-1 text-sm"
          >
            輪替密鑰
          </button>
          <button
            type="button"
            onClick={handleDelete}
            disabled={deleting}
            className="df-btn-danger-soft min-h-0 whitespace-nowrap rounded-full px-3 py-1 text-sm"
          >
            註銷
          </button>
        </div>
      </td>
      <td className="whitespace-nowrap px-3 py-3 text-sm font-medium text-foreground md:text-base">
        {client.name}
      </td>
      <td className="whitespace-nowrap px-3 py-3">
        <div className="flex flex-col gap-1.5">
          <div className="flex flex-nowrap items-center gap-1.5">
            <span className="w-16 shrink-0 text-xs font-medium text-muted-foreground">
              Client ID
            </span>
            <code className={CODE_BOX_ID}>{client.client_id}</code>
            <CopyButton value={client.client_id} />
          </div>
          <div className="flex flex-nowrap items-center gap-1.5">
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
  const [deleteTarget, setDeleteTarget] = useState<ApiClientListItem | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [permissionClient, setPermissionClient] = useState<ApiClientListItem | null>(null)

  const { data, isLoading, isError, isFetching } = useListApiClientsQuery({
    page,
    pageSize: PAGE_SIZE,
  })
  const [createApiClient, { isLoading: isCreating, reset: resetCreate }] =
    useCreateApiClientMutation()
  const [updateApiClient, { isLoading: isUpdating }] = useUpdateApiClientMutation()
  const [rotateApiClientSecret, { isLoading: isRotating, reset: resetRotate }] =
    useRotateApiClientSecretMutation()
  const [deleteApiClient, { isLoading: isDeleting }] = useDeleteApiClientMutation()

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

  const openPermissions = useCallback((client: ApiClientListItem): void => {
    setPermissionClient(client)
  }, [])
  const closePermissions = useCallback((): void => setPermissionClient(null), [])

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

  const handleRequestDelete = useCallback((client: ApiClientListItem): void => {
    setActionError(null)
    setDeleteTarget(client)
  }, [])
  const cancelDelete = useCallback((): void => setDeleteTarget(null), [])

  const handleConfirmDelete = useCallback(async (): Promise<void> => {
    if (deleteTarget === null) return
    setActionError(null)
    const result = await deleteApiClient(deleteTarget.uid)
    setDeleteTarget(null)
    if ('error' in result) {
      setActionError(extractApiErrorDetail(result.error, '註銷使用者失敗,請稍後再試'))
    }
  }, [deleteTarget, deleteApiClient])

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
                  <th className="df-th">Credentials</th>
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
                    deleting={isDeleting}
                    onEdit={openEdit}
                    onRotate={handleRequestRotate}
                    onDelete={handleRequestDelete}
                    onViewPermissions={openPermissions}
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

      <ClientPermissionDialog
        key={permissionClient?.uid ?? 'closed'}
        client={permissionClient}
        onClose={closePermissions}
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

      <ConfirmDialog
        open={deleteTarget !== null}
        title="註銷使用者"
        confirmLabel="確認註銷"
        tone="danger"
        confirmDisabled={isDeleting}
        onConfirm={handleConfirmDelete}
        onCancel={cancelDelete}
      >
        {deleteTarget !== null ? (
          <p>確定要註銷「{deleteTarget.name}」?</p>
        ) : null}
        <p>
          註銷後該使用者將<strong>立即無法取得 token</strong>,密鑰全數撤銷
          <br />
          並自此清單移除,無法於介面復原
        </p>
      </ConfirmDialog>
    </section>
  )
}
