'use client'

// 路由級錯誤邊界:禁顯示業務 uid,允許顯示 error.digest
interface ErrorPageProps {
  error: Error & { digest?: string }
  reset: () => void
}

export default function ErrorPage({
  error,
  reset,
}: ErrorPageProps): React.ReactNode {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-background px-4">
      <h1 className="text-xl font-bold text-foreground md:text-2xl">
        頁面發生錯誤
      </h1>
      <p className="text-sm text-muted-foreground md:text-base">
        很抱歉,處理您的請求時發生錯誤,請重試或聯絡管理者。
      </p>
      {error.digest !== undefined ? (
        <p className="font-mono text-sm text-muted-foreground">
          digest: {error.digest}
        </p>
      ) : null}
      <button type="button" onClick={reset} className="df-btn-primary">
        重試
      </button>
    </main>
  )
}
