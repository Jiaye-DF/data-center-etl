'use client'

import { memo } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useAppDispatch, useAppSelector } from '@/store/hooks'
import { closeMobileNav } from '@/store/theme-slice'
import { useAuth } from '@/lib/auth/useAuth'

interface NavItem {
  href: string
  label: string
  icon: React.ReactNode
}

interface NavGroup {
  /** 分組標題;省略代表無標題的頂層項目(如儀表板) */
  title?: string
  items: NavItem[]
}

const NAV_GROUPS: NavGroup[] = [
  {
    items: [{ href: '/', label: '儀表板', icon: <OverviewIcon /> }],
  },
  {
    title: 'ETL 作業',
    items: [
      { href: '/sources', label: '原始資料管理', icon: <DatabaseIcon /> },
      { href: '/sources-hub', label: 'ETL 資料管理', icon: <LayersIcon /> },
      { href: '/schedules', label: 'ETL 排程管理', icon: <ClockIcon /> },
      { href: '/runs', label: 'ETL 執行紀錄', icon: <HistoryIcon /> },
    ],
  },
  {
    title: '語意層',
    items: [
      { href: '/semantic-mappings', label: '語意映射管理', icon: <TagIcon /> },
    ],
  },
  {
    title: '系統管理',
    items: [{ href: '/users', label: '使用者與角色', icon: <UsersIcon /> }],
  },
]

function isActivePath(pathname: string, href: string): boolean {
  return href === '/' ? pathname === '/' : pathname.startsWith(href)
}

interface NavLinkProps {
  item: NavItem
  active: boolean
  collapsed: boolean
  onNavigate: () => void
}

const NavLink = memo(function NavLink({
  item,
  active,
  collapsed,
  onNavigate,
}: NavLinkProps): React.ReactNode {
  const stateClass = active
    ? 'bg-primary/10 text-primary font-medium'
    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
  return (
    <Link
      href={item.href}
      onClick={onNavigate}
      title={collapsed ? item.label : undefined}
      aria-current={active ? 'page' : undefined}
      className={`flex min-h-[44px] items-center gap-3 rounded-xl px-3 text-sm transition-colors md:text-base ${collapsed ? 'justify-center' : ''} ${stateClass}`}
    >
      <span className="shrink-0">{item.icon}</span>
      {collapsed ? null : item.label}
    </Link>
  )
})

interface NavListProps {
  collapsed: boolean
  onNavigate: () => void
}

function NavList({ collapsed, onNavigate }: NavListProps): React.ReactNode {
  const pathname = usePathname()
  return (
    <nav className="flex flex-col gap-4 px-2 py-4">
      {NAV_GROUPS.map((group, index) => (
        <div key={group.title ?? `group-${index}`} className="flex flex-col gap-1">
          {group.title !== undefined ? (
            collapsed ? (
              <div className="mx-auto my-1 h-px w-6 bg-border" aria-hidden />
            ) : (
              <p className="px-3 pb-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground/70">
                {group.title}
              </p>
            )
          ) : null}
          {group.items.map((item) => (
            <NavLink
              key={item.href}
              item={item}
              active={isActivePath(pathname, item.href)}
              collapsed={collapsed}
              onNavigate={onNavigate}
            />
          ))}
        </div>
      ))}
    </nav>
  )
}

export function Sidebar(): React.ReactNode {
  const dispatch = useAppDispatch()
  const sidebarState = useAppSelector((s) => s.theme.sidebarState)
  const mobileOpen = useAppSelector((s) => s.theme.mobileNavOpen)
  const { isAdmin } = useAuth()

  const collapsed = sidebarState === 'collapsed'
  const handleNavigate = (): void => {
    dispatch(closeMobileNav())
  }

  // 非 admin 無任何 ETL 後台導覽項可看,整個側欄不渲染(Header 仍保留供登出)
  if (!isAdmin) {
    return null
  }

  return (
    <>
      {/* 桌機側欄:sticky 於 Header 之下,依三態切換寬度 / 隱藏 */}
      {sidebarState !== 'hidden' ? (
        <aside
          className={`sticky top-14 hidden h-[calc(100vh-3.5rem)] shrink-0 overflow-y-auto border-r border-border bg-card transition-[width] duration-200 ease-out md:block ${collapsed ? 'w-16' : 'w-60'}`}
        >
          <NavList collapsed={collapsed} onNavigate={handleNavigate} />
        </aside>
      ) : null}

      {/* 手機側欄:滑出式抽屜 + 遮罩 */}
      {mobileOpen ? (
        <div className="fixed inset-0 z-40 md:hidden">
          <button
            type="button"
            aria-label="關閉選單"
            onClick={handleNavigate}
            className="absolute inset-0 bg-black/40 backdrop-blur-sm"
          />
          <aside className="absolute top-14 left-0 h-[calc(100vh-3.5rem)] w-64 overflow-y-auto border-r border-border bg-card">
            <NavList collapsed={false} onNavigate={handleNavigate} />
          </aside>
        </div>
      ) : null}
    </>
  )
}

function OverviewIcon(): React.ReactNode {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <rect x="3" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="3" width="7" height="7" rx="1.5" />
      <rect x="3" y="14" width="7" height="7" rx="1.5" />
      <rect x="14" y="14" width="7" height="7" rx="1.5" />
    </svg>
  )
}

function DatabaseIcon(): React.ReactNode {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <ellipse cx="12" cy="5" rx="8" ry="3" />
      <path d="M4 5v6c0 1.66 3.58 3 8 3s8-1.34 8-3V5" />
      <path d="M4 11v6c0 1.66 3.58 3 8 3s8-1.34 8-3v-6" />
    </svg>
  )
}

function LayersIcon(): React.ReactNode {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M12 2 2 7l10 5 10-5-10-5Z" />
      <path d="m2 12 10 5 10-5" />
      <path d="m2 17 10 5 10-5" />
    </svg>
  )
}

function ClockIcon(): React.ReactNode {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </svg>
  )
}

function HistoryIcon(): React.ReactNode {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M3 12a9 9 0 1 0 3-6.7L3 8" />
      <path d="M3 4v4h4" />
      <path d="M12 8v4l3 2" />
    </svg>
  )
}

function TagIcon(): React.ReactNode {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M12.586 2.586A2 2 0 0 0 11.172 2H4a2 2 0 0 0-2 2v7.172a2 2 0 0 0 .586 1.414l8.704 8.704a2.426 2.426 0 0 0 3.42 0l6.58-6.58a2.426 2.426 0 0 0 0-3.42z" />
      <circle cx="7.5" cy="7.5" r="1" />
    </svg>
  )
}

function UsersIcon(): React.ReactNode {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
      <path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  )
}
