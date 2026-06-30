import type { Metadata } from 'next'
import { StoreProvider } from '@/store/provider'
import './globals.css'

export const metadata: Metadata = {
  title: 'data-center-etl',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="zh-TW">
      <body>
        <StoreProvider>{children}</StoreProvider>
      </body>
    </html>
  )
}
