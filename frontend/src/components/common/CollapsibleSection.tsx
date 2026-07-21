'use client'

import { useCallback, useId, useState } from 'react'

/** 可摺疊卡片：標題列（accent bar + 標題 + 收合摘要 + chevron），內容可收合。
 *  原始資料 / ETL 資料管理與語意映射管理共用(v1.5.1 自 DatasetBrowser 抽出)。 */
export function CollapsibleSection({
  title,
  summary,
  defaultOpen = true,
  children,
}: {
  title: string
  summary?: string
  defaultOpen?: boolean
  children: React.ReactNode
}): React.ReactNode {
  const [open, setOpen] = useState(defaultOpen)
  const contentId = useId()
  const toggle = useCallback((): void => setOpen((prev) => !prev), [])
  const hasSummary = summary !== undefined && summary !== ''

  return (
    <div className="df-card p-4 md:p-5">
      <h2 className="m-0">
        <button
          type="button"
          onClick={toggle}
          aria-expanded={open}
          aria-controls={contentId}
          className="flex w-full items-center gap-2 text-left"
        >
          <span aria-hidden className="h-4 w-1 rounded-full bg-primary" />
          <span className="text-sm font-semibold text-foreground md:text-base">
            {title}
          </span>
          {hasSummary ? (
            <span className="ml-auto truncate text-sm font-normal text-muted-foreground">
              {summary}
            </span>
          ) : null}
          <svg
            aria-hidden
            viewBox="0 0 20 20"
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
            className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform ${
              hasSummary ? 'ml-2' : 'ml-auto'
            } ${open ? 'rotate-180' : ''}`}
          >
            <path
              d="M5 7.5 10 12.5 15 7.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      </h2>
      {open ? (
        <div id={contentId} className="mt-4">
          {children}
        </div>
      ) : null}
    </div>
  )
}
