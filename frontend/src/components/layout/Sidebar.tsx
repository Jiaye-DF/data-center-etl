'use client'

import { memo } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useAppDispatch, useAppSelector } from '@/store/hooks'
import { closeMobileNav } from '@/store/theme-slice'

interface NavItem {
  href: string
  label: string
  icon: React.ReactNode
}

const NAV_ITEMS: NavItem[] = [
  { href: '/', label: '總覽', icon: <OverviewIcon /> },
  { href: '/raw-data', label: '原始資料管理', icon: <DatabaseIcon /> },
  { href: '/etl-data', label: 'ETL 資料管理', icon: <LayersIcon /> },
  { href: '/schedules', label: '排程管理', icon: <ClockIcon /> },
  { href: '/runs', label: '執行紀錄', icon: <HistoryIcon /> },
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
    <nav className="flex flex-col gap-1 px-2 py-4">
      {NAV_ITEMS.map((item) => (
        <NavLink
          key={item.href}
          item={item}
          active={isActivePath(pathname, item.href)}
          collapsed={collapsed}
          onNavigate={onNavigate}
        />
      ))}
    </nav>
  )
}

export function Sidebar(): React.ReactNode {
  const dispatch = useAppDispatch()
  const sidebarState = useAppSelector((s) => s.theme.sidebarState)
  const mobileOpen = useAppSelector((s) => s.theme.mobileNavOpen)

  const collapsed = sidebarState === 'collapsed'
  const handleNavigate = (): void => {
    dispatch(closeMobileNav())
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
