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
          您目前的帳號為一般成員(member),無權限查看資料中心的資料層設定、同步排程與 ETL 後台資訊。
        </p>
        <p className="mt-2 text-sm text-muted-foreground md:text-base">
          如業務上需要存取,請洽資訊團隊(系統負責團隊)申請權限。
        </p>
        <button type="button" onClick={logout} className="df-btn-outline mt-6 w-full">
          登出
        </button>
      </div>
    </main>
  )
}
