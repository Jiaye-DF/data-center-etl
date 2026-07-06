'use client'

import { useCallback, useEffect, useState } from 'react'
import { useAppDispatch, useAppSelector } from '@/store/hooks'
import { setTheme } from '@/store/theme-slice'
import { THEMES, type ThemeId, type ThemeItem } from '@/lib/theme/themes'

export function ThemeSwitcher(): React.ReactNode {
  const dispatch = useAppDispatch()
  const current = useAppSelector((s) => s.theme.theme)
  const [open, setOpen] = useState(false)

  const close = useCallback((): void => {
    setOpen(false)
  }, [])

  const handleSelect = useCallback(
    (id: ThemeId): void => {
      dispatch(setTheme(id))
    },
    [dispatch],
  )

  useEffect(() => {
    if (!open) {
      return
    }
    const onKey = (event: KeyboardEvent): void => {
      if (event.key === 'Escape') {
        close()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, close])

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="切換主題"
        className="df-btn-outline min-h-[40px] px-3"
      >
        <PaletteIcon />
        <span className="hidden sm:inline">主題</span>
      </button>

      {open ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          role="dialog"
          aria-modal="true"
          aria-label="選擇主題"
        >
          <button
            type="button"
            aria-label="關閉"
            onClick={close}
            className="absolute inset-0 bg-black/40 backdrop-blur-sm"
          />
          <div className="df-card relative z-10 w-full max-w-2xl p-5 md:p-6">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold text-foreground md:text-xl">
                選擇主題
              </h2>
              <button
                type="button"
                onClick={close}
                aria-label="關閉"
                className="df-btn-outline min-h-[36px] w-9 px-0"
              >
                ✕
              </button>
            </div>
            <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3">
              {THEMES.map((item) => (
                <ThemeCard
                  key={item.id}
                  item={item}
                  active={current === item.id}
                  onSelect={handleSelect}
                />
              ))}
            </div>
          </div>
        </div>
      ) : null}
    </>
  )
}

interface ThemeCardProps {
  item: ThemeItem
  active: boolean
  onSelect: (id: ThemeId) => void
}

function ThemeCard({ item, active, onSelect }: ThemeCardProps): React.ReactNode {
  const handleClick = useCallback((): void => {
    onSelect(item.id)
  }, [onSelect, item.id])

  return (
    <button
      type="button"
      onClick={handleClick}
      aria-pressed={active}
      className={`flex flex-col gap-2 rounded-xl border p-3 text-left transition-all hover:border-primary ${
        active ? 'border-primary ring-2 ring-primary/40' : 'border-border'
      }`}
    >
      <span
        className="flex h-16 w-full overflow-hidden rounded-lg border border-border"
        aria-hidden
      >
        <span
          className="flex flex-1 items-center justify-center text-sm font-semibold"
          style={{
            background: item.preview.background,
            color: item.preview.foreground,
          }}
        >
          Aa
        </span>
        <span className="flex w-1/3 flex-col">
          <span
            className="flex-1"
            style={{ background: item.preview.primary }}
          />
          <span
            className="flex-1"
            style={{ background: item.preview.accent }}
          />
        </span>
      </span>
      <span className="flex items-center gap-2">
        <span className="text-lg leading-none" aria-hidden>
          {item.icon}
        </span>
        <span className="flex flex-col">
          <span className="text-sm font-medium text-foreground">
            {item.labelZh}
          </span>
          <span className="text-sm text-muted-foreground">{item.labelEn}</span>
        </span>
      </span>
    </button>
  )
}

function PaletteIcon(): React.ReactNode {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <circle cx="13.5" cy="6.5" r=".5" fill="currentColor" />
      <circle cx="17.5" cy="10.5" r=".5" fill="currentColor" />
      <circle cx="8.5" cy="7.5" r=".5" fill="currentColor" />
      <circle cx="6.5" cy="12.5" r=".5" fill="currentColor" />
      <path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.926 0 1.648-.746 1.648-1.688 0-.437-.18-.835-.437-1.125-.29-.289-.438-.652-.438-1.125a1.64 1.64 0 0 1 1.668-1.668h1.996c3.051 0 5.555-2.503 5.555-5.554C21.965 6.012 17.461 2 12 2z" />
    </svg>
  )
}
