'use client'

import { Suspense, useCallback, useEffect, useMemo, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { API_BASE_URL, useLoginMutation } from '@/lib/api/authApi'
import { useAuth } from '@/lib/auth/useAuth'

/** DF-SSO 中央登入器(可公開 env;機密 SSO_APP_SECRET 僅存在後端,禁入前端 bundle) */
const SSO_URL = process.env.NEXT_PUBLIC_SSO_URL ?? ''
const SSO_APP_ID = process.env.NEXT_PUBLIC_SSO_APP_ID ?? ''

/** backend SSO callback(task-003)契約錯誤碼 → 顯示訊息 */
const ERROR_MESSAGES: Record<string, string> = {
  no_code: 'SSO 回呼缺少授權碼,請重新登入',
  exchange_error: 'SSO 中央暫時無法連線,請稍後再試',
  exchange_failed: 'SSO 登入失敗,請重新登入',
  session_expired: '登入已逾期,請重新登入',
  reauth_failed: '自動重新登入失敗,請重新登入',
}

/** 從 RTK Query 錯誤物件取後端 detail(禁 any,逐層型別守衛) */
function extractDetail(error: unknown): string {
  if (typeof error === 'object' && error !== null && 'data' in error) {
    const data = (error as { data?: unknown }).data
    if (typeof data === 'object' && data !== null && 'detail' in data) {
      const detail = (data as { detail?: unknown }).detail
      if (typeof detail === 'string' && detail !== '') {
        return detail
      }
    }
  }
  return '登入失敗,請稍後再試'
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
        router.replace(nextPath)
      }
    },
    [login, username, password, nextPath, router],
  )

  // 契約 #3(嚴格模式):登入頁 401 只顯示按鈕,禁自動 redirect 到 /authorize
  const ssoConfigured = SSO_URL !== '' && SSO_APP_ID !== ''
  const handleSsoLogin = useCallback((): void => {
    const callbackUrl = `${API_BASE_URL}/sso/callback`
    window.location.assign(
      `${SSO_URL}/api/auth/sso/authorize?client_id=${encodeURIComponent(SSO_APP_ID)}&redirect_uri=${encodeURIComponent(callbackUrl)}`,
    )
  }, [])

  const errorMessage = useMemo((): string | null => {
    if (loginError !== undefined) {
      return extractDetail(loginError)
    }
    if (queryError !== null) {
      return ERROR_MESSAGES[queryError] ?? 'SSO 登入發生錯誤,請重新登入'
    }
    return null
  }, [loginError, queryError])

  return (
    <main className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-md rounded-lg border border-gray-200 bg-white p-6 shadow-sm md:p-8">
        <h1 className="text-xl font-bold text-gray-900 md:text-2xl">
          ETL 管理後台
        </h1>
        <p className="mt-1 text-sm text-gray-600 md:text-base">請登入以繼續</p>

        {loggedOut ? (
          <p className="mt-4 rounded bg-gray-100 px-3 py-2 text-sm text-gray-700 md:text-base">
            已登出
          </p>
        ) : null}
        {errorMessage !== null ? (
          <p
            role="alert"
            className="mt-4 rounded bg-red-50 px-3 py-2 text-sm text-red-700 md:text-base"
          >
            {errorMessage}
          </p>
        ) : null}

        <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4">
          <label className="flex flex-col gap-1">
            <span className="text-sm font-medium text-gray-700 md:text-base">
              帳號
            </span>
            <input
              type="text"
              name="username"
              autoComplete="username"
              required
              value={username}
              onChange={handleUsernameChange}
              className="min-h-[44px] rounded border border-gray-300 px-3 text-sm text-gray-900 md:text-base"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-sm font-medium text-gray-700 md:text-base">
              密碼
            </span>
            <input
              type="password"
              name="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={handlePasswordChange}
              className="min-h-[44px] rounded border border-gray-300 px-3 text-sm text-gray-900 md:text-base"
            />
          </label>
          <button
            type="submit"
            disabled={isLoggingIn || isAuthLoading}
            className="min-h-[44px] rounded bg-gray-900 px-4 text-sm font-medium text-white disabled:opacity-50 md:text-base"
          >
            {isLoggingIn ? '登入中…' : '登入'}
          </button>
        </form>

        <div className="mt-6 flex items-center gap-3">
          <span className="h-px flex-1 bg-gray-200" />
          <span className="text-sm text-gray-500 md:text-base">或</span>
          <span className="h-px flex-1 bg-gray-200" />
        </div>

        <button
          type="button"
          onClick={handleSsoLogin}
          disabled={!ssoConfigured}
          className="mt-4 min-h-[44px] w-full rounded border border-gray-300 px-4 text-sm font-medium text-gray-900 disabled:opacity-50 md:text-base"
        >
          透過 DF-SSO 登入
        </button>
        {!ssoConfigured ? (
          <p className="mt-2 text-sm text-gray-500">
            尚未設定 DF-SSO(NEXT_PUBLIC_SSO_URL / NEXT_PUBLIC_SSO_APP_ID)
          </p>
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
        <main className="flex min-h-screen items-center justify-center">
          <p className="text-sm text-gray-500 md:text-base">載入中…</p>
        </main>
      }
    >
      <LoginContent />
    </Suspense>
  )
}
