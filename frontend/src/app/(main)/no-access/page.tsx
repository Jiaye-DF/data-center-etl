'use client'

import { useAuth } from '@/lib/auth/useAuth'

export default function NoAccessPage(): React.ReactNode {
  const { logout } = useAuth()

  return (
    <main className="flex min-h-[60vh] items-center justify-center px-4">
      <div className="df-card w-full max-w-md p-6 text-center md:p-8">
        <span className="mx-auto flex h-11 w-11 items-center justify-center rounded-xl bg-danger/10 text-danger">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
            <circle cx="12" cy="12" r="9" />
            <path d="M12 8v5" />
            <path d="M12 16h.01" />
          </svg>
        </span>
        <h1 className="mt-4 text-xl font-bold text-foreground md:text-2xl">
          無存取權限
        </h1>
        <p className="mt-3 text-sm text-muted-foreground md:text-base">
          您的帳號無此系統的存取權限,如有需要請洽資訊團隊。
        </p>
        <button type="button" onClick={logout} className="df-btn-outline mt-6 w-full">
          登出
        </button>
      </div>
    </main>
  )
}
