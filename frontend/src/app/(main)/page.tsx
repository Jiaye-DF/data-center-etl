'use client'

import { memo, useEffect } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/lib/auth/useAuth'
import { consumeReauthReturnTo } from '@/lib/auth/sso'

interface SectionItem {
  href: string
  title: string
  description: string
}

const SECTIONS: SectionItem[] = [
  {
    href: '/raw-data',
    title: '原始資料管理',
    description: '瀏覽來源 ERP 原始資料庫的 schema 與資料表結構',
  },
  {
    href: '/etl-data',
    title: 'ETL 資料管理',
    description: '瀏覽 ETL 轉換後的資料中心庫',
  },
  {
    href: '/schedules',
    title: '排程管理',
    description: '排程設定與手動觸發',
  },
  {
    href: '/runs',
    title: '執行紀錄',
    description: '執行紀錄與逐表詳細 log',
  },
]

interface SectionCardProps {
  item: SectionItem
}

const SectionCard = memo(function SectionCard({
  item,
}: SectionCardProps): React.ReactNode {
  return (
    <Link
      href={item.href}
      className="df-card group flex min-h-[44px] flex-col gap-1.5 p-5 transition-all hover:-translate-y-0.5 hover:border-primary hover:shadow-md"
    >
      <span className="flex items-center gap-2 text-base font-semibold text-foreground md:text-lg">
        {item.title}
        <span className="text-muted-foreground transition-transform group-hover:translate-x-0.5">
          →
        </span>
      </span>
      <span className="text-sm text-muted-foreground md:text-base">
        {item.description}
      </span>
    </Link>
  )
})

export default function DashboardPage(): React.ReactNode {
  const router = useRouter()
  const { user } = useAuth()

  // silent re-auth 保留現場復原:登入成功回到 dashboard 時導回原頁(復原一次即清除)
  useEffect(() => {
    const returnTo = consumeReauthReturnTo()
    if (returnTo !== null && returnTo !== '/') {
      router.replace(returnTo)
    }
  }, [router])

  return (
    <section className="mx-auto flex max-w-7xl flex-col gap-6">
      <div>
        <h1 className="text-xl font-bold text-foreground md:text-2xl">總覽</h1>
        {user !== null ? (
          <p className="mt-1 text-sm text-muted-foreground md:text-base">
            歡迎,{user.username}
          </p>
        ) : null}
      </div>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {SECTIONS.map((item) => (
          <SectionCard key={item.href} item={item} />
        ))}
      </div>
    </section>
  )
}
