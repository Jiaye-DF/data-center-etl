'use client'

import { Suspense, useCallback, useEffect, useMemo, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { useLoginMutation } from '@/lib/api/authApi'
import { useAuth } from '@/lib/auth/useAuth'
import {
  buildSsoAuthorizeUrl,
  isSsoConfigured,
  setLastLoginProvider,
} from '@/lib/auth/sso'
import { extractApiErrorDetail } from '@/utils/apiError'

/** backend SSO callback(task-003)契約錯誤碼 → 顯示訊息 */
const ERROR_MESSAGES: Record<string, string> = {
  no_code: 'SSO 回呼缺少授權碼,請重新登入',
  exchange_error: 'SSO 中央暫時無法連線,請稍後再試',
  exchange_failed: 'SSO 登入失敗,請重新登入',
  session_expired: '登入已逾期,請重新登入',
  reauth_failed: '自動重新登入失敗,請重新登入',
}

/** 僅允許站內相對路徑,避免 open redirect */
function sanitizeNextPath(value: string | null): string {
  if (value !== null && value.startsWith('/') && !value.startsWith('//')) {
    return value
  }
  return '/'
}

function LoginContent(): React.ReactNode {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { isAuthenticated, isLoading: isAuthLoading } = useAuth()
  const [login, { isLoading: isLoggingIn, error: loginError }] = useLoginMutation()

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')

  const nextPath = useMemo(
    (): string => sanitizeNextPath(searchParams.get('next')),
    [searchParams],
  )
  const queryError = searchParams.get('error')
  const loggedOut = searchParams.get('logged_out') === '1'

  // 已登入者進登入頁 → 回後台(非 SSO authorize 自動跳轉,不違契約 #3)
  useEffect(() => {
    if (isAuthenticated) {
      router.replace(nextPath)
    }
  }, [isAuthenticated, nextPath, router])

  const handleUsernameChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>): void => {
      setUsername(event.target.value)
    },
    [],
  )

  const handlePasswordChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>): void => {
      setPassword(event.target.value)
    },
    [],
  )

  const handleSubmit = useCallback(
    async (event: React.FormEvent<HTMLFormElement>): Promise<void> => {
      event.preventDefault()
      const result = await login({ username, password })
      if ('data' in result && result.data !== undefined) {
        setLastLoginProvider(result.data.provider)
        router.replace(nextPath)
      }
    },
    [login, username, password, nextPath, router],
  )

  // 契約 #3(嚴格模式):登入頁 401 只顯示按鈕,禁自動 redirect 到 /authorize
  const ssoConfigured = isSsoConfigured()
  const handleSsoLogin = useCallback((): void => {
    window.location.assign(buildSsoAuthorizeUrl())
  }, [])

  const errorMessage = useMemo((): string | null => {
    if (loginError !== undefined) {
      return extractApiErrorDetail(loginError, '登入失敗,請稍後再試')
    }
    if (queryError !== null) {
      return ERROR_MESSAGES[queryError] ?? 'SSO 登入發生錯誤,請重新登入'
    }
    return null
  }, [loginError, queryError])

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="df-card w-full max-w-md p-6 md:p-8">
        <div className="flex items-center gap-3">
          <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary text-primary-foreground">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <ellipse cx="8" cy="6" rx="5" ry="2.2" />
              <path d="M3 6v5c0 1.2 2.24 2.2 5 2.2s5-1 5-2.2V6" />
              <path d="M3 11v5c0 1.2 2.24 2.2 5 2.2" />
              <path d="M15 13h6m0 0-2.5-2.5M21 13l-2.5 2.5" />
            </svg>
          </span>
          <div>
            <h1 className="text-xl font-bold text-foreground md:text-2xl">
              ETL 管理後台
            </h1>
            <p className="text-sm text-muted-foreground md:text-base">
              請登入以繼續
            </p>
          </div>
        </div>

        {loggedOut ? (
          <p className="mt-6 rounded-lg bg-muted px-3 py-2 text-sm text-muted-foreground md:text-base">
            已登出
          </p>
        ) : null}
        {errorMessage !== null ? (
          <p
            role="alert"
            className="mt-6 rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger md:text-base"
          >
            {errorMessage}
          </p>
        ) : null}

        <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4">
          <label className="flex flex-col gap-1.5">
            <span className="text-sm font-medium text-foreground md:text-base">
              帳號
            </span>
            <input
              type="text"
              name="username"
              autoComplete="username"
              required
              value={username}
              onChange={handleUsernameChange}
              className="df-input"
            />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-sm font-medium text-foreground md:text-base">
              密碼
            </span>
            <input
              type="password"
              name="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={handlePasswordChange}
              className="df-input"
            />
          </label>
          <button
            type="submit"
            disabled={isLoggingIn || isAuthLoading}
            className="df-btn-primary mt-1"
          >
            {isLoggingIn ? '登入中…' : '登入'}
          </button>
        </form>

        {ssoConfigured ? (
          <>
            <div className="mt-6 flex items-center gap-3">
              <span className="h-px flex-1 bg-border" />
              <span className="text-sm text-muted-foreground md:text-base">
                或
              </span>
              <span className="h-px flex-1 bg-border" />
            </div>

            <button
              type="button"
              onClick={handleSsoLogin}
              className="df-btn-outline mt-4 w-full"
            >
              透過 DF-SSO 登入
            </button>
          </>
        ) : null}
      </div>
    </main>
  )
}

// useSearchParams 必包 Suspense(production build 硬性要求)
export default function LoginPage(): React.ReactNode {
  return (
    <Suspense
      fallback={
        <main className="flex min-h-screen items-center justify-center bg-background">
          <p className="text-sm text-muted-foreground md:text-base">載入中…</p>
        </main>
      }
    >
      <LoginContent />
    </Suspense>
  )
}
