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
    href: '/tables',
    title: '資料表管理',
    description: 'ETL 表清單、啟用 / 停用、欄位 mapping 與 Comment',
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
      className="flex min-h-[44px] flex-col gap-1 rounded-lg border border-gray-200 bg-white p-4 shadow-sm hover:border-gray-400 md:p-5"
    >
      <span className="text-base font-semibold text-gray-900 md:text-lg">
        {item.title}
      </span>
      <span className="text-sm text-gray-600 md:text-base">
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
        <h1 className="text-xl font-bold text-gray-900 md:text-2xl">總覽</h1>
        {user !== null ? (
          <p className="mt-1 text-sm text-gray-600 md:text-base">
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
