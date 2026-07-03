'use client'

// 全域錯誤邊界:樣式尚未載入,依規範允許 inline style + 中性色 hex 與最低限硬編碼文字
interface GlobalErrorProps {
  error: Error & { digest?: string }
  reset: () => void
}

export default function GlobalError({
  error,
  reset,
}: GlobalErrorProps): React.ReactNode {
  return (
    <html lang="zh-TW">
      <body
        style={{
          margin: 0,
          minHeight: '100vh',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '16px',
          fontFamily: 'system-ui, sans-serif',
          backgroundColor: '#f9fafb',
          color: '#111827',
        }}
      >
        <h1 style={{ fontSize: '20px', margin: 0 }}>系統發生錯誤</h1>
        <p style={{ fontSize: '16px', margin: 0, color: '#4b5563' }}>
          請重試;若持續發生,請聯絡管理者。
        </p>
        {error.digest !== undefined ? (
          <p style={{ fontSize: '14px', margin: 0, color: '#6b7280' }}>
            digest: {error.digest}
          </p>
        ) : null}
        <button
          type="button"
          onClick={reset}
          style={{
            minHeight: '44px',
            padding: '0 16px',
            fontSize: '16px',
            border: 'none',
            borderRadius: '4px',
            backgroundColor: '#111827',
            color: '#ffffff',
            cursor: 'pointer',
          }}
        >
          重試
        </button>
      </body>
    </html>
  )
}
