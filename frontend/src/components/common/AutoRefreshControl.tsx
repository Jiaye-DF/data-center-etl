'use client'

import { useEffect, useRef, useState } from 'react'
import { formatTime } from '@/utils/datetime'

export interface AutoRefreshControlProps {
  /** 手動重新整理(通常是 RTK Query 的 refetch) */
  onRefresh: () => void
  /** 是否正在抓取資料(true = icon 轉圈) */
  isFetching: boolean
  /** 最後一次成功更新的時間(本地時間;null = 尚未有資料);由 useLastUpdatedAt 產生 */
  lastUpdatedAt: Date | null
  /** 是否正在自動輪詢(false = 已暫停,例如 run 已結束不再輪詢) */
  polling: boolean
  /** 自動輪詢間隔秒數,僅 polling=true 時顯示於文案 */
  intervalSeconds: number
}

/**
 * 追蹤「最後一次成功更新」時間點:isFetching 由 true 轉為 false 視為一次更新完成。
 * 4 個掛載點共用同一顆 hook,避免各自重複寫 useState/useEffect(對齊 05-components.md reuse 規則)。
 */
export function useLastUpdatedAt(isFetching: boolean): Date | null {
  const [lastUpdatedAt, setLastUpdatedAt] = useState<Date | null>(() =>
    isFetching ? null : new Date(),
  )
  const prevFetchingRef = useRef(isFetching)

  useEffect(() => {
    if (prevFetchingRef.current && !isFetching) {
      setLastUpdatedAt(new Date())
    }
    prevFetchingRef.current = isFetching
  }, [isFetching])

  return lastUpdatedAt
}

function pad2(value: number): string {
  return value.toString().padStart(2, '0')
}

// lastUpdatedAt 是前端本地 Date(非後端 ISO 字串),拼成 utils/datetime.ts formatTime() 認得的
// "YYYY-MM-DD HH:mm:ss" 樣式以重用其抽取邏輯,禁止再自行 new Date(...).toLocaleString()
function toWallClockString(date: Date): string {
  return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(
    date.getDate(),
  )} ${pad2(date.getHours())}:${pad2(date.getMinutes())}:${pad2(date.getSeconds())}`
}

function RefreshIcon({ spinning }: { spinning: boolean }): React.ReactNode {
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
      className={spinning ? 'animate-spin' : undefined}
    >
      <path d="M21 12a9 9 0 1 1-2.64-6.36" />
      <path d="M21 3v6h-6" />
    </svg>
  )
}

/**
 * AWS 主控台式重新整理控制列:手動刷新鈕 + 自動更新狀態 + 最後更新時間。
 * 純呈現元件,輪詢由呼叫端的 RTK Query `pollingInterval` 決定,本元件不碰網路。
 */
export function AutoRefreshControl({
  onRefresh,
  isFetching,
  lastUpdatedAt,
  polling,
  intervalSeconds,
}: AutoRefreshControlProps): React.ReactNode {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground md:text-base">
      <button
        type="button"
        onClick={onRefresh}
        disabled={isFetching}
        aria-label="重新整理"
        title="重新整理"
        className="df-btn-outline min-h-[44px] min-w-[44px] px-0 md:min-h-[32px] md:min-w-[32px]"
      >
        <RefreshIcon spinning={isFetching} />
      </button>
      <span>{polling ? `自動更新中(${intervalSeconds}s)` : '已暫停'}</span>
      <span>
        最後更新{' '}
        {lastUpdatedAt === null
          ? '—'
          : formatTime(toWallClockString(lastUpdatedAt))}
      </span>
    </div>
  )
}
