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
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 px-4">
      <h1 className="text-xl font-bold text-gray-900 md:text-2xl">
        頁面發生錯誤
      </h1>
      <p className="text-sm text-gray-600 md:text-base">
        很抱歉,處理您的請求時發生錯誤,請重試或聯絡管理者。
      </p>
      {error.digest !== undefined ? (
        <p className="font-mono text-sm text-gray-500">digest: {error.digest}</p>
      ) : null}
      <button
        type="button"
        onClick={reset}
        className="min-h-[44px] rounded bg-gray-900 px-4 text-sm font-medium text-white md:text-base"
      >
        重試
      </button>
    </main>
  )
}
