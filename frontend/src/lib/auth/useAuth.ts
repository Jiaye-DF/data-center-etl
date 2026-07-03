'use client'

import { useCallback, useMemo } from 'react'
import { API_BASE_URL, useGetMeQuery, type AuthUser, type UserRole } from '@/lib/api/authApi'

export interface UseAuthResult {
  /** 目前登入者;未登入為 null */
  user: AuthUser | null
  role: UserRole | null
  isAdmin: boolean
  /** viewer 角色:各頁面據此隱藏寫入類 UI(010 / 011 使用) */
  isViewer: boolean
  isLoading: boolean
  isAuthenticated: boolean
  /** 登出:整頁導向 backend SSO 登出端點(雙軌通用 — SSO 先通知中央再跟隨 redirect,本地登入僅清 cookie) */
  logout: () => void
}

export function useAuth(): UseAuthResult {
  const { data, isLoading, isSuccess } = useGetMeQuery()

  const logout = useCallback((): void => {
    window.location.assign(`${API_BASE_URL}/sso/logout`)
  }, [])

  return useMemo((): UseAuthResult => {
    const user = isSuccess && data !== undefined ? data : null
    return {
      user,
      role: user?.role ?? null,
      isAdmin: user?.role === 'admin',
      isViewer: user?.role === 'viewer',
      isLoading,
      isAuthenticated: user !== null,
      logout,
    }
  }, [data, isSuccess, isLoading, logout])
}
