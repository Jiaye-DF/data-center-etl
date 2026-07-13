'use client'

import { useCallback, useEffect, useMemo } from 'react'
import { API_BASE_URL, useGetMeQuery, type AuthUser, type UserRole } from '@/lib/api/authApi'
import {
  clearLastLoginProvider,
  clearReauthAttempts,
  setLastLoginProvider,
} from '@/lib/auth/sso'

export interface UseAuthResult {
  /** 目前登入者;未登入為 null */
  user: AuthUser | null
  role: UserRole | null
  isAdmin: boolean
  /** member 角色:各頁面據此隱藏寫入類 UI(010 / 011 使用) */
  isMember: boolean
  isLoading: boolean
  isAuthenticated: boolean
  /** /me 回 401(session 失效);silent re-auth 只攔截此情況,中央不可達等其他錯誤不觸發 */
  isSessionExpired: boolean
  /** 登出:整頁導向 backend SSO 登出端點(雙軌通用 — SSO 先通知中央再跟隨 redirect,本地登入僅清 cookie) */
  logout: () => void
}

export function useAuth(): UseAuthResult {
  const { data, isLoading, isSuccess, error } = useGetMeQuery()

  const user = isSuccess && data !== undefined ? data : null
  const isSessionExpired =
    typeof error === 'object' &&
    error !== null &&
    'status' in error &&
    error.status === 401

  // me 成功 → 記錄 provider hint(非機密,silent re-auth 分流依據)並歸零 re-auth 計數
  useEffect(() => {
    if (user !== null) {
      setLastLoginProvider(user.provider)
      clearReauthAttempts()
    }
  }, [user])

  const logout = useCallback((): void => {
    clearLastLoginProvider()
    clearReauthAttempts()
    window.location.assign(`${API_BASE_URL}/sso/logout`)
  }, [])

  return useMemo((): UseAuthResult => {
    return {
      user,
      role: user?.role ?? null,
      isAdmin: user?.role === 'admin',
      isMember: user?.role === 'member',
      isLoading,
      isAuthenticated: user !== null,
      isSessionExpired,
      logout,
    }
  }, [user, isLoading, isSessionExpired, logout])
}
