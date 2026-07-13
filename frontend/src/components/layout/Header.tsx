'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { useAuth } from '@/lib/auth/useAuth'
import { useAppDispatch } from '@/store/hooks'
import { cycleSidebarState, toggleMobileNav } from '@/store/theme-slice'
import { ThemeSwitcher } from './ThemeSwitcher'

const ROLE_LABELS: Record<string, string> = {
  admin: '管理者',
  member: '成員',
}

export function Header(): React.ReactNode {
  const dispatch = useAppDispatch()
  const { user, logout } = useAuth()
  const [menuOpen, setMenuOpen] = useState(false)
  const popRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!menuOpen) {
      return
    }
    const onClickOutside = (event: MouseEvent): void => {
      if (popRef.current && !popRef.current.contains(event.target as Node)) {
        setMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [menuOpen])

  const handleDesktopToggle = useCallback((): void => {
    dispatch(cycleSidebarState())
  }, [dispatch])

  const handleMobileToggle = useCallback((): void => {
    dispatch(toggleMobileNav())
  }, [dispatch])

  const roleLabel =
    user !== null ? (ROLE_LABELS[user.role] ?? user.role) : ''
  const displayName =
    user !== null ? (user.display_name ?? user.username) : ''

  return (
    <header className="sticky top-0 z-50 flex h-14 items-center justify-between border-b border-border bg-card px-4 md:px-6">
      <div className="flex items-center gap-2">
        <button
          type="button"
          aria-label="切換選單"
          onClick={handleDesktopToggle}
          className="hidden h-10 w-10 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground md:inline-flex"
        >
          <MenuIcon />
        </button>
        <button
          type="button"
          aria-label="開關選單"
          onClick={handleMobileToggle}
          className="inline-flex h-10 w-10 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground md:hidden"
        >
          <MenuIcon />
        </button>
        <Link href="/" className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <BrandIcon />
          </span>
          <span className="font-semibold tracking-tight text-foreground">
            DataHub 管理後台
          </span>
        </Link>
      </div>

      <div className="flex items-center gap-2">
        <ThemeSwitcher />
        {user !== null ? (
          <div ref={popRef} className="relative">
            <button
              type="button"
              onClick={() => setMenuOpen((o) => !o)}
              aria-expanded={menuOpen}
              className="flex min-h-[40px] items-center gap-2 rounded-lg px-2 text-sm text-foreground transition-colors hover:bg-muted"
            >
              <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-primary/15 text-sm font-semibold text-primary">
                {displayName.slice(0, 1).toUpperCase()}
              </span>
              <span className="hidden md:inline">{displayName}</span>
            </button>
            {menuOpen ? (
              <div className="absolute right-0 z-50 mt-2 w-60 overflow-hidden rounded-xl border border-border bg-card shadow-lg">
                <div className="px-4 py-3">
                  <p className="font-semibold text-foreground">
                    {displayName}
                  </p>
                  {user.display_name !== null ? (
                    <p className="text-xs text-muted-foreground">
                      {user.username}
                    </p>
                  ) : null}
                  <span className="df-badge mt-1 bg-muted text-muted-foreground">
                    {roleLabel}
                  </span>
                </div>
                <div className="border-t border-border" />
                <button
                  type="button"
                  onClick={logout}
                  className="flex w-full items-center gap-2 px-4 py-3 text-sm text-danger transition-colors hover:bg-muted"
                >
                  <LogoutIcon />
                  登出
                </button>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    </header>
  )
}

function MenuIcon(): React.ReactNode {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M4 6h16M4 12h16M4 18h16" />
    </svg>
  )
}

function BrandIcon(): React.ReactNode {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <ellipse cx="8" cy="6" rx="5" ry="2.2" />
      <path d="M3 6v5c0 1.2 2.24 2.2 5 2.2s5-1 5-2.2V6" />
      <path d="M3 11v5c0 1.2 2.24 2.2 5 2.2" />
      <path d="M15 13h6m0 0-2.5-2.5M21 13l-2.5 2.5" />
    </svg>
  )
}

function LogoutIcon(): React.ReactNode {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <path d="M16 17l5-5-5-5M21 12H9" />
    </svg>
  )
}
