'use client'

import { memo, Suspense, useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useAuth } from '@/lib/auth/useAuth'

// 互鎖註記:本 layout 只屬 task-009;nav 三項(tables / schedules / runs)一次建好,
// task-010 / task-011 各自新增 route 目錄,不回頭改本檔。
interface NavItem {
  href: string
  label: string
}

const NAV_ITEMS: NavItem[] = [
  { href: '/', label: '總覽' },
  { href: '/tables', label: '資料表管理' },
  { href: '/schedules', label: '排程管理' },
  { href: '/runs', label: '執行紀錄' },
]

const ROLE_LABELS: Record<string, string> = {
  admin: '管理者',
  viewer: '檢視者',
}

function isActivePath(pathname: string, href: string): boolean {
  return href === '/' ? pathname === '/' : pathname.startsWith(href)
}

interface SideNavLinkProps {
  item: NavItem
  active: boolean
  onNavigate: () => void
}

const SideNavLink = memo(function SideNavLink({
  item,
  active,
  onNavigate,
}: SideNavLinkProps): React.ReactNode {
  const activeClass = active
    ? 'bg-gray-900 text-white'
    : 'text-gray-700 hover:bg-gray-100'
  return (
    <Link
      href={item.href}
      onClick={onNavigate}
      className={`flex min-h-[44px] items-center rounded px-3 text-sm font-medium md:text-base ${activeClass}`}
    >
      {item.label}
    </Link>
  )
})

interface SideNavProps {
  onNavigate: () => void
}

// usePathname 為 client hook,依規範由外層包 Suspense
function SideNav({ onNavigate }: SideNavProps): React.ReactNode {
  const pathname = usePathname()
  return (
    <nav className="flex flex-col gap-1 px-2 py-2">
      {NAV_ITEMS.map((item) => (
        <SideNavLink
          key={item.href}
          item={item}
          active={isActivePath(pathname, item.href)}
          onNavigate={onNavigate}
        />
      ))}
    </nav>
  )
}

interface MainLayoutProps {
  children: React.ReactNode
}

export default function MainLayout({
  children,
}: MainLayoutProps): React.ReactNode {
  const router = useRouter()
  const { user, isLoading, isAuthenticated, logout } = useAuth()
  const [menuOpen, setMenuOpen] = useState(false)

  const toggleMenu = useCallback((): void => {
    setMenuOpen((open) => !open)
  }, [])

  const closeMenu = useCallback((): void => {
    setMenuOpen(false)
  }, [])

  // auth guard 第二層:cookie 存在但 session 失效(/me 401)→ 回登入頁
  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace('/login')
    }
  }, [isLoading, isAuthenticated, router])

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-gray-500 md:text-base">載入中…</p>
      </div>
    )
  }

  if (!isAuthenticated || user === null) {
    return null
  }

  const roleLabel = ROLE_LABELS[user.role] ?? user.role

  return (
    <div className="flex min-h-screen flex-col bg-gray-50 md:flex-row">
      {/* mobile 頂欄(漢堡選單) */}
      <header className="flex items-center justify-between border-b border-gray-200 bg-white px-4 py-2 md:hidden">
        <span className="text-lg font-bold text-gray-900">ETL 管理後台</span>
        <button
          type="button"
          onClick={toggleMenu}
          aria-label="開關選單"
          aria-expanded={menuOpen}
          className="flex min-h-[44px] min-w-[44px] items-center justify-center rounded text-gray-700 hover:bg-gray-100"
        >
          ☰
        </button>
      </header>

      {/* 側邊導覽:mobile 展開列 / 桌機固定側欄 */}
      <aside
        className={`${menuOpen ? 'flex' : 'hidden'} w-full flex-col border-b border-gray-200 bg-white md:flex md:w-56 md:border-b-0 md:border-r`}
      >
        <div className="hidden px-4 py-4 md:block">
          <span className="text-lg font-bold text-gray-900">ETL 管理後台</span>
        </div>
        <Suspense fallback={null}>
          <SideNav onNavigate={closeMenu} />
        </Suspense>
        <div className="mt-auto flex flex-col gap-2 border-t border-gray-200 px-4 py-3">
          <p className="text-sm text-gray-700 md:text-base">
            {user.username}
            <span className="ml-2 rounded bg-gray-100 px-2 py-0.5 text-sm text-gray-600">
              {roleLabel}
            </span>
          </p>
          <button
            type="button"
            onClick={logout}
            className="min-h-[44px] rounded border border-gray-300 px-3 text-sm font-medium text-gray-700 hover:bg-gray-100 md:text-base"
          >
            登出
          </button>
        </div>
      </aside>

      <main className="flex-1 p-4 md:p-6 lg:p-8">{children}</main>
    </div>
  )
}
