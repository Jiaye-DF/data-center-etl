import { API_BASE_URL, type AuthProvider } from '@/lib/api/authApi'

/** DF-SSO 中央登入器(可公開 env;機密 SSO_APP_SECRET 僅存在後端,禁入前端 bundle) */
const SSO_URL = process.env.NEXT_PUBLIC_SSO_URL ?? ''
const SSO_APP_ID = process.env.NEXT_PUBLIC_SSO_APP_ID ?? ''

/** 非機密 hint:最後一次登入來源(silent re-auth 分流依據) */
const LAST_LOGIN_PROVIDER_KEY = 'last_login_provider'
/** silent re-auth 重試次數(sessionStorage) */
const REAUTH_ATTEMPTS_KEY = 'reauth_attempts'
/** silent re-auth 保留現場(path + query;dashboard 進入點負責復原) */
const REAUTH_RETURN_TO_KEY = 'reauth_return_to'

/** re-auth 重試上限(超過 → 踢登入頁帶 ?error=reauth_failed) */
export const REAUTH_MAX_ATTEMPTS = 2

export function isSsoConfigured(): boolean {
  return SSO_URL !== '' && SSO_APP_ID !== ''
}

/** 組中央 authorize URL(登入頁 SSO 按鈕 / silent re-auth 共用) */
export function buildSsoAuthorizeUrl(): string {
  const callbackUrl = `${API_BASE_URL}/sso/callback`
  return `${SSO_URL}/api/auth/sso/authorize?client_id=${encodeURIComponent(SSO_APP_ID)}&redirect_uri=${encodeURIComponent(callbackUrl)}`
}

export function getLastLoginProvider(): AuthProvider | null {
  if (typeof window === 'undefined') {
    return null
  }
  const value = window.localStorage.getItem(LAST_LOGIN_PROVIDER_KEY)
  return value === 'local' || value === 'sso' ? value : null
}

export function setLastLoginProvider(provider: AuthProvider): void {
  window.localStorage.setItem(LAST_LOGIN_PROVIDER_KEY, provider)
}

export function clearLastLoginProvider(): void {
  window.localStorage.removeItem(LAST_LOGIN_PROVIDER_KEY)
}

/** 累加並回傳 re-auth 次數(呼叫端據此判斷是否超過上限) */
export function incrementReauthAttempts(): number {
  const raw = window.sessionStorage.getItem(REAUTH_ATTEMPTS_KEY)
  const parsed = raw === null ? 0 : Number.parseInt(raw, 10)
  const next = (Number.isNaN(parsed) ? 0 : parsed) + 1
  window.sessionStorage.setItem(REAUTH_ATTEMPTS_KEY, String(next))
  return next
}

export function clearReauthAttempts(): void {
  window.sessionStorage.removeItem(REAUTH_ATTEMPTS_KEY)
}

export function saveReauthReturnTo(pathWithQuery: string): void {
  window.sessionStorage.setItem(REAUTH_RETURN_TO_KEY, pathWithQuery)
}

/** 取出並清除保留現場(復原一次即失效);僅接受站內相對路徑 */
export function consumeReauthReturnTo(): string | null {
  const value = window.sessionStorage.getItem(REAUTH_RETURN_TO_KEY)
  if (value === null) {
    return null
  }
  window.sessionStorage.removeItem(REAUTH_RETURN_TO_KEY)
  if (value.startsWith('/') && !value.startsWith('//')) {
    return value
  }
  return null
}
