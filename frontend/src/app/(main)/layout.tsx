'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/lib/auth/useAuth'
import { Header } from '@/components/layout/Header'
import { Sidebar } from '@/components/layout/Sidebar'
import {
  buildSsoAuthorizeUrl,
  clearReauthAttempts,
  getLastLoginProvider,
  incrementReauthAttempts,
  isSsoConfigured,
  REAUTH_MAX_ATTEMPTS,
  saveReauthReturnTo,
} from '@/lib/auth/sso'

// silent re-auth 去重 flag(module-level):同頁多個 401 只觸發一次
let reauthInFlight = false

interface MainLayoutProps {
  children: React.ReactNode
}

export default function MainLayout({
  children,
}: MainLayoutProps): React.ReactNode {
  const router = useRouter()
  const { user, isLoading, isAuthenticated, isSessionExpired } = useAuth()

  // 認證恢復後重置去重 flag,讓下一次 401 仍能觸發 re-auth
  useEffect(() => {
    if (isAuthenticated) {
      reauthInFlight = false
    }
  }, [isAuthenticated])

  // auth guard 第二層:工作中 401(session 失效)→ silent re-auth 攔截(08-df-sso § Silent Re-Auth)
  useEffect(() => {
    if (isLoading || isAuthenticated || reauthInFlight) {
      return
    }
    reauthInFlight = true

    // 非 401(中央不可達 502 等)→ 維持回登入頁,不計 re-auth 次數
    if (!isSessionExpired) {
      router.replace('/login')
      return
    }

    const attempts = incrementReauthAttempts()
    if (attempts > REAUTH_MAX_ATTEMPTS) {
      clearReauthAttempts()
      router.replace('/login?error=reauth_failed')
      return
    }

    // 保留現場:登入成功後由 dashboard 進入點復原
    saveReauthReturnTo(window.location.pathname + window.location.search)

    if (getLastLoginProvider() === 'sso' && isSsoConfigured()) {
      // SSO 來源:整頁跳中央 authorize,中央 session 仍在時無感重登
      window.location.href = buildSsoAuthorizeUrl()
    } else {
      router.replace('/login')
    }
  }, [isLoading, isAuthenticated, isSessionExpired, router])

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <p className="text-sm text-muted-foreground md:text-base">載入中…</p>
      </div>
    )
  }

  if (!isAuthenticated || user === null) {
    return null
  }

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <Header />
      <div className="flex flex-1">
        <Sidebar />
        <main className="min-w-0 flex-1 p-4 md:p-6 lg:p-8">{children}</main>
      </div>
    </div>
  )
}
