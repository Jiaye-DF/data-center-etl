'use client'

import { useEffect, useRef } from 'react'
import { useAppDispatch, useAppSelector } from '@/store/hooks'
import { setTheme } from '@/store/theme-slice'
import {
  applyThemeToDocument,
  isValidThemeId,
  THEME_STORAGE_KEY,
} from '@/lib/theme/themes'

// 主題狀態管理:掛載時自 localStorage / 系統偏好還原,之後每次 theme 變動同步至 <html> 與 localStorage
export function ThemeManager(): null {
  const dispatch = useAppDispatch()
  const theme = useAppSelector((s) => s.theme.theme)
  const restored = useRef(false)

  useEffect(() => {
    if (restored.current) {
      return
    }
    restored.current = true
    try {
      const stored = localStorage.getItem(THEME_STORAGE_KEY)
      if (stored !== null && isValidThemeId(stored)) {
        dispatch(setTheme(stored))
        return
      }
    } catch {
      // 忽略 storage 不可用
    }
    if (typeof window !== 'undefined' && window.matchMedia) {
      const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches
      dispatch(setTheme(isDark ? 'dark' : 'light'))
    }
  }, [dispatch])

  useEffect(() => {
    applyThemeToDocument(theme)
    try {
      localStorage.setItem(THEME_STORAGE_KEY, theme)
    } catch {
      // 忽略 storage 不可用
    }
  }, [theme])

  return null
}
